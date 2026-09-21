"""Typed positions, never votes, approvals or instructions to execute."""

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Reference = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=512)]


class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    verdict: Literal["proceed", "revise", "insufficient_evidence"]
    rationale: str = Field(min_length=1, max_length=800)
    next_check: str = Field(min_length=1, max_length=500)
    references: list[Reference] = Field(max_length=8)


def source_catalog(evidence):
    """Existence in this catalog is not a claim that a source supports a position."""
    if not evidence:
        return []
    sources = {}
    sha = evidence.get("github_sha")
    if isinstance(sha, str) and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", sha):
        sources[f"commit:{sha}"] = f"Commit {sha}"
    for item in evidence.get("files", []):
        path = item.get("path")
        if isinstance(path, str) and 1 <= len(path) <= 507:
            sources[f"file:{path}"] = path
    for item in evidence.get("browser", []):
        width = item.get("viewport")
        if type(width) is int and width in (320, 768, 1440) and "http_status" in item and not item.get("error"):
            sources[f"view:{width}"] = f"Browser observation {width} px"
    return [{"id": key, "label": label} for key, label in sorted(sources.items())]


def validate_assessment(value, evidence):
    assessment = Assessment.model_validate(value)
    allowed = {source["id"] for source in source_catalog(evidence)}
    if any(reference not in allowed for reference in assessment.references):
        raise ValueError("Assessment references must identify collected sources")
    return assessment.model_dump()


def decision_view(mission):
    if not mission["decision_question"]:
        return None
    latest = {turn["agent"]: turn for turn in mission["turns"]}
    positions = []
    for agent in mission["agents"]:
        turn = latest.get(agent)
        positions.append({
            "agent": agent,
            "turn_id": turn["id"] if turn else None,
            "status": turn["status"] if turn else "pending",
            "assessment": turn["assessment"] if turn and turn["status"] == "done" else None,
        })
    assessed = [position["assessment"] for position in positions if position["assessment"] is not None]
    verdicts = {assessment["verdict"] for assessment in assessed}
    agreement = "mixed" if len(verdicts) > 1 else "aligned" if len(assessed) == len(positions) and assessed else "none"
    return {
        "question": mission["decision_question"],
        "positions": positions,
        "agreement": agreement,
        "complete": mission["status"] == "finished" and len(assessed) == len(positions),
        "references": source_catalog(mission["evidence"]),
    }
