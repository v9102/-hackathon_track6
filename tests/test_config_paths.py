"""Contract tests for app.core.config path resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings


class TestBaseDirResolution:
    def test_env_override_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RESUME_AGENT_BASE_DIR", "/tmp/custom-base")
        assert Settings().base_dir == Path("/tmp/custom-base")

    def test_repo_marker_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RESUME_AGENT_BASE_DIR", raising=False)
        base = Settings().base_dir
        assert (base / "pyproject.toml").exists()
        assert (base / "app").is_dir()