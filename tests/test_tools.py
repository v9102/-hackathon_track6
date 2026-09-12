"""Tests for the tools module - JD Parser and configuration."""

import json
import os
from pathlib import Path

import pytest

from app.tools.jdp_parser import (
    parse_required_skills,
    parse_preferred_skills,
    parse_years_exp,
    parse_degree_req,
    parse_tools_tech,
    parse_responsibilities,
    build_role_kb,
)
from app.core.config import settings


class TestJdpParser:
    """Test cases for JD Parser tool."""

    def test_parse_required_skills(self):
        """Test required skills extraction."""
        jd = "Required skills: React, Node.js, JavaScript, SQL, Git."
        skills = parse_required_skills(jd)
        assert "React" in skills
        assert "JavaScript" in skills
        assert "SQL" in skills

    def test_parse_preferred_skills(self):
        """Test preferred skills extraction."""
        jd = "Preferred skills: TypeScript, AWS, Docker. Nice-to-have: Kubernetes."
        skills = parse_preferred_skills(jd)
        assert "TypeScript" in skills
        assert "AWS" in skills

    def test_parse_years_exp(self):
        """Test years experience extraction."""
        jd = "3+ years experience required."
        years = parse_years_exp(jd)
        assert years == 3

    def test_parse_degree_req(self):
        """Test degree requirement extraction."""
        jd = "B.S. in Computer Science required."
        degree = parse_degree_req(jd)
        assert degree is not None

    def test_parse_tools_tech(self):
        """Test tools/tech extraction."""
        jd = "Position requires Python, Docker, and AWS."
        tech = parse_tools_tech(jd)
        assert "Python" in tech
        assert "Docker" in tech

    def test_parse_responsibilities(self):
        """Test responsibilities extraction."""
        jd = "Responsibilities: Build web apps, collaborate with team."
        resp = parse_responsibilities(jd)
        assert len(resp) > 0


class TestConfig:
    """Test cases for configuration management."""

    def test_settings_exist(self):
        """Test that settings object is properly configured."""
        from app.core.config import settings
        assert settings is not None
        assert hasattr(settings, "base_dir")
        assert hasattr(settings, "storage_dir")
        assert hasattr(settings, "role_kb_path")

    def test_path_independence(self):
        """Test that paths are pathlib.Path objects."""
        from app.core.config import settings
        assert isinstance(settings.base_dir, Path)
        assert isinstance(settings.storage_dir, Path)
        assert isinstance(settings.role_kb_path, Path)


class TestBuildRoleKB:
    """Test role KB building functionality."""

    def test_role_kb_structure(self):
        """Test that build_role_kb returns dict with expected keys."""
        jd = "Software Engineer position. 3+ years experience. Required skills: React, Node.js."
        kb = build_role_kb(jd_text=jd)
        assert "title" in kb
        assert "years_exp" in kb
        assert "required_skills" in kb
        assert "preferred_skills" in kb
        assert "degree" in kb
        assert "tools" in kb
        assert "responsibilities" in kb