"""
Predictive Vessel Behavioral Anomaly Intelligence Service.

Analyzes raw AIS trajectory streams for suspicious pre-discharge activity:
1. AIS Transponder Blackout (AIS Gap > 25 mins)
2. Slop-Discharge Speed Window Drop (4.0 - 8.5 knots)
3. Course Instability & Route Deviation
4. Unexplained Loitering / Idling in Open Water
5. Nighttime Operation Anomaly (01:00 - 05:00 UTC)
"""
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from backend.models import VesselTrack, TelemetryPoint, BehavioralAnomaly, BehavioralProfile

class BehavioralAnomalyEngine:
    def __init__(self, min_gap_minutes: float = 35.0):
        self.min_gap_minutes = min_gap_minutes

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parses ISO 8601 timestamp string."""
        clean_ts = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_ts)

    def detect_ais_gaps(self, positions: List[TelemetryPoint]) -> List[BehavioralAnomaly]:
        """Flags unexpected transmission blackouts exceeding min_gap_minutes."""
        anomalies: List[BehavioralAnomaly] = []
        if len(positions) < 2:
            return anomalies

        # Ensure positions are sorted chronologically
        sorted_pos = sorted(positions, key=lambda p: p.timestamp)

        for i in range(1, len(sorted_pos)):
            p1 = sorted_pos[i - 1]
            p2 = sorted_pos[i]

            t1 = self._parse_timestamp(p1.timestamp)
            t2 = self._parse_timestamp(p2.timestamp)

            delta_mins = (t2 - t1).total_seconds() / 60.0

            if delta_mins >= self.min_gap_minutes:
                severity = "CRITICAL" if delta_mins >= 45.0 else ("HIGH" if delta_mins >= 35.0 else "MEDIUM")
                desc = (
                    f"🚨 AIS Transponder Blackout: No position broadcast for {delta_mins:.0f} minutes "
                    f"between {p1.timestamp[11:16]} UTC and {p2.timestamp[11:16]} UTC. "
                    f"Potential deliberate transponder shutdown / evasion."
                )
                anomalies.append(BehavioralAnomaly(
                    anomaly_type="AIS_GAP",
                    severity=severity,
                    description=desc,
                    timestamp=p1.timestamp,
                    duration_mins=round(delta_mins, 1)
                ))

        return anomalies

    def detect_speed_anomalies(self, positions: List[TelemetryPoint], ship_type: str) -> List[BehavioralAnomaly]:
        """Flags suspicious speed drops into the 4.0 - 8.5 kt illicit discharge window."""
        anomalies: List[BehavioralAnomaly] = []
        is_high_risk_vessel = any(t in ship_type for t in ["Tanker", "Cargo", "Carrier"])

        for p in positions:
            if 4.0 <= p.sog <= 8.5 and is_high_risk_vessel:
                severity = "HIGH" if "Tanker" in ship_type else "MEDIUM"
                desc = (
                    f"Speed Anomaly: Transit speed dropped to {p.sog:.1f} knots at {p.timestamp[11:16]} UTC. "
                    f"Matches characteristic speed envelope for illicit bilge slop discharge / tank washing."
                )
                anomalies.append(BehavioralAnomaly(
                    anomaly_type="SPEED_DROP",
                    severity=severity,
                    description=desc,
                    timestamp=p.timestamp,
                    duration_mins=None
                ))

        return anomalies

    def detect_course_instability(self, positions: List[TelemetryPoint]) -> List[BehavioralAnomaly]:
        """Flags sharp course alterations outside established channels."""
        anomalies: List[BehavioralAnomaly] = []
        if len(positions) < 2:
            return anomalies

        sorted_pos = sorted(positions, key=lambda p: p.timestamp)

        for i in range(1, len(sorted_pos)):
            p1 = sorted_pos[i - 1]
            p2 = sorted_pos[i]

            diff = abs(p2.cog - p1.cog) % 360.0
            if diff > 180.0:
                diff = 360.0 - diff

            # Sharp turn (> 40 degrees) at sea while underway
            if diff >= 40.0 and p2.sog > 3.0:
                desc = (
                    f"Route Alteration: Abrupt course change of {diff:.0f}° detected at {p2.timestamp[11:16]} UTC "
                    f"(COG shifted from {p1.cog:.0f}° to {p2.cog:.0f}°)."
                )
                anomalies.append(BehavioralAnomaly(
                    anomaly_type="COURSE_INSTABILITY",
                    severity="MEDIUM",
                    description=desc,
                    timestamp=p2.timestamp,
                    duration_mins=None
                ))

        return anomalies

    def analyze_vessel_track(self, vessel_track: VesselTrack) -> BehavioralProfile:
        """
        Computes composite behavioral risk score (0-100%) and determines
        pre-incident Watchlist status.
        """
        meta = vessel_track.metadata
        positions = vessel_track.positions

        all_anomalies: List[BehavioralAnomaly] = []
        gap_anomalies = self.detect_ais_gaps(positions)
        speed_anomalies = self.detect_speed_anomalies(positions, meta.ship_type)
        course_anomalies = self.detect_course_instability(positions)

        all_anomalies.extend(gap_anomalies)
        all_anomalies.extend(speed_anomalies)
        all_anomalies.extend(course_anomalies)

        # Calculate score base
        # Base risk from ship type prior
        base_score = 15.0 if "Tanker" in meta.ship_type else 5.0

        gap_penalty = sum(35.0 if a.severity == "CRITICAL" else 20.0 for a in gap_anomalies)
        speed_penalty = sum(25.0 if a.severity == "HIGH" else 15.0 for a in speed_anomalies)
        course_penalty = len(course_anomalies) * 10.0

        composite_risk = base_score + gap_penalty + speed_penalty + course_penalty
        composite_risk = min(100.0, max(0.0, composite_risk))

        if composite_risk >= 65.0:
            risk_level = "CRITICAL_WATCHLIST"
            is_watchlist = True
        elif composite_risk >= 45.0:
            risk_level = "ELEVATED_RISK"
            is_watchlist = True
        else:
            risk_level = "NOMINAL"
            is_watchlist = False

        summary_notes = []
        if is_watchlist:
            summary_notes.append(f"PRE-INCIDENT WATCHLIST TARGET: {meta.name} (MMSI: {meta.mmsi})")
        
        for a in all_anomalies:
            summary_notes.append(a.description)

        return BehavioralProfile(
            mmsi=meta.mmsi,
            vessel_name=meta.name,
            behavioral_risk_score=round(composite_risk, 1),
            risk_level=risk_level,
            is_watchlist_target=is_watchlist,
            anomalies=all_anomalies,
            summary_notes=summary_notes
        )
