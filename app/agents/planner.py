"""Agentic Planner - orchestrates the full autonomous tailoring loop.

Goal -> Decision -> Action -> Intermediate result -> Evaluation -> Adaptation
-> Action -> Re-evaluation -> Final verification -> Outcome.

The planner is the single driver of the system:

1. Parse the JD into a role KB and record the goal.
2. Inspect *every* candidate resume, score them and select the best one.
3. Build an evidence map from the candidate's ORIGINAL resume (ground truth).
4. In a loop: surface supported evidence -> render a real PDF -> re-evaluate the
   actual rendered artifact -> decide the next action -> reject unsupported
   proposals -> roll back regressions -> continue until targets are met or no
   evidence-based improvement remains.
5. Verify the final artifact and persist all artifacts + an honest audit trail
   into ``storage/runs/<run_id>/``.
"""

from __future__ import annotations

import copy
import json
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.agents.evaluator import EvaluationAgent
from app.agents.revisor import RevisionAgent
from app.agents.selector import ResumeSelector, load_candidate_resumes
from app.agents.tailor import tailor_remove_skills, tailor_surface
from app.core.config import settings
from app.core.state import DecisionRecord, RunState
from app.tools.evidence import build_evidence_map, evidence_for_skill
from app.tools.jdp_parser import build_role_kb
from app.tools.latex_renderer import check_pdf_artifact, render_pdf
from app.tools.skills import extract_canonical_skills, normalize_skill

_DEFAULT_JD = """Full Stack Software Engineer

We are building AI-powered productivity tools and need a Full Stack Engineer who can
ship end-to-end features.

Required skills: Python, React, Node.js, JavaScript, TypeScript, SQL, PostgreSQL,
Docker, Git.

Preferred skills: Azure, AWS, Kubernetes, Next.js, React Native.

Nice-to-have: GraphQL, Kafka.

Responsibilities:
- Design and implement backend services and APIs
- Build responsive front-end interfaces
- Write and maintain database schemas
- Containerize and deploy services
"""


def _metrics(evaluation: dict[str, Any]) -> dict[str, float]:
    return {
        "ats": float(evaluation.get("ats_match_percent", 0.0)),
        "relevance": float(evaluation.get("relevance_percent", 0.0)),
        "factuality": float(evaluation.get("factuality_score", 0.0)),
        "format": float(evaluation.get("format_score") or 0.0),
    }


def canonicalize_required(role_kb: dict[str, Any]) -> list[str]:
    from app.tools.skills import canonicalize_list

    return sorted(canonicalize_list(role_kb.get("required_skills", [])))


def _skill_lacks_evidence(
    evidence_map: dict[str, Any], skill: str
) -> bool:
    """True when the candidate has no authentic, supported evidence for ``skill``."""
    from app.tools.evidence import evidence_for_skill

    ev = evidence_for_skill(evidence_map, skill)
    return ev is None or not ev.supported


def _worse(a: dict[str, float], b: dict[str, float]) -> bool:
    """True when switching metrics ``b`` for ``a`` is a regression."""
    for key in ("ats", "relevance", "factuality", "format"):
        if b.get(key, 0.0) < a.get(key, 0.0) - 1e-9:
            return True
    return False


