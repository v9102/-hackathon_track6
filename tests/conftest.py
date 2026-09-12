"""Shared pytest fixtures and path configuration for the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure absolute imports (`from app...`) resolve in CI and local runs.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
