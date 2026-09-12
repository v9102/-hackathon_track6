"""Parse extracted resume text into the structured intermediate representation.

The agent therefore works on ``StructuredResume`` objects rather than raw text,
which lets it modify individual bullets and re-render.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.models import Bullet, SectionEntry, StructuredResume

_SECTION_ALIASES: dict[str, list[str]] = {
    "summary": ["career summary", "summary", "profile", "about"],
    "education": ["education", "academic"],
    "skills": ["skills", "technical skills", "skills & tools"],
    "projects": ["projects", "project", "personal projects"],
    "experience": ["experience", "work experience", "professional experience"],
    "open_source": ["open source", "open-source", "oss"],
    "achievements": ["achievements", "achievement", "accomplishments", "certifications"],
}

_BULLET_RE = re.compile(r"^\s*(?:[•◦\*▪–—-]|\d+[.)])\s+(.+)$")

# Standalone bullet glyphs produced by pdftotext layout (no text content).
_STRAY_MARKERS = {"•", "◦", "▪", "*", "-", "–", "—", ".", "o", "o."}

_DASH_RE = re.compile("[\u2014\u2013-]")  # em dash, en dash, hyphen
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_DATE_RE = re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b")


def _is_linkish(line: str) -> bool:
    """A lone link/availability line (never a tech subtitle)."""
    stripped = line.strip().strip("()").strip()
    if stripped.lower() in {"github", "gitlab", "bitbucket", "live", "repo", "code"}:
        return True
    if stripped.lower().startswith("live ") and len(stripped) < 25:
        return True
    stripped2 = stripped.upper()
    return bool(
        re.fullmatch(
            r"(?:GITHUB|GITLAB|LIVE)\s*[\u2014\u2013-]\s*(?:REPO|GITHUB|LIVE)",
            stripped2,
        )
    )


_ROLE_WORDS = {
    "engineer", "developer", "designer", "intern", "manager", "analyst",
    "consultant", "architect", "researcher", "scientist", "lead", "head",
    "owner", "specialist", "associate", "coordinator",
}


def _heading_kind(line: str) -> str | None:
    """Classify a non-bullet line that follows bullets.

    Returns a category used to decide whether it starts a NEW entry or is a
    wrapped continuation of the previous bullet: ``dash``/``role``/``link`` are
    unambiguous entry starts; ``date``/``year``/``short`` are only boundaries
    when the previous bullet ended a sentence.
    """
    if not line:
        return None
    stripped = line.strip()
    if not stripped:
        return None
    if not stripped[0].isupper():
        return None
    if _DASH_RE.search(stripped) and not _DATE_RE.search(stripped):
        return "dash"
    if _DATE_RE.search(stripped):
        return "date"
    if _YEAR_RE.fullmatch(stripped):
        return "year"
    if _is_linkish(stripped):
        return "link"
    words = stripped.split()
    if (
        len(words) <= 3
        and not stripped.rstrip().endswith(";")
        and not _skill_tokens(stripped)
    ):
        last = words[-1].rstrip(".,").lower()
        if last in _ROLE_WORDS:
            return "role"
        return "short"
    return None


def _parse_entries(section_key: str, lines: list[str]) -> list[SectionEntry]:
    """Turn raw lines of a project-like section into entries.

    pdftotext output renders each entry as a run of *info* lines (title, tech
    stack, link, dates) followed by its ``\\circ`` bullets. Long bullets wrap
    onto multiple lines that begin mid-sentence and are indented. A new entry
    begins when a heading-like line appears AFTER the current entry has already
    accumulated bullets; wrapped bullet continuations are merged into the last
    bullet instead.
    """
    entries: list[SectionEntry] = []
    info: list[str] = []
    bullets: list[str] = []

    def flush() -> None:
        if not info and not bullets:
            return
        title = info[0] if info else ""
        subtitle, meta = _pick_subtitle(info[1:])
        bullet_objs = [
            Bullet(id=f"{section_key}_{len(entries)}_{idx}", original=b, current=b)
            for idx, b in enumerate(bullets)
        ]
        entries.append(
            SectionEntry(
                id=f"{section_key}_{len(entries)}",
                title=title,
                subtitle=subtitle,
                meta=meta,
                bullets=bullet_objs,
            )
        )
        info.clear()
        bullets.clear()

    for raw in lines:
        line = raw.strip()
        if not line or line in _STRAY_MARKERS:
            continue
        m = _BULLET_RE.match(raw)
        if m:
            if info or bullets:
                bullets.append(m.group(1).strip())
            continue
        if bullets:
            heading = _heading_kind(line)
            prev_ends = bullets[-1].rstrip().endswith((".", ":", ";", "!", "?"))
            if heading and (prev_ends or heading in {"dash", "role", "link"}):
                flush()
                info.append(line)
            else:
                # Wrapped continuation of the previous bullet (mid-sentence).
                bullets[-1] = bullets[-1] + " " + line
        else:
            info.append(line)
    flush()
    return entries


def _skill_tokens(line: str) -> int:
    """Rough count of canonical technology tokens in an info line."""
    from app.tools.skills import CANONICAL_ALIASES

    lowered = line.lower()
    return sum(1 for name in CANONICAL_ALIASES if name.lower() in lowered)


def _pick_subtitle(info: list[str]) -> tuple[str, str]:
    """Choose the tech-stack subtitle line; everything else becomes meta.

    A lone link/date line is never the subtitle. When no line carries real
    technology tokens, prefer a dashed company/organisation line and otherwise
    fall back to the first info line (preserving the engineered sample format).
    """

    def score(line: str) -> int:
        if _is_linkish(line):
            return 0
        return _skill_tokens(line)

    if not info:
        return "", ""

    scored = [(idx, score(line)) for idx, line in enumerate(info)]
    best_idx, best_score = max(scored, key=lambda s: (s[1], -s[0]))
    if best_score == 0:
        # No genuine tech line: use the first non-linkish, dashed line if any.
        for i, line in enumerate(info):
            if _DASH_RE.search(line) and not _is_linkish(line):
                return line, " | ".join(x for j, x in enumerate(info) if j != i)
        return info[0], " | ".join(info[1:])
    subtitle = info[best_idx]
    meta = " | ".join(line for i, line in enumerate(info) if i != best_idx)
    return subtitle, meta


def _split_header_content(line: str) -> tuple[str | None, str]:
    """Split 'Skills: Python, React' into (key, 'Python, React') else (None,'')."""
    lower = line.strip().lower()
    for key, aliases in _SECTION_ALIASES.items():
        for alias in aliases:
            if lower.startswith(alias + ":"):
                rest = line.strip()[len(alias) + 1:].strip()
                return key, rest
    return None, ""


def _is_section_header(line: str) -> str | None:
    """Return normalized section key when ``line`` is a section header."""
    lower = re.sub(r"[:\s]+$", "", line.strip().lower())
    for key, aliases in _SECTION_ALIASES.items():
        if lower in aliases:
            return key
    # Inline section header with content on the same line ("Skills: ...").
    inline_key, _ = _split_header_content(line)
    if inline_key is not None:
        return inline_key
    # UPPERCASE headers (e.g. 'PROJECTS', 'EXPERIENCE')
    upper = line.strip().upper().lower()
    for key, aliases in _SECTION_ALIASES.items():
        if any(a == upper for a in aliases):
            return key
    return None


def _split_blocks(lines: list[str]) -> list[list[str]]:
    """Split a flat line list into blocks separated by blank lines."""
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        else:
            if current:
                blocks.append(current)
                current = []
    if current:
        blocks.append(current)
    return blocks


def parse_resume_text(text: str, source_path: str = "") -> StructuredResume:
    """Build a ``StructuredResume`` from plain extracted resume text."""
    raw_lines = [ln.rstrip("\r") for ln in text.splitlines()]
    lines = [ln.rstrip("\n") for ln in raw_lines]

    sections: dict[str, list[str]] = {
        "summary": [], "education": [], "skills": [], "projects": [],
        "experience": [], "open_source": [], "achievements": [],
    }
    header: list[str] = []
    current: str | None = None

    for line in lines:
        if not line.strip():
            continue
        key = _is_section_header(line)
        if key is not None:
            current = key
            _, inline = _split_header_content(line)
            if inline:
                sections[current].append(inline)
            continue
        if current is None:
            header.append(line.strip())
        elif current in sections:
            sections[current].append(line.strip())

    name = header[0] if header else ""
    headline = header[1] if len(header) > 1 else ""
    contact = header[2:] if len(header) > 2 else []

    education_blocks = _split_blocks(sections["education"])
    education_lines = [
        " | ".join(blk) for blk in education_blocks
    ]

    resume = StructuredResume(
        name=name,
        headline=headline,
        contact=contact,
        summary=" ".join(sections["summary"]),
        education=education_lines,
        skills_lines=sections["skills"],
        achievements=sections["achievements"],
        source_path=source_path,
        source_text=text,
    )
    resume.projects = _parse_entries("project", sections["projects"])
    resume.experience = _parse_entries("experience", sections["experience"])
    resume.open_source = _parse_entries("open_source", sections["open_source"])

    # Cleanup: drop empty education.
    resume.education = [e for e in resume.education if e.strip()]

    return resume


def parse_resume_pdf(pdf_path: Any, source_path: str = "") -> StructuredResume:
    """Extract text from a resume PDF and parse it into a structured resume."""
    from app.tools.jdp_parser import extract_text_from_pdf

    text = extract_text_from_pdf(pdf_path)
    return parse_resume_text(text, source_path=str(source_path or pdf_path))