#!/usr/bin/env python3
"""Streamlit dashboard for the autonomous resume agent.

Visualises the *real* audit trail produced by ``app.main``: the selected run's
pipeline flow (Goal -> JD -> Selection -> Evidence -> Tailor -> Evaluate ->
Decision -> Revision -> Re-evaluate -> Verification -> Final Result), the
resume-selection comparison, the decision/action trail with before-after
metrics, per-skill evidence status, and the final artifact. Reads only from
``storage/runs/<run_id>/``, so everything shown corresponds to actual artifacts.

Run with:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import json

import streamlit as st

from app.core.config import settings

st.set_page_config(page_title="Autonomous Resume Agent", page_icon="🤖", layout="wide")

runs_dir = settings.runs_dir
runs_dir.mkdir(parents=True, exist_ok=True)
run_ids = sorted(
    (p.name for p in runs_dir.iterdir() if (p / "state.json").exists()),
    reverse=True,
)

# The pipeline a judge should see at a glance.
PIPELINE_STAGES = [
    ("Goal", "the user goal is recorded"),
    ("JD Analysis", "role KB parsed from the JD"),
    ("Resume Selection", "all candidates scored, best picked"),
    ("Evidence", "candidate evidence map built"),
    ("Tailor", "supported skills surfaced into bullets"),
    ("Evaluate", "scores measured on the real artifact"),
    ("Problem / Decision", "revisor names the next action + reason"),
    ("Revision", "a bullet is actually rewritten"),
    ("Re-evaluate", "scores measured again after revision"),
    ("Rollback", "a regressing revision is reverted"),
    ("Verification", "final PDF checked (sections / readable)"),
    ("Final Result", "status resolved"),
]


def _load_run(run_id: str) -> dict:
    path = runs_dir / run_id / "state.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _stage_status(state: dict) -> dict[str, bool]:
    history = state.get("evaluation_history", [])
    decisions = state.get("decisions", [])
    stages = {
        "Goal": bool(state.get("goal")),
        "JD Analysis": bool(state.get("jd_text")) and bool(state.get("role_kb", {}).get("required_skills")),
        "Resume Selection": state.get("selected_resume") is not None,
        "Evidence": bool(state.get("evidence_map")),
        "Tailor": bool(decisions),
        "Evaluate": bool(history),
        "Problem / Decision": bool(decisions),
        "Revision": any(
            d.get("accepted") and d.get("action") == "surface_supported_skill"
            for d in decisions
        ),
        "Re-evaluate": any(h.get("stage") in {"committed", "re-evaluate"} for h in history),
        "Rollback": any(not d.get("accepted") for d in decisions),
        "Verification": bool((state.get("verification") or {}).get("valid")),
        "Final Result": bool(state.get("final_status")) and state.get("final_status")
        not in {"", "best_effort"},
    }
    return stages


st.title("🤖 Autonomous Resume Agent — Agentic Loop Dashboard")
st.caption("Every number shown here is read from the persisted run audit trail in storage/runs/.")

if not run_ids:
    st.warning("No runs yet. Run `python -m app.main` first, then refresh this dashboard.")
    st.stop()

selected = st.sidebar.selectbox("Run", run_ids)
state = _load_run(selected)
run_dir = runs_dir / selected

# --------------------------------------------------------------------------- #
# 1. Pipeline flow overview
# --------------------------------------------------------------------------- #
st.subheader("Agentic pipeline")
stage_status = _stage_status(state)
cols = st.columns(len(PIPELINE_STAGES))
for col, (label, hint) in zip(cols, PIPELINE_STAGES):
    done = stage_status[label]
    col.markdown(
        f"### {'✅' if done else '⬜'}\n**{label}**\n\n<small>{hint}</small>",
        unsafe_allow_html=True,
    )
st.caption("Stages marked ✅ have evidence for this run in state.json; ⬜ did not occur (or rolled back).")

col_status, col_sel, col_verif, col_iters = st.columns(4)
col_status.metric("Final status", state.get("final_status", "-"))
col_verif.metric("Verification", str((state.get("verification") or {}).get("valid", "-")))
col_sel.metric("Selected resume", (state.get("selected_resume") or {}).get("name", "-"))
col_iters.metric("Evaluation snapshots", len(state.get("evaluation_history", [])))

# --------------------------------------------------------------------------- #
# 2. Goal + JD analysis
# --------------------------------------------------------------------------- #
with st.expander("Goal and JD analysis", expanded=False):
    st.markdown(f"**Goal:** {state.get('goal') or '-'}")
    role_kb = state.get("role_kb") or {}
    st.markdown(
        f"**Role:** {role_kb.get('title') or '-'}  |  "
        f"**Required skills ({len(role_kb.get('required_skills', []))}):** "
        f"{', '.join(role_kb.get('required_skills', [])) or '-'}"
    )
    st.markdown(
        f"**Preferred:** {', '.join(role_kb.get('preferred_skills', [])) or '-'}  |  "
        f"**Years exp:** {role_kb.get('years_exp') or '-'}"
    )

# --------------------------------------------------------------------------- #
# 3. Resume selection comparison
# --------------------------------------------------------------------------- #
st.subheader("Resume selection — all candidates scored")
candidates = state.get("candidates", [])
sel_name = (state.get("selected_resume") or {}).get("name", "")
if candidates:
    rows = []
    for candidate in candidates:
        matched = candidate.get("matched_required", [])
        rows.append(
            {
                "candidate": candidate.get("name", ""),
                "score": candidate.get("selection_score"),
                "evidence_bullets": candidate.get("evidence_count"),
                "matched_required": ", ".join(matched) if matched else "-",
                "reason": candidate.get("reasoning", ""),
            }
        )
    rows.sort(key=lambda r: r["score"], reverse=True)
    for row in rows:
        emoji = "🏆 " if row["candidate"] == sel_name else ""
        st.markdown(
            f"**{emoji}{row['candidate']}** — {row['score']}/100 "
            f"({row['evidence_bullets']} evidence bullets)"
        )
        st.caption(f"Matched required: {row['matched_required']}")
        st.caption(row["reason"])
else:
    st.caption("No candidates recorded.")

# --------------------------------------------------------------------------- #
# 4. Evidence map summary
# --------------------------------------------------------------------------- #
st.subheader("Candidate evidence layer")
evidence = state.get("evidence_map", {})
supported = {k for k, v in evidence.items() if v.get("supported")}
if evidence:
    st.markdown(
        f"{len(supported)} canonical skills are supported by the candidate's "
        f"own original resume evidence."
    )
    with st.expander("Supported skills and sources"):
        for skill in sorted(supported):
            info = evidence[skill]
            st.markdown(f"**{skill}** — {info.get('strength')}: {', '.join(info.get('sources', []))}")
else:
    st.caption("No evidence map recorded.")

# --------------------------------------------------------------------------- #
# 5. Evaluation history
# --------------------------------------------------------------------------- #
st.subheader("Iteration loop: Evaluate → Problem → Decision → Revision → Re-evaluate")
history = state.get("evaluation_history", [])
for entry in history:
    stage = entry.get("stage", "")
    ats = entry.get("ats_match_percent")
    rel = entry.get("relevance_percent")
    fact = entry.get("factuality_score")
    fmt = entry.get("format_score")
    with st.expander(
        f"iter {entry.get('iteration')} — {stage} "
        f"(ATS {ats} | Rel {rel} | Fact {fact} | Fmt {fmt})",
        expanded=True,
    ):
        cols = st.columns(4)
        for key, col in zip(["ats_match_percent", "relevance_percent", "factuality_score", "format_score"], cols):
            col.metric(key, entry.get(key))
        unsupported = entry.get("unsupported_claims", [])
        if unsupported:
            st.error(f"Unsupported claims: {len(unsupported)}")
            for u in unsupported:
                st.caption(u.get("claim", ""))
        else:
            st.success("No unsupported claims")

# --------------------------------------------------------------------------- #
# 6. Decisions / actions with before-after metrics
# --------------------------------------------------------------------------- #
st.subheader("Decisions / Actions (audit trail)")
decisions = state.get("decisions", [])
for decision in decisions:
    accepted = decision.get("accepted")
    status = "✅ accepted" if accepted else "❌ rejected"
    with st.expander(f"iter {decision.get('iteration')} — {status}: {decision.get('decision')}"):
        st.markdown(f"**Reason:** {decision.get('reason')}")
        st.markdown(f"**Action:** {decision.get('action')} → **Target:** {decision.get('target') or '-'}")
        st.markdown(f"**Evidence:** {decision.get('evidence') or '-'}")
        before = decision.get("before")
        after = decision.get("after")
        if before or after:
            st.markdown("**Bullet before / after:**")
            st.markdown(f"```\n{before or '(none)'}\n```")
            st.markdown(f"```\n{after or '(none)'}\n```")
        ev_before = decision.get("evaluation_before") or {}
        ev_after = decision.get("evaluation_after") or {}
        if ev_before or ev_after:
            st.markdown("**Metrics before → after:**")
            for key in ("ats", "relevance", "factuality", "format"):
                b = ev_before.get(key, "-")
                a = ev_after.get(key, "-")
                if b == "-" and a == "-":
                    continue
                st.markdown(f"`{key:<10} {b} → {a}`")
        if not accepted and decision.get("rollback_reason"):
            st.warning(f"Rollback: {decision.get('rollback_reason')}")

# --------------------------------------------------------------------------- #
# 7. Per-skill status vs the JD
# --------------------------------------------------------------------------- #
st.subheader("Per-skill status vs the JD")
final_eval = state.get("current_evaluation", {})
per_skill = final_eval.get("per_skill_status") or {}
if per_skill:
    icons = {"supported": "✅", "unsupported": "⛔", "unknown": "❔"}
    for skill, status in per_skill.items():
        classif = status.get("classification", "unknown")
        icon = icons.get(classif, "❔")
        strength = status.get("strength", "missing")
        sources = len(status.get("sources", []))
        st.markdown(
            f"{icon} **{skill}** — {classif} / {strength} ({sources} source(s))"
        )
    if any(s.get("classification") == "unsupported" for s in per_skill.values()):
        st.error("Unsupported claims were refused — the agent does not fabricate experience.")
else:
    st.caption("No per-skill breakdown recorded.")

# --------------------------------------------------------------------------- #
# 8. Final artifact + verification
# --------------------------------------------------------------------------- #
st.subheader("Final artifact")
verification = state.get("verification", {})
st.json(verification)

planned = {
    "state.json": "state.json",
    "original_resume.pdf": "original_resume.pdf",
    "tailored_resume_final.pdf": "tailored_resume_final.pdf",
    "evaluations.json": "evaluations.json",
    "revision_log.json": "revision_log.json",
    "evidence_report.json": "evidence_report.json",
    "final_report.json": "final_report.json",
    "final_report.txt": "final_report.txt",
}
for label, filename in planned.items():
    path = run_dir / filename
    if path.exists():
        st.markdown(f"[{label}]({path})")
        with open(path, "rb") as f:
            st.download_button(f"Download {label}", data=f.read(), file_name=filename)
    else:
        st.caption(f"{label} — missing")

st.subheader("Raw state")
with st.expander("Show full state JSON"):
    st.json(state)