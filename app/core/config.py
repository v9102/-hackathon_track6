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