"""Central agent state for the autonomous resume agent.

The state persists for the whole run and answers the questions a judge would
ask: what is the goal, which resume was chosen and why, what evidence exists,
what problems were found, what actions were taken, whether a change improved
the artifact, and whether the agent should continue or stop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.models import StructuredResume


@dataclass
class ResumeCandidate:
    """A candidate resume under consideration."""

    name: str
    path: str
    full_text: str
    skills: set[str] = field(default_factory=set)
    selection_score: float = 0.0
    evidence_count: int = 0
    reasoning: str = ""


@dataclass
class DecisionRecord:
    """One recorded decision/action adaptation in the agent's audit trail."""

    iteration: int
    decision: str
    reason: str
    action: str
    target: str
    before: str
    after: str
    evidence: str
    accepted: bool = True
    rollback_reason: str = ""
    evaluation_before: dict[str, float] = field(default_factory=dict)
    evaluation_after: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "decision": self.decision,
            "reason": self.reason,
            "action": self.action,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "evidence": self.evidence,
            "accepted": self.accepted,
            "rollback_reason": self.rollback_reason,
            "evaluation_before": self.evaluation_before,
            "evaluation_after": self.evaluation_after,
        }


@dataclass
class RunState:
    """Persistent state for a single autonomous tailoring run."""

    run_id: str = ""
    goal: str = ""
    jd_text: str = ""
    role_kb: dict[str, Any] = field(default_factory=dict)
    candidates: list[ResumeCandidate] = field(default_factory=list)
    selected_resume: ResumeCandidate | None = None
    evidence_map: dict[str, Any] = field(default_factory=dict)
    structured_resume: StructuredResume | None = None
    current_artifact: str = ""
    iteration: int = 0
    max_iterations: int = 3
    evaluation_history: list[dict[str, Any]] = field(default_factory=list)
    current_evaluation: dict[str, Any] = field(default_factory=dict)
    decisions: list[DecisionRecord] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    verification: dict[str, Any] = field(default_factory=dict)
    final_status: str = ""
    run_dir: str = ""

    # ------------------------------------------------------------------ #
    def iteration_metrics(self) -> dict[str, float]:
        """Latest aggregate metrics (0.0 when none yet)."""
        if not self.current_evaluation:
            return {"ats": 0.0, "relevance": 0.0, "factuality": 0.0, "format": 0.0}
        return {
            "ats": float(self.current_evaluation.get("ats_score", 0)),
            "relevance": float(self.current_evaluation.get("relevance_score", 0)),
            "factuality": float(self.current_evaluation.get("factuality_score", 0)),
            "format": float(self.current_evaluation.get("format_score", 0)),
        }

    # ------------------------------------------------------------------ #
    def set_run_dir(self) -> None:
        """Create the run directory and persist the state snapshot."""
        if not self.run_id:
            import uuid

            self.run_id = uuid.uuid4().hex[:8]
        run_dir = settings.runs_dir / self.run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self.run_dir = str(run_dir)

    def persist(self) -> Path:
        """Write the current state to storage/runs/<run_id>/state.json."""
        if not self.run_dir:
            self.set_run_dir()
        payload = self.to_dict()
        state_path = Path(self.run_dir) / "state.json"
        state_path.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
        return state_path

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "jd_text": self.jd_text,
            "role_kb": self.role_kb,
            "candidates": [
                {
                    "name": c.name,
                    "path": c.path,
                    "selection_score": c.selection_score,
                    "evidence_count": c.evidence_count,
                    "skills": sorted(c.skills),
                    "reasoning": c.reasoning,
                }
                for c in self.candidates
            ],
            "selected_resume": (
                {
                    "name": self.selected_resume.name,
                    "path": self.selected_resume.path,
                    "selection_score": self.selected_resume.selection_score,
                    "reasoning": self.selected_resume.reasoning,
                }
                if self.selected_resume
                else None
            ),
            "evidence_map": self.evidence_map,
            "structured_resume": (
                self.structured_resume.to_dict() if self.structured_resume else None
            ),
            "current_artifact": self.current_artifact,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "evaluation_history": self.evaluation_history,
            "current_evaluation": self.current_evaluation,
            "decisions": [d.to_dict() for d in self.decisions],
            "actions": self.actions,
            "verification": self.verification,
            "final_status": self.final_status,
            "run_dir": self.run_dir,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RunState:
        state = cls(
            run_id=str(payload.get("run_id", "")),
            goal=str(payload.get("goal", "")),
            jd_text=str(payload.get("jd_text", "")),
            role_kb=payload.get("role_kb", {}),
            evidence_map=payload.get("evidence_map", {}),
            current_artifact=str(payload.get("current_artifact", "")),
            iteration=int(payload.get("iteration", 0)),
            max_iterations=int(payload.get("max_iterations", 3)),
            evaluation_history=payload.get("evaluation_history", []),
            current_evaluation=payload.get("current_evaluation", {}),
            actions=payload.get("actions", []),
            verification=payload.get("verification", {}),
            final_status=str(payload.get("final_status", "")),
            run_dir=str(payload.get("run_dir", "")),
        )
        state.candidates = [
            ResumeCandidate(
                name=str(c.get("name", "")),
                path=str(c.get("path", "")),
                full_text=str(c.get("full_text", "")),
                skills=set(c.get("skills", [])),
                selection_score=float(c.get("selection_score", 0)),
                evidence_count=int(c.get("evidence_count", 0)),
                reasoning=str(c.get("reasoning", "")),
            )
            for c in payload.get("candidates", [])
        ]
        selected = payload.get("selected_resume")
        if selected:
            for cand in state.candidates:
                if cand.name == selected.get("name"):
                    state.selected_resume = cand
                    state.selected_resume.selection_score = float(
                        selected.get("selection_score", 0)
                    )
                    state.selected_resume.reasoning = str(
                        selected.get("reasoning", "")
                    )
        if payload.get("structured_resume"):
            state.structured_resume = StructuredResume.from_dict(
                payload["structured_resume"]
            )
        state.decisions = [
            DecisionRecord(**d)
            for d in payload.get("decisions", [])
        ]
        return state