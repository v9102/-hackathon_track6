#!/usr/bin/env python3
"""Root wrapper for the change report CLI (logic lives in app.tools.reports).

Run: ``python3 change_report.py --tailoring ... --revisions ...`` or, better,
run the full agentic pipeline with ``python3 -m app.main`` which writes the
final human/machine reports into ``storage/runs/<run_id>/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Change Report (delegates to app.tools.reports)")
    parser.add_argument("--tailoring", type=Path, required=True, help="Tailoring report JSON")
    parser.add_argument("--revisions", type=Path, required=True, help="Revision log JSON")
    parser.add_argument("--output", type=Path, default=Path("evidence_report.json"), help="Output machine report")
    parser.add_argument("--human-output", type=Path, default=Path("change_report.txt"), help="Output human report")
    args = parser.parse_args()

    from app.tools.reports import generate_human_report, generate_machine_report

    tailoring = json.loads(args.tailoring.read_text(encoding="utf-8"))
    revisions = json.loads(args.revisions.read_text(encoding="utf-8"))

    args.human_output.parent.mkdir(parents=True, exist_ok=True)
    args.human_output.write_text(generate_human_report(tailoring, revisions), encoding="utf-8")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generate_machine_report(tailoring, revisions), indent=2), encoding="utf-8")

    print(f"Human report : {args.human_output}")
    print(f"Machine report: {args.output}")


if __name__ == "__main__":
    main()
