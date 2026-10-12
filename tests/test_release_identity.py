from pathlib import Path
import re
import unittest

from ifcqc.version import APP_VERSION
from ifcqc.geometry_diagnostics import diagnose_geometry_file

ROOT = Path(__file__).resolve().parents[1]


class ReleaseIdentityTests(unittest.TestCase):
    def test_frontend_backend_header_and_package_agree(self):
        js = (ROOT / "web/version.js").read_text()
        self.assertEqual(APP_VERSION, re.search(r'APP_VERSION = "([^"]+)"', js).group(1))
        self.assertIn(f'"{APP_VERSION}"', (ROOT / "pyproject.toml").read_text())
        self.assertIn(f'v{APP_VERSION}', (ROOT / "web/index.html").read_text())
        viewer = (ROOT / "web/viewer.js").read_text()
        self.assertIn('import { APP_VERSION } from "./version.js";', viewer)
        self.assertIn('viewer_version: APP_VERSION', viewer)

    def test_fresh_geometry_measurements_use_release_identity(self):
        result = diagnose_geometry_file(ROOT / "samples/geometry_demo.ifc")
        self.assertEqual(APP_VERSION, result["provenance"]["app_version"])

