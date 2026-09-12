"""Evaluation Agent - ATS/Factuality Assessment.

The Evaluation Agent assesses resumes against job descriptions using three
scores:
- ATS Match %: Keyword overlap between resume and job description
- Relevance %: Match score from skill intersection analysis
- Factuality Check: Flags any resume claim NOT supported in resume text
  or the known profile (cross-checked across all candidate resumes)

This agent operates on a truth-first principle - it never fabricates
support for claims and instead flags unsupported statements for revision.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.core.config import settings
from app.tools.jdp_parser import extract_skills_from_text


def compute_ats_match(resume_text: str, jd_text: str) -> float:
    """Compute ATS match % = keyword overlap with JD.
    
    Args:
        resume_text: Resume text content
        jd_text: Job description text
        
    Returns:
        ATS match percentage (0-100)
    """
    # Extract common tech terms from both texts
    common_tech = [
        "Python", "Java", "Go", "JavaScript", "TypeScript", "React", "Node",
        "SQL", "Docker", "Kubernetes", "AWS", "Git",
    ]
    
    jd_skills: set[str] = set()
    resume_skills: set[str] = set()
    
    for term in common_tech:
        if re.search(rf"\b{re.escape(term)}\b", jd_text, re.IGNORECASE):
            jd_skills.add(term.lower())
        if re.search(rf"\b{re.escape(term)}\b", resume_text, re.IGNORECASE):
            resume_skills.add(term.lower())
    
    if not jd_skills:
        return 0.0
    
    intersection = jd_skills & resume_skills
    return round(len(intersection) / len(jd_skills) * 100, 2)


def compute_relevance(resume_skills: Set[str], required_skills: Set[str]) -> float:
    """Compute relevance % = match_score from skill intersection analysis.
    
    Args:
        resume_skills: Set of skills found in resume
        required_skills: Set of required skills from role KB
        
    Returns:
        Relevance percentage (0-100)
    """
    if not required_skills:
        return 0.0
    
    intersection = resume_skills & required_skills
    return round(len(intersection) / len(required_skills) * 100, 2)


def check_factuality(
    resume_text: str,
    role_kb: Dict[str, Any],
    all_resumes: Optional[Dict[str, Dict[str, any]]] = None,
) -> Dict[str, Any]:
    """Check factuality - flag claims not supported in resume text or known profile.
    
    Args:
        resume_text: Resume text to validate
        role_kb: Role knowledge base with requirements
        all_resumes: Optional dict of all candidate resumes for cross-check
        
    Returns:
        Dictionary with factuality score and flags list
    """
    flags: List[Dict[str, str]] = []
    resume_skills = extract_skills_from_text(resume_text)
    
    # Cross-check with other resumes if provided
    if all_resumes:
        resume_skill_set = set(resume_skills)
        for other_name, other_data in all_resumes.items():
            other_skills = set.extract_skills_from_text(other_data.get("full_text", ""))
            # Skills in this resume but not in others may be exaggerated
            exaggerated = resume_skill_set - other_skills
            for skill in exaggerated:
                flags.append({
                    "claim": f"Claims {skill} but other resumes don't mention it",
                    "severity": "low",
                })
    
    # Check for exaggerated claim patterns
    leetcode_match = re.search(r"\b(\d{3,4})\s*LeetCode\b", resume_text, re.IGNORECASE)
    if leetcode_match:
        claimed = int(leetcode_match.group(1))
        # Check across all resumes for actual LeetCode counts
        all_counts: list[int] = []
        if all_resumes:
            for other_name, other_data in all_resumes.items():
                m = re.search(r"\b(\d{1,3})\s*LeetCode\b", other_data.get("full_text", ""), re.IGNORECASE)
                if m:
                    all_counts.append(int(m.group(1)))
        if all_counts:
            avg = sum(all_counts) / len(all_counts)
            if abs(claimed - avg) > 20:
                flags.append({
                    "claim": f"Claims {claimed} LeetCode problems but average across resumes is {round(avg)}",
                    "severity": "medium",
                })
    
    # Check for skills mentioned in role responsibilities but not in resume
    responsibilities = role_kb.get("responsibilities", [])
    for resp in responsibilities:
        resp_lower = resp.lower()
        resp_skills = set(re.findall(r"\b(\w+\.?\w*)\b", resp_lower))
        for skill in resp_skills:
            if skill not in set(resume_skills) and skill not in {
                "built", "designed", "implemented", "created", "developed",
                "experience", "worked", "used"
            }:
                flags.append({
                    "claim": f"Resume doesn't mention {skill} needed for: {resp[:60]}",
                    "severity": "medium",
                })
                break  # One flag per responsibility is enough
    
    # Compute factuality score: 100 - (15 per medium flag, 5 per low flag)
    medium_count = sum(1 for f in flags if f.get("severity") == "medium")
    low_count = sum(1 for f in flags if f.get("severity") == "low")
    factuality_score = round(max(0, 100 - (medium_count * 15 + low_count * 5)), 2)
    
    return {
        "factuality_score": factuality_score,
        "flags": flags,
        "resume_skills": sorted(list(set(resume_skills))),
    }


class EvaluationAgent:
    """Agent that evaluates resumes against job descriptions.
    
    Responsibilities:
    - Compute ATS match percentage
    - Compute relevance percentage  
    - Perform factuality cross-checking
    - Generate flags for unsupported claims
    - Return structured evaluation results
    """
    
    def evaluate(
        self,
        resume_text: str,
        jd_text: str,
        all_resumes_data: Optional[Dict[str, Dict[str, any]]] = None,
    ) -> Dict[str, Any]:
        """Execute the full evaluation pipeline.
        
        Args:
            resume_text: Resume text content
            jd_text: Job description text
            all_resumes_data: Optional dict of all candidate resumes
            
        Returns:
            Dictionary with ATS match %, relevance %, factuality score, and flags
        """
        # Extract skills from resume
        resume_skills = extract_skills_from_text(resume_text)
        
        # Extract required skills from JD text
        from app.tools.jdp_parser import parse_required_skills, parse_responsibilities
        jd_required_skills = parse_required_skills(jd_text)
        jd_responsibilities = parse_responsibilities(jd_text)
        required_skills: Set[str] = set(jd_required_skills)
        
        # Compute ATS match
        ats_match = compute_ats_match(resume_text, jd_text)
        
        # Compute relevance % = match_score from skill intersection
        relevance = compute_relevance(resume_skills, required_skills)
        
        # Check factuality - pass both required skills and responsibilities
        factuality = check_factuality(
            resume_text, 
            {"required_skills": list(required_skills), "responsibilities": jd_responsibilities}, 
            all_resumes_data
        )
        
        return {
            "ats_match_percent": ats_match,
            "relevance_percent": relevance,
            "factuality_score": factuality["factuality_score"],
            "flags": factuality["flags"],
            "resume_skills": sorted(list(resume_skills)),
            "matched_skills": sorted(list(resume_skills & required_skills)),
            "missing_skills": sorted(list(required_skills - resume_skills)),
        }
