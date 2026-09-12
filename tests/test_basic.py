"""Tests for the Resume Tailoring System."""

import json
import os
from pathlib import Path

import pytest

# Import all main modules
from jdp_parser import build_role_kb, parse_required_skills, parse_preferred_skills
from resume_tailor import compute_match_score, load_resume_pdf
from evaluate_resume import compute_ats_match, compute_relevance, check_factuality
from revisor import load_evaluation


class TestJdpParser:
    """Test cases for the JD Parser."""

    def test_parse_required_skills(self):
        """Test that required skills are parsed correctly."""
        jd_text = "Required skills: React, Node.js, JavaScript, SQL, Git."
        skills = parse_required_skills(jd_text)
        assert "React" in skills
        assert "JavaScript" in skills
        assert "SQL" in skills

    def test_parse_preferred_skills(self):
        """Test that preferred skills are parsed correctly."""
        jd_text = "Preferred skills: TypeScript, AWS, Docker."
        skills = parse_preferred_skills(jd_text)
        assert "TypeScript" in skills
        assert "AWS" in skills
        assert "Docker" in skills

    def test_build_role_kb(self):
        """Test that role KB is built correctly."""
        jd_text = "Software Engineer position. 3+ years experience required. Required skills: React, Node.js."
        kb = build_role_kb(title="SWE", jd_text=jd_text, use_tavily=False)
        assert "title" in kb
        assert "years_exp" in kb
        assert "required_skills" in kb
        assert kb["years_exp"] == 3


class TestResumeTailor:
    """Test cases for the Resume Tailor."""

    def test_load_resume(self):
        """Test that a resume can be loaded."""
        resume_path = "Resumes/ShaunakMishra_Resume.pdf"
        if os.path.exists(resume_path):
            resume = load_resume_pdf(Path(resume_path))
            assert "full_text" in resume
            assert "skills" in resume

    def test_compute_match_score(self):
        """Test match score computation."""
        resume_skills = {"Python", "React", "SQL"}
        required_skills = {"Python", "JavaScript", "React"}
        score = compute_match_score(resume_skills, required_skills)
        assert 0 <= score <= 1
        # 2 out of 3 skills match = 2/3
        assert abs(score - 2/3) < 0.01


class TestEvaluateResume:
    """Test cases for the Resume Evaluator."""

    def test_compute_ats_match(self):
        """Test ATS match percentage computation."""
        resume_text = "Python Django React SQL Git"
        jd_text = "Python Django React Position. Required skills: Python, Django, React, SQL."
        score = compute_ats_match(resume_text, jd_text)
        assert 0 <= score <= 100
        # All skills match = 100%
        assert score == 100.0

    def test_compute_relevance(self):
        """Test relevance percentage computation."""
        resume_skills = {"Python", "React"}
        required_skills = {"Python", "JavaScript", "React"}
        score = compute_relevance(resume_skills, required_skills)
        assert 0 <= score <= 100
        # 2 out of 3 = 66.7%
        assert abs(score - 66.7) < 1


class TestRevisor:
    """Test cases for the Revisor."""

    def test_load_evaluation(self):
        """Test that evaluation JSON can be loaded."""
        eval_path = "evaluation.json"
        if os.path.exists(eval_path):
            eval_data = load_evaluation(Path(eval_path))
            assert "ats_match_percent" in eval_data
            assert "relevance_percent" in eval_data
            assert "flags" in eval_data