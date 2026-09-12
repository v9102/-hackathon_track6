"""Root convenience wrapper around the authoritative Streamlit dashboard.

Run: ``streamlit run dashboard.py`` or ``streamlit run app/dashboard.py``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make sure the project root is on sys.path before importing app.dashboard.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app.dashboard as _dashboard  # noqa: F401 (triggers the dashboard UI)