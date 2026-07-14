"""
Classification Agent — deterministic threshold-based classification.
HOT / NURTURE / DISQUALIFY derived entirely from score + icp_config.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional, Literal

from agents.scoring import ScoreResult
from governance.logger import log_event

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "icp_config.json")

ClassLabel = Literal["HOT", "NURTURE", "DISQUALIFY"]


@dataclass
class ClassificationResult:
    label: ClassLabel
    score: int
    reason: str       # carried through from ScoreResult unchanged

    def to_dict(self) -> dict:
        return asdict(self)


def classify(
    score_result: ScoreResult,
    icp_config: Optional[dict] = None,
    lead_id: str = "unknown",
) -> ClassificationResult:
    """
    Apply score thresholds from icp_config to produce a classification label.
    The scoring reason is carried through unchanged for traceability.
    """
    if icp_config is None:
        with open(os.path.abspath(_CONFIG_PATH)) as f:
            icp_config = json.load(f)

    thresholds = icp_config["thresholds"]
    s = score_result.score

    if s >= thresholds["HOT"]:
        label: ClassLabel = "HOT"
    elif s >= thresholds["NURTURE"]:
        label = "NURTURE"
    else:
        label = "DISQUALIFY"

    result = ClassificationResult(
        label=label,
        score=s,
        reason=score_result.reason,
    )

    log_event(
        lead_id=lead_id,
        stage="classification",
        input_snapshot={"score": s, "thresholds": thresholds},
        output_snapshot=result.to_dict(),
        classification=label,
    )
    return result
