"""
Hydrodynamic Coastal Boundary & Marine Waterbody Routing Engine.

Prevents Lagrangian drift trajectories from crossing over landmasses, islands, and peninsulas.
Implements realistic coastal hydrodynamic vector steering (boundary layer tangential flow,
no-normal-flow Dirichlet condition on solid boundaries, and seaward hydrodynamic deflection).
"""
import math
from typing import Tuple, Dict, Any, List, Optional
from shapely.geometry import Point, Polygon, MultiPolygon, LineString
from ml_engine.metrics import haversine_distance_km

# ─────────────────────────────────────────────────────────────
# HIGH-RESOLUTION REGIONAL LANDMASS POLYGONS (Coordinates: [lng, lat])
# ─────────────────────────────────────────────────────────────

# 1. Mumbai / Maharashtra Mainland & Peninsulas
MUMBAI_MAINLAND_COORDS = [
    [72.820, 18.500], [72.880, 18.500], [73.500, 18.500], [73.500, 19.600],
    [72.820, 19.600], [72.780, 19.400], [72.785, 19.300], [72.800, 19.200],
    [72.795, 19.120], [72.815, 19.050], [72.810, 18.910], [72.830, 18.900],
    [72.850, 18.940], [72.880, 18.960], [72.930, 18.950], [72.890, 18.750],
    [72.860, 18.650], [72.840, 18.550], [72.820, 18.500]
]

# 2. Singapore Strait & Surrounding Landmasses
# Singapore Mainland
SINGAPORE_MAINLAND_COORDS = [
    [103.600, 1.250], [103.680, 1.230], [103.750, 1.250], [103.850, 1.260],
    [103.980, 1.320], [104.050, 1.380], [104.100, 1.450], [103.950, 1.470],
    [103.750, 1.460], [103.620, 1.400], [103.600, 1.250]
]
# Sentosa & Southern Islands
SENTOSA_ISLAND_COORDS = [
    [103.805, 1.240], [103.840, 1.242], [103.855, 1.255], [103.845, 1.262],
    [103.815, 1.258], [103.805, 1.240]
]
# Batam / Bintan / Belakang Padang (Indonesia - South of Singapore Strait)
INDONESIA_BATAM_COORDS = [
    [103.650, 1.160], [103.780, 1.150], [103.900, 1.140], [104.150, 1.160],
    [104.200, 1.050], [103.600, 1.050], [103.650, 1.160]
]

# 3. Gulf of Kutch Landmasses (Gujarat)
# Saurashtra Mainland (South of Gulf of Kutch)
SAURASHTRA_SOUTH_COORDS = [
    [69.000, 22.440], [69.450, 22.450], [69.650, 22.460], [69.850, 22.490],
    [70.150, 22.580], [70.500, 22.600], [70.500, 22.000], [69.000, 22.000],
    [69.000, 22.440]
]
# Kutch Mainland (North of Gulf of Kutch)
KUTCH_NORTH_COORDS = [
    [69.000, 22.780], [69.500, 22.790], [69.800, 22.820], [70.300, 22.950],
    [70.500, 23.300], [69.000, 23.300], [69.000, 22.780]
]

# 4. Gulf of Mannar & Palk Strait (Tamil Nadu & Sri Lanka)
TAMIL_NADU_COORDS = [
    [78.000, 8.500], [78.160, 8.780], [78.180, 9.000], [78.800, 9.200],
    [79.250, 9.300], [79.250, 9.500], [78.000, 9.500], [78.000, 8.500]
]
SRI_LANKA_NORTH_COORDS = [
    [79.700, 8.800], [80.300, 8.800], [80.300, 9.800], [79.800, 9.800],
    [79.650, 9.200], [79.700, 8.800]
]

# 5. Bay of Bengal (Chennai Coast)
CHENNAI_MAINLAND_COORDS = [
    [80.000, 12.800], [80.260, 12.800], [80.280, 13.050], [80.310, 13.350],
    [80.250, 13.600], [80.000, 13.600], [80.000, 12.800]
]

# 6. Lakshadweep Atoll Islands
KALPENI_ATOLL_COORDS = [
    [73.630, 10.040], [73.660, 10.040], [73.670, 10.120], [73.640, 10.120],
    [73.630, 10.040]
]


