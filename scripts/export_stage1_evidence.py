#!/usr/bin/env python3
"""Export repeatable file-backed Stage 1 evidence; no browser/GPU claims."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ifcqc.geometry_acceptance import run_acceptance_matrix
from ifcqc.geometry_diagnostics import diagnose_geometry_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--comparison", type=Path)
    args = parser.parse_args()
    comparison = json.loads(args.comparison.read_text()) if args.comparison else None
    report = diagnose_geometry_file(args.model, comparison,
        lambda item: print(item["message"], flush=True))
    matrix = run_acceptance_matrix(ROOT / "samples")
    report["acceptance_matrix"] = matrix
    report["ready"] = report["ready"] and matrix["passed"]
    report["stage2_ready"] = report["duplicate_prerequisites_ready"] and matrix["passed"]
    report["report_type"] = "OpenBIM QC Stage 1 extraction evidence"
    report["conclusion"] = "pass" if report["ready"] else "needs_attention"
    report["browser_geometry_evidence"] = comparison
    report["browser_gpu_validation"] = {"verdict": "not_evaluated",
        "message": "CLI execution does not test browser rendering or physical GPU performance."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "conclusion": report["conclusion"],
        "sha256": report["provenance"]["model_sha256"],
        "critical_ids": report["critical_unresolved_ids"]}))


if __name__ == "__main__":
    main()
