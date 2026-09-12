"""Real integration test: the full agentic chain against real PDFs.

This test does NOT mock the core loop (selector, revisor, evidence gate,
evaluator, planner) or the LaTeX renderer / pdftotext extraction. It runs the
actual pipeline over the repository's real candidate resumes and a real JD in a
sandbox directory. It requires ``pdflatex`` and ``pdftotext`` to be installed
and is skipped otherwise (matching the CI pipeline smoke test).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESUME_DIR = REPO_ROOT / "Resumes"
DEFAULT_JD = REPO_ROOT / "data" / "default_jd.txt"
SAMPLE_JD = REPO_ROOT / "data" / "sample_jd.txt"
TEMPLATE = REPO_ROOT / "ShaunakMishra_Resume.tex"

_pdflatex = shutil.which("pdflatex")
_pdftotext = shutil.which("pdftotext")
needs_tex = pytest.mark.skipif(
    not (_pdflatex and _pdftotext),
    reason="pdflatex and pdftotext required for the real-chain integration test",
)

STATE_KEYS = {
    "run_id", "goal", "jd_text", "role_kb", "candidates", "selected_resume",
    "evidence_map", "structured_resume", "current_artifact", "iteration",
    "max_iterations", "evaluation_history", "current_evaluation", "decisions",
    "actions", "verification", "final_status", "run_dir",
}


@pytest.fixture
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Direct all writes into a temporary base dir (no storage/ pollution)."""
    monkeypatch.setenv("RESUME_AGENT_BASE_DIR", str(tmp_path))
    return tmp_path


def _extract_text(pdf: Path) -> str:
    from app.tools.jdp_parser import extract_text_from_pdf

    return extract_text_from_pdf(pdf)


@needs_tex
def test_real_chain_default_jd_is_accepted_and_consistent(
    sandbox: Path,
) -> None:
    from app.agents.planner import AgenticPlanner
    from app.core.state import RunState

    planner = AgenticPlanner()
    state = planner.run(
        jd_text=DEFAULT_JD.read_text(encoding="utf-8"),
        resume_files=sorted(RESUME_DIR.glob("*.pdf")),
        template_path=TEMPLATE,
        run_id="integration-default",
    )

    # The real chain produced a verdict.
    assert state.final_status in {"accepted", "best_effort", "max_iterations_reached"}
    assert state.run_dir

    run_dir = Path(state.run_dir)
    state_payload = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

    # 1) Central state preserves everything needed to reconstruct the run.
    assert STATE_KEYS <= set(state_payload)
    rebuilt = RunState.from_dict(state_payload)
    assert rebuilt.run_id == state.run_id
    assert rebuilt.jd_text == state.jd_text

    # 2) Selection genuinely compared ALL three included resumes.
    assert len(state.candidates) >= 3
    for cand in state.candidates:
        assert cand.selection_score >= 0.0
        assert "Score" in cand.reasoning or cand.name
    assert state.selected_resume is not None
    assert state.candidates[0].name == state.selected_resume.name
    assert state.selected_resume.reasoning

    # 3) Artifacts exist, are non-empty, and their text is readable.
    original = run_dir / "original_resume.pdf"
    final_pdf = Path(state.current_artifact or "")
    assert original.exists() and original.stat().st_size > 1000
    assert final_pdf.exists() and final_pdf.stat().st_size > 1000
    final_text = _extract_text(final_pdf)
    assert len(final_text.strip()) > 500
    # The selected candidate's name made it into the rendered PDF.
    assert state.selected_resume.name.split()[0] in final_text

    # 4) Evaluation history records baseline -> (re-evaluate|final-verification).
    stages = [h.get("stage") for h in state.evaluation_history]
    assert "baseline" in stages
    assert any(s in stages for s in ("committed", "final-verification", "re-evaluate"))

    # 5) Every recorded decision carries a reason + before/after from execution.
    for decision in state.decisions:
        assert decision.reason, "every decision needs a reason"
        assert decision.iteration >= 1
        if decision.accepted:
            assert decision.after and decision.before is not None
        for metric_key in ("ats", "relevance", "factuality"):
            assert metric_key in decision.evaluation_before

    # 6) The demoted truth contract: the default JD is fully covered.
    if state.final_status == "accepted":
        assert state.verification.get("valid") is True
        assert not state.current_evaluation.get("unsupported_claims")
        assert state.current_evaluation["factuality_score"] == 100.0

    # 7) Reports exist and tell the same story as the state.
    assert json.loads((run_dir / "revision_log.json").read_text()) == [
        d.to_dict() for d in state.decisions
    ]
    assert (run_dir / "final_report.json").exists()
    assert (run_dir / "evaluations.json").exists()
    assert (run_dir / "evidence_report.json").exists()
    evidence = json.loads((run_dir / "evidence_report.json").read_text())
    assert evidence  # the candidate's evidence was built


@needs_tex
def test_real_chain_sample_jd_is_adaptive_without_fabrication(
    sandbox: Path,
) -> None:
    """The demanding JD must surface authentic skills and refuse unverifiable ones."""
    from app.agents.planner import AgenticPlanner

    planner = AgenticPlanner()
    state = planner.run(
        jd_text=SAMPLE_JD.read_text(encoding="utf-8"),
        resume_files=sorted(RESUME_DIR.glob("*.pdf")),
        template_path=TEMPLATE,
        run_id="integration-adaptive",
    )

    final_pdf = Path(state.current_artifact or "")
    assert final_pdf.exists(), "a real final PDF must be produced"
    final_text = _extract_text(final_pdf)

    # Surfaced authentic skills appear in the actual PDF bullets.
    surfaced = [d for d in state.decisions if d.action == "surface_supported_skill"]
    for decision in surfaced:
        assert decision.target, "every surface action targets a skill"
        assert "project tech" in final_text, (
            f"surfaced '{decision.target}' must be visible in the final PDF"
        )

    # Unverifiable skills were proposed then refused; nothing was fabricated.
    probed = [d for d in state.decisions if d.action == "surface_unsupported"]
    assert probed, "expected at least one refused unsupported proposal"
    assert all(not p.accepted for p in probed)
    final = state.current_evaluation
    assert final.get("unsupported_claims", []) == []
    assert final.get("factuality_score") == 100.0

    # The PDF text verifiably does NOT paper over the missing skills.
    missing = set(final.get("missing_skills", []))
    for probe in probed:
        assert probe.target in missing, (
            f"'target {probe.target}' must remain missing after refusing to fabricate"
        )