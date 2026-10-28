"""
Cache manager for Sentinel crops, GFS fields, Copernicus subsets, AIS filters.
"""
import json
import hashlib
from pathlib import Path
from datetime import datetime


CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def get_cache_key(params: dict) -> str:
    """Generate cache key from parameters"""
    key_str = json.dumps(params, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()


def _cache_path(key: str, cache_type: str) -> Path:
    if not isinstance(key, str) or not isinstance(cache_type, str):
        raise ValueError("cache key and cache type must be strings")
    if not all(part.replace("_", "").replace("-", "").isalnum() for part in (key, cache_type)):
        raise ValueError("invalid cache key")
    return CACHE_DIR / f"{cache_type}_{key}.json"


def get_cached(key: str, cache_type: str = "general"):
    """Retrieve from cache if exists and valid"""
    cache_file = _cache_path(key, cache_type)
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
            data["from_cache"] = True
            return data
        except Exception:
            return None
    return None


def save_to_cache(key: str, data: dict, cache_type: str = "general"):
    """Save to cache"""
    cache_file = _cache_path(key, cache_type)
    payload = dict(data)
    payload["cached_at"] = datetime.utcnow().isoformat() + "Z"
    try:
        with open(cache_file, "w") as f:
            json.dump(payload, f, indent=2)
        return True
    except Exception:
        return False
