import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
import unittest
from unittest.mock import patch

from ifcqc.geometry_worker import _atomic_json, run_geometry_job
from ifcqc.runtime import GeometryJobManager, JobRecord


class _StoppedProcess:
    exitcode = 0

    def is_alive(self):
        return False

    def join(self, timeout=None):
        return None


class GeometryWorkerTests(unittest.TestCase):
    def test_atomic_json_retries_temporary_windows_permission_error(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / "status.json"
            real_replace = os.replace
            calls = 0

            def flaky_replace(source, destination):
                nonlocal calls
                calls += 1
                if calls < 3:
                    raise PermissionError(5, "Access is denied")
                return real_replace(source, destination)

            with patch("ifcqc.geometry_worker.os.replace", side_effect=flaky_replace):
                _atomic_json(target, {"state": "running"})

            self.assertEqual({"state": "running"}, json.loads(target.read_text()))
            self.assertEqual(3, calls)

    def test_progress_status_failure_does_not_abort_geometry_result(self):
        with TemporaryDirectory() as directory:
            status = Path(directory) / "status.json"
            result = Path(directory) / "result.json"
            real_atomic = _atomic_json

            def selective_write(path, payload, attempts=12):
                if Path(path) == status:
                    raise PermissionError(5, "Access is denied")
                return real_atomic(Path(path), payload, attempts)

            def diagnostic(_model_path, _browser_evidence, progress):
                progress({"processed": 25, "total": 100, "percent": 25.0})
                return {"counts": {"represented_products": 100}, "ready": True}

            with (
                patch("ifcqc.geometry_worker._atomic_json", side_effect=selective_write),
                patch("ifcqc.geometry_worker.diagnose_geometry_file", side_effect=diagnostic),
            ):
                run_geometry_job("model.ifc", None, str(status), str(result), 0, 0)

            self.assertTrue(result.is_file())
            self.assertTrue(json.loads(result.read_text())["ready"])

    def test_parent_recovers_completion_from_result_file(self):
        manager = GeometryJobManager(timeout_seconds=30)
        try:
            job_dir = manager.root / ("a" * 32)
            job_dir.mkdir(parents=True)
            status = job_dir / "status.json"
            result = job_dir / "result.json"
            status.write_text(json.dumps({"state": "running", "phase": "tessellating"}))
            diagnostic = {"counts": {"represented_products": 7}, "ready": True}
            result.write_text(json.dumps(diagnostic))
            job_id = "a" * 32
            manager._jobs[job_id] = JobRecord(
                job_id, "model", _StoppedProcess(), status, result, monotonic(), 30,
            )

            response = manager.status(job_id)

            self.assertEqual("completed", response["state"])
            self.assertEqual(100.0, response["percent"])
            self.assertEqual(diagnostic, response["result"])
        finally:
            manager.close()


if __name__ == "__main__":
    unittest.main()
