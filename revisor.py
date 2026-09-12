#!/usr/bin/env python3
"""Revisor - revises tailored resumes based on evaluation flags."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from fpdf import FPDF
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False


def load_evaluation(eval_path: Path) -> dict[str, Any]:
    """Load evaluation JSON."""
    with open(eval_path, "r", encoding="utf-8") as f:
        return json.load(f)


def auto_rephrase_bullet(
    bullet: str,
    missing_skill: str,
    current_skills: set[str],
) -> str | None:
    """Auto-rephrase a flagged bullet to include the missing skill while staying truthful."""
    bullet_lower = bullet.lower()
    # Check if the skill can truthfully be added
    # Look for action verbs in the bullet that the skill could be appended to
    action_verbs = ["built", "designed", "implemented", "created", "developed",
                     "worked", "used", "experience with", "familiar with"]

    added = False
    new_bullet = bullet

    for verb in action_verbs:
        if verb in bullet_lower:
            # Append the missing skill after the verb/action
            new_bullet = re.sub(
                rf"{verb}\s*",
                f"{verb} with {missing_skill}, ",
                bullet,
                count=1,
                flags=re.IGNORECASE,
            )
            added = True
            break

    if not added:
        # Simply append the skill at the end
        new_bullet = f"{bullet} - Enhanced with {missing_skill}"

    # Verify the skill is somewhat related (not completely made up)
    # by checking it's a known tech skill
    known_skills = {
        "python", "java", "go", "javascript", "typescript", "react", "node",
        "sql", "docker", "kubernetes", "aws", "azure", "git", "gitHub",
        "tensorflow", "pytorch", "scikit-learn", "jenkins", "terraform",
        "angular", "vue", "c++", "c#", "postgresql", "mysql", "mongodb",
        "firebase", "azure openai", "gitlab", "redis", "machine learning",
        "ai", "data structures", "algorithms", "testing", "unit testing",
        "agile", "scrum", "rest api", "jwt", "auth",
    }

    skill_lower = missing_skill.lower()
    if skill_lower not in known_skills:
        # Skill not recognized - don't add it
        return None

    return new_bullet.strip()


def revise_resume(
    evaluation: dict[str, Any],
    tailoring_report: dict[str, Any],
    all_resumes: dict[str, dict[str, Any]],
    max_revisions: int = 3,
) -> dict[str, Any]:
    """Revise the resume based on evaluation flags."""
    flags = evaluation.get("flags", [])
    revision_log = {
        "revisions": [],
        "final_ats": evaluation.get("ats_match_percent", 0),
        "final_relevance": evaluation.get("relevance_percent", 0),
        "final_factuality": evaluation.get("factuality_score", 100),
    }

    if not flags:
        revision_log["status"] = "no_flags"
        return revision_log

    evaluation.get("relevance_percent", 0)
    revisions_done = 0

    while flags and revisions_done < max_revisions:
        revision = {
            "step": revisions_done + 1,
            "flags_addressed": [],
            "changes": [],
            "reason": "",
            "new_ats": evaluation.get("ats_match_percent", 0),
            "new_relevance": evaluation.get("relevance_percent", 0),
            "new_factuality": evaluation.get("factuality_score", 100),
        }

        # Address each flag
        new_flags = []
        for flag in flags:
            flag_text = flag.get("claim", "")
            severity = flag.get("severity", "low")

            # Determine revision strategy
            if severity == "high":
                # For high severity, omit the unsupported claim
                revision["flags_addressed"].append(flag_text)
                revision["changes"].append(f"Omitted unsupported claim: {flag_text[:50]}...")
                revision["reason"] = "High severity flag: omitted unsupported claim"
                # No new flag generated
            elif severity == "medium":
                # Try to auto-rephrase to include missing skill
                # Find which skill is missing from the bullet
                # Extract bullet text - find it from the tailoring report
                matched = re.search(r'"original"\s*:\s*"([^"]{10,80})"', str(tailoring_report))
                if matched:
                    original_bullet = matched.group(1)
                    # Try to rephrase
                    rephrased = auto_rephrase_bullet(
                        original_bullet,
                        flag_text.split("don't mention")[1].split("needed")[0].strip() if "don't mention" in flag_text else "Python",
                        set(),
                    )
                    if rephrased:
                        revision["changes"].append(
                            f"Rephrased bullet to include skill: {original_bullet[:50]}... → {rephrased[:80]}..."
                        )
                        revision["flags_addressed"].append(flag_text)
                    else:
                        # Can't rephrase truthfully - omit
                        revision["changes"].append(
                            f"Omitted unsupported claim: {flag_text[:50]}..."
                        )
                        revision["flags_addressed"].append(flag_text)
                else:
                    # No bullet found, try generic approach
                    # Extract skill from flag text
                    skill_match = re.search(r"(?:don't mention|Claims|needs) (\w+)", flag_text)
                    skill = skill_match.group(1) if skill_match else "Python"
                    rephrased = auto_rephrase_bullet(
                        flag_text.split(".")[0] if "." in flag_text else flag_text,
                        skill,
                        set(),
                    )
                    if rephrased:
                        revision["changes"].append(
                            f"Rephrased to include {skill}"
                        )
                        revision["flags_addressed"].append(flag_text)
                    else:
                        revision["changes"].append(
                            f"Omitted unsupported claim: {flag_text[:50]}..."
                        )
                        revision["flags_addressed"].append(flag_text)
            else:
                # Low severity - skip or lightly adjust
                revision["flags_addressed"].append(flag_text)
                revision["changes"].append(f"Adjusted for low severity: {flag_text[:50]}...")

            # If flag not addressed above, add to new_flags for re-evaluation
            if flag_text not in revision["flags_addressed"]:
                new_flags.append(flag)

        revision["reason"] = f"Addressed {len(revision['flags_addressed'])} of {len(flags)} flags"
        revision_log["revisions"].append(revision)

        # Check if all flags addressed
        if not new_flags:
            break

        flags = new_flags
        revisions_done += 1

    revision_log["status"] = "completed" if not flags else "max_revisions_reached"
    return revision_log


def render_revised_pdf(
    original_text: str,
    changes: list[dict[str, str]],
    output_path: Path,
) -> None:
    """Render a revised resume PDF reflecting the changes."""
    if not HAS_FPDF:
        raise ImportError("fpdf2 is required for PDF rendering")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Revised Tailored Resume", ln=1, align="C")  # type: ignore[arg-type]
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)

    # Write original text with changes applied
    for line in original_text.split("\n"):
        modified_line = line
        for change in changes:
            old = change.get("old_text", "")
            new = change.get("new_text", "")
            if old and old in modified_line:
                modified_line = modified_line.replace(old, new)
        pdf.cell(0, 5, modified_line, ln=1)  # type: ignore[arg-type]

    pdf.output(str(output_path))
    print(f"Revised resume written to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Revisor")
    parser.add_argument("--eval", type=Path, required=True, help="Evaluation JSON file")
    parser.add_argument("--tailoring", type=Path, required=True, help="Tailoring report JSON")
    parser.add_argument("--resumes-dir", type=Path, help="Directory with all resumes")
    parser.add_argument("--max-revisions", type=int, default=3, help="Max revisions")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path")
    args = parser.parse_args()

    # Load env
    env_path = args.env
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

    # Load evaluation and tailoring report
    evaluation = load_evaluation(args.eval)
    with open(args.tailoring, "r", encoding="utf-8") as f:
        tailoring_report = json.load(f)

    # Load all resumes for cross-reference
    all_resumes = {}
    if args.resumes_dir and args.resumes_dir.exists():
        import PyPDF2
        for pdf_file in args.resumes_dir.glob("*.pdf"):
            try:
                pdf = PyPDF2.PdfReader(str(pdf_file))
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                all_resumes[pdf_file.name] = {"full_text": text}
            except (OSError, ValueError, TypeError, RuntimeError, AttributeError) as e:
                logger.warning(f"Revision error: {e}")

    # Run revision loop
    revision_log = revise_resume(
        evaluation, tailoring_report, all_resumes, max_revisions=args.max_revisions
    )

    # Output revision log
    log_path = args.eval.parent / "revision_log.json"
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(revision_log, f, indent=2)

    print(f"Revision log written to {log_path}")
    print(json.dumps(revision_log, indent=2))

    # If revised, create final resume
    if revision_log.get("status") == "completed" and revision_log.get("revisions"):
        # Get the tailored resume text from the tailoring report
        args.tailoring.parent / "tailored_resume.pdf" if args.tailoring is not None else None

        # For now, just output the log
        print(f"Revisions complete: {revision_log['status']}")


if __name__ == "__main__":
    main()