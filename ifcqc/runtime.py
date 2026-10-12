"""Bounded local model sessions and isolated background geometry jobs."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import shutil
import tempfile
from threading import Lock
from time import monotonic, time
import uuid

from .geometry_worker import _atomic_json, run_geometry_job


@dataclass
class ModelRecord:
    model_id: str
    path: Path
    filename: str
    size: int
    sha256: str
    created_at: float


class ModelStore:
    def __init__(self, max_file_bytes: int, max_models: int = 3, max_total_bytes: int = 250 * 1024 * 1024):
        self.max_file_bytes = max_file_bytes
        self.max_models = max_models
        self.max_total_bytes = max_total_bytes
        self.root = Path(tempfile.mkdtemp(prefix="openbim-qc-models-"))
        self._records: dict[str, ModelRecord] = {}
        self._lock = Lock()

    def save(self, source, filename: str, protected_ids: set[str] | None = None) -> ModelRecord:
        safe_name = Path(filename).name[:200] or "model.ifc"
        if not safe_name.lower().endswith(".ifc"):
            raise ValueError("Please upload an .ifc file.")
        model_id = uuid.uuid4().hex
        path = self.root / f"{model_id}.ifc"
        size = 0
        digest = sha256()
        try:
            with path.open("wb") as target:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_file_bytes:
                        raise ValueError("The IFC file must not exceed 100 MB.")
                    target.write(chunk)
                    digest.update(chunk)
            if size == 0:
                raise ValueError("The uploaded IFC file is empty.")
            record = ModelRecord(model_id, path, safe_name, size, digest.hexdigest(), time())
            with self._lock:
                self._evict_for(size, protected_ids or set())
                self._records[model_id] = record
            return record
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def _evict_for(self, incoming_size: int, protected_ids: set[str]) -> None:
        ordered = sorted(self._records.values(), key=lambda item: item.created_at)
        current_size = sum(item.size for item in ordered)
        while ordered and (
            len(ordered) >= self.max_models
            or current_size + incoming_size > self.max_total_bytes
        ):
            candidate_index = next(
                (index for index, item in enumerate(ordered) if item.model_id not in protected_ids),
                None,
            )
            if candidate_index is None:
                raise ValueError("Local model capacity is in use by a running geometry job.")
            oldest = ordered.pop(candidate_index)
            current_size -= oldest.size
            self._records.pop(oldest.model_id, None)
            oldest.path.unlink(missing_ok=True)
        if incoming_size > self.max_total_bytes:
            raise ValueError("The model exceeds the local session storage budget.")

    def get(self, model_id: str) -> ModelRecord:
        with self._lock:
            record = self._records.get(model_id)
        if record is None or not record.path.is_file():
            raise ValueError("The model session expired; upload the IFC again.")
        return record

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)


@dataclass
class JobRecord:
    job_id: str
    model_id: str
    process: multiprocessing.Process
    status_path: Path
    result_path: Path
    started: float
    timeout_seconds: int
    no_progress_seconds: int = 5 * 60
    cache_key: str = ""
    cached: bool = False


class _CompletedProcess:
    """Process-shaped sentinel for a result served from the in-memory cache."""

    exitcode = 0

    @staticmethod
    def is_alive() -> bool:
        return False

    @staticmethod
    def join(timeout=None) -> None:
        return None

    @staticmethod
    def terminate() -> None:
        return None


def geometry_timeout_seconds(model_size: int) -> int:
    """Return a bounded wall-clock budget for the supported 100 MiB range."""
    if model_size <= 25 * 1024 * 1024:
        return 15 * 60
    if model_size <= 75 * 1024 * 1024:
        return 30 * 60
    return 45 * 60


def no_progress_timeout_seconds(wall_timeout_seconds: int) -> int:
    """Allow long individual shapes while still detecting a stalled worker."""
    return min(15 * 60, max(5 * 60, wall_timeout_seconds // 3))


class GeometryJobManager:
    def __init__(
        self,
        timeout_seconds: int | None = None,
        memory_limit_bytes: int = 4 * 1024 * 1024 * 1024,
        cpu_seconds: int | None = None,
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.cpu_seconds = cpu_seconds
        self.root = Path(tempfile.mkdtemp(prefix="openbim-qc-jobs-"))
        self._jobs: dict[str, JobRecord] = {}
        self._cache: dict[str, dict] = {}
        self._lock = Lock()
        self._context = multiprocessing.get_context("spawn")

    def start(self, model: ModelRecord, browser_evidence: dict | None) -> str:
        with self._lock:
            for existing in self._jobs.values():
                if existing.process.is_alive():
                    raise ValueError("Another geometry validation is already running. Cancel it or wait for it to finish.")
            job_id = uuid.uuid4().hex
            job_dir = self.root / job_id
            job_dir.mkdir(parents=True)
            status_path = job_dir / "status.json"
            result_path = job_dir / "result.json"
            timeout_seconds = self.timeout_seconds or geometry_timeout_seconds(model.size)
            no_progress_seconds = no_progress_timeout_seconds(timeout_seconds)
            evidence_json = json.dumps(browser_evidence or {}, sort_keys=True, separators=(",", ":"))
            evidence_hash = sha256(evidence_json.encode("utf-8")).hexdigest()
            cache_key = f"{model.sha256}:{evidence_hash}"
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                result_path.write_text(json.dumps(cached_result), encoding="utf-8")
                status_path.write_text(json.dumps({
                    "state": "completed",
                    "phase": "complete",
                    "processed": cached_result["counts"]["represented_products"],
                    "total": cached_result["counts"]["represented_products"],
                    "percent": 100.0,
                    "message": "Reused cached Stage 1 evidence for this exact IFC and browser geometry.",
                }), encoding="utf-8")
                self._jobs[job_id] = JobRecord(
                    job_id, model.model_id, _CompletedProcess(), status_path, result_path,
                    monotonic(), timeout_seconds, no_progress_seconds, cache_key, True,
                )
                return job_id
            status_path.write_text(json.dumps({
                "state": "queued",
                "phase": "queued",
                "processed": 0,
                "total": None,
                "percent": 0.0,
                "message": f"Geometry validation is queued with a {timeout_seconds // 60}-minute limit.",
            }), encoding="utf-8")
            cpu_seconds = self.cpu_seconds or timeout_seconds
            process = self._context.Process(
                target=run_geometry_job,
                args=(
                    str(model.path), browser_evidence, str(status_path), str(result_path),
                    self.memory_limit_bytes, cpu_seconds,
                ),
                daemon=True,
            )
            record = JobRecord(
                job_id, model.model_id, process, status_path, result_path,
                monotonic(), timeout_seconds, no_progress_seconds, cache_key, False,
            )
            self._jobs[job_id] = record
            process.start()
            return job_id

    def status(self, job_id: str) -> dict:
        record = self._get(job_id)
        elapsed = monotonic() - record.started
        if record.process.is_alive() and not record.result_path.is_file():
            try:
                status_age = max(0.0, time() - record.status_path.stat().st_mtime)
            except OSError:
                status_age = elapsed
            if elapsed > record.timeout_seconds:
                record.process.terminate()
                record.process.join(timeout=2)
                self._write_status(record, {
                    "state": "timed_out",
                    "phase": "timed_out",
                    "percent": None,
                    "message": f"Geometry validation exceeded its size-aware {record.timeout_seconds // 60}-minute limit.",
                    "error": "Stage 1 is inconclusive because the worker timed out before completion.",
                })
            elif status_age > record.no_progress_seconds:
                record.process.terminate()
                record.process.join(timeout=2)
                self._write_status(record, {
                    "state": "timed_out",
                    "phase": "stalled",
                    "percent": None,
                    "message": f"Geometry validation made no reported progress for {record.no_progress_seconds // 60} minutes.",
                    "error": "Stage 1 is inconclusive because the geometry worker appeared stalled.",
                })
        payload = self._read_status(record)
        if not record.process.is_alive():
            record.process.join(timeout=0)
        if not record.process.is_alive() and record.result_path.is_file():
            try:
                diagnostic = json.loads(record.result_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                diagnostic = None
            if diagnostic is not None and payload.get("state") != "completed":
                total = diagnostic["counts"]["represented_products"]
                payload = {
                    "state": "completed",
                    "phase": "complete",
                    "processed": total,
                    "total": total,
                    "percent": 100.0,
                    "message": "Geometry extraction evidence is complete.",
                }
                self._write_status(record, payload)
            if diagnostic is not None and record.cache_key:
                self._cache[record.cache_key] = diagnostic
        if not record.process.is_alive() and payload.get("state") in {"queued", "running"}:
            payload = {
                "state": "failed",
                "phase": "failed",
                "percent": None,
                "message": "The isolated geometry worker stopped unexpectedly.",
                "error": f"Geometry worker exited with code {record.process.exitcode}.",
            }
            self._write_status(record, payload)
        response = {
            "job_id": job_id,
            "model_id": record.model_id,
            "elapsed_seconds": round(elapsed, 1),
            "timeout_seconds": record.timeout_seconds,
            "no_progress_seconds": record.no_progress_seconds,
            "cached": record.cached,
            **payload,
        }
        if payload.get("state") == "completed" and record.result_path.is_file():
            response["result"] = json.loads(record.result_path.read_text(encoding="utf-8"))
        return response

    def active_model_ids(self) -> set[str]:
        with self._lock:
            return {
                record.model_id for record in self._jobs.values()
                if record.process.is_alive()
            }

    def cancel(self, job_id: str) -> dict:
        record = self._get(job_id)
        if record.process.is_alive():
            record.process.terminate()
            record.process.join(timeout=2)
            payload = {
                "state": "cancelled",
                "phase": "cancelled",
                "percent": None,
                "message": "Geometry validation was cancelled.",
            }
            self._write_status(record, payload)
        return self.status(job_id)

    def _get(self, job_id: str) -> JobRecord:
        with self._lock:
            record = self._jobs.get(job_id)
        if record is None:
            raise ValueError("Unknown or expired geometry job.")
        return record

    @staticmethod
    def _read_status(record: JobRecord) -> dict:
        try:
            return json.loads(record.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"state": "running", "phase": "starting", "percent": 0.0, "message": "Starting geometry worker."}

    @staticmethod
    def _write_status(record: JobRecord, payload: dict) -> None:
        _atomic_json(record.status_path, payload)

    def close(self) -> None:
        for record in self._jobs.values():
            if record.process.is_alive():
                record.process.terminate()
        shutil.rmtree(self.root, ignore_errors=True)