class AgenticPlanner:
    """Autonomous agent that takes a resume from baseline to target."""

    def __init__(self) -> None:
        self.evaluator = EvaluationAgent()
        self.revisor = RevisionAgent()
        self.selector = ResumeSelector()

    # ------------------------------------------------------------------ #
    def _acceptance_met(
        self, evaluation: dict[str, Any]
    ) -> tuple[bool, str | None]:
        ats = float(evaluation.get("ats_match_percent", 0.0))
        relevance = float(evaluation.get("relevance_percent", 0.0))
        factuality = float(evaluation.get("factuality_score", 0.0))
        fmt = evaluation.get("format_score")
        if fmt is None:
            return False, "format_score is unavailable"

        reasons: list[str] = []
        if ats < settings.target_ats:
            reasons.append(f"ATS {ats:.1f} < {settings.target_ats:.0f}")
        if relevance < settings.target_relevance:
            reasons.append(f"Relevance {relevance:.1f} < {settings.target_relevance:.0f}")
        if settings.requires_full_factuality and factuality < 100:
            reasons.append(f"Factuality {factuality:.1f} < 100")
        if fmt < settings.min_format_score:
            reasons.append(f"Format {fmt:.1f} < {settings.min_format_score:.0f}")
        if evaluation.get("unsupported_claims"):
            reasons.append("Unsupported claims remain")
        if reasons:
            return False, "; ".join(reasons)
        return True, None

    # ------------------------------------------------------------------ #
    def _record_decision(
        self,
        state: RunState,
        iteration: int,
        decision: dict[str, Any],
        *,
        accepted: bool,
        before: str,
        after: str,
        evidence: str,
        eval_before: dict[str, float],
        eval_after: dict[str, float],
        rollback_reason: str = "",
        decision_title: str | None = None,
        decision_reason: str | None = None,
        target_value: str | None = None,
    ) -> None:
        record = DecisionRecord(
            iteration=iteration,
            decision=decision_title or str(decision.get("decision", "")),
            reason=decision_reason or str(decision.get("reason", "")),
            action=str(decision.get("action", "")),
            target=target_value if target_value is not None else str(decision.get("target") or ""),
            before=before,
            after=after,
            evidence=evidence,
            accepted=accepted,
            rollback_reason=rollback_reason,
            evaluation_before=eval_before,
            evaluation_after=eval_after,
        )
        state.decisions.append(record)
        state.actions.append(record.action)
        state.persist()

    # ------------------------------------------------------------------ #
    def _evaluate_artifact(
        self,
        state: RunState,
        resume: Any,
        pdf_path: Path | None,
        artifact_text: str = "",
    ) -> dict[str, Any]:
        role_kb = state.role_kb
        text = artifact_text or resume.full_text()
        return self.evaluator.evaluate_agentic(
            resume,
            role_kb,
            self._evidence_objects(state),
            artifact_text=text,
            artifact_path=pdf_path,
        )

    @staticmethod
    def _evidence_objects(state: RunState) -> dict[str, Any]:
        from app.tools.evidence import SkillEvidence

        payload = state.evidence_map
        if payload and next(iter(payload.values())).get("supported") is not None:
            return {
                k: SkillEvidence(**v)
                for k, v in payload.items()
                if isinstance(v, dict)
            }
        return {}

    # ------------------------------------------------------------------ #
    def _apply_revision(
        self,
        state: RunState,
        iteration: int,
        decision: dict[str, Any],
        current: Any,
        current_pdf: Path | None,
        candidate: Any,
        actions: list[dict[str, str]],
        run_dir: Path,
        template_path: Path | None,
    ) -> tuple[Any, Path | None, str | None]:
        """Render + re-evaluate a candidate revision, committing or rolling back.

        Returns ``(resume, pdf, stop_status)`` where ``stop_status`` is ``None``
        on a normal commit/rollback (the loop should continue) or
        ``render_failed`` when the intermediate PDF could not be compiled (the
        loop must stop).
        """
        eval_before = self._evaluate_artifact(state, current, current_pdf)

        candidate_pdf = run_dir / f"tailored_resume_v{iteration}.pdf"
        try:
            render_pdf(candidate, candidate_pdf, template_path)
        except Exception as e:  # noqa: BLE001
            first = actions[0]
            self._record_decision(
                state, iteration, decision,
                accepted=False,
                before=first.get("before", ""),
                after=first.get("after", ""),
                evidence=first.get("evidence", ""),
                eval_before=_metrics(eval_before),
                eval_after={},
                rollback_reason=f"PDF render failed: {e}",
                decision_title=first.get("decision"),
                decision_reason=first.get("reason"),
                target_value=first.get("target"),
            )
            return current, current_pdf, "render_failed"

        from app.tools.jdp_parser import extract_text_from_pdf

        try:
            artifact_text = extract_text_from_pdf(candidate_pdf)
        except (OSError, ValueError, Exception):  # noqa: BLE001
            artifact_text = candidate.full_text()

        eval_after = self._evaluate_artifact(
            state, candidate, candidate_pdf, artifact_text
        )

        # Adaptation: roll back a revision that made things worse.
        if _worse(_metrics(eval_before), _metrics(eval_after)):
            candidate_pdf.unlink(missing_ok=True)
            for action_entry in actions:
                self._record_decision(
                    state, iteration, decision,
                    accepted=False,
                    before=action_entry["before"],
                    after=action_entry["after"],
                    evidence=action_entry["evidence"],
                    eval_before=_metrics(eval_before),
                    eval_after=_metrics(eval_after),
                    rollback_reason=(
                        "Revision regressed evaluation scores; rolled back."
                    ),
                    decision_title=action_entry.get("decision"),
                    decision_reason=action_entry.get("reason"),
                    target_value=action_entry.get("target"),
                )
            state.current_evaluation = eval_before
            state.evaluation_history.append(
                {"iteration": iteration, "stage": "rolled-back", **eval_before}
            )
            state.persist()
            return current, current_pdf, None

        # Commit the successful revision.
        state.structured_resume = copy.deepcopy(candidate)
        state.current_artifact = str(candidate_pdf)
        state.current_evaluation = eval_after
        state.evaluation_history.append(
            {"iteration": iteration, "stage": "committed", **eval_after}
        )
        for action_entry in actions:
            self._record_decision(
                state, iteration, decision,
                accepted=True,
                before=action_entry["before"],
                after=action_entry["after"],
                evidence=action_entry["evidence"],
                eval_before=_metrics(eval_before),
                eval_after=_metrics(eval_after),
                decision_title=action_entry.get("decision"),
                decision_reason=action_entry.get("reason"),
                target_value=action_entry.get("target"),
            )
        state.persist()
        return candidate, candidate_pdf, None

    # ------------------------------------------------------------------ #
    def _run_loop(self, state: RunState, template_path: Path | None) -> None:
        run_dir = Path(state.run_dir)
        evidence_map = self._evidence_objects(state)
        if state.structured_resume is None:
            state.final_status = "best_effort"
            state.verification = {
                "artifact": None,
                "valid": False,
                "reason": "No structured resume could be parsed.",
            }
            state.persist()
            return
        current_resume = copy.deepcopy(state.structured_resume)
        current_pdf: Path | None = None
        max_iterations = int(state.max_iterations)

        # Baseline: evaluate the ORIGINAL resume (text-only, true baseline).
        baseline = self._evaluate_artifact(state, current_resume, None)
        state.evaluation_history.append({"iteration": 0, "stage": "baseline", **baseline})
        state.persist()

        for iteration in range(1, max_iterations + 1):
            state.iteration = iteration
            state.persist()

            eval_before = self._evaluate_artifact(
                state, current_resume, current_pdf
            )
            okay, _missing_reason = self._acceptance_met(eval_before)
            if okay:
                state.final_status = "accepted"
                state.current_evaluation = eval_before
                state.evaluation_history.append(
                    {"iteration": iteration, "stage": "re-evaluate", **eval_before}
                )
                state.persist()
                return

            unsatisfiable = {
                str(d.target)
                for d in state.decisions
                if not d.accepted and d.action == "surface_unsupported"
            }
            decision = self.revisor.decide_next_action(
                eval_before, state.role_kb, evidence_map, settings,
                unsatisfiable=unsatisfiable,
            )

            if decision["action"] == "accept":
                self._finalize(state, current_resume, template_path)
                state.persist()
                return

            if decision["action"] in {"surface_supported_skill", "surface_unsupported"}:
                skill = normalize_skill(str(decision.get("target") or ""))
                evidence = evidence_for_skill(evidence_map, skill)

                # Evidence gate: an action without authentic evidence is rejected.
                if decision["action"] == "surface_unsupported" and (
                    evidence is None or not evidence.supported
                ):
                    self._record_decision(
                        state, iteration, decision,
                        accepted=False,
                        before="",
                        after="",
                        evidence=f"No candidate evidence for '{skill}'",
                        eval_before=_metrics(eval_before),
                        eval_after={},
                        rollback_reason=(
                            f"'{skill}' cannot be added: the candidate's "
                            f"original resume provides no authentic evidence for it."
                        ),
                    )
                    # Adapt: nothing left to do for this skill; re-decide.
                    remaining_probeable = [
                        s
                        for s in canonicalize_required(state.role_kb)
                        if s in set(eval_before.get("missing_skills", []))
                        and _skill_lacks_evidence(evidence_map, s)
                        and s != skill
                    ]
                    if not remaining_probeable:
                        state.final_status = "best_effort"
                        state.current_evaluation = eval_before
                        state.persist()
                        return
                    continue

                # Build the candidate modification on a COPY of the artifact.
                # Surface ALL authentic, subtitle-supported required skills in a
                # single tailoring action (not just the first one).
                skills_to_surface = eval_before.get("supported_not_present", [])
                if skill not in skills_to_surface:
                    skills_to_surface = [skill] + skills_to_surface
                candidate_resume = copy.deepcopy(current_resume)
                modified, actions = tailor_surface(
                    candidate_resume, {"required_skills": skills_to_surface}
                )
                if not actions:
                    self._record_decision(
                        state, iteration, decision,
                        accepted=False,
                        before="",
                        after="",
                        evidence=", ".join(evidence.sources) if evidence else "",
                        eval_before=_metrics(eval_before),
                        eval_after={},
                        rollback_reason=(
                            f"No bullet could be modified to truthfully surface '{skill}'."
                        ),
                    )
                    state.final_status = "best_effort"
                    state.current_evaluation = eval_before
                    state.persist()
                    return

                current_resume, current_pdf, stop_status = self._apply_revision(
                    state, iteration, decision, current_resume, current_pdf,
                    modified, actions, run_dir, template_path,
                )
                if stop_status is not None:
                    state.final_status = stop_status
                    state.persist()
                    return
                continue

            if decision["action"] == "remove_unsupported_claim":
                # Truthful fix for unsubstantiated claims: edit them OUT of the
                # actual bullet/skills text, render, re-evaluate, and commit the
                # improvement (or roll it back if it regressed).
                unsupported_skills = sorted(
                    extract_canonical_skills(
                        " ".join(
                            c.get("claim", "")
                            for c in eval_before.get("unsupported_claims", [])
                        )
                    )
                )
                candidate_resume = copy.deepcopy(current_resume)
                modified, actions = tailor_remove_skills(
                    candidate_resume, set(unsupported_skills)
                )
                if not actions:
                    self._record_decision(
                        state, iteration, decision,
                        accepted=False,
                        before="",
                        after="",
                        evidence=f"Unsupported skills: {', '.join(unsupported_skills)}",
                        eval_before=_metrics(eval_before),
                        eval_after={},
                        rollback_reason=(
                            "Unsupported skills could not be located in the "
                            "tailored output to remove."
                        ),
                    )
                    state.final_status = "best_effort"
                    state.current_evaluation = eval_before
                    state.persist()
                    return

                current_resume, current_pdf, stop_status = self._apply_revision(
                    state, iteration, decision, current_resume, current_pdf,
                    modified, actions, run_dir, template_path,
                )
                if stop_status is not None:
                    state.final_status = stop_status
                    state.persist()
                    return
                continue

            state.final_status = "best_effort"
            state.persist()
            return

        state.final_status = "max_iterations_reached"
        self._finalize(
            state, current_resume, template_path,
            iteration=max_iterations, fallback="max_iterations_reached",
        )
        state.persist()

    # ------------------------------------------------------------------ #
    def _finalize(
        self,
        state: RunState,
        resume: Any,
        template_path: Path | None = None,
        iteration: int | None = None,
        fallback: str = "best_effort",
    ) -> str:
        """Render the final PDF, verify it, and resolve the outcome.

        Nothing is accepted until a real final artifact exists, has been
        re-evaluated, and passes every acceptance criterion. Otherwise the
        outcome falls back to ``fallback`` (``best_effort`` or
        ``max_iterations_reached``).
        """
        run_dir = Path(state.run_dir)
        final_pdf = run_dir / "tailored_resume_final.pdf"
        try:
            render_pdf(resume, final_pdf, template_path)
        except Exception as e:  # noqa: BLE001 - defensive
            state.final_status = "render_failed"
            state.current_evaluation = self._evaluate_artifact(state, resume, None)
            state.verification = {
                "artifact": str(final_pdf),
                "valid": False,
                "reason": f"Final PDF render failed: {e}",
            }
            return state.final_status

        from app.tools.jdp_parser import extract_text_from_pdf

        artifact_text = resume.full_text()
        try:
            artifact_text = extract_text_from_pdf(final_pdf)
        except Exception:  # noqa: BLE001 - defensive
            artifact_text = resume.full_text()

        checks = check_pdf_artifact(
            final_pdf,
            required_sections=state.role_kb.get("required_sections"),
        )
        eval_final = self._evaluate_artifact(
            state, resume, final_pdf, artifact_text
        )
        state.current_artifact = str(final_pdf)
        state.verification = {
            "artifact": str(final_pdf),
            "valid": bool(checks.get("valid")),
            "reason": "; ".join(checks.get("issues", [])) or "PDF artifact verified",
        }
        state.current_evaluation = eval_final
        stage = iteration or state.iteration or 0
        state.evaluation_history.append(
            {"iteration": stage, "stage": "final-verification", **eval_final}
        )
        ok, _reason = self._acceptance_met(eval_final)
        if ok:
            state.final_status = "accepted"
        else:
            state.final_status = fallback
        return state.final_status

    # ------------------------------------------------------------------ #
    def run(
        self,
        jd_text: str,
        resume_files: list[Path],
        template_path: Path | None = None,
        run_id: str | None = None,
    ) -> RunState:
        """Run the full autonomous pipeline and return the final state."""
        state = RunState(
            run_id=run_id or uuid.uuid4().hex[:8],
            goal=(
                "From the parsed JD, select the best candidate resume, tailor it to "
                "truthfully maximize ATS match, relevance and formatting while "
                "keeping factuality at 100%, then verify the final PDF."
            ),
            jd_text=jd_text,
            max_iterations=int(settings.max_iterations),
        )
        state.set_run_dir()

        # 1) Parse JD into role KB.
        state.role_kb = build_role_kb(jd_text=jd_text)
        state.persist()

        # 2) Inspect all candidate resumes and select the best.
        resumes = load_candidate_resumes(resume_files)
        candidates = self.selector.select(state.role_kb, resumes)
        state.candidates = candidates
        if candidates:
            best = candidates[0]
            state.selected_resume = best
            selected_structured = next(
                (r for r in resumes if r.name == best.name), None
            )
            if selected_structured is not None:
                state.structured_resume = copy.deepcopy(selected_structured)
                evidence_map = build_evidence_map(selected_structured)
                state.evidence_map = {
                    k: asdict(v) for k, v in evidence_map.items()
                }
                # Copy the original PDF into the run sandbox (baseline artifact).
                src_pdf = Path(selected_structured.source_path)
                if src_pdf.exists():
                    shutil.copy(src_pdf, Path(state.run_dir) / "original_resume.pdf")
        else:
            state.final_status = "no_candidates"
            state.persist()
            return state

        # 3) Agentic loop.
        self._run_loop(state, template_path)

        # 4) Final verification of the produced artifact.
        artifact = Path(state.current_artifact) if state.current_artifact else None
        if artifact is not None and artifact.exists():
            checks = check_pdf_artifact(
                artifact,
                required_sections=["Projects", "Skills", "Education"],
            )
            state.verification = {
                "artifact": str(artifact),
                "valid": checks.get("valid", False),
                "checks": checks,
                "decision_count": len(state.decisions),
                "accepted_decisions": sum(1 for d in state.decisions if d.accepted),
                "rejected_decisions": sum(1 for d in state.decisions if not d.accepted),
                "final_status": state.final_status,
            }
        else:
            state.verification = {
                "artifact": None,
                "valid": False,
                "reason": "No final PDF artifact produced",
                "final_status": state.final_status,
            }

        # 5) Write audit-trail reports into the run sandbox.
        self._write_run_reports(state)
        state.persist()
        return state

    # ------------------------------------------------------------------ #
    def _write_run_reports(self, state: RunState) -> None:
        run_dir = Path(state.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        (run_dir / "evaluations.json").write_text(
            json.dumps(state.evaluation_history, indent=2, default=str),
            encoding="utf-8",
        )
        (run_dir / "revision_log.json").write_text(
            json.dumps([d.to_dict() for d in state.decisions], indent=2, default=str),
            encoding="utf-8",
        )
        (run_dir / "evidence_report.json").write_text(
            json.dumps(state.evidence_map, indent=2, default=str),
            encoding="utf-8",
        )
        final_report = self._build_final_report(state)
        (run_dir / "final_report.json").write_text(
            json.dumps(final_report, indent=2, default=str), encoding="utf-8"
        )
        (run_dir / "final_report.txt").write_text(
            _format_report_txt(final_report), encoding="utf-8"
        )

    def _build_final_report(self, state: RunState) -> dict[str, Any]:
        role_kb = state.role_kb
        required = [normalize_skill(s) for s in role_kb.get("required_skills", [])]
        per_skill: dict[str, Any] = {}
        for skill in required:
            status = state.current_evaluation.get("per_skill_status", {}).get(skill)
            if status is None:
                status = {
                    "required": True,
                    "matched": skill in state.current_evaluation.get("matched_skills", []),
                    "supported": False,
                    "classification": "unknown",
                    "strength": "missing",
                    "sources": [],
                }
            per_skill[skill] = status
        return {
            "run_id": state.run_id,
            "goal": state.goal,
            "final_status": state.final_status,
            "role_kb": role_kb,
            "selected_resume": state.selected_resume.name if state.selected_resume else None,
            "selection_reasoning": (
                state.selected_resume.reasoning if state.selected_resume else ""
            ),
            "final_evaluation": state.current_evaluation,
            "evaluation_history": state.evaluation_history,
            "per_skill_status": per_skill,
            "decisions": [d.to_dict() for d in state.decisions],
            "verification": state.verification,
            "artifacts": {
                "run_dir": state.run_dir,
                "original_resume": str(Path(state.run_dir) / "original_resume.pdf"),
                "final_tailored": state.current_artifact,
            },
        }


def _format_report_txt(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"Automated Resume Agent - Final Report ({report['run_id']})")
    lines.append("=" * 60)
    lines.append(f"Final status: {report['final_status']}")
    lines.append(f"Selected resume: {report['selected_resume']}")
    lines.append(f"Selection reasoning: {report['selection_reasoning']}")
    lines.append("")
    lines.append("Final evaluation:")
    fe = report["final_evaluation"]
    for key in (
        "ats_match_percent",
        "relevance_percent",
        "factuality_score",
        "format_score",
    ):
        lines.append(f"  {key}: {fe.get(key)}")
    unsupported = fe.get("unsupported_claims", [])
    lines.append(f"  unsupported_claims: {len(unsupported)}")
    for u in unsupported:
        lines.append(f"    - {u.get('claim', '')}")
    lines.append("")
    lines.append("Per-skill status (required skills):")
    for skill, status in report["per_skill_status"].items():
        lines.append(
            f"  {skill}: supported={status.get('supported')} "
            f"strength={status.get('strength')} sources={len(status.get('sources', []))}"
        )
    lines.append("")
    lines.append("Decisions / actions taken (audit trail):")
    for decision in report["decisions"]:
        lines.append(
            f"  iter {decision['iteration']} "
            f"[{'accepted' if decision['accepted'] else 'REJECTED'}] "
            f"{decision['decision']}"
        )
        if not decision["accepted"]:
            lines.append(f"    rollback reason: {decision['rollback_reason']}")
    lines.append("")
    lines.append("Artifacts:")
    lines.append(f"  run_dir: {report['artifacts']['run_dir']}")
    lines.append(f"  final_tailored: {report['artifacts']['final_tailored']}")
    return "\n".join(lines)