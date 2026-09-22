"""
Unit tests for seaLens Final Innovation Refinements:
1. Repeat Offender Intelligence Network
2. Natural Language Intelligence Brief Generator
3. Real SHA-256 Cryptographic Evidence Integrity Chain
"""
import pytest
import re
from backend.services.repeat_offender_engine import RepeatOffenderEngine
from backend.services.intelligence_brief_generator import generate_intelligence_brief
from backend.services.report_generator import generate_markdown_dossier
from backend.scenarios_data import (
    build_scenario_alpha, build_scenario_beta, build_scenario_gamma,
    build_scenario_delta, build_scenario_epsilon, build_scenario_zeta, SCENARIOS
)

def test_repeat_offender_engine_serial_offender():
    engine = RepeatOffenderEngine()
    alpha = build_scenario_alpha()
    
    # Test MT Ocean Titan (MMSI: 419001234) - has 2 historical + 1 active match = 3 total
    profile = engine.get_profile(419001234, active_scenarios={"alpha": alpha})
    assert profile.mmsi == 419001234
    assert profile.vessel_name == "MT Ocean Titan"
    assert profile.total_incidents_logged >= 3
    assert profile.is_serial_offender is True
    assert "LEVEL 3" in profile.serial_offender_level
    assert "IMMEDIATE PORT STATE ARREST" in profile.prosecution_priority

def test_repeat_offender_engine_cleared_vessel():
    engine = RepeatOffenderEngine()
    # Test CMA CGM Mumbai (MMSI: 228394000) - 0 historical, low score
    profile = engine.get_profile(228394000)
    assert profile.mmsi == 228394000
    assert profile.is_serial_offender is False
    assert "CLEARED" in profile.serial_offender_level

def test_intelligence_brief_generator():
    alpha = build_scenario_alpha()
    brief = generate_intelligence_brief(alpha)
    
    assert brief["scenario_id"] == "scenario_alpha_rogue_tanker"
    assert "NTRO-MDA-CABLE-2026" in brief["cable_id"]
    assert brief["classification"] == "RESTRICTED // MARITIME SIGNALS & SAR INTELLIGENCE"
    assert "MT Ocean Titan" in brief["executive_summary"]
    assert "45-minute AIS transponder blackout" in brief["executive_summary"] or "Blackout" in brief["executive_summary"]
    assert brief["threat_level"] == "CRITICAL"

def test_sha256_cryptographic_evidence_dossier():
    alpha = build_scenario_alpha()
    dossier = generate_markdown_dossier(alpha)
    
    # Verify report contains SHA-256 evidence digest section
    assert "Evidence Integrity Hash:" in dossier
    
    # Extract hash matching SHA256:[a-f0-9]{64}
    match = re.search(r"SHA256:([a-f0-9]{64})", dossier)
    assert match is not None, "Dossier should contain a valid 64-character SHA-256 hex digest"
    sha256_hex = match.group(1)
    assert len(sha256_hex) == 64

def test_all_six_scenarios():
    assert len(SCENARIOS) == 6
    assert "scenario_delta_gulf_of_kutch" in SCENARIOS
    assert "scenario_epsilon_gulf_of_mannar" in SCENARIOS
    assert "scenario_zeta_lakshadweep" in SCENARIOS

    for sc_id, sc in SCENARIOS.items():
        assert sc.id == sc_id
        assert len(sc.slicks) > 0
        assert len(sc.vessels) > 0
        assert sc.sar_image.scene_id is not None

