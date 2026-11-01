"""Storage configuration boundary for local demos and a future PostGIS deployment."""
from __future__ import annotations

import os
from typing import Dict


def storage_status() -> Dict[str, str]:
    database_url = os.getenv("DATABASE_URL", "")
    if database_url.startswith(("postgresql://", "postgres://")):
        return {
            "mode": "postgis_configured_not_migrated",
            "detail": "A PostgreSQL URL is configured. Run the supplied schema migration and deploy a PostgreSQL driver before using it for tracks.",
        }
    return {
        "mode": "local_files",
        "detail": "Demo mode uses local files and in-memory scenario data. PostGIS is not configured.",
    }
