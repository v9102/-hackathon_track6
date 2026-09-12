"""Contract tests for the LaTeX renderer and the two canonical demo JDs.

These pin the behaviors the demo narrative depends on: the default JD is fully
covered (honest accept) and the sample JD forces adaptation with unverifiable
skills, while the renderer escape/validation logic stays regression-free.
"""

from __future__ import annotations

from pathlib import Path

from app.agents.planner import _DEFAULT_JD
from app.tools.jdp_parser import build_role_kb
from app.tools.latex_renderer import (
    check_pdf_artifact,
    format_score_estimate,
    tex_escape,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class TestTeXEscape:
    def test_escapes_latex_specials(self) -> None:
        assert tex_escape("a&b%c#d_e$f") == "a\\&b\\%c\\#d\\_e\\$f"

    def test_maps_tilde_and_dash_variants(self) -> None:
        out = tex_escape("real~world\u2014x\u2013y\u223c")
        assert out.count("$\\sim$") == 2
        assert "---" in out
        assert "--" in out

    def test_maps_math_symbols(self) -> None:
        assert tex_escape("\u2192ok") == "$\\rightarrow$ok"
        assert tex_escape("x\u2265y") == "x$\\geq$y"


class TestCheckPdfArtifact:
    def test_missing_file_is_invalid(self) -> None:
        checks = check_pdf_artifact(Path("/nonexistent/resume.pdf"))
        assert checks["exists"] is False
        assert checks["valid"] is False
        assert any("does not exist" in i for i in checks["issues"])

    def test_valid_readable_pdf_with_sections(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf = tmp_path / "resume.pdf"
        pdf.write_bytes(b"\x00" * 1500)
        monkeypatch.setattr(
            "app.tools.jdp_parser.extract_text_from_pdf",
            lambda _p: "Shaunak Mishra Projects Skills Education WorkflowOS",
        )
        checks = check_pdf_artifact(pdf)
        assert checks["valid"] is True
        assert checks["readable"] is True
        assert checks["sections"] == ["Projects", "Skills", "Education"]

    def test_too_small_file_is_invalid(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf = tmp_path / "resume.pdf"
        pdf.write_bytes(b"\x00" * 200)
        monkeypatch.setattr(
            "app.tools.jdp_parser.extract_text_from_pdf",
            lambda _p: "Projects Skills Education content",
        )
        checks = check_pdf_artifact(pdf)
        assert checks["valid"] is False
        assert any("too small" in i for i in checks["issues"])

    def test_missing_sections_flagged(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pdf = tmp_path / "resume.pdf"
        pdf.write_bytes(b"\x00" * 1500)
        monkeypatch.setattr(
            "app.tools.jdp_parser.extract_text_from_pdf",
            lambda _p: "Short resume with no project mentions",
        )
        checks = check_pdf_artifact(pdf)
        assert checks["valid"] is False
        assert any("Missing sections" in i for i in checks["issues"])


class TestFormatScoreEstimate:
    def test_missing_file_scores_zero(self) -> None:
        assert format_score_estimate({"exists": False, "readable": False, "text_length": 0, "sections": [], "issues": ["PDF file does not exist"]}) == 0.0

    def test_perfect_artifact_scores_full(self) -> None:
        checks = {
            "exists": True,
            "readable": True,
            "text_length": 2000,
            "sections": ["Projects", "Skills", "Education"],
            "issues": [],
        }
        assert format_score_estimate(checks) == 100.0

    def test_unreadable_small_pdf_penalised(self) -> None:
        checks = {
            "exists": True,
            "readable": False,
            "text_length": 0,
            "sections": [],
            "issues": ["PDF text is empty/unreadable", "Missing sections: Projects, Skills, Education"],
        }
        score = format_score_estimate(checks)
        assert 0.0 <= score < 40.0


class TestDemoDataContracts:
    def test_default_jd_matches_planner_builtin(self) -> None:
        default_jd = (DATA_DIR / "default_jd.txt").read_text(encoding="utf-8").strip()
        assert default_jd == _DEFAULT_JD.strip()

    def test_default_jd_is_fully_covered(self) -> None:
        kb = build_role_kb(title="Full Stack Software Engineer", jd_text=(DATA_DIR / "default_jd.txt").read_text(encoding="utf-8"))
        assert set(kb["required_skills"]) == {
            "Python", "React", "Node.js", "JavaScript",
            "TypeScript", "SQL", "PostgreSQL", "Docker", "Git",
        }
        assert "Kafka" in kb["preferred_skills"]

    def test_sample_jd_forces_unverifiable_skills(self) -> None:
        kb = build_role_kb(title="Full Stack", jd_text=(DATA_DIR / "sample_jd.txt").read_text(encoding="utf-8"))
        required = set(kb["required_skills"])
        assert "Kubernetes" in required
        assert "Redis" in required
        assert "Kafka" in required
        assert "Python" in required