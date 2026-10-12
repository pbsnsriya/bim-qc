"""Zero-dependency development server for the OpenBIM QC Assistant."""

from __future__ import annotations

import cgi
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import urlparse

from ifcqc import analyze_ifc
from ifcqc.analyzer import analyze_ifc_file
from ifcqc.backends import capabilities
from ifcqc.bcf import build_bcfzip
from ifcqc.geometry_checks import run_geometry_checks
from ifcqc.geometry_acceptance import run_acceptance_matrix
from ifcqc.geometry_diagnostics import diagnose_geometry
from ifcqc.ids_validator import validate_ids
from ifcqc.runtime import GeometryJobManager, ModelStore


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"
MAX_IFC_BYTES = 100 * 1024 * 1024
# JSON escaping adds overhead beyond the source IFC byte count.
MAX_BODY_BYTES = 120 * 1024 * 1024
MAX_MULTIPART_BYTES = MAX_IFC_BYTES + 1024 * 1024
MODEL_STORE = ModelStore(MAX_IFC_BYTES)
GEOMETRY_JOBS = GeometryJobManager()


def require_ifc_content(payload: dict) -> str:
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("The IFC content must be text.")
    if len(content.encode("utf-8")) > MAX_IFC_BYTES:
        raise ValueError("The IFC file must not exceed 100 MB.")
    return content


