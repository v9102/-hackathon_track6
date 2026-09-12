#!/usr/bin/env streamlit
"Resume Tailoring System Dashboard"

import json
import os
import subprocess
from pathlib import Path

import streamlit as st

# Page config
st.set_page_config(
    page_title="Resume Tailoring System",
    page_icon="📄",
    layout="wide",
)

st.title("🤖 Agentic Resume Tailoring System")
st.markdown("**Build a truthful, automated resume tailoring system**")

# Sidebar for navigation
st.sidebar.title("Navigation")
task = st.sidebar.radio(
    "Select Task:",
    ["1: JD Parser", "2: Resume Tailor", "3: Evaluate Resume", "4: Revision Loop", "5: Change Report", "6: All Tasks"]
)

# Common paths
WORK_DIR = Path(".", "hackathon_track6")
ROLE_KB_PATH = WORK_DIR / "role_kb.json"
TAILORING_REPORT_PATH = WORK_DIR / "tailoring_report_resume.json"
EVALUATION_PATH = WORK_DIR / "evaluation.json"
REVISION_LOG_PATH = WORK_DIR / "revision_log.json"
EVIDENCE_REPORT_PATH = WORK_DIR / "evidence_report.json"
CHANGE_REPORT_PATH = WORK_DIR / "change_report.txt"

# Task 1: JD Parser
if task == "1: JD Parser":
    st.header("Task 1: Job Description Parser")
    
    st.subheader("Parse Job Description")
    jd_text = st.text_area("Enter Job Description text:", height=200)
    col1, col2 = st.columns(2)
    with col1:
        jd_title = st.text_input("Role Title (optional):", "Software Engineer")
    with col2:
        use_tavily = st.checkbox("Use Tavily API (optional)")
    
    if st.button("Parse JD") and jd_text:
        env_path = Path(".env")
        env_vars = {}
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env_vars[k.strip()] = v.strip()
        
        tavily_key = os.getenv("TAVILY_API_KEY") if use_tavily else None
        
        # Run the parser
        cmd = f"python3 jdp_parser.py --jd '{jd_text}' --title '{jd_title}'"
        if use_tavily and tavily_key:
            cmd += " --use-tavily"
        
        result = subprocess.run(
            cmd,
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
        )
        st.code(cmd)
        st.success("Role KB parsed successfully!")
        
        # Display the output
        kb_path = WORK_DIR / "role_kb.json"
        if kb_path.exists():
            with open(kb_path) as f:
                kb = json.load(f)
            st.json(kb)
    
    st.subheader("Or parse from PDF")
    jd_file = st.file_uploader("Upload Job Description PDF", type=["pdf"])
    if jd_file and st.button("Parse JD from PDF"):
        pdf_path = WORK_DIR / "temp_jd.pdf"
        with open(pdf_path, "wb") as f:
            f.write(jd_file.read())
        
        cmd = f"python3 jdp_parser.py --jd-file {pdf_path} --title '{jd_title}'"
        if use_tavily and tavily_key:
            cmd += " --use-tavily"
        
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, check=False)
        st.code(cmd)
        
        kb_path = WORK_DIR / "role_kb.json"
        if kb_path.exists():
            with open(kb_path) as f:
                kb = json.load(f)
            st.json(kb)

# Task 2: Resume Tailor
elif task == "2: Resume Tailor":
    st.header("Task 2: Resume Tailor")
    
    st.subheader("Select Resume")
    resume_files = list((WORK_DIR / "Resumes").glob("*.pdf"))
    selected_resume = st.selectbox("Choose a resume:", resume_files)
    
    st.subheader("Select Role KB")
    if ROLE_KB_PATH.exists():
        role_title = st.selectbox("Role from KB:", [""] + [k["title"] for k in [{"title": "Unknown Role"}]])
    
    st.subheader("Tailoring Options")
    tailor_col1, tailor_col2 = st.columns(2)
    with tailor_col1:
        generate_pdf = st.checkbox("Generate tailored PDF", True)
    with tailor_col2:
        include_report = st.checkbox("Include tailoring report", True)
    
    if st.button("Tailor Resume") and selected_resume:
        role = st.text_input("Target Role:", "SWE")
        
        cmd = f"python3 resume_tailor.py --resume {selected_resume} --role {role} --kb {ROLE_KB_PATH}"
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, check=False)
        st.code(cmd)
        
        st.success("Resume tailored successfully!")
        
        # Show results
        col1, col2 = st.columns(2)
        
        with col1:
            tailored_pdf = WORK_DIR / "tailored_resume.pdf"
            if tailored_pdf.exists():
                st.success(f"Tailored PDF generated: {tailored_pdf.name}")
                with open(tailored_pdf, "rb") as f:
                    st.download_button(
                        "Download tailored resume PDF",
                        f.read(),
                        file_name="tailored_resume.pdf",
                    )
        
        with col2:
            report_path = WORK_DIR / "tailoring_report_resume.json"
            if report_path.exists():
                with open(report_path) as f:
                    report = json.load(f)
                st.json(report)
                if include_report:
                    st.download_button(
                        "Download tailoring report JSON",
                        report,
                        file_name="tailoring_report_resume.json",
                    )
    
    st.subheader("Resume Sources")
    st.markdown("""
    - **Resumes/ShaunakMishra_Resume.pdf** - Full-Stack Engineer (Shaunak's resume)
    - Add more resumes to the Resumes/ directory to use them
    """)

