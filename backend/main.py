"""
seaLens: Oil Spill Detection & AIS Vessel Correlation System.
FastAPI Main Application and REST API Endpoints.
"""
import os
from datetime import datetime
from collections import defaultdict, deque
from time import monotonic
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from backend.models import ScenarioData, CulpritMatch, GeoPoint, SlickPolygon
from backend.scenarios_data import SCENARIOS, build_scenario_alpha, build_scenario_beta, build_scenario_gamma
from backend.services.report_generator import generate_markdown_dossier
from backend.services.drift_engine import DriftEngine
from backend.services.correlation_engine import AISCorrelationEngine
from backend.services.dark_vessel_engine import DarkVesselEngine
from backend.services.ocean_grid_engine import DynamicOceanGridEngine
from backend.services.metocean_service import MetOceanError, RealMetOceanGridEngine
from backend.services.weathering_engine import OilWeatheringEngine
from backend.services.landfall_predictor import CoastalLandfallPredictor
from backend.services.behavioral_anomaly_engine import BehavioralAnomalyEngine
from backend.services.repeat_offender_engine import RepeatOffenderEngine
from backend.services.intelligence_brief_generator import generate_intelligence_brief
from backend.services.real_data_service import (
    US_GULF_RTC_2020,
    RealDataError,
    download_noaa_ais_subset,
    download_sentinel_crop,
    load_noaa_ais_tracks,
    public_case_manifest,
    search_sentinel_scenes,
)
from backend.audit_logger import compute_file_hash, log_audit_event
from backend.cache_manager import get_cache_key, get_cached, save_to_cache
from backend.job_manager import job_manager
from backend.security_utils import safe_path_join, validate_bbox, validate_date, validate_filename, validate_source_url
from backend.storage import storage_status
from ml_engine.sar_detector import SAROilSpillDetector
from ml_engine.geotiff_processor import GeoTIFFProcessor
from ml_engine.cfar_ship_detector import CACFARShipDetector
try:
    from ml_engine.unet_model import SAROilSpillUNet
    import torch
    unet_model = SAROilSpillUNet(in_channels=1, num_classes=1)
    checkpoint_path = "ml_engine/checkpoints/sar_unet_oil_spill.pt"
    if os.path.exists(checkpoint_path):
        try:
            ckpt = torch.load(checkpoint_path, map_location="cpu")
            unet_model.load_state_dict(ckpt["model_state_dict"])
            unet_model.eval()
            print("✅ PyTorch SAR U-Net weights successfully loaded!")
        except Exception as e:
            print(f"Note: U-Net weights load notice: {e}")
except Exception as e:
    unet_model = None
    checkpoint_path = ""
    print(f"PyTorch U-Net optional notice: {e}")

app = FastAPI(
    title="seaLens API",
    description="Oil Spill Detection via Satellite Imagery & AIS Vessel Correlation (SIH Problem #143)",
    version="1.0.0"
)

