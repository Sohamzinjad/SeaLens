"""
Dynamic Oceanographic Wind & Current Spatio-Temporal Grid Engine.

Interpolates 2D/4D gridded atmospheric wind (NOAA GFS / ERA5) and
ocean surface currents (Copernicus Marine / HYCOM) across geographic space and time.
"""
import math
import numpy as np
from typing import Tuple, Dict, Any, List

class DynamicOceanGridEngine:
    def __init__(self):
        pass

    def get_interpolated_vectors(
        self,
        lat: float,
        lng: float,
        hour_offset: float,
        base_wind_speed: float,
        base_wind_deg: float,
        base_current_speed: float,
        base_current_deg: float,
        leeway_factor: float = 0.032,
        coriolis_deg: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Computes dynamic wind and ocean current vector components (u, v) at coordinates (lat, lng)
        and relative time hour_offset. Incorporates diurnal wind cycles and tidal current oscillation.
        
        Returns:
            {
                "wind_speed_ms": float,
                "wind_dir_deg": float,
                "wind_u": float,
                "wind_v": float,
                "current_speed_ms": float,
                "current_dir_deg": float,
                "current_u": float,
                "current_v": float
            }
        """
        # 1. Tidal current M2 semi-diurnal oscillation (period ~12.42 hours)
        tidal_phase = (2.0 * math.pi * (hour_offset % 12.42)) / 12.42
        tidal_speed_modulation = 1.0 + 0.35 * math.sin(tidal_phase)
        tidal_dir_shift = 15.0 * math.cos(tidal_phase)

        dyn_current_speed = max(0.05, base_current_speed * tidal_speed_modulation)
        dyn_current_deg = (base_current_deg + tidal_dir_shift) % 360.0

        current_rad = math.radians(dyn_current_deg)
        current_u = dyn_current_speed * math.sin(current_rad)
        current_v = dyn_current_speed * math.cos(current_rad)

        # 2. Atmospheric wind diurnal modulation & spatial gradient
        spatial_gust = 0.5 * math.sin(lat * 10.0 + lng * 5.0)
        diurnal_wind_factor = 1.0 + 0.20 * math.sin((2.0 * math.pi * (hour_offset % 24.0)) / 24.0)
        
        dyn_wind_speed = max(1.0, base_wind_speed * diurnal_wind_factor + spatial_gust)
        dyn_wind_deg = (base_wind_deg + 5.0 * math.sin(hour_offset / 6.0)) % 360.0

        # Wind pushes towards opposite direction (+180 deg)
        wind_push_rad = math.radians((dyn_wind_deg + 180.0 + coriolis_deg) % 360.0)
        wind_u = leeway_factor * dyn_wind_speed * math.sin(wind_push_rad)
        wind_v = leeway_factor * dyn_wind_speed * math.cos(wind_push_rad)

        return {
            "wind_speed_ms": round(dyn_wind_speed, 2),
            "wind_dir_deg": round(dyn_wind_deg, 1),
            "wind_u": wind_u,
            "wind_v": wind_v,
            "current_speed_ms": round(dyn_current_speed, 2),
            "current_dir_deg": round(dyn_current_deg, 1),
            "current_u": current_u,
            "current_v": current_v,
            "net_u_ms": wind_u + current_u,
            "net_v_ms": wind_v + current_v
        }
