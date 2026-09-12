"""Revision Agent - proposes the next best action in the agentic loop.

The Revision Agent inspects the latest evaluation and, following the goal
(take the selected resume from ``baseline`` to the JD target), decides a single
next action:

- ``surface_supported_skill`` — rephrase a bullet using a required skill that is
  genuinely supported by the candidate's project tech stack, but not yet visible
  in the rendered resume text.
- ``remove_unsupported_claim`` — drop a claim that has no supporting evidence.
- ``surface_unsupported`` — *proposed* adding a missing required skill that the
  agent would like to include; this requires authentic evidence and is rejected
  by the planner's evidence gate when none exists (documented adaptation).
- ``accept`` — no further evidence-based improvement is possible; finalize.

The agent never fabricates: any action that would introduce unsupported content
is proposed only for explicit validation and is refused without real evidence.
"""

from __future__ import annotations

from typing import Any

from app.tools.skills import canonicalize_list


class RevisionAgent:
    """Agent that decides the next resume revision action."""

    def __init__(self) -> None:
        """Initialize the RevisionAgent."""

    def decide_next_action(
        self,
        evaluation: dict[str, Any],
        role_kb: dict[str, Any],
        evidence_map: dict[str, Any],
        settings: Any,
        unsatisfiable: set[str] | None = None,
    ) -> dict[str, Any]:
        """Decide the single best next action given the current evaluation.

        ``unsatisfiable`` is the set of required skills already proven to lack
        authentic evidence; they are never re-proposed (the agent adapts).
        """
        target_ats = float(getattr(settings, "target_ats", 80.0))
        ats = float(evaluation.get("ats_match_percent", 0.0))

        supported_not_present = evaluation.get("supported_not_present", [])
        unsupported_claims = evaluation.get("unsupported_claims", [])
        missing = set(evaluation.get("missing_skills", []))

        required = canonicalize_list(role_kb.get("required_skills", []))
        required_without_evidence = sorted(
            skill
            for skill in required
            if skill in missing
            and not (
                (skill in evidence_map) and evidence_map[skill].supported
            )
            and skill not in (unsatisfiable or set())
        )

        if supported_not_present and ats < target_ats:
            skill = supported_not_present[0]
            return {
                "decision": f"Surface '{skill}' into its most relevant project bullet",
                "decision_id": f"surface-{skill.lower()}",
                "reason": (
                    f"The JD requires '{skill}' and the candidate's project tech "
                    f"stack supports it, but it is not visible in the rendered "
                    f"resume text. Surfacing authentic evidence raises ATS coverage."
                ),
                "action": "surface_supported_skill",
                "target": skill,
                "requires_evidence": True,
            }

        if unsupported_claims:
            return {
                "decision": "Remove claims with no supporting candidate evidence",
                "decision_id": "remove-unsupported",
                "reason": f"{len(unsupported_claims)} claim(s) cannot be supported.",
                "action": "remove_unsupported_claim",
                "target": [c.get("claim", "") for c in unsupported_claims],
                "requires_evidence": False,
            }

        if required_without_evidence and ats < target_ats:
            skill = required_without_evidence[0]
            return {
                "decision": f"Weigh adding '{skill}' to the most relevant project bullet",
                "decision_id": f"probe-{skill.lower()}",
                "reason": (
                    f"The JD requires '{skill}' and ATS is below {target_ats:.0f}. "
                    f"The agent weighs adding it, but this needs authentic evidence."
                ),
                "action": "surface_unsupported",
                "target": skill,
                "requires_evidence": True,
            }

        return {
            "decision": "Accept current artifact",
            "decision_id": "accept",
            "reason": "All evidence-based improvements are exhausted or targets met.",
            "action": "accept",
            "target": None,
            "requires_evidence": False,
        }

    def revise(
        self,
        evaluation: dict[str, Any],
        max_revisions: int = 3,
    ) -> dict[str, Any]:
        """Compatibility revision logger built on decide_next_action."""
        revisions: list[dict[str, Any]] = []
        flags = evaluation.get("flags", [])

        if not flags:
            return {
                "revisions": revisions,
                "final_ats": evaluation.get("ats_match_percent", 0),
                "final_relevance": evaluation.get("relevance_percent", 0),
                "final_factuality": evaluation.get("factuality_score", 100),
                "status": "completed",
                "reason": "No flags - resume passes factuality check",
                "total_flags": 0,
            }

        for step in range(1, max_revisions + 1):
            decision = {
                "action": (
                    "remove_unsupported_claim"
                    if flags
                    else "accept"
                ),
                "reason": (
                    f"Step {step}: {len(flags)} flag(s) present"
                    if flags
                    else "No actionable evidence-based deficiency."
                ),
            }
            revisions.append(
                {
                    "step": step,
                    "decision": decision["action"],
                    "reason": decision["reason"],
                    "flags_addressed": flags,
                }
            )
            if decision["action"] == "accept":
                break

        if not flags:
            status = "completed"
            reason = "No flags - resume passes factuality check"
        elif len(revisions) >= max_revisions:
            status = "max_revisions_reached"
            reason = f"Max {max_revisions} revisions reached"
        else:
            status = "completed"
            reason = "Flags addressed"

        return {
            "revisions": revisions,
            "final_ats": evaluation.get("ats_match_percent", 0),
            "final_relevance": evaluation.get("relevance_percent", 0),
            "final_factuality": evaluation.get("factuality_score", 100),
            "status": status,
            "reason": reason,
            "total_flags": len(flags),
        }