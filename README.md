# Hackathon Track 6 - Resume Tailoring System

## Overview
An automated, agentic resume tailoring system that parses job descriptions, matches resumes to role requirements, evaluates factual consistency, and revises resumes through an automated loop.

## Project Structure
```
hackathon_track6/
├── jdp_parser.py          # Task 1: Job Description Parser
├── resume_tailor.py       # Task 2: Resume Tailoring
├── evaluate_resume.py     # Task 3: ATS/Factuality Evaluator
├── revisor.py            # Task 4: Revision Loop
├── change_report.py       # Task 5: Change/Evidence Report
├── requirements.txt       # Python dependencies
├── role_kb.json          # Output from jdp_parser (role knowledge base)
├── Resumes/              # Three resume PDFs for testing
│   ├── ShaunakMishra_Resume.pdf
│   ├── AI_ML_Engineer_Resume.pdf
│   └── DevOps_Engineer_Resume.pdf
├── tailored_resume.pdf   # Output: tailored resume PDF
├── evaluation.json        # Output: evaluation scores + flags
├── revision_log.json     # Output: revision history
├── tailoring_report.json # Output: tailoring decisions
└── evidence_report.json  # Output: machine-readable report
```

## How to Run

### Task 1: Job Description Parser
```bash
python3 jdp_parser.py --jd "Job description text here"
# or with a PDF file:
python3 jdp_parser.py --jd-file jd.pdf --title "Software Engineer"
```
Outputs: `role_kb.json` with fields: title, years_exp, required_skills, preferred_skills, degree, tools, red_flags

### Task 2: Resume Tailoring
```bash
python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf --role SWE --kb role_kb.json
```
Outputs: `tailored_resume.pdf` + `tailoring_report_resume.json`

### Task 3: Resume Evaluator
```bash
python3 evaluate_resume.py --resume tailored_resume.pdf --kb role_kb.json --jd "Job description text"
```
Outputs: `evaluation.json` with ats_match_percent, relevance_percent, factuality_score, and flags list

### Task 4: Revision Loop
```bash
python3 revisor.py --eval evaluation.json --tailoring tailoring_report_resume.json --resumes-dir Resumes
```
Outputs: `revision_log.json` - each revision step, what was changed, why

### Task 5: Change/Evidence Report
```bash
python3 change_report.py --tailoring tailoring_report_resume.json --revisions revision_log.json
```
Outputs: 
- `change_report.txt` - human-readable summary
- `evidence_report.json` - machine-readable structured data

## Key Features
- **Agentic workflow**: Parses JD → Tailors resume → Evaluates → Revises → Reports
- **Factual consistency**: Cross-checks claims across multiple resumes to catch unsupported claims
- **Truth-first approach**: Never fabricates skills or experience; only rephrases existing evidence
- **Automated revision**: Up to 3 revision iterations to eliminate all flags

## Output Files
- `role_kb.json`: Role knowledge base extracted from JD
- `tailored_resume.pdf`: Resume tailored to the target role
- `evaluation.json`: ATS match %, relevance %, factuality score, and flags
- `revision_log.json`: Step-by-step revision history
- `tailoring_report_resume.json`: What was kept/removed/rewritten and reasons
- `evidence_report.json`: Machine-readable data for judges
- `change_report.txt`: Human-readable summary for reviewers