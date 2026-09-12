"""Agents Package - Reasoning & Coordination Layer.

This package contains the autonomous agents that form the core of the
Resume Tailoring System. Each agent is designed to be:
- Stateless where possible
- Testable with deterministic inputs/outputs
- Composable within the orchestration framework
- Interchangeable without breaking the pipeline
"""

from __future__ import annotations

from app.agents.tailor import TailorAgent
from app.agents.evaluator import EvaluationAgent
from app.agents.revisor import RevisionAgent

__all__ = ["TailorAgent", "EvaluationAgent", "RevisionAgent"]