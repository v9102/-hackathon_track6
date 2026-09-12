"""Resume Tailoring System - Agentic AI Package.

A production-grade modular monorepo for automated, truthful resume tailoring.

Key Features:
- LaTeX template compliance (provided format)
- No content fabrication (truth-first approach)
- Factual consistency cross-checking
- Automated revision loop (up to 3 iterations)
- Pydantic Settings for configuration
- Absolute imports starting with 'app.'
- Path independence via pathlib.Path
- Streamlit dashboard for web access
"""

# Package version
__version__ = "2.0.0"

# Re-export key components for convenience
from app.core.config import settings
from app.agents import TailorAgent, EvaluationAgent, RevisionAgent
from app.tools.jdp_parser import (
    parse_required_skills,
    parse_preferred_skills,
    parse_years_exp,
    parse_degree_req,
    parse_tools_tech,
    parse_responsibilities,
    build_role_kb,
)

__all__ = [
    "__version__",
    "settings",
    "TailorAgent",
    "EvaluationAgent",
    "RevisionAgent",
    "parse_required_skills",
    "parse_preferred_skills",
    "parse_years_exp",
    "parse_degree_req",
    "parse_tools_tech",
    "parse_responsibilities",
    "build_role_kb",
]