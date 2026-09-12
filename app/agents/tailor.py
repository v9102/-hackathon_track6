"""Tailoring agent.

Modifies the **actual** structured resume: it surfaces candidate evidence
(project tech tags) into the most relevant project bullets, and never invents
experience. Every modification is recorded as an explicit action with the
before/after text and the supporting evidence.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from app.agents.revisor import RevisionAgent
from app.core.models import StructuredResume
from app.tools.jdp_parser import extract_skills_from_text, extract_text_from_pdf
from app.tools.skills import (
    CANONICAL_ALIASES,
    extract_canonical_skills,
)


def _contains_skill(text: str, skill: str) -> bool:
    return skill.lower() in text.lower()


def _rewrite_bullet_with_skill(bullet_text: str, skill: str) -> str:
    """Reword a bullet to surface a supported skill truthfully."""
    text = bullet_text.strip().rstrip(".")
    return f"{text} (project tech: {skill})."


def _strip_skill_from_text(text: str, skill: str) -> str:
    """Remove every alias of ``skill`` from ``text`` (whole-token only)."""
    aliases = CANONICAL_ALIASES.get(skill, [skill])
    cleaned = text
    for alias in sorted(aliases, key=len, reverse=True):
        cleaned = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
    # Tidy the damage the removal leaves behind (spaces, double commas).
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"([,.]){2,}", r"\1", cleaned)
    cleaned = re.sub(r"\s*[)(]\s*", " ", cleaned)
    cleaned = re.sub(r"\s*\(\s*\)", " ", cleaned)
    return cleaned.strip()


def tailor_remove_skills(
    resume: StructuredResume,
    skills: set[str],
) -> tuple[StructuredResume, list[dict[str, str]]]:
    """Remove unsupported-skill claims from project/experience bullets.

    This is the truthful alternative to fabricating: when a skill appears in a
    bullet but the candidate's original evidence cannot substantiate it, the
    agent edits it out of the actual bullet text and records the before/after.
    """
    sr: StructuredResume = copy.deepcopy(resume)
    actions: list[dict[str, str]] = []
    for section in sr.all_sections():
        for entry in section:
            for bullet in entry.bullets:
                before = bullet.current
                after_text = before
                removed_here: list[str] = []
                for skill in sorted(skills):
                    candidate_after = _strip_skill_from_text(after_text, skill)
                    if candidate_after != after_text:
                        remaining = extract_canonical_skills(candidate_after)
                        if skill not in remaining:
                            after_text = candidate_after
                            removed_here.append(skill)
                if removed_here and after_text != before:
                    bullet.current = after_text.rstrip(".") + "."
                    actions.append(
                        {
                            "decision": "Remove unsupported claim(s)",
                            "reason": (
                                f"Skills {', '.join(sorted(removed_here))} appear in a "
                                "bullet but the candidate's original resume provides no "
                                "authentic evidence for them."
                            ),
                            "action": "remove_unsupported_claim",
                            "target": ", ".join(sorted(removed_here)),
                            "before": before,
                            "after": bullet.current,
                            "evidence": "none (unsupported claim refused)",
                        }
                    )

    # Strip the unsupported skills from the skills lines too, so the finished
    # artifact no longer asserts them anywhere (keep the line only if others
    # remain).
    cleaned_lines: list[str] = []
    for line in sr.skills_lines:
        line_cleaned = line
        removed_from_line: list[str] = []
        for skill in sorted(skills):
            after_line = _strip_skill_from_text(line_cleaned, skill)
            if after_line != line_cleaned:
                remaining = extract_canonical_skills(after_line)
                if skill not in remaining:
                    line_cleaned = after_line
                    removed_from_line.append(skill)
        if not line_cleaned:
            continue
        if removed_from_line:
            cleaned_lines.append(line_cleaned)
            actions.append(
                {
                    "decision": "Remove unsupported claim(s)",
                    "reason": (
                        f"Skill(s) {', '.join(sorted(removed_from_line))} listed in "
                        "the skills line but unsupported by the candidate's evidence."
                    ),
                    "action": "remove_unsupported_claim",
                    "target": ", ".join(sorted(removed_from_line)),
                    "before": line,
                    "after": line_cleaned,
                    "evidence": "none (unsupported claim refused)",
                }
            )
        else:
            cleaned_lines.append(line)
    sr.skills_lines = cleaned_lines
    return sr, actions


def tailor_surface(
    resume: StructuredResume,
    role_kb: dict[str, Any],
) -> tuple[StructuredResume, list[dict[str, str]]]:
    """Surface supported, subtitle-only skills into the most relevant bullets.

    Only skills that already appear in a project's tech tags are surfaced —
    this is extractive/stylistic, not fabrication. Returns the modified resume
    and a list of applied actions.
    """

    sr: StructuredResume = copy.deepcopy(resume)
    required_skills = set(role_kb.get("required_skills", []))
    actions: list[dict[str, str]] = []

    for skill in sorted(required_skills):
        for entry in sr.projects:
            entry_skills = extract_canonical_skills(entry.subtitle)
            if skill not in entry_skills:
                continue
            for bullet in entry.bullets:
                if _contains_skill(bullet.current, skill):
                    break
            else:
                target = next((b for b in entry.bullets), None)
                if target is None:
                    continue
                before = target.current
                after = _rewrite_bullet_with_skill(target.current, skill)
                target.current = after
                if f"{entry.title} tech stack" not in target.evidence:
                    target.evidence.append(f"{entry.title} tech stack: {entry.subtitle}")
                actions.append(
                    {
                        "decision": f"Surface {skill} evidence into {entry.title}",
                        "reason": (
                            f"{skill} is required by the JD and is part of the "
                            f"'{entry.title}' tech stack ({entry.subtitle})."
                        ),
                        "action": "rewrite_bullet",
                        "target": target.id,
                        "before": before,
                        "after": after,
                        "evidence": entry.subtitle,
                    }
                )
                break
    return sr, actions


def tailor_initial(
    resume: StructuredResume,
    role_kb: dict[str, Any],
) -> tuple[StructuredResume, list[dict[str, str]]]:
    """Run the initial tailoring pass (currently surface-only)."""
    return tailor_surface(resume, role_kb)


class TailorAgent:
    """Compatibility facade for single-resume orchestration.

    Kept so the legacy ``run_pipeline``/``parse_job_description`` interfaces
    (and their tests) keep working; the authoritative path is
    ``app.agents.planner.AgenticPlanner``.
    """

    def __init__(self) -> None:
        self.role_kb: dict[str, Any] | None = None
        self.resume_skills: set[str] = set()
        self.match_score: float = 0.0

    def parse_job_description(self, jd_text: str, title: str = "Unknown Role") -> dict[str, Any]:
        from app.tools.jdp_parser import build_role_kb

        self.role_kb = build_role_kb(title=title, jd_text=jd_text)
        return self.role_kb

    def compute_match_score(self, required_skills: list[str]) -> float:
        """Relevance = matched required skills / total required skills."""
        required = set(required_skills)
        if not required:
            return 0.0
        return len(self.resume_skills & required) / len(required)

    def run_pipeline(
        self,
        jd_text: str,
        resume_path: Any,
        tailored_output: Any,
    ) -> dict[str, Any]:
        """Legacy single-resume pipeline (evaluate + revision log + render)."""
        from app.agents.evaluator import EvaluationAgent
        from app.tools.jdp_parser import build_role_kb

        output = Path(tailored_output)
        output.parent.mkdir(parents=True, exist_ok=True)

        role_kb = build_role_kb(jd_text=jd_text)
        resume_text = extract_text_from_pdf(Path(resume_path))
        self.resume_skills = extract_skills_from_text(resume_text)
        self.match_score = self.compute_match_score(role_kb.get("required_skills", []))

        evaluator = EvaluationAgent()
        evaluation = evaluator.evaluate(resume_text, jd_text)
        revision_log = RevisionAgent().revise(evaluation, 3)

        # "Render": re-evaluate and persist a report artifact.
        evaluator.evaluate(resume_text, jd_text)
        rendered_text = (
            f"Tailoring report for {Path(resume_path).name}\n"
            f"Match score: {self.match_score * 100:.2f}%\n"
            f"ATS match: {evaluation.get('ats_match_percent', 0)}%\n"
            f"Relevance: {evaluation.get('relevance_percent', 0)}%\n"
            f"Factuality: {evaluation.get('factuality_score', 0)}\n"
        )
        output.write_text(rendered_text, encoding="utf-8")

        return {
            "role_kb": role_kb,
            "evaluation": evaluation,
            "revision_log": revision_log,
            "match_score": self.match_score,
            "resume_analysis": {
                "file_path": str(Path(resume_path).resolve()),
                "skills": self.resume_skills,
            },
            "rendered_path": str(output.resolve()),
        }