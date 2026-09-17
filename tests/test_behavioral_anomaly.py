"""
Unit tests for the Predictive Vessel Behavioral Anomaly Intelligence Engine & API endpoints.
"""
import pytest
from backend.models import VesselTrack, VesselMetadata, TelemetryPoint, SlickPolygon, GeoPoint
from backend.services.behavioral_anomaly_engine import BehavioralAnomalyEngine
from backend.services.correlation_engine import AISCorrelationEngine
from backend.scenarios_data import SCENARIOS, build_scenario_alpha

def test_detect_ais_gaps():
    engine = BehavioralAnomalyEngine(min_gap_minutes=25.0)

    # Track with a 45-minute blackout
    positions = [
        TelemetryPoint(timestamp="2026-09-01T01:00:00Z", lat=18.0, lng=72.0, sog=12.0, cog=45.0, nav_status="Under way"),
        TelemetryPoint(timestamp="2026-09-01T01:15:00Z", lat=18.1, lng=72.1, sog=12.0, cog=45.0, nav_status="Under way"),
        # 45 min gap
        TelemetryPoint(timestamp="2026-09-01T02:00:00Z", lat=18.3, lng=72.3, sog=5.5, cog=45.0, nav_status="Under way"),
    ]

    gaps = engine.detect_ais_gaps(positions)
    assert len(gaps) == 1
    assert gaps[0].anomaly_type == "AIS_GAP"
    assert gaps[0].severity == "CRITICAL"
    assert gaps[0].duration_mins == 45.0

def test_detect_speed_anomalies():
    engine = BehavioralAnomalyEngine()

    positions = [
        TelemetryPoint(timestamp="2026-09-01T01:00:00Z", lat=18.0, lng=72.0, sog=14.0, cog=45.0, nav_status="Under way"),
        # Speed drop to 5.2 knots (slop washing window)
        TelemetryPoint(timestamp="2026-09-01T01:30:00Z", lat=18.1, lng=72.1, sog=5.2, cog=45.0, nav_status="Under way"),
    ]

    speed_anomalies = engine.detect_speed_anomalies(positions, "Crude Oil Tanker")
    assert len(speed_anomalies) == 1
    assert speed_anomalies[0].anomaly_type == "SPEED_DROP"
    assert speed_anomalies[0].severity == "HIGH"

def test_behavioral_profile_watchlist():
    engine = BehavioralAnomalyEngine()
    track = VesselTrack(
        metadata=VesselMetadata(
            mmsi=419001234,
            name="MT Ocean Titan",
            ship_type="Crude Oil Tanker",
            flag="Panama",
            length_m=245.0,
            beam_m=42.0,
            gross_tonnage=62500
        ),
        positions=[
            TelemetryPoint(timestamp="2026-09-01T01:00:00Z", lat=18.0, lng=72.0, sog=14.0, cog=45.0, nav_status="Under way"),
            TelemetryPoint(timestamp="2026-09-01T01:15:00Z", lat=18.1, lng=72.1, sog=13.0, cog=45.0, nav_status="Under way"),
            # 45 min gap + speed drop
            TelemetryPoint(timestamp="2026-09-01T02:00:00Z", lat=18.3, lng=72.3, sog=5.2, cog=45.0, nav_status="Under way"),
        ]
    )

    prof = engine.analyze_vessel_track(track)
    assert prof.is_watchlist_target is True
    assert prof.risk_level == "CRITICAL_WATCHLIST"
    assert prof.behavioral_risk_score >= 70.0
    assert len(prof.anomalies) == 2  # Gap + Speed drop

def test_correlation_engine_behavioral_fusion():
    corr_engine = AISCorrelationEngine()
    sc = build_scenario_alpha()

    matches = corr_engine.correlate_incident(
        slick=sc.slicks[0],
        origin_lat=sc.drift_origin_cone["properties"]["origin_lat"],
        origin_lng=sc.drift_origin_cone["properties"]["origin_lng"],
        vessel_tracks=sc.vessels
    )

    top_match = matches[0]
    assert top_match.vessel_name == "MT Ocean Titan"
    assert top_match.verdict == "PRIMARY SUSPECT"
    assert top_match.behavioral_score >= 70.0
    assert any("WATCHLIST" in note for note in top_match.evidence_notes)
