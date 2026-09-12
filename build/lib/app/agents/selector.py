"""Resume selection agent.

Given a parsed JD role KB and every candidate resume, the selector extracts
requirements, inspects all candidate resumes, scores each against the JD and
picks the best one. Scores + reasoning are stored so the decision is auditable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.models import StructuredResume
from app.core.state import ResumeCandidate
from app.tools.skills import (
    canonicalize_list,
    extract_canonical_skills,
    normalize_skill,
)


def _evidence_depth(resume: StructuredResume, required_skills: set[str]) -> int:
    """Count bullets that reference at least one required skill."""
    count = 0
    for bullet in resume.all_bullets():
        skills_in_bullet = extract_canonical_skills(bullet.original)
        if skills_in_bullet & required_skills:
            count += 1
    return count


class ResumeSelector:
    """Scores and selects the best candidate resume for a JD."""

    def score_resume(
        self,
        resume: StructuredResume,
        role_kb: dict[str, Any],
        preferred_weight: float = 0.25,
        depth_weight: float = 0.15,
    ) -> tuple[float, dict[str, Any]]:
        """Return (score, breakdown) for one resume against the role KB."""
        required = canonicalize_list(role_kb.get("required_skills", []))
        preferred = canonicalize_list(role_kb.get("preferred_skills", []))

        if not required:
            return 0.0, {"reason": "JD has no required skills"}

        resume_skills = extract_canonical_skills(resume.full_text())
        matched_req = resume_skills & required
        required_hit = len(matched_req) / len(required)

        preferred_hit = 0.0
        if preferred:
            preferred_hit = len(resume_skills & preferred) / len(preferred)

        depth = _evidence_depth(resume, required)
        depth_norm = min(depth / 3.0, 1.0)

        score = 100.0 * (
            (1.0 - preferred_weight - depth_weight) * required_hit
            + preferred_weight * preferred_hit
            + depth_weight * depth_norm
        )

        breakdown = {
            "required_skills": sorted(required),
            "matched_required": sorted(matched_req),
            "required_hit_ratio": round(required_hit, 3),
            "preferred_hit_ratio": round(preferred_hit, 3),
            "evidence_depth": depth,
            "score": round(score, 2),
        }
        return round(score, 2), breakdown

    def reasoning_text(
        self, name: str, score: float, breakdown: dict[str, Any]
    ) -> str:
        req_total = len(breakdown.get("required_skills", []))
        matched = breakdown.get("matched_required", [])
        return (
            f"Score {score:.1f}/100: matches {len(matched)}/{req_total} required "
            f"skills ({', '.join(matched) if matched else 'none'}) with "
            f"{breakdown.get('evidence_depth', 0)} evidence bullets referencing them."
        )

    def select(
        self,
        role_kb: dict[str, Any],
        structured_resumes: list[StructuredResume],
    ) -> list[ResumeCandidate]:
        """Score all resumes and return candidates sorted best-first."""
        candidates: list[ResumeCandidate] = []
        for resume in structured_resumes:
            if not resume.name:
                continue
            score, breakdown = self.score_resume(resume, role_kb)
            skills = extract_canonical_skills(resume.full_text())
            candidates.append(
                ResumeCandidate(
                    name=resume.name,
                    path=resume.source_path,
                    full_text=resume.source_text,
                    skills=skills,
                    selection_score=score,
                    evidence_count=_evidence_depth(resume, canonicalize_list(role_kb.get("required_skills", []))),
                    reasoning=self.reasoning_text(resume.name, score, breakdown),
                )
            )
        candidates.sort(key=lambda c: c.selection_score, reverse=True)
        return candidates

    def select_best(
        self,
        role_kb: dict[str, Any],
        structured_resumes: list[StructuredResume],
    ) -> ResumeCandidate:
        candidates = self.select(role_kb, structured_resumes)
        if not candidates:
            raise ValueError("No candidate resumes available for selection")
        return candidates[0]


def load_candidate_resumes(resume_files: list[Path]) -> list[StructuredResume]:
    """Parse every candidate resume PDF into a structured resume."""
    from app.tools.resume_parser import parse_resume_pdf

    resumes: list[StructuredResume] = []
    for pdf in resume_files:
        if not pdf.exists():
            continue
        try:
            resumes.append(parse_resume_pdf(pdf, source_path=str(pdf)))
        except (OSError, ValueError, Exception):  # noqa: BLE001, S112 - skip unreadable
            continue
    return [r for r in resumes if normalize_skill(r.name)]