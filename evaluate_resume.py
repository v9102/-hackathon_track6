#!/usr/bin/env python3
"""Root wrapper for the resume evaluator CLI (logic lives in app.agents.evaluator).

Run: ``python3 evaluate_resume.py --resume ... --jd "..."`` or ``python3 -m app.main``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume Evaluator (delegates to app.agents.evaluator)")
    parser.add_argument("--resume", type=Path, required=True, help="Resume PDF")
    parser.add_argument("--kb", type=Path, required=False, help="Role KB JSON file")
    parser.add_argument("--jd", type=str, default="", help="Job description text")
    parser.add_argument("--j-file", type=Path, help="Original JD PDF file")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path (unused)")
    parser.add_argument("--resumes-dir", type=Path, help="Unused: cross-resume checks are not falsity evidence")
    parser.add_argument("--output", type=Path, default=Path("evaluation.json"), help="Output JSON")
    args = parser.parse_args()

    from app.agents.evaluator import EvaluationAgent
    from app.tools.jdp_parser import extract_text_from_pdf

    jd_text = args.jd or ""
    if not jd_text and args.j_file:
        jd_text = extract_text_from_pdf(args.j_file)

    resume_text = extract_text_from_pdf(args.resume)
    evaluation = EvaluationAgent().evaluate(resume_text, jd_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evaluation, indent=2), encoding="utf-8")

    print("Evaluation results:")
    for key in ("ats_match_percent", "relevance_percent", "factuality_score"):
        print(f"  {key}: {evaluation.get(key)}")
    print(f"  flags: {len(evaluation.get('flags', []))}")
    print(f"  written to: {args.output}")


if __name__ == "__main__":
    main()
