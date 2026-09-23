"""
Pre-packaged realistic scenarios for Hackathon / Demonstration.
Includes SAR detections, AIS vessel tracks, environmental conditions, and drift backtracks.
"""
from typing import Dict, List
from backend.models import (
    ScenarioData, SARImageMetadata, EnvironmentalCondition,
    SlickPolygon, VesselTrack, VesselMetadata, TelemetryPoint, GeoPoint
)
from ml_engine.sar_detector import SAROilSpillDetector
from backend.services.drift_engine import DriftEngine
from backend.services.ocean_grid_engine import DynamicOceanGridEngine
from backend.services.correlation_engine import AISCorrelationEngine

detector = SAROilSpillDetector()
drift_engine = DriftEngine()
ocean_grid_engine = DynamicOceanGridEngine()
correlation_engine = AISCorrelationEngine()

def build_scenario_alpha() -> ScenarioData:
    """
    Scenario Alpha: The Rogue Tanker (Arabian Sea / Mumbai Offshore Corridor)
    A 240m Crude Oil Tanker (MT Ocean Titan) performs an illicit tank cleaning discharge.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=6.2,
        wind_direction_deg=225.0,  # SW Monsoon wind
        current_speed_ms=0.45,
        current_direction_deg=45.0, # Flowing NE
        sea_state=3,
        surface_temp_c=28.5
    )

    sar_meta = SARImageMetadata(
        scene_id="S1A_IW_GRDH_1SDV_20260901T060012_ARABIAN_SEA",
        satellite="Sentinel-1A C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-01T06:00:00Z",
        bounds=[[18.70, 72.25], [19.00, 72.60]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_alpha_rogue_tanker.jpg"
    )

    # Detected slick coordinates at 06:00 UTC (after 3.5 hrs of drift)
    # Drift has pushed it from approx (18.82, 72.35) towards NE to (18.855, 72.410)
    slick_coords = [
        [72.400, 18.850],
        [72.415, 18.860],
        [72.428, 18.868],
        [72.422, 18.872],
        [72.408, 18.864],
        [72.395, 18.854],
        [72.400, 18.850]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 9.2,
        "edge_sharpness": 0.88,
        "thickness_microns": 3.0
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=18.86,
        base_lng=72.41,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    # Backtrack 3.5 hours to find discharge point
    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=3.5,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg,
        grid_engine=ocean_grid_engine,
        detection_timestamp=sar_meta.acquisition_time,
    )

    # Vessels in the area between 01:00 UTC and 06:00 UTC
    vessels = [
        # Vessel 1: Rogue Tanker (MT Ocean Titan)
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419001234,
                imo=9487123,
                name="MT Ocean Titan",
                callsign="9V9821",
                ship_type="Crude Oil Tanker",
                flag="Panama",
                length_m=245.0,
                beam_m=42.0,
                gross_tonnage=62500,
                risk_weight=1.5
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T01:15:00Z", lat=18.750, lng=72.260, sog=14.1, cog=48.0, heading=48.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T01:45:00Z", lat=18.795, lng=72.310, sog=13.2, cog=50.0, heading=49.0, nav_status="Under way using engine"),
                # 🚨 45-MINUTE AIS TRANSPONDER BLACKOUT GAP (01:45 to 02:30 UTC) - Going dark prior to dumping slops!
                # Critical discharge window: transponder turns back on, speed drops to 5.2 knots, exactly on backtracked origin!
                TelemetryPoint(timestamp="2026-09-01T02:30:00Z", lat=origin_lat, lng=origin_lng, sog=5.2, cog=52.0, heading=51.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T03:00:00Z", lat=18.840, lng=72.378, sog=6.8, cog=50.0, heading=50.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T03:30:00Z", lat=18.875, lng=72.420, sog=12.8, cog=48.0, heading=48.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T04:30:00Z", lat=18.940, lng=72.500, sog=13.8, cog=48.0, heading=48.0, nav_status="Under way using engine"),
            ]
        ),
        # Vessel 2: Innocent Container Ship (CMA CGM Mumbai)
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=228394000,
                imo=9724567,
                name="CMA CGM Mumbai",
                callsign="FNCB",
                ship_type="Container Ship",
                flag="France",
                length_m=366.0,
                beam_m=51.0,
                gross_tonnage=140000,
                risk_weight=0.6
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T02:00:00Z", lat=18.720, lng=72.380, sog=19.4, cog=340.0, heading=340.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:30:00Z", lat=18.775, lng=72.360, sog=19.2, cog=340.0, heading=340.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T03:00:00Z", lat=18.830, lng=72.340, sog=19.5, cog=340.0, heading=340.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T03:30:00Z", lat=18.885, lng=72.320, sog=19.0, cog=340.0, heading=340.0, nav_status="Under way using engine"),
            ]
        ),
        # Vessel 3: Offshore Tug (Smit Lion)
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=538004521,
                imo=9234188,
                name="Smit Lion",
                callsign="V7AB4",
                ship_type="Tugboat",
                flag="Marshall Islands",
                length_m=65.0,
                beam_m=16.0,
                gross_tonnage=2200,
                risk_weight=0.3
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T02:15:00Z", lat=18.910, lng=72.250, sog=8.0, cog=110.0, heading=110.0, nav_status="Restricted maneuverability"),
                TelemetryPoint(timestamp="2026-09-01T02:45:00Z", lat=18.900, lng=72.290, sog=8.1, cog=110.0, heading=110.0, nav_status="Restricted maneuverability"),
                TelemetryPoint(timestamp="2026-09-01T03:15:00Z", lat=18.890, lng=72.330, sog=7.9, cog=110.0, heading=110.0, nav_status="Restricted maneuverability"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_alpha_rogue_tanker",
        title="Scenario Alpha: The Rogue Tanker",
        description="A 240m Crude Oil Tanker discharged bilge slops during offshore transit. Detected by Sentinel-1 SAR after 3.5 hours of ocean drift.",
        region_name="Arabian Sea // Mumbai High Outer Channel",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_beta() -> ScenarioData:
    """
    Scenario Beta: Multi-Vessel Confluence in Singapore Strait
    Multiple vessels traversed the strait; system disambiguates a high-risk bunkering barge
    from an innocent bulk carrier and a ferry.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=4.8,
        wind_direction_deg=110.0,
        current_speed_ms=0.60,
        current_direction_deg=270.0, # Westward tidal current
        sea_state=2,
        surface_temp_c=29.2
    )

    sar_meta = SARImageMetadata(
        scene_id="S1A_IW_GRDH_1SDV_20260901T041530_SINGAPORE_STRAIT",
        satellite="Sentinel-1B C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-01T04:15:00Z",
        bounds=[[1.15, 103.70], [1.35, 104.05]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_beta_singapore_strait.jpg"
    )

    slick_coords = [
        [103.820, 1.220],
        [103.835, 1.225],
        [103.850, 1.228],
        [103.845, 1.233],
        [103.830, 1.230],
        [103.815, 1.224],
        [103.820, 1.220]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 8.0,
        "edge_sharpness": 0.82,
        "thickness_microns": 2.2
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=1.226,
        base_lng=103.833,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=2.0,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg,
        grid_engine=ocean_grid_engine,
        detection_timestamp=sar_meta.acquisition_time,
    )

    vessels = [
        # Suspect Bunker Barge
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=563009876,
                imo=9148722,
                name="Bunker Star 8",
                callsign="9V2311",
                ship_type="Bunkering Tanker",
                flag="Singapore",
                length_m=95.0,
                beam_m=16.0,
                gross_tonnage=4200,
                risk_weight=1.3
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T02:00:00Z", lat=1.210, lng=103.880, sog=6.4, cog=260.0, heading=260.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:15:00Z", lat=origin_lat, lng=origin_lng, sog=5.8, cog=262.0, heading=261.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:30:00Z", lat=1.225, lng=103.830, sog=6.1, cog=260.0, heading=260.0, nav_status="Under way using engine"),
            ]
        ),
        # Bulk Carrier
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=352001122,
                imo=9654321,
                name="MV Pacific Hope",
                callsign="3FGT2",
                ship_type="Bulk Carrier",
                flag="Panama",
                length_m=225.0,
                beam_m=32.0,
                gross_tonnage=38000,
                risk_weight=0.7
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T01:45:00Z", lat=1.240, lng=103.890, sog=12.2, cog=255.0, heading=255.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:15:00Z", lat=1.238, lng=103.850, sog=12.0, cog=255.0, heading=255.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:45:00Z", lat=1.235, lng=103.810, sog=12.1, cog=255.0, heading=255.0, nav_status="Under way using engine"),
            ]
        ),
        # High-Speed Ferry
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=563004321,
                imo=8943211,
                name="Batam Fast Ferry",
                callsign="9V8812",
                ship_type="Passenger / Cruise",
                flag="Singapore",
                length_m=38.0,
                beam_m=9.0,
                gross_tonnage=350,
                risk_weight=0.1
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T02:05:00Z", lat=1.180, lng=103.860, sog=24.5, cog=330.0, heading=330.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T02:20:00Z", lat=1.220, lng=103.840, sog=24.0, cog=330.0, heading=330.0, nav_status="Under way using engine"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_beta_singapore_strait",
        title="Scenario Beta: Multi-Vessel Confluence",
        description="High-density traffic corridor with 3 simultaneous vessels. The correlation algorithm differentiates a bunkering tanker from a bulk carrier.",
        region_name="Singapore Strait Traffic Separation Scheme (TSS)",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_gamma() -> ScenarioData:
    """
    Scenario Gamma: Low-Wind False Positive Look-Alike Rejection (Bay of Bengal)
    Calm sea surface mimics dark radar signature; system rejects false alarm.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=1.8, # Under 2.5 m/s threshold!
        wind_direction_deg=180.0,
        current_speed_ms=0.20,
        current_direction_deg=0.0,
        sea_state=1,
        surface_temp_c=30.1
    )

    sar_meta = SARImageMetadata(
        scene_id="S1A_IW_GRDH_1SDV_20260901T080000_BAY_OF_BENGAL",
        satellite="Sentinel-1A C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-01T08:00:00Z",
        bounds=[[13.20, 80.80], [13.60, 81.40]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_gamma_lookalike.jpg"
    )

    slick_coords = [
        [81.050, 13.380],
        [81.120, 13.390],
        [81.180, 13.430],
        [81.150, 13.470],
        [81.080, 13.460],
        [81.030, 13.410],
        [81.050, 13.380]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 2.6, # Low damping
        "edge_sharpness": 0.35,  # Diffuse boundary
        "thickness_microns": 0.5
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=13.42,
        base_lng=81.10,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=1.0,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg,
        grid_engine=ocean_grid_engine,
        detection_timestamp=sar_meta.acquisition_time,
    )

    # Nearby fishing trawler
    vessels = [
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419888999,
                name="Sagar Kanya 4",
                ship_type="Fishing Vessel",
                flag="India",
                length_m=28.0,
                beam_m=6.5,
                gross_tonnage=120,
                risk_weight=0.2
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T07:00:00Z", lat=13.400, lng=81.080, sog=4.2, cog=45.0, heading=45.0, nav_status="Engaged in fishing"),
                TelemetryPoint(timestamp="2026-09-01T07:30:00Z", lat=13.415, lng=81.095, sog=3.8, cog=45.0, heading=45.0, nav_status="Engaged in fishing"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_gamma_lookalike",
        title="Scenario Gamma: Look-Alike False Positive Rejection",
        description="Low-wind condition (< 2.0 m/s) in Bay of Bengal creates dark specular radar reflection. The AI engine flags as natural look-alike.",
        region_name="Bay of Bengal // Offshore Chennai",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_delta() -> ScenarioData:
    """
    Scenario Delta: Coastal SPM Pipeline Breach & Reef Threat (Gulf of Kutch, Gujarat)
    A 333m Supertanker (VLCC MT Al-Zubarah) unloads at Vadinar Single Point Mooring (SPM).
    A subsea flexible hose leak releases heavy crude, drifting ENE toward Marine National Park.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=7.8,
        wind_direction_deg=235.0,
        current_speed_ms=0.85,
        current_direction_deg=70.0,
        sea_state=3,
        surface_temp_c=29.8
    )

    sar_meta = SARImageMetadata(
        scene_id="S1C_IW_GRDH_1SDV_20260902T051200_GULF_KUTCH",
        satellite="Sentinel-1C C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-02T05:12:00Z",
        bounds=[[22.35, 69.45], [22.65, 69.80]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_delta_gulf_of_kutch.jpg"
    )

    slick_coords = [
        [69.600, 22.490],
        [69.625, 22.505],
        [69.645, 22.518],
        [69.640, 22.525],
        [69.615, 22.512],
        [69.595, 22.498],
        [69.600, 22.490]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 11.4,
        "edge_sharpness": 0.92,
        "thickness_microns": 4.5
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=22.508,
        base_lng=69.620,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=2.5,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg
    )

    vessels = [
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419003322,
                imo=9789123,
                name="MT Al-Zubarah",
                callsign="AWZB9",
                ship_type="Crude Oil Tanker",
                flag="Panama",
                length_m=333.0,
                beam_m=60.0,
                gross_tonnage=162000,
                risk_weight=1.8
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T02:00:00Z", lat=22.480, lng=69.560, sog=2.1, cog=70.0, heading=68.0, nav_status="Moored"),
                TelemetryPoint(timestamp="2026-09-02T02:42:00Z", lat=origin_lat, lng=origin_lng, sog=0.4, cog=70.0, heading=68.0, nav_status="Moored"),
                TelemetryPoint(timestamp="2026-09-02T03:30:00Z", lat=22.485, lng=69.575, sog=0.5, cog=70.0, heading=68.0, nav_status="Moored"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419000455,
                imo=9345111,
                name="MV Narmada Shield",
                callsign="VWTG1",
                ship_type="Tugboat",
                flag="India",
                length_m=45.0,
                beam_m=12.0,
                gross_tonnage=980,
                risk_weight=0.3
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T02:30:00Z", lat=22.470, lng=69.550, sog=5.2, cog=40.0, heading=40.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T03:00:00Z", lat=22.490, lng=69.570, sog=5.0, cog=40.0, heading=40.0, nav_status="Under way using engine"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419888123,
                imo=9801122,
                name="ICGS Varad",
                callsign="VWC12",
                ship_type="Law Enforcement",
                flag="India",
                length_m=105.0,
                beam_m=13.6,
                gross_tonnage=2400,
                risk_weight=0.1
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T03:00:00Z", lat=22.520, lng=69.530, sog=18.0, cog=110.0, heading=110.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T03:30:00Z", lat=22.505, lng=69.590, sog=17.5, cog=110.0, heading=110.0, nav_status="Under way using engine"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_delta_gulf_of_kutch",
        title="Scenario Delta: Coastal SPM Pipeline Breach",
        description="Crude oil discharge at Vadinar SPM mooring terminal in Gulf of Kutch. System computes Lagrangian drift toward Narara Reef Marine Sanctuary.",
        region_name="Gulf of Kutch // Jamnagar Oil Terminal",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_epsilon() -> ScenarioData:
    """
    Scenario Epsilon: Dark Ship STS Oil Transfer (Gulf of Mannar / Palk Strait, Tamil Nadu)
    Two unflagged tankers execute illicit Ship-to-Ship fuel transfer. Transponder blackout during midnight operation.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=5.2,
        wind_direction_deg=190.0,
        current_speed_ms=0.40,
        current_direction_deg=30.0,
        sea_state=2,
        surface_temp_c=29.1
    )

    sar_meta = SARImageMetadata(
        scene_id="S1A_IW_GRDH_1SDV_20260902T023000_GULF_MANNAR",
        satellite="Sentinel-1A C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-02T02:30:00Z",
        bounds=[[8.65, 78.30], [9.05, 78.65]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_epsilon_gulf_of_mannar.jpg"
    )

    slick_coords = [
        [78.460, 8.840],
        [78.480, 8.855],
        [78.495, 8.865],
        [78.490, 8.870],
        [78.472, 8.858],
        [78.455, 8.845],
        [78.460, 8.840]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 10.2,
        "edge_sharpness": 0.89,
        "thickness_microns": 3.8
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=8.855,
        base_lng=78.475,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=3.0,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg
    )

    vessels = [
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=352999001,
                imo=9128999,
                name="MT Shadow Voyager",
                callsign="3FSH8",
                ship_type="Crude Oil Tanker",
                flag="Panama",
                length_m=228.0,
                beam_m=38.0,
                gross_tonnage=54000,
                risk_weight=2.0
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T22:30:00Z", lat=8.800, lng=78.420, sog=12.5, cog=42.0, heading=40.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T23:30:00Z", lat=origin_lat, lng=origin_lng, sog=1.2, cog=45.0, heading=45.0, nav_status="Not under command"),
                TelemetryPoint(timestamp="2026-09-02T01:00:00Z", lat=8.870, lng=78.490, sog=13.0, cog=42.0, heading=42.0, nav_status="Under way using engine"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=538009123,
                imo=9412000,
                name="MT Blue Coral",
                callsign="V7BC3",
                ship_type="Bunkering Tanker",
                flag="Marshall Islands",
                length_m=110.0,
                beam_m=18.0,
                gross_tonnage=6800,
                risk_weight=1.2
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T23:00:00Z", lat=8.810, lng=78.435, sog=2.5, cog=45.0, heading=45.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-01T23:30:00Z", lat=origin_lat + 0.002, lng=origin_lng + 0.002, sog=1.1, cog=45.0, heading=45.0, nav_status="Not under command"),
                TelemetryPoint(timestamp="2026-09-02T01:15:00Z", lat=8.880, lng=78.510, sog=9.8, cog=45.0, heading=45.0, nav_status="Under way using engine"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419002211,
                imo=9556789,
                name="MV Sethu Express",
                callsign="VWSE2",
                ship_type="General Cargo",
                flag="India",
                length_m=140.0,
                beam_m=22.0,
                gross_tonnage=11200,
                risk_weight=0.4
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-01T23:15:00Z", lat=8.860, lng=78.390, sog=11.5, cog=120.0, heading=120.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T00:15:00Z", lat=8.830, lng=78.450, sog=11.2, cog=120.0, heading=120.0, nav_status="Under way using engine"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_epsilon_gulf_of_mannar",
        title="Scenario Epsilon: Dark Ship STS Oil Transfer",
        description="Unflagged tanker pair performs unauthorized Ship-to-Ship (STS) fuel transfer in Gulf of Mannar corridor with transponder blackout.",
        region_name="Gulf of Mannar // Tuticorin Corridor",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_zeta() -> ScenarioData:
    """
    Scenario Zeta: Deepwater Channel Bilge Dump (Nine Degree Channel, Lakshadweep Atoll)
    International transit tanker flushes dirty bilges near Minicoy Island coral reefs.
    """
    env = EnvironmentalCondition(
        wind_speed_ms=6.0,
        wind_direction_deg=270.0,
        current_speed_ms=0.52,
        current_direction_deg=90.0,
        sea_state=3,
        surface_temp_c=30.2
    )

    sar_meta = SARImageMetadata(
        scene_id="S1B_IW_GRDH_1SDV_20260902T114000_LAKSHADWEEP",
        satellite="Sentinel-1B C-Band SAR",
        mode="IW (Interferometric Wide)",
        polarization="VV + VH",
        acquisition_time="2026-09-02T11:40:00Z",
        bounds=[[9.95, 73.20], [10.35, 73.65]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_zeta_lakshadweep.jpg"
    )

    slick_coords = [
        [73.390, 10.130],
        [73.415, 10.145],
        [73.438, 10.155],
        [73.432, 10.162],
        [73.408, 10.150],
        [73.385, 10.138],
        [73.390, 10.130]
    ]

    slick_specs = [{
        "polygon_coords": slick_coords,
        "radar_damping_db": 8.8,
        "edge_sharpness": 0.85,
        "thickness_microns": 2.9
    }]

    slicks_dict = detector.process_sar_scene(
        scene_id=sar_meta.scene_id,
        base_lat=10.145,
        base_lng=73.410,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=slick_specs
    )
    slicks = [SlickPolygon(**s) for s in slicks_dict]

    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat,
        detect_lng=slicks[0].centroid.lng,
        elapsed_hours=3.2,
        wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg
    )

    vessels = [
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419008877,
                imo=9651122,
                name="MT Indus Star",
                callsign="VWIS9",
                ship_type="Crude Oil Tanker",
                flag="India",
                length_m=274.0,
                beam_m=48.0,
                gross_tonnage=81000,
                risk_weight=1.5
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T07:30:00Z", lat=10.100, lng=73.280, sog=14.8, cog=85.0, heading=85.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T08:24:00Z", lat=origin_lat, lng=origin_lng, sog=4.8, cog=88.0, heading=87.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T09:30:00Z", lat=10.160, lng=73.460, sog=14.2, cog=85.0, heading=85.0, nav_status="Under way using engine"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=636015432,
                imo=9710088,
                name="MV Container Express",
                callsign="A8CE1",
                ship_type="Container Ship",
                flag="Liberia",
                length_m=290.0,
                beam_m=40.0,
                gross_tonnage=74000,
                risk_weight=0.5
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T08:00:00Z", lat=10.210, lng=73.300, sog=18.5, cog=92.0, heading=92.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T09:00:00Z", lat=10.200, lng=73.480, sog=18.2, cog=92.0, heading=92.0, nav_status="Under way using engine"),
            ]
        ),
        VesselTrack(
            metadata=VesselMetadata(
                mmsi=419004567,
                imo=9231122,
                name="MV Kadmat Island",
                callsign="VWKI5",
                ship_type="Passenger / Cruise",
                flag="India",
                length_m=85.0,
                beam_m=15.0,
                gross_tonnage=3400,
                risk_weight=0.2
            ),
            positions=[
                TelemetryPoint(timestamp="2026-09-02T08:15:00Z", lat=10.050, lng=73.350, sog=13.0, cog=350.0, heading=350.0, nav_status="Under way using engine"),
                TelemetryPoint(timestamp="2026-09-02T09:00:00Z", lat=10.180, lng=73.330, sog=12.8, cog=350.0, heading=350.0, nav_status="Under way using engine"),
            ]
        )
    ]

    culprits = correlation_engine.correlate_incident(
        slick=slicks[0],
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        vessel_tracks=vessels
    )

    return ScenarioData(
        id="scenario_zeta_lakshadweep",
        title="Scenario Zeta: Deepwater Channel Bilge Dump",
        description="Illicit bilge cleaning by transit tanker in Nine Degree Channel near Lakshadweep Coral Atolls. High ecological vulnerability warning.",
        region_name="Nine Degree Channel // Lakshadweep Atoll",
        sar_image=sar_meta,
        environmental=env,
        slicks=slicks,
        vessels=vessels,
        drift_origin_cone=origin_cone,
        culprits=culprits
    )

def build_scenario_wakashio_validation() -> ScenarioData:
    """Historical MV Wakashio backtest using the same dynamic drift and AIS pipeline."""
    # These values are reasonable August southern-Indian-Ocean estimates for a
    # demonstration only; they are not sourced ERA5/CMEMS observations.
    env = EnvironmentalCondition(
        wind_speed_ms=5.5, wind_direction_deg=110.0,
        current_speed_ms=0.25, current_direction_deg=260.0,
        sea_state=3, surface_temp_c=25.0,
    )
    # Approximate Pointe d'Esny reef coordinate used only as the public reference.
    reef_lat, reef_lng = -20.438, 57.759
    sar_meta = SARImageMetadata(
        scene_id="HISTORICAL_WAKASHIO_BACKTEST_20200807T120000",
        satellite="Simulated SAR backtest input",
        mode="Historical validation simulation",
        polarization="VV + VH",
        acquisition_time="2020-08-07T12:00:00Z",  # After leakage began around 6 Aug.
        bounds=[[-20.60, 57.50], [-20.25, 57.95]],
        resolution_m=10.0,
        image_url="/sar_samples/scenario_wakashio_validation.jpg",
    )
    # Simulated SAR slick is offset from the reef, so reverse drift has real work.
    slick_coords = [
        [57.505, -20.440], [57.520, -20.435], [57.535, -20.442],
        [57.525, -20.450], [57.510, -20.450], [57.505, -20.440],
    ]
    slicks = [SlickPolygon(**slick) for slick in detector.process_sar_scene(
        scene_id=sar_meta.scene_id, base_lat=-20.443, base_lng=57.520,
        wind_speed_ms=env.wind_speed_ms,
        slick_specs=[{"polygon_coords": slick_coords, "radar_damping_db": 8.8,
                      "edge_sharpness": 0.84, "thickness_microns": 2.5}],
    )]
    origin_lat, origin_lng, origin_cone = drift_engine.backtrack_origin(
        detect_lat=slicks[0].centroid.lat, detect_lng=slicks[0].centroid.lng,
        elapsed_hours=12.0, wind_speed_ms=env.wind_speed_ms,
        wind_direction_from_deg=env.wind_direction_deg,
        current_speed_ms=env.current_speed_ms,
        current_direction_to_deg=env.current_direction_deg,
        grid_engine=ocean_grid_engine, detection_timestamp=sar_meta.acquisition_time,
    )
    wakashio = VesselTrack(
        metadata=VesselMetadata(mmsi=353371000, imo=9337119, name="MV Wakashio",
            callsign="3EIX5", ship_type="Bulk Carrier", flag="Panama",
            length_m=299.95, beam_m=50.0, gross_tonnage=101932, risk_weight=1.2),
        # Half-hourly AIS observations show continuous, stationary grounded status;
        # they intentionally avoid inventing an AIS-gap concealment signal.
        positions=[TelemetryPoint(
            timestamp=f"2020-08-07T{minutes // 60:02d}:{minutes % 60:02d}:00Z",
            lat=reef_lat, lng=reef_lng, sog=0.0, cog=0.0, heading=0.0,
            nav_status="Aground",
        ) for minutes in range(0, 721, 30)],
    )
    culprits = correlation_engine.correlate_incident(slicks[0], origin_lat, origin_lng, [wakashio])
    return ScenarioData(
        id="scenario_wakashio_validation",
        title="Historical Validation Case: MV Wakashio, Mauritius 2020 (publicly documented incident — Pointe d'Esny reef grounding, 25 Jul 2020; oil leakage from ~6 Aug 2020; used to validate system accuracy through backtesting against a known, independently verified outcome)",
        description="Historical backtest against a known, independently verified outcome; not a live investigation or a claim to solve an unknown attribution.",
        region_name="Mauritius // Pointe d'Esny reef (historical validation)",
        sar_image=sar_meta, environmental=env, slicks=slicks, vessels=[wakashio],
        drift_origin_cone=origin_cone, culprits=culprits,
    )

SCENARIOS: Dict[str, ScenarioData] = {
    "scenario_beta_singapore_strait": build_scenario_beta(),
    "scenario_alpha_rogue_tanker": build_scenario_alpha(),
    "scenario_gamma_lookalike": build_scenario_gamma(),
    "scenario_delta_gulf_of_kutch": build_scenario_delta(),
    "scenario_epsilon_gulf_of_mannar": build_scenario_epsilon(),
    "scenario_zeta_lakshadweep": build_scenario_zeta(),
    "scenario_wakashio_validation": build_scenario_wakashio_validation(),
}
