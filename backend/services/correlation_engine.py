"""
AIS Vessel Trajectory Correlation & Culprit Attribution Engine.

Performs spatio-temporal intersections between reverse-projected oil spill origin
and historical AIS vessel tracks to rank suspect vessels with quantifiable forensic metrics.
"""
import math
from datetime import datetime
from typing import List, Dict, Any, Tuple
from ml_engine.metrics import haversine_distance_km
from backend.models import VesselTrack, SlickPolygon, CulpritMatch, TelemetryPoint
from backend.services.behavioral_anomaly_engine import BehavioralAnomalyEngine

VESSEL_TYPE_PRIORS = {
    "Crude Oil Tanker": 95.0,
    "Chemical Tanker": 90.0,
    "Bunkering Tanker": 88.0,
    "Oil Products Tanker": 82.0,
    "Bulk Carrier": 55.0,
    "Container Ship": 40.0,
    "General Cargo": 35.0,
    "Fishing Vessel": 20.0,
    "Tugboat": 15.0,
    "Passenger / Cruise": 5.0,
    "Pleasure Craft": 5.0,
}

class AISCorrelationEngine:
    def __init__(
        self,
        max_search_radius_km: float = 8.0,
        w_prox: float = 0.35,
        w_speed: float = 0.15,
        w_vessel: float = 0.15,
        w_align: float = 0.15,
        w_behavioral: float = 0.20
    ):
        self.max_search_radius_km = max_search_radius_km
        self.w_prox = w_prox
        self.w_speed = w_speed
        self.w_vessel = w_vessel
        self.w_align = w_align
        self.w_behavioral = w_behavioral
        self.behavioral_engine = BehavioralAnomalyEngine()

    def find_closest_approach(
        self,
        positions: List[TelemetryPoint],
        target_lat: float,
        target_lng: float
    ) -> Tuple[float, TelemetryPoint]:
        """
        Finds the minimum distance (km) and the corresponding telemetry point along a vessel track.
        """
        min_dist = float("inf")
        closest_pt = positions[0]

        for pt in positions:
            dist = haversine_distance_km(pt.lat, pt.lng, target_lat, target_lng)
            if dist < min_dist:
                min_dist = dist
                closest_pt = pt

        return round(min_dist, 3), closest_pt

    def calculate_alignment_score(self, ship_cog: float, slick_orientation_deg: float) -> float:
        """
        Calculates how closely the vessel's Course Over Ground (COG) matches the
        major elongation axis of the oil slick.
        Linear moving discharges align parallel to the ship's heading.
        """
        # Modulo 180 symmetry for line orientation
        ship_angle = ship_cog % 180.0
        slick_angle = slick_orientation_deg % 180.0
        
        diff = abs(ship_angle - slick_angle)
        if diff > 90:
            diff = 180.0 - diff

        # Diff: 0 deg -> 100% score, 90 deg -> 0% score
        score = max(0.0, 100.0 * (1.0 - (diff / 90.0)))
        return round(score, 1)

    def calculate_speed_anomaly_score(self, sog_knots: float, ship_type: str) -> float:
        """
        Illegal discharges (bilge slops or tank washings) often occur at reduced transit
        speeds between 4.0 and 8.5 knots.
        """
        if 4.0 <= sog_knots <= 8.5:
            # Prime speed window for illicit tank washing
            return 95.0
        elif 8.5 < sog_knots <= 12.0:
            return 75.0
        elif 2.0 <= sog_knots < 4.0:
            return 60.0
        elif sog_knots > 14.0:
            # High speed transit: less typical for prolonged bilge discharge, but possible
            return 35.0
        else:
            # Stationary / drifting
            return 25.0

    def correlate_incident(
        self,
        slick: SlickPolygon,
        origin_lat: float,
        origin_lng: float,
        vessel_tracks: List[VesselTrack]
    ) -> List[CulpritMatch]:
        """
        Ranks all vessels in the area of interest against the back-tracked spill origin.
        """
        matches: List[CulpritMatch] = []

        for track in vessel_tracks:
            meta = track.metadata
            positions = track.positions
            if not positions:
                continue

            # 1. Spatial Proximity
            min_dist_km, closest_pt = self.find_closest_approach(positions, origin_lat, origin_lng)

            if min_dist_km > self.max_search_radius_km:
                prox_score = 0.0
            else:
                prox_score = max(0.0, 100.0 * (1.0 - (min_dist_km / self.max_search_radius_km)))

            # 2. Speed Anomaly
            speed_score = self.calculate_speed_anomaly_score(closest_pt.sog, meta.ship_type)

            # 3. Vessel Type Prior Risk
            vessel_score = VESSEL_TYPE_PRIORS.get(meta.ship_type, 30.0)

            # 4. Heading / Track Alignment
            align_score = self.calculate_alignment_score(closest_pt.cog, slick.orientation_deg)

            # 5. Behavioral Anomaly Intelligence Scoring
            beh_profile = self.behavioral_engine.analyze_vessel_track(track)
            behavioral_score = beh_profile.behavioral_risk_score

            # Composite Weighted Score
            composite = (
                self.w_prox * prox_score +
                self.w_speed * speed_score +
                self.w_vessel * vessel_score +
                self.w_align * align_score +
                self.w_behavioral * behavioral_score
            )
            composite = round(min(100.0, max(0.0, composite)), 1)

            # Evidence & Verdict
            evidence_notes = []
            if min_dist_km < 1.0:
                evidence_notes.append(f"Direct Intersect: Closest Point of Approach (CPA) is {min_dist_km*1000:.0f} meters at {closest_pt.timestamp}.")
            else:
                evidence_notes.append(f"Proximity: Passed within {min_dist_km:.2f} km of estimated origin at {closest_pt.timestamp}.")

            if 4.0 <= closest_pt.sog <= 8.5:
                evidence_notes.append(f"Speed Anomaly: SOG of {closest_pt.sog:.1f} knots matches characteristic tank-washing/slop-discharge profile.")
            else:
                evidence_notes.append(f"SOG recorded at {closest_pt.sog:.1f} knots during passage.")

            if meta.ship_type in ["Crude Oil Tanker", "Chemical Tanker", "Bunkering Tanker", "Oil Products Tanker"]:
                evidence_notes.append(f"High-Risk Vessel Category: {meta.ship_type} carrying hazardous hydrocarbon cargo.")

            if align_score >= 80.0:
                evidence_notes.append(f"Trajectory Alignment: Vessel course ({closest_pt.cog:.0f}°) matches slick elongation axis ({slick.orientation_deg:.0f}°) within ±10°.")

            if beh_profile.is_watchlist_target:
                evidence_notes.append(f"🚨 PRE-INCIDENT WATCHLIST MATCH: Pre-flagged with Risk Score {beh_profile.behavioral_risk_score}% prior to satellite detection.")

            for note in beh_profile.summary_notes:
                if note not in evidence_notes:
                    evidence_notes.append(note)

            if composite >= 70.0:
                verdict = "PRIMARY SUSPECT"
            elif composite >= 50.0:
                verdict = "POTENTIAL CONTRIBUTOR"
            else:
                verdict = "CLEARED"

            behavioral_anomalies_str = [a.description for a in beh_profile.anomalies]

            matches.append(CulpritMatch(
                mmsi=meta.mmsi,
                vessel_name=meta.name,
                ship_type=meta.ship_type,
                flag=meta.flag,
                composite_score=composite,
                proximity_score=round(prox_score, 1),
                speed_anomaly_score=round(speed_score, 1),
                vessel_type_score=round(vessel_score, 1),
                alignment_score=round(align_score, 1),
                behavioral_score=round(behavioral_score, 1),
                closest_approach_distance_km=min_dist_km,
                closest_approach_time=closest_pt.timestamp,
                rank=0,
                verdict=verdict,
                evidence_notes=evidence_notes,
                behavioral_anomalies=behavioral_anomalies_str
            ))

        # Sort matches descending by composite score
        matches.sort(key=lambda m: m.composite_score, reverse=True)
        for idx, match in enumerate(matches):
            match.rank = idx + 1

        return matches

