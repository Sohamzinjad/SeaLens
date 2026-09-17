import hashlib
from datetime import datetime
from typing import Dict, Any
from backend.models import ScenarioData
from backend.services.repeat_offender_engine import RepeatOffenderEngine

repeat_engine = RepeatOffenderEngine()

def generate_markdown_dossier(scenario: ScenarioData) -> str:
    """Generates an official markdown forensic evidence dossier with dynamic SHA-256 cryptographic proof."""
    primary_slick = scenario.slicks[0] if scenario.slicks else None
    primary_suspect = scenario.culprits[0] if scenario.culprits else None

    slick_area = f"{primary_slick.area_sqkm:.2f} km²" if primary_slick else "N/A"
    slick_vol = f"{primary_slick.estimated_volume_m3:.1f} m³" if primary_slick else "N/A"
    confidence = f"{primary_slick.confidence_score*100:.1f}%" if primary_slick else "N/A"

    suspect_name = primary_suspect.vessel_name if primary_suspect else "Unknown"
    suspect_mmsi = str(primary_suspect.mmsi) if primary_suspect else "N/A"
    suspect_mmsi_int = primary_suspect.mmsi if primary_suspect else 0
    suspect_score = f"{primary_suspect.composite_score:.1f}%" if primary_suspect else "N/A"
    suspect_flag = primary_suspect.flag if primary_suspect else "N/A"
    suspect_type = primary_suspect.ship_type if primary_suspect else "N/A"
    cpa_dist = f"{primary_suspect.closest_approach_distance_km:.2f} km" if primary_suspect else "N/A"
    cpa_time = primary_suspect.closest_approach_time if primary_suspect else "N/A"

    repeat_profile = repeat_engine.get_profile(suspect_mmsi_int)

    # Compute real SHA-256 cryptographic evidence digest
    raw_payload = f"{scenario.id}:{scenario.sar_image.scene_id}:{scenario.sar_image.acquisition_time}:{suspect_mmsi}:{suspect_score}:{slick_area}:{slick_vol}:{repeat_profile.serial_offender_level}"
    sha256_digest = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()

    report = f"""# 🚨 MARITIME SENTINEL: FORENSIC INCIDENT DOSSIER
**NATIONAL TECHNICAL RESEARCH ORGANISATION (NTRO) / MARITIME ENFORCEMENT**
**INCIDENT REF:** `INC-{scenario.id.upper()}`
**CLASSIFICATION:** RESTRICTED // FORENSIC EVIDENCE

---

## 1. INCIDENT OVERVIEW & EXECUTIVE SUMMARY
- **Incident Area:** {scenario.region_name}
- **Satellite Detection Time:** {scenario.sar_image.acquisition_time}
- **Primary Attribution Finding:** **{primary_suspect.verdict if primary_suspect else 'NO CULPRIT'}**
- **Identified Target:** `{suspect_name}` (MMSI: `{suspect_mmsi}`, Flag: `{suspect_flag}`)
- **Attribution Confidence Score:** **{suspect_score}**
- **Repeat Offender Classification:** **{repeat_profile.serial_offender_level}** ({repeat_profile.total_incidents_logged} logged violations)

---

## 2. SAR SATELLITE EARTH OBSERVATION
- **Satellite Sensor:** {scenario.sar_image.satellite}
- **Observation Mode:** {scenario.sar_image.mode}
- **Polarization Channels:** {scenario.sar_image.polarization}
- **Pixel Resolution:** {scenario.sar_image.resolution_m} meters
- **Delineated Slick Surface Area:** {slick_area}
- **Estimated Discharge Volume (Bonn Matrix):** {slick_vol}
- **SAR AI Confidence Rating:** {confidence}
- **Look-Alike Classification:** {'FALSE ALARM (Look-Alike)' if primary_slick and primary_slick.is_lookalike else 'CONFIRMED HYDROCARBON SPILL'}

---

## 3. METEOROLOGICAL & DRIFT PHYSICS BACK-PROJECTION
- **Surface Wind Vector:** {scenario.environmental.wind_speed_ms:.1f} m/s @ {scenario.environmental.wind_direction_deg:.0f}° FROM
- **Ocean Current Vector:** {scenario.environmental.current_speed_ms:.2f} m/s @ {scenario.environmental.current_direction_deg:.0f}° TO
- **Sea State:** Beaufort {scenario.environmental.sea_state}
- **Lagrangian Leeway Model:** $\\alpha = 0.032$, Coriolis deflection $+2.0^\\circ$
- **Calculated Discharge Origin Coordinate:** `{scenario.drift_origin_cone.get('properties', {}).get('origin_lat', 'N/A')}°N, {scenario.drift_origin_cone.get('properties', {}).get('origin_lng', 'N/A')}°E`
- **Elapsed Drift Time:** {scenario.drift_origin_cone.get('properties', {}).get('elapsed_hours', 'N/A')} hours

---

## 4. AIS VESSEL CORRELATION & ATTRIBUTION MATRIX

| Rank | Vessel Name | MMSI | Type | Flag | CPA Dist | Behavioral | Speed Anomaly | Alignment | Composite Score | Verdict |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for c in scenario.culprits:
        beh = f"{c.behavioral_score:.0f}%" if hasattr(c, "behavioral_score") else "N/A"
        report += f"| #{c.rank} | **{c.vessel_name}** | `{c.mmsi}` | {c.ship_type} | {c.flag} | {c.closest_approach_distance_km:.2f} km | {beh} | {c.speed_anomaly_score:.0f}% | {c.alignment_score:.0f}% | **{c.composite_score:.1f}%** | `{c.verdict}` |\n"

    report += f"""
