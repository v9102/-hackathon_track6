# Resume Tailoring System - Hackathon Track 6

**Professional Agentic AI Resume Tailoring System**

An automated, **truthful** resume tailoring system that parses job descriptions, matches resumes to role requirements, evaluates factual consistency, and revises resumes through an autonomous **Goal -> Decision -> Action -> Intermediate Result -> Evaluation -> Adaptation -> Re-Evaluation -> Final Verification -> Outcome** loop. The agent never fabricates candidate experience: every change is backed by authentic, verifiable evidence from the candidate's own resume.

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

## 🚀 Full Agentic Pipeline (Task 6)

```bash
# Run the autonomous agent against the default role profile
python3 -m app.main run

# Run against a specific job description that forces adaptation
python3 -m app.main run --jd data/sample_jd.txt

# Point at a custom resume dir / LaTeX template
python3 -m app.main run --jd data/sample_jd.txt --resume-dir Resumes --template ShaunakMishra_Resume.tex

# Interactive web dashboard
streamlit run dashboard.py
```

Each run produces a traceable artifact set under `storage/runs/<run_id>/`:

| File | Description |
|------|-------------|
| `state.json` | Full run state: decisions, before/after diffs, evaluation history |
| `final_report.txt` | Human-readable outcome summary |
| `tailored_resume_final.pdf` | Final, evaluated, verified deliverable PDF |

### What the agent does (honestly)

1. **Goal** - Reads the JD and builds a role knowledge base of required/preferred skills.
2. **Decision** - Evaluates the original resume (ATS %, relevance %, factuality %, format %) and picks an action: *accept as-is*, *surface* authentic but buried skills, or *probe* a skill the resume never mentions.
3. **Action** - Modifies only a **copy** of the resume; every modification is linked to real evidence (e.g. a project subtitle listing `Python, TypeScript`).
4. **Intermediate Result + Adaptation** - Re-evaluates the revised resume. Rejected probes (skills with **no** authentic evidence, e.g. `Kafka`/`Kubernetes`) are marked unsatisfiable and never re-proposed.
5. **Re-Evaluation + Final Verification** - Re-renders the final PDF from the LaTeX template, verifies it is a valid PDF with all required sections, and records the final score.
6. **Outcome** - `accepted`, `best_effort`, `max_iterations_reached`, or `render_failed`, each with a full audit trail.

Example run against `data/sample_jd.txt`:

```
Decisions          : 4 (2 accepted, 2 rejected/rolled-back)
    [OK ] iter 1: Surface Python evidence into WorkflowOS — Multi-Agent Data Processing System
    [OK ] iter 1: Surface TypeScript evidence into WorkflowOS — Multi-Agent Data Processing System
    [REJ] iter 2: Weigh adding 'Kafka' to the most relevant project bullet
           -> 'Kafka' cannot be added: the candidate's original resume provides no authentic evidence for it.
    [REJ] iter 3: Weigh adding 'Kubernetes' to the most relevant project bullet
           -> 'Kubernetes' cannot be added: the candidate's original resume provides no authentic evidence for it.
```

With the default role profile the agent correctly reports `accepted` (0 decisions): the original resume already meets acceptance and no fabrication is warranted.

## 🏗️ Project Structure

```
hackathon_track6/
├── .github/                   # GitHub Actions & CI/CD
│   └── workflows/
│       └── python-tests.yml
├── .gitignore                # Git ignore rules
├── .env.example              # Environment variable templates
├── pyproject.toml            # Package dependencies & entry points
├── requirements.txt          # Pinned dependencies
├── README.md                 # This file
├── demo_video_script.txt     # Demo video outline
├── app/                      # Authoritative application package
│   ├── agents/               # planner, revisor, tailor, evaluator
│   ├── core/                 # config, models, run state
│   └── tools/                # resume parser, JD parser, LaTeX renderer, skills, evidence
├── ShaunakMishra_Resume.tex  # LaTeX template (provided format)
├── data/sample_jd.txt        # Demo JD that forces the adaptive loop
├── Resumes/                  # Candidate resume PDFs
├── storage/runs/             # Per-run artifacts (state.json, final report, final PDF)
├── tests/                    # Test suite (35 tests)
├── jdp_parser.py             # Root convenience wrapper (JD parsing)
├── resume_tailor.py          # Root convenience wrapper (tailoring)
├── evaluate_resume.py        # Root convenience wrapper (evaluation)
├── revisor.py                # Root convenience wrapper (revision loop)
├── change_report.py          # Root convenience wrapper (change reports)
├── dashboard.py              # Streamlit Web Dashboard
└── main.py                   # Root convenience wrapper (app.main)
```

