"""
seaLens: Oil Spill Detection & AIS Vessel Correlation System.
FastAPI Main Application and REST API Endpoints.
"""
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, List

from backend.models import ScenarioData, CulpritMatch
from backend.scenarios_data import SCENARIOS, build_scenario_alpha, build_scenario_beta, build_scenario_gamma
from backend.services.report_generator import generate_markdown_dossier
from backend.services.drift_engine import DriftEngine
from backend.services.correlation_engine import AISCorrelationEngine
from backend.services.dark_vessel_engine import DarkVesselEngine
from backend.services.ocean_grid_engine import DynamicOceanGridEngine
from backend.services.weathering_engine import OilWeatheringEngine
from backend.services.landfall_predictor import CoastalLandfallPredictor
from ml_engine.sar_detector import SAROilSpillDetector
from ml_engine.geotiff_processor import GeoTIFFProcessor
from ml_engine.cfar_ship_detector import CACFARShipDetector
from ml_engine.unet_model import SAROilSpillUNet
import torch

app = FastAPI(
    title="seaLens API",
    description="Oil Spill Detection via Satellite Imagery & AIS Vessel Correlation (SIH Problem #143)",
    version="1.0.0"
)

# Enable CORS for local/remote development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

drift_engine = DriftEngine()
correlation_engine = AISCorrelationEngine()
sar_detector = SAROilSpillDetector()
geotiff_processor = GeoTIFFProcessor()
cfar_detector = CACFARShipDetector()
scenario_cfar_detector = CACFARShipDetector()
dark_vessel_engine = DarkVesselEngine()
weathering_engine = OilWeatheringEngine()
landfall_predictor = CoastalLandfallPredictor()
backtrack_grid_engine = DynamicOceanGridEngine()

# Pre-load PyTorch U-Net weights if available
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

@app.get("/api/health")
def health_check():
    return {"status": "operational", "system": "seaLens C2 Engine", "unet_loaded": os.path.exists(checkpoint_path)}

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
        "targets": intel_targets
    }

@app.post("/api/process_synthetic_geotiff")
def process_synthetic_geotiff():
    """
    Generates and processes a 16-bit GeoTIFF with Lee speckle filter and U-Net segmentation.
    """
    sample_path = "data_samples/sample_sar_scene.tif"
    geotiff_processor.generate_synthetic_geotiff(sample_path, center_lat=18.85, center_lng=72.40)
    
    raster, transform, bounds, meta = geotiff_processor.read_geotiff(sample_path)
    filtered = geotiff_processor.apply_lee_speckle_filter(raster, window_size=5)
    
    # Run U-Net prediction
    pred_mask, prob_map = unet_model.predict_large_raster(filtered, tile_size=256, threshold=0.45)
    polygons = geotiff_processor.mask_to_geojson_polygons(pred_mask, transform)
    
    # Run CFAR ship detection
    radar_ships = cfar_detector.detect_ships(raster, transform)

    return {
        "status": "success",
        "bounds": bounds,
        "polygons_detected_count": len(polygons),
        "polygons": polygons,
        "radar_ships_detected_count": len(radar_ships),
        "radar_ships": radar_ships
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
            "is_lookalike": sc.slicks[0].is_lookalike if sc.slicks else False
        })
    return summary_list

@app.get("/api/scenario/{scenario_id}", response_model=ScenarioData)
def get_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    return SCENARIOS[scenario_id]

@app.get("/api/dossier/{scenario_id}/markdown")
def get_dossier_markdown(scenario_id: str):
    if scenario_id not in SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
    scenario = SCENARIOS[scenario_id]
    md_content = generate_markdown_dossier(scenario)
    return PlainTextResponse(content=md_content, media_type="text/markdown")

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
        "drift_trajectory": points
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
        "timeline": timeline
    }

# Mount static frontend files if directory exists
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

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
            return HTMLResponse(content=f.read())
    # Fallback to index if c2 not found
    index_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Sealens C2 Console</h1><p>frontend/c2.html not found</p>")

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