def content_for_payload(payload: dict) -> str:
    """Resolve a stored model session, falling back to the legacy inline API."""
    model_id = payload.get("model_id")
    if isinstance(model_id, str) and model_id:
        record = MODEL_STORE.get(model_id)
        return record.path.read_text(encoding="utf-8", errors="strict")
    return require_ifc_content(payload)

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".ifc": "application/octet-stream",
    ".ids": "application/xml; charset=utf-8",
    ".wasm": "application/wasm",
    ".md": "text/markdown; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, status: int, body: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if filename:
            safe_name = filename.replace('"', "").replace("\r", "").replace("\n", "")
            self.send_header("Content-Disposition", f'attachment; filename="{safe_name}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/health":
            self.send_json(200, {"status": "ok"})
            return
        if path == "/api/capabilities":
            self.send_json(200, capabilities())
            return
        if path == "/api/geometry-acceptance":
            self.send_json(200, run_acceptance_matrix(SAMPLES))
            return
        if path == "/api/demo":
            text = (SAMPLES / "geometry_demo.ifc").read_text(encoding="utf-8")
            self.send_json(200, analyze_ifc(text, "geometry_demo.ifc"))
            return
        if path == "/api/demo-file":
            data = (SAMPLES / "geometry_demo.ifc").read_bytes()
            self.send_bytes(200, data, "application/octet-stream")
            return
        if path == "/api/demo-ids-file":
            data = (SAMPLES / "wall-naming.ids").read_bytes()
            self.send_bytes(200, data, "application/xml; charset=utf-8")
            return
        job_match = re.fullmatch(r"/api/geometry-jobs/([0-9a-f]{32})", path)
        if job_match:
            try:
                self.send_json(200, GEOMETRY_JOBS.status(job_match.group(1)))
            except ValueError as exc:
                self.send_json(404, {"error": str(exc)})
            return
        relative = "index.html" if path == "/" else path.lstrip("/")
        target = (WEB / relative).resolve()
        if WEB.resolve() not in target.parents and target != WEB.resolve():
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", MIME_TYPES.get(target.suffix, "application/octet-stream"))
        if target.suffix in {".html", ".js"}:
            self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/models":
            self._upload_model()
            return
        reanalyze_match = re.fullmatch(r"/api/models/([0-9a-f]{32})/analyze", path)
        if reanalyze_match:
            self._reanalyze_model(reanalyze_match.group(1))
            return
        if path == "/api/geometry-jobs":
            self._start_geometry_job()
            return
        cancel_match = re.fullmatch(r"/api/geometry-jobs/([0-9a-f]{32})/cancel", path)
        if cancel_match:
            try:
                self.send_json(200, GEOMETRY_JOBS.cancel(cancel_match.group(1)))
            except ValueError as exc:
                self.send_json(404, {"error": str(exc)})
            return
        if path not in {
            "/api/analyze", "/api/validate-ids", "/api/geometry-diagnostics",
            "/api/geometry-checks", "/api/export-bcf",
        }:
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY_BYTES:
                raise ValueError("Request must be between 1 byte and 120 MB; IFC files are limited to 100 MB.")
            payload = json.loads(self.rfile.read(size))
            if path == "/api/analyze":
                filename = str(payload.get("filename", "model.ifc"))[:200]
                profile = str(payload.get("profile", "coordination"))
                content = content_for_payload(payload)
                self.send_json(200, analyze_ifc(content, filename, profile))
            elif path == "/api/validate-ids":
                content = content_for_payload(payload)
                ids_content = payload.get("ids_content")
                if not isinstance(ids_content, str):
                    raise ValueError("Both IFC and IDS content must be text.")
                filename = str(payload.get("ids_filename", "requirements.ids"))[:200]
                self.send_json(200, validate_ids(content, ids_content, filename))
            elif path == "/api/geometry-checks":
                content = content_for_payload(payload)
                config = payload.get("config", {})
                if not isinstance(config, dict):
                    raise ValueError("Geometry configuration must be an object.")
                self.send_json(200, run_geometry_checks(content, config))
            elif path == "/api/geometry-diagnostics":
                content = content_for_payload(payload)
                browser_evidence = payload.get("browser_evidence")
                if browser_evidence is not None and not isinstance(browser_evidence, dict):
                    raise ValueError("Browser geometry evidence must be an object.")
                self.send_json(200, diagnose_geometry(content, browser_evidence))
            else:
                issues = payload.get("issues")
                if not isinstance(issues, list) or not all(isinstance(issue, dict) for issue in issues):
                    raise ValueError("BCF export requires an issue list.")
                if len(issues) > 5_000:
                    raise ValueError("BCF export is limited to 5,000 issues.")
                filename = str(payload.get("filename", "openbim-qc-issues.bcfzip"))[:200]
                if not filename.lower().endswith(".bcfzip"):
                    filename += ".bcfzip"
                self.send_bytes(200, build_bcfzip(issues), "application/zip", filename)
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            self.send_json(500, {"error": "The model could not be analysed."})

    def _read_json(self, maximum: int = MAX_BODY_BYTES) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size <= 0 or size > maximum:
            raise ValueError(f"Request must be between 1 byte and {maximum // (1024 * 1024)} MB.")
        payload = json.loads(self.rfile.read(size))
        if not isinstance(payload, dict):
            raise ValueError("The request body must be a JSON object.")
        return payload

    def _upload_model(self) -> None:
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_MULTIPART_BYTES:
                raise ValueError("Multipart upload must contain one IFC file up to 100 MB.")
            content_type = self.headers.get("Content-Type", "")
            if not content_type.lower().startswith("multipart/form-data"):
                raise ValueError("Model upload must use multipart/form-data.")
            cgi.maxlen = MAX_MULTIPART_BYTES
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(size),
                },
                keep_blank_values=True,
            )
            if "file" not in form:
                raise ValueError("Multipart upload is missing the IFC file field.")
            upload = form["file"]
            if isinstance(upload, list) or not getattr(upload, "file", None):
                raise ValueError("Upload exactly one IFC file.")
            filename = str(getattr(upload, "filename", None) or "model.ifc")
            profile = str(form.getfirst("profile", "coordination"))
            record = MODEL_STORE.save(upload.file, filename, GEOMETRY_JOBS.active_model_ids())
            try:
                result = analyze_ifc_file(record.path, record.filename, profile)
            except Exception:
                record.path.unlink(missing_ok=True)
                raise
            self.send_json(201, {
                "model_id": record.model_id,
                "size_bytes": record.size,
                "analysis": result,
            })
        except (ValueError, RuntimeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            self.send_json(500, {"error": "The uploaded model could not be analysed."})

    def _reanalyze_model(self, model_id: str) -> None:
        try:
            payload = self._read_json(1024 * 1024)
            profile = str(payload.get("profile", "coordination"))
            record = MODEL_STORE.get(model_id)
            self.send_json(200, analyze_ifc_file(record.path, record.filename, profile))
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            self.send_json(500, {"error": "The stored model could not be analysed."})

    def _start_geometry_job(self) -> None:
        try:
            payload = self._read_json(20 * 1024 * 1024)
            model_id = payload.get("model_id")
            if not isinstance(model_id, str):
                raise ValueError("A stored model_id is required for background geometry validation.")
            browser_evidence = payload.get("browser_evidence")
            if browser_evidence is not None and not isinstance(browser_evidence, dict):
                raise ValueError("Browser geometry evidence must be an object.")
            record = MODEL_STORE.get(model_id)
            job_id = GEOMETRY_JOBS.start(record, browser_evidence)
            self.send_json(202, {
                "job_id": job_id,
                "model_id": model_id,
                "state": "queued",
                "poll_url": f"/api/geometry-jobs/{job_id}",
            })
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
        except Exception:
            self.send_json(500, {"error": "The geometry job could not be started."})

    def log_message(self, fmt: str, *args) -> None:
        print(f"[openbim-qc] {fmt % args}")


def main() -> None:
    address = ("127.0.0.1", 8000)
    print(f"OpenBIM QC Assistant running at http://{address[0]}:{address[1]}")
    server = ThreadingHTTPServer(address, Handler)
    try:
        server.serve_forever()
    finally:
        GEOMETRY_JOBS.close()
        MODEL_STORE.close()


if __name__ == "__main__":
    main()
