"""Root convenience wrapper around the authoritative ``app.main`` entry point.

Run: ``python3 main.py`` or ``python3 -m app.main``.
"""

from __future__ import annotations

import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())