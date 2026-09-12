"""Render the structured resume to LaTeX and compile it to a real PDF.

Reuses the existing LaTeX template preamble (``ShaunakMishra_Resume.tex``) so
the generated artifact matches the project's provided format, then validates
the produced PDF (exists, non-empty, readable, expected sections present).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.models import SectionEntry, StructuredResume

_UNICODE_TO_TEX: dict[str, str] = {
    "\u2014": "---",         # em dash
    "\u2013": "--",          # en dash
    "\u2192": "$\\rightarrow$",
    "\u00b7": "$\\cdot$",
    "\u00b0": "$^{\\circ}$",
    "\u03bc": "$\\mu$",
    "\u2248": "$\\approx$",
    "\u223c": "$\\sim$",
    "\u2264": "$\\leq$",
    "\u2265": "$\\geq$",
    "\u00b1": "$\\pm$",
    "\u2022": "*",
    "\u25e6": "*",
}

_SPECIALS: dict[str, str] = {
    "\\": "\\textbackslash{}",
    "%": "\\%",
    "&": "\\&",
    "#": "\\#",
    "_": "\\_",
    "$": "\\$",
    "{": "\\{",
    "}": "\\}",
    "^": "\\^{}",
    "~": "$\\sim$",
}


def tex_escape(text: str) -> str:
    """Escape text so it is safe inside a LaTeX body."""
    out: list[str] = []
    for ch in text:
        if ch in _UNICODE_TO_TEX:
            out.append(_UNICODE_TO_TEX[ch])
        elif ch in _SPECIALS:
            out.append(_SPECIALS[ch])
        else:
            out.append(ch)
    return "".join(out)


def _preamble(template_path: Path | None = None) -> str:
    """Extract the preamble from the provided LaTeX template."""
    path = template_path or settings.default_template_path
    if path.exists():
        text = path.read_text(encoding="utf-8")
        marker = "\\begin{document}"
        idx = text.find(marker)
        if idx >= 0:
            return text[:idx]
    # Fallback minimal preamble mirroring the provided template format.
    return """\\documentclass[letterpaper,10.5pt]{article}
