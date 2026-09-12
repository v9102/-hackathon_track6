#!/usr/bin/env python3
"""Root wrapper for the resume tailor CLI (logic lives in app.agents.planner).

Run: ``python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf ...``
or, preferably: ``python3 -m app.main``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Resume Tailor (delegates to app.agents.planner)")
    parser.add_argument("--resume", type=Path, required=True, help="Resume PDF file")
    parser.add_argument("--role", type=str, required=True, help="Target role (ignored; JD derived from KB)")
    parser.add_argument("--kb", type=Path, required=True, help="Role KB JSON file")
    parser.add_argument("--template", type=Path, required=False, help="LaTeX template file")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path (unused)")
    parser.add_argument("--output", type=Path, default=Path("tailored_resume.tex"), help="Output path (unused)")
    args = parser.parse_args()

    from app.agents.planner import AgenticPlanner

    kb = json.loads(args.kb.read_text(encoding="utf-8"))
    required = kb.get("required_skills", [])
    preferred = kb.get("preferred_skills", [])
    title = kb.get("title", args.role)
    jd_text = (
        f"{title}\n\nRequired skills: {', '.join(required)}\n"
        f"Preferred skills: {', '.join(preferred)}\n"
    )
    if kb.get("responsibilities"):
        jd_text += "Responsibilities:\n" + "\n".join(f"- {r}" for r in kb["responsibilities"]) + "\n"

    planner = AgenticPlanner()
    state = planner.run(jd_text=jd_text, resume_files=[Path(args.resume)],
                        template_path=Path(args.template) if args.template else None)
    print(f"Run {state.run_id} ({state.final_status})")
    print(f"Artifacts: {state.run_dir}")


if __name__ == "__main__":
    main()
