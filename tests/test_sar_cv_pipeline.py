"""
Test Suite for Computer Vision & SAR Deep Learning Pipeline:
1. PyTorch U-Net Model & Pretrained Checkpoint
2. GeoTIFF Ingestion, 5x5 Lee Speckle Filter & Georeferencing
3. 2D CA-CFAR Radar Ship Spotter
4. Dark Vessel Intelligence Cross-Matching
"""
import os
import torch
import numpy as np
from ml_engine.unet_model import SAROilSpillUNet
from ml_engine.geotiff_processor import GeoTIFFProcessor
from ml_engine.cfar_ship_detector import CACFARShipDetector
from backend.services.dark_vessel_engine import DarkVesselEngine
from backend.scenarios_data import build_scenario_alpha

def test_unet_weights_and_inference():
    ckpt_path = "ml_engine/checkpoints/sar_unet_oil_spill.pt"
    assert os.path.exists(ckpt_path), "Checkpoint file must exist"
    
    ckpt = torch.load(ckpt_path, map_location="cpu")
    model = SAROilSpillUNet(in_channels=1, num_classes=1)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    # Test dummy 2D raster inference
    dummy_raster = np.random.uniform(0.2, 0.8, (512, 512)).astype(np.float32)
    # Add fake dark slick
    dummy_raster[200:260, 200:300] *= 0.2
    
    binary_mask, prob_map = model.predict_large_raster(dummy_raster, tile_size=256, threshold=0.40)
    assert binary_mask.shape == (512, 512)
    assert prob_map.shape == (512, 512)
    print("✓ U-Net model checkpoint loading and large raster inference verified.")

def test_geotiff_processor_and_lee_filter():
    processor = GeoTIFFProcessor()
    test_tif = "data_samples/test_synthetic_sar.tif"
    
    # 1. Generate georeferenced GeoTIFF
    processor.generate_synthetic_geotiff(test_tif, center_lat=18.85, center_lng=72.40, resolution_px=256)
    assert os.path.exists(test_tif)

    # 2. Read GeoTIFF
    raster, transform, bounds, meta = processor.read_geotiff(test_tif)
    assert raster.shape == (256, 256)
    assert bounds[0][0] < bounds[1][0] # min_lat < max_lat

    # 3. Apply Lee Speckle Filter
    filtered = processor.apply_lee_speckle_filter(raster, window_size=5)
    assert filtered.shape == (256, 256)
    # Variance should be reduced after Lee filtering
    assert np.var(filtered) <= np.var(raster)

    # 4. Mask to GeoJSON Polygons
    dummy_mask = np.zeros((256, 256), dtype=np.uint8)
    dummy_mask[100:150, 100:150] = 1
    polygons = processor.mask_to_geojson_polygons(dummy_mask, transform)
    assert len(polygons) == 1
    # Check that coordinates are in valid lat/lng range for Mumbai
    first_pt = polygons[0][0]
    assert 72.0 < first_pt[0] < 73.0 # Lng
    assert 18.0 < first_pt[1] < 19.0 # Lat
    print("✓ GeoTIFF reader, Lee speckle filter, and affine georeferencer verified.")

def test_cfar_ship_detector():
    cfar = CACFARShipDetector()
    processor = GeoTIFFProcessor()
    test_tif = "data_samples/test_synthetic_sar.tif"
    raster, transform, _, _ = processor.read_geotiff(test_tif)

    # Inject two bright metallic point targets (ships)
    raster[60:64, 60:64] = 0.95
    raster[180:185, 180:183] = 0.98

    detected_ships = cfar.detect_ships(raster, transform)
    assert len(detected_ships) >= 2
    for ship in detected_ships:
        assert "lat" in ship and "lng" in ship
        assert ship["estimated_length_m"] > 0
        assert ship["cfar_snr_db"] >= 3.5
    print(f"✓ 2D CA-CFAR Radar Detector successfully spotted {len(detected_ships)} ships.")

def test_dark_vessel_cross_match():
    dark_engine = DarkVesselEngine(match_tolerance_km=1.8)
    sc = build_scenario_alpha()
    origin_lat = sc.drift_origin_cone["properties"]["origin_lat"]
    origin_lng = sc.drift_origin_cone["properties"]["origin_lng"]

    # Radar detects MT Ocean Titan (AIS active) and a rogue Dark Tanker (AIS disabled)
    radar_ships = [
        {"id": "RADAR-01", "lat": origin_lat, "lng": origin_lng, "estimated_length_m": 245.0, "estimated_beam_m": 42.0, "cfar_snr_db": 20.0},
        {"id": "RADAR-DARK-02", "lat": 18.820, "lng": 72.280, "estimated_length_m": 175.0, "estimated_beam_m": 28.0, "cfar_snr_db": 17.5}
    ]

    intel_targets = dark_engine.cross_match_radar_and_ais(
        radar_ships=radar_ships,
        ais_vessels=sc.vessels,
        origin_lat=origin_lat,
        origin_lng=origin_lng
    )

    assert len(intel_targets) == 2
    # First target should match MT Ocean Titan
    assert intel_targets[0]["is_dark_vessel"] is False
    assert intel_targets[0]["matched_ais_name"] == "MT Ocean Titan"

    # Second target must be flagged as DARK VESSEL
    dark_target = intel_targets[1]
    assert dark_target["is_dark_vessel"] is True
    assert "DARK VESSEL" in dark_target["status"]
    assert dark_target["matched_mmsi"] is None
    print("✓ Dark Vessel Intelligence Cross-Matching verified.")

if __name__ == "__main__":
    test_unet_weights_and_inference()
    test_geotiff_processor_and_lee_filter()
    test_cfar_ship_detector()
    test_dark_vessel_cross_match()
    print("\n🎉 ALL CV, GEOTIFF, U-NET, AND CFAR PIPELINE TESTS PASSED!")
