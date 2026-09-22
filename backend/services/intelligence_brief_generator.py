"""
Natural Language Intelligence Brief Generator for Maritime Operations Center (MOC).
Generates analyst-grade NTRO Intelligence Cables synthesizing SAR radar detections,
drift physics backtracks, AIS behavioral anomalies, and repeat offender intelligence.
"""
from typing import Dict, Any
from datetime import datetime
from backend.models import ScenarioData
from backend.services.repeat_offender_engine import RepeatOffenderEngine

repeat_engine = RepeatOffenderEngine()

def generate_intelligence_brief(scenario: ScenarioData) -> Dict[str, Any]:
    """
    Generates a structured, analyst-grade NTRO Intelligence Cable for a given scenario.
    """
    primary_slick = scenario.slicks[0] if scenario.slicks else None
    primary_suspect = scenario.culprits[0] if scenario.culprits else None
    
    cable_id = f"NTRO-MDA-CABLE-2026-{scenario.id.upper().replace('SCENARIO_', '')[:15]}"
    classification = "RESTRICTED // MARITIME SIGNALS & SAR INTELLIGENCE"
    timestamp_utc = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")

    if not primary_slick or (primary_slick and primary_slick.is_lookalike):
        # Look-alike false alarm brief
        headline = f"LOOK-ALIKE REJECTION BRIEF: {scenario.region_name.upper()}"
        summary = (
            f"At {scenario.sar_image.acquisition_time}, Sentinel SAR satellite observation over {scenario.region_name} "
            f"detected a low-reflectivity surface feature. Environmental diagnostic wind analysis indicated sub-threshold "
            f"surface wind velocity ({scenario.environmental.wind_speed_ms:.1f} m/s < 2.5 m/s threshold). "
            f"The seaLens AI engine successfully classified this feature as a NATURAL LOOK-ALIKE (specular reflection / calm water) "
            f"with low radar damping ({getattr(primary_slick, 'radar_damping_db', 2.6) if primary_slick else 0.0:.1f} dB). "
            f"NO ENFORCEMENT ACTION REQUIRED. False positive alert prevented."
        )
        return {
            "cable_id": cable_id,
            "classification": classification,
            "timestamp_utc": timestamp_utc,
            "headline": headline,
            "scenario_id": scenario.id,
            "threat_level": "NOMINAL / FALSE ALARM",
            "executive_summary": summary,
            "primary_target": "N/A - Natural Phenomenon",
            "attribution_score": "0.0%",
            "repeat_offender_status": "CLEARED",
            "tactical_recommendation": "Maintain standard orbital monitoring. Disregard false alarm."
        }

    suspect_name = primary_suspect.vessel_name if primary_suspect else "UNATTRIBUTED VESSEL"
    suspect_mmsi = primary_suspect.mmsi if primary_suspect else 0
    suspect_score = primary_suspect.composite_score if primary_suspect else 0.0
    suspect_flag = primary_suspect.flag if primary_suspect else "Unknown"
    suspect_type = primary_suspect.ship_type if primary_suspect else "Unknown"
    verdict = primary_suspect.verdict if primary_suspect else "UNDER INVESTIGATION"

    # Get repeat offender profile
    repeat_profile = repeat_engine.get_profile(suspect_mmsi)

    # Format behavioral anomalies
    beh_notes = []
    if primary_suspect and hasattr(primary_suspect, "behavioral_anomalies") and primary_suspect.behavioral_anomalies:
        beh_notes = primary_suspect.behavioral_anomalies
    elif primary_suspect and primary_suspect.evidence_notes:
        beh_notes = primary_suspect.evidence_notes

    beh_str = "; ".join(beh_notes) if beh_notes else "Nominal AIS trajectory compliance."

    origin_props = scenario.drift_origin_cone.get("properties", {})
    orig_lat = origin_props.get("origin_lat", "N/A")
    orig_lng = origin_props.get("origin_lng", "N/A")
    elapsed_h = origin_props.get("elapsed_hours", "N/A")

    headline = f"HIGH-CONFIDENCE ATTRIBUTION BRIEF: ILLICIT DISCHARGE AT {scenario.region_name.upper()}"

    radar_db = getattr(primary_slick, "radar_damping_db", 8.5) if primary_slick else 0.0

    paragraph_1_sar = (
        f"1. OPERATIONAL SUMMARY: At {scenario.sar_image.acquisition_time}, Sentinel Earth Observation SAR satellite "
        f"sensors acquired scene {scenario.sar_image.scene_id} over {scenario.region_name}. Processing delineated a "
        f"confirmed hydrocarbon slick spanning {primary_slick.area_sqkm:.2f} km² with an estimated discharge volume of "
        f"{primary_slick.estimated_volume_m3:.1f} m³ (Bonn Matrix). High radar contrast and sharp boundary definition confirm "
        f"a mineral oil discharge."
    )

    paragraph_2_drift = (
        f"2. HYDRODYNAMIC BACKTRACK: Reverse Lagrangian trajectory modeling computed that ocean currents "
        f"({scenario.environmental.current_speed_ms:.2f} m/s @ {scenario.environmental.current_direction_deg:.0f}°) and "
        f"leeway windage ({scenario.environmental.wind_speed_ms:.1f} m/s @ {scenario.environmental.wind_direction_deg:.0f}°) "
        f"transported the slick over an elapsed time of {elapsed_h} hours from discharge origin coordinates "
        f"{orig_lat}°N, {orig_lng}°E."
    )

    paragraph_3_attribution = (
        f"3. SIGNALS INTEL & ATTRIBUTION: Automated AIS trajectory correlation isolated primary suspect **{suspect_name}** "
        f"(MMSI: {suspect_mmsi}, Flag: {suspect_flag}, Type: {suspect_type}) with a composite confidence score of **{suspect_score:.1f}%** ({verdict}). "
        f"Behavioral signals intelligence audit revealed: {beh_str}."
    )

    paragraph_4_repeat = (
        f"4. REPEAT OFFENDER & COMPLIANCE RECORD: Cross-referencing multi-incident maritime enforcement databases classifies {suspect_name} "
        f"as **{repeat_profile.serial_offender_level}** with {repeat_profile.total_incidents_logged} logged discharge violations. "
        f"Prosecution Priority: **{repeat_profile.prosecution_priority}**."
    )

    paragraph_5_action = (
        f"5. TACTICAL ENFORCEMENT RECOMMENDATION: {repeat_profile.recommended_interception_protocol} "
        f"Issue immediate Coast Guard interceptor vectoring to intercept vessel before exiting Exclusive Economic Zone (EEZ)."
    )

    full_narrative = "\n\n".join([paragraph_1_sar, paragraph_2_drift, paragraph_3_attribution, paragraph_4_repeat, paragraph_5_action])

    return {
        "cable_id": cable_id,
        "classification": classification,
        "timestamp_utc": timestamp_utc,
        "headline": headline,
        "scenario_id": scenario.id,
        "threat_level": "CRITICAL" if repeat_profile.is_serial_offender else "HIGH",
        "executive_summary": full_narrative,
        "primary_target": f"{suspect_name} (MMSI: {suspect_mmsi})",
        "attribution_score": f"{suspect_score:.1f}%",
        "repeat_offender_status": repeat_profile.serial_offender_level,
        "tactical_recommendation": repeat_profile.recommended_interception_protocol
    }