# Task 3: Evaluate Resume
elif task == "3: Evaluate Resume":
    st.header("Task 3: ATS/Factuality Evaluator")
    
    st.subheader("Evaluation Setup")
    
    col1, col2 = st.columns(2)
    with col1:
        eval_resume = st.selectbox("Select tailored resume:", ["tailored_resume.pdf"] if (WORK_DIR / "tailored_resume.pdf").exists() else [])
    with col2:
        if ROLE_KB_PATH.exists():
            st.selectbox("Role KB:", [ROLE_KB_PATH.name])
    
    st.subheader("Job Description")
    jd_source = st.radio("JD source:", ["Use role_kb JD", "Enter custom JD text"])
    custom_jd = ""
    if jd_source == "Enter custom JD text":
        custom_jd = st.text_area("Paste JD text:", height=150)
    
    resumes_dir = st.text_input("Resumes directory for cross-check:", str(WORK_DIR / "Resumes"))
    
    if st.button("Evaluate Resume") and (eval_resume or custom_jd):
        env_path = Path(".env")
        env_cmd = ""
        if env_path.exists():
            env_cmd = f"--env {env_path}"
        
        jd_arg = f"--jd '{custom_jd}'" if custom_jd else ""
        
        cmd = f"python3 evaluate_resume.py --resume {eval_resume} --kb {ROLE_KB_PATH} {env_cmd} {jd_arg} --resumes-dir {resumes_dir}"
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, check=False)
        st.code(cmd)
        
        st.success("Evaluation complete!")
        
        # Display results
        eval_path = WORK_DIR / "evaluation.json"
        if eval_path.exists():
            with open(eval_path) as f:
                eval_data = json.load(f)
            
            st.subheader("Evaluation Results")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("ATS Match %", f"{eval_data.get('ats_match_percent', 0)}%")
            with col2:
                st.metric("Relevance %", f"{eval_data.get('relevance_percent', 0)}%")
            with col3:
                st.metric("Factuality Score", f"{eval_data.get('factuality_score', 0)}")
            
            # Flags
            st.subheader("Flags (Factuality Issues)")
            flags = eval_data.get("flags", [])
            if flags:
                for flag in flags:
                    severity = flag.get("severity", "low")
                    color = "🔴" if severity == "high" else "🟡" if severity == "medium" else "🟢"
                    st.markdown(f"{color} **{flag.get('claim', 'Unknown claim')}**")
            else:
                st.success("No factuality issues found! ✅")
            
            # Download evaluation
            with open(eval_path, "rb") as f:
                st.download_button(
                    "Download evaluation JSON",
                    f.read(),
                    file_name="evaluation.json",
                )
    
    st.subheader("How to read results:")
    st.info("""
    - **ATS Match %**: Keyword overlap between resume and JD
    - **Relevance %**: Match score from Task 2 (intersection/resume skills / required skills)
    - **Factuality Score**: 100 - (15 × number of unsupported claims)
    - **Flags**: Specific claims in resume not supported by text or other resumes
    """)

# Task 4: Revision Loop
elif task == "4: Revision Loop":
    st.header("Task 4: Revision Loop")
    
    st.subheader("Revision Setup")
    
    col1, col2 = st.columns(2)
    with col1:
        eval_file = st.selectbox("Evaluation JSON:", [EVALUATION_PATH.name] if EVALUATION_PATH.exists() else [])
    with col2:
        tailoring_file = st.selectbox("Tailoring Report:", [TAILORING_REPORT_PATH.name] if TAILORING_REPORT_PATH.exists() else "")
    
    max_revisions = st.slider("Max revisions:", 1, 5, 3)
    
    if st.button("Run Revisor") and eval_file and tailoring_file:
        resumes_dir = st.text_input("Resumes directory:", str(WORK_DIR / "Resumes"))
        
        cmd = f"python3 revisor.py --eval {eval_file} --tailoring {tailoring_file} --resumes-dir {resumes_dir} --max-revisions {max_revisions}"
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, check=False)
        st.code(cmd)
        
        st.success("Revision process complete!")
        
        # Show results
        rev_log_path = WORK_DIR / "revision_log.json"
        if rev_log_path.exists():
            with open(rev_log_path) as f:
                rev_log = json.load(f)
            
            st.subheader("Revision Log")
            st.json(rev_log)
            
            # Download buttons
            col1, col2 = st.columns(2)
            with col1:
                if rev_log_path.exists():
                    with open(rev_log_path, "rb") as f:
                        st.download_button(
                            "Download revision log",
                            f.read(),
                            file_name="revision_log.json",
                        )
            
            # Generate final resume
            final_pdf = WORK_DIR / "final_resume.pdf"
            if final_pdf.exists():
                with open(final_pdf, "rb") as f:
                    st.download_button(
                        "Download final tailored resume",
                        f.read(),
                        file_name="final_resume.pdf",
                    )
    
    st.subheader("Revision Process:")
    st.markdown("""
    1. **Check flags**: Evaluation identifies unsupported claims
    2. **Auto-rephrase**: Try to add missing skills truthfully
    3. **Omit claims**: Remove unsupported statements
    4. **Re-evaluate**: Run evaluation again
    5. **Repeat**: Up to max revisions (default 3)
    6. **Stop**: When no flags remain or max revisions reached
    """)

