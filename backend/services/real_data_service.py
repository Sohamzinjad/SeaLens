"""Public, credential-free ingestion helpers for real Sentinel-1 and NOAA AIS data.

The first supported backtest area is the Louisiana Gulf coast.  It deliberately
uses sources that do not require the user to share credentials with seaLens:

* Element 84's public AWS Sentinel-1 GRD STAC catalogue and S3 archive.
* NOAA/BOEM MarineCadastre's daily, one-minute AIS archive.

Downloading a complete AIS day is still large.  ``download_noaa_ais_subset``
therefore requires an explicit opt-in and writes only records inside the chosen
bounds to the local cache.  Nothing is sent to third parties except the public
source requests themselves.
"""
from __future__ import annotations

import csv
import io
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import numpy as np

from backend.models import TelemetryPoint, VesselMetadata, VesselTrack

try:  # Optional until a user starts a NOAA bulk import.
    import zstandard as zstd
except ImportError:  # pragma: no cover - exercised by the API error path.
    zstd = None


SENTINEL_STAC_URL = "https://earth-search.aws.element84.com/v1/search"
SENTINEL_S3_PREFIX = "s3://sentinel-s1-l1c/"
RTC_COG_PREFIX = "https://sentinel-s1-rtc-indigo.s3.us-west-2.amazonaws.com/tiles/RTC/"
NOAA_AIS_URL = "https://noaaocm.blob.core.windows.net/ais/csv2/csv{year}/ais-{day}.csv.zst"


@dataclass(frozen=True)
class HistoricalTestCase:
    """A reproducible public-data case; it is not an asserted spill incident."""

    id: str
    name: str
    bbox: Tuple[float, float, float, float]  # west, south, east, north
    acquisition_start: str
    acquisition_end: str
    chosen_scene_id: str
    chosen_scene_time: str
    ais_day: str
    notes: str


US_GULF_RTC_2020 = HistoricalTestCase(
    id="texas_gulf_2020_01_10",
    name="Texas Gulf Coast — Sentinel-1 RTC / NOAA AIS alignment check",
    bbox=(-95.05, 28.83, -94.69, 29.81),
    acquisition_start="2020-01-10T00:26:30Z",
    acquisition_end="2020-01-10T00:27:00Z",
    chosen_scene_id="S1A_20200110_15RUN_ASC",
    chosen_scene_time="2020-01-10T00:26:44Z",
    ais_day="2020-01-10",
    notes=(
        "A public Sentinel-1A IW dual-polarisation radiometrically terrain-corrected scene covers this AOI. "
        "The same UTC day is present in NOAA MarineCadastre AIS. This is a data "
        "alignment demonstration, not a claim that the scene contains an oil spill."
    ),
)


class RealDataError(RuntimeError):
    """Safe, user-actionable failure returned by the HTTP API."""


def _utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def _validate_bbox(bbox: Iterable[float]) -> Tuple[float, float, float, float]:
    values = tuple(float(value) for value in bbox)
    if len(values) != 4:
        raise RealDataError("bbox must contain [west, south, east, north]")
    west, south, east, north = values
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise RealDataError("bbox must be valid WGS84 coordinates [west, south, east, north]")
    return values


def public_case_manifest() -> Dict[str, Any]:
    """Return the reproducible default case and source/provenance information."""
    return {
        "case": asdict(US_GULF_RTC_2020),
        "sources": {
            "sentinel_catalog": "https://earth-search.aws.element84.com/v1",
            "sentinel_archive": "https://registry.opendata.aws/sentinel-1/",
            "analysis_ready_sentinel_archive": "https://registry.opendata.aws/sentinel-1-rtc-indigo/",
            "ais_archive": "https://marinecadastre.gov/accessais/",
            "ais_bulk_index": "https://noaaocm.blob.core.windows.net/ais/csv2/csv2024/index.html",
        },
        "attribution": "Contains modified Copernicus Sentinel data (2024); AIS data: NOAA/BOEM MarineCadastre.",
        "limitations": [
            "This setup aligns real public SAR and AIS data; it does not label or prove an oil spill.",
            "Raw Sentinel-1 GRD measurement TIFFs require calibration and careful interpretation before operational use.",
            "NOAA AIS is a coastal planning dataset sampled at one-minute intervals and may have receiver coverage gaps.",
        ],
        "recommended_asset": (
            "https://sentinel-s1-rtc-indigo.s3.us-west-2.amazonaws.com/tiles/RTC/1/IW/15/R/UN/2020/"
            "S1A_20200110_15RUN_ASC/Gamma0_VV.tif"
        ),
    }


