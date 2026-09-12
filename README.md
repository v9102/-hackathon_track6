# Resume Tailoring System - Hackathon Track 6

**Professional Agentic AI Resume Tailoring System**

An automated, truthful resume tailoring system that parses job descriptions, matches resumes to role requirements, evaluates factual consistency, and revises resumes through an automated loop.

## 📦 Quickstart Installation

```bash
# Clone the repository
git clone https://github.com/v9102/-hackathon_track6.git
cd -hackathon_track6

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

## 🚀 Quickstart Commands (Task 1-5)

```bash
# Task 1: Parse Job Description
python3 jdp_parser.py --jd "Software Engineer - Full Stack React Node.js position. 3+ years experience required. Required skills: React, Node.js, JavaScript, SQL, Git."

# Task 2: Tailor Resume (uses provided LaTeX template)
python3 resume_tailor.py --resume Resumes/ShaunakMishra_Resume.pdf --role SWE --kb role_kb.json

# Task 3: Evaluate Resume
python3 evaluate_resume.py --resume tailored_resume.pdf --kb role_kb.json --jd "Software Engineer JD text"

# Task 4: Revision Loop
python3 revisor.py --eval evaluation.json --tailoring tailoring_report_resume.json --resumes-dir Resumes

# Task 5: Generate Reports
python3 change_report.py --tailoring tailoring_report_resume.json --revisions revision_log.json

# Task 6: Full Pipeline (Streamlit Dashboard)
streamlit run dashboard.py
```

## 🏗️ Project Structure

```
-hackathon_track6/
├── .github/                   # GitHub Actions & CI/CD
│   └── workflows/
│       └── python-tests.yml
├── .gitignore                # Git ignore rules
├── .env.example              # Environment variable templates
├── pyproject.toml            # Package dependencies & entry points
├── requirements.txt          # Pinned dependencies
├── README.md                 # This file
├── demo_video_script.txt     # Demo video outline
├── evidence_report.json      # Machine-readable report
├── role_kb.json              # JD parser output
├── tailored_resume.pdf       # LaTeX-compiled tailored resume
├── evaluation.json           # ATS/factuality scores
├── revision_log.json         # Revision history
├── tailoring_report_resume.json
├── ShaunakMishra_Resume.tex  # LaTeX template (provided format)
├── Resumes/                  # Resume PDFs for testing
│   ├── ShaunakMishra_Resume.pdf
│   ├── AI_ML_Engineer_Resume.pdf
│   └── DevOps_Engineer_Resume.pdf
├── tests/                    # Test suite
│   ├── test_basic.py         # Basic functionality tests
│   └── test_agents.py        # Agent behavior tests
├── jdp_parser.py             # Task 1: JD Parser
├── resume_tailor.py          # Task 2: Resume Tailor
├── evaluate_resume.py        # Task 3: ATS/Factuality Evaluator
├── revisor.py                # Task 4: Revision Loop
├── change_report.py          # Task 5: Change/Evidence Report
├── dashboard.py              # Streamlit Web Dashboard
└── main.py                   # App entry point
```

## 🛠️ Architecture

### Module Organization

| Module | Responsibility | Entry Point |
|--------|---------------|-------------|
| `jdp_parser.py` | Job description parsing | `python3 jdp_parser.py` |
| `resume_tailor.py` | LaTeX resume tailoring | `python3 resume_tailor.py` |
| `evaluate_resume.py` | ATS + factuality scoring | `python3 evaluate_resume.py` |
| `revisor.py` | Automated revision loop | `python3 revisor.py` |
| `change_report.py` | Human + machine-readable reports | `python3 change_report.py` |
| `dashboard.py` | Web interface | `streamlit run dashboard.py` |
| `main.py` | Package entry point | `jdp_parser:main` etc. |

### Data Flow

```text
JD Text
   ↓
jdp_parser.py → role_kb.json
   ↓
resume_tailor.py → tailored_resume.pdf + tailoring_report.json
   ↓
evaluate_resume.py → evaluation.json (ATS %, relevance %, flags)
   ↓
revisor.py → revision_log.json (revised resume + changes)
   ↓
change_report.py → change_report.txt + evidence_report.json
```

## ✅ Compliance Highlights

- **LaTeX template compliance**: Uses the provided `ShaunakMishra_Resume.tex` format throughout
- **No content fabrication**: Only rephrases existing resume bullets or omits irrelevant sections
- **All skills from actual resume**: Extracted via `pdftotext` + PyPDF2
- **Agentic AI**: Autonomous goal pursuit, tool interaction, decision making, adaptation, verification
- **Factuality cross-check**: Claims verified across 3 resumes + known profile
- **Quickstart ready**: `cp -r Monetize ./hackathon_track6` then run tasks
- **Professional CI**: GitHub Actions with linting and testing
- **Package manageable**: `pyproject.toml` with pip install support

## 📊 Output Files Summary

| File | Description | Format |
|------|-------------|--------|
| `role_kb.json` | Role knowledge base | JSON |
| `tailored_resume.pdf` | Tailored resume | LaTeX PDF |
| `evaluation.json` | ATS + factuality scores | JSON |
| `revision_log.json` | Revision history | JSON |
| `tailoring_report.json` | Tailoring decisions | JSON |
| `evidence_report.json` | Machine-readable for judges | JSON |
| `change_report.txt` | Human-readable summary | TXT |

## 🚀 Development

### Local Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint code
ruff check .

# Type check
mypy jdp_parser.py resume_tailor.py evaluate_resume.py revisor.py change_report.py

# Start dashboard
streamlit run dashboard.py
```

### Adding New Features

1. Add functionality to the relevant `.py` file
2. Add tests to `tests/` directory
3. Update `pyproject.toml` if new dependencies needed
4. Run `pip install -e .` to reinstall
5. Commit and push to trigger GitHub Actions

## 📦 Package Installation

```bash
# Install from GitHub
pip install git+https://github.com/v9102/-hackathon_track6.git

# Or from local directory
pip install -e ./

# Install with dev dependencies
pip install -e ".[dev]"
```

## 👥 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add some amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see LICENSE file for details.

## 📞 Contact

- **GitHub**: @v9102
- **Repository**: `-hackathon_track6`
- **Project**: Resume Tailoring System

---

*Built with ❤️ for the Agentic AI Hackathon*