#!/usr/bin/env python3
"""Root wrapper for the revisor CLI (logic lives in app.agents.revisor).

Run: ``python3 revisor.py --eval evaluation.json ...`` or ``python3 -m app.main``
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


# Legacy library API (kept for direct imports, e.g. tests/test_basic.py).
def load_evaluation(eval_path: Path) -> dict[str, Any]:
    """Load an evaluation JSON file produced by the evaluator."""
    return json.loads(eval_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Revisor (delegates to app.agents.revisor)")
    parser.add_argument("--eval", type=Path, required=True, help="Evaluation JSON file")
    parser.add_argument("--tailoring", type=Path, required=False, help="Tailoring report JSON")
    parser.add_argument("--resumes-dir", type=Path, help="Unused in the agentic loop")
    parser.add_argument("--max-revisions", type=int, default=3, help="Max revisions")
    parser.add_argument("--env", type=Path, default=Path(".env"), help="Env file path (unused)")
    parser.add_argument("--output", type=Path, default=Path("revision_log.json"), help="Output JSON")
    args = parser.parse_args()

    from app.agents.revisor import RevisionAgent

    evaluation = json.loads(args.eval.read_text(encoding="utf-8"))
    log = RevisionAgent().revise(evaluation, max_revisions=args.max_revisions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Status: {log.get('status')} (revisions: {len(log.get('revisions', []))})")
    print(f"Written to: {args.output}")


if __name__ == "__main__":
    main()
