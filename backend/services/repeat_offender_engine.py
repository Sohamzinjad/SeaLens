"""
Repeat Offender Intelligence Network Service.
Cross-references vessel MMSIs across multi-incident satellite databases and historical maritime enforcement logs
to identify serial polluters and escalate legal prosecution priority.
"""
from typing import Dict, List, Optional
from backend.models import RepeatOffenderProfile, HistoricalIncident

HISTORICAL_INCIDENTS_DB: Dict[int, List[HistoricalIncident]] = {
    # MMSI 419001234: MT Ocean Titan (Crude Oil Tanker)
    419001234: [
        HistoricalIncident(
            incident_id="HIST-2025-089",
            timestamp="2025-11-14T03:20:00Z",
            location_name="Malacca Strait Traffic Separation Scheme",
            region="Southeast Asia Transit Corridor",
            lat=2.450,
            lng=101.880,
            estimated_volume_m3=45.0,
            spill_type="Illicit Tank Washout Slops Discharge",
            enforcement_action="Coast Guard Fine Issued ($120,000 USD - Unpaid)",
            evidence_source="EMSA CleanSeaNet SAR + Singapore VTS Radar"
        ),
        HistoricalIncident(
            incident_id="HIST-2026-031",
            timestamp="2026-03-22T14:10:00Z",
            location_name="Gulf of Oman Deep Water Tanker Route",
            region="Middle East Maritime Operations Zone",
            lat=24.120,
            lng=58.450,
            estimated_volume_m3=28.5,
            spill_type="Heavy Fuel Oil Residue Release",
            enforcement_action="Interpol Maritime Red Watchlist Citation Issued",
            evidence_source="Sentinel-1A SAR + AIS Anomaly Engine"
        )
    ],
    # MMSI 563009876: Bunker Star 8 (Bunkering Tanker)
    563009876: [
        HistoricalIncident(
            incident_id="HIST-2026-012",
            timestamp="2026-01-18T19:45:00Z",
            location_name="Johor Offshore Bunkering Anchorage",
            region="Singapore Strait Eastern Approaches",
            lat=1.280,
            lng=104.120,
            estimated_volume_m3=12.0,
            spill_type="Bunkering Overflow Discharge",
            enforcement_action="MPA Regulatory Safety Audit & Formal Warning",
            evidence_source="Harbor Patrol Reconnaissance"
        )
    ]
}

KNOWN_VESSEL_METADATA: Dict[int, Dict[str, str]] = {
    419001234: {"name": "MT Ocean Titan", "type": "Crude Oil Tanker", "flag": "Panama"},
    563009876: {"name": "Bunker Star 8", "type": "Bunkering Tanker", "flag": "Singapore"},
    228394000: {"name": "CMA CGM Mumbai", "type": "Container Ship", "flag": "France"},
    538004521: {"name": "Smit Lion", "type": "Tugboat", "flag": "Marshall Islands"},
    352001122: {"name": "MV Pacific Hope", "type": "Bulk Carrier", "flag": "Panama"},
    563004321: {"name": "Batam Fast Ferry", "type": "Passenger / Cruise", "flag": "Singapore"},
    419888999: {"name": "Sagar Kanya 4", "type": "Fishing Vessel", "flag": "India"},
}

class RepeatOffenderEngine:
    """
    Cross-references vessel telemetry and attribution results against multi-incident databases
    to detect serial polluters and build prosecution profiles.
    """
    def __init__(self, historical_db: Optional[Dict[int, List[HistoricalIncident]]] = None):
        self.db = historical_db if historical_db is not None else HISTORICAL_INCIDENTS_DB

    def get_profile(self, mmsi: int, active_scenarios: Optional[Dict[str, Any]] = None) -> RepeatOffenderProfile:
        """
        Generates a comprehensive Repeat Offender Intelligence Profile for a given vessel MMSI.
        """
        hist_incidents = self.db.get(mmsi, [])
        meta = KNOWN_VESSEL_METADATA.get(mmsi, {"name": f"Vessel-{mmsi}", "type": "Unknown", "flag": "Unknown"})

        active_matches = []
        if active_scenarios:
            for sc_id, sc in active_scenarios.items():
                # Check if vessel appears in culprits with composite score >= 45%
                if hasattr(sc, "culprits"):
                    for culprit in sc.culprits:
                        if culprit.mmsi == mmsi and culprit.composite_score >= 45.0:
                            active_matches.append(f"{sc.title} ({sc.region_name}) - Composite Score: {culprit.composite_score:.1f}% [{culprit.verdict}]")

        total_count = len(hist_incidents) + len(active_matches)

        if total_count >= 3:
            serial_level = "SERIAL OFFENDER (LEVEL 3 - CRITICAL)"
            is_serial = True
            priority = "PRIORITY 1 - IMMEDIATE PORT STATE ARREST & ASSET SEIZURE"
            protocol = (
                f"FLAGGED AS REPEAT SERIAL POLLUTER ({total_count} LOGGED INCIDENTS). Dispatch naval/coast guard interceptor "
                f"for immediate boarding upon entering territorial waters. Issue UN/MARPOL Annex I seizure warrant and "
                f"notify Flag State maritime administration ({meta['flag']})."
            )
        elif total_count == 2:
            serial_level = "RECURRING SUSPECT (LEVEL 2 - ELEVATED)"
            is_serial = True
            priority = "PRIORITY 2 - HIGH-RISK BOARDING & INSPECTION WARRANT"
            protocol = (
                f"RECURRING VIOLATIONS DETECTED ({total_count} LOGGED INCIDENTS). Mandate Port State Control (PSC) "
                f"forensic oil-sampling inspection at next port of call. Place vessel under 24/7 AIS & SAR satellite surveillance."
            )
        elif total_count == 1:
            serial_level = "SINGLE INCIDENT LOGGED (LEVEL 1)"
            is_serial = False
            priority = "MONITORING & PORT AUDIT"
            protocol = "Log incident into Maritime Domain Awareness database. Issue formal inquiry to vessel operator and Flag State."
        else:
            serial_level = "CLEARED / NO HISTORICAL VIOLATIONS"
            is_serial = False
            priority = "ROUTINE MARITIME COMPLIANCE"
            protocol = "No enforcement action required. Vessel maintains clean environmental compliance record."

        return RepeatOffenderProfile(
            mmsi=mmsi,
            vessel_name=meta["name"],
            ship_type=meta["type"],
            flag=meta["flag"],
            total_incidents_logged=total_count,
            serial_offender_level=serial_level,
            is_serial_offender=is_serial,
            prosecution_priority=priority,
            historical_incidents=hist_incidents,
            active_scenario_matches=active_matches,
            recommended_interception_protocol=protocol
        )
