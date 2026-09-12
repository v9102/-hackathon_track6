#!/usr/bin/env python3
"""Resume Evaluator - evaluates tailored resumes against job descriptions."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using PyPDF2 or pdftotext."""
    import subprocess
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ValueError(f"Failed to extract text from PDF: {result.stderr}")
    return result.stdout


def extract_skills_from_text(text: str) -> set[str]:
    """Extract skill mentions from text."""
    common_skills = [
        "Python", "Java", "Go", "Rust", "TypeScript", "JavaScript", "C++", "C#",
        "React", "Node", "Express", "Next.js", "Angular", "Vue",
        "PostgreSQL", "MySQL", "MongoDB", "Redis",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "Git", "GitHub", "GitLab",
        "TensorFlow", "PyTorch", "scikit-learn",
        "Jenkins", "Terraform", "ArgoCD",
        "SQL", "REST API", "JWT", "Auth",
        "Machine Learning", "AI",
        "Data Structures", "Algorithms",
        "Testing", "Unit Testing",
        "Agile", "Scrum",
        "Firebase", "Azure OpenAI",
    ]
    found: set[str] = set()
    for skill in common_skills:
        if re.search(rf"\b{re.escape(skill)}\b", text, re.IGNORECASE):
            found.add(skill)
    return found


def compute_ats_match(resume_text: str, jd_text: str) -> float:
    """Compute ATS match % = keyword overlap with JD."""
    # Extract required skills from JD using simple pattern matching
    common_tech = [
        "Python", "Java", "Go", "JavaScript", "TypeScript", "React", "Node",
        "SQL", "Docker", "Kubernetes", "AWS", "Git",
    ]
    jd_skills = set()
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", jd_text, re.IGNORECASE):
            jd_skills.add(term.lower())

    resume_skills = set()
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", resume_text, re.IGNORECASE):
            resume_skills.add(term.lower())

    if not jd_skills:
        return 0.0

    intersection = jd_skills & resume_skills
    return round(len(intersection) / len(jd_skills) * 100, 2)


def compute_relevance(resume_skills: set[str], required_skills: set[str]) -> float:
    """Compute relevance % = match_score from Task 2."""
    if not required_skills:
        return 0.0
    intersection = resume_skills & required_skills
    return round(len(intersection) / len(required_skills) * 100, 2)


def check_factuality(
    resume_text: str,
    role_kb: dict[str, Any],
    all_resumes: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """Check factuality - flag claims not supported in resume text or known profile."""
    flags = []

    resume_skills = extract_skills_from_text(resume_text)

    # Check against role KB responsibilities
    responsibilities = role_kb.get("responsibilities", [])
    for resp in responsibilities:
        resp_lower = resp.lower()
        # If resume mentions a skill/tools related to this responsibility
        # but doesn't actually claim this responsibility, flag it
        key_skills = set(re.findall(r"\b(\w+\.?\w*)\b", resp_lower))
        for skill in key_skills:
            if skill not in resume_skills and skill not in {
                "built", "designed", "implemented", "created", "developed",
                "experience", "worked", "used"
            }:
                # This skill is mentioned in responsibility but not in resume
                flags.append({
                    "claim": f"Resume doesn't mention {skill} needed for: {resp[:60]}",
                    "severity": "medium",
                })
                break

    # Cross-check with other resumes for consistency
    resume_id = None
    for rid, rdata in all_resumes.items():
        if rdata.get("file_path") == str(resume_text)[:50] if len(resume_text) > 50 else resume_text:
            resume_id = rid
            break

    if resume_id and resume_id in all_resumes:
        other_skills = all_resumes[resume_id]["skills"]
        # Check for claims that contradict other resumes
        for skill in resume_skills:
            if skill not in other_skills:
                # Skill appears in this resume but not others - possible exaggeration
                flags.append({
                    "claim": f"Claims {skill} but other resumes don't mention it",
                    "severity": "low",
                })

    # Check for exaggerated claims
    leetcode_match = re.search(r"\b(\d{3,4})\s*LeetCode\b", resume_text, re.IGNORECASE)
    if leetcode_match:
        claimed = int(leetcode_match.group(1))
        # Check across all resumes for actual LeetCode counts
        all_counts = []
        for rtext in all_resumes.values():
            m = re.search(r"\b(\d{1,3})\s*LeetCode\b", rtext.get("full_text", ""), re.IGNORECASE)
            if m:
                all_counts.append(int(m.group(1)))
        if all_counts:
            avg = sum(all_counts) / len(all_counts)
            if abs(claimed - avg) > 20:
                flags.append({
                    "claim": f"Claims {claimed} LeetCode problems but average across resumes is {round(avg)}",
                    "severity": "medium",
                })

    return flags


def main():
    parser = argparse.ArgumentParser(description="Resume Evaluator")
    parser.add_argument("--resume", type=Path, required=True, help="Tailored resume PDF")
    parser.add_argument("--kb", type=Path, required=True, help="Role KB JSON file")
    parser.add_argument("--jd", type=str, help="Original job description text")
    parser.add_argument("--j-file", type=Path, help="Original JD PDF file")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path")
    parser.add_argument("--resumes-dir", type=Path, help="Directory with all resumes for cross-check")
    args = parser.parse_args()

    # Load env
    env_path = args.env
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

    # Load role KB
    with open(args.kb, "r", encoding="utf-8") as f:
        role_kb = json.load(f)

    # Extract tailored resume text
    if args.jd:
        jd_text = args.jd
    elif args.j_file:
        jd_text = extract_text_from_pdf(args.j_file)
    else:
        parser.error("Either --jd or --j-file must be provided")

    resume_text = extract_text_from_pdf(args.resume)
    resume_skills = extract_skills_from_text(resume_text)

    # Compute ATS match
    ats_score = compute_ats_match(resume_text, jd_text)

    # Compute relevance
    required_skills = set(role_kb.get("required_skills", []))
    relevance_score = compute_relevance(resume_skills, required_skills)

    # Cross-check with other resumes if directory provided
    all_resumes = {}
    if args.resumes_dir and args.resumes_dir.exists():
        import PyPDF2
        for pdf_file in args.resumes_dir.glob("*.pdf"):
            try:
                pdf = PyPDF2.PdfReader(str(pdf_file))
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
                all_resumes[pdf_file.name] = {
                    "full_text": text,
                    "skills": extract_skills_from_text(text),
                }
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Failed to process {pdf_file}: {e}")

    # Factuality check
    flags = check_factuality(resume_text, role_kb, all_resumes)

    # Build evaluation result
    evaluation = {
        "ats_match_percent": ats_score,
        "relevance_percent": relevance_score,
        "factuality_score": round(max(0, 100 - len(flags) * 15), 2),  # deduct 15 per flag
        "flags": flags,
        "resume_skills": sorted(resume_skills),
        "required_skills": sorted(required_skills),
        "matched_skills": sorted(resume_skills & required_skills),
        "missing_skills": sorted(required_skills - resume_skills),
    }

    # Write evaluation
    output_path = args.resume.parent / "evaluation.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, indent=2)

    print(f"Evaluation written to {output_path}")
    print(json.dumps(evaluation, indent=2))


if __name__ == "__main__":
    main()