def search_sentinel_scenes(
    bbox: Iterable[float],
    start: str,
    end: str,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Query the public Sentinel-1 STAC API without credentials."""
    clean_bbox = _validate_bbox(bbox)
    if _utc_timestamp(end) <= _utc_timestamp(start):
        raise RealDataError("end must be after start")
    payload = {
        "collections": ["sentinel-1-grd"],
        "bbox": list(clean_bbox),
        "datetime": f"{start}/{end}",
        "limit": max(1, min(int(limit), 25)),
        "query": {"sar:instrument_mode": {"eq": "IW"}},
    }
    try:
        response = requests.post(SENTINEL_STAC_URL, json=payload, timeout=30)
        response.raise_for_status()
        features = response.json().get("features", [])
    except requests.RequestException as exc:
        raise RealDataError(f"Public Sentinel-1 catalogue request failed: {exc}") from exc

    scenes: List[Dict[str, Any]] = []
    for feature in features:
        assets = feature.get("assets", {})
        scenes.append({
            "id": feature.get("id"),
            "acquisition_time": feature.get("properties", {}).get("datetime"),
            "platform": feature.get("properties", {}).get("platform"),
            "mode": feature.get("properties", {}).get("sar:instrument_mode"),
            "polarizations": feature.get("properties", {}).get("sar:polarizations", []),
            "bbox": feature.get("bbox"),
            "thumbnail_url": assets.get("thumbnail", {}).get("href"),
            "vv_asset": assets.get("vv", {}).get("href"),
            "vh_asset": assets.get("vh", {}).get("href"),
        })
    return scenes


def _sentinel_asset_is_allowed(asset_url: str) -> bool:
    raw_grd = asset_url.startswith(SENTINEL_S3_PREFIX) and "/measurement/" in asset_url and asset_url.endswith(".tiff")
    analysis_ready = asset_url.startswith(RTC_COG_PREFIX) and asset_url.endswith(".tif")
    return raw_grd or analysis_ready


def download_sentinel_crop(
    asset_url: str,
    bbox: Iterable[float],
    output_path: str,
    max_pixels: int = 2048,
) -> Dict[str, Any]:
    """Read a small WGS84 crop from the public AWS GRD archive into a GeoTIFF.

    Rasterio/GDAL performs HTTP range reads, avoiding a full scene download.
    Georeferenced RTC COG assets can be processed directly. Raw GRD measurement
    assets are discoverable but intentionally rejected here because their TIFF
    pixels have no CRS; they require SAFE annotation/calibration first.
    """
    if not _sentinel_asset_is_allowed(asset_url):
        raise RealDataError("Only public sentinel-s1-l1c measurement TIFF assets are permitted")
    clean_bbox = _validate_bbox(bbox)
    if not 128 <= max_pixels <= 4096:
        raise RealDataError("max_pixels must be between 128 and 4096")
    try:
        import rasterio
        from rasterio.enums import Resampling
        from rasterio.transform import array_bounds
        from rasterio.windows import from_bounds
        from rasterio.warp import calculate_default_transform, reproject, transform_bounds
    except ImportError as exc:  # pragma: no cover - dependency is production-required.
        raise RealDataError("rasterio is required to crop Sentinel-1 data") from exc

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", AWS_REGION="eu-central-1"):
            with rasterio.open(asset_url) as source:
                if source.crs is None:
                    raise RealDataError(
                        "This raw GRD measurement TIFF has no georeferencing. Select an analysis-ready RTC COG "
                        "or process the complete SAFE product with its annotation/calibration metadata."
                    )
                projected_bounds = transform_bounds("EPSG:4326", source.crs, *clean_bbox, densify_pts=21)
                window = from_bounds(*projected_bounds, transform=source.transform).round_offsets().round_lengths()
                window = window.intersection(rasterio.windows.Window(0, 0, source.width, source.height))
                if window.width <= 0 or window.height <= 0:
                    raise RealDataError("Requested crop does not intersect the Sentinel-1 scene")
                scale = min(1.0, max_pixels / max(window.width, window.height))
                out_width = max(1, int(round(window.width * scale)))
                out_height = max(1, int(round(window.height * scale)))
                data = source.read(1, window=window, out_shape=(out_height, out_width), resampling=Resampling.average)
                source_transform = source.window_transform(window) * source.transform.scale(window.width / out_width, window.height / out_height)
                source_bounds = array_bounds(out_height, out_width, source_transform)
                transform, write_width, write_height = calculate_default_transform(
                    source.crs, "EPSG:4326", out_width, out_height, *source_bounds
                )
                geographic = np.zeros((write_height, write_width), dtype=data.dtype)
                reproject(
                    source=data,
                    destination=geographic,
                    src_transform=source_transform,
                    src_crs=source.crs,
                    dst_transform=transform,
                    dst_crs="EPSG:4326",
                    resampling=Resampling.average,
                )
                profile = source.profile.copy()
                profile.update(
                    driver="GTiff", count=1, height=write_height, width=write_width,
                    transform=transform, crs="EPSG:4326", compress="deflate"
                )
                with rasterio.open(output_path, "w", **profile) as destination:
                    destination.write(geographic, 1)
                crop_bounds = array_bounds(write_height, write_width, transform)
    except RealDataError:
        raise
    except Exception as exc:
        raise RealDataError(f"Unable to read the public Sentinel-1 crop: {exc}") from exc
    return {
        "output_path": output_path,
        "source_asset": asset_url,
        "raw_measurement": asset_url.startswith(SENTINEL_S3_PREFIX),
        "analysis_ready_rtc": asset_url.startswith(RTC_COG_PREFIX),
        "shape": [write_height, write_width],
        "crs": str(profile.get("crs")),
        "bounds_in_scene_crs": [round(value, 3) for value in crop_bounds],
        "attribution": "Contains modified Copernicus Sentinel data (2024).",
    }


def noaa_daily_ais_url(day: str) -> str:
    try:
        parsed = date.fromisoformat(day)
    except ValueError as exc:
        raise RealDataError("AIS day must use YYYY-MM-DD") from exc
    if parsed.year < 2009 or parsed > date.today():
        raise RealDataError("AIS day is outside the supported NOAA archive range")
    return NOAA_AIS_URL.format(year=parsed.year, day=parsed.isoformat())


def _row_in_bbox(row: Dict[str, str], bbox: Tuple[float, float, float, float]) -> bool:
    try:
        longitude, latitude = float(row["LON"]), float(row["LAT"])
    except (KeyError, TypeError, ValueError):
        return False
    west, south, east, north = bbox
    return west <= longitude <= east and south <= latitude <= north


def _row_in_time_range(row: Dict[str, str], start: Optional[str], end: Optional[str]) -> bool:
    if not start and not end:
        return True
    try:
        observed = _utc_timestamp(row["BaseDateTime"])
    except (KeyError, TypeError, ValueError):
        return False
    return (not start or observed >= _utc_timestamp(start)) and (not end or observed <= _utc_timestamp(end))


def download_noaa_ais_subset(
    day: str,
    bbox: Iterable[float],
    output_path: str,
    max_records: int = 20_000,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Stream one NOAA AIS day and cache only the requested geographic subset."""
    if zstd is None:
        raise RealDataError("Install the zstandard package before importing NOAA AIS archives")
    clean_bbox = _validate_bbox(bbox)
    if start_time and end_time and _utc_timestamp(end_time) <= _utc_timestamp(start_time):
        raise RealDataError("AIS end_time must be after start_time")
    if not 1 <= max_records <= 100_000:
        raise RealDataError("max_records must be between 1 and 100000")
    url = noaa_daily_ais_url(day)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    matched = 0
    scanned = 0
    try:
        with requests.get(url, stream=True, timeout=(20, 180)) as response:
            response.raise_for_status()
            with zstd.ZstdDecompressor().stream_reader(response.raw) as binary_stream:
                text_stream = io.TextIOWrapper(binary_stream, encoding="utf-8", newline="")
                reader = csv.DictReader(text_stream)
                with open(output_path, "w", encoding="utf-8", newline="") as output:
                    writer: Optional[csv.DictWriter] = None
                    for row in reader:
                        scanned += 1
                        if not _row_in_bbox(row, clean_bbox) or not _row_in_time_range(row, start_time, end_time):
                            continue
                        if writer is None:
                            writer = csv.DictWriter(output, fieldnames=reader.fieldnames or list(row))
                            writer.writeheader()
                        writer.writerow(row)
                        matched += 1
                        if matched >= max_records:
                            break
    except requests.RequestException as exc:
        raise RealDataError(f"NOAA AIS download failed: {exc}") from exc
    return {
        "output_path": output_path,
        "source_url": url,
        "records_kept": matched,
        "records_scanned": scanned,
        "truncated_at_max_records": matched >= max_records,
        "time_window_utc": {"start": start_time, "end": end_time},
        "attribution": "NOAA/BOEM MarineCadastre AIS data; one-minute broadcast records.",
    }


AIS_TYPE_NAMES = {
    30: "Fishing Vessel", 31: "Tugboat", 32: "Tugboat", 36: "Pleasure Craft",
    37: "Pleasure Craft", 52: "Tugboat", 60: "Passenger / Cruise", 69: "Passenger / Cruise",
    70: "General Cargo", 71: "General Cargo", 72: "General Cargo", 79: "General Cargo",
    80: "Oil Products Tanker", 81: "Chemical Tanker", 82: "Crude Oil Tanker",
    83: "Oil Products Tanker", 84: "Oil Products Tanker", 89: "Oil Products Tanker",
}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _ship_type_from_ais(value: Any) -> str:
    code = _as_int(value, -1)
    return AIS_TYPE_NAMES.get(code, "General Cargo")


def _nav_status(value: Any) -> str:
    labels = {
        0: "Under way using engine", 1: "At anchor", 2: "Not under command",
        3: "Restricted maneuverability", 5: "Moored", 6: "Aground",
    }
    return labels.get(_as_int(value, -1), "Unknown")


def load_noaa_ais_tracks(
    filepath: str,
    max_vessels: int = 500,
    min_positions: int = 1,
) -> List[VesselTrack]:
    """Normalize a locally cached NOAA subset into existing AIS vessel tracks.

    NOAA's CSV describes broadcast positions, not verified vessel registries.
    Missing metadata is retained as an explicit ``UNKNOWN`` label rather than
    invented.  The cap is intentional: this is a demo/investigation endpoint,
    not a replacement for PostGIS-scale indexing.
    """
    if not os.path.isfile(filepath):
        raise RealDataError("AIS subset was not found. Import the NOAA subset first.")
    if not 1 <= max_vessels <= 2_000:
        raise RealDataError("max_vessels must be between 1 and 2000")
    grouped: Dict[int, List[Dict[str, str]]] = {}
    try:
        with open(filepath, encoding="utf-8", newline="") as source:
            for row in csv.DictReader(source):
                mmsi = _as_int(row.get("MMSI"), 0)
                timestamp = row.get("BaseDateTime", "")
                if not mmsi or not timestamp:
                    continue
                # Validate required movement/location values before model creation.
                try:
                    float(row["LAT"]); float(row["LON"])
                    _utc_timestamp(timestamp)
                except (KeyError, TypeError, ValueError):
                    continue
                grouped.setdefault(mmsi, []).append(row)
    except OSError as exc:
        raise RealDataError(f"Unable to read local AIS subset: {exc}") from exc

    tracks: List[VesselTrack] = []
    # Prioritize tracks with enough positions for a behavioral signal.
    ordered_groups = sorted(grouped.items(), key=lambda item: len(item[1]), reverse=True)
    for mmsi, rows in ordered_groups:
        rows.sort(key=lambda row: row["BaseDateTime"])
        if len(rows) < min_positions:
            continue
        first = rows[0]
        positions = [TelemetryPoint(
            timestamp=row["BaseDateTime"].replace("+00:00", "Z"),
            lat=_as_float(row.get("LAT")),
            lng=_as_float(row.get("LON")),
            sog=_as_float(row.get("SOG")),
            cog=_as_float(row.get("COG")),
            heading=_as_float(row.get("Heading")) if row.get("Heading") not in (None, "", "511") else None,
            nav_status=_nav_status(row.get("Status")),
            draught_m=_as_float(row.get("Draft")) if row.get("Draft") not in (None, "") else None,
        ) for row in rows]
        tracks.append(VesselTrack(
            metadata=VesselMetadata(
                mmsi=mmsi,
                imo=_as_int(first.get("IMO")) or None,
                name=(first.get("VesselName") or f"MMSI {mmsi}").strip(),
                callsign=(first.get("CallSign") or "").strip() or None,
                ship_type=_ship_type_from_ais(first.get("VesselType")),
                flag="UNKNOWN (NOAA AIS)",
                length_m=_as_float(first.get("Length")),
                beam_m=_as_float(first.get("Width")),
                gross_tonnage=0,
            ),
            positions=positions,
        ))
        if len(tracks) >= max_vessels:
            break
    return tracks