class CoastalWaterRoutingEngine:
    def __init__(self):
        # Build Shapely Land Polygons
        self.land_polygons = [
            Polygon(MUMBAI_MAINLAND_COORDS),
            Polygon(SINGAPORE_MAINLAND_COORDS),
            Polygon(SENTOSA_ISLAND_COORDS),
            Polygon(INDONESIA_BATAM_COORDS),
            Polygon(SAURASHTRA_SOUTH_COORDS),
            Polygon(KUTCH_NORTH_COORDS),
            Polygon(TAMIL_NADU_COORDS),
            Polygon(SRI_LANKA_NORTH_COORDS),
            Polygon(CHENNAI_MAINLAND_COORDS),
            Polygon(KALPENI_ATOLL_COORDS)
        ]
        self.multi_land = MultiPolygon(self.land_polygons)

    def is_land(self, lat: float, lng: float) -> bool:
        """Returns True if coordinate is on land / continent / island."""
        pt = Point(lng, lat)
        return self.multi_land.contains(pt)

    def get_distance_to_nearest_land_km(self, lat: float, lng: float) -> Tuple[float, Optional[Tuple[float, float]]]:
        """
        Computes Euclidean/Haversine distance in km from (lat, lng) to the nearest shoreline boundary.
        Returns: (distance_km, (nearest_shore_lat, nearest_shore_lng))
        """
        pt = Point(lng, lat)
        min_dist_deg = float("inf")
        nearest_shore_pt = None

        for poly in self.land_polygons:
            exterior = poly.exterior
            dist = pt.distance(exterior)
            if dist < min_dist_deg:
                min_dist_deg = dist
                nearest_proj = exterior.interpolate(exterior.project(pt))
                nearest_shore_pt = (nearest_proj.y, nearest_proj.x) # (lat, lng)

        # Convert degree distance to approximate km (at lat)
        lat_rad = math.radians(lat)
        km_per_deg_lat = 111.139
        km_per_deg_lng = 111.139 * math.cos(lat_rad)
        mean_km_per_deg = (km_per_deg_lat + km_per_deg_lng) / 2.0
        dist_km = min_dist_deg * mean_km_per_deg

        return dist_km, nearest_shore_pt

    def compute_hydrodynamic_steered_step(
        self,
        current_lat: float,
        current_lng: float,
        target_u_kmh: float,
        target_v_kmh: float,
        dt_hours: float = 1.0,
        sub_steps: int = 6
    ) -> Tuple[float, float, bool]:
        """
        Computes forward step through marine waterbodies with hydrodynamic coastal steering.
        
        Physics:
        1. Decomposes raw velocity into alongshore (tangential) and cross-shore (normal) vectors.
        2. Applies no-normal-flow Dirichlet boundary condition at coastlines (v_normal -> 0).
        3. Channels current flow along natural water corridors/straits.
        4. Sub-steps across dt_hours to prevent jumping across landmasses.
        
        Returns:
            (next_lat, next_lng, is_landfall_reached)
        """
        step_dt = dt_hours / float(sub_steps)
        cur_lat, cur_lng = current_lat, current_lng
        is_beached = False

        for _ in range(sub_steps):
            if is_beached:
                break

            # Distance to nearest shoreline
            dist_km, nearest_shore = self.get_distance_to_nearest_land_km(cur_lat, cur_lng)

            # Raw displacement components for sub-step
            d_east_km = target_u_kmh * step_dt
            d_north_km = target_v_kmh * step_dt

            # If approaching coast (< 2.5 km buffer)
            if dist_km < 2.5 and nearest_shore:
                shore_lat, shore_lng = nearest_shore
                
                # Vector pointing from shore to current water location (seaward normal)
                seaward_d_lat = cur_lat - shore_lat
                seaward_d_lng = cur_lng - shore_lng
                seaward_norm = math.hypot(seaward_d_lat, seaward_d_lng)

                if seaward_norm > 1e-6:
                    n_lat = seaward_d_lat / seaward_norm
                    n_lng = seaward_d_lng / seaward_norm

                    # Alongshore tangent vector (perpendicular to normal)
                    # Rotate 90 deg: (-n_lng, n_lat)
                    t_lat = -n_lng
                    t_lng = n_lat

                    # Project raw displacement onto seaward normal and alongshore tangent
                    raw_dot_n = d_north_km * n_lat + d_east_km * n_lng
                    raw_dot_t = d_north_km * t_lat + d_east_km * t_lng

                    # Align tangent in the forward direction of drift
                    if raw_dot_t < 0:
                        t_lat = -t_lat
                        t_lng = -t_lng
                        raw_dot_t = -raw_dot_t

                    # Hydrodynamic boundary suppression:
                    # Inward onshore velocity (raw_dot_n < 0) is suppressed as distance -> 0
                    proximity_factor = max(0.0, min(1.0, (dist_km - 0.25) / 2.0))
                    
                    if raw_dot_n < 0:
                        steered_dot_n = raw_dot_n * proximity_factor
                    else:
                        steered_dot_n = raw_dot_n

                    # Alongshore current preservation & channeling through waterbody
                    steered_dot_t = raw_dot_t * (1.15 - 0.15 * proximity_factor)

                    # Soft seaward buoyancy pressure to keep trajectory centered in water corridor
                    repulsion_km = 0.04 * (1.0 - proximity_factor)

                    d_north_km = (steered_dot_n + repulsion_km) * n_lat + steered_dot_t * t_lat
                    d_east_km = (steered_dot_n + repulsion_km) * n_lng + steered_dot_t * t_lng

            # Test prospective position
            d_lat = d_north_km / 111.139
            d_lng = d_east_km / (111.139 * math.cos(math.radians(cur_lat)))
            next_lat = cur_lat + d_lat
            next_lng = cur_lng + d_lng

            # Verify prospective point is not inside land
            if self.is_land(next_lat, next_lng):
                # Landfall impact reached! Find exact boundary point
                if nearest_shore:
                    cur_lat = nearest_shore[0]
                    cur_lng = nearest_shore[1]
                is_beached = True
                break
            else:
                cur_lat = next_lat
                cur_lng = next_lng

        return cur_lat, cur_lng, is_beached
