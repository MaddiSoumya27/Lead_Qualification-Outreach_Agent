"""
Routing Agent — deterministic dispatch based on classification label.
  DISQUALIFY -> archive_lead()
  NURTURE    -> sequence_enroll() + crm_write(status=nurture)
  HOT        -> returns True (passes to Drafting Agent)
"""
from __future__ import annotations
from agents.classification import ClassificationResult
from tools.archive_lead import archive_lead
from tools.sequence_enroll import sequence_enroll
from tools.crm_write import crm_write
from governance.logger import log_event


def route(
    classification: ClassificationResult,
    lead_id: str,
    sequence_name: str = "default_nurture",
) -> bool:
    """
    Route the lead based on its classification label.
    Returns True only for HOT (continues to drafting), False otherwise.
    """
    label = classification.label
    reason = classification.reason

    if label == "DISQUALIFY":
        archive_lead(lead_id=lead_id, reason=reason)
        crm_write(lead_id=lead_id, fields={"status": "disqualify", "reason": reason})
        log_event(
            lead_id=lead_id,
            stage="routing",
            input_snapshot={"label": label},
            output_snapshot={"action": "archived"},
        )
        return False

    if label == "NURTURE":
        sequence_enroll(lead_id=lead_id, sequence_name=sequence_name, reason=reason)
        crm_write(lead_id=lead_id, fields={"status": "nurture", "reason": reason})
        log_event(
            lead_id=lead_id,
            stage="routing",
            input_snapshot={"label": label},
            output_snapshot={"action": "sequence_enrolled"},
        )
        return False

    # HOT
    log_event(
        lead_id=lead_id,
        stage="routing",
        input_snapshot={"label": label},
        output_snapshot={"action": "passed_to_drafting"},
    )
    return True
