import json
from io import BytesIO
from pathlib import Path
from threading import Thread
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from zipfile import ZipFile

from http.server import ThreadingHTTPServer
from server import Handler, MAX_BODY_BYTES, MAX_IFC_BYTES


ROOT = Path(__file__).resolve().parents[1]


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health(self):
        with urlopen(f"{self.base}/api/health") as response:
            self.assertEqual({"status": "ok"}, json.load(response))

    def test_capacity_allows_100_mb_ifc_with_json_overhead(self):
        self.assertEqual(100 * 1024 * 1024, MAX_IFC_BYTES)
        self.assertGreater(MAX_BODY_BYTES, MAX_IFC_BYTES)

    def upload_model(self, fixture="geometry_demo.ifc", profile="coordination"):
        content = (ROOT / "samples" / fixture).read_bytes()
        boundary = "----OpenBIMQCTestBoundary"
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"profile\"\r\n\r\n"
            f"{profile}\r\n--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"file\"; filename=\"{fixture}\"\r\n"
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--\r\n".encode()
        request = Request(
            f"{self.base}/api/models",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urlopen(request) as response:
            self.assertEqual(201, response.status)
            return json.load(response)

    def test_multipart_model_session_and_reanalysis(self):
        uploaded = self.upload_model()
        self.assertEqual("geometry_demo.ifc", uploaded["analysis"]["filename"])
        self.assertGreater(uploaded["size_bytes"], 0)
        request = Request(
            f"{self.base}/api/models/{uploaded['model_id']}/analyze",
            data=json.dumps({"profile": "handover"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertEqual("handover", result["profile"])

    def test_background_geometry_job_reports_progress_and_completes(self):
        uploaded = self.upload_model()
        backend = __import__("ifcqc.geometry_diagnostics", fromlist=["diagnose_geometry"])
        evidence = backend.diagnose_geometry((ROOT / "samples/geometry_demo.ifc").read_text())
        request = Request(
            f"{self.base}/api/geometry-jobs",
            data=json.dumps({
                "model_id": uploaded["model_id"],
                "browser_evidence": {
                    "element_ids": [int(key) for key in evidence["element_extents_metres"]],
                    "element_extents_metres": evidence["element_extents_metres"],
                },
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            started = json.load(response)
        states = []
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            with urlopen(f"{self.base}/api/geometry-jobs/{started['job_id']}") as response:
                status = json.load(response)
            states.append(status["state"])
            if status["state"] in {"completed", "failed", "cancelled", "timed_out"}:
                break
            time.sleep(0.1)
        self.assertEqual("completed", status["state"], status)
        self.assertTrue(status["result"]["ready"])
        self.assertEqual(100.0, status["percent"])
        self.assertTrue({"queued", "running"} & set(states))

    def test_background_geometry_job_can_be_cancelled(self):
        uploaded = self.upload_model()
        request = Request(
            f"{self.base}/api/geometry-jobs",
            data=json.dumps({"model_id": uploaded["model_id"]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            started = json.load(response)
        cancel = Request(
            f"{self.base}/api/geometry-jobs/{started['job_id']}/cancel",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(cancel) as response:
            status = json.load(response)
        self.assertEqual("cancelled", status["state"])

    def test_capabilities_are_explicit(self):
        with urlopen(f"{self.base}/api/capabilities") as response:
            result = json.load(response)
        self.assertEqual("builtin-subset", result["ids_backend"])
        self.assertIn("ifcopenshell_available", result)

    def test_demo_file_is_ifc_geometry_fixture(self):
        with urlopen(f"{self.base}/api/demo-file") as response:
            content = response.read().decode()
        self.assertIn("IFCWALL", content)
        self.assertIn("IFCEXTRUDEDAREASOLID", content)

    def test_wasm_has_correct_content_type(self):
        with urlopen(f"{self.base}/vendor/web-ifc/web-ifc.wasm") as response:
            self.assertEqual("application/wasm", response.headers.get_content_type())
            self.assertGreater(int(response.headers["Content-Length"]), 1_000_000)
            self.assertGreater(len(response.read()), 1_000_000)

    def test_viewer_uses_absolute_wasm_location(self):
        source = (ROOT / "web/viewer.js").read_text()
        self.assertIn('api.SetWasmPath(wasmBase, true)', source)

    def test_viewer_modules_are_directly_available(self):
        for path in (
            "/viewer.js",
            "/vendor/three/three.module.js",
            "/vendor/three/three.core.js",
            "/vendor/three/examples/jsm/controls/OrbitControls.js",
            "/vendor/web-ifc/web-ifc-api.js",
        ):
            with self.subTest(path=path), urlopen(f"{self.base}{path}") as response:
                self.assertEqual(200, response.status)
                self.assertEqual("text/javascript", response.headers.get_content_type())
                self.assertEqual("no-store", response.headers["Cache-Control"])
                response.read()

    def test_viewer_avoids_bare_module_specifiers(self):
        controls = (ROOT / "web/vendor/three/examples/jsm/controls/OrbitControls.js").read_text()
        self.assertNotIn("from 'three'", controls)

    def test_viewer_exposes_issue_selection_bridge(self):
        source = (ROOT / "web/viewer.js").read_text()
        self.assertIn("selectExpressID", source)
        self.assertIn("selectExpressIDs", source)
        self.assertIn("ifc-element-selected", source)
        self.assertIn("clearSelection", source)
        self.assertIn("setSelectionMode", source)
        self.assertIn("material.depthTest = false", source)
        self.assertIn("new THREE.Box3Helper", source)
        self.assertIn("raycaster.intersectObjects", source)
        self.assertIn("runGpuValidation", source)
        self.assertIn("WEBGL_debug_renderer_info", source)
        self.assertIn("webglcontextlost", source)

    def test_analyze_with_handover_profile(self):
        content = (ROOT / "samples/qc_demo.ifc").read_text()
        request = Request(
            f"{self.base}/api/analyze",
            data=json.dumps({"filename": "qc.ifc", "content": content, "profile": "handover"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertEqual("handover", result["profile"])
        self.assertNotIn("duplicate_global_id", {issue["rule_id"] for issue in result["issues"]})

    def test_reject_unknown_profile(self):
        content = (ROOT / "samples/clean_demo.ifc").read_text()
        request = Request(
            f"{self.base}/api/analyze",
            data=json.dumps({"content": content, "profile": "unknown"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as context:
            urlopen(request)
        self.assertEqual(400, context.exception.code)

    def test_validate_sample_ids(self):
        request = Request(
            f"{self.base}/api/validate-ids",
            data=json.dumps({
                "content": (ROOT / "samples/geometry_demo.ifc").read_text(),
                "ids_content": (ROOT / "samples/wall-naming.ids").read_text(),
                "ids_filename": "wall-naming.ids",
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertEqual(1, result["summary"]["failed"])
        self.assertEqual(73, result["issues"][0]["entity_id"])

    def test_run_geometry_checks(self):
        request = Request(
            f"{self.base}/api/geometry-checks",
            data=json.dumps({
                "content": (ROOT / "samples/geometry_demo.ifc").read_text(),
                "config": {"clearance_mm": 50},
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertEqual("ifcopenshell", result["engine"])
        self.assertEqual(2, result["by_rule"]["hard_clash"])
        self.assertEqual(1, result["by_rule"]["probable_duplicate_element"])

    def test_geometry_diagnostics_pass_demo(self):
        from ifcqc.geometry_diagnostics import diagnose_geometry

        content = (ROOT / "samples/geometry_demo.ifc").read_text()
        backend = diagnose_geometry(content)
        request = Request(
            f"{self.base}/api/geometry-diagnostics",
            data=json.dumps({
                "content": content,
                "browser_evidence": {
                    "element_ids": [int(key) for key in backend["element_extents_metres"]],
                    "element_extents_metres": backend["element_extents_metres"],
                },
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        self.assertTrue(result["ready"])
        self.assertEqual(7, result["counts"]["generated_shapes"])
        self.assertEqual(100.0, result["coverage_percent"])

    def test_known_answer_geometry_matrix(self):
        with urlopen(f"{self.base}/api/geometry-acceptance") as response:
            result = json.load(response)
        self.assertTrue(result["passed"])
        self.assertEqual(6, result["passed_cases"])

    def test_export_bcf(self):
        request = Request(
            f"{self.base}/api/export-bcf",
            data=json.dumps({
                "filename": "demo.bcfzip",
                "issues": [{
                    "rule_id": "missing_name", "severity": "warning", "title": "Missing name",
                    "message": "Wall needs a name", "entity_id": 73,
                    "global_id": "2WallDemoGuid000000003",
                }],
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            self.assertEqual("application/zip", response.headers.get_content_type())
            self.assertIn("demo.bcfzip", response.headers["Content-Disposition"])
            with ZipFile(BytesIO(response.read())) as archive:
                self.assertIn("bcf.version", archive.namelist())


if __name__ == "__main__":
    unittest.main()