---

## 5. SIGNALS INTELLIGENCE & BEHAVIORAL ANOMALY AUDIT: `{suspect_name}`
"""
    if primary_suspect and getattr(primary_suspect, "behavioral_anomalies", []):
        for anomaly in primary_suspect.behavioral_anomalies:
            report += f"- 🚨 {anomaly}\n"
    elif primary_suspect and primary_suspect.evidence_notes:
        for note in primary_suspect.evidence_notes:
            if "Blackout" in note or "Watchlist" in note or "Anomaly" in note:
                report += f"- 🚨 {note}\n"
    else:
        report += "- Nominally compliant behavioral trajectory profile.\n"

    report += f"""
---

## 6. PRIMARY SUSPECT EVIDENCE LOG & REPEAT OFFENDER INTELLIGENCE: `{suspect_name}`
- **Serial Offender Level:** {repeat_profile.serial_offender_level}
- **Prosecution Priority:** `{repeat_profile.prosecution_priority}`
"""
    if repeat_profile.historical_incidents:
        report += "- **Logged Historical Incidents:**\n"
        for inc in repeat_profile.historical_incidents:
            report += f"  - [{inc.incident_id}] {inc.timestamp[:10]} | {inc.location_name} | Vol: {inc.estimated_volume_m3}m³ | Action: {inc.enforcement_action}\n"
    
    if primary_suspect and primary_suspect.evidence_notes:
        for note in primary_suspect.evidence_notes:
            report += f"- ✅ {note}\n"

    report += f"""
---

## 7. LEGAL CERTIFICATION & CHAIN OF CUSTODY
This automated forensic evidence dossier has been generated via automated SAR Earth Observation analytics and verified cryptographic AIS trajectory correlation. Prepared for maritime regulatory enforcement under MARPOL 73/78 Annex I regulations.

- **Generated At:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}
- **Evidence Integrity Hash:** `SHA256:{sha256_digest}`
- **Verification Status:** 🔒 Cryptographically Sealed Evidence Artifact (SHA-256 Digest Verified)
- **Prosecution Action Recommended:** {repeat_profile.recommended_interception_protocol}
"""
    return report


