"""
Audit logging for security and reproducibility.
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path


AUDIT_DIR = Path("audit_logs")
AUDIT_DIR.mkdir(exist_ok=True)


def log_audit_event(action: str, metadata: dict):
    """Log audit event with source URL, fetch time, file hash, params"""
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "source_url": metadata.get("source_url"),
        "fetch_time": metadata.get("fetch_time", datetime.utcnow().isoformat() + "Z"),
        "file_hash": metadata.get("file_hash"),
        "parameters": metadata.get("parameters", {}),
        "user_action": metadata.get("user_action", action),
        "ip": metadata.get("ip"),
    }
    
    log_file = AUDIT_DIR / f"audit_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(event) + "\n")
    
    return event


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of file"""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except Exception:
        return None
