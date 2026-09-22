"""
Lagrangian Ocean Drift & Reverse Backtrack Physics Engine.

Models the transport and dispersion of surface oil slicks under the combined influence
of ocean surface currents and surface atmospheric wind (Leeway model).

Physics Formulation:
  V_slick = V_current + alpha * V_wind
  alpha ≈ 0.030 to 0.035 (3.0% - 3.5% wind leeway factor)
  Deflection angle (Coriolis leeway deflection): ~0-5 degrees to the right in Northern Hemisphere.
"""
import math
from datetime import datetime
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
from ml_engine.metrics import haversine_distance_km
from backend.services.ocean_grid_engine import DynamicOceanGridEngine

class DriftEngine:
    def __init__(self, leeway_factor: float = 0.032, coriolis_deg: float = 2.0):
        self.leeway_factor = leeway_factor
        self.coriolis_deg = coriolis_deg

    def calculate_drift_velocity(
        self,
        wind_speed_ms: float,
        wind_direction_from_deg: float,
        current_speed_ms: float,
        current_direction_to_deg: float
    ) -> Tuple[float, float, float]:
        """
        Computes net drift velocity vector.
        
        Returns:
            (v_east_ms, v_north_ms, net_speed_kmh, net_bearing_deg)
        """
        # Wind pushes in the direction opposite to where it originates
        wind_push_bearing = (wind_direction_from_deg + 180.0 + self.coriolis_deg) % 360.0
        wind_push_rad = math.radians(wind_push_bearing)
        
        wind_u = self.leeway_factor * wind_speed_ms * math.sin(wind_push_rad)
        wind_v = self.leeway_factor * wind_speed_ms * math.cos(wind_push_rad)

        # Current velocity components (towards current_direction_to_deg)
        current_rad = math.radians(current_direction_to_deg)
        current_u = current_speed_ms * math.sin(current_rad)
        current_v = current_speed_ms * math.cos(current_rad)

        # Net velocity vector (m/s)
        net_u = wind_u + current_u
        net_v = wind_v + current_v

        net_speed_ms = math.sqrt(net_u**2 + net_v**2)
        net_speed_kmh = net_speed_ms * 3.6
        
        net_bearing_rad = math.atan2(net_u, net_v)
        net_bearing_deg = (math.degrees(net_bearing_rad) + 360.0) % 360.0

        return (net_u, net_v, net_speed_kmh, net_bearing_deg)

    def backtrack_origin_simple(
        self,
        detect_lat: float,
        detect_lng: float,
        elapsed_hours: float,
        wind_speed_ms: float,
        wind_direction_from_deg: float,
        current_speed_ms: float,
        current_direction_to_deg: float,
        dispersion_sigma_km: float = 0.5
    ) -> Tuple[float, float, Dict[str, Any]]:
        """
        Constant-vector reverse backtrack retained for deterministic examples and tests.
        
        Returns:
            (origin_lat, origin_lng, origin_cone_geojson)
        """
        net_u, net_v, net_speed_kmh, net_bearing = self.calculate_drift_velocity(
            wind_speed_ms, wind_direction_from_deg,
            current_speed_ms, current_direction_to_deg
        )

        # Reverse drift: move in opposite direction
        # 1 degree lat ≈ 111.139 km
        # 1 degree lng ≈ 111.139 * cos(lat) km
        total_drift_km = net_speed_kmh * elapsed_hours
        reverse_bearing_rad = math.radians((net_bearing + 180.0) % 360.0)

        delta_north_km = total_drift_km * math.cos(reverse_bearing_rad)
        delta_east_km = total_drift_km * math.sin(reverse_bearing_rad)

        origin_lat = detect_lat + (delta_north_km / 111.139)
        origin_lng = detect_lng + (delta_east_km / (111.139 * math.cos(math.radians(detect_lat))))

        # Generate expanding uncertainty cone / ellipse
        # Spread increases linearly with time due to turbulent eddy diffusivity
        uncertainty_radius_km = max(0.8, dispersion_sigma_km * math.sqrt(elapsed_hours))
        
        # Generate polygon coordinates for the uncertainty envelope
        cone_coords = []
        for angle_deg in range(0, 360, 20):
            rad = math.radians(angle_deg)
            lat_offset = (uncertainty_radius_km * math.cos(rad)) / 111.139
            lng_offset = (uncertainty_radius_km * math.sin(rad)) / (111.139 * math.cos(math.radians(origin_lat)))
            cone_coords.append([round(origin_lng + lng_offset, 6), round(origin_lat + lat_offset, 6)])
        
        # Close polygon
        cone_coords.append(cone_coords[0])

        origin_cone_geojson = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [cone_coords]
            },
            "properties": {
                "origin_lat": round(origin_lat, 6),
                "origin_lng": round(origin_lng, 6),
                "elapsed_hours": elapsed_hours,
                "uncertainty_radius_km": round(uncertainty_radius_km, 2),
                "drift_speed_knots": round(net_speed_kmh / 1.852, 2)
            }
        }

        return origin_lat, origin_lng, origin_cone_geojson

    def backtrack_origin(
        self,
        detect_lat: float,
        detect_lng: float,
        elapsed_hours: float,
        wind_speed_ms: float,
        wind_direction_from_deg: float,
        current_speed_ms: float,
        current_direction_to_deg: float,
        dispersion_sigma_km: float = 0.5,
        grid_engine: Optional[DynamicOceanGridEngine] = None,
        detection_timestamp: Optional[str] = None,
        step_hours: float = 0.25,
    ) -> Tuple[float, float, Dict[str, Any]]:
        """Backtrack through dynamic wind/current vectors in 15-minute steps.

        The vector field is queried at the particle's changing position and at each
        prior time. ``backtrack_origin_simple`` preserves the former constant-vector
        behaviour for callers that explicitly need it.
        """
        if elapsed_hours < 0:
            raise ValueError("elapsed_hours must be non-negative")
        if step_hours <= 0:
            raise ValueError("step_hours must be positive")

        grid = grid_engine or DynamicOceanGridEngine()
        if detection_timestamp:
            detected_at = datetime.fromisoformat(detection_timestamp.replace("Z", "+00:00"))
            detection_hour = detected_at.timestamp() / 3600.0
        else:
            # The grid is periodic; zero is a deterministic phase when no timestamp is supplied.
            detection_hour = 0.0

        origin_lat, origin_lng = detect_lat, detect_lng
        elapsed = 0.0
        total_drift_km = 0.0
        while elapsed < elapsed_hours:
            dt_hours = min(step_hours, elapsed_hours - elapsed)
            vector = grid.get_interpolated_vectors(
                lat=origin_lat,
                lng=origin_lng,
                hour_offset=detection_hour - elapsed,
                base_wind_speed=wind_speed_ms,
                base_wind_deg=wind_direction_from_deg,
                base_current_speed=current_speed_ms,
                base_current_deg=current_direction_to_deg,
                leeway_factor=self.leeway_factor,
                coriolis_deg=self.coriolis_deg,
            )
            north_km = vector["net_v_ms"] * 3.6 * dt_hours
            east_km = vector["net_u_ms"] * 3.6 * dt_hours
            # Reverse the forward displacement; longitude conversion uses the current latitude.
            origin_lat -= north_km / 111.139
            origin_lng -= east_km / (111.139 * math.cos(math.radians(origin_lat)))
            total_drift_km += math.hypot(north_km, east_km)
            elapsed += dt_hours

        uncertainty_radius_km = max(0.8, dispersion_sigma_km * math.sqrt(elapsed_hours))
        cone_coords = []
        for angle_deg in range(0, 360, 20):
            rad = math.radians(angle_deg)
            lat_offset = (uncertainty_radius_km * math.cos(rad)) / 111.139
            lng_offset = (uncertainty_radius_km * math.sin(rad)) / (111.139 * math.cos(math.radians(origin_lat)))
            cone_coords.append([round(origin_lng + lng_offset, 6), round(origin_lat + lat_offset, 6)])
        cone_coords.append(cone_coords[0])

        return origin_lat, origin_lng, {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [cone_coords]},
            "properties": {
                "origin_lat": round(origin_lat, 6),
                "origin_lng": round(origin_lng, 6),
                "elapsed_hours": elapsed_hours,
                "uncertainty_radius_km": round(uncertainty_radius_km, 2),
                "drift_speed_knots": round((total_drift_km / elapsed_hours) / 1.852, 2) if elapsed_hours else 0.0,
                "model": "dynamic_grid_15_minute_backtrack",
            },
        }

    def generate_drift_trajectory_points(
        self,
        origin_lat: float,
        origin_lng: float,
        elapsed_hours: float,
        steps: int,
        wind_speed_ms: float,
        wind_direction_from_deg: float,
        current_speed_ms: float,
        current_direction_to_deg: float,
        grid_engine: Optional[DynamicOceanGridEngine] = None,
        detection_timestamp: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates map-animation points. With a grid/timestamp, the route uses the
        same dynamic field as the default reverse backtrack; otherwise it retains
        the former constant-vector visualization.
        """
        if grid_engine:
            if detection_timestamp:
                detected_at = datetime.fromisoformat(detection_timestamp.replace("Z", "+00:00"))
                detection_hour = detected_at.timestamp() / 3600.0
            else:
                detection_hour = 0.0
            points = [{"hour_offset": 0.0, "lat": round(origin_lat, 6), "lng": round(origin_lng, 6)}]
            cur_lat, cur_lng = origin_lat, origin_lng
            dt_hours = elapsed_hours / steps
            for step in range(1, steps + 1):
                vector = grid_engine.get_interpolated_vectors(
                    lat=cur_lat,
                    lng=cur_lng,
                    hour_offset=detection_hour - elapsed_hours + (step - 1) * dt_hours,
                    base_wind_speed=wind_speed_ms,
                    base_wind_deg=wind_direction_from_deg,
                    base_current_speed=current_speed_ms,
                    base_current_deg=current_direction_to_deg,
                    leeway_factor=self.leeway_factor,
                    coriolis_deg=self.coriolis_deg,
                )
                cur_lat += vector["net_v_ms"] * 3.6 * dt_hours / 111.139
                cur_lng += vector["net_u_ms"] * 3.6 * dt_hours / (111.139 * math.cos(math.radians(cur_lat)))
                points.append({"hour_offset": round(step * dt_hours, 2), "lat": round(cur_lat, 6), "lng": round(cur_lng, 6)})
            return points

        net_u, net_v, net_speed_kmh, net_bearing = self.calculate_drift_velocity(
            wind_speed_ms, wind_direction_from_deg,
            current_speed_ms, current_direction_to_deg
        )
        
        points = []
        for step in range(steps + 1):
            t = (step / steps) * elapsed_hours
            dist_km = net_speed_kmh * t
            rad = math.radians(net_bearing)
            d_lat = (dist_km * math.cos(rad)) / 111.139
            d_lng = (dist_km * math.sin(rad)) / (111.139 * math.cos(math.radians(origin_lat)))
            
            points.append({
                "hour_offset": round(t, 2),
                "lat": round(origin_lat + d_lat, 6),
                "lng": round(origin_lng + d_lng, 6)
            })
            
        return points
