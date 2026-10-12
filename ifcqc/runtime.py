"""Bounded local model sessions and isolated background geometry jobs."""

from __future__ import annotations

from dataclasses import dataclass
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
            if size == 0:
                raise ValueError("The uploaded IFC file is empty.")
            record = ModelRecord(model_id, path, safe_name, size, time())
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


class GeometryJobManager:
    def __init__(
        self,
        timeout_seconds: int = 15 * 60,
        memory_limit_bytes: int = 4 * 1024 * 1024 * 1024,
        cpu_seconds: int = 15 * 60,
    ):
        self.timeout_seconds = timeout_seconds
        self.memory_limit_bytes = memory_limit_bytes
        self.cpu_seconds = cpu_seconds
        self.root = Path(tempfile.mkdtemp(prefix="openbim-qc-jobs-"))
        self._jobs: dict[str, JobRecord] = {}
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
            status_path.write_text(json.dumps({
                "state": "queued",
                "phase": "queued",
                "processed": 0,
                "total": None,
                "percent": 0.0,
                "message": "Geometry validation is queued.",
            }), encoding="utf-8")
            process = self._context.Process(
                target=run_geometry_job,
                args=(
                    str(model.path), browser_evidence, str(status_path), str(result_path),
                    self.memory_limit_bytes, self.cpu_seconds,
                ),
                daemon=True,
            )
            record = JobRecord(
                job_id, model.model_id, process, status_path, result_path,
                monotonic(), self.timeout_seconds,
            )
            self._jobs[job_id] = record
            process.start()
            return job_id

    def status(self, job_id: str) -> dict:
        record = self._get(job_id)
        if record.process.is_alive() and monotonic() - record.started > record.timeout_seconds:
            record.process.terminate()
            record.process.join(timeout=2)
            self._write_status(record, {
                "state": "timed_out",
                "phase": "timed_out",
                "percent": None,
                "message": f"Geometry validation exceeded the {record.timeout_seconds // 60}-minute limit.",
                "error": "Geometry validation timed out before completion.",
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
        if not record.process.is_alive() and payload.get("state") in {"queued", "running"}:
            payload = {
                "state": "failed",
                "phase": "failed",
                "percent": None,
                "message": "The isolated geometry worker stopped unexpectedly.",
                "error": f"Geometry worker exited with code {record.process.exitcode}.",
            }
            self._write_status(record, payload)
        response = {"job_id": job_id, "model_id": record.model_id, **payload}
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
