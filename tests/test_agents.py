"""Tests for the agents module - Tailor, Evaluator, Revisor."""



from app.agents.evaluator import EvaluationAgent
from app.agents.revisor import RevisionAgent
from app.agents.tailor import TailorAgent


class TestTailorAgent:
    """Test cases for the Tailor Agent."""

    def test_initialization(self):
        """Test TailorAgent can be instantiated."""
        agent = TailorAgent()
        assert agent is not None
        assert agent.role_kb is None

    def test_parse_job_description(self):
        """Test job description parsing."""
        jd_text = "Software Engineer position. 3+ years experience. Required skills: React, Node.js."
        agent = TailorAgent()
        kb = agent.parse_job_description(jd_text)
        assert kb is not None
        assert "title" in kb

    def test_compute_match_score(self):
        """Test match score computation."""
        agent = TailorAgent()
        agent.resume_skills = {"Python", "React", "SQL"}
        score = agent.compute_match_score(["Python", "JavaScript", "React"])
        assert 0 <= score <= 1
        # 2 out of 3 = 0.667
        assert abs(score - 2/3) < 0.01

    def test_evaluate_resume(self):
        """Test resume evaluation."""
        jd_text = "Python Django React Position. Required skills: Python, Django, React."
        agent = TailorAgent()
        evaluation = agent.evaluate_resume(jd_text, jd_text)
        assert "ats_match_percent" in evaluation
        assert "relevance_percent" in evaluation
        assert "factuality_score" in evaluation

    def test_revise_resume(self):
        """Test resume revision loop."""
        jd_text = "Python Django React Position."
        agent = TailorAgent()
        evaluation = agent.evaluate_resume(jd_text, jd_text)
        revision = agent.revise_resume(evaluation, max_revisions=2)
        assert "revisions" in revision
        assert "status" in revision


class TestEvaluationAgent:
    """Test cases for the Evaluation Agent."""

    def test_evaluate_basic(self):
        """Test basic evaluation functionality."""
        agent = EvaluationAgent()
        resume_text = "Python Django React SQL Git"
        jd_text = "Python Django React Position. Required skills: Python, Django, React."
        
        evaluation = agent.evaluate(resume_text, jd_text)
        assert "ats_match_percent" in evaluation
        assert "relevance_percent" in evaluation
        assert "factuality_score" in evaluation
        assert "flags" in evaluation
        assert 0 <= evaluation["ats_match_percent"] <= 100
        assert 0 <= evaluation["relevance_percent"] <= 100
        assert 0 <= evaluation["factuality_score"] <= 100

    def test_evaluate_with_flags(self):
        """Test evaluation that produces flags."""
        agent = EvaluationAgent()
        # Resume missing skills present in JD
        resume_text = "Python SQL"  # Missing Django, React
        jd_text = "Python Django React Position. Required skills: Python, Django, React."
        
        evaluation = agent.evaluate(resume_text, jd_text)
        assert len(evaluation["flags"]) > 0  # Should have flags for missing skills
        assert evaluation["factuality_score"] < 100  # Lower score due to flags


class TestRevisionAgent:
    """Test cases for the Revision Agent."""

    def test_revision_initial_status(self):
        """Test revision starts with no flags addressed."""
        agent = RevisionAgent()
        evaluation = {
            "flags": [{"claim": "Resume claims Python but doesn't mention it", "severity": "medium"}],
            "ats_match_percent": 50.0,
            "relevance_percent": 50.0,
            "factuality_score": 75,
        }
        revision = agent.revise(evaluation, max_revisions=3)
        assert "revisions" in revision
        assert revision["status"] in ["completed", "max_revisions_reached"]

    def test_revision_no_flags(self):
        """Test revision when no flags exist."""
        agent = RevisionAgent()
        evaluation = {
            "flags": [],
            "ats_match_percent": 95.0,
            "relevance_percent": 95.0,
            "factuality_score": 100,
        }
        revision = agent.revise(evaluation, max_revisions=3)
        assert revision["status"] == "completed"
        assert len(revision["revisions"]) == 0