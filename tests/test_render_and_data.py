"""Contract tests for the LaTeX renderer and the two canonical demo JDs.

These pin the behaviors the demo narrative depends on: the default JD is fully
covered (honest accept) and the sample JD forces adaptation with unverifiable
skills, while the renderer escape/validation logic stays regression-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.planner import _DEFAULT_JD
from app.tools.jdp_parser import build_role_kb
from app.tools.latex_renderer import (
    _preamble,
    check_pdf_artifact,
    format_score_estimate,
    render_pdf,
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


class TestPreambleTopMargin:
    def test_file_preamble_neutralizes_negative_topmargin(self) -> None:
        template = Path(__file__).resolve().parent.parent / "ShaunakMishra_Resume.tex"
        preamble = _preamble(template)
        assert "\\topmargin}{0pt}" in preamble
        assert "-0.7in" not in preamble

    def test_fallback_preamble_neutralizes_negative_topmargin(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.tex"
        preamble = _preamble(missing)
        assert "\\topmargin}{0pt}" in preamble
        assert "-0.7in" not in preamble


class TestPdfRendersNameWithoutClipping:
    def test_render_without_template_file_still_shows_name(self, tmp_path: Path) -> None:
        shutil = __import__("shutil")
        if shutil.which("pdflatex") is None or shutil.which("pdftotext") is None:
            pytest.skip("pdflatex/pdftotext not installed")

        from app.core.models import Bullet, SectionEntry, StructuredResume
        from app.tools.jdp_parser import extract_text_from_pdf

        resume = StructuredResume(
            name="Zed Testerson",
            headline="Full-Stack Engineer",
            contact=["z@example.com"],
            summary="A summary line used for evaluation text length.",
            skills_lines=["Python, Go"],
            education=["B.S. Computer Science"],
            projects=[
                SectionEntry(
                    id="p",
                    title="Project",
                    subtitle="Go | Python",
                    meta="2024",
                    bullets=[
                        Bullet(id="b0", original="Did the thing.", current="Did the thing.")
                    ],
                )
            ],
        )
        pdf = tmp_path / "no_template.pdf"
        render_pdf(resume, pdf, tmp_path / "missing_template.tex")  # fallback preamble
        text = extract_text_from_pdf(pdf)
        assert text.lstrip().startswith("Zed Testerson")


class TestPdfLatexMissing:
    def test_render_fails_clearly_when_pdflatex_is_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.core.models import StructuredResume
        from app.tools.latex_renderer import render_pdf

        monkeypatch.setattr("app.tools.latex_renderer.shutil.which", lambda _cmd: None)

        with pytest.raises(RuntimeError, match="pdflatex is not installed"):
            render_pdf(
                StructuredResume(name="Test Name", skills_lines=["Python"]),
                tmp_path / "out.pdf",
            )


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