"""
Forward Drift Simulation, Coastal Landfall ETA & Environmental Risk Predictor.

Projects the future trajectory of detected oil slicks over a 72-hour horizon,
determines intersection with coastline / Marine Protected Areas (MPAs), and computes
Shoreline Landfall Impact ETA and containment boom deployment plans with hydrodynamic
waterbody channeling and strict land avoidance.
"""
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from ml_engine.metrics import haversine_distance_km
from backend.services.ocean_grid_engine import DynamicOceanGridEngine
from backend.services.weathering_engine import OilWeatheringEngine
from backend.services.coastal_water_engine import CoastalWaterRoutingEngine

# Sensitive Coastal Infrastructure & Ecological Zones across All Theaters
COASTAL_TARGETS = [
    # Arabian Sea / Mumbai Region
    {"name": "Manori & Gorai Coastal Wetlands & Marine Sanctuary", "lat": 19.240, "lng": 72.780, "type": "Coastal Mangrove Wetland", "vulnerability": "CRITICAL", "region": "Arabian Sea"},
    {"name": "Vasai Creek Fishery & Mangrove Ecosystem", "lat": 19.330, "lng": 72.810, "type": "Estuarine Fishery", "vulnerability": "CRITICAL", "region": "Arabian Sea"},
    {"name": "Alibag Coastal Reefs & Tourism Beaches", "lat": 18.640, "lng": 72.870, "type": "Tourist Beach & Coral Habitat", "vulnerability": "HIGH", "region": "Arabian Sea"},
    {"name": "JNPT Port International Navigation Channel", "lat": 18.940, "lng": 72.880, "type": "Major Port Channel", "vulnerability": "CRITICAL", "region": "Arabian Sea"},
    {"name": "Elephanta Island UNESCO Protected Marine Sanctuary", "lat": 18.960, "lng": 72.930, "type": "Marine Protected Area", "vulnerability": "CRITICAL", "region": "Arabian Sea"},
    {"name": "Thane Creek Flamingo & Mangrove Sanctuary", "lat": 19.040, "lng": 72.980, "type": "Mangrove Wetland Ecosystem", "vulnerability": "CRITICAL", "region": "Arabian Sea"},
    
    # Singapore Strait
    {"name": "Sisters' Islands Marine Park", "lat": 1.215, "lng": 103.835, "type": "Coral Reef Sanctuary", "vulnerability": "CRITICAL", "region": "Singapore Strait"},
    {"name": "Sentosa Island Recreational Beaches", "lat": 1.250, "lng": 103.820, "type": "Tourism Beach", "vulnerability": "HIGH", "region": "Singapore Strait"},
    {"name": "Pulau Semakau Coral Reefs", "lat": 1.205, "lng": 103.765, "type": "Marine Biosphere", "vulnerability": "CRITICAL", "region": "Singapore Strait"},

    # Gulf of Kutch / Gujarat
    {"name": "Narara Reef Marine National Park & Coral Biosphere", "lat": 22.465, "lng": 69.720, "type": "Coral Reef & Marine National Park", "vulnerability": "CRITICAL", "region": "Gulf of Kutch"},
    {"name": "Pirotan Island Mangrove & Marine Sanctuary", "lat": 22.585, "lng": 69.950, "type": "Marine Sanctuary", "vulnerability": "CRITICAL", "region": "Gulf of Kutch"},
    {"name": "Vadinar Coastal Fishing Grounds & SPM Buffer", "lat": 22.450, "lng": 69.670, "type": "Commercial Fishery & Port Channel", "vulnerability": "HIGH", "region": "Gulf of Kutch"},

    # Gulf of Mannar & Palk Strait (Tamil Nadu)
    {"name": "Gulf of Mannar Marine Biosphere Reserve (Tuticorin Sector)", "lat": 8.820, "lng": 78.220, "type": "UNESCO Biosphere Reserve & Coral Reefs", "vulnerability": "CRITICAL", "region": "Gulf of Mannar"},
    {"name": "Mandapam & Rameshwaram Coastal Fishery Corridor", "lat": 9.270, "lng": 79.150, "type": "Marine Biosphere & Fishery", "vulnerability": "CRITICAL", "region": "Gulf of Mannar"},
    {"name": "Kurusadai Island Coral Reef Ecosystem", "lat": 9.245, "lng": 79.215, "type": "Coral Reef Ecosystem", "vulnerability": "CRITICAL", "region": "Gulf of Mannar"},

    # Bay of Bengal / Chennai
    {"name": "Pulicat Lagoon Estuary & Mangroves", "lat": 13.420, "lng": 80.320, "type": "Estuarine Biosphere", "vulnerability": "CRITICAL", "region": "Bay of Bengal"},
    {"name": "Marina Coastal Biosphere", "lat": 13.040, "lng": 80.280, "type": "Public Coastline", "vulnerability": "HIGH", "region": "Bay of Bengal"},

    # Lakshadweep Archipelago
    {"name": "Kalpeni Atoll Coral Lagoon & Turtle Sanctuary", "lat": 10.080, "lng": 73.640, "type": "Atoll Coral Lagoon", "vulnerability": "CRITICAL", "region": "Lakshadweep"},
    {"name": "Androth Island Coastal Reefs", "lat": 10.820, "lng": 73.680, "type": "Coral Habitat", "vulnerability": "HIGH", "region": "Lakshadweep"},

    # Mauritius Sector
    {"name": "Ile aux Aigrettes Coral & Nature Sanctuary", "lat": -20.420, "lng": 57.730, "type": "Islet Nature Reserve & Coral Habitat", "vulnerability": "CRITICAL", "region": "Mauritius"},
    {"name": "Pointe d'Esny RAMSAR Wetland & Mangroves", "lat": -20.435, "lng": 57.720, "type": "RAMSAR Wetland Ecosystem", "vulnerability": "CRITICAL", "region": "Mauritius"},
    {"name": "Blue Bay Marine Park UNESCO Reserve", "lat": -20.445, "lng": 57.715, "type": "UNESCO Marine Park", "vulnerability": "CRITICAL", "region": "Mauritius"},
]

