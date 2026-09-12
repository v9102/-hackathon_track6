"""Candidate evidence layer.

Separates what the agent can actually support from what it cannot:

- **Supported** — a skill that appears in the candidate's own artifact,
  ideally inside a project/experience bullet (strong) or the skills list
  (declared).
- **Required** — a skill requested by the JD (from the role KB).
- **Unsupported claim** — a skill present in the *output* resume that has no
  supporting mention in the candidate's *original* evidence.

Absence of a skill in *another* candidate's resume is NOT treated as evidence
of falsity. Only the candidate's own evidence matters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import StructuredResume
from app.tools.skills import extract_canonical_skills, normalize_skill


@dataclass
class SkillEvidence:
    """Evidence collected for one canonical skill."""

    skill: str
    supported: bool
    sources: list[str] = field(default_factory=list)
    strength: str = "missing"  # "project" | "experience" | "skills_section" | "headline" | "missing"

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill,
            "supported": self.supported,
            "sources": self.sources,
            "strength": self.strength,
        }


def _project_like_evidence(resume: StructuredResume) -> list[tuple[str, str, str]]:
    """Return (section_kind, entry_title, bullet_text) triples."""
    out: list[tuple[str, str, str]] = []
    for kind, section in (
        ("project", resume.projects),
        ("experience", resume.experience),
        ("open_source", resume.open_source),
    ):
        for entry in section:
            for bullet in entry.bullets:
                out.append((kind, entry.title, bullet.original))
    return out


def build_evidence_map(resume: StructuredResume) -> dict[str, SkillEvidence]:
    """Build an evidence map from a structured resume.

    The skill canonical names are used as keys and values carry the sources
    (project/experience bullet or skills-section line) that substantiate the
    claim together with an evidence strength.
    """
    from app.tools.skills import CANONICAL_ALIASES

    evidence_map: dict[str, SkillEvidence] = {}
    project_bullets = _project_like_evidence(resume)

    for skill in CANONICAL_ALIASES:
        evidence_map[skill] = SkillEvidence(skill=skill, supported=False)

    # 1) Strongest evidence first: bullets in projects/experience/open source
    #    plus the project's own tech-stack subtitle (the candidate stated it).
    for kind, title, bullet in project_bullets:
        found_skills = extract_canonical_skills(bullet)
        for skill in found_skills:
            ev = evidence_map.setdefault(
                skill, SkillEvidence(skill=skill, supported=False)
            )
            ev.supported = True
            snippet = f"{title} ({kind})"
            if snippet not in ev.sources:
                ev.sources.append(snippet)
            if ev.strength == "missing":
                ev.strength = kind if kind in {"project", "experience"} else "experience"

    for kind, section in (
        ("project", resume.projects),
        ("experience", resume.experience),
        ("open_source", resume.open_source),
    ):
        for entry in section:
            found_skills = extract_canonical_skills(entry.subtitle)
            for skill in found_skills:
                ev = evidence_map.setdefault(
                    skill, SkillEvidence(skill=skill, supported=False)
                )
                ev.supported = True
                snippet = f"{entry.title} tech stack ({kind})"
                if snippet not in ev.sources:
                    ev.sources.append(snippet)
                if ev.strength == "missing":
                    ev.strength = kind if kind in {"project", "experience"} else "experience"

    # 2) Declared in the skills section (weaker, still supported).
    for line in resume.skills_lines:
        found_skills = extract_canonical_skills(line)
        for skill in found_skills:
            ev = evidence_map.setdefault(
                skill, SkillEvidence(skill=skill, supported=False)
            )
            ev.supported = True
            if "Skills section" not in ev.sources:
                ev.sources.append("Skills section")
            if ev.strength == "missing":
                ev.strength = "skills_section"

    # 3) Declared in the headline/summary (weakest support).
    for text in [resume.headline, resume.summary]:
        found_skills = extract_canonical_skills(text)
        for skill in found_skills:
            ev = evidence_map.setdefault(
                skill, SkillEvidence(skill=skill, supported=False)
            )
            ev.supported = True
            if "headline/summary" not in ev.sources:
                ev.sources.append("headline/summary")
            if ev.strength == "missing":
                ev.strength = "headline"

    # Remove entries with no support at all.
    return {k: v for k, v in evidence_map.items() if v.supported}


def evidence_for_skill(evidence_map: dict[str, SkillEvidence], skill: str) -> SkillEvidence | None:
    return evidence_map.get(normalize_skill(skill))


def required_evidence_summary(
    evidence_map: dict[str, SkillEvidence],
    required_skills: list[str],
    output_skills: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Summarize, per required skill, support status and sources.

    Verdict classification per skill:
    - ``supported`` — the candidate's own evidence substantiates the skill.
    - ``unsupported`` — the skill appears in the rendered output but the
      candidate's original evidence contains no authentic mention of it.
    - ``unknown`` — no evidence either way: the skill is required by the JD
      but is neither evidenced by the candidate nor present in the output.
    """
    output_skills = output_skills or set()
    summary: dict[str, dict[str, Any]] = {}
    for raw in required_skills:
        canonical = normalize_skill(raw)
        ev = evidence_for_skill(evidence_map, canonical)
        if ev is not None and ev.supported:
            classification = "supported"
        elif canonical in output_skills:
            classification = "unsupported"
        else:
            classification = "unknown"
        summary[canonical] = {
            "required": True,
            "matched": ev is not None,
            "supported": ev.supported if ev else False,
            "classification": classification,
            "strength": ev.strength if ev else "missing",
            "sources": ev.sources if ev else [],
        }
    return summary


def find_unsupported_claims(
    evidence_map: dict[str, SkillEvidence],
    output_text: str,
) -> list[dict[str, str]]:
    """Claims in ``output_text`` that the candidate evidence cannot support.

    A claim is unsupported when a skill appears in the output resume but the
    candidate's original evidence contains no mention of it.
    """
    claims: list[dict[str, str]] = []
    output_skills = extract_canonical_skills(output_text)
    ev_skills = {k for k, e in evidence_map.items() if e.supported}
    for skill in sorted(output_skills):
        if skill not in ev_skills:
            claims.append(
                {
                    "claim": f"Skill '{skill}' present in output but not substantiated "
                    "by candidate evidence",
                    "severity": "high",
                }
            )
    return claims


def skills_with_strong_evidence(
    evidence_map: dict[str, SkillEvidence], skills: list[str]
) -> list[str]:
    """Required skills that are supported at project or experience strength."""
    out: list[str] = []
    for raw in skills:
        ev = evidence_for_skill(evidence_map, raw)
        if ev and ev.strength in {"project", "experience"}:
            out.append(ev.skill)
    return out