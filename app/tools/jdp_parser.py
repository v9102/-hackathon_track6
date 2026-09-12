#!/usr/bin/env python3
"""Job Description Parser Tool.

Extracts structured information from job description text or PDFs:
- Required skills
- Preferred skills
- Years of experience
- Degree requirements
- Tools/technologies
- Responsibilities

This tool is designed to be deterministic, reproducible, and testable.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_skills_from_text(text: str) -> set[str]:
    """Extract skill mentions from resume/text."""
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


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using pdftotext."""
    import subprocess
    result = subprocess.run(
        ["pdftotext", str(pdf_path), "-"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ValueError(f"Failed to extract text from PDF: {result.stderr}")
    return result.stdout


def parse_required_skills(jd_text: str) -> list[str]:
    """Extract required skills from JD text."""
    skills: set[str] = set()
    
    # Pattern 1: "Required skills:" section
    if "required skills" in jd_text.lower():
        lower_jd = jd_text.lower()
        idx = lower_jd.find("required skills")
        if idx >= 0:
            after = jd_text[idx + len("required skills"):]
            for trigger in ["nice-to-have", "responsibilities", "education", "experience"]:
                idx2 = after.lower().find(trigger)
                if idx2 >= 0:
                    after = after[:idx2]
                    break
            items = re.split(r"[,;]\s*|\n", after)
            for item in items:
                item = item.strip().rstrip(".,")
                item = item.strip(":|- ")
                if item and len(item) > 1:
                    skills.add(item)
    
    # Pattern 2: Fallback - look for skill patterns in whole text
    common_tech = ["Python", "Java", "Go", "JavaScript", "TypeScript", "React", "Node",
                   "SQL", "Docker", "Kubernetes", "AWS", "Git"]
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", jd_text, re.IGNORECASE):
            skills.add(term)
    
    return sorted(skills)


def parse_preferred_skills(jd_text: str) -> list[str]:
    """Extract preferred/nice-to-have skills from JD text."""
    skills: set[str] = set()
    
    # Pattern 1: "Preferred skills:" section
    if "preferred skills" in jd_text.lower():
        lower_jd = jd_text.lower()
        idx = lower_jd.find("preferred skills")
        if idx >= 0:
            after = jd_text[idx + len("preferred skills"):]
            for trigger in ["nice-to-have", "responsibilities", "education", "experience"]:
                idx2 = after.lower().find(trigger)
                if idx2 >= 0:
                    after = after[:idx2]
                    break
            items = re.split(r"[,;]\s*|\n", after)
            for item in items:
                item = item.strip().rstrip(".,")
                item = item.strip(":|- ")
                if item and len(item) > 1:
                    skills.add(item)
    
    # Pattern 2: "Nice-to-have:" section
    if "nice-to-have" in jd_text.lower():
        idx = jd_text.lower().find("nice-to-have")
        after = jd_text[idx + len("nice-to-have"):]
        for trigger in ["education", "experience"]:
            idx2 = after.lower().find(trigger)
            if idx2 >= 0:
                after = after[:idx2]
        items = re.split(r"[,;]\s*|\n", after)
        for item in items:
            item = item.strip().rstrip(".,")
            item = item.strip(":|- ")
            if item and len(item) > 1:
                skills.add(item)
    
    # Pattern 3: Fallback - look for "Preferred:" patterns anywhere
    if not skills:
        for match in re.finditer(r"(?:Preferred|Nice-to-have|Bonus|Plus)[:\s]+([A-Za-z0-9 .+,&-]+)", jd_text):
            chunk = match.group(1)
            for s in re.split(r"[,;]", chunk):
                s = s.strip().rstrip(".,")
                item = s.strip(":|- ")
                if s and len(s) > 1:
                    skills.add(s)
    return sorted(skills)[:10]


def parse_years_exp(jd_text: str) -> int | None:
    """Extract years of experience requirement."""
    matches = re.findall(
        r"\b(\d+)[\s+]\+?[\s]?years?[:\s]?(?:of\s+)?(?:experience|exp)\b",
        jd_text, re.IGNORECASE,
    )
    if matches:
        return int(matches[0])
    matches = re.findall(r"\b(minimum|at least|required)[\s]+(\d+)[\s]?years\b", jd_text, re.IGNORECASE)
    if matches:
        return int(matches[0][1])
    return None


def parse_degree_req(jd_text: str) -> str | None:
    """Extract degree requirement from JD text."""
    patterns = [
        r"(?:B\.?S?\.?|BA|BS|B\.?Tech|B\.?Eng)(?:\s+(?:required|preferred))?",
        r"(?:M\.?S?\.?|MA|MS|M\.?Tech|M\.?Eng)(?:\s+(?:required|preferred))?",
    ]
    for pattern in patterns:
        match = re.search(pattern, jd_text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def parse_tools_tech(jd_text: str) -> list[str]:
    """Extract tools and technologies mentioned in JD."""
    tech: list[str] = []
    common_tech = [
        "Python", "Java", "Go", "Rust", "TypeScript", "JavaScript", "C++", "C#",
        "React", "Node", "Express", "Next.js", "Angular",
        "PostgreSQL", "MySQL", "MongoDB", "Redis",
        "Docker", "Kubernetes", "AWS", "Azure", "GCP",
        "Git", "GitHub", "GitLab",
        "TensorFlow", "PyTorch", "scikit-learn",
        "Jenkins", "Terraform", "ArgoCD",
    ]
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", jd_text, re.IGNORECASE) and term not in tech:
            tech.append(term)
    return tech


def parse_responsibilities(jd_text: str) -> list[str]:
    """Extract responsibilities from JD text."""
    responsibilities: list[str] = []
    
    # Pattern 1: "Responsibilities:" section
    if "responsibilities" in jd_text.lower():
        lower_jd = jd_text.lower()
        idx = lower_jd.find("responsibilities")
        if idx >= 0:
            after = jd_text[idx + len("responsibilities"):]
            items = re.split(r"[-•*]\s+([A-Za-z .,]{5,150})", after)
            for b in items:
                b = b.strip()
                if b and len(b) > 5:
                    responsibilities.append(b)
    
    # Pattern 2: Fallback - look for responsibility bullets in general text
    if not responsibilities:
        all_bullets = re.findall(r"[-•*]\s+([A-Z][A-Za-z0-9 .,&-]{10,200})", jd_text)
        for b in all_bullets:
            b = b.strip()
            if b and len(b) > 10 and b not in responsibilities:
                responsibilities.append(b)
    
    return responsibilities[:15]


def build_role_kb(
    title: str = "Unknown Role",
    jd_text: str | None = None,
    use_tavily: bool = False,
) -> dict[str, Any]:
    """Build a role knowledge base from JD text."""
    required_skills = parse_required_skills(jd_text or "")
    preferred_skills = parse_preferred_skills(jd_text or "")
    years_exp = parse_years_exp(jd_text or "")
    degree = parse_degree_req(jd_text or "")
    tools = parse_tools_tech(jd_text or "")
    responsibilities = parse_responsibilities(jd_text or "")
    
    red_flags: list[str] = []
    if not required_skills:
        red_flags.append("No required skills detected")
    if not tools:
        red_flags.append("No tools/tech detected")
    if years_exp is None:
        red_flags.append("Years of experience not clearly specified")
    
    role_kb: dict[str, Any] = {
        "title": title,
        "years_exp": years_exp,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "degree": degree,
        "tools": tools,
        "responsibilities": responsibilities,
        "red_flags": red_flags,
    }
    
    return role_kb


def render_tailored_pdf(tailored_text: str, template_path: Path, output_path: Path) -> Path:
    """Render tailored resume as PDF using LaTeX template.
    
    Args:
        tailored_text: The tailored resume content
        template_path: Path to the LaTeX template file
        output_path: Path where PDF should be saved
        
    Returns:
        Path to the generated PDF
    """
    import subprocess
    
    # Read the template
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()
    
    # Replace placeholders with tailored content
    # Find and replace the tailored bullets section
    # For now, just append a Tailoring Modifications section
    tailoring_section = r"""\section{Tailoring Modifications}

\begin{itemize}[leftmargin=*]
\item Resume tailored to emphasize required skills from job description\end{itemize}"""
    
    # Insert the tailoring section before \end{document}
    if r"\end{document}" in template:
        template = template.replace(r"\end{document}", tailoring_section + r"\end{document}")
    
    # Write the modified template to a temporary file
    temp_template = output_path.parent / "temp_template.tex"
    with open(temp_template, 'w', encoding='utf-8') as f:
        f.write(template)
    
    # Compile LaTeX to PDF
    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory=", 
             str(output_path.parent), str(temp_template)],
            capture_output=True,
            text=True,
            timeout=30000,
            check=False,
        )
        pdf_path = output_path.parent / (output_path.stem + ".pdf")
        
        # Clean up temporary files
        for ext in [".aux", ".log", ".toc"]:
            temp_file = Path(str(temp_template).replace(".tex", ext))
            if temp_file.exists():
                temp_file.unlink()
        
        # Clean up any generated PDF in the output directory
        if pdf_path.exists():
            # Remove the old PDF if it exists
            old_pdf = Path(str(output_path))
            if old_pdf.exists():
                old_pdf.unlink()
        
        return pdf_path
    except (OSError, ValueError, TypeError, RuntimeError, AttributeError) as e:
        print(f"LaTeX compilation error: {e}")
        # Fallback: create a simple text file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(tailored_text)
        return output_path
