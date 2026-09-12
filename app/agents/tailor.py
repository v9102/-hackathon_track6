"""Core Agent Orchestration - Tailor Agent.

The Tailor Agent coordinates the resume tailoring workflow:
1. Parses the job description using available tools
2. Loads and evaluates candidate resumes
3. Computes match scores and identifies gaps
4. Triggers revision loop if factuality issues are found
5. Renders the final tailored resume

This agent is designed to be the "brain" of the system, making
deterministic decisions based on evaluation results while maintaining
factual consistency constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.evaluator import EvaluationAgent
from app.agents.revisor import RevisionAgent
from app.core.config import settings
from app.tools.jdp_parser import extract_skills_from_text, extract_text_from_pdf


class TailorAgent:
    """Core agent that orchestrates the resume tailoring pipeline."""
    
    def __init__(self, config=None):
        """Initialize the TailorAgent."""
        self.config = config or settings
        self.role_kb: Optional[Dict[str, Any]] = None
        self.resume_skills: set[str] = set()
        self.match_score: float = 0.0
    
    def parse_job_description(self, jd_text: str, title: str = "Unknown Role") -> Dict[str, Any]:
        """Parse a job description and build the role knowledge base."""
        from app.tools.jdp_parser import build_role_kb
        self.role_kb = build_role_kb(
            title=title,
            jd_text=jd_text,
            use_tavily=False,
        )
        return self.role_kb
    
    def load_resume(self, resume_path: Path) -> Dict[str, Any]:
        """Load and analyze a candidate resume."""
        full_text = extract_text_from_pdf(resume_path)
        self.resume_skills = extract_skills_from_text(full_text)
        
        return {
            "full_text": full_text,
            "skills": self.resume_skills,
            "file_path": str(resume_path),
        }
    
    def compute_match_score(self, required_skills: List[str]) -> float:
        """Compute the match score between resume and job requirements."""
        if not required_skills:
            self.match_score = 0.0
            return 0.0
        
        resume_skills_set = self.resume_skills or set()
        required_set = set(required_skills)
        intersection = resume_skills_set & required_set
        self.match_score = len(intersection) / len(required_set)
        return self.match_score
    
    def evaluate_resume(self, eval_text: str, jd_text: str) -> Dict[str, Any]:
        """Evaluate resume factuality and ATS match against JD."""
        
        evaluator = EvaluationAgent()
        return evaluator.evaluate(eval_text, jd_text)
    
    def revise_resume(self, evaluation: Dict[str, Any], max_revisions: int = 3) -> Dict[str, Any]:
        """Run the revision loop based on evaluation flags."""
        
        revisor = RevisionAgent()
        return revisor.revise(evaluation, max_revisions)
    
    def render_tailored_resume(self, tailored_text: str, output_path: Path) -> Path:
        """Save the tailored resume as a text report."""
        # Ensure output goes to storage directory
        final_path = Path(str(output_path)).resolve()
        final_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save as text-based report
        # In production, compile with: pdflatex ShaunakMishra_Resume.tex
        facts = self.evaluate_resume(tailored_text, "") if tailored_text else {"flags": []}
        
        content = "Resume Tailoring Report\n========================\n"
        content += f"Role: {self.config.base_dir.name}\n"
        content += f"Match Score: {self.match_score:.1%}\n"
        content += f"Required Skills: {self.role_kb.get('required_skills', [])}\n"
        content += f"Matched Skills: {self.resume_skills & set(self.role_kb.get('required_skills', []))}\n"
        content += f"Missing Skills: {set(self.role_kb.get('required_skills', [])) - self.resume_skills}\n"
        content += "\nEvaluation:\n"
        content += f"  ATS Match: {facts.get('ats_match_percent', 0)}%\n"
        content += f"  Relevance: {facts.get('relevance_percent', 0)}%\n"
        content += f"  Factuality: {facts.get('factuality_score', 0)}\n"
        content += f"  Flags: {len(facts.get('flags', []))} unsupported claims\n"
        
        final_path.write_text(content)
        return final_path
    
    def run_pipeline(
        self,
        jd_text: str,
        resume_path: Path,
        tailored_output: Path = Path("storage/tailored_resume.pdf"),
    ) -> Dict[str, Any]:
        """Execute the complete tailoring pipeline."""
        # Step 1: Parse JD
        self.parse_job_description(jd_text, title="SWE")
        
        # Step 2: Load resume
        resume_analysis = self.load_resume(resume_path)
        
        # Step 3: Compute match score
        self.compute_match_score(self.role_kb.get("required_skills", []))
        
        # Step 4: Evaluate factuality
        evaluation = self.evaluate_resume(resume_analysis["full_text"], jd_text)
        
        # Step 5: Revise if needed
        revision_log = self.revise_resume(evaluation, max_revisions=3)
        
        # Step 6: Render tailored resume
        rendered_path = self.render_tailored_resume(resume_analysis["full_text"], tailored_output)
        
        # Compile results
        results: Dict[str, Any] = {
            "role_kb": self.role_kb,
            "resume_analysis": resume_analysis,
            "match_score": self.match_score,
            "evaluation": evaluation,
            "revision_log": revision_log,
            "tailored_output": str(tailored_output),
            "rendered_path": str(rendered_path),
        }
        
        return results