## 🛠️ Architecture

### Module Organization

| Module | Responsibility | Entry Point |
|--------|---------------|-------------|
| `app/agents/planner.py` | Orchestrates the Goal->Decision->...->Outcome loop | `python3 -m app.main run` |
| `app/tools/jdp_parser.py` | JD parsing into a role KB | `python3 jdp_parser.py --jd "..."` |
| `app/tools/resume_parser.py` | Resume PDF -> structured resume | via planner |
| `app/tools/latex_renderer.py` | LaTeX -> PDF with artifact verification | via planner |
| `app/agents/evaluator.py` | ATS/relevance/factuality/format scoring | `python3 evaluate_resume.py` |
| `app/agents/revisor.py` | Action selection + skill probing | `python3 revisor.py` |
| `app/agents/tailor.py` | Evidence-backed bullet rephrasing | `python3 resume_tailor.py` |
| `app/core/state.py` | Run state + persistence | via planner |
| `dashboard.py` | Web interface | `streamlit run dashboard.py` |

### Data Flow

```text
JD Text
   ↓
jdp_parser.py → role_kb(job_analysis)
   ↓
resume_parser.py → structured_resume  (pdftotext + rule-based parse)
   ↓
planner loop:
   revisor.decide_next_action(evaluation, role_kb, evidence_map, unsatisfiable)
       → action (accept / surface / probe)
   tailor.tailor_surface / tailor_sustain
       → modified resume + evidence-linked action records
   latex_renderer.render_pdf → candidate.pdf
   evaluator.evaluate_agentic → re-evaluation (formats via artifact)
   adaptation: rejected probes join `unsatisfiable`, never re-proposed
   ↓
verification → storage/runs/<run_id>/tailored_resume_final.pdf + final_report.txt
```

## ✅ Compliance Highlights

- **Agentic, not hard-coded**: Deterministic but fully autonomous loop with real intermediate results, adaptation, and final verification; each decision is logged with before/after diffs and the evidence that justifies it.
- **No content fabrication**: The planner **refuses** any action without authentic evidence (`evidence_for_skill(...).supported`), and probe-only decisions are recorded as rejected.
- **Re-evaluation after every revision**: a revision that regresses any score is automatically rolled back.
- **Final PDF verification**: `check_pdf_artifact` confirms the final PDF exists, has all required sections, and is reasonably sized.
- **LaTeX template compliance**: Uses the provided `ShaunakMishra_Resume.tex` format via `pdflatex`; renders without `fullpage`/TS1 fontset (uses `geometry` + math bullet labels).
- **Professional CI**: GitHub Actions runs `ruff check .`, `mypy` on the root wrappers, and the 35 pytest tests (3 end-to-end agentic pipeline tests included).

## 📊 Output Files Summary

| File | Description | Format |
|------|-------------|--------|
| `storage/runs/<run_id>/state.json` | Full decision/adaptation audit trail | JSON |
| `storage/runs/<run_id>/final_report.txt` | Human-readable run summary | TXT |
| `storage/runs/<run_id>/tailored_resume_final.pdf` | Final evaluated deliverable | PDF |
| `role_kb.json` | JD parser output (CLI wrapper) | JSON |
| `tailored_resume.pdf` | Tailored resume (CLI wrapper) | LaTeX PDF |
| `evidence_report.json` | Machine-readable change/evidence report | JSON |

## 🚀 Development

### Local Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run the full test-suite
pytest tests/ -v

# Lint + type check (matches CI)
ruff check .
mypy main.py dashboard.py jdp_parser.py resume_tailor.py evaluate_resume.py revisor.py change_report.py

# Start dashboard
streamlit run dashboard.py
```

### Adding New Features

1. Add functionality under `app/` (keep root scripts as thin wrappers).
2. Add tests to `tests/` directory.
3. Update `pyproject.toml` if new dependencies needed.
4. Run `pip install -e .` to reinstall.
5. Commit and push to trigger GitHub Actions.

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