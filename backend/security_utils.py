"""
Security utilities for input validation and safe operations.
"""
import os
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException


def validate_bbox(bbox: List[float]) -> List[float]:
    """Validate bounding box [min_lon, min_lat, max_lon, max_lat]"""
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise HTTPException(status_code=400, detail="bbox must be [min_lon, min_lat, max_lon, max_lat]")
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
        raise HTTPException(status_code=400, detail="Longitude must be between -180 and 180")
    if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
        raise HTTPException(status_code=400, detail="Latitude must be between -90 and 90")
    if min_lon >= max_lon or min_lat >= max_lat:
        raise HTTPException(status_code=400, detail="Invalid bbox: min >= max")
    # Limit bbox size to prevent huge downloads
    area = abs((max_lon - min_lon) * (max_lat - min_lat))
    if area > 50:  # degrees squared
        raise HTTPException(status_code=400, detail="BBox too large. Please use a smaller area.")
    return bbox


def validate_date(date_str: str) -> str:
    """Validate ISO date format"""
    pattern = r'^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z?)?$'
    if not re.match(pattern, date_str):
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD or ISO format")
    return date_str


def validate_filename(filename: str) -> str:
    """Prevent path traversal in filenames"""
    if not filename:
        raise HTTPException(status_code=400, detail="Filename required")
    # Check for path traversal attempts
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    # Only allow alphanumeric, dash, underscore, dot
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename characters")
    return filename


def validate_source_url(url: str) -> str:
    """Allow only HTTPS assets hosted by the public sources seaLens supports."""
    parsed = urlparse(url)
    allowed_domains = {
        "sentinel-s1-rtc-indigo.s3.us-west-2.amazonaws.com",
        "earth-search.aws.element84.com",
        "noaaocm.blob.core.windows.net",
    }
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
        raise HTTPException(status_code=400, detail="Source URL must be a plain HTTPS URL")
    if parsed.hostname not in allowed_domains:
        raise HTTPException(status_code=400, detail="Source URL host is not approved for this endpoint")
    return url


def check_download_size_limit(size_mb: float, max_mb: float = 500) -> None:
    """Enforce download size limits"""
    if size_mb > max_mb:
        raise HTTPException(status_code=400, detail=f"Download too large ({size_mb}MB). Limit is {max_mb}MB")


def safe_path_join(base_dir: str, filename: str) -> Path:
    """Safely join paths to prevent traversal"""
    filename = validate_filename(filename)
    base = Path(base_dir).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Path traversal detected")
    return target
