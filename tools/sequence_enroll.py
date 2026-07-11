"""
Mock sequence enrollment tool for NURTURE leads.
"""
from governance.logger import log_event

_ENROLLED: list[dict] = []


def sequence_enroll(lead_id: str, sequence_name: str, reason: str) -> dict:
    record = {"lead_id": lead_id, "sequence_name": sequence_name, "reason": reason}
    _ENROLLED.append(record)
    log_event(
        lead_id=lead_id,
        stage="sequence_enroll",
        input_snapshot={"sequence_name": sequence_name},
        output_snapshot={"reason": reason, "status": "enrolled"},
    )
    return {"success": True, **record}


def get_enrolled() -> list[dict]:
    return list(_ENROLLED)


def clear_enrolled():
    _ENROLLED.clear()
