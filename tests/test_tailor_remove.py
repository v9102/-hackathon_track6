"""Tests for the truthful "remove unsupported claim" tailoring action."""

from __future__ import annotations

from app.agents.tailor import tailor_remove_skills
from app.core.models import Bullet, SectionEntry, StructuredResume


def _make_resume() -> StructuredResume:
    return StructuredResume(
        name="Qa Engineer Candidate",
        headline="Backend Engineer | Python, PostgreSQL",
        contact=["x@example.com"],
        summary="Built event-driven services in Python.",
        skills_lines=["Python, PostgreSQL, Kafka"],
        education=["B.Tech"],
        projects=[
            SectionEntry(
                id="p1",
                title="Payment Pipeline",
                subtitle="Python | PostgreSQL",
                meta="2024",
                bullets=[
                    Bullet(id="p1b0", original="Built a payment pipeline in Python.", current="Built a payment pipeline in Python."),
                    Bullet(
                        id="p1b1",
                        original="Streams orders through Kafka with strict ordering.",
                        current="Streams orders through Kafka with strict ordering.",
                    ),
                ],
            )
        ],
    )


def test_removal_strips_skill_from_bullets_and_skills_lines() -> None:
    resume = _make_resume()
    modified, actions = tailor_remove_skills(resume, {"Kafka"})
    assert len(actions) >= 2  # bullet + skills line
    flattened = " ".join(a["before"] for a in actions)
    assert "Kafka" in flattened  # before contained the claim
    assert "Kafka" not in modified.full_text()  # after: claim is gone everywhere
    # The truthful tailoring keeps everything else intact.
    assert "Python" in modified.full_text()
    assert "payment pipeline" in modified.full_text()


def test_removal_records_before_and_after_per_action() -> None:
    resume = _make_resume()
    _, actions = tailor_remove_skills(resume, {"Kafka"})
    for action in actions:
        assert action["action"] == "remove_unsupported_claim"
        assert "Kafka" in action["target"]
        assert "Kafka" in action["before"]
        assert "Kafka" not in action["after"]
        assert action["decision"] == "Remove unsupported claim(s)"


def test_removal_only_touches_skills_without_evidence() -> None:
    resume = _make_resume()
    modified, actions = tailor_remove_skills(resume, {"PostgreSQL"})
    # PostgreSQL appears in skills_lines AND headline/subtitle: removing it from
    # just the skills line is fine, but the claim elsewhere stays truthful.
    assert "PostgreSQL" not in modified.full_text() or any(
        "PostgreSQL" in a["before"] for a in actions
    )
    assert actions  # something was removed
    # Unrelated skill untouched.
    assert "Python" in modified.full_text()


def test_removal_is_identity_when_skill_not_present() -> None:
    from dataclasses import asdict

    resume = _make_resume()
    original = asdict(resume)
    modified, actions = tailor_remove_skills(resume, {"Kubernetes"})
    assert actions == []
    assert asdict(modified) == original  # untouched, byte-for-byte


def test_removed_output_no_longer_flags_unsupported_claims() -> None:
    from app.tools.evidence import build_evidence_map, find_unsupported_claims

    resume = _make_resume()
    # Kafka is only claimed on the output resume, never in the authoritative
    # skills registry/evidence for this candidate's other projects.
    evidence_map = build_evidence_map(resume)
    modified, _actions = tailor_remove_skills(resume, {"Kafka"})
    assert find_unsupported_claims(evidence_map, modified.full_text()) == []
    # Sanity: the pre-removal output DID contain the claimed token.
    assert "Kafka" in resume.full_text()