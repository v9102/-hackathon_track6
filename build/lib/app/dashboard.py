#!/usr/bin/env python3
"""Streamlit dashboard for the autonomous resume agent.

Visualises the *real* audit trail produced by ``app.main``: the selected run's
state, the iteration loop (decision -> action -> evaluation), per-skill
evidence, and the final artifact verification. Reads only from
``storage/runs/<run_id>/``, so everything shown corresponds to actual artifacts.

Run with:  streamlit run app/dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.core.config import settings

st.set_page_config(page_title="Autonomous Resume Agent", page_icon="🤖", layout="wide")

runs_dir = settings.runs_dir
runs_dir.mkdir(parents=True, exist_ok=True)
run_ids = sorted(
    (p.name for p in runs_dir.iterdir() if (p / "state.json").exists()),
    reverse=True,
)


def _load_run(run_id: str) -> dict:
    path = runs_dir / run_id / "state.json"
    return json.loads(path.read_text(encoding="utf-8"))


st.title("🤖 Autonomous Resume Agent — Agentic Loop Dashboard")
st.caption("Every number here is read from the persisted run audit trail in storage/runs/.")

if not run_ids:
    st.warning(
        "No runs yet. Run `python -m app.main` first, then refresh this dashboard."
    )
    st.stop()

selected = st.sidebar.selectbox("Run", run_ids)
state = _load_run(selected)
run_dir = runs_dir / selected

col_status, col_sel, col_iters = st.columns(3)
col_status.metric("Final status", state.get("final_status", "-"))
col_status.metric("Verification", str(state.get("verification", {}).get("valid", "-")))
col_sel.metric(
    "Selected resume",
    (state.get("selected_resume") or {}).get("name", "-"),
)
col_iters.metric(
    "Iterations", len(state.get("evaluation_history", []))
)

st.subheader("Selection reasoning")
selected_info = state.get("selected_resume")
if selected_info:
    st.info(selected_info.get("reasoning", ""))
    st.caption(f"Selection score: {selected_info.get('selection_score')}")

st.subheader("Iteration loop: Goal → Decision → Action → Evaluating → Verifying → Outcome")
history = state.get("evaluation_history", [])
for entry in history:
    stage = entry.get("stage", "")
    with st.expander(
        f"iter {entry.get('iteration')} — {stage} "
        f"(ATS {entry.get('ats_match_percent')} | "
        f"Rel {entry.get('relevance_percent')} | "
        f"Fact {entry.get('factuality_score')})",
        expanded=True,
    ):
        keys = ["ats_match_percent", "relevance_percent", "factuality_score", "format_score"]
        cols = st.columns(4)
        for key, col in zip(keys, cols):
            col.metric(key, entry.get(key))
        unsupported = entry.get("unsupported_claims", [])
        if unsupported:
            st.error(f"Unsupported claims: {len(unsupported)}")
            for u in unsupported:
                st.caption(u.get("claim", ""))
        else:
            st.success("No unsupported claims")

st.subheader("Decisions / Actions (audit trail)")
decisions = state.get("decisions", [])
for decision in decisions:
    status = "✅ accepted" if decision.get("accepted") else "❌ rejected"
    with st.expander(
        f"iter {decision.get('iteration')} — {status}: {decision.get('decision')}",
    ):
        st.markdown(f"**Reason:** {decision.get('reason')}")
        st.markdown(f"**Target:** {decision.get('target') or '-'}")
        st.markdown(f"**Evidence:** {decision.get('evidence') or '-'}")
        before = decision.get("before")
        after = decision.get("after")
        if before or after:
            st.markdown("**Before:**")
            st.code(before or "(none)")
            st.markdown("**After:**")
            st.code(after or "(none)")
        if not decision.get("accepted") and decision.get("rollback_reason"):
            st.warning(f"Rollback: {decision.get('rollback_reason')}")
        ev_before = decision.get("evaluation_before")
        ev_after = decision.get("evaluation_after")
        if ev_before:
            c1, c2 = st.columns(2)
            c1.caption("Before: " + json.dumps(ev_before))
            c2.caption("After: " + json.dumps(ev_after))

st.subheader("Per-skill status vs the JD")
final_eval = state.get("current_evaluation", {})
per_skill = final_eval.get("per_skill_status") or {}
if per_skill:
    for skill, status in per_skill.items():
        supported = status.get("supported")
        icon = "✅" if supported else "❌"
        strength = status.get("strength", "missing")
        sources = len(status.get("sources", []))
        st.markdown(f"{icon} **{skill}** — {strength} ({sources} source(s))")
else:
    st.caption("No per-skill breakdown recorded.")

st.subheader("Final artifact")
artifact = (state.get("current_artifact") or "").strip()
if artifact:
    st.text(artifact)
    if Path(artifact).exists():
        with open(artifact, "rb") as f:
            st.download_button("Download tailored PDF", data=f.read(), file_name=Path(artifact).name)

st.subheader("Verification")
st.json(state.get("verification", {}))

st.subheader("Raw state")
with st.expander("Show full state JSON"):
    st.json(state)