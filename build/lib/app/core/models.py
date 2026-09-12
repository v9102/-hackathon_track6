"""Structured resume data model for the agentic tailoring system.

The agent operates on this intermediate representation rather than on raw text.
Every bullet carries an id, the original and current text, and the candidate
evidence that supports the claim. Changes made by the agent always operate on
the ``current`` text and are recorded per-bullet so they can be rendered,
evaluated and rolled back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Bullet:
    """An individual resume bullet point."""

    id: str
    original: str
    current: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original": self.original,
            "current": self.current,
            "evidence": self.evidence,
        }


@dataclass
class SectionEntry:
    """A project/experience entry with a title, meta and bullet list."""

    id: str
    title: str
    subtitle: str  # e.g. tech tags or role
    meta: str  # e.g. dates or link
    bullets: list[Bullet] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "meta": self.meta,
            "bullets": [b.to_dict() for b in self.bullets],
        }


@dataclass
class StructuredResume:
    """Intermediate representation of the candidate's resume."""

    name: str = ""
    headline: str = ""
    contact: list[str] = field(default_factory=list)
    summary: str = ""
    education: list[str] = field(default_factory=list)
    skills_lines: list[str] = field(default_factory=list)
    projects: list[SectionEntry] = field(default_factory=list)
    experience: list[SectionEntry] = field(default_factory=list)
    open_source: list[SectionEntry] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
    source_path: str = ""
    source_text: str = ""

    def all_sections(self) -> list[list[SectionEntry]]:
        """Return project-like section lists in a fixed display order."""
        return [self.projects, self.experience, self.open_source]

    def all_bullets(self) -> list[Bullet]:
        """Flatten every bullet across project-like sections."""
        bullets: list[Bullet] = []
        for section in self.all_sections():
            for entry in section:
                bullets.extend(entry.bullets)
        return bullets

    def full_text(self) -> str:
        """Render a plain-text version (used for keyword evaluation)."""
        parts: list[str] = [self.name, self.headline]
        if self.summary:
            parts.append(self.summary)
        if self.skills_lines:
            parts.extend(self.skills_lines)
        if self.education:
            parts.extend(self.education)
        for section in self.all_sections():
            for entry in section:
                parts.append(entry.title)
                parts.append(entry.subtitle)
                for bullet in entry.bullets:
                    parts.append(bullet.current)
        if self.achievements:
            parts.extend(self.achievements)
        return "\n".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "headline": self.headline,
            "contact": self.contact,
            "summary": self.summary,
            "education": self.education,
            "skills_lines": self.skills_lines,
            "projects": [e.to_dict() for e in self.projects],
            "experience": [e.to_dict() for e in self.experience],
            "open_source": [e.to_dict() for e in self.open_source],
            "achievements": self.achievements,
            "source_path": self.source_path,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> StructuredResume:
        def _bullet(raw: dict[str, Any]) -> Bullet:
            return Bullet(
                id=str(raw.get("id", "")),
                original=str(raw.get("original", "")),
                current=str(raw.get("current", "")),
                evidence=[str(x) for x in raw.get("evidence", [])],
            )

        def _entry(section: str, raw: dict[str, Any]) -> SectionEntry:
            return SectionEntry(
                id=f"{section}_{raw.get('id', '')}",
                title=str(raw.get("title", "")),
                subtitle=str(raw.get("subtitle", "")),
                meta=str(raw.get("meta", "")),
                bullets=[_bullet(b) for b in raw.get("bullets", [])],
            )

        resume = cls(
            name=str(payload.get("name", "")),
            headline=str(payload.get("headline", "")),
            contact=[str(x) for x in payload.get("contact", [])],
            summary=str(payload.get("summary", "")),
            education=[str(x) for x in payload.get("education", [])],
            skills_lines=[str(x) for x in payload.get("skills_lines", [])],
            achievements=[str(x) for x in payload.get("achievements", [])],
            source_path=str(payload.get("source_path", "")),
        )
        resume.projects = [_entry("project", e) for e in payload.get("projects", [])]
        resume.experience = [_entry("experience", e) for e in payload.get("experience", [])]
        resume.open_source = [_entry("open_source", e) for e in payload.get("open_source", [])]
        return resume