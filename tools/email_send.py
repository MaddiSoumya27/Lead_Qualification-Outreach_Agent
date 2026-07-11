"""
Mock email send tool.
HARD-GATED: verifies an approval record with matching content hash exists
before sending. Raises PermissionError otherwise.
"""
import hashlib
from governance.logger import log_event

# In-memory approval registry (populated by the human gate before send is called)
_APPROVAL_REGISTRY: dict[str, dict] = {}

# Sent emails store (mock)
_SENT_EMAILS: list[dict] = []


def compute_content_hash(subject: str, body: str) -> str:
    """Deterministic SHA-256 hash of exact subject+body content."""
    payload = f"{subject}\n{body}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def register_approval(lead_id: str, subject: str, body: str, approver: str, timestamp: str) -> str:
    """
    Called by the human gate BEFORE email_send is ever invoked.
    Stores the approval record keyed by lead_id + content hash.
    Returns the content hash.
    """
    content_hash = compute_content_hash(subject, body)
    _APPROVAL_REGISTRY[lead_id] = {
        "content_hash": content_hash,
        "approver": approver,
        "timestamp": timestamp,
        "subject": subject,
        "body": body,
    }
    log_event(
        lead_id=lead_id,
        stage="gate_approved",
        input_snapshot={"subject": subject, "body_length": len(body)},
        output_snapshot={"content_hash": content_hash, "approver": approver},
        gate_decision="approved",
        authorized_by=approver,
    )
    return content_hash


def email_send(lead_id: str, subject: str, body: str, sender: str = "system") -> dict:
    """
    Send email. Hard-checks for a matching approval record (lead_id + content hash).
    Raises PermissionError and logs a violation if no matching record exists.
    """
    content_hash = compute_content_hash(subject, body)
    approval = _APPROVAL_REGISTRY.get(lead_id)

    if approval is None or approval["content_hash"] != content_hash:
        violation_msg = (
            f"email_send BLOCKED for lead {lead_id}: "
            f"no matching approval record for content hash {content_hash[:16]}…"
        )
        log_event(
            lead_id=lead_id,
            stage="email_send_blocked",
            input_snapshot={"subject": subject, "content_hash": content_hash},
            output_snapshot={"error": violation_msg},
            gate_decision="blocked",
        )
        raise PermissionError(violation_msg)

    # Approved — send
    record = {
        "lead_id": lead_id,
        "subject": subject,
        "body": body,
        "content_hash": content_hash,
        "sender": sender,
        "approved_by": approval["approver"],
    }
    _SENT_EMAILS.append(record)
    log_event(
        lead_id=lead_id,
        stage="email_send",
        input_snapshot={"subject": subject, "content_hash": content_hash},
        output_snapshot={"status": "sent", "approved_by": approval["approver"]},
        gate_decision="sent",
        authorized_by=approval["approver"],
    )
    return {"success": True, "lead_id": lead_id, "content_hash": content_hash}


def get_sent_emails() -> list[dict]:
    return list(_SENT_EMAILS)


def get_approval(lead_id: str) -> dict | None:
    return _APPROVAL_REGISTRY.get(lead_id)


def clear_email_store():
    """Reset store — test use only."""
    _APPROVAL_REGISTRY.clear()
    _SENT_EMAILS.clear()
