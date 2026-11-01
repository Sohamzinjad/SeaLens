"""Small in-process job queue for slow public-data operations.

This keeps a local demo server responsive while a SAR crop or NOAA archive is
being downloaded.  It is intentionally not a distributed production queue;
the status response says so and deployment should replace it with Celery/RQ or
an equivalent durable worker.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LocalJobManager:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="sealens-data")
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()

    def submit(self, job_type: str, task: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        job_id = uuid4().hex
        record: Dict[str, Any] = {
            "job_id": job_id,
            "job_type": job_type,
            "status": "queued",
            "created_at": _now(),
            "updated_at": _now(),
            "result": None,
            "error": None,
            "execution": "local_in_process",
        }
        with self._lock:
            self._jobs[job_id] = record

        def run() -> None:
            with self._lock:
                record["status"] = "running"
                record["updated_at"] = _now()
            try:
                result = task()
            except Exception as exc:  # Never expose a traceback to the browser.
                with self._lock:
                    record["status"] = "failed"
                    record["error"] = str(exc)
                    record["updated_at"] = _now()
            else:
                with self._lock:
                    record["status"] = "completed"
                    record["result"] = result
                    record["updated_at"] = _now()

        self._executor.submit(run)
        return self.public(job_id)

    def public(self, job_id: str) -> Dict[str, Any]:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            return dict(record)


job_manager = LocalJobManager()
