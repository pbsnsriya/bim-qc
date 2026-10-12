#!/usr/bin/env python3
"""Check analytic fixtures with independent web-ifc WASM measurements."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ifcqc.geometry_acceptance import CASES, run_acceptance_matrix
from ifcqc.geometry_diagnostics import diagnose_geometry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "stage1-fixture-evidence.json")
    args = parser.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as folder:
        for case in CASES:
            source = ROOT / "samples" / case["file"]
            if not case["core_ready"]:
                diagnostic = diagnose_geometry(source.read_text())
                rows.append({"id": case["id"], "expected": "rejected",
                    "passed": not diagnostic["core_ready"], "comparison": "not_applicable"})
                continue
            evidence = Path(folder) / f"{case['id']}.json"
            subprocess.run(["node", str(ROOT / "scripts/web_ifc_evidence.mjs"),
                str(source), str(evidence)], cwd=ROOT, check=True)
            diagnostic = diagnose_geometry(source.read_text(), json.loads(evidence.read_text()))
            rows.append({"id": case["id"], "expected": "pass",
                "passed": diagnostic["ready"], "comparison": diagnostic["cross_engine"]})
    matrix = run_acceptance_matrix(ROOT / "samples")
    report = {"scope": "Analytic and Node WASM checks; no browser/GPU certification",
        "passed": matrix["passed"] and all(row["passed"] for row in rows),
        "analytic_matrix": matrix, "cross_engine_cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": report["passed"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
