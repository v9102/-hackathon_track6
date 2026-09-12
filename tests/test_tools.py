"""Deterministic unit tests for app.tools.jdp_parser."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.tools.jdp_parser import (
    build_role_kb,
    extract_skills_from_text,
    extract_text_from_pdf,
    parse_degree_req,
    parse_preferred_skills,
    parse_required_skills,
    parse_responsibilities,
    parse_tools_tech,
    parse_years_exp,
)

SAMPLE_JD = """
Software Engineer
3+ years experience required.

Required skills: React, Node.js, JavaScript, SQL, Git.
Preferred skills: TypeScript, AWS, Docker.
Nice-to-have: Kubernetes.

Responsibilities:
- Build scalable web applications
- Collaborate with cross-functional teams

Education: B.S. in Computer Science required.
"""


class TestExtractSkillsFromText:
    def test_extracts_known_skills(self) -> None:
        text = "Experienced with Python, Docker, and AWS deployments."
        skills = extract_skills_from_text(text)
        assert {"Python", "Docker", "AWS"}.issubset(skills)

    def test_empty_input_returns_empty_set(self) -> None:
        assert extract_skills_from_text("") == set()

    def test_malformed_input_returns_empty_set(self) -> None:
        assert extract_skills_from_text("!!! @@@ ###") == set()


class TestParseRequiredSkills:
    def test_parses_labeled_section(self) -> None:
        jd = "Required skills: React, Node.js, JavaScript, SQL, Git."
        skills = parse_required_skills(jd)
        assert "React" in skills
        assert "JavaScript" in skills
        assert "SQL" in skills

    def test_fallback_detects_common_tech_in_body(self) -> None:
        jd = "We need strong Python and Docker experience."
        skills = parse_required_skills(jd)
        assert "Python" in skills
        assert "Docker" in skills

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_required_skills("") == []

    def test_malformed_input_returns_empty_or_fallback_only(self) -> None:
        assert parse_required_skills("!!! @@@") == []


class TestParsePreferredSkills:
    def test_parses_preferred_and_nice_to_have(self) -> None:
        jd = "Preferred skills: TypeScript, AWS, Docker. Nice-to-have: Kubernetes."
        skills = parse_preferred_skills(jd)
        assert "TypeScript" in skills
        assert "AWS" in skills

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_preferred_skills("") == []


class TestParseYearsExp:
    def test_parses_plus_notation(self) -> None:
        assert parse_years_exp("3+ years experience required.") == 3

    def test_parses_minimum_phrasing(self) -> None:
        assert parse_years_exp("Minimum 5 years of experience.") == 5

    def test_empty_input_returns_none(self) -> None:
        assert parse_years_exp("") is None

    def test_malformed_input_returns_none(self) -> None:
        assert parse_years_exp("many years of experience") is None


class TestParseDegreeReq:
    def test_detects_bachelors(self) -> None:
        degree = parse_degree_req("B.S. in Computer Science required.")
        assert degree is not None

    def test_empty_input_returns_none(self) -> None:
        assert parse_degree_req("") is None


class TestParseToolsTech:
    def test_extracts_technologies(self) -> None:
        jd = "Position requires Python, Docker, and AWS."
        tech = parse_tools_tech(jd)
        assert "Python" in tech
        assert "Docker" in tech
        assert "AWS" in tech

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_tools_tech("") == []


class TestParseResponsibilities:
    def test_extracts_responsibility_section(self) -> None:
        jd = "Responsibilities: Build web apps, collaborate with team."
        resp = parse_responsibilities(jd)
        assert len(resp) > 0

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_responsibilities("") == []


class TestBuildRoleKB:
    def test_full_structure_and_role_title(self) -> None:
        kb = build_role_kb(title="SWE", jd_text=SAMPLE_JD)
        assert kb["title"] == "SWE"
        assert kb["years_exp"] == 3
        assert "React" in kb["required_skills"]
        assert "TypeScript" in kb["preferred_skills"]
        assert isinstance(kb["red_flags"], list)

    def test_empty_jd_populates_red_flags(self) -> None:
        kb = build_role_kb(title="Unknown Role", jd_text="")
        assert kb["required_skills"] == []
        assert "No required skills detected" in kb["red_flags"]
        assert "No tools/tech detected" in kb["red_flags"]
        assert "Years of experience not clearly specified" in kb["red_flags"]

    def test_none_jd_treated_as_empty(self) -> None:
        kb = build_role_kb(title="Unknown Role", jd_text=None)
        assert kb["required_skills"] == []
        assert len(kb["red_flags"]) >= 1


class TestExtractTextFromPdf:
    def test_failed_pdftotext_raises_value_error(self, mocker: pytest.Mock) -> None:
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=1, stderr="pdftotext: error", stdout="")

        with pytest.raises(ValueError, match="Failed to extract text from PDF"):
            extract_text_from_pdf(Path("/nonexistent/resume.pdf"))

    def test_successful_pdftotext_returns_stdout(self, mocker: pytest.Mock) -> None:
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="Python React SQL")

        text = extract_text_from_pdf(Path("/fake/resume.pdf"))
        assert text == "Python React SQL"


class TestSkillNormalization:
    """Alias mapping must normalize common forms without unsafe equivalences."""

    def test_common_aliases_normalize(self) -> None:
        from app.tools.skills import normalize_skill

        assert normalize_skill("Node") == "Node.js"
        assert normalize_skill("NodeJS") == "Node.js"
        assert normalize_skill("node.js") == "Node.js"
        assert normalize_skill("JS") == "JavaScript"
        assert normalize_skill("JavaScript") == "JavaScript"
        assert normalize_skill("TS") == "TypeScript"
        assert normalize_skill("K8s") == "Kubernetes"
        assert normalize_skill("Postgres") == "PostgreSQL"

    def test_technically_distinct_skills_are_not_merged(self) -> None:
        from app.tools.skills import normalize_skill

        distinct = ["SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis"]
        normalized = {normalize_skill(s) for s in distinct}
        assert len(normalized) == len(distinct)

    def test_github_is_not_git(self) -> None:
        from app.tools.skills import normalize_skill

        assert normalize_skill("Git") != normalize_skill("GitHub")

    def test_nextjs_is_not_react(self) -> None:
        from app.tools.skills import normalize_skill

        assert normalize_skill("Next.js") != normalize_skill("React")

    def test_unknown_skill_identity(self) -> None:
        from app.tools.skills import normalize_skill

        assert normalize_skill("Kafka") == "Kafka"

    def test_extraction_uses_canonical_names(self) -> None:
        from app.tools.skills import extract_canonical_skills

        text = "Built with Node and K8s on Postgres with k8s for the JS frontend."
        skills = extract_canonical_skills(text)
        assert "Node.js" in skills
        assert "Kubernetes" in skills
        assert "PostgreSQL" in skills
        assert "JavaScript" in skills

    def test_canonicalize_list_dedupes_aliases(self) -> None:
        from app.tools.skills import canonicalize_list

        raw = ["node", "Node.js", "js", "JavaScript", "Postgres"]
        canonical = canonicalize_list(raw)
        assert canonical == {"Node.js", "JavaScript", "PostgreSQL"}


class TestEvidenceClassification:
    """Required skills must be classified supported/unsupported/unknown."""

    def _resume_with(self):
        from app.core.models import Bullet, SectionEntry, StructuredResume

        return StructuredResume(
            name="Jamie Doe",
            headline="Backend Engineer",
            skills_lines=["Python, PostgreSQL"],
            projects=[
                SectionEntry(
                    id="project_0",
                    title="WorkflowOS",
                    subtitle="Python | PostgreSQL",
                    meta="2024",
                    bullets=[
                        Bullet(
                            id="project_0_0",
                            original="Built an ETL pipeline.",
                            current="Built an ETL pipeline.",
                            evidence=["WorkflowOS tech stack: Python | PostgreSQL"],
                        )
                    ],
                )
            ],
        )

    def test_supported_when_candidate_evidence_exists(self) -> None:
        from app.tools.evidence import build_evidence_map, required_evidence_summary

        resume = self._resume_with()
        evidence_map = build_evidence_map(resume)
        summary = required_evidence_summary(
            evidence_map, ["Python", "PostgreSQL"], output_skills=set()
        )
        assert summary["Python"]["classification"] == "supported"
        assert summary["PostgreSQL"]["classification"] == "supported"

    def test_unsupported_when_output_claims_without_evidence(self) -> None:
        from app.tools.evidence import (
            build_evidence_map,
            find_unsupported_claims,
            required_evidence_summary,
        )

        resume = self._resume_with()
        evidence_map = build_evidence_map(resume)
        summary = required_evidence_summary(
            evidence_map,
            ["Kafka"],
            output_skills={"Kafka"},
        )
        assert summary["Kafka"]["classification"] == "unsupported"

        claims = find_unsupported_claims(evidence_map, "I can do Kafka and Flink.")
        assert any("Kafka" in c["claim"] for c in claims)

    def test_unregistered_tech_is_not_falsely_accused(self) -> None:
        from app.tools.evidence import build_evidence_map, find_unsupported_claims

        resume = self._resume_with()
        evidence_map = build_evidence_map(resume)
        claims = find_unsupported_claims(evidence_map, "Familiar with Flink streaming.")
        assert claims == []  # unknown techs stay UNKNOWN, never falsely called out

    def test_unknown_when_no_evidence_and_not_claimed(
        self,
    ) -> None:
        from app.tools.evidence import build_evidence_map, required_evidence_summary

        resume = self._resume_with()
        evidence_map = build_evidence_map(resume)
        summary = required_evidence_summary(
            evidence_map, ["Kafka"], output_skills=set()
        )
        assert summary["Kafka"]["classification"] == "unknown"

    def test_absence_in_other_resumes_is_not_falsity(self) -> None:
        from app.tools.evidence import (
            build_evidence_map,
            find_unsupported_claims,
            required_evidence_summary,
        )

        resume = self._resume_with()
        evidence_map = build_evidence_map(resume)
        summary = required_evidence_summary(evidence_map, ["Python"], output_skills=set())
        assert summary["Python"]["classification"] == "supported"

        claims = find_unsupported_claims(evidence_map, resume.full_text())
        assert not claims
