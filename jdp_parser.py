#!/usr/bin/env python3
"""Root wrapper for the JD parser CLI (logic lives in app.tools.jdp_parser).

Run: ``python3 jdp_parser.py --jd "..."``  or  ``python3 -m app.main``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# Legacy library API (kept for direct imports, e.g. tests/test_basic.py).
from app.tools.jdp_parser import (  # noqa: F401
    build_role_kb,
    parse_preferred_skills,
    parse_required_skills,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Job Description Parser")
    parser.add_argument("--jd", type=str, help="Job description text")
    parser.add_argument("--jd-file", type=Path, help="Job description PDF file")
    parser.add_argument("--title", type=str, default="Unknown Role", help="Role title")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path")
    parser.add_argument("--output", type=Path, default=Path("role_kb.json"), help="Output KB file")
    parser.add_argument("--use-tavily", action="store_true", help="Ignored: Tavily enrichment not required")
    args = parser.parse_args()

    from app.tools.jdp_parser import extract_text_from_pdf

    jd_text = args.jd or ""
    if not jd_text and args.jd_file:
        jd_text = extract_text_from_pdf(args.jd_file)

    kb = build_role_kb(title=args.title, jd_text=jd_text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(kb, indent=2), encoding="utf-8")
    print(f"Role KB written to {args.output}")
    print(f"  title:             {kb['title']}")
    print(f"  required_skills:   {kb['required_skills']}")
    print(f"  preferred_skills:  {kb['preferred_skills']}")


if __name__ == "__main__":
    main()
