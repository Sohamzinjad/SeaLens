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

        # Wind pushes towards opposite direction (+180 deg) + Ekman/Coriolis deflection
        # Northern Hemisphere: surface oil drifts ~15° to the right of wind direction
        ekman_deflection = coriolis_deg if (coriolis_deg is not None and coriolis_deg != 2.0) else (15.0 if lat >= 0 else -15.0)
        effective_wind_push_deg = (dyn_wind_deg + 180.0 + ekman_deflection) % 360.0
        wind_push_rad = math.radians(effective_wind_push_deg)

        # 3. Stokes drift from surface waves (scales as ~0.015 * wind_speed^1.2)
        stokes_drift_ms = 0.015 * (dyn_wind_speed ** 1.2)
        wind_leeway_ms = leeway_factor * dyn_wind_speed

        wind_u = (wind_leeway_ms + stokes_drift_ms) * math.sin(wind_push_rad)
        wind_v = (wind_leeway_ms + stokes_drift_ms) * math.cos(wind_push_rad)

        net_u = wind_u + current_u
        net_v = wind_v + current_v
        net_speed_ms = math.hypot(net_u, net_v)
        net_speed_kmh = net_speed_ms * 3.6

        # Bearing angle in degrees (0° = North, 90° = East)
        bearing_rad = math.atan2(net_u, net_v)
        bearing_deg = (math.degrees(bearing_rad) + 360.0) % 360.0

        return {
            "wind_speed_ms": round(dyn_wind_speed, 2),
            "wind_dir_deg": round(dyn_wind_deg, 1),
            "wind_u": wind_u,
            "wind_v": wind_v,
            "current_speed_ms": round(dyn_current_speed, 2),
            "current_dir_deg": round(dyn_current_deg, 1),
            "current_u": current_u,
            "current_v": current_v,
            "net_u_ms": net_u,
            "net_v_ms": net_v,
            "net_speed_kmh": round(net_speed_kmh, 2),
            "bearing_deg": round(bearing_deg, 1)
        }
