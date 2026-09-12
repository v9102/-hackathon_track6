#!/usr/bin/env python3
"""Single authoritative entry point for the autonomous resume agent.

Usage:
    python -m app.main                      # default demo run
    python -m app.main run --jd <file>      # run with a specific JD file
    python -m app.main run --help
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.agents.planner import _DEFAULT_JD, AgenticPlanner
from app.core.config import settings


def _list_candidate_resumes(resume_dir: Path) -> list[Path]:
    if resume_dir.is_dir():
        return sorted(p for p in resume_dir.glob("*.pdf") if p.is_file())
    return [resume_dir]


def run_pipeline(args: argparse.Namespace):
    """Run the full autonomous agentic pipeline."""
    jd_source: str = args.jd or ""
    if not jd_source:
        default_jd = settings.default_jd_path
        if default_jd.exists():
            jd_source = default_jd.read_text(encoding="utf-8")
        else:
            jd_source = _DEFAULT_JD
    else:
        jd_path = Path(jd_source)
        if jd_path.exists():
            jd_source = jd_path.read_text(encoding="utf-8")

    resume_files = _list_candidate_resumes(Path(args.resume_dir) if args.resume_dir else settings.resume_dir)
    template_path = Path(args.template) if args.template else settings.default_template_path

    print("=" * 72)
    print("Autonomous Resume Agent - Goal -> Decision -> Action -> ... -> Outcome")
    print("=" * 72)
    print(f"  JD source      : {'(default sample)' if not args.jd else args.jd}")
    print(f"  Candidate PDFs : {len(resume_files)} resume(s)")
    print(f"  Template       : {template_path}")
    print(f"  Max iterations : {settings.max_iterations}")
    print("=" * 72)

    planner = AgenticPlanner()
    state = planner.run(jd_text=jd_source, resume_files=resume_files, template_path=template_path)

    print("\nFINAL OUTCOME")
    print("-" * 72)
    print(f"  Run ID             : {state.run_id}")
    print(f"  Final status       : {state.final_status}")
    if state.selected_resume:
        print(f"  Selected resume    : {state.selected_resume.name}")
        print(f"  Selection score    : {state.selected_resume.selection_score}")
        print(f"  Selection reason   : {state.selected_resume.reasoning}")

    final = state.current_evaluation
    if final:
        print("  Final evaluation   :")
        for key in ("ats_match_percent", "relevance_percent", "factuality_score", "format_score"):
            print(f"      {key:<20}: {final.get(key)}")
        print(f"      unsupported_claims : {len(final.get('unsupported_claims', []))}")

    if state.decisions:
        print(f"  Decisions          : {len(state.decisions)} "
              f"({sum(1 for d in state.decisions if d.accepted)} accepted, "
              f"{sum(1 for d in state.decisions if not d.accepted)} rejected/rolled-back)")
        for decision in state.decisions:
            mark = "OK " if decision.accepted else "REJ"
            print(f"      [{mark}] iter {decision.iteration}: {decision.decision}")
            if not decision.accepted:
                print(f"             -> {decision.rollback_reason}")
    if state.verification:
        print("  Verification       :",
              state.verification.get("valid"), "-",
              state.verification.get("artifact"))
    print("  Artifacts          :", state.run_dir)

    final_report = Path(state.run_dir) / "final_report.txt"
    if final_report.exists():
        print(f"\nHuman-readable report written to: {final_report}")

    return state


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.main", description="Autonomous Resume Agent")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "demo"])

    sub = parser.add_argument_group("run options")
    sub.add_argument("--jd", default="", help="Path to a JD text file (defaults to data/default_jd.txt or built-in sample)")
    sub.add_argument("--resume-dir", default="", help="Directory (or PDF) with candidate resumes (default: Resumes/)")
    sub.add_argument("--template", default="", help="LaTeX template path (default: ShaunakMishra_Resume.tex)")
    sub.add_argument("--task", default="", help="Deprecated: legacy task modes removed; use 'run'.")

    args = parser.parse_args()
    if args.task:
        print("Note: legacy --task modes have been replaced by the single agentic 'run' command.")
    state = run_pipeline(args)
    return 0 if state.final_status != "render_failed" else 1


if __name__ == "__main__":
    sys.exit(main())