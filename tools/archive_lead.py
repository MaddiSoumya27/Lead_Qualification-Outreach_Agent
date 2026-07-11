"""
Mock archive tool for DISQUALIFY leads.
"""
from governance.logger import log_event

_ARCHIVE: list[dict] = []


def archive_lead(lead_id: str, reason: str) -> dict:
    record = {"lead_id": lead_id, "reason": reason}
    _ARCHIVE.append(record)
    log_event(
        lead_id=lead_id,
        stage="archive_lead",
        input_snapshot={"reason": reason},
        output_snapshot={"status": "archived"},
    )
    return {"success": True, **record}


def get_archived() -> list[dict]:
    return list(_ARCHIVE)


def clear_archive():
    _ARCHIVE.clear()
