"""
GeoTIFF Satellite Imagery Processor & Radar Speckle Filter.

Provides raster ingestion via Rasterio, Lee speckle noise suppression,
and georeferenced pixel-to-geographic EPSG:4326 polygon vectorization.
"""
import os
import cv2
try:
    import rasterio
    from rasterio.transform import from_bounds
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    rasterio = None
    from_bounds = None
import numpy as np
from typing import Tuple, List, Dict, Any, Optional

class GeoTIFFProcessor:
    def __init__(self, default_crs: str = "EPSG:4326"):
        self.default_crs = default_crs

    def read_geotiff(self, filepath: str, normalize: bool = True) -> Tuple[np.ndarray, Any, List[List[float]], Dict[str, Any]]:
        """
        Reads a GeoTIFF raster file.
        
        Returns:
            (raster_array: np.ndarray, transform: Affine, bounds: [[min_lat, min_lng], [max_lat, max_lng]], meta: dict)
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"GeoTIFF file not found: {filepath}")

        if HAS_RASTERIO:
            with rasterio.open(filepath) as src:
                raster = src.read(1).astype(np.float32)
                transform = src.transform
                bounds_obj = src.bounds
                meta = src.meta.copy()

            bounds = [
                [round(bounds_obj.bottom, 6), round(bounds_obj.left, 6)],
                [round(bounds_obj.top, 6), round(bounds_obj.right, 6)]
            ]
        else:
            raster = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
            if raster is None:
                raise ValueError(f"Unable to read image at {filepath}")
            raster = raster.astype(np.float32)
            transform = None
            bounds = [[18.70, 72.25], [19.00, 72.55]]
            meta = {"driver": "GTiff", "height": raster.shape[0], "width": raster.shape[1]}

        # Percentile normalization is useful for U-Net inference, but it expands
        # ordinary sea-clutter variation and is unsuitable for CFAR statistics.
        if normalize:
            p2, p98 = np.percentile(raster, (2, 98))
            normalized = np.clip((raster - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)
        else:
            scale = 65535.0 if float(np.max(raster)) > 1.0 else 1.0
            normalized = np.clip(raster / scale, 0.0, 1.0)

        return normalized, transform, bounds, meta

    def apply_lee_speckle_filter(self, img: np.ndarray, window_size: int = 5) -> np.ndarray:
        """
        Applies the standard Lee speckle reduction filter on SAR radar backscatter.
        Suppresses multiplicative granular noise while preserving edges.
        """
        img_f = img.astype(np.float32)
        mean = cv2.blur(img_f, (window_size, window_size))
        mean_sq = cv2.blur(img_f ** 2, (window_size, window_size))
        variance = np.maximum(0.0, mean_sq - (mean ** 2))

        # Overall scene noise variance
        noise_variance = np.mean(variance) * 0.5
        
        # Adaptive Lee weight
        weights = variance / (variance + noise_variance + 1e-7)
        weights = np.clip(weights, 0.0, 1.0)

        filtered = mean + weights * (img_f - mean)
        return np.clip(filtered, 0.0, 1.0)

    def mask_to_geojson_polygons(
        self,
        binary_mask: np.ndarray,
        transform: Any,
        min_area_pixels: int = 50
    ) -> List[List[List[float]]]:
        """
        Converts binary segmentation mask into georeferenced GeoJSON polygon coordinate rings.
        Output coords format: [[lng, lat], [lng, lat], ...] (GeoJSON standard)
        """
        contours, _ = cv2.findContours(
            binary_mask.astype(np.uint8),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        polygons = []
        for cnt in contours:
            if cv2.contourArea(cnt) < min_area_pixels:
                continue

            # Simplify contour to reduce vertex count
            epsilon = 0.005 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)

            geo_coords = []
            for pt in approx:
                px, py = pt[0][0], pt[0][1]
                if HAS_RASTERIO and transform is not None:
                    lng, lat = rasterio.transform.xy(transform, py, px, offset='center')
                else:
                    # Fallback linear geographic scaling
                    lng = round(72.25 + (px / binary_mask.shape[1]) * 0.30, 6)
                    lat = round(18.70 + ((binary_mask.shape[0] - py) / binary_mask.shape[0]) * 0.30, 6)
                geo_coords.append([round(lng, 6), round(lat, 6)])

            if len(geo_coords) >= 3:
                # Ensure closed ring
                if geo_coords[0] != geo_coords[-1]:
                    geo_coords.append(geo_coords[0])
                polygons.append(geo_coords)

        return polygons

    def generate_synthetic_geotiff(
        self,
        output_path: str,
        center_lat: float = 18.85,
        center_lng: float = 72.40,
        span_deg: float = 0.30,
        resolution_px: int = 512,
        vessel_signatures: Optional[List[Dict[str, Any]]] = None,
        calm_clutter: bool = False,
    ) -> str:
        """
        Generates a valid, georeferenced 16-bit GeoTIFF with synthetic radar backscatter
        and a simulated oil slick for offline testing.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        west = center_lng - span_deg / 2.0
        east = center_lng + span_deg / 2.0
        south = center_lat - span_deg / 2.0
        north = center_lat + span_deg / 2.0

        transform = from_bounds(west, south, east, north, resolution_px, resolution_px) if HAS_RASTERIO else None

        if calm_clutter:
            # Scenario rasters use homogeneous open-water clutter, allowing the
            # detector to distinguish embedded metallic echoes reproducibly.
            rng = np.random.default_rng(42)
            clutter = rng.normal(0.45, 0.025, (resolution_px, resolution_px)).astype(np.float32)
            clutter = np.clip(clutter, 0.30, 0.60)
        else:
            shape_k = 4.0
            scale_theta = 0.15
            clutter = np.random.gamma(shape_k, scale_theta, (resolution_px, resolution_px)).astype(np.float32)
            clutter = np.clip(clutter / 1.5, 0.2, 0.9)

        y, x = np.ogrid[:resolution_px, :resolution_px]
        cx, cy = resolution_px // 2 + 30, resolution_px // 2 - 20
        angle = np.radians(45.0)
        cos_a, sin_a = np.cos(angle), np.sin(angle)
        dx = (x - cx) * cos_a + (y - cy) * sin_a
        dy = -(x - cx) * sin_a + (y - cy) * cos_a
        slick_mask = (dx**2 / (80**2) + dy**2 / (25**2)) <= 1.0
        clutter[slick_mask] = clutter[slick_mask] * 0.25

        # Embed bright, elongated point scatterers at known geographic locations.
        # These are pixel features; CA-CFAR must rediscover them from the raster.
        for signature in vessel_signatures or []:
            lat, lng = signature["lat"], signature["lng"]
            if not (south <= lat <= north and west <= lng <= east):
                continue
            if HAS_RASTERIO:
                row, col = rasterio.transform.rowcol(transform, lng, lat)
            else:
                col = int((lng - west) / span_deg * resolution_px)
                row = int((north - lat) / span_deg * resolution_px)
            half_length = max(3, int(signature.get("length_px", 7) / 2))
            half_beam = max(1, int(signature.get("beam_px", 3) / 2))
            yy, xx = np.ogrid[:resolution_px, :resolution_px]
            ship_mask = ((xx - col) / half_length) ** 2 + ((yy - row) / half_beam) ** 2 <= 1.0
            clutter[ship_mask] = float(signature.get("intensity", 0.99))

        raw_16bit = (np.clip(clutter, 0.0, 1.0) * 65535.0).astype(np.uint16)

        if HAS_RASTERIO:
            with rasterio.open(
                output_path,
                'w',
                driver='GTiff',
                height=resolution_px,
                width=resolution_px,
                count=1,
                dtype=rasterio.uint16,
                crs='EPSG:4326',
                transform=transform,
            ) as dst:
                dst.write(raw_16bit, 1)
        else:
            cv2.imwrite(output_path, raw_16bit)

        print(f"✅ Generated georeferenced GeoTIFF at: {output_path}")
        return output_path