# Task 5: Change Report
elif task == "5: Change Report":
    st.header("Task 5: Change/Evidence Report")
    
    st.subheader("Report Generation")
    
    col1, col2 = st.columns(2)
    with col1:
        tailoring_sel = st.selectbox("Tailoring report:", [TAILORING_REPORT_PATH.name] if TAILORING_REPORT_PATH.exists() else [])
    with col2:
        revisions_sel = st.selectbox("Revision log:", [REVISION_LOG_PATH.name] if REVISION_LOG_PATH.exists() else "")
    
    if st.button("Generate Reports") and tailoring_sel and revisions_sel:
        cmd = f"python3 change_report.py --tailoring {tailoring_sel} --revisions {revisions_sel}"
        result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, check=False)
        st.code(cmd)
        
        st.success("Reports generated!")
        
        # Human-readable report
        with open(CHANGE_REPORT_PATH, "r") as f:
            human_report = f.read()
        
        st.subheader("Human-Readable Report")
        st.text_area("Report:", human_report, height=300)
        
        with open(CHANGE_REPORT_PATH, "rb") as f:
            st.download_button(
                "Download change_report.txt",
                f.read(),
                file_name="change_report.txt",
            )
        
        # Machine-readable evidence report
        with open(EVIDENCE_REPORT_PATH, "rb") as f:
            st.download_button(
                "Download evidence_report.json",
                f.read(),
                file_name="evidence_report.json",
            )
    
    st.subheader("Report Formats:")
    st.markdown("""
    - **Human-readable**: `change_report.txt` - Summary for hiring managers
    - **Machine-readable**: `evidence_report.json` - Structured data for judges
    - Includes: match scores, kept/removed/rewritten bullets, revisions, ATS %, factuality
    """)

# Task 6: All Tasks
else:
    st.header("Task 6: Run Full Pipeline")
    
    st.subheader("Quickstart: Run All Tasks")
    
    if st.button("Execute Full Pipeline"):
        steps = [
            ("Task 1: Parse JD", "python3 jdp_parser.py --jd 'Software Engineer - Full Stack React Node.js position. 3+ years experience required. Required skills: React, Node.js, JavaScript, SQL, Git. Preferred skills: TypeScript, AWS, Docker. B.S. in Computer Science or related field. Responsibilities: Build web applications, collaborate with team, debug and maintain code.'"),
            ("Task 2: Tailor Resume", "python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf --role SWE --kb role_kb.json"),
            ("Task 3: Evaluate", "python3 evaluate_resume.py --resume tailored_resume.pdf --kb role_kb.json --jd 'Software Engineer - Full Stack React Node.js position...'"),
            ("Task 4: Revise", "python3 revisor.py --eval evaluation.json --tailoring tailoring_report_resume.json --resumes-dir Resumes"),
            ("Task 5: Report", "python3 change_report.py --tailoring tailoring_report_resume.json --revisions revision_log.json"),
        ]
        
        progress_bar = st.progress(0)
        status_container = st.empty()
        
        for i, (name, cmd) in enumerate(steps):
            status_container.info(f"Running: {name}")
            result = subprocess.run(cmd, cwd=WORK_DIR, capture_output=True, text=True, timeout=60000, check=False)
            progress_bar.progress((i + 1) / len(steps))
            
            if result.returncode != 0:
                st.error(f"**{name} failed**: {result.stderr}")
                break
            status_container.success(f"**{name} completed** ✅")
        
        st.balloons()
        st.success("Full pipeline complete! Check the sidebar to view individual task results.")
    
    st.subheader("Or run individual tasks from the sidebar")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("""**Agentic Resume Tailoring System**\n\nBuilt with Streamlit\nTasks 1-5: Resume optimization pipeline\nTask 6: Full integration demo\n\n✅ No content fabrication\n✅ LaTeX template compliance\n✅ Factuality verification\n✅ Agentic revision loop""")