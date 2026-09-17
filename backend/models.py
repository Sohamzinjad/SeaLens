"""
Data models and schemas for Oil Spill Detection and AIS Vessel Correlation.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class GeoPoint(BaseModel):
    lat: float
    lng: float

class VesselMetadata(BaseModel):
    mmsi: int
    imo: Optional[int] = None
    name: str
    callsign: Optional[str] = None
    ship_type: str  # e.g., "Crude Oil Tanker", "Chemical Tanker", "Container Ship", "Fishing Vessel"
    flag: str
    length_m: float
    beam_m: float
    gross_tonnage: int
    risk_weight: float = 1.0  # Base risk multiplier

class TelemetryPoint(BaseModel):
    timestamp: str  # ISO 8601
    lat: float
    lng: float
    sog: float  # Speed Over Ground (knots)
    cog: float  # Course Over Ground (degrees)
    heading: Optional[float] = None
    nav_status: str  # e.g. "Under way using engine", "Moored", "Restricted maneuverability"
    draught_m: Optional[float] = None

class VesselTrack(BaseModel):
    metadata: VesselMetadata
    positions: List[TelemetryPoint]

class SlickPolygon(BaseModel):
    id: str
    geojson: Dict[str, Any]  # GeoJSON Polygon / MultiPolygon
    centroid: GeoPoint
    area_sqkm: float
    perimeter_km: float
    length_major_axis_km: float
    orientation_deg: float
    confidence_score: float  # 0.0 - 1.0
    is_lookalike: bool = False
    lookalike_reason: Optional[str] = None
    estimated_volume_m3: float

class EnvironmentalCondition(BaseModel):
    wind_speed_ms: float
    wind_direction_deg: float  # Direction wind is coming FROM
    current_speed_ms: float
    current_direction_deg: float  # Direction current is flowing TO
    sea_state: int  # Beaufort scale 0-12
    surface_temp_c: float

class SARImageMetadata(BaseModel):
    scene_id: str
    satellite: str  # e.g., "Sentinel-1A C-Band SAR"
    mode: str  # "IW (Interferometric Wide)"
    polarization: str  # "VV + VH"
    acquisition_time: str
    bounds: List[List[float]]  # [[min_lat, min_lng], [max_lat, max_lng]]
    resolution_m: float = 10.0
    image_url: Optional[str] = None

class BehavioralAnomaly(BaseModel):
    anomaly_type: str  # "AIS_GAP", "SPEED_DROP", "COURSE_INSTABILITY", "LOITERING", "NIGHTTIME_OP"
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    description: str
    timestamp: str
    duration_mins: Optional[float] = None

class BehavioralProfile(BaseModel):
    mmsi: int
    vessel_name: str
    behavioral_risk_score: float  # 0.0 - 100.0%
    risk_level: str  # "CRITICAL_WATCHLIST", "ELEVATED_RISK", "NOMINAL"
    is_watchlist_target: bool = False
    anomalies: List[BehavioralAnomaly] = []
    summary_notes: List[str] = []

class HistoricalIncident(BaseModel):
    incident_id: str
    timestamp: str
    location_name: str
    region: str
    lat: float
    lng: float
    estimated_volume_m3: float
    spill_type: str
    enforcement_action: str
    evidence_source: str

class RepeatOffenderProfile(BaseModel):
    mmsi: int
    vessel_name: str
    ship_type: str
    flag: str
    total_incidents_logged: int
    serial_offender_level: str  # "SERIAL OFFENDER (LEVEL 3 - CRITICAL)", "RECURRING SUSPECT (LEVEL 2)", "FIRST-TIME INCIDENT (LEVEL 1)", "CLEARED"
    is_serial_offender: bool = False
    prosecution_priority: str  # "PRIORITY 1 - IMMEDIATE PORT STATE ARREST", "PRIORITY 2 - FLAG STATE NOTIFICATION", "MONITORING"
    historical_incidents: List[HistoricalIncident] = []
    active_scenario_matches: List[str] = []
    recommended_interception_protocol: str


class CulpritMatch(BaseModel):
    mmsi: int
    vessel_name: str
    ship_type: str
    flag: str
    composite_score: float  # 0 - 100%
    proximity_score: float  # 0 - 100%
    speed_anomaly_score: float  # 0 - 100%
    vessel_type_score: float  # 0 - 100%
    alignment_score: float  # 0 - 100%
    behavioral_score: float = 0.0  # 0 - 100%
    closest_approach_distance_km: float
    closest_approach_time: str
    rank: int
    verdict: str  # "PRIMARY SUSPECT", "POTENTIAL CONTRIBUTOR", "CLEARED"
    evidence_notes: List[str]
    behavioral_anomalies: List[str] = []

class ScenarioData(BaseModel):
    id: str
    title: str
    description: str
    region_name: str
    sar_image: SARImageMetadata
    environmental: EnvironmentalCondition
    slicks: List[SlickPolygon]
    vessels: List[VesselTrack]
    drift_origin_cone: Dict[str, Any]  # GeoJSON Polygon representing probable back-tracked source
    culprits: List[CulpritMatch]