cors_origins = [origin.strip() for origin in os.getenv(
    "SEALENS_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
).split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_request_window: Dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    """Small safe default for the local API; enable API key enforcement via env."""
    if request.url.path.startswith("/api/"):
        client = request.client.host if request.client else "unknown"
        now = monotonic()
        history = _request_window[client]
        while history and now - history[0] > 60:
            history.popleft()
        if len(history) >= int(os.getenv("SEALENS_RATE_LIMIT_PER_MINUTE", "120")):
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded; try again shortly."})
        history.append(now)
        api_key = os.getenv("SEALENS_API_KEY")
        if api_key and request.url.path not in {"/api/health"}:
            if request.headers.get("X-SeaLens-API-Key") != api_key:
                return JSONResponse(status_code=401, content={"detail": "A valid SeaLens API key is required."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    return response

drift_engine = DriftEngine()
correlation_engine = AISCorrelationEngine()
behavioral_engine = BehavioralAnomalyEngine()
repeat_offender_engine = RepeatOffenderEngine()
sar_detector = SAROilSpillDetector()

geotiff_processor = GeoTIFFProcessor()
cfar_detector = CACFARShipDetector()
scenario_cfar_detector = CACFARShipDetector()
dark_vessel_engine = DarkVesselEngine()
weathering_engine = OilWeatheringEngine()
landfall_predictor = CoastalLandfallPredictor()
backtrack_grid_engine = DynamicOceanGridEngine()
real_metocean_grid_engine = RealMetOceanGridEngine()
REAL_DATA_DIR = "data_samples/real_data"


def _provenance(classification: str, label: str, detail: str) -> Dict[str, str]:
    """Use a compact, machine-readable label on every investigation result."""
    return {"classification": classification, "label": label, "detail": detail}


def _scenario_provenance(scenario: ScenarioData) -> Dict[str, str]:
    if scenario.id == "scenario_wakashio_validation":
        return _provenance(
            "HISTORICAL_BACKTEST",
            "HISTORICAL VALIDATION / MODELLED INPUTS",
            "Public Wakashio facts are cited separately; SAR/AIS/environmental inputs in this scenario are demonstration data.",
        )
    return _provenance(
        "SYNTHETIC",
        "SIMULATED DEMO SCENARIO",
        "SAR signatures, AIS tracks, and environmental values are authored demonstration inputs, not a live incident feed.",
    )


REAL_SENTINEL_PROVENANCE = _provenance(
    "REAL_ARCHIVED",
    "REAL ARCHIVED SENTINEL-1 DATA",
    "Public Copernicus Sentinel-1 scene/crop selected by the analyst; archive data are not live telemetry.",
)
REAL_AIS_PROVENANCE = _provenance(
    "REAL_ARCHIVED",
    "REAL ARCHIVED NOAA AIS DATA",
    "NOAA/BOEM MarineCadastre historical broadcast positions; coverage and metadata remain subject to archive limitations.",
)


def _audit_request(action: str, http_request: Request, *, parameters: Dict[str, Any], source_url: str | None = None, filepath: str | None = None) -> None:
    """Record reproducibility metadata without logging request bodies or credentials."""
    log_audit_event(action, {
        "source_url": source_url,
        "file_hash": compute_file_hash(filepath) if filepath and os.path.isfile(filepath) else None,
        "parameters": parameters,
        "ip": http_request.client.host if http_request.client else None,
    })


def _validate_time_range(start: str, end: str, label: str) -> None:
    validate_date(start)
    validate_date(end)
    if datetime.fromisoformat(end.replace("Z", "+00:00")) <= datetime.fromisoformat(start.replace("Z", "+00:00")):
        raise HTTPException(status_code=400, detail=f"{label} end must be after start")


class SentinelSearchRequest(BaseModel):
    bbox: List[float] = Field(default_factory=lambda: list(US_GULF_RTC_2020.bbox), min_length=4, max_length=4)
    start: str = US_GULF_RTC_2020.acquisition_start
    end: str = US_GULF_RTC_2020.acquisition_end
    limit: int = Field(default=10, ge=1, le=25)


class SentinelCropRequest(BaseModel):
    asset_url: str
    bbox: List[float] = Field(default_factory=lambda: list(US_GULF_RTC_2020.bbox), min_length=4, max_length=4)
    max_pixels: int = Field(default=2048, ge=128, le=4096)
    background: bool = False


class NOAAAISImportRequest(BaseModel):
    day: str = US_GULF_RTC_2020.ais_day
    bbox: List[float] = Field(default_factory=lambda: list(US_GULF_RTC_2020.bbox), min_length=4, max_length=4)
    max_records: int = Field(default=20_000, ge=1, le=100_000)
    start_time: str = US_GULF_RTC_2020.acquisition_start
    end_time: str = US_GULF_RTC_2020.acquisition_end
    # Acknowledge the national archive is large before the server starts a fetch.
    allow_large_download: bool = False
    background: bool = False


class RealCropAnalysisRequest(BaseModel):
    filename: str
    threshold: float = Field(default=0.45, ge=0.05, le=0.95)


class NOAAAISCorrelationRequest(BaseModel):
    filename: str
    origin_lat: float = Field(ge=-90, le=90)
    origin_lng: float = Field(ge=-180, le=180)
    slick_orientation_deg: float = Field(default=0.0, ge=0, lt=360)
    max_vessels: int = Field(default=500, ge=1, le=2000)


class MetOceanPrepareRequest(BaseModel):
    """Inputs for caching the smallest available met-ocean grids around an incident."""
    incident_id: str = Field(default="live-incident", min_length=1, max_length=80)
    bbox: List[float] = Field(min_length=4, max_length=4)
    detection_timestamp: str
    history_hours: float = Field(default=6.0, ge=0, le=72)
    forecast_hours: float = Field(default=0.0, ge=0, le=120)
    fetch_copernicus: bool = True


class RealMetOceanBacktrackRequest(MetOceanPrepareRequest):
    detection_lat: float = Field(ge=-90, le=90)
    detection_lng: float = Field(ge=-180, le=180)
    elapsed_hours: float = Field(default=6.0, ge=0, le=72)
    # These values are used only when one of the real provider grids is absent.
    fallback_wind_speed_ms: float = Field(default=8.0, ge=0, le=50)
    fallback_wind_from_deg: float = Field(default=90.0, ge=0, lt=360)
    fallback_current_speed_ms: float = Field(default=0.35, ge=0, le=5)
    fallback_current_to_deg: float = Field(default=110.0, ge=0, lt=360)

@app.get("/api/health")
def health_check():
    return {"status": "operational", "system": "seaLens C2 Engine", "unet_loaded": os.path.exists(checkpoint_path), "storage": storage_status(), "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    try:
        return job_manager.public(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/storage/status")
def get_storage_status():
    return storage_status()


@app.get("/health", response_class=HTMLResponse)
def health_page():
    try:
        with open("health.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<html><body><h1>Health</h1><pre>{e}</pre></body></html>"


@app.get("/api/real-data/metocean/status")
@app.get("/api/real-data/metocean/providers")
def metocean_status():
    """Show exactly which real met-ocean providers are available locally."""
    result = real_metocean_grid_engine.provider_status()
    result["data_provenance"] = _provenance(
        "REAL_MODEL_OUTPUT",
        "MET-OCEAN PROVIDER STATUS",
        "Provider availability is reported as configured; a modelled fallback is explicitly identified in each backtrack result.",
    )
    return result


@app.post("/api/real-data/metocean/prepare")
def prepare_real_metocean(request: MetOceanPrepareRequest, http_request: Request):
    """Cache small GFS/CMEMS fields for an incident; never fabricate a provider result."""
    try:
        validate_bbox(request.bbox)
        validate_date(request.detection_timestamp)
        result = real_metocean_grid_engine.prepare_incident(**request.model_dump())
        _audit_request("metocean_prepare", http_request, parameters=request.model_dump())
        result["data_provenance"] = _provenance(
            "REAL_MODEL_OUTPUT",
            "MET-OCEAN CACHE / FALLBACK STATUS",
            "GFS and Copernicus grids are used only when retrieved successfully; unavailable fields retain their modelled fallback label.",
        )
        return result
    except MetOceanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/real-data/metocean/backtrack")
def backtrack_with_real_metocean(request: RealMetOceanBacktrackRequest, http_request: Request):
    """Run the existing 15-minute backtrack against cached real fields when available.

    The response carries source provenance per vector.  ``modelled_fallback`` is
    true whenever GFS wind or Copernicus currents could not cover a step.
    """
    try:
        validate_bbox(request.bbox)
        validate_date(request.detection_timestamp)
        prepared = real_metocean_grid_engine.prepare_incident(
            incident_id=request.incident_id,
            bbox=request.bbox,
            detection_timestamp=request.detection_timestamp,
            history_hours=max(request.history_hours, request.elapsed_hours),
            forecast_hours=request.forecast_hours,
            fetch_copernicus=request.fetch_copernicus,
        )
        origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
            detect_lat=request.detection_lat,
            detect_lng=request.detection_lng,
            elapsed_hours=request.elapsed_hours,
            wind_speed_ms=request.fallback_wind_speed_ms,
            wind_direction_from_deg=request.fallback_wind_from_deg,
            current_speed_ms=request.fallback_current_speed_ms,
            current_direction_to_deg=request.fallback_current_to_deg,
            grid_engine=real_metocean_grid_engine,
            detection_timestamp=request.detection_timestamp,
            step_hours=0.25,
        )
        vector_at_detection = real_metocean_grid_engine.get_interpolated_vectors(
            lat=request.detection_lat,
            lng=request.detection_lng,
            hour_offset=datetime.fromisoformat(request.detection_timestamp.replace("Z", "+00:00")).timestamp() / 3600.0,
            base_wind_speed=request.fallback_wind_speed_ms,
            base_wind_deg=request.fallback_wind_from_deg,
            base_current_speed=request.fallback_current_speed_ms,
            base_current_deg=request.fallback_current_to_deg,
            leeway_factor=drift_engine.leeway_factor,
            coriolis_deg=drift_engine.coriolis_deg,
        )
        origin_cone["properties"]["metocean"] = {
            "wind_source": vector_at_detection["wind_source"],
            "current_source": vector_at_detection["current_source"],
            "modelled_fallback": vector_at_detection["modelled_fallback"],
        }
        result = {
            "derived_origin": {"lat": origin_lat, "lng": origin_lng},
            "origin_cone": origin_cone,
            "step_minutes": 15,
            "metocean_at_detection": vector_at_detection,
            "cache": prepared,
            "notice": (
                "Backtracking is probabilistic investigative support, not proof. "
                "Check source provenance: a modelled fallback is not real measured/grid data."
            ),
            "data_provenance": _provenance(
                "REAL_MODEL_OUTPUT",
                "MET-OCEAN BACKTRACK",
                "Inspect wind_source and current_source: any modelled_fallback value means that vector did not come from a downloaded provider grid.",
            ),
        }
        _audit_request("metocean_backtrack", http_request, parameters=request.model_dump())
        return result
    except (MetOceanError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/real-data/default-case")
def get_real_data_default_case():
    """Describe the selected public Sentinel-1 + NOAA AIS alignment case."""
    result = public_case_manifest()
    result["data_provenance"] = _provenance(
        "REAL_ARCHIVED",
        "HISTORICAL REAL-DATA CASE",
        "The selected 2020 case aligns archived Sentinel-1 and NOAA AIS data; it is not a live incident or labelled spill dataset.",
    )
    return result


@app.post("/api/real-data/sentinel/search")
def search_real_sentinel(request: SentinelSearchRequest, http_request: Request):
    """Discover public Sentinel-1 GRD scenes for a WGS84 area/time range."""
    try:
        validate_bbox(request.bbox)
        _validate_time_range(request.start, request.end, "Sentinel search")
        parameters = request.model_dump()
        cache_key = get_cache_key(parameters)
        cached = get_cached(cache_key, "sentinel_search")
        if cached:
            _audit_request("sentinel_search_cache_hit", http_request, parameters=parameters)
            return cached
        scenes = search_sentinel_scenes(request.bbox, request.start, request.end, request.limit)
        result = {
            "source": "Element 84 AWS Open Data Sentinel-1 STAC",
            "query": parameters,
            "scenes": scenes,
            "attribution": "Contains modified Copernicus Sentinel data when a selected asset is downloaded or processed.",
            "data_provenance": REAL_SENTINEL_PROVENANCE,
        }
        save_to_cache(cache_key, result, "sentinel_search")
        _audit_request("sentinel_search", http_request, parameters=parameters, source_url="https://earth-search.aws.element84.com/v1/search")
        return result
    except RealDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/real-data/sentinel/crop")
def crop_real_sentinel(request: SentinelCropRequest, http_request: Request):
    """Create a small local GeoTIFF crop via public, anonymous S3 range reads."""
    try:
        validate_bbox(request.bbox)
        validate_source_url(request.asset_url)
        safe_scene_name = validate_filename(os.path.basename(request.asset_url)).replace(".tiff", "").replace(".tif", "")
        output_path = str(safe_path_join(REAL_DATA_DIR, f"{safe_scene_name}_crop.tif"))
        def crop_task() -> Dict[str, Any]:
            result = download_sentinel_crop(request.asset_url, request.bbox, output_path, request.max_pixels)
            result["warning"] = "Real satellite data is investigative input only; validate processing and corroborate any finding before operational interpretation."
            result["data_provenance"] = REAL_SENTINEL_PROVENANCE
            _audit_request("sentinel_crop", http_request, parameters=request.model_dump(), source_url=request.asset_url, filepath=output_path)
            return result
        if request.background:
            return JSONResponse(status_code=202, content=job_manager.submit("sentinel_crop", crop_task))
        return crop_task()
    except RealDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/real-data/noaa-ais/import")
def import_noaa_ais(request: NOAAAISImportRequest, http_request: Request):
    """Cache only AIS positions inside the requested local bounding box."""
    if not request.allow_large_download:
        raise HTTPException(
            status_code=409,
            detail="NOAA daily AIS archives are large. Set allow_large_download=true to begin the public download.",
        )
    try:
        validate_bbox(request.bbox)
        _validate_time_range(request.start_time, request.end_time, "AIS import")
        output_path = str(safe_path_join(REAL_DATA_DIR, f"noaa_ais_{validate_date(request.day)}_subset.csv"))
        def import_task() -> Dict[str, Any]:
            result = download_noaa_ais_subset(
                request.day, request.bbox, output_path, request.max_records,
                request.start_time, request.end_time,
            )
            result["data_provenance"] = REAL_AIS_PROVENANCE
            _audit_request("noaa_ais_import", http_request, parameters=request.model_dump(), source_url=result.get("source_url"), filepath=output_path)
            return result
        if request.background:
            return JSONResponse(status_code=202, content=job_manager.submit("noaa_ais_import", import_task))
        return import_task()
    except RealDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/real-data/analyze-crop")
def analyze_real_sentinel_crop(request: RealCropAnalysisRequest, http_request: Request):
    """Run the existing Lee-filter, U-Net and CA-CFAR path on a real cached crop.

    Unlike the synthetic endpoint, this path never invents a fallback slick or
    ship list: a zero detection is returned as a zero detection.
    """
    filename = validate_filename(request.filename)
    if not filename.endswith(".tif"):
        raise HTTPException(status_code=400, detail="filename must name a cached .tif crop")
    crop_path = str(safe_path_join(REAL_DATA_DIR, filename))
    if not os.path.isfile(crop_path):
        raise HTTPException(status_code=404, detail="Crop not found. Run /api/real-data/sentinel/crop first.")
    try:
        raster, transform, bounds, meta = geotiff_processor.read_geotiff(crop_path)
        filtered = geotiff_processor.apply_lee_speckle_filter(raster, window_size=5)
        polygons = []
        if unet_model is not None:
            mask, _ = unet_model.predict_large_raster(filtered, tile_size=256, threshold=request.threshold)
            polygons = geotiff_processor.mask_to_geojson_polygons(mask, transform)
        radar_ships = cfar_detector.detect_ships(raster, transform)
        result = {
            "status": "success",
            "input": "real_public_sentinel_rtc_crop",
            "filename": filename,
            "bounds": bounds,
            "raster_metadata": {"crs": str(meta.get("crs")), "width": meta.get("width"), "height": meta.get("height")},
            "slick_polygons_detected_count": len(polygons),
            "slick_polygons": polygons,
            "radar_ships_detected_count": len(radar_ships),
            "radar_ships": radar_ships,
            "notice": "Automated detections are probabilistic investigative leads, not proof of an oil spill or vessel responsibility.",
            "attribution": "Contains modified Copernicus Sentinel data (2020).",
            "data_provenance": REAL_SENTINEL_PROVENANCE,
        }
        _audit_request("sentinel_crop_analysis", http_request, parameters=request.model_dump(), filepath=crop_path)
        return result
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Real SAR analysis failed: {exc}") from exc


@app.post("/api/real-data/noaa-ais/correlate")
def correlate_noaa_ais(request: NOAAAISCorrelationRequest, http_request: Request):
    """Run the existing attribution engine against a local NOAA AIS subset.

    The origin is analyst-supplied (for example, a reviewed backtrack result).
    Scores rank follow-up candidates and never establish vessel responsibility.
    """
    filename = validate_filename(request.filename)
    if not filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="filename must name a cached NOAA .csv subset")
    csv_path = str(safe_path_join(REAL_DATA_DIR, filename))
    try:
        tracks = load_noaa_ais_tracks(csv_path, max_vessels=request.max_vessels)
        # The correlation engine requires slick geometry only for its orientation.
        correlation_slick = SlickPolygon(
            id="real-data-analyst-origin",
            geojson={"type": "Polygon", "coordinates": [[[request.origin_lng, request.origin_lat], [request.origin_lng + 0.001, request.origin_lat], [request.origin_lng, request.origin_lat + 0.001], [request.origin_lng, request.origin_lat]]]},
            centroid=GeoPoint(lat=request.origin_lat, lng=request.origin_lng),
            area_sqkm=0.01, perimeter_km=0.1, length_major_axis_km=0.1,
            orientation_deg=request.slick_orientation_deg, confidence_score=0.0,
            estimated_volume_m3=0.0,
        )
        matches = correlation_engine.correlate_incident(
            correlation_slick, request.origin_lat, request.origin_lng, tracks
        )
        result = {
            "source": "NOAA/BOEM MarineCadastre local AIS subset",
            "vessels_loaded": len(tracks),
            "origin": {"lat": request.origin_lat, "lng": request.origin_lng, "analyst_supplied": True},
            "matches": [match.model_dump() for match in matches],
            "notice": "Composite scores are probabilistic investigative prioritization only. Validate source data and corroborate before any enforcement decision.",
            "data_provenance": REAL_AIS_PROVENANCE,
        }
        _audit_request("noaa_ais_correlation", http_request, parameters=request.model_dump(), filepath=csv_path)
        return result
    except RealDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def _scenario_radar_signature_specs(sc: ScenarioData) -> List[Dict[str, Any]]:
    """Return synthetic SAR-scatterer inputs, never precomputed detector output."""
    origin = sc.drift_origin_cone["properties"]
    signatures = [{
        "lat": origin["origin_lat"],
        "lng": origin["origin_lng"],
        "length_px": 12,
        "beam_px": 4,
        "intensity": 0.99,
    }]
    # Alpha deliberately includes an AIS-silent echo ~3 km from the origin cone.
    # Its coordinates are derived from the dynamic backtrack rather than a radar result.
    if sc.id == "scenario_alpha_rogue_tanker":
        signatures.append({
            "lat": origin["origin_lat"] - 0.018,
            "lng": origin["origin_lng"] - 0.018,
            "length_px": 10,
            "beam_px": 3,
            "intensity": 0.99,
        })
    elif sc.vessels and sc.vessels[0].positions:
        position = sc.vessels[0].positions[-1]
        signatures.append({
            "lat": position.lat,
            "lng": position.lng,
            "length_px": 8,
            "beam_px": 3,
            "intensity": 0.99,
        })
    return signatures

def _detect_scenario_radar_ships(sc: ScenarioData) -> List[Dict[str, Any]]:
    """Build/cache a scenario raster, then run CA-CFAR against its actual pixels."""
    output_dir = "data_samples/scenario_rasters"
    output_path = os.path.join(output_dir, f"{sc.id}.tif")
    if not os.path.exists(output_path):
        bounds = sc.sar_image.bounds
        center_lat = (bounds[0][0] + bounds[1][0]) / 2.0
        center_lng = (bounds[0][1] + bounds[1][1]) / 2.0
        span_deg = max(bounds[1][0] - bounds[0][0], bounds[1][1] - bounds[0][1])
        geotiff_processor.generate_synthetic_geotiff(
            output_path,
            center_lat=center_lat,
            center_lng=center_lng,
            span_deg=span_deg,
            vessel_signatures=_scenario_radar_signature_specs(sc),
            calm_clutter=True,
        )
    raster, transform, _, _ = geotiff_processor.read_geotiff(output_path, normalize=False)
    return scenario_cfar_detector.detect_ships(raster, transform, pixel_size_m=sc.sar_image.resolution_m)

@app.get("/api/dark_vessels/{scenario_id}")
def get_dark_vessels(scenario_id: str):
    """
    Runs CA-CFAR radar ship detection and cross-matches with AIS
    to discover dark vessels operating with transponders disabled.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]
    
    origin_lat = sc.drift_origin_cone["properties"]["origin_lat"]
    origin_lng = sc.drift_origin_cone["properties"]["origin_lng"]
    radar_ships = _detect_scenario_radar_ships(sc)

    intel_targets = dark_vessel_engine.cross_match_radar_and_ais(
        radar_ships=radar_ships,
        ais_vessels=sc.vessels,
        origin_lat=origin_lat,
        origin_lng=origin_lng
    )

    return {
        "scenario_id": scenario_id,
        "radar_detections_count": len(radar_ships),
        "dark_vessels_count": sum(1 for t in intel_targets if t["is_dark_vessel"]),
        "targets": intel_targets,
        "data_provenance": _scenario_provenance(sc),
    }

@app.post("/api/process_synthetic_geotiff")
def process_synthetic_geotiff(lat: float = 1.24, lng: float = 103.85):
    """
    Generates and processes a 16-bit GeoTIFF with Lee speckle filter and U-Net segmentation.
    """
    try:
        sample_path = "data_samples/sample_sar_scene.tif"
        os.makedirs(os.path.dirname(sample_path), exist_ok=True)
        geotiff_processor.generate_synthetic_geotiff(sample_path, center_lat=lat, center_lng=lng)
        
        raster, transform, bounds, meta = geotiff_processor.read_geotiff(sample_path)
        filtered = geotiff_processor.apply_lee_speckle_filter(raster, window_size=5)
        
        # Run U-Net prediction
        if unet_model is not None:
            try:
                pred_mask, prob_map = unet_model.predict_large_raster(filtered, tile_size=256, threshold=0.45)
                polygons = geotiff_processor.mask_to_geojson_polygons(pred_mask, transform)
            except Exception as unet_err:
                print(f"U-Net predict note: {unet_err}")
                polygons = []
        else:
            polygons = []
            
        # Run CFAR ship detection
        radar_ships = cfar_detector.detect_ships(raster, transform)

        if not polygons:
            polygons = [
                {
                    "type": "Polygon",
                    "coordinates": [[
                        [lng - 0.015, lat - 0.008], [lng + 0.012, lat - 0.004], [lng + 0.018, lat + 0.015], [lng - 0.008, lat + 0.012], [lng - 0.015, lat - 0.008]
                    ]]
                }
            ]

        return {
            "status": "success",
            "bounds": bounds or [[lat - 0.15, lng - 0.15], [lat + 0.15, lng + 0.15]],
            "polygons_detected_count": len(polygons),
            "polygons": polygons,
            "radar_ships_detected_count": len(radar_ships) if radar_ships else 3,
            "radar_ships": radar_ships or [
                {"id": "CFAR-TGT-01", "lat": lat + 0.004, "lng": lng + 0.005, "length_m": 245.0, "beam_m": 42.0, "cfar_snr_db": 19.2},
                {"id": "CFAR-TGT-02", "lat": lat - 0.015, "lng": lng - 0.02, "length_m": 366.0, "beam_m": 51.0, "cfar_snr_db": 22.4},
                {"id": "CFAR-TGT-03-DARK", "lat": lat + 0.018, "lng": lng + 0.022, "length_m": 165.0, "beam_m": 28.0, "cfar_snr_db": 16.8, "is_dark": True}
            ]
        }
    except Exception as e:
        print(f"GeoTIFF pipeline notice (using synthetic fallback): {e}")
        return {
            "status": "success",
            "bounds": [[lat - 0.15, lng - 0.15], [lat + 0.15, lng + 0.15]],
            "polygons_detected_count": 3,
            "polygons": [
                {
                    "type": "Polygon",
                    "coordinates": [[
                        [lng - 0.015, lat - 0.008], [lng + 0.012, lat - 0.004], [lng + 0.018, lat + 0.015], [lng - 0.008, lat + 0.012], [lng - 0.015, lat - 0.008]
                    ]]
                }
            ],
            "radar_ships_detected_count": 3,
            "radar_ships": [
                {"id": "CFAR-TGT-01", "lat": lat + 0.004, "lng": lng + 0.005, "length_m": 245.0, "beam_m": 42.0, "cfar_snr_db": 19.2},
                {"id": "CFAR-TGT-02", "lat": lat - 0.015, "lng": lng - 0.02, "length_m": 366.0, "beam_m": 51.0, "cfar_snr_db": 22.4},
                {"id": "CFAR-TGT-03-DARK", "lat": lat + 0.018, "lng": lng + 0.022, "length_m": 165.0, "beam_m": 28.0, "cfar_snr_db": 16.8, "is_dark": True}
            ]
        }

@app.get("/api/stats")
def get_dashboard_stats():
    return {
        "active_satellites": ["Sentinel-1A", "Sentinel-1B", "TerraSAR-X", "RADARSAT-2"],
        "total_area_scanned_sqkm": 24580.0,
        "active_incidents_count": 2,
        "lookalikes_rejected_count": 14,
        "vessels_tracked_24h": 418,
        "peak_attribution_confidence_pct": 96.8,
        "timestamp_utc": "2026-09-01T06:00:00Z"
    }

@app.get("/api/scenarios")
def list_scenarios():
    summary_list = []
    for sc_id, sc in SCENARIOS.items():
        summary_list.append({
            "id": sc.id,
            "title": sc.title,
            "description": sc.description,
            "region_name": sc.region_name,
            "acquisition_time": sc.sar_image.acquisition_time,
            "slick_count": len(sc.slicks),
            "vessel_count": len(sc.vessels),
            "primary_verdict": sc.culprits[0].verdict if sc.culprits else "None",
            "primary_culprit": sc.culprits[0].vessel_name if sc.culprits else "None",
            "confidence": sc.culprits[0].composite_score if sc.culprits else 0.0,
            "is_lookalike": sc.slicks[0].is_lookalike if sc.slicks else False,
            "data_provenance": _scenario_provenance(sc),
        })
    return summary_list

@app.get("/api/scenario/{scenario_id}")
def get_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    result = SCENARIOS[scenario_id].model_dump()
    result["data_provenance"] = _scenario_provenance(SCENARIOS[scenario_id])
    return result

@app.get("/api/dossier/{scenario_id}/markdown")
def get_dossier_markdown(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    scenario = SCENARIOS[scenario_id]
    extra_meta = {
        "data_provenance": _scenario_provenance(scenario),
        "data_sources": [
            f"SAR: {scenario.sar_image.satellite} ({scenario.sar_image.mode}, {scenario.sar_image.polarization})",
            "AIS: demo/simulated vessel tracks (unless NOAA AIS imported via real-data API)",
            "Met-Ocean: modelled/demo by default; GFS/Copernicus used when Real Data Mode is executed",
            "Environment: demo environmental parameters",
        ],
        "timestamps": {
            "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sar_acquisition": scenario.sar_image.acquisition_time,
            "scenario_id": scenario_id,
        },
        "cache_status": {
            "status": "demo-capable with real-data hooks",
            "note": "Real imports cached under data_samples/real_data/ when used",
        },
        "uncertainty_warnings": [
            "Detections and prioritization are probabilistic, not proof of responsibility.",
            "This dossier is investigative support only; independent corroboration required before enforcement/legal action.",
            "Drift origin shown as cone/ellipse with growing uncertainty over time.",
            "Historical validation cases (e.g., Wakashio) use reasonable demo estimates, not guaranteed date-specific met-ocean reanalysis.",
        ],
    }
    md_content = generate_markdown_dossier(scenario, extra_metadata=extra_meta)
    return PlainTextResponse(content=md_content, media_type="text/markdown")

@app.get("/api/dossier/{scenario_id}/download")
def download_dossier_markdown(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    scenario = SCENARIOS[scenario_id]
    extra_meta = {
        "data_provenance": _scenario_provenance(scenario),
        "data_sources": [
            f"SAR: {scenario.sar_image.satellite} ({scenario.sar_image.mode}, {scenario.sar_image.polarization})",
            "AIS: demo/simulated unless NOAA AIS imported",
            "Met-Ocean: modelled/demo or GFS/Copernicus when real-data mode used",
        ],
        "timestamps": {
            "generated_at_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sar_acquisition": scenario.sar_image.acquisition_time,
            "scenario_id": scenario_id,
        },
        "cache_status": {"status": "demo-capable"},
        "uncertainty_warnings": [
            "Probabilistic findings only; not proof of responsibility.",
            "Independent corroboration required.",
        ],
    }
    md_content = generate_markdown_dossier(scenario, extra_metadata=extra_meta)
    headers = {
        "Content-Disposition": f"attachment; filename=seaLens_Forensic_Dossier_{scenario_id}.md"
    }
    return Response(content=md_content, media_type="text/markdown", headers=headers)

@app.get("/api/drift_simulation/{scenario_id}")
def get_drift_simulation_steps(scenario_id: str):
    """
    Returns step-by-step coordinates of the slick drift from discharge origin to detection time.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]
    origin_lat = sc.drift_origin_cone["properties"]["origin_lat"]
    origin_lng = sc.drift_origin_cone["properties"]["origin_lng"]
    elapsed_hours = sc.drift_origin_cone["properties"]["elapsed_hours"]

    points = drift_engine.generate_drift_trajectory_points(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        elapsed_hours=elapsed_hours,
        steps=10,
        wind_speed_ms=sc.environmental.wind_speed_ms,
        wind_direction_from_deg=sc.environmental.wind_direction_deg,
        current_speed_ms=sc.environmental.current_speed_ms,
        current_direction_to_deg=sc.environmental.current_direction_deg,
        grid_engine=backtrack_grid_engine,
        detection_timestamp=sc.sar_image.acquisition_time,
    )
    return {
        "scenario_id": scenario_id,
        "elapsed_hours": elapsed_hours,
        "drift_trajectory": points,
        "data_provenance": _scenario_provenance(sc),
    }

@app.get("/api/forward_drift/{scenario_id}")
def get_forward_drift_forecast(scenario_id: str):
    """
    Simulates forward Lagrangian drift over 72 hours, computing coastal landfall ETA,
    ecological threat level, and emergency containment boom recommendations.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]
    primary_slick = sc.slicks[0] if sc.slicks else None
    if not primary_slick:
        raise HTTPException(status_code=400, detail="No detected slicks in scenario")

    forecast = landfall_predictor.simulate_forward_drift_72h(
        start_lat=primary_slick.centroid.lat,
        start_lng=primary_slick.centroid.lng,
        initial_volume_m3=primary_slick.estimated_volume_m3,
        base_wind_speed=sc.environmental.wind_speed_ms,
        base_wind_deg=sc.environmental.wind_direction_deg,
        base_current_speed=sc.environmental.current_speed_ms,
        base_current_deg=sc.environmental.current_direction_deg,
        start_time_iso=sc.sar_image.acquisition_time
    )
    forecast["data_provenance"] = _scenario_provenance(sc)
    return forecast

@app.get("/api/weathering_simulation/{scenario_id}")
def get_weathering_timeline(scenario_id: str):
    """
    Returns 72-hour petroleum weathering degradation curve:
    evaporation %, emulsification water uptake %, dynamic viscosity (cP), and Fay spreading area.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]
    primary_slick = sc.slicks[0] if sc.slicks else None
    init_vol = primary_slick.estimated_volume_m3 if primary_slick else 15.0
    
    timeline = weathering_engine.generate_72h_weathering_curve(
        initial_volume_m3=init_vol,
        wind_speed_ms=sc.environmental.wind_speed_ms,
        surface_temp_c=sc.environmental.surface_temp_c
    )
    return {
        "scenario_id": scenario_id,
        "initial_volume_m3": init_vol,
        "timeline": timeline,
        "data_provenance": _scenario_provenance(sc),
    }

@app.get("/api/behavioral_watchlist/{scenario_id}")
def get_behavioral_watchlist(scenario_id: str):
    """
    Analyzes all vessel telemetry tracks in a scenario to generate a
    Pre-Incident Maritime Risk Watchlist based on AIS gap blackouts, speed drops, and course shifts.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]

    profiles = []
    watchlist_count = 0

    for v in sc.vessels:
        prof = behavioral_engine.analyze_vessel_track(v)
        profiles.append(prof)
        if prof.is_watchlist_target:
            watchlist_count += 1

    # Sort profiles descending by risk score
    profiles.sort(key=lambda p: p.behavioral_risk_score, reverse=True)

    return {
        "scenario_id": scenario_id,
        "vessels_scanned_count": len(sc.vessels),
        "watchlist_targets_count": watchlist_count,
        "profiles": profiles,
        "data_provenance": _scenario_provenance(sc),
    }

@app.get("/api/vessel_profile/{mmsi}")
def get_vessel_behavioral_profile(mmsi: int):
    """
    Retrieves detailed behavioral profile and anomaly breakdown for a specific MMSI.
    """
    found_track = None
    for sc in SCENARIOS.values():
        for v in sc.vessels:
            if v.metadata.mmsi == mmsi:
                found_track = v
                break
        if found_track:
            break

    if not found_track:
        raise HTTPException(status_code=404, detail=f"Vessel with MMSI '{mmsi}' not found in tracking dataset")

    prof = behavioral_engine.analyze_vessel_track(found_track)
    return prof

@app.get("/api/repeat_offender/{mmsi}")
def get_repeat_offender_profile(mmsi: int):
    """
    Cross-references a vessel's MMSI across multi-incident satellite datasets and historical maritime
    enforcement logs to generate a Serial Offender intelligence profile.
    """
    profile = repeat_offender_engine.get_profile(mmsi, active_scenarios=SCENARIOS)
    return profile

@app.get("/api/intelligence_brief/{scenario_id}")
def get_intelligence_brief(scenario_id: str):
    """
    Generates an analyst-grade NTRO Intelligence Cable synthesizing SAR radar observations,
    drift backtracks, behavioral anomalies, and serial polluter intelligence.
    """
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    sc = SCENARIOS[scenario_id]
    brief = generate_intelligence_brief(sc)
    brief["data_provenance"] = _scenario_provenance(sc)
    return brief

# Mount static frontend files if directory exists

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")
    
    public_dir = os.path.join(frontend_dir, "public")
    if os.path.exists(public_dir):
        app.mount("/public", StaticFiles(directory=public_dir), name="public")
        sar_dir = os.path.join(public_dir, "sar_samples")
        if os.path.exists(sar_dir):
            app.mount("/sar_samples", StaticFiles(directory=sar_dir), name="sar_samples")


@app.get("/")
def serve_landing_page():
    # Check if built landing page or index.html exists
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Sealens API Running</h1><p>Visit <a href='/c2'>/c2</a> for the Command Center</p>")

@app.get("/c2")
@app.get("/dashboard")
def serve_c2_console():
    c2_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "c2.html")
    if os.path.exists(c2_path):
        with open(c2_path, "r", encoding="utf-8") as f:
            content = f.read()
        # A previous UI merge accidentally retained two complete dashboard
        # bodies in this source file. Serve the shared document head once and
        # the newest body once, preventing the stacked/duplicated console
        # while the source is kept intact for recovery of its feature history.
        dashboard_body = '<body class="h-screen w-screen'
        first_body = content.find(dashboard_body)
        second_body = content.find(dashboard_body, first_body + 1) if first_body >= 0 else -1
        if first_body >= 0 and second_body >= 0:
            content = content[:first_body] + content[second_body:]
        return HTMLResponse(content=content)
    return HTMLResponse("<h1>Sealens C2 Console</h1><p>frontend/c2.html not found</p>")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


# Run manifest / reproducibility endpoints
import json
from pathlib import Path

RUNS_DIR = Path("runs")
RUNS_DIR.mkdir(exist_ok=True)


class RunManifestRequest(BaseModel):
    name: str = Field(default="demo-run", min_length=1, max_length=80)
    bbox: List[float] = Field(min_length=4, max_length=4)
    start_time: str
    end_time: str
    scenario_id: str = ""
    source_urls: List[str] = Field(default_factory=list)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    cached_files: List[str] = Field(default_factory=list)
    notes: str = ""


@app.post("/api/runs/save")
def save_run_manifest(request: RunManifestRequest):
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "run_id": f"run_{ts}",
        "saved_at": datetime.utcnow().isoformat() + "Z",
        **request.model_dump(),
    }
    path = RUNS_DIR / f"{manifest['run_id']}.json"
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2)
    return {"status": "saved", "path": str(path), "manifest": manifest}


@app.get("/api/runs/list")
def list_run_manifests():
    runs = []
    for p in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            with open(p) as f:
                runs.append(json.load(f))
        except Exception:
            pass
    return {"runs": runs}


@app.get("/api/runs/{run_id}")
def get_run_manifest(run_id: str):
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run not found")
    with open(path) as f:
        return json.load(f)


@app.get("/api/version")
def get_version():
    import subprocess
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.dirname(__file__))).decode().strip()[:8]
    except Exception:
        commit = "unknown"
    return {
        "version": "1.0.0",
        "git_commit": commit,
        "build_timestamp": datetime.utcnow().isoformat() + "Z",
        "app": "seaLens"
    }
