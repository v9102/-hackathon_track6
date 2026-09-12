from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from app.core.config import settings


def _resolve_path(value: Path | str | None, default: Path) -> Path:
    """Resolve a user path; bare filenames are placed under storage/."""
    if value is None:
        return default
    path = Path(value)
    if not path.is_absolute() and len(path.parts) == 1:
        return settings.storage_dir / path.name
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    settings.ensure_storage()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_task(task: str, **kwargs: Any) -> None:
    """Execute a specific task by name."""
    print(f"\nRunning task: {task}")
    settings.ensure_storage()

    if task == "parse":
        from app.agents.tailor import TailorAgent

        jd_text = kwargs.get("jd_text", "")
        if not jd_text:
            print("Error: --jd text required for parse task")
            return

        title = kwargs.get("title", "Unknown Role")
        output_path = _resolve_path(kwargs.get("output"), settings.parsed_role_kb_path)

        tailor = TailorAgent()
        role_kb = tailor.parse_job_description(jd_text, title=title)
        _write_json(output_path, role_kb)
        print(f"JD parsed successfully! Role KB written to {output_path}")

    elif task == "tailor":
        from app.agents.tailor import TailorAgent

        default_resume = settings.resume_dir / "ShaunakMishra_Resume.pdf"
        resume_path = Path(kwargs.get("resume_path", default_resume))
        jd_text = kwargs.get("jd_text", "")
        role = kwargs.get("role", "SWE")
        output_path = _resolve_path(kwargs.get("output_path"), settings.tailored_resume_path)

        if not resume_path.exists():
            print(f"Error: Resume not found at {resume_path}")
            return

        agent = TailorAgent()
        results = agent.run_pipeline(
            jd_text=jd_text or "Required skills: Python, React, SQL.",
            resume_path=resume_path,
            tailored_output=output_path,
        )

        role_kb = results["role_kb"] or {}
        evaluation = results["evaluation"]
        revision_log = results["revision_log"]
        resume_analysis = results["resume_analysis"]

        required_skills = role_kb.get("required_skills", [])
        resume_skills = sorted(resume_analysis.get("skills", []))
        matched = sorted(set(resume_skills) & set(required_skills))

        tailoring_report = {
            "role_title": role_kb.get("title", role),
            "source_resume": Path(resume_analysis.get("file_path", str(resume_path))).name,
            "match_score": round(results["match_score"] * 100, 2),
            "required_skills": required_skills,
            "resume_skills": resume_skills,
            "matched_skills": matched,
            "missing_skills": sorted(set(required_skills) - set(resume_skills)),
            "preferred_skills": role_kb.get("preferred_skills", []),
            "kept_bullets": [],
            "removed_bullets": [],
            "rewritten_bullets": [],
        }

        _write_json(settings.parsed_role_kb_path, role_kb)
        _write_json(settings.tailoring_report_path, tailoring_report)
        _write_json(settings.evaluation_path, evaluation)
        _write_json(settings.revision_log_path, revision_log)

        print("Resume tailored successfully!")
        print(f"  Output: {results['rendered_path']}")
        print(f"  Tailoring report: {settings.tailoring_report_path}")

    elif task == "evaluate":
        resume_path = _resolve_path(
            kwargs.get("resume_path"),
            settings.tailored_resume_path,
        )
        jd_text = kwargs.get("jd_text", "")

        if not resume_path.exists():
            print(f"Error: Resume not found at {resume_path}")
            return

        from app.tools.jdp_parser import extract_text_from_pdf
        from app.agents.evaluator import EvaluationAgent

        resume_text = extract_text_from_pdf(resume_path)
        evaluator = EvaluationAgent()
        evaluation = evaluator.evaluate(resume_text, jd_text)

        output_path = _resolve_path(kwargs.get("output"), settings.evaluation_path)
        _write_json(output_path, evaluation)

        print("Evaluation Results:")
        print(f"  ATS Match: {evaluation.get('ats_match_percent', 0)}%")
        print(f"  Relevance: {evaluation.get('relevance_percent', 0)}%")
        print(f"  Factuality: {evaluation.get('factuality_score', 0)}")
        print(f"  Flags: {len(evaluation.get('flags', []))} unsupported claims")
        print(f"  Written to: {output_path}")

        if evaluation.get("flags"):
            for flag in evaluation["flags"][:3]:
                print(f"    - {flag.get('claim', 'Unknown claim')[:80]}...")

    elif task == "revise":
        eval_path = _resolve_path(kwargs.get("eval_path"), settings.evaluation_path)
        tailoring_path = _resolve_path(
            kwargs.get("tailoring_path"),
            settings.tailoring_report_path,
        )
        max_revisions = int(kwargs.get("max_revisions", 3))

        if not eval_path.exists():
            print(f"Error: Evaluation file not found at {eval_path}")
            return

        if not tailoring_path.exists():
            print(f"Error: Tailoring file not found at {tailoring_path}")
            return

        with eval_path.open(encoding="utf-8") as f:
            evaluation = json.load(f)

        from app.agents.revisor import RevisionAgent

        revisor = RevisionAgent()
        revision_log = revisor.revise(evaluation, max_revisions=max_revisions)

        output_path = _resolve_path(kwargs.get("output"), settings.revision_log_path)
        _write_json(output_path, revision_log)

        print("Revision Complete!")
        print(f"  Status: {revision_log.get('status')}")
        print(f"  Steps: {len(revision_log.get('revisions', []))}")
        print(f"  Final ATS: {revision_log.get('final_ats', 0)}%")
        print(f"  Final Relevance: {revision_log.get('final_relevance', 0)}%")
        print(f"  Final Factuality: {revision_log.get('final_factuality', 100)}")
        print(f"  Written to: {output_path}")

    elif task == "reports":
        tailoring_path = _resolve_path(
            kwargs.get("tailoring_path"),
            settings.tailoring_report_path,
        )
        revisions_path = _resolve_path(
            kwargs.get("revisions_path"),
            settings.revision_log_path,
        )

        if not tailoring_path.exists():
            print(f"Error: Tailoring file not found at {tailoring_path}")
            return

        if not revisions_path.exists():
            print(f"Error: Revision file not found at {revisions_path}")
            return

        with tailoring_path.open(encoding="utf-8") as f:
            tailoring = json.load(f)
        with revisions_path.open(encoding="utf-8") as f:
            revisions = json.load(f)

        from app.tools.reports import generate_human_report, generate_machine_report

        human_report = generate_human_report(tailoring, revisions)
        evidence = generate_machine_report(tailoring, revisions)

        evidence_path = _resolve_path(kwargs.get("output"), settings.evidence_report_path)
        human_path = _resolve_path(kwargs.get("human_output"), settings.change_report_path)

        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        human_path.write_text(human_report, encoding="utf-8")
        _write_json(evidence_path, evidence)

        print("=" * 60)
        print("HUMAN-READABLE REPORT")
        print("=" * 60)
        print(human_report)
        print("=" * 60)
        print(f"\nMachine-readable report written to {evidence_path}")
        print(f"Human-readable report written to {human_path}")

    else:
        print(f"Unknown task: {task}")
        print("Available tasks: parse, tailor, evaluate, revise, reports")


