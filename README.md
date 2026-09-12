# Resume Tailoring System - Hackathon Track 6

Automated, agentic resume tailoring system that parses job descriptions, matches resumes to role requirements, evaluates factual consistency, and revises resumes through an automated loop.

## Project Structure

```
hackathon_track6/
├── jdp_parser.py           # Task 1: Job Description Parser
├── resume_tailor.py        # Task 2: Resume Tailoring (LaTeX template)
├── evaluate_resume.py      # Task 3: ATS/Factuality Evaluator
├── revisor.py             # Task 4: Revision Loop
├── change_report.py        # Task 5: Change/Evidence Report
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── demo_video_script.txt   # Demo video outline
├── evidence_report.json    # Machine-readable report
├── role_kb.json            # Output from JD parser
├── tailored_resume.pdf     # LaTeX-compiled tailored resume
├── evaluation.json         # ATS/factuality scores
├── revision_log.json       # Revision history
├── tailoring_report_resume.json
├── ShaunakMishra_Resume.tex  # LaTeX template (provided format)
├── Resumes/                # Resume PDFs for testing
│   ├── ShaunakMishra_Resume.pdf
│   ├── AI_ML_Engineer_Resume.pdf
│   └── DevOps_Engineer_Resume.pdf
└── .git/                   # Git repository
```

## Quickstart

```bash
# 1. Clone or copy the repository
cp -r /path/To/Monetize ./hackathon_track6
cd hackathon_track6

# 2. Task 1: Parse Job Description
python3 jdp_parser.py --jd "Software Engineer - Full Stack React Node.js position. 3+ years experience required. Required skills: React, Node.js, JavaScript, SQL, Git."

# 3. Task 2: Tailor Resume (uses provided LaTeX template)
python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf --role SWE --kb role_kb.json

# 4. Task 3: Evaluate Resume
python3 evaluate_resume.py --resume tailored_resume.pdf --kb role_kb.json --jd "Software Engineer JD text"

# 5. Task 4: Revision Loop
python3 revisor.py --eval evaluation.json --tailoring tailoring_report_resume.json --resumes-dir Resumes

# 6. Task 5: Generate Reports
python3 change_report.py --tailoring tailoring_report_resume.json --revisions revision_log.json
```

## Key Features

- **Agentic workflow**: Parses JD → Tailors resume → Evaluates → Revises → Reports
- **LaTeX template compliance**: Uses the provided `ShaunakMishra_Resume.tex` format throughout
- **No content fabrication**: Only rephrases existing resume bullets or omits irrelevant sections
- **Factual consistency**: Cross-checks claims across 3 resumes to catch unsupported claims
- **Automated revision**: Up to 3 revision iterations to eliminate all flags

## Output Files

| File | Description |
|------|-------------|
| `role_kb.json` | Role knowledge base extracted from JD |
| `tailored_resume.pdf` | Resume tailored to the target role (LaTeX format) |
| `evaluation.json` | ATS match %, relevance %, factuality score, and flags |
| `revision_log.json` | Step-by-step revision history |
| `tailoring_report_resume.json` | What was kept/removed/rewritten and reasons |
| `evidence_report.json` | Machine-readable data for judges |
| `change_report.txt` | Human-readable summary for reviewers |

## Compliance Highlights

✅ Uses the provided LaTeX template format (no fpdf2 or docx generation)  
✅ All skills/education extracted from actual resume text  
✅ Agentic AI: autonomous goal pursuit, tool interaction, decision making, adaptation, verification  
✅ Quickstart: `cp -r Monetize ./hackathon_track6` then run tasks  
✅ Dashboard available: `streamlit run dashboard.py`  
✅ Submission filename format: `TechRebels_video_agentic` (team name format)

## Demo Video Outline

- **Goal**: Build a truthful, automated resume tailoring system
- **Decision**: Select resume based on JD match
- **Action**: Run `jdp_parser → resume_tailor → evaluate → revise`
- **Intermediate Result**: 82% ATS match, 3 unsupported claims removed
- **Adaptation**: Revised 2 bullet points, swapped in 1 project from alternate resume
- **Final Outcome**: Tailored resume ready to submit, with audit trail

## Repository Stats

- **Primary Language**: Python (81.8%)
- **Secondary Language**: TeX (18.2%)
- **Stars**: 0
- **Forks**: 0
- **Open Issues**: 0