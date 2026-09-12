"""Evaluation Agent - ATS / Relevance / Factuality / Format assessment.

The Evaluation Agent assesses a resume against a job description. It has two
entry points:

- ``EvaluationAgent.evaluate(resume_text, jd_text)`` — lightweight scoring,
  kept for compatibility.
- ``EvaluationAgent.evaluate_agentic(...)`` — full evaluation of the actual
  rendered artifact (PDF text) against the role KB and the candidate's
  ground-truth evidence map.

It operates truth-first: it never fabricates support. An unsupported claim is
a skill present in the *output* resume that has no mention in the candidate's
*original* evidence. Absence of a skill in another candidate's resume is NOT
treated as evidence of falsity.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.models import StructuredResume
from app.tools.evidence import (
    SkillEvidence,
    evidence_for_skill,
    find_unsupported_claims,
    required_evidence_summary,
)
from app.tools.jdp_parser import parse_required_skills, parse_responsibilities
from app.tools.latex_renderer import check_pdf_artifact, format_score_estimate
from app.tools.skills import (
    canonicalize_list,
    extract_canonical_skills,
)


def compute_ats_match(resume_text: str, jd_text: str) -> float:
    """Compute ATS match % = required-skill coverage of the resume text.

    Uses the actual skills required by the JD (canonicalized) rather than any
    hard-coded tech list.
    """
    required = canonicalize_list(parse_required_skills(jd_text))
    if not required:
        return 0.0
    resume_skills = extract_canonical_skills(resume_text)
    matched = resume_skills & required
    return round(len(matched) / len(required) * 100, 2)


def compute_relevance(resume_skills: set[str], required_skills: set[str]) -> float:
    """Compute relevance % = fraction of required skills the resume covers."""
    if not required_skills:
        return 0.0
    intersection = resume_skills & required_skills
    return round(len(intersection) / len(required_skills) * 100, 2)


def check_factuality(
    resume_text: str,
    role_kb: dict[str, Any],
    all_resumes: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check factuality - flag responsibilities the resume cannot fulfil.

    ``all_resumes`` is accepted for interface compatibility but is NOT used to
    judge truthfulness: another resume's silence about a skill is not evidence
    that this candidate lacks it.
    """
    flags: list[dict[str, str]] = []
    resume_skills = extract_canonical_skills(resume_text)

    responsibilities = role_kb.get("responsibilities", [])
    for resp in responsibilities:
        for skill in sorted(extract_canonical_skills(resp)):
            if skill not in resume_skills:
                flags.append(
                    {
                        "claim": f"Resume doesn't mention {skill} needed for: {resp[:60]}",
                        "severity": "medium",
                    }
                )
                break

    medium_count = sum(1 for f in flags if f.get("severity") == "medium")
    low_count = sum(1 for f in flags if f.get("severity") == "low")
    factuality_score = round(max(0, 100 - (medium_count * 15 + low_count * 5)), 2)

    return {
        "factuality_score": factuality_score,
        "flags": flags,
        "resume_skills": sorted(set(resume_skills)),
    }


