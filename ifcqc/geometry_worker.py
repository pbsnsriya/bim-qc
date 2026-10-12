"""Isolated geometry-diagnostics worker used by the local API."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import traceback

from .geometry_diagnostics import diagnose_geometry_file


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _set_resource_limits(memory_limit_bytes: int, cpu_seconds: int) -> None:
    """Apply best-effort Unix limits; wall-clock timeout is enforced by the parent."""
    try:
        import resource

        if memory_limit_bytes > 0:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))
        if cpu_seconds > 0:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 5))
    except (ImportError, OSError, ValueError):
        pass


def run_geometry_job(
    model_path: str,
    browser_evidence: dict | None,
    status_path: str,
    result_path: str,
    memory_limit_bytes: int,
    cpu_seconds: int,
) -> None:
    """Run one job and communicate only through bounded JSON files."""
    status = Path(status_path)
    result = Path(result_path)
    _set_resource_limits(memory_limit_bytes, cpu_seconds)

    def progress(update: dict) -> None:
        _atomic_json(status, {"state": "running", **update})

    try:
        progress({
            "phase": "opening",
            "processed": 0,
            "total": None,
            "percent": 0.0,
            "message": "Opening IFC in the isolated geometry worker.",
        })
        diagnostic = diagnose_geometry_file(model_path, browser_evidence, progress)
        _atomic_json(result, diagnostic)
        _atomic_json(status, {
            "state": "completed",
            "phase": "complete",
            "processed": diagnostic["counts"]["represented_products"],
            "total": diagnostic["counts"]["represented_products"],
            "percent": 100.0,
            "message": "Geometry extraction evidence is complete.",
        })
    except MemoryError:
        _atomic_json(status, {
            "state": "failed",
            "phase": "failed",
            "percent": None,
            "message": "Geometry validation exceeded its memory limit.",
            "error": "Geometry validation exceeded its memory limit.",
        })
    except Exception as exc:
        _atomic_json(status, {
            "state": "failed",
            "phase": "failed",
            "percent": None,
            "message": "Geometry validation failed in the isolated worker.",
            "error": str(exc) or exc.__class__.__name__,
            "debug": traceback.format_exc(limit=4),
        })
