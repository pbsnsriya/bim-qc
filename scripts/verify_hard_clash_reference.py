#!/usr/bin/env python3
"""Export the Stage 3 factual matrix; exit 1 when the reference gate fails."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ifcqc.hard_clash_acceptance import run_hard_clash_acceptance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = run_hard_clash_acceptance(ROOT / "samples")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "passed": report["passed"],
        "passed_cases": report["passed_cases"], "total_cases": report["total_cases"],
        "model_clash_checking_enabled": report["model_clash_checking_enabled"]}))
    return 0 if report["passed"] else 1


if __name__ == "__main__": sys.exit(main())