class EvaluationAgent:
    """Agent that evaluates resumes against job descriptions."""

    def evaluate(
        self,
        resume_text: str,
        jd_text: str,
        all_resumes_data: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Execute the lightweight evaluation pipeline (compat interface)."""
        resume_skills = extract_canonical_skills(resume_text)
        jd_required_skills = parse_required_skills(jd_text)
        jd_responsibilities = parse_responsibilities(jd_text)
        required_skills: set[str] = canonicalize_list(jd_required_skills)

        ats_match = compute_ats_match(resume_text, jd_text)
        relevance = compute_relevance(resume_skills, required_skills)
        factuality = check_factuality(
            resume_text,
            {"required_skills": list(required_skills), "responsibilities": jd_responsibilities},
            all_resumes_data,
        )

        return {
            "ats_match_percent": ats_match,
            "relevance_percent": relevance,
            "factuality_score": factuality["factuality_score"],
            "flags": factuality["flags"],
            "resume_skills": sorted(resume_skills),
            "matched_skills": sorted(resume_skills & required_skills),
            "missing_skills": sorted(required_skills - resume_skills),
        }

    def evaluate_agentic(
        self,
        structured_resume: StructuredResume,
        role_kb: dict[str, Any],
        evidence_map: dict[str, SkillEvidence],
        artifact_text: str = "",
        artifact_path: Path | None = None,
    ) -> dict[str, Any]:
        """Evaluate the *actual rendered artifact* against the role KB + evidence.

        - ``output_text``: text of the rendered PDF (extracted), falling back to
          the structured resume text when no PDF is available.
        - Unsupported claims are judged against the candidate's ORIGINAL
          evidence map - never against arbitrary JD keywords or other resumes.
        - Format is scored from the rendered PDF artifact when available.
        """
        output_text = (artifact_text or structured_resume.full_text()).strip()
        required: set[str] = canonicalize_list(role_kb.get("required_skills", []))
        resume_skills = extract_canonical_skills(output_text)
        matched = resume_skills & required
        missing = required - resume_skills

        bullet_text = " ".join(b.current for b in structured_resume.all_bullets())
        bullet_skills = extract_canonical_skills(bullet_text)
        subtitle_skills: set[str] = set()
        for kind, section in (
            ("project", structured_resume.projects),
            ("experience", structured_resume.experience),
            ("open_source", structured_resume.open_source),
        ):
            for entry in section:
                subtitle_skills.update(extract_canonical_skills(entry.subtitle))

        # Required skills that are authentic (a project tech tag) but not yet
        # visible in any bullet prose - the truthful "surface this" opportunity.
        supported_not_present = sorted(
            skill
            for skill in required
            if skill in subtitle_skills and skill not in bullet_skills
        )

        ats_match = round(len(matched) / len(required) * 100, 2) if required else 0.0

        supported_required = {
            skill
            for skill in required
            if (ev := evidence_for_skill(evidence_map, skill)) is not None and ev.supported
        }
        relevance = round(len(supported_required) / len(required) * 100, 2) if required else 0.0

        strong_required = {
            skill
            for skill in supported_required
            if (ev := evidence_for_skill(evidence_map, skill)) is not None
            and ev.strength in {"project", "experience"}
        }
        strong_coverage = round(len(strong_required) / len(required) * 100, 2) if required else 0.0

        unsupported_claims = find_unsupported_claims(evidence_map, output_text)
        factuality = round(max(0.0, 100.0 - 15.0 * len(unsupported_claims)), 2)

        format_score: float | None = None
        formatting_issues: list[str] = []
        if artifact_path is not None and artifact_path.exists():
            checks = check_pdf_artifact(artifact_path, required_sections=role_kb.get("required_sections"))
            format_score = round(format_score_estimate(checks), 2)
            formatting_issues = checks.get("issues", [])
        else:
            formatting_issues.append("No PDF artifact available to validate layout")

        per_skill = required_evidence_summary(
    evidence_map, sorted(required), output_skills=resume_skills
)

        recommendations = [
            f"Surface '{skill}' into a project bullet (supported by a project "
            "tech stack but not yet visible in the rendered bullet prose)"
            for skill in supported_not_present
        ]

        flags: list[dict[str, str]] = list(unsupported_claims)
        for skill in sorted(missing):
            evidence = evidence_for_skill(evidence_map, skill)
            if evidence is None or not evidence.supported:
                flags.append(
                    {
                        "claim": f"Required skill '{skill}' has no supporting candidate evidence",
                        "severity": "medium",
                    }
                )

        return {
            "ats_match_percent": ats_match,
            "relevance_percent": relevance,
            "strong_coverage_percent": strong_coverage,
            "factuality_score": factuality,
            "format_score": format_score,
            "unsupported_claims": unsupported_claims,
            "flags": flags,
            "formatting_issues": formatting_issues,
            "resume_skills": sorted(resume_skills),
            "matched_skills": sorted(matched),
            "missing_skills": sorted(missing),
            "supported_skills": sorted(supported_required),
            "strong_skills": sorted(strong_required),
            "supported_not_present": supported_not_present,
            "per_skill_status": per_skill,
            "recommendations": recommendations,
        }