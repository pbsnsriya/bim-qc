"""Isolated geometry-diagnostics worker used by the local API."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from time import sleep
import traceback

from .geometry_diagnostics import diagnose_geometry_file


def _atomic_json(path: Path, payload: dict, attempts: int = 12) -> None:
    """Write JSON safely, including when Windows briefly locks the target.

    Antivirus, indexing, and a concurrent status poll can hold ``status.json``
    long enough for ``os.replace`` to raise WinError 5. Retrying keeps that
    incidental lock from aborting a multi-minute geometry extraction. A final
    in-place write is acceptable because readers already tolerate transient
    incomplete JSON and retry on the next poll.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload)
    last_error: OSError | None = None
    for attempt in range(max(1, attempts)):
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(content)
                handle.flush()
            os.replace(temporary, path)
            return
        except PermissionError as exc:
            last_error = exc
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        sleep(min(0.01 * (2 ** attempt), 0.25))

    for attempt in range(4):
        try:
            path.write_text(content, encoding="utf-8")
            return
        except PermissionError as exc:
            last_error = exc
            sleep(0.25 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise OSError(f"Could not write JSON status file: {path}")


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

    def safe_status(payload: dict) -> None:
        try:
            _atomic_json(status, payload)
        except OSError:
            # Progress reporting is best-effort. It must never terminate the
            # actual tessellation job; the parent can recover completion from
            # the atomically written result file.
            pass

    def progress(update: dict) -> None:
        safe_status({"state": "running", **update})

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
        safe_status({
            "state": "completed",
            "phase": "complete",
            "processed": diagnostic["counts"]["represented_products"],
            "total": diagnostic["counts"]["represented_products"],
            "percent": 100.0,
            "message": "Geometry extraction evidence is complete.",
        })
    except MemoryError:
        safe_status({
            "state": "failed",
            "phase": "failed",
            "percent": None,
            "message": "Geometry validation exceeded its memory limit.",
            "error": "Geometry validation exceeded its memory limit.",
        })
    except Exception as exc:
        safe_status({
            "state": "failed",
            "phase": "failed",
            "percent": None,
            "message": "Geometry validation failed in the isolated worker.",
            "error": str(exc) or exc.__class__.__name__,
            "debug": traceback.format_exc(limit=4),
        })
