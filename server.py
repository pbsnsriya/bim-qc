"""Zero-dependency development server for the OpenBIM QC Assistant."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from ifcqc import analyze_ifc
from ifcqc.backends import capabilities
from ifcqc.bcf import build_bcfzip
from ifcqc.geometry_checks import run_geometry_checks
from ifcqc.geometry_diagnostics import diagnose_geometry
from ifcqc.ids_validator import validate_ids


ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"
SAMPLES = ROOT / "samples"
MAX_BODY_BYTES = 25 * 1024 * 1024

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
        if path not in {
            "/api/analyze", "/api/validate-ids", "/api/geometry-diagnostics",
            "/api/geometry-checks", "/api/export-bcf",
        }:
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY_BYTES:
                raise ValueError("Request must be between 1 byte and 25 MB.")
            payload = json.loads(self.rfile.read(size))
            if path == "/api/analyze":
                filename = str(payload.get("filename", "model.ifc"))[:200]
                profile = str(payload.get("profile", "coordination"))
                content = payload.get("content")
                if not isinstance(content, str):
                    raise ValueError("The IFC content must be text.")
                self.send_json(200, analyze_ifc(content, filename, profile))
            elif path == "/api/validate-ids":
                content = payload.get("content")
                ids_content = payload.get("ids_content")
                if not isinstance(content, str) or not isinstance(ids_content, str):
                    raise ValueError("Both IFC and IDS content must be text.")
                filename = str(payload.get("ids_filename", "requirements.ids"))[:200]
                self.send_json(200, validate_ids(content, ids_content, filename))
            elif path == "/api/geometry-checks":
                content = payload.get("content")
                config = payload.get("config", {})
                if not isinstance(content, str):
                    raise ValueError("The IFC content must be text.")
                if not isinstance(config, dict):
                    raise ValueError("Geometry configuration must be an object.")
                self.send_json(200, run_geometry_checks(content, config))
            elif path == "/api/geometry-diagnostics":
                content = payload.get("content")
                if not isinstance(content, str):
                    raise ValueError("The IFC content must be text.")
                self.send_json(200, diagnose_geometry(content))
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

    def log_message(self, fmt: str, *args) -> None:
        print(f"[openbim-qc] {fmt % args}")


def main() -> None:
    address = ("127.0.0.1", 8000)
    print(f"OpenBIM QC Assistant running at http://{address[0]}:{address[1]}")
    ThreadingHTTPServer(address, Handler).serve_forever()


if __name__ == "__main__":
    main()
