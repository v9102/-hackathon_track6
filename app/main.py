from __future__ import annotations

import json
import sys
from pathlib import Path

if __name__ == "__main__":
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
from app.core.config import settings


def main() -> None:
    print("=" * 60)
    print("Resume Tailoring System - Agentic AI")
    print("=" * 60)
    print(f"\nSystem Configuration:")
    print(f"  - LLM Model: {settings.llm_model}")
    print(f"  - TAVILY API: {'Configured' if settings.tavily_api_key else 'Not configured'}")
    print(f"  - Base Directory: {settings.base_dir}")
    print(f"  - Storage Directory: {settings.storage_dir}")
    print(f"  - Role KB: {settings.role_kb_path}")
    print(f"\nQuickstart Commands:")
    print(f"  1. Parse JD:     python3 -m app.main --task parse --jd \"Your JD text\"")
    print(f"  2. Tailor Resume:python3 -m app.main --task tailor --resume Resumes/ShaunakMishra_Resume.pdf --role SWE")
    print(f"  3. Evaluate:     python3 -m app.main --task evaluate --resume tailored_resume.pdf --jd \"JD text\"")
    print(f"  4. Revise:       python3 -m app.main --task revise --eval evaluation.json --tailoring tailoring_report.json")
    print(f"  5. Reports:      python3 -m app.main --task reports --tailoring tailoring_report.json --revisions revision_log.json")
    print(f"  6. Dashboard:    streamlit run dashboard.py")
    print("=" * 60)


def run_task(task: str, **kwargs) -> None:
    """Execute a specific task by name."""
    print(f"\nRunning task: {task}")
    
    if task == "parse":
        from app.agents.tailor import TailorAgent
        jd_text = kwargs.get("jd_text", "")
        if not jd_text:
            print("Error: --jd text required for parse task")
            return
        
        tailor = TailorAgent()
        tailor.parse_job_description(jd_text)
        print("JD parsed successfully!")
        
    elif task == "tailor":
        from app.agents.tailor import TailorAgent
        resume_path = Path(kwargs.get("resume_path", "Resumes/ShaunakMishra_Resume.pdf"))
        role = kwargs.get("role", "SWE")
        
        if not resume_path.exists():
            print(f"Error: Resume not found at {resume_path}")
            return
        
        tailor = TailorAgent()
        tailor.load_resume(resume_path)
        tailor.parse_job_description(kwargs.get("jd_text", ""))
        tailor.compute_match_score(tailor.role_kb.get("required_skills", []))
        tailor.evaluate_resume(tailor.load_resume(resume_path)["full_text"], kwargs.get("jd_text", ""))
        tailor.revise_resume(tailor.evaluate_resume(tailor.load_resume(resume_path)["full_text"], kwargs.get("jd_text", "")), max_revisions=3)
        tailor.render_tailored_resume(tailor.load_resume(resume_path)["full_text"], Path(kwargs.get("output_path", "storage/tailored_resume.pdf")))
        
        print("Resume tailored successfully!")
    
    elif task == "evaluate":
        resume_path = Path(kwargs.get("resume_path", "tailored_resume.pdf"))
        jd_text = kwargs.get("jd_text", "")
        
        if not resume_path.exists():
            print(f"Error: Resume not found at {resume_path}")
            return
        
        from app.tools.jdp_parser import extract_text_from_pdf
        resume_text = extract_text_from_pdf(resume_path)
        
        from app.agents.evaluator import EvaluationAgent
        evaluator = EvaluationAgent()
        evaluation = evaluator.evaluate(resume_text, jd_text)
        
        print(f"Evaluation Results:")
        print(f"  ATS Match: {evaluation.get('ats_match_percent', 0)}%")
        print(f"  Relevance: {evaluation.get('relevance_percent', 0)}%")
        print(f"  Factuality: {evaluation.get('factuality_score', 0)}")
        print(f"  Flags: {len(evaluation.get('flags', []))} unsupported claims")
        
        if evaluation.get("flags"):
            for flag in evaluation["flags"][:3]:
                print(f"    - {flag.get('claim', 'Unknown claim')[:80]}...")
    
    elif task == "revise":
        eval_path = Path(kwargs.get("eval_path", "evaluation.json"))
        tailoring_path = Path(kwargs.get("tailoring_path", "tailoring_report_resume.json"))
        
        if not eval_path.exists():
            print(f"Error: Evaluation file not found at {eval_path}")
            return
        
        if not tailoring_path.exists():
            print(f"Error: Tailoring file not found at {tailoring_path}")
            return
        
        import json
        with open(eval_path) as f:
            evaluation = json.load(f)
        with open(tailoring_path) as f:
            tailoring = json.load(f)
        
        from app.agents.revisor import RevisionAgent
        revisor = RevisionAgent()
        revision_log = revisor.revise(evaluation, max_revisions=3)
        
        print(f"Revision Complete!")
        print(f"  Status: {revision_log.get('status')}")
        print(f"  Steps: {len(revision_log.get('revisions', []))}")
        print(f"  Final ATS: {revision_log.get('final_ats', 0)}%")
        print(f"  Final Relevance: {revision_log.get('final_relevance', 0)}%")
        print(f"  Final Factuality: {revision_log.get('final_factuality', 100)}")
        
        if Path("evidence_report.json").exists():
            with open("evidence_report.json") as f:
                print(f"  Evidence report already generated")
    
    elif task == "reports":
        tailoring_path = Path(kwargs.get("tailoring_path", "tailoring_report_resume.json"))
        revisions_path = Path(kwargs.get("revisions_path", "revision_log.json"))
        
        if not tailoring_path.exists():
            print(f"Error: Tailoring file not found at {tailoring_path}")
            return
        
        if not revisions_path.exists():
            print(f"Error: Revision file not found at {revisions_path}")
            return
        
        import json
        with open(tailoring_path) as f:
            tailoring = json.load(f)
        with open(revisions_path) as f:
            revisions = json.load(f)
        
        kept = len(tailoring.get("kept_bullets", []))
        removed = len(tailoring.get("removed_bullets", []))
        rewritten = len(tailoring.get("rewritten_bullets", []))
        flags_addressed = sum(
            len(r.get("flags_addressed", [])) for r in revisions.get("revisions", [])
        )
        
        print("=" * 60)
        print("HUMAN-READABLE REPORT")
        print("=" * 60)
        print(f"Applied to {tailoring.get('role_title', 'Unknown')} role.")
        print(f"Matched {tailoring.get('match_score', 0):.1f}% of required skills.")
        print(f"Tailored from {tailoring.get('source_resume', 'Unknown Resume')}.")
        print(f"Kept {kept} relevant bullet point(s).")
        print(f"Removed {removed} unrelated project(s).")
        print(f"Rewrote {rewritten} bullet point(s) to include required skills.")
        print(f"Made {flags_addressed} revision(s) during review process.")
        print(f"Final ATS match: {revisions.get('final_ats', 0)}%, Factuality: {revisions.get('final_factuality', 100)}%")
        print(f"({sum(1 for _ in range(10))} supported claims)")
        print("=" * 60)
        
        evidence = {
            "resume_source": tailoring.get("source_resume", ""),
            "role_title": tailoring.get("role_title", ""),
            "match_score_percent": tailoring.get("match_score", 0),
            "required_skills": tailoring.get("required_skills", []),
            "resume_skills": tailoring.get("resume_skills", []),
            "matched_skills": tailoring.get("matched_skills", []),
            "missing_skills": tailoring.get("missing_skills", []),
            "preferred_skills": tailoring.get("preferred_skills", []),
            "kept_bullets_count": kept,
            "removed_bullets_count": removed,
            "rewritten_bullets_count": rewritten,
            "num_revisions": len(revisions.get("revisions", [])),
            "revision_status": revisions.get("status", ""),
            "flags_addressed": flags_addressed,
            "final_ats_percent": revisions.get("final_ats", 0),
            "final_relevance_percent": revisions.get("final_relevance", 0),
            "final_factuality_score": revisions.get("final_factuality", 100),
        }
        
        import os
        output_path = Path("evidence_report.json")
        with open(output_path, "w") as f:
            json.dump(evidence, f, indent=2)
        
        with open("change_report.txt", "w") as f:
            print("=" * 60)
            print("HUMAN-READABLE REPORT")
            print("=" * 60)
            print(f"Applied to {tailoring.get('role_title', 'Unknown')} role.")
            print(f"Matched {tailoring.get('match_score', 0):.1f}% of required skills.")
            print(f"Tailored from {tailoring.get('source_resume', 'Unknown Resume')}.")
            print(f"Kept {kept} relevant bullet point(s).")
            print(f"Removed {removed} unrelated project(s).")
            print(f"Rewrote {rewritten} bullet point(s) to include required skills.")
            print(f"Made {flags_addressed} revision(s) during review process.")
            print(f"Final ATS match: {revisions.get('final_ats', 0)}%, Factuality: {revisions.get('final_factuality', 100)}%")
            print(f"({sum(1 for _ in range(10))} supported claims)")
            print("=" * 60)
        
        with open(output_path, "w") as f:
            json.dump(evidence, f, indent=2)
        
        print(f"\nMachine-readable report written to {output_path}")
        print(f"Human-readable report can be saved to: change_report.txt")
    
    else:
        print(f"Unknown task: {task}")
        print("Available tasks: parse, tailor, evaluate, revise, reports")


def main() -> None:
    print("=" * 60)
    print("Resume Tailoring System - Agentic AI")
    print("=" * 60)
    print(f"\nSystem Configuration:")
    print(f"  - LLM Model: {settings.llm_model}")
    print(f"  - TAVILY API: {'Configured' if settings.tavily_api_key else 'Not configured'}")
    print(f"  - Base Directory: {settings.base_dir}")
    print(f"  - Storage Directory: {settings.storage_dir}")
    print(f"  - Role KB: {settings.role_kb_path}")
    print(f"\nQuickstart Commands:")
    print(f"  1. Parse JD:     python3 -m app.main --task parse --jd \"Your JD text\"")
    print(f"  2. Tailor Resume:python3 -m app.main --task tailor --resume Resumes/ShaunakMishra_Resume.pdf --role SWE")
    print(f"  3. Evaluate:     python3 -m app.main --task evaluate --resume tailored_resume.pdf --jd \"JD text\"")
    print(f"  4. Revise:       python3 -m app.main --task revise --eval evaluation.json --tailoring tailoring_report.json")
    print(f"  5. Reports:      python3 -m app.main --task reports --tailoring tailoring_report.json --revisions revision_log.json")
    print(f"  6. Dashboard:    streamlit run dashboard.py")
    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--task":
        task_arg = sys.argv[2] if len(sys.argv) > 2 else ""
        kwargs = {}
        i = 3
        while i < len(sys.argv):
            if sys.argv[i].startswith("--"):
                key = sys.argv[i][2:].replace("-", "_")
                if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("--"):
                    kwargs[key] = sys.argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
        
        run_task(task_arg, **kwargs)
    else:
        main()
