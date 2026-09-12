"""Resume Tailoring System - Main Entry Point.

Usage:
    python3 jdp_parser.py --jd "Job description text"
    python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf --role SWE --kb role_kb.json
    python3 evaluate_resume.py --resume tailored_resume.pdf --kb role_kb.json --jd "JD text"
    python3 revisor.py --eval evaluation.json --tailoring tailoring_report_resume.json --resumes-dir Resumes
    python3 change_report.py --tailoring tailoring_report_resume.json --revisions revision_log.json
    streamlit run dashboard.py
"""

from change_report import main as change_report_main
from evaluate_resume import main as evaluate_resume_main
from jdp_parser import main as jdp_parser_main
from resume_tailor import main as resume_tailor_main
from revisor import main as revisor_main

__all__ = [
    "change_report_main",
    "evaluate_resume_main",
    "jdp_parser_main",
    "resume_tailor_main",
    "revisor_main",
]