def main() -> None:
    print("=" * 60)
    print("Resume Tailoring System - Agentic AI")
    print("=" * 60)
    print("\nSystem Configuration:")
    print(f"  - LLM Model: {settings.llm_model}")
    print(f"  - TAVILY API: {'Configured' if settings.tavily_api_key else 'Not configured'}")
    print(f"  - Base Directory: {settings.base_dir}")
    print(f"  - Storage Directory: {settings.storage_dir}")
    print(f"  - Role KB: {settings.role_kb_path}")
    print("\nQuickstart Commands:")
    print('  1. Parse JD:     python3 -m app.main --task parse --jd "Your JD text"')
    print("  2. Tailor Resume:python3 -m app.main --task tailor --resume Resumes/ShaunakMishra_Resume.pdf --role SWE")
    print("  3. Evaluate:     python3 -m app.main --task evaluate --resume storage/tailored_resume.pdf --jd \"JD text\"")
    print("  4. Revise:       python3 -m app.main --task revise")
    print("  5. Reports:      python3 -m app.main --task reports")
    print("  6. Dashboard:    streamlit run dashboard.py")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--task":
        task_arg = sys.argv[2] if len(sys.argv) > 2 else ""
        task_kwargs: dict[str, Any] = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:].replace("-", "_")
                if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                    task_kwargs[key] = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        run_task(task_arg, **task_kwargs)
    else:
        main()