\\usepackage[margin=0.5in]{geometry}
\\usepackage{titlesec}
\\usepackage{enumitem}
\\usepackage[pdftex]{hyperref}
\\usepackage{fancyhdr}
\\pagestyle{fancy}
\\fancyhf{}
\\renewcommand{\\headrulewidth}{0pt}
\\addtolength{\\oddsidemargin}{-0.375in}
\\addtolength{\\textwidth}{1in}
\\addtolength{\\topmargin}{-0.7in}
\\addtolength{\\textheight}{1.45in}
\\raggedbottom
\\raggedright
\\titleformat{\\section}{\\vspace{-8pt}\\scshape\\large}{}{0em}{}[\\titlerule \\vspace{-7pt}]
\\newcommand{\\resumeSubheading}[5]{
\\vspace{-2pt}\\item
\\begin{tabular*}{0.97\\textwidth}{@{}l@{\\extracolsep{\\fill}}r@{}}
\\textbf{#1} & \\textit{\\small #5} \\\\
\\textit{\\small #3} & \\textit{\\small #4} \\\\
\\end{tabular*}\\vspace{-7pt}
}
\\newcommand{\\resumeSubHeadingListStart}{\\begin{itemize}[leftmargin=*, label=$\\bullet$, itemsep=0pt, topsep=1pt]}
\\newcommand{\\resumeSubHeadingListEnd}{\\end{itemize}}
\\newcommand{\\resumeItemListStart}{\\begin{itemize}[leftmargin=*, label=$\\circ$, itemsep=0pt, topsep=1pt]}
\\newcommand{\\resumeItemListEnd}{\\end{itemize}\\vspace{-6pt}}
"""


_YEAR_RE = re.compile(r"\b(?:20\d{2}|19\d{2})\b|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}")


def _entry_meta_split(meta: str, subtitle: str) -> tuple[str, str]:
    """Split a SectionEntry meta into (year_part, link_part)."""
    year_match = _YEAR_RE.search(meta)
    year_part = year_match.group(0) if year_match else ""
    link_part = meta
    if year_match:
        link_part = (meta[: year_match.start()] + meta[year_match.end():]).strip(" |")
    if not link_part and subtitle:
        link_part = ""
    return year_part, link_part


def _render_entry(entry: SectionEntry, section_key: str) -> str:
    year_part, link_part = _entry_meta_split(entry.meta, entry.subtitle)
    lines: list[str] = []
    lines.append("\\resumeSubheading")
    lines.append("{" + tex_escape(entry.title) + "}{}")
    lines.append("{}{" + tex_escape(entry.subtitle) + "}{" + tex_escape(year_part) + "}")
    lines.append("{" + tex_escape(link_part) + "}" if link_part else "{}")
    lines.append("\\resumeItemListStart")
    for bullet in entry.bullets:
        lines.append("\\item " + tex_escape(bullet.current))
    lines.append("\\resumeItemListEnd")
    return "\n".join(lines)


def _render_section_list(label: str, entries: list[SectionEntry], section_key: str) -> str:
    if not entries:
        return ""
    out = [f"\\section{{{label}}}", "\\resumeSubHeadingListStart"]
    for entry in entries:
        out.append(_render_entry(entry, section_key))
    out.append("\\resumeSubHeadingListEnd")
    out.append("\\vspace{-6pt}")
    return "\n".join(out)


def render_latex(resume: StructuredResume, template_path: Path | None = None) -> str:
    """Generate complete LaTeX source for a structured resume."""
    parts: list[str] = [_preamble(template_path), "\\begin{document}"]

    # --- Heading ---
    contact_line = " $|$ ".join(tex_escape(c) for c in resume.contact)
    heading = [
        "\\begin{center}",
        "{\\Large \\textbf{" + tex_escape(resume.name) + "}}\\\\[3pt]",
    ]
    if resume.headline:
        heading.append("{\\small " + tex_escape(resume.headline) + "}\\\\[3pt]")
    if contact_line:
        heading.append("\\small " + contact_line)
    heading.append("\\end{center}")
    heading.append("\\vspace{-6pt}")
    parts.append("\n".join(heading))

    # --- Summary ---
    if resume.summary:
        parts.append(
            "\\section{Career Summary}\n"
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
            "  \\small{\\item{" + tex_escape(resume.summary) + "}}\n"
            "\\end{itemize}\n\\vspace{-14pt}"
        )

    # --- Education ---
    if resume.education:
        edu_items = " \\\\ ".join(tex_escape(e) for e in resume.education)
        parts.append(
            "\\section{Education}\n"
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
            "  \\small{\\item{" + edu_items + "}}\n"
            "\\end{itemize}\n\\vspace{-14pt}"
        )

    # --- Skills ---
    if resume.skills_lines:
        skills_body = " \\\\ ".join(tex_escape(s) for s in resume.skills_lines)
        parts.append(
            "\\section{Skills}\n"
            "\\begin{itemize}[leftmargin=0.15in, label={}]\n"
            "  \\small{\\item{" + skills_body + "}}\n"
            "\\end{itemize}\n\\vspace{-14pt}"
        )

    # --- Projects / Experience / Open Source ---
    parts.append(_render_section_list("Projects", resume.projects, "project"))
    parts.append(_render_section_list("Experience", resume.experience, "experience"))
    parts.append(_render_section_list("Open Source", resume.open_source, "open_source"))

    # --- Achievements ---
    if resume.achievements:
        ach_items = "\n".join("\\item " + tex_escape(a) for a in resume.achievements)
        parts.append(
            "\\section{Achievements}\n"
            "\\resumeItemListStart\n" + ach_items + "\n\\resumeItemListEnd"
        )

    parts.append("\\end{document}")
    return "\n".join(parts)


def compile_tex(tex_path: Path, output_pdf: Path) -> Path:
    """Compile ``tex_path`` into ``output_pdf`` using pdflatex.

    Returns the path to the produced PDF. Raises ``RuntimeError`` when the
    compile fails or no PDF is produced.
    """
    out_dir = output_pdf.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    jobname = output_pdf.stem
    tex_path = tex_path.resolve()
    command = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-jobname={jobname}",
        f"-output-directory={out_dir}",
        str(tex_path),
    ]
    for _ in range(2):  # second pass resolves references
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if "Fatal error" in result.stdout or "Emergency stop" in result.stdout:
            break
    pdf_candidate = out_dir / f"{jobname}.pdf"
    if not pdf_candidate.exists():
        raise RuntimeError(
            "pdflatex did not produce a PDF. "
            f"Check: {tex_path} (log: {tex_path.with_suffix('.log')})"
        )
    # Ensure final name matches the requested path exactly.
    if pdf_candidate != output_pdf:
        output_pdf.unlink(missing_ok=True)
        pdf_candidate.rename(output_pdf)
    return output_pdf


def render_pdf(
    resume: StructuredResume,
    output_pdf: Path,
    template_path: Path | None = None,
) -> Path:
    """Render a structured resume directly to a PDF artifact."""
    tex_path = output_pdf.with_suffix(".tex")
    source = render_latex(resume, template_path)
    tex_path.write_text(source, encoding="utf-8")
    return compile_tex(tex_path, output_pdf)


# --------------------------------------------------------------------------- #
# PDF validation
# --------------------------------------------------------------------------- #
def check_pdf_artifact(pdf_path: Path, required_sections: list[str] | None = None) -> dict[str, Any]:
    """Validate that ``pdf_path`` is a real, readable resume PDF."""
    required_sections = required_sections or ["Projects", "Skills", "Education"]
    issues: list[str] = []
    checks: dict[str, Any] = {"exists": pdf_path.exists()}

    if not pdf_path.exists():
        issues.append("PDF file does not exist")
        checks.update({"readable": False, "page_count": 0, "text_length": 0, "sections": [], "valid": False})
        checks["issues"] = issues
        return checks

    size = pdf_path.stat().st_size
    checks["size_bytes"] = size
    if size < 1000:
        issues.append("PDF looks empty or too small")

    from app.tools.jdp_parser import extract_text_from_pdf
    try:
        text = extract_text_from_pdf(pdf_path)
    except (OSError, ValueError, Exception) as e:  # noqa: BLE001 - defensive
        text = ""
        issues.append(f"PDF text extraction failed: {e}")
    checks["readable"] = bool(text.strip())
    checks["text_length"] = len(text.strip())
    if not text.strip():
        issues.append("PDF text is empty/unreadable")

    present = [s for s in required_sections if re.search(rf"\b{re.escape(s)}\b", text, re.IGNORECASE)]
    checks["sections"] = present
    missing_sections = [s for s in required_sections if s not in present]
    if missing_sections:
        issues.append(f"Missing sections: {', '.join(missing_sections)}")

    checks["issues"] = issues
    checks["valid"] = not issues
    return checks


def format_score_estimate(checks: dict[str, Any]) -> float:
    """Derive a 0-100 formatting score from PDF validation checks."""
    score = 100.0
    if not checks.get("exists"):
        return 0.0
    if not checks.get("readable"):
        score -= 50
    checks_len = checks.get("text_length", 0)
    if checks_len < 500:
        score -= 30
    elif checks_len < 1000:
        score -= 10
    n_sections = len(checks.get("sections", []))
    if n_sections < 3:
        score -= 15 * (3 - n_sections)
    issues = checks.get("issues", [])
    score -= 5 * len(issues)
    return round(max(0.0, min(100.0, score)), 2)