class CoastalLandfallPredictor:
    def __init__(self):
        self.grid_engine = DynamicOceanGridEngine()
        self.weathering_engine = OilWeatheringEngine()
        self.water_engine = CoastalWaterRoutingEngine()

    def simulate_forward_drift_72h(
        self,
        start_lat: float,
        start_lng: float,
        initial_volume_m3: float,
        base_wind_speed: float,
        base_wind_deg: float,
        base_current_speed: float,
        base_current_deg: float,
        start_time_iso: str = "2026-09-01T06:00:00Z"
    ) -> Dict[str, Any]:
        """
        Runs forward Lagrangian simulation in 1-hour increments up to +72 hours
        routed strictly through marine waterbodies with hydrodynamic land avoidance.
        """
        dt_start = datetime.fromisoformat(start_time_iso.replace("Z", "+00:00"))
        
        trajectory_points = []
        cur_lat, cur_lng = start_lat, start_lng

        landfall_hit = None
        min_shore_dist_km = float("inf")
        closest_target = None
        has_made_landfall = False

        cumulative_shore_deposit = 0.0
        total_deflections = 0

        for h in range(1, 73):
            # Dynamic wind/current vectors at current location and time
            dyn = self.grid_engine.get_interpolated_vectors(
                lat=cur_lat,
                lng=cur_lng,
                hour_offset=float(h),
                base_wind_speed=base_wind_speed,
                base_wind_deg=base_wind_deg,
                base_current_speed=base_current_speed,
                base_current_deg=base_current_deg
            )

            # Net unconstrained velocity in km/h
            net_u_kmh = dyn["net_u_ms"] * 3.6
            net_v_kmh = dyn["net_v_ms"] * 3.6

            # Compute hydrodynamic step routed strictly through waterbodies
            next_lat, next_lng, is_beached, deposit_frac, deflection_cnt = self.water_engine.compute_hydrodynamic_steered_step(
                current_lat=cur_lat,
                current_lng=cur_lng,
                target_u_kmh=net_u_kmh,
                target_v_kmh=net_v_kmh,
                dt_hours=1.0,
                sub_steps=12
            )

            cur_lat = next_lat
            cur_lng = next_lng
            cumulative_shore_deposit += deposit_frac
            total_deflections += deflection_cnt

            pt_time = (dt_start + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Weathering & Fay spreading calculations per hour
            w_state = self.weathering_engine.compute_weathering_state(
                elapsed_hours=h,
                initial_volume_m3=initial_volume_m3,
                wind_speed_ms=dyn["wind_speed_ms"]
            )
            slick_area = w_state["slick_area_sqkm"]
            slick_radius_km = round(math.sqrt(max(0.001, slick_area / math.pi)), 3)

            # Dispersion uncertainty cone radius (widens over time, bounded near shoreline)
            cone_radius_km = round(0.4 + 0.15 * math.sqrt(h), 2)

            trajectory_points.append({
                "hour": h,
                "timestamp": pt_time,
                "lat": round(cur_lat, 6),
                "lng": round(cur_lng, 6),
                "uncertainty_radius_km": cone_radius_km,
                "slick_area_sqkm": slick_area,
                "slick_radius_km": slick_radius_km,
                "bearing_deg": dyn["bearing_deg"],
                "wind_speed_ms": dyn["wind_speed_ms"],
                "current_speed_ms": dyn["current_speed_ms"],
                "is_landfall_point": is_beached,
                "has_deflected": deflection_cnt > 0,
                "shore_deposit_pct": round(min(100.0, cumulative_shore_deposit * 100.0), 1)
            })

            # Check proximity to coastal targets
            for target in COASTAL_TARGETS:
                dist = haversine_distance_km(cur_lat, cur_lng, target["lat"], target["lng"])
                if dist < min_shore_dist_km:
                    min_shore_dist_km = round(dist, 2)
                    closest_target = target

                # If slick reaches beach boundary or gets within 3.5 km of sensitive target
                if (is_beached or dist <= 3.5) and landfall_hit is None:
                    landfall_hit = {
                        "target_name": target["name"],
                        "target_type": target["type"],
                        "vulnerability": target["vulnerability"],
                        "eta_hours": h,
                        "impact_timestamp": pt_time,
                        "impact_lat": round(cur_lat, 6),
                        "impact_lng": round(cur_lng, 6),
                        "distance_km": round(dist, 2)
                    }
                    has_made_landfall = True

        # If no direct hit within 3.5km, calculate closest approach ETA
        if not landfall_hit and closest_target and min_shore_dist_km < 18.0:
            est_hours = round(min_shore_dist_km / 1.2, 1)
            landfall_hit = {
                "target_name": closest_target["name"],
                "target_type": closest_target["type"],
                "vulnerability": closest_target["vulnerability"],
                "eta_hours": est_hours,
                "impact_timestamp": (dt_start + timedelta(hours=est_hours)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "impact_lat": closest_target["lat"],
                "impact_lng": closest_target["lng"],
                "distance_km": min_shore_dist_km,
                "is_closest_approach": True
            }

        # Threat classification
        if landfall_hit:
            threat_level = "CRITICAL_SHORELINE_THREAT" if landfall_hit["eta_hours"] <= 24 else "HIGH_RISK_APPROACH"
        else:
            threat_level = "OFFSHORE_SAFE_CORRIDOR"

        # Containment & Response Recommendations
        containment_plan = {
            "containment_booms_recommended_m": 1200 if initial_volume_m3 > 10 else 600,
            "skimmer_vessels_needed": 2 if initial_volume_m3 > 10 else 1,
            "chemical_dispersant_status": "PROHIBITED (Within 10km Coastal Buffer)" if min_shore_dist_km < 10.0 else "AUTHORIZED FOR DEEP SEA APPLICATION",
            "priority_defense_site": closest_target["name"] if closest_target else "Open Sea Corridor",
            "suggested_barrier_coords": [round(start_lat + 0.02, 4), round(start_lng + 0.02, 4)]
        }

        # 72h Weathering projection
        weathering_curve = self.weathering_engine.generate_72h_weathering_curve(
            initial_volume_m3=initial_volume_m3,
            wind_speed_ms=base_wind_speed
        )

        return {
            "threat_level": threat_level,
            "landfall_impact": landfall_hit,
            "closest_coastal_target": closest_target,
            "min_distance_to_shore_km": min_shore_dist_km,
            "trajectory_72h": trajectory_points,
            "containment_plan": containment_plan,
            "weathering_timeline": weathering_curve
        }
