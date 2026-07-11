"""
Mock CRM write tool.
GATED: only callable for nurture/disqualify status or post-approval.
Logs every call.
"""
from governance.logger import log_event

# In-memory mock CRM store
_CRM_STORE: dict[str, dict] = {}

ALLOWED_STATUSES = {"nurture", "disqualify", "approved"}


def crm_write(lead_id: str, fields: dict, authorized_by: str = "system") -> dict:
    """
    Write/update a lead record in the mock CRM.
    Only allowed for nurture, disqualify, or approved statuses.
    Raises ValueError if gating condition fails.
    """
    status = str(fields.get("status", "")).lower()
    if status and status not in ALLOWED_STATUSES:
        violation_msg = f"crm_write blocked: status '{status}' not in allowed set {ALLOWED_STATUSES}"
        log_event(
            lead_id=lead_id,
            stage="crm_write_blocked",
            input_snapshot={"fields": fields},
            output_snapshot={"error": violation_msg},
            authorized_by=authorized_by,
        )
        raise PermissionError(violation_msg)

    if lead_id not in _CRM_STORE:
        _CRM_STORE[lead_id] = {}
    _CRM_STORE[lead_id].update(fields)

    log_event(
        lead_id=lead_id,
        stage="crm_write",
        input_snapshot={"fields": fields},
        output_snapshot={"record": _CRM_STORE[lead_id]},
        authorized_by=authorized_by,
    )
    return {"success": True, "lead_id": lead_id, "record": _CRM_STORE[lead_id]}


def crm_read(lead_id: str) -> dict:
    """Read a record from the mock CRM (no gating needed for reads)."""
    return _CRM_STORE.get(lead_id, {})


def clear_crm():
    """Reset CRM store — test use only."""
    _CRM_STORE.clear()
