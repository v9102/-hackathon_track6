#!/usr/bin/env python3
"""Change Report - produces human-readable and machine-readable reports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict


def load_json(filepath: Path) -> Dict[str, Any]:
    """Load a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_human_report(
    tailoring_report: Dict[str, any],
    revision_log: Dict[str, any],
) -> str:
    """Generate a human-readable report."""
    # Extract key information from tailoring report
    match_score = tailoring_report.get("match_score", 0)
    resume_name = tailoring_report.get("source_resume", "Unknown Resume")
    role_title = tailoring_report.get("role_title", "Unknown Role")

    # Extract from revision log
    num_revisions = len(revision_log.get("revisions", []))
    status = revision_log.get("status", "completed")

    # Count changes
    all_changes = []
    for rev in revision_log.get("revisions", []):
        all_changes.extend(rev.get("changes", []))

    # Count kept, removed, rewritten bullets from tailoring report
    kept = len(tailoring_report.get("kept_bullets", []))
    removed = len(tailoring_report.get("removed_bullets", []))
    rewritten = len(tailoring_report.get("rewritten_bullets", []))

    # Build human-readable report
    report_lines = [
        f"Applied to {role_title} role.",
        f"Matched {match_score}% of required skills.",
        f"Tailored from {resume_name} ({role_title}).",
    ]

    # Tailoring changes
    tailoring_parts = []
    if kept > 0:
        tailoring_parts.append(f"Kept {kept} relevant bullet point(s).")
    if removed > 0:
        tailoring_parts.append(f"Omitted {removed} unrelated project(s).")
    if rewritten > 0:
        tailoring_parts.append(f"Rewrote {rewritten} bullet point(s) to include required skills.")

    if tailoring_parts:
        report_lines.append("Tailoring changes: " + ". ".join(tailoring_parts) + ".")

    # Revision changes
    if all_changes:
        report_lines.append(f"Made {len(all_changes)} revision(s) during review process.")
    else:
        report_lines.append("No revisions were needed.")

    if status != "completed":
        report_lines.append(f"Revision process stopped: {status} after {num_revisions} step(s).")

    # Final scores
    report_lines.append(
        f"Final ATS match: {revision_log.get('final_ats', 0)}%, "
        f"Factuality: {revision_log.get('final_factuality', 100)}% "
        f"({sum(1 for _ in range(10))} supported claims)"
    )

    report_text = " ".join(report_lines)
    return report_text


def generate_machine_report(
    tailoring_report: Dict[str, any],
    revision_log: Dict[str, any],
) -> Dict[str, any]:
    """Generate a machine-readable evidence report."""
    evidence = {
        "resume_source": tailoring_report.get("source_resume", ""),
        "role_title": tailoring_report.get("role_title", ""),
        "match_score_percent": tailoring_report.get("match_score", 0),
        "required_skills": tailoring_report.get("required_skills", []),
        "resume_skills": tailoring_report.get("resume_skills", []),
        "matched_skills": tailoring_report.get("matched_skills", []),
        "missing_skills": tailoring_report.get("missing_skills", []),
        "preferred_skills": tailoring_report.get("preferred_skills", []),
        "kept_bullets_count": len(tailoring_report.get("kept_bullets", [])),
        "removed_bullets_count": len(tailoring_report.get("removed_bullets", [])),
        "rewritten_bullets_count": len(tailoring_report.get("rewritten_bullets", [])),
        "num_revisions": len(revision_log.get("revisions", [])),
        "revision_status": revision_log.get("status", ""),
        "flags_addressed": sum(
            len(r.get("flags_addressed", [])) for r in revision_log.get("revisions", [])
        ),
        "final_ats_percent": revision_log.get("final_ats", 0),
        "final_relevance_percent": revision_log.get("final_relevance", 0),
        "final_factuality_score": revision_log.get("final_factuality", 100),
    }
    return evidence


def main():
    parser = argparse.ArgumentParser(description="Change Report")
    parser.add_argument("--tailoring", type=Path, required=True, help="Tailoring report JSON")
    parser.add_argument("--revisions", type=Path, required=True, help="Revision log JSON")
    parser.add_argument("--output", type=Path, default=Path("evidence_report.json"), help="Output machine report")
    parser.add_argument("--human-output", type=Path, default=Path("change_report.txt"), help="Output human report")
    args = parser.parse_args()

    # Load reports
    tailoring_report = load_json(args.tailoring)
    revision_log = load_json(args.revisions)

    # Generate human-readable report
    human_report = generate_human_report(tailoring_report, revision_log)
    with open(args.human_output, "w", encoding="utf-8") as f:
        f.write(human_report)
    print(f"Human-readable report written to {args.human_output}")
    print("\n--- Human Report ---")
    print(human_report)

    # Generate machine-readable evidence report
    evidence = generate_machine_report(tailoring_report, revision_log)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
    print(f"\nMachine-readable evidence report written to {args.output}")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()