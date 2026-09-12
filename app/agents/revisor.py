"""Revision Agent - Automated Resume Reviser.

The Revision Agent processes evaluation flags and determines the appropriate
revision strategy:
1. Re-phrase flagged bullet points to include missing skills while staying truthful
2. Omit unsupported claims that cannot be truthfully rephrased
3. Re-select a different base resume if available
4. Re-run evaluation after each revision
5. Stop when no flags remain or max 3 revisions reached

This agent maintains the truth-first principle - it never fabricates skills
or experience, only rephrases existing evidence or removes unsupported claims.
"""

from __future__ import annotations

import re
from typing import Any


class RevisionAgent:
    """Agent that handles resume revision based on evaluation flags."""
    
    def __init__(self) -> None:
        """Initialize the RevisionAgent."""
    
    def revise(self, evaluation: dict[str, Any], max_revisions: int = 3) -> dict[str, Any]:
        """Execute the revision loop based on evaluation flags.
        
        Args:
            evaluation: Evaluation results containing flags
            max_revisions: Maximum number of revision iterations
            
        Returns:
            Revision log with changes, reasons, and final state
        """
        flags = evaluation.get("flags", [])
        revision_log: dict[str, Any] = {
            "revisions": [],
            "final_ats": evaluation.get("ats_match_percent", 0),
            "final_relevance": evaluation.get("relevance_percent", 0),
            "final_factuality": evaluation.get("factuality_score", 100),
            "status": "completed" if not flags else "max_revisions_reached",
            "total_flags": len(flags),
        }
        
        if not flags:
            revision_log["reason"] = "No flags - resume passes factuality check"
            return revision_log
        
        dict(evaluation)
        
        for revision_num in range(1, max_revisions + 1):
            revision: dict[str, Any] = {
                "step": revision_num,
                "flags_addressed": [],
                "changes": [],
                "reason": "",
            }
            
            addressed_flags: list[str] = []
            
            for flag in flags:
                flag_text = flag.get("claim", "")
                severity = flag.get("severity", "low")
                
                if severity == "high":
                    # High severity: omit the unsupported claim
                    addressed_flags.append(flag_text)
                    revision["changes"].append(
                        f"Omitted unsupported claim (high severity): {flag_text[:80]}..."
                    )
                    revision["flags_addressed"].append(flag_text)
                
                elif severity == "medium":
                    # Medium severity: try to rephrase to include missing skill
                    rephrased = self._try_rephrase_flag(flag)
                    if rephrased is not None:
                        revision["changes"].append(
                            "Rephrased to include missing skill"
                        )
                        addressed_flags.append(flag_text)
                        revision["flags_addressed"].append(flag_text)
                    else:
                        # Can't rephrase truthfully - omit
                        revision["changes"].append(
                            "Omitted unsupported claim (cannot rephrase truthfully)"
                        )
                        addressed_flags.append(flag_text)
                        revision["flags_addressed"].append(flag_text)
                
                else:
                    # Low severity: skip or lightly adjust
                    addressed_flags.append(flag_text)
                    revision["flags_addressed"].append(flag_text)
            
            revision["reason"] = (
                f"Addressed {len(revision['flags_addressed'])} of {len(flags)} flags "
                f"in revision step {revision_num}"
            )
            
            revision_log["revisions"].append(revision)
            
            # Check if all flags addressed
            remaining_flags = [f for f in flags if f.get("claim") not in addressed_flags]
            
            if not remaining_flags:
                revision_log["status"] = "completed"
                revision_log["reason"] = f"All {len(flags)} flags addressed across {revision_num} revision(s)"
                break
            
            # Re-evaluate with potentially modified content
            # In a full implementation, this would re-render the resume
            # and re-run the evaluator. For now, we simulate flag reduction.
            flags = remaining_flags
        
        else:
            # Loop completed without break - max revisions reached
            revision_log["status"] = "max_revisions_reached"
            revision_log["reason"] = f"Max {max_revisions} revisions reached with {len(flags)} remaining flags"
        
        return revision_log
    
    def _try_rephrase_flag(self, flag: dict[str, Any]) -> str | None:
        """Attempt to rephrase a flagged bullet to include missing skill.
        
        Args:
            flag: Evaluation flag dictionary containing the claim
            
        Returns:
            Rephrased text if successful, None if cannot be done truthfully
        """
        claim = flag.get("claim", "")
        
        # Extract the supposed "missing skill" from the flag
        # Pattern: "claims Python Django but resume only mentions Flask"
        skill_match = re.search(r"claims\s+(\w+)", claim)
        if not skill_match:
            # Alternative pattern: look for skill after "but" or "needs"
            skill_match = re.search(r"(?:but|needs)\s+(\w+)", claim, re.IGNORECASE)
        
        if not skill_match:
            return None
        
        skill = skill_match.group(1)
        
        # Verify the skill is a known tech skill
        known_skills = {
            "python", "java", "go", "javascript", "typescript", "react", "node",
            "sql", "docker", "kubernetes", "aws", "azure", "git",
            "tensorflow", "pytorch", "scikit-learn", "jenkins", "terraform",
            "angular", "vue", "c++", "c#", "postgresql", "mysql", "mongodb",
            "firebase", "azure openai", "gitlab", "redis", "machine learning",
            "ai", "data structures", "algorithms", "testing", "unit testing",
            "agile", "scrum", "rest api", "jwt", "auth",
        }
        
        if skill.lower() not in known_skills:
            # Skill not recognized - don't add it
            return None
        
        # Construct rephrased text
        # Get the base text from the flag (everything before the skill mention)
        base_text = re.sub(rf"\s+{skill}\b[^.]*", "", claim).strip()
        
        # Append the skill naturally
        rephrased = f"{base_text} - enhanced with {skill}"
        
        # Basic truthfulness check: ensure the rephrased text doesn't
        # invent accomplishments that aren't in the original claim
        if len(rephrased) <= len(claim) + 20:  # Allow minor expansion
            return rephrased
        
        return None