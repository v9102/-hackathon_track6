"""Streamlit Dashboard for Resume Tailoring System.
import json

Provides a web interface for the complete resume tailoring pipeline:
- Parse job descriptions
- Tailor resumes using LaTeX template
- Evaluate with ATS + factuality scores
- Run revision loop
- Generate human + machine-readable reports
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="Resume Tailoring System",
    page_icon="📄",
    layout="wide",
)

# Session state initialization
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = {}

st.title("🤖 Agentic Resume Tailoring System")
st.markdown("**Automated, truthful resume tailoring with factual consistency verification**")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select Page:",
    ["Pipeline", "Task 1: JD Parser", "Task 2: Resume Tailor", 
     "Task 3: Evaluate", "Task 4: Revision", "Task 5: Reports",
     "Dashboard"]
)

# ============================================================
# PAGE: Pipeline (Full end-to-end)
# ============================================================
if page == "Pipeline":
    st.header("🔄 Full Pipeline Execution")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Inputs")
        jd_text = st.text_area(
            "Job Description Text:",
            height=150,
            placeholder="Paste the full job description here..."
        )
        
        resume_path = st.file_uploader(
            "Resume PDF:",
            type=["pdf"],
            help="Upload a resume PDF to tailor"
        )
        
        col_a, col_b = st.columns(2)
        with col_a:
            tailored_output = st.text_input(
                "Output PDF path:",
                value="storage/tailored_resume.pdf"
            )
        with col_b:
            max_revisions = st.slider(
                "Max revisions:",
                min_value=1,
                max_value=5,
                value=3
            )
    
    with col2:
        st.subheader("Pipeline Status")
        if st.button("🚀 Run Full Pipeline", type="primary"):
            if not jd_text:
                st.error("Please enter a job description")
            elif not resume_path:
                st.error("Please upload a resume PDF")
            else:
                with st.spinner("Running pipeline..."):
                    try:
                        from app.main import run_task
                        from app.tools.jdp_parser import extract_text_from_pdf
                        
                        # Step 1: Parse JD
                        st.info("Step 1: Parsing Job Description...")
                        from app.main import run_task as run_main
                        run_main(task="parse", jd_text=jd_text)
                        
                        # Step 2: Tailor Resume
                        st.info("Step 2: Tailoring Resume...")
                        tailored_path = Path(tailored_output)
                        
                        # Copy resume if uploaded
                        import shutil
                        resume_dest = Path("Resumes") / resume_path.name
                        if resume_path != resume_dest:
                            shutil.copy(resume_path, resume_dest)
                        
                        run_main(
                            task="tailor",
                            resume_path=Path("Resumes") / resume_path.name,
                            role=st.session_state.get("role", "SWE"),
                            jd_text=jd_text,
                            output_path=tailored_output,
                        )
                        
                        # Step 3: Evaluate
                        st.info("Step 3: Evaluating Resume...")
                        resume_text = extract_text_from_pdf(tailored_path)
                        
                        from app.main import run_task as run_main2
                        run_main2(
                            task="evaluate",
                            resume_path=tailored_path,
                            jd_text=jd_text,
                        )
                        
                        # Step 4: Revise
                        st.info("Step 4: Running Revision Loop...")
                        from app.main import run_main2
                        run_main2(
                            task="revise",
                            eval_path=Path("evaluation.json"),
                            tailoring_path=Path("tailoring_report_resume.json"),
                        )
                        
                        # Step 5: Reports
                        st.info("Step 5: Generating Reports...")
                        run_main2(task="reports")
                        
                        st.session_state.pipeline_results = {
                            "status": "completed",
                            "jd_text": jd_text[:50] + "..." if len(jd_text) > 50 else jd_text,
                        }
                        
                        st.success("Pipeline complete! Check the results below.")
                        
                    except Exception as e:
                        st.error(f"Pipeline failed: {e!s}")
                        st.exception(e)
        
        # Display results if available
        if st.session_state.pipeline_results:
            st.success("✅ Pipeline completed successfully")
            results = st.session_state.pipeline_results
            st.json({
                "status": results.get("status"),
                "jd_preview": results.get("jd_text"),
            })
    
    # Display existing results
    if Path("evaluation.json").exists():
        st.subheader("Evaluation Results")
        with open("evaluation.json") as f:
            eval_data = json.load(f)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("ATS Match %", f"{eval_data.get('ats_match_percent', 0)}%")
        with col2:
            st.metric("Relevance %", f"{eval_data.get('relevance_percent', 0)}%")
        with col3:
            st.metric("Factuality Score", f"{eval_data.get('factuality_score', 0)}")
        
        if eval_data.get("flags"):
            st.warning(f"⚠️ {len(eval_data['flags'])} factuality flags detected")
            for flag in eval_data["flags"][:3]:
                st.caption(flag.get("claim", "Unknown")[:100])
    
    if Path("evidence_report.json").exists():
        st.subheader("📋 Evidence Report")
        with open("evidence_report.json") as f:
            evidence = json.load(f)
        st.json(evidence)


# ============================================================
# PAGE: Task 1 - JD Parser
# ============================================================
elif page == "Task 1: JD Parser":
    st.header("Task 1: Job Description Parser")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        jd_input = st.text_area(
            "Job Description Text:",
            height=200,
            placeholder="Paste job description text..."
        )
        
        role_title = st.text_input("Role Title:", value="Software Engineer")
        
        if st.button("Parse JD", type="primary"):
            if not jd_input:
                st.error("Please enter job description text")
            else:
                with st.spinner("Parsing..."):
                    from app.main import run_task
                    run_task(task="parse", jd_text=jd_input)
                    st.success("✅ JD parsed successfully!")
                    st.json({
                        "title": st.session_state.get("role_kb", {}).get("title"),
                        "required_skills": st.session_state.get("role_kb", {}).get("required_skills", [])[:10],
                    })
    
    # Display parsed KB
    if Path("role_kb.json").exists():
        with open("role_kb.json") as f:
            kb = json.load(f)
        st.subheader("Parsed Role Knowledge Base")
        st.json(kb)


# ============================================================
# PAGE: Task 2 - Resume Tailor
# ============================================================
elif page == "Task 2: Resume Tailor":
    st.header("Task 2: Resume Tailor (LaTeX Template)")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        resume_upload = st.file_uploader(
            "Resume PDF:",
            type=["pdf"],
            help="Upload a resume PDF to tailor"
        )
        
        role = st.selectbox("Target Role:", ["SWE", "ML Engineer", "DevOps", "Data Scientist"])
        
        if st.button("Tailor Resume", type="primary"):
            if not resume_upload:
                st.error("Please upload a resume PDF")
            else:
                import shutil
                dest = Path("Resumes") / resume_upload.name
                if resume_upload != dest:
                    shutil.copy(resume_upload, dest)
                
                from app.main import run_task
                run_task(
                    task="tailor",
                    resume_path=dest,
                    role=role,
                    jd_text=st.session_state.get("jd_text", ""),
                )
                st.success("✅ Resume tailored successfully!")
                st.info("Check tailored_resume.pdf in the storage directory")
    
    # Show tailored resume info
    if Path("tailored_resume.pdf").exists():
        st.success("✅ Tailored resume PDF generated")
        with open("tailored_resume.pdf", "rb") as f:
            st.download_button(
                "Download tailored resume",
                data=f.read(),
                file_name="tailored_resume.pdf",
            )
    
    if Path("tailoring_report_resume.json").exists():
        with open("tailoring_report_resume.json") as f:
            report = json.load(f)
        st.json({
            "match_score": report.get("match_score"),
            "resume_skills": report.get("resume_skills", [])[:10],
            "required_skills": report.get("required_skills", [])[:10],
        })


# ============================================================
# PAGE: Task 3 - Evaluate
# ============================================================
elif page == "Task 3: Evaluate":
    st.header("Task 3: ATS/Factuality Evaluator")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        eval_resume = st.selectbox(
            "Select resume:",
            ["tailored_resume.pdf"] if Path("tailored_resume.pdf").exists() else []
        )
        
        eval_jd = st.text_area(
            "Job Description (or select from recent):",
            height=100,
            placeholder="Paste JD text or leave blank to use stored KB..."
        )
        
        if st.button("Evaluate Resume", type="primary"):
            if not eval_resume:
                st.error("No resume selected")
            else:
                from app.main import run_task
                run_task(
                    task="evaluate",
                    resume_path=Path(eval_resume),
                    jd_text=eval_jd,
                )
                st.success("✅ Evaluation complete!")
    
    # Display results
    if Path("evaluation.json").exists():
        with open("evaluation.json") as f:
            eval_data = json.load(f)
        
        st.subheader("Evaluation Results")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("ATS Match %", f"{eval_data.get('ats_match_percent', 0)}%")
        with col2:
            st.metric("Relevance %", f"{eval_data.get('relevance_percent', 0)}%")
        with col3:
            st.metric("Factuality Score", f"{eval_data.get('factuality_score', 0)}")
        
        if eval_data.get("flags"):
            st.warning(f"⚠️ {len(eval_data['flags'])} factuality issue(s) detected")
            with st.expander("View Flags"):
                for i, flag in enumerate(eval_data["flags"]):
                    st.caption(f"**Flag {i+1}** ({flag.get('severity', 'unknown')}): {flag.get('claim', '')[:150]}")
    
    if Path("evidence_report.json").exists():
        st.success("📋 Evidence report available")


# ============================================================
# PAGE: Task 4 - Revision
# ============================================================
elif page == "Task 4: Revision":
    st.header("Task 4: Revision Loop")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        eval_path = st.selectbox(
            "Evaluation JSON:",
            [p for p in ["evaluation.json"] if Path(p).exists()]
        )
        tailoring_path = st.selectbox(
            "Tailoring Report:",
            [p for p in ["tailoring_report_resume.json"] if Path(p).exists()]
        )
        max_rev = st.slider("Max revisions:", 1, 5, 3)
        
        if st.button("Run Revision Loop", type="primary"):
            from app.main import run_task
            run_task(
                task="revise",
                eval_path=Path(eval_path),
                tailoring_path=Path(tailoring_path),
                max_revisions=max_rev,
            )
            st.success("✅ Revision complete!")
    
    # Display results
    if Path("revision_log.json").exists():
        with open("revision_log.json") as f:
            rev_data = json.load(f)
        
        st.subheader("Revision Log")
        st.json({
            "status": rev_data.get("status"),
            "steps": len(rev_data.get("revisions", [])),
            "final_ats": rev_data.get("final_ats"),
            "final_factuality": rev_data.get("final_factuality"),
        })
        
        if Path("evidence_report.json").exists():
            st.success("📋 Evidence report generated")


# ============================================================
# PAGE: Task 5 - Reports
# ============================================================
elif page == "Task 5: Reports":
    st.header("Task 5: Change & Evidence Reports")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        tailoring_path = st.selectbox(
            "Tailoring Report:",
            [p for p in ["tailoring_report_resume.json"] if Path(p).exists()]
        )
    
    with col2:
        revisions_path = st.selectbox(
            "Revision Log:",
            [p for p in ["revision_log.json"] if Path(p).exists()]
        )
    
    if st.button("Generate Reports", type="primary"):
        from app.main import run_task
        run_task(task="reports")
        st.success("✅ Reports generated!")
    
    # Display results
    if Path("change_report.txt").exists():
        st.subheader("📄 Human-Readable Report")
        with open("change_report.txt") as f:
            st.text_area("Report content:", f.read(), height=300)
        
        with open("evidence_report.json", "rb") as f:
            st.download_button(
                "📥 Download Evidence Report (JSON)",
                data=f.read(),
                file_name="evidence_report.json",
            )
    
    if Path("change_report.txt").exists() and Path("evidence_report.json").exists():
        st.success("✅ Both reports generated!")


# ============================================================
# Default: Show dashboard overview
# ============================================================
else:
    st.info("Select a page from the sidebar to navigate")
    st.markdown("""
    ## Welcome to the Resume Tailoring System
    
    This dashboard provides access to all 5 pipeline tasks:
    1. **JD Parser** - Extract role requirements from job descriptions
    2. **Resume Tailor** - Tailor resumes using LaTeX template
    3. **Evaluator** - ATS match + factuality verification
    3. **Revision** - Automated revision loop
    4. **Reports** - Human + machine-readable reports
    
    **Key Features:**
    - ✅ LaTeX template compliance (your provided format)
    - ✅ No content fabrication (truth-first approach)
    - ✅ Factual consistency cross-checking
    - ✅ Automated revision loop (up to 3 iterations)
    - ✅ Quickstart: `cp -r Monetize ./hackathon_track6`
    - ✅ Streamlit dashboard for web access
    """)