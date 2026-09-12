"""Mocked unit tests for app.agents — no live LLM or network calls."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.agents.evaluator import EvaluationAgent
from app.agents.revisor import RevisionAgent
from app.agents.tailor import TailorAgent

MOCK_ROLE_KB: dict[str, Any] = {
    "title": "SWE",
    "years_exp": 3,
    "required_skills": ["Python", "React", "SQL"],
    "preferred_skills": ["TypeScript"],
    "degree": "B.S.",
    "tools": ["Python", "React"],
    "responsibilities": ["Build web applications"],
    "red_flags": [],
}

MOCK_EVALUATION: dict[str, Any] = {
    "ats_match_percent": 85.0,
    "relevance_percent": 66.67,
    "factuality_score": 90.0,
    "flags": [],
    "resume_skills": ["Python", "React"],
    "matched_skills": ["Python", "React"],
    "missing_skills": ["SQL"],
}

MOCK_REVISION: dict[str, Any] = {
    "revisions": [],
    "final_ats": 85.0,
    "final_relevance": 66.67,
    "final_factuality": 90.0,
    "status": "completed",
    "total_flags": 0,
    "reason": "No flags - resume passes factuality check",
}


class TestTailorAgent:
    def test_initialization(self) -> None:
        agent = TailorAgent()
        assert agent.role_kb is None
        assert agent.resume_skills == set()
        assert agent.match_score == 0.0

    def test_compute_match_score(self) -> None:
        agent = TailorAgent()
        agent.resume_skills = {"Python", "React", "SQL"}
        score = agent.compute_match_score(["Python", "JavaScript", "React"])
        assert abs(score - 2 / 3) < 0.01

    def test_run_pipeline_orchestration_with_mocked_dependencies(
        self,
        mocker: pytest.Mock,
        tmp_path: Path,
    ) -> None:
        """Verify orchestration flow maps mocked payloads into the result dict."""
        resume_path = tmp_path / "resume.pdf"
        resume_path.write_bytes(b"%PDF-fake")
        output_path = tmp_path / "tailored_report.txt"

        mocker.patch(
            "app.tools.jdp_parser.build_role_kb",
            return_value=MOCK_ROLE_KB,
        )
        mocker.patch(
            "app.agents.tailor.extract_text_from_pdf",
            return_value="Python React experience with SQL databases.",
        )
        mocker.patch(
            "app.agents.tailor.extract_skills_from_text",
            return_value={"Python", "React"},
        )
        mock_evaluate = mocker.patch.object(
            EvaluationAgent,
            "evaluate",
            return_value=MOCK_EVALUATION,
        )
        mock_revise = mocker.patch.object(
            RevisionAgent,
            "revise",
            return_value=MOCK_REVISION,
        )

        agent = TailorAgent()
        jd_text = "Required skills: Python, React, SQL. 3+ years experience."
        results = agent.run_pipeline(
            jd_text=jd_text,
            resume_path=resume_path,
            tailored_output=output_path,
        )

        # Pipeline evaluation + render_tailored_resume both invoke the evaluator.
        assert mock_evaluate.call_count == 2
        mock_evaluate.assert_any_call(
            "Python React experience with SQL databases.",
            jd_text,
        )
        mock_revise.assert_called_once_with(MOCK_EVALUATION, 3)

        # Response mapping into the pipeline result dictionary.
        assert results["role_kb"] == MOCK_ROLE_KB
        assert results["evaluation"] == MOCK_EVALUATION
        assert results["revision_log"] == MOCK_REVISION
        assert results["match_score"] == pytest.approx(2 / 3, rel=1e-2)
        assert "Python" in results["resume_analysis"]["skills"]
        assert results["rendered_path"] == str(output_path.resolve())
        assert output_path.exists()

    def test_run_pipeline_short_circuits_on_empty_resume_text(
        self,
        mocker: pytest.Mock,
        tmp_path: Path,
    ) -> None:
        """Empty PDF text should still produce a structured, non-crashing result."""
        resume_path = tmp_path / "empty.pdf"
        resume_path.write_bytes(b"%PDF-empty")
        output_path = tmp_path / "report.txt"

        mocker.patch("app.tools.jdp_parser.build_role_kb", return_value=MOCK_ROLE_KB)
        mocker.patch("app.agents.tailor.extract_text_from_pdf", return_value="")
        mocker.patch("app.agents.tailor.extract_skills_from_text", return_value=set())
        mocker.patch.object(EvaluationAgent, "evaluate", return_value=MOCK_EVALUATION)
        mocker.patch.object(RevisionAgent, "revise", return_value=MOCK_REVISION)

        agent = TailorAgent()
        results = agent.run_pipeline("Required skills: Python.", resume_path, output_path)

        assert results["match_score"] == 0.0
        assert results["resume_analysis"]["skills"] == set()


class TestEvaluationAgent:
    def test_evaluate_basic(self) -> None:
        agent = EvaluationAgent()
        resume_text = "Python Django React SQL Git"
        jd_text = "Python Django React Position. Required skills: Python, Django, React."

        evaluation = agent.evaluate(resume_text, jd_text)

        assert 0 <= evaluation["ats_match_percent"] <= 100
        assert 0 <= evaluation["relevance_percent"] <= 100
        assert 0 <= evaluation["factuality_score"] <= 100
        assert isinstance(evaluation["flags"], list)

    def test_evaluate_with_responsibility_flags(self) -> None:
        """Flags are raised from responsibility cross-checks, not missing JD keywords."""
        agent = EvaluationAgent()
        resume_text = "Python SQL"
        jd_text = (
            "Required skills: Python.\n"
            "Responsibilities:\n"
            "- Built scalable Django microservices for production workloads"
        )

        evaluation = agent.evaluate(resume_text, jd_text)
        assert len(evaluation["flags"]) > 0
        assert evaluation["factuality_score"] < 100


class TestDecideNextAction:
    """Adaptation contract: surface-first, evidence-gated probes, no repeat."""

    @staticmethod
    def _settings() -> object:
        from types import SimpleNamespace

        return SimpleNamespace(target_ats=80.0)

    def test_surfaces_supported_skill_first(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "ats_match_percent": 60.0,
            "relevance_percent": 60.0,
            "supported_not_present": ["Python", "TypeScript"],
            "missing_skills": ["Python"],
            "unsupported_claims": [],
        }
        decision = agent.decide_next_action(
            evaluation, {"required_skills": ["Python", "TypeScript", "Kafka"]}, {}, self._settings()
        )
        assert decision["action"] == "surface_supported_skill"
        assert decision["target"] == "Python"

    def test_probes_skill_lacking_evidence(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "ats_match_percent": 60.0,
            "relevance_percent": 60.0,
            "supported_not_present": [],
            "missing_skills": ["Kafka"],
            "unsupported_claims": [],
        }
        decision = agent.decide_next_action(
            evaluation, {"required_skills": ["Kafka"]}, {}, self._settings()
        )
        assert decision["action"] == "surface_unsupported"
        assert decision["target"] == "Kafka"

    def test_unsatisfiable_skill_is_never_reproposed(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "ats_match_percent": 60.0,
            "relevance_percent": 60.0,
            "supported_not_present": [],
            "missing_skills": ["Kafka"],
            "unsupported_claims": [],
        }
        decision = agent.decide_next_action(
            evaluation,
            {"required_skills": ["Kafka"]},
            {},
            self._settings(),
            unsatisfiable={"Kafka"},
        )
        assert decision["action"] == "accept"

    def test_evidence_supported_missing_skill_is_not_probed(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "ats_match_percent": 60.0,
            "relevance_percent": 60.0,
            "supported_not_present": [],
            "missing_skills": ["Docker"],
            "unsupported_claims": [],
        }
        decision = agent.decide_next_action(
            evaluation,
            {"required_skills": ["Docker"]},
            {"Docker": type("E", (), {"supported": True})()},
            self._settings(),
        )
        assert decision["action"] == "accept"

    def test_accepts_when_targets_met(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "ats_match_percent": 90.0,
            "relevance_percent": 90.0,
            "supported_not_present": [],
            "missing_skills": [],
            "unsupported_claims": [],
        }
        decision = agent.decide_next_action(evaluation, {"required_skills": []}, {}, self._settings())
        assert decision["action"] == "accept"


class TestRevisionAgent:
    def test_revision_no_flags(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "flags": [],
            "ats_match_percent": 95.0,
            "relevance_percent": 95.0,
            "factuality_score": 100,
        }
        revision = agent.revise(evaluation, max_revisions=3)
        assert revision["status"] == "completed"
        assert revision["revisions"] == []

    def test_revision_initial_status_with_flags(self) -> None:
        agent = RevisionAgent()
        evaluation = {
            "flags": [{"claim": "Unsupported claim", "severity": "medium"}],
            "ats_match_percent": 50.0,
            "relevance_percent": 50.0,
            "factuality_score": 75,
        }
        revision = agent.revise(evaluation, max_revisions=3)
        assert revision["status"] in {"completed", "max_revisions_reached"}
        assert len(revision["revisions"]) >= 1
