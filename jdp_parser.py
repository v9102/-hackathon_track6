#!/usr/bin/env python3
"""Job Description Parser - extracts role requirements from JD text or PDF."""

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
    """Extract text from a PDF file using pdftotext."""
    import subprocess
    result = subprocess.run([
        "pdftotext", str(pdf_path), "-"
    ], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ValueError(f"Failed to extract text from PDF: {result.stderr}")
    return result.stdout


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from a file (PDF or plain text)."""
    if file_path.suffix.lower() == ".pdf":
        return extract_text_from_pdf(file_path)
    else:
        return file_path.read_text(encoding="utf-8")


def _find_marker_positions(text: str) -> dict[str, int]:
    """Find the start position of each section marker in the JD text."""
    markers = [
        "required skills", "preferred skills", "nice-to-have",
        "responsibilities", "education", "experience", "tools"
    ]
    positions: dict[str, int] = {}
    for marker in markers:
        m = re.search(rf'{re.escape(marker)}[:\n]', text, re.IGNORECASE)
        if m:
            positions[marker] = m.start()
    return positions


def parse_required_skills(jd_text: str) -> list[str]:
    """Extract required skills from JD text."""
    positions = _find_marker_positions(jd_text)
    req_start = positions.get("required skills", 0)
    pre_start = positions.get("preferred skills", len(jd_text))
    
    if req_start >= len(jd_text) or pre_start <= req_start:
        return []
    
    section_text = jd_text[req_start:pre_start]
    # Remove the "Required skills:" marker
    section_text = re.sub(r'(?i)required skills[:\n]\s*', '', section_text).strip()
    
    skills: set[str] = set()
    # Split by common delimiters
    items = re.split(r"[,;]\s*|\n", section_text)
    excluded = {"and", "or", "but", "nor", "for", "yet", "so", "as", "if", "until",
                "while", "of", "to", "in", "on", "by", "at", "from", "up", "about",
                "into", "over", "through", "after", "beneath", "under", "above",
                "below", "between", "during", "before", "since", "without", "against", "among", "around", "throughout",
                "despite", "towards", "upon", "via", "vs", "vs\\.?"}
    for item in items:
        item = item.strip().rstrip(".,")
        if item and len(item) > 1 and item not in excluded:
            skills.add(item)
    if skills:
        return list(skills)[:20]
    # Fallback
    common_tech = ["Python", "Java", "Go", "JavaScript", "TypeScript", "React", "Node",
                   "SQL", "Docker", "Kubernetes", "AWS", "Git"]
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", jd_text, re.IGNORECASE):
            skills.add(term)
    return list(skills)[:20]


def parse_preferred_skills(jd_text: str) -> list[str]:
    """Extract preferred/nice-to-have skills from JD text."""
    positions = _find_marker_positions(jd_text)
    pre_start = positions.get("preferred skills", 0)
    resp_start = positions.get("responsibilities", len(jd_text))
    
    if pre_start >= len(jd_text) or resp_start <= pre_start:
        return []
    
    section_text = jd_text[pre_start:resp_start]
    # Remove the "Preferred skills:" marker
    section_text = re.sub(r'(?i)preferred skills[:\n]\s*', '', section_text).strip()
    
    # Further truncate at degree/education references
    # Find where "B.S.", "M.S.", "degree" appear and cut there
    degree_match = re.search(r'(?i)(B\.?\s?[A-Z]\.?\s?in|M\.?\s?[A-Z]\.?\s?in|degree)', section_text)
    if degree_match:
        section_text = section_text[:degree_match.start()].strip()
    
    skills: set[str] = set()
    items = re.split(r"[,;]\s*|\n", section_text)
    for item in items:
        item = item.strip().rstrip(".,")
        if item and len(item) > 1:
            skills.add(item)
    return list(skills)[:10]


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
        r"(?:B\.?S?\.?|BA|BS|B\.?Tech|B\.?Eng)\s+(?:required|preferred)?",
        r"(?:M\.?S?\.?|MA|MS|M\.?Tech|M\.?Eng)\s+(?:required|preferred)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, jd_text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def parse_tools_tech(jd_text: str) -> list[str]:
    """Extract tools and technologies mentioned."""
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
    positions = _find_marker_positions(jd_text)
    resp_start = positions.get("responsibilities", 0)
    
    if resp_start >= len(jd_text):
        return []
    
    section_text = jd_text[resp_start:]
    
    # Strip "Responsibilities: " prefix if present
    section_text = re.sub(r'Responsibilities:[\\s]*', '', section_text, flags=re.IGNORECASE).strip()
    
    responsibilities: list[str] = []
    bullets = re.findall(r"[-•*]\s+([A-Za-z .,]{5,150})", section_text)
    for b in bullets:
        b = b.strip()
        if b and len(b) > 5 and b not in responsibilities:
            responsibilities.append(b)
    if not bullets:
        sentences = re.split(r"[.!?]", section_text)
        for s in sentences:
            s = s.strip()
            if s and s[0].isupper() and len(s) > 10:
                responsibilities.append(s)
    if not responsibilities:
        all_bullets = re.findall(r"[-•*]\s+([A-Z][A-Za-z0-9 .,&-]{10,200})", jd_text)
        for b in all_bullets:
            b = b.strip()
            if b and len(b) > 10 and b not in responsibilities:
                responsibilities.append(b)
    return responsibilities[:15]


def search_role_kb(role_name: str, api_key: str) -> str:
    """Optional: search Tavily API for role responsibilities."""
    try:
        import requests  # type: ignore[import-untyped]
        url = "https://api.tavily.com/search"
        payload = {"query": f"{role_name} responsibilities", "api_key": api_key}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return results[0].get("content", "")
    except (OSError, ValueError, TypeError, RuntimeError, ConnectionError) as e:
        logger.warning(f"Could not get first result: {e}")
    return ""


def build_role_kb(
    title: str,
    jd_text: str,
    use_tavily: bool = False,
    tavily_key: str | None = None,
) -> dict[str, Any]:
    """Build role knowledge base from JD text."""
    required_skills = parse_required_skills(jd_text)
    preferred_skills = parse_preferred_skills(jd_text)
    years_exp = parse_years_exp(jd_text)
    degree = parse_degree_req(jd_text)
    tools = parse_tools_tech(jd_text)
    responsibilities = parse_responsibilities(jd_text)

    red_flags: list[str] = []
    if not required_skills:
        red_flags.append("No required skills detected")
    if not tools:
        red_flags.append("No tools/tech detected")
    if years_exp is None:
        red_flags.append("Years of experience not clearly specified")

    if use_tavily and tavily_key:
        tavily_result = search_role_kb(title, tavily_key)
        if tavily_result:
            responsibilities = [tavily_result]

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


def main():
    parser = argparse.ArgumentParser(description="Job Description Parser")
    parser.add_argument("--jd", type=str, help="Job description text")
    parser.add_argument("--jd-file", type=Path, help="Job description PDF file")
    parser.add_argument("--title", type=str, default="Unknown Role", help="Role title")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path")
    parser.add_argument("--output", type=Path, default=Path("role_kb.json"), help="Output KB file")
    parser.add_argument("--use-tavily", action="store_true", help="Use Tavily API to enrich role KB")
    args = parser.parse_args()

    env_path = args.env
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

    tavily_key = os.getenv("TAVILY_API_KEY") if args.use_tavily else None

    if args.jd_file:
        jd_text = extract_text_from_pdf(args.jd_file)
    elif args.jd:
        jd_text = args.jd
    else:
        parser.error("Either --jd or --jd-file must be provided")

    role_kb = build_role_kb(
        title=args.title,
        jd_text=jd_text,
        use_tavily=args.use_tavily,
        tavily_key=tavily_key,
    )

    args.output.write_text(json.dumps(role_kb, indent=2))
    print(f"Role KB written to {args.output}")
    print(json.dumps(role_kb, indent=2))


if __name__ == "__main__":
    main()