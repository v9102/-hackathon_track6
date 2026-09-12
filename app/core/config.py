"""Configuration management using Pydantic Settings.

Provides validated environment variables for the Resume Tailoring System.
Ensures path independence across Linux, macOS, and Windows production servers.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production settings for the Resume Tailoring System."""
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # API Keys
    tavily_api_key: str | None = os.getenv("TAVILY_API_KEY")
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")

    # LLM Configuration
    llm_model: str = "gpt-4o-mini"
    temperature: float = 0.0

    # Agent loop configuration
    max_iterations: int = 3
    target_ats: float = 80.0
    target_relevance: float = 80.0
    requires_full_factuality: bool = True
    min_format_score: float = 80.0

    # File Paths - Absolute via pathlib
    @property
    def base_dir(self) -> Path:
        """Base directory for the application."""
        return Path(__file__).resolve().parent.parent.parent

    @property
    def data_dir(self) -> Path:
        """Data directory for role KB and static files."""
        return self.base_dir / "data"

    @property
    def storage_dir(self) -> Path:
        """Runtime output directory (gitignored)."""
        return self.base_dir / "storage"

    @property
    def resume_dir(self) -> Path:
        """Resume source directory."""
        return self.base_dir / "Resumes"

    @property
    def reports_dir(self) -> Path:
        """Generated reports directory within storage."""
        return self.storage_dir / "reports"

    @property
    def runs_dir(self) -> Path:
        """Per-run artifact sandbox: storage/runs/<run_id>/."""
        return self.storage_dir / "runs"

    @property
    def assets_dir(self) -> Path:
        """Base document templates directory."""
        return self.base_dir / "app" / "assets"

    @property
    def default_jd_path(self) -> Path:
        """Sample JD for demo runs."""
        return self.base_dir / "data" / "sample_jd.txt"

    @property
    def default_template_path(self) -> Path:
        """LaTeX template reused for rendering (base_dir)."""
        return self.base_dir / "ShaunakMishra_Resume.tex"

    # Derived paths
    @property
    def role_kb_path(self) -> Path:
        """Path to role knowledge base."""
        return self.data_dir / "role_kb.json"

    @property
    def tailored_resume_path(self) -> Path:
        """Path for tailored resume PDF."""
        return self.storage_dir / "tailored_resume.pdf"

    @property
    def evaluation_path(self) -> Path:
        """Path for evaluation JSON."""
        return self.storage_dir / "evaluation.json"

    @property
    def revision_log_path(self) -> Path:
        """Path for revision log JSON."""
        return self.storage_dir / "revision_log.json"

    @property
    def tailoring_report_path(self) -> Path:
        """Path for tailoring report JSON."""
        return self.storage_dir / "tailoring_report_resume.json"

    @property
    def change_report_path(self) -> Path:
        """Path for change report TXT."""
        return self.storage_dir / "change_report.txt"

    @property
    def evidence_report_path(self) -> Path:
        """Path for machine-readable evidence report JSON."""
        return self.storage_dir / "evidence_report.json"

    @property
    def parsed_role_kb_path(self) -> Path:
        """Path for runtime-parsed role KB (written during JD parse)."""
        return self.storage_dir / "role_kb.json"

    def ensure_storage(self) -> Path:
        """Create storage directory if missing and return its path."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        return self.storage_dir


# Singleton instance
settings = Settings()


def get_path(filename: str, subdir: str = "reports") -> Path:
    """Get a path relative to the storage directory.
    
    Args:
        filename: Name of the file
        subdir: Subdirectory within storage (default: "reports")
    
    Returns:
        Full path to the file in storage directory
    """
    return settings.storage_dir / subdir / filename