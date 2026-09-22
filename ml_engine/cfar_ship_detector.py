"""
2D Cell-Averaging Constant False Alarm Rate (CA-CFAR) Radar Ship Detector.

Detects bright specular metallic point scatterers (ship hulls) in SAR radar imagery
against heterogeneous ocean sea clutter.
"""
import cv2
import numpy as np
try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    rasterio = None
from typing import List, Dict, Any, Tuple
from ml_engine.metrics import haversine_distance_km

class CACFARShipDetector:
    def __init__(
        self,
        guard_cells: int = 8,
        training_cells: int = 16,
        cfar_multiplier: float = 3.0,
        min_vessel_area_px: int = 1,
        max_vessel_area_px: int = 800
    ):
        self.guard_cells = guard_cells
        self.training_cells = training_cells
        self.cfar_multiplier = cfar_multiplier
        self.min_vessel_area_px = min_vessel_area_px
        self.max_vessel_area_px = max_vessel_area_px

    def detect_ships(
        self,
        raster: np.ndarray,
        transform: Any,
        pixel_size_m: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        Runs 2D CA-CFAR detector across the SAR raster.
        
        Returns:
            List of detected ships with pixel coordinates, geographic lat/lng, and estimated hull length.
        """
        H, W = raster.shape
        outer_k = 2 * (self.guard_cells + self.training_cells) + 1
        inner_k = 2 * self.guard_cells + 1

        outer_mean = cv2.blur(raster, (outer_k, outer_k))
        inner_mean = cv2.blur(raster, (inner_k, inner_k))

        outer_area = outer_k * outer_k
        inner_area = inner_k * inner_k
        train_area = outer_area - inner_area

        # Clutter background mean
        clutter_mean = (outer_mean * outer_area - inner_mean * inner_area) / train_area

        # Clutter variance
        outer_sq = cv2.blur(raster ** 2, (outer_k, outer_k))
        inner_sq = cv2.blur(raster ** 2, (inner_k, inner_k))
        clutter_var = np.maximum(0.0, (outer_sq * outer_area - inner_sq * inner_area) / train_area - (clutter_mean ** 2))
        clutter_std = np.sqrt(clutter_var)

        # Dynamic CFAR Threshold
        cfar_thresh = clutter_mean + self.cfar_multiplier * clutter_std
        detection_mask = ((raster > cfar_thresh) & (raster > 0.65)).astype(np.uint8)

        # Morphological grouping to cluster ship pixels
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        detection_mask = cv2.morphologyEx(detection_mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(detection_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        detected_vessels = []
        for idx, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            # Centroid
            M = cv2.moments(cnt)
            if M["m00"] > 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
            else:
                cx = int(cnt[0][0][0])
                cy = int(cnt[0][0][1])

            # Rotated bounding box for ship orientation and length
            rect = cv2.minAreaRect(cnt)
            (rx, ry), (width_px, height_px), angle_deg = rect
            length_px = max(1.0, max(width_px, height_px))
            beam_px = max(1.0, min(width_px, height_px))
            est_length_m = round(max(30.0, length_px * pixel_size_m), 1)
            est_beam_m = round(max(8.0, beam_px * pixel_size_m), 1)

            # Georeference to WGS84 (Lat, Lng)
            if HAS_RASTERIO and transform is not None:
                lng, lat = rasterio.transform.xy(transform, cy, cx, offset='center')
            else:
                lng = 72.35 + (cx / max(1, W)) * 0.20
                lat = 18.75 + (cy / max(1, H)) * 0.20

            # Backscatter intensity at vessel peak
            peak_intensity = float(np.max(raster[max(0, cy-2):min(H, cy+3), max(0, cx-2):min(W, cx+3)]))
            clutter_val = max(0.01, float(clutter_mean[cy, cx]))

            detected_vessels.append({
                "id": f"RADAR-SHIP-{idx+1:02d}",
                "px": cx,
                "py": cy,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "estimated_length_m": est_length_m,
                "estimated_beam_m": est_beam_m,
                "radar_intensity": round(peak_intensity, 3),
                "cfar_snr_db": round(10.0 * np.log10(peak_intensity / clutter_val), 1)
            })

        return detected_vessels
