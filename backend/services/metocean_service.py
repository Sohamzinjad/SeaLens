"""Real met-ocean fields with a transparent offline fallback.

The operational path deliberately separates the two public data providers:

* NOAA NOMADS GFS supplies 10 m wind components (``UGRD``/``VGRD``) without
  credentials.  Small GRIB2 subsets are cached per incident.
* Copernicus Marine supplies surface-current components (``uo``/``vo``).  Its
  official toolbox needs a free account, so it is used only when credentials
  have been configured locally.  No credentials are accepted by this API.

Both data sets are sampled with spatial bilinear interpolation and linear time
interpolation at each 15-minute drift step.  If either source is unavailable,
``DynamicOceanGridEngine`` remains the explicit offline/demo fallback; callers
receive provenance fields which make that distinction visible.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import requests

from backend.services.ocean_grid_engine import DynamicOceanGridEngine


GFS_FILTER_URL = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
DEFAULT_CMEMS_DATASET = "cmems_mod_glo_phy_anfc_0.083deg_PT1H-m"


class MetOceanError(RuntimeError):
    """A safe failure which can be shown in an API response."""


def _utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def _safe_incident_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    return safe[:80] or "incident"


def _expanded_bbox(bbox: Iterable[float], margin_deg: float = 0.30) -> Tuple[float, float, float, float]:
    west, south, east, north = (float(item) for item in bbox)
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise MetOceanError("bbox must be [west, south, east, north] in WGS84")
    return (
        max(-180.0, west - margin_deg), max(-90.0, south - margin_deg),
        min(180.0, east + margin_deg), min(90.0, north + margin_deg),
    )


class RealMetOceanGridEngine:
    """A drift-grid adapter backed by cached GFS and optional Copernicus fields."""

    def __init__(self, cache_root: str | Path = "data_samples/metocean_cache") -> None:
        self.cache_root = Path(cache_root)
        self.fallback = DynamicOceanGridEngine()
        self._incident_dir: Optional[Path] = None
        self._status: Dict[str, Any] = {}

    @staticmethod
    def credentials_configured() -> bool:
        return bool(
            os.getenv("COPERNICUSMARINE_SERVICE_USERNAME")
            and os.getenv("COPERNICUSMARINE_SERVICE_PASSWORD")
        )

    def provider_status(self) -> Dict[str, Any]:
        return {
            "gfs_wind": {
                "provider": "NOAA NOMADS GFS 0.25 degree",
                "credential_required": False,
                "source": "https://nomads.ncep.noaa.gov/",
            },
            "copernicus_currents": {
                "provider": "Copernicus Marine Toolbox",
                "credential_required": True,
                "credentials_configured": self.credentials_configured(),
                "dataset": os.getenv("SEALENS_CMEMS_DATASET_ID", DEFAULT_CMEMS_DATASET),
                "source": "https://toolbox-docs.marine.copernicus.eu/en/stable/usage/quickoverview.html",
            },
            "offline_fallback": "DynamicOceanGridEngine (modelled wind/current pattern; not observed data)",
            "last_prepare": self._status or None,
        }

    def prepare_incident(
        self,
        incident_id: str,
        bbox: Iterable[float],
        detection_timestamp: str,
        history_hours: float = 6.0,
        forecast_hours: float = 0.0,
        fetch_copernicus: bool = True,
    ) -> Dict[str, Any]:
        """Cache the minimum provider subsets needed around one incident.

        GFS is a forecast product.  It is suitable for current/near-future
        investigations, not a source of 2020 backtest winds.  The method makes
        that limit explicit rather than silently substituting present-day data.
        """
        incident_dir = self.cache_root / _safe_incident_id(incident_id)
        incident_dir.mkdir(parents=True, exist_ok=True)
        self._incident_dir = incident_dir
        when = _utc(detection_timestamp)
        clean_bbox = _expanded_bbox(bbox)
        now = datetime.now(timezone.utc)
        warnings: List[str] = []
        gfs_files: List[str] = []
        cmems_file: Optional[str] = None

        # NOMADS operational GFS is not an archive.  Keep backtests honest.
        if when < now - timedelta(hours=36) or when > now + timedelta(days=10):
            warnings.append(
                "NOAA GFS was not fetched: the requested incident is outside the operational forecast window. "
                "Use a Copernicus historical/reanalysis dataset (configured locally) for historical backtesting."
            )
        else:
            try:
                gfs_files = self._cache_gfs_wind(incident_dir, clean_bbox, when, history_hours, forecast_hours)
            except MetOceanError as exc:
                warnings.append(f"NOAA GFS wind unavailable; using modelled wind fallback: {exc}")

        if fetch_copernicus:
            if self.credentials_configured():
                try:
                    cmems_file = self._cache_copernicus_currents(
                        incident_dir, clean_bbox, when, history_hours, forecast_hours
                    )
                except MetOceanError as exc:
                    warnings.append(f"Copernicus current unavailable; using modelled current fallback: {exc}")
            else:
                warnings.append(
                    "Copernicus Marine credentials are not configured locally; using the modelled current fallback."
                )

        self._status = {
            "incident_id": _safe_incident_id(incident_id),
            "detection_timestamp": when.isoformat().replace("+00:00", "Z"),
            "bbox": list(clean_bbox),
            "gfs_wind_cache_files": [Path(path).name for path in gfs_files],
            "copernicus_current_cache_file": Path(cmems_file).name if cmems_file else None,
            "warnings": warnings,
            "wind_source": "NOAA GFS cached grid" if gfs_files else "modelled fallback",
            "current_source": "Copernicus Marine cached grid" if cmems_file else "modelled fallback",
        }
        return self._status

    def _cache_gfs_wind(
        self,
        incident_dir: Path,
        bbox: Tuple[float, float, float, float],
        when: datetime,
        history_hours: float,
        forecast_hours: float,
    ) -> List[str]:
        # GFS output is hourly; 15-minute particles are time-interpolated later.
        start = when - timedelta(hours=max(0.0, history_hours))
        end = when + timedelta(hours=max(0.0, forecast_hours))
        targets: List[datetime] = []
        cursor = start.replace(minute=0, second=0, microsecond=0)
        if cursor > start:
            cursor -= timedelta(hours=1)
        while cursor <= end + timedelta(hours=1):
            targets.append(cursor)
            cursor += timedelta(hours=1)
        written: List[str] = []
        unavailable: List[str] = []
        for target in targets:
            output = incident_dir / f"gfs_wind_{target.strftime('%Y%m%dT%H00Z')}.npz"
            if output.exists():
                written.append(str(output))
                continue
            raw = incident_dir / f"gfs_wind_{target.strftime('%Y%m%dT%H00Z')}.grib2"
            try:
                self._download_gfs_subset(target, bbox, raw)
                self._convert_grib_to_npz(raw, output, ("u10", "v10"))
                written.append(str(output))
            except MetOceanError as exc:
                # Fresh model cycles can take time to appear on NOMADS. Keep
                # already available neighbouring forecast hours for 15-minute
                # interpolation rather than discarding the whole incident cache.
                unavailable.append(target.strftime("%Y-%m-%dT%HZ"))
            finally:
                raw.unlink(missing_ok=True)
        if not written:
            suffix = f" (unavailable: {', '.join(unavailable)})" if unavailable else ""
            raise MetOceanError(f"No requested GFS wind fields were available{suffix}")
        return written

    def _download_gfs_subset(self, target: datetime, bbox: Tuple[float, float, float, float], output: Path) -> None:
        # Select the run immediately before target; it supplies f000..f005.  A
        # recent run may not be published yet, in which case the caller falls
        # back rather than using made-up values.
        run_hour = (target.hour // 6) * 6
        run = target.replace(hour=run_hour, minute=0, second=0, microsecond=0)
        forecast_hour = int((target - run).total_seconds() // 3600)
        west, south, east, north = bbox
        # NOMADS longitudes are degrees east.  This app currently rejects AOIs
        # crossing the antimeridian in _expanded_bbox.
        west_east = west % 360
        east_east = east % 360
        if east_east < west_east:
            raise MetOceanError("GFS subset cannot cross the antimeridian")
        params = {
            "file": f"gfs.t{run_hour:02d}z.pgrb2.0p25.f{forecast_hour:03d}",
            "lev_10_m_above_ground": "on",
            "var_UGRD": "on",
            "var_VGRD": "on",
            "subregion": "",
            "leftlon": f"{west_east:.3f}", "rightlon": f"{east_east:.3f}",
            "toplat": f"{north:.3f}", "bottomlat": f"{south:.3f}",
            "dir": f"/gfs.{run.strftime('%Y%m%d')}/{run_hour:02d}/atmos",
        }
        try:
            response = requests.get(GFS_FILTER_URL, params=params, timeout=60)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise MetOceanError(f"NOMADS request failed: {exc}") from exc
        # A successful error page is still HTTP 200 on some NOMADS mirrors.
        if len(response.content) < 100 or response.content[:2] != b"GR":
            raise MetOceanError("NOMADS returned no GRIB2 data for the requested run/time")
        output.write_bytes(response.content)

    @staticmethod
    def _convert_grib_to_npz(raw_path: Path, output_path: Path, variables: Tuple[str, str]) -> None:
        try:
            import xarray as xr
        except ImportError as exc:  # pragma: no cover - dependency is in requirements.
            raise MetOceanError("xarray/cfgrib is required to decode the cached GFS subset") from exc
        try:
            dataset = xr.open_dataset(raw_path, engine="cfgrib")
            lat_name = "latitude" if "latitude" in dataset.coords else "lat"
            lon_name = "longitude" if "longitude" in dataset.coords else "lon"
            available = list(dataset.data_vars)
            u_name = next((name for name in variables if name in dataset.data_vars), None)
            v_name = next((name for name in variables[::-1] if name in dataset.data_vars), None)
            if not u_name or not v_name:
                raise MetOceanError(f"Decoded GFS subset lacks u10/v10 fields (found {available})")
            valid_time = dataset.coords.get("valid_time", dataset.coords.get("time"))
            timestamp = float(np.asarray(valid_time.values).astype("datetime64[s]").astype(np.int64).reshape(-1)[0])
            np.savez_compressed(
                output_path,
                lat=np.asarray(dataset[lat_name].values, dtype=float),
                lon=np.asarray(dataset[lon_name].values, dtype=float),
                time=np.array([timestamp], dtype=float),
                u=np.asarray(dataset[u_name].values, dtype=float).squeeze()[None, ...],
                v=np.asarray(dataset[v_name].values, dtype=float).squeeze()[None, ...],
            )
        except MetOceanError:
            raise
        except Exception as exc:
            raise MetOceanError(f"Could not decode GFS GRIB2 subset: {exc}") from exc

    def _cache_copernicus_currents(
        self,
        incident_dir: Path,
        bbox: Tuple[float, float, float, float],
        when: datetime,
        history_hours: float,
        forecast_hours: float,
    ) -> str:
        try:
            import copernicusmarine
        except ImportError as exc:  # pragma: no cover - optional until credentials are added.
            raise MetOceanError("copernicusmarine is not installed; install project requirements") from exc
        raw_path = incident_dir / "copernicus_surface_currents.nc"
        output_path = incident_dir / "copernicus_surface_currents.npz"
        if output_path.exists():
            return str(output_path)
        west, south, east, north = bbox
        try:
            # Credentials are read only from the user's local environment by the
            # official toolbox. They are never included in responses or cache files.
            result = copernicusmarine.subset(
                dataset_id=os.getenv("SEALENS_CMEMS_DATASET_ID", DEFAULT_CMEMS_DATASET),
                username=os.environ["COPERNICUSMARINE_SERVICE_USERNAME"],
                password=os.environ["COPERNICUSMARINE_SERVICE_PASSWORD"],
                variables=["uo", "vo"],
                minimum_longitude=west, maximum_longitude=east,
                minimum_latitude=south, maximum_latitude=north,
                minimum_depth=0, maximum_depth=0,
                start_datetime=(when - timedelta(hours=max(0.0, history_hours))).isoformat(),
                end_datetime=(when + timedelta(hours=max(0.0, forecast_hours))).isoformat(),
                output_directory=str(incident_dir),
                output_filename=raw_path.name,
                overwrite=True,
            )
            candidate = Path(str(result)) if result else raw_path
            if not candidate.exists():
                candidate = raw_path
            self._convert_netcdf_to_npz(candidate, output_path, ("uo", "vo"))
            return str(output_path)
        except MetOceanError:
            raise
        except Exception as exc:
            raise MetOceanError(f"Copernicus Marine subset failed: {exc}") from exc

    @staticmethod
    def _convert_netcdf_to_npz(raw_path: Path, output_path: Path, variables: Tuple[str, str]) -> None:
        try:
            import xarray as xr
            dataset = xr.open_dataset(raw_path)
            lat_name = next(name for name in ("latitude", "lat") if name in dataset.coords)
            lon_name = next(name for name in ("longitude", "lon") if name in dataset.coords)
            time_name = next(name for name in ("time", "valid_time") if name in dataset.coords)
            u_name, v_name = variables
            if u_name not in dataset.data_vars or v_name not in dataset.data_vars:
                raise MetOceanError(f"Current subset lacks {u_name}/{v_name}")
            # The subset is surface-only; squeeze a singleton depth dimension if supplied.
            u = np.asarray(dataset[u_name].squeeze(drop=True).values, dtype=float)
            v = np.asarray(dataset[v_name].squeeze(drop=True).values, dtype=float)
            if u.ndim == 2:
                u, v = u[None, ...], v[None, ...]
            timestamps = np.asarray(dataset[time_name].values).astype("datetime64[s]").astype(np.int64)
            np.savez_compressed(
                output_path,
                lat=np.asarray(dataset[lat_name].values, dtype=float),
                lon=np.asarray(dataset[lon_name].values, dtype=float),
                time=np.asarray(timestamps, dtype=float), u=u, v=v,
            )
        except MetOceanError:
            raise
        except Exception as exc:
            raise MetOceanError(f"Could not read Copernicus current subset: {exc}") from exc

    @staticmethod
    def _sample_grid(path: Path, lat: float, lon: float, unix_seconds: float) -> Optional[Tuple[float, float]]:
        try:
            with np.load(path) as grid:
                lats = np.asarray(grid["lat"], dtype=float)
                lons = np.asarray(grid["lon"], dtype=float)
                times = np.asarray(grid["time"], dtype=float).reshape(-1)
                u = np.asarray(grid["u"], dtype=float)
                v = np.asarray(grid["v"], dtype=float)
        except (OSError, KeyError, ValueError):
            return None
        if lats.size < 2 or lons.size < 2 or times.size < 1:
            return None
        # Align to whichever longitude convention the provider used.
        sample_lon = lon % 360 if np.nanmax(lons) > 180 else lon
        order_lat, order_lon, order_time = np.argsort(lats), np.argsort(lons), np.argsort(times)
        lats, lons, times = lats[order_lat], lons[order_lon], times[order_time]
        u, v = u[order_time][:, order_lat][:, :, order_lon], v[order_time][:, order_lat][:, :, order_lon]
        if not (lats[0] <= lat <= lats[-1] and lons[0] <= sample_lon <= lons[-1]):
            return None

        def indices(axis: np.ndarray, value: float) -> Tuple[int, int, float]:
            upper = int(np.searchsorted(axis, value, side="right"))
            upper = min(max(upper, 1), len(axis) - 1)
            lower = upper - 1
            fraction = (value - axis[lower]) / (axis[upper] - axis[lower])
            return lower, upper, float(np.clip(fraction, 0.0, 1.0))

        y0, y1, fy = indices(lats, lat)
        x0, x1, fx = indices(lons, sample_lon)
        # If time is outside this small cached field, do not extrapolate.
        if unix_seconds < times[0] or unix_seconds > times[-1]:
            return None
        if len(times) == 1:
            t0 = t1 = 0
            ft = 0.0
        else:
            t0, t1, ft = indices(times, unix_seconds)

        def bilinear(field: np.ndarray, index: int) -> float:
            values = field[index]
            return float(
                values[y0, x0] * (1 - fx) * (1 - fy)
                + values[y0, x1] * fx * (1 - fy)
                + values[y1, x0] * (1 - fx) * fy
                + values[y1, x1] * fx * fy
            )

        u0, u1 = bilinear(u, t0), bilinear(u, t1)
        v0, v1 = bilinear(v, t0), bilinear(v, t1)
        if not all(math.isfinite(value) for value in (u0, u1, v0, v1)):
            return None
        return (u0 * (1 - ft) + u1 * ft, v0 * (1 - ft) + v1 * ft)

    def _find_sample(self, prefix: str, lat: float, lng: float, unix_seconds: float) -> Optional[Tuple[float, float]]:
        if not self._incident_dir or not self._incident_dir.exists():
            return None
        candidates = sorted(self._incident_dir.glob(f"{prefix}*.npz"))
        samples = [self._sample_grid(path, lat, lng, unix_seconds) for path in candidates]
        valid = [sample for sample in samples if sample is not None]
        # Hourly GFS files each have a single time.  Nearby fields are combined
        # in _sample_grid only when they are written as one CMEMS file, so pick
        # the closest hourly cache here. Fifteen-minute interpolation happens by
        # treating the two neighbouring files as one temporal pair below.
        if prefix == "gfs_wind_" and len(candidates) >= 2:
            timed: List[Tuple[float, Path]] = []
            for path in candidates:
                try:
                    with np.load(path) as item:
                        timed.append((float(np.asarray(item["time"]).reshape(-1)[0]), path))
                except (OSError, KeyError, ValueError):
                    continue
            timed.sort()
            before = [entry for entry in timed if entry[0] <= unix_seconds]
            after = [entry for entry in timed if entry[0] >= unix_seconds]
            if before and after:
                left, right = before[-1], after[0]
                a = self._sample_grid(left[1], lat, lng, left[0])
                b = self._sample_grid(right[1], lat, lng, right[0])
                if a and b:
                    ratio = 0.0 if left[0] == right[0] else (unix_seconds - left[0]) / (right[0] - left[0])
                    return (a[0] * (1 - ratio) + b[0] * ratio, a[1] * (1 - ratio) + b[1] * ratio)
        return valid[0] if valid else None

    def get_interpolated_vectors(
        self, lat: float, lng: float, hour_offset: float, base_wind_speed: float,
        base_wind_deg: float, base_current_speed: float, base_current_deg: float,
        leeway_factor: float = 0.032, coriolis_deg: float = 2.0,
    ) -> Dict[str, Any]:
        """Return actual cached vectors where available, otherwise modelled vectors.

        ``hour_offset`` is Unix hours, as supplied by :class:`DriftEngine`.
        """
        fallback = self.fallback.get_interpolated_vectors(
            lat, lng, hour_offset, base_wind_speed, base_wind_deg,
            base_current_speed, base_current_deg, leeway_factor, coriolis_deg,
        )
        timestamp = hour_offset * 3600.0
        wind = self._find_sample("gfs_wind_", lat, lng, timestamp)
        current = self._find_sample("copernicus_surface_currents", lat, lng, timestamp)
        wind_u, wind_v = fallback["wind_u"], fallback["wind_v"]
        current_u, current_v = fallback["current_u"], fallback["current_v"]

        if wind is not None:
            # GFS u/v is the atmospheric vector *towards*. Surface oil leeway
            # follows that vector with an Ekman deflection and Stokes component.
            atmospheric_u, atmospheric_v = wind
            speed = math.hypot(atmospheric_u, atmospheric_v)
            bearing = math.atan2(atmospheric_u, atmospheric_v)
            deflection = coriolis_deg if coriolis_deg != 2.0 else (15.0 if lat >= 0 else -15.0)
            push = bearing + math.radians(deflection)
            drift_speed = leeway_factor * speed + 0.015 * (speed ** 1.2)
            wind_u, wind_v = drift_speed * math.sin(push), drift_speed * math.cos(push)
            wind_speed, wind_from = speed, (math.degrees(bearing) + 180.0) % 360.0
        else:
            wind_speed, wind_from = fallback["wind_speed_ms"], fallback["wind_dir_deg"]

        if current is not None:
            current_u, current_v = current
            current_speed = math.hypot(current_u, current_v)
            current_dir = (math.degrees(math.atan2(current_u, current_v)) + 360.0) % 360.0
        else:
            current_speed, current_dir = fallback["current_speed_ms"], fallback["current_dir_deg"]

        net_u, net_v = wind_u + current_u, wind_v + current_v
        return {
            "wind_speed_ms": round(wind_speed, 2), "wind_dir_deg": round(wind_from, 1),
            "wind_u": wind_u, "wind_v": wind_v,
            "current_speed_ms": round(current_speed, 2), "current_dir_deg": round(current_dir, 1),
            "current_u": current_u, "current_v": current_v,
            "net_u_ms": net_u, "net_v_ms": net_v,
            "net_speed_kmh": round(math.hypot(net_u, net_v) * 3.6, 2),
            "bearing_deg": round((math.degrees(math.atan2(net_u, net_v)) + 360.0) % 360.0, 1),
            "wind_source": "NOAA GFS cached grid" if wind is not None else "modelled fallback",
            "current_source": "Copernicus Marine cached grid" if current is not None else "modelled fallback",
            "modelled_fallback": wind is None or current is None,
        }
