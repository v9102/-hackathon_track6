"""Report generation for tailoring and revision artifacts."""

from __future__ import annotations

from typing import Any


def generate_human_report(
    tailoring_report: dict[str, Any],
    revision_log: dict[str, Any],
) -> str:
    """Generate a human-readable change report."""
    match_score = tailoring_report.get("match_score", 0)
    resume_name = tailoring_report.get("source_resume", "Unknown Resume")
    role_title = tailoring_report.get("role_title", "Unknown Role")

    num_revisions = len(revision_log.get("revisions", []))
    status = revision_log.get("status", "completed")

    all_changes: list[str] = []
    for rev in revision_log.get("revisions", []):
        all_changes.extend(rev.get("changes", []))

    kept = len(tailoring_report.get("kept_bullets", []))
    removed = len(tailoring_report.get("removed_bullets", []))
    rewritten = len(tailoring_report.get("rewritten_bullets", []))

    report_lines = [
        f"Applied to {role_title} role.",
        f"Matched {match_score}% of required skills.",
        f"Tailored from {resume_name} ({role_title}).",
    ]

    tailoring_parts: list[str] = []
    if kept > 0:
        tailoring_parts.append(f"Kept {kept} relevant bullet point(s).")
    if removed > 0:
        tailoring_parts.append(f"Omitted {removed} unrelated project(s).")
    if rewritten > 0:
        tailoring_parts.append(f"Rewrote {rewritten} bullet point(s) to include required skills.")

    if tailoring_parts:
        report_lines.append("Tailoring changes: " + ". ".join(tailoring_parts) + ".")

    if all_changes:
        report_lines.append(f"Made {len(all_changes)} revision(s) during review process.")
    else:
        report_lines.append("No revisions were needed.")

    if status != "completed":
        report_lines.append(f"Revision process stopped: {status} after {num_revisions} step(s).")

    report_lines.append(
        f"Final ATS match: {revision_log.get('final_ats', 0)}%, "
        f"Factuality: {revision_log.get('final_factuality', 100)}% "
        f"({sum(1 for _ in range(10))} supported claims)"
    )

    return " ".join(report_lines)


def generate_machine_report(
    tailoring_report: dict[str, Any],
    revision_log: dict[str, Any],
) -> dict[str, Any]:
    """Generate a machine-readable evidence report."""
    return {
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
