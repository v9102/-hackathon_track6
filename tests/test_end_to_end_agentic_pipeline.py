"""End-to-end integration test for the agentic pipeline.

No part of the core loop (selector / revisor decision logic / evidence gate /
evaluator / planner) is mocked. Only the external OS tools are simulated:
``pdftotext`` (PDF text extraction) and ``pdflatex`` (PDF render) plus the PDF
layout validator, so this test runs without poppler/LaTeX installed.

The scenario intentionally includes:
1. A required skill (Docker) that is supported by a project tech tag but not
   yet visible in bullet prose -> the surface action rewrites a real bullet.
2. Required skills (Java, Redis) the candidate has NO evidence for -> the
   revisor proposes adding them and the planner's evidence gate REJECTS both,
   recording the decisions and adapting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RESUME_TEXT = """Shaunak Mishra
Backend Engineer

Skills: Python, React, PostgreSQL, Docker, Git

Projects
WorkflowOS
Python | React | PostgreSQL | Docker
- Built a log-processing pipeline that handles high volume quickly
- Designed a React dashboard for pipeline monitoring

Experience
Backend Engineer
2023 - 2024
- Built REST APIs in Python against PostgreSQL schemas

Education
State University
B.S. Computer Science
"""

JD_TEXT = """Full Stack Engineer
Required skills: Python, React, PostgreSQL, Docker, Git, Java, Redis.
Preferred skills: TypeScript, AWS.
"""


@pytest.fixture
def e2e_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Return a tmp run environment with external tools mocked."""
    resume_pdf = tmp_path / "candidate.pdf"

    def fake_extract_text(pdf_path) -> str:
        # Used both for parsing the source resume and for re-reading the
        # rendered artifacts (which are .pdf placeholders holding the text).
        return Path(pdf_path).read_text(encoding="utf-8")

    def fake_render(resume, out_pdf, template_path=None) -> Path:
        out_pdf = Path(out_pdf)
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        # Simulate a real compiled PDF: section titles are part of the text
        # and the artifact is long enough to pass the size/readability checks.
        text = resume.full_text()
        text += "\n\nProjects\nOpen Source\nExperience\nEducation\nTechnical Skills"
        pad = 1200 - len(text)
        if pad > 0:
            text += "\n" + ("Lorem ipsum fiscal vantage sollicitudin " * (pad // 40 + 1))
        out_pdf.write_text(text[: max(len(text), 1200)], encoding="utf-8")
        return out_pdf

    def fake_check_pdf(pdf_path, required_sections=None) -> dict:
        text = Path(pdf_path).read_text(encoding="utf-8")
        return {
            "exists": True,
            "readable": True,
            "text_length": len(text.strip()),
            "sections": required_sections or [],
            "size_bytes": 2048,
            "issues": [],
            "valid": True,
        }

    monkeypatch.setattr("app.tools.jdp_parser.extract_text_from_pdf", fake_extract_text)
    monkeypatch.setattr("app.agents.planner.render_pdf", fake_render)
    monkeypatch.setattr("app.agents.planner.check_pdf_artifact", fake_check_pdf)

    resume_pdf.write_bytes(b"%PDF-fake\n" + RESUME_TEXT.encode())
    return {"resume": resume_pdf, "tmp": tmp_path}


def test_agentic_pipeline_rejects_unsupported_and_surfaces_evidence(e2e_env) -> None:
    from app.agents.planner import AgenticPlanner

    planner = AgenticPlanner()
    state = planner.run(
        jd_text=JD_TEXT,
        resume_files=[e2e_env["resume"]],
        run_id="e2e-test",
    )

    # The loop genuinely terminated after exhausting evidence-based options.
    assert state.final_status in {"accepted", "best_effort", "max_iterations_reached"}

    # Docker was surfaced into a project bullet: real before/after text.
    docker_decisions = [
        d for d in state.decisions if d.action == "surface_supported_skill"
    ]
    assert docker_decisions, "expected a surface action for Docker"
    surface = docker_decisions[0]
    assert surface.accepted is True
    assert "Docker" in surface.after
    assert surface.before != surface.after

    # Java and Redis have no authentic evidence -> proposals were rejected.
    probes = [d for d in state.decisions if d.action == "surface_unsupported"]
    assert len(probes) == 2
    assert all(p.accepted is False for p in probes)
    assert any("Java" in p.target for p in probes)
    assert any("Redis" in p.target for p in probes)
    for probe in probes:
        assert "authentic evidence" in probe.rollback_reason

    # Factuality stayed at 100% - nothing was ever fabricated.
    final = state.current_evaluation
    assert final["factuality_score"] == 100.0
    assert final["unsupported_claims"] == []

    # The required-but-unmeetable skills are still marked missing.
    assert "Java" in final["missing_skills"]
    assert "Redis" in final["missing_skills"]

    # Artifacts + audit trail persisted.
    run_dir = Path(state.run_dir)
    assert (run_dir / "state.json").exists()
    assert (run_dir / "revision_log.json").exists()
    assert (run_dir / "final_report.json").exists()
    assert (run_dir / "final_report.txt").exists()
    if state.current_artifact:
        assert Path(state.current_artifact).exists()


def test_agentic_pipeline_accepts_when_targets_are_me(e2e_env) -> None:
    """A JD fully covered by evidence finishes with status 'accepted'."""
    from app.agents.planner import AgenticPlanner

    jd = "Full Stack Engineer\nRequired skills: Python, React, PostgreSQL, Docker, Git.\n"

    planner = AgenticPlanner()
    state = planner.run(
        jd_text=jd,
        resume_files=[e2e_env["resume"]],
        run_id="e2e-accept",
    )

    assert state.final_status == "accepted"
    final = state.current_evaluation
    assert final["factuality_score"] == 100.0
    assert final["ats_match_percent"] >= 80.0
    assert state.verification.get("valid") is True


def test_agentic_pipeline_rolls_back_worse_revision(
    e2e_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A revision that regresses metrics is rolled back and recorded.

    Here the evaluator is swapped for one that reports a worsening format score
    whenever bullets grow longer. The planner must then detect the regression,
    refuse the revision, restore the previous artifact and record the failure.
    """

    class RegressingEvaluator:
        def evaluate_agentic(
            self, resume, role_kb, evidence_map,
            artifact_text="", artifact_path=None,
        ) -> dict:
            from app.agents.evaluator import EvaluationAgent

            ev = EvaluationAgent().evaluate_agentic(
                resume, role_kb, evidence_map,
                artifact_text=artifact_text, artifact_path=artifact_path,
            )
            longest = max((len(b.current) for b in resume.all_bullets()), default=0)
            ev["format_score"] = max(0.0, 90.0 - longest)
            return ev

    monkeypatch.setattr("app.agents.planner.EvaluationAgent", RegressingEvaluator)

    from app.agents.planner import AgenticPlanner

    planner = AgenticPlanner()
    state = planner.run(
        jd_text=JD_TEXT,
        resume_files=[e2e_env["resume"]],
        run_id="e2e-rollback",
    )

    # The surface action was attempted and rolled back because it regressed.
    rolled_back = [
        d for d in state.decisions
        if not d.accepted and "regressed" in d.rollback_reason
    ]
    assert rolled_back, "expected at least one rolled-back revision"
    # The artifact on disk is the rolled-back (pre-change) version, which still
    # evaluates with the ORIGINAL bullet text.
    assert state.final_status != "accepted"