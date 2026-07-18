"""
Append-only JSONL governance logger.
Every pipeline stage transition and tool call writes one entry here.
"""
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "logs", "audit.jsonl")


def _ensure_log_dir():
    os.makedirs(os.path.dirname(os.path.abspath(LOG_PATH)), exist_ok=True)


def log_event(
    lead_id: str,
    stage: str,
    input_snapshot: Any = None,
    output_snapshot: Any = None,
    injection_detected: bool = False,
    gate_decision: Optional[str] = None,
    authorized_by: Optional[str] = None,
    email: Optional[str] = None,
    classification: Optional[str] = None,
    extra: Optional[dict] = None,
):
    """Append one structured entry to the audit JSONL log."""
    _ensure_log_dir()
    entry = {
        "lead_id": lead_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "input_snapshot": input_snapshot,
        "output_snapshot": output_snapshot,
        "injection_detected": injection_detected,
        "gate_decision": gate_decision,
        "authorized_by": authorized_by,
        "email": email,
        "classification": classification,
    }
    if extra:
        entry.update(extra)
    with open(os.path.abspath(LOG_PATH), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def query_log(lead_id: Optional[str] = None, stage: Optional[str] = None, classification: Optional[str] = None, limit: Optional[int] = None) -> list[dict]:
    """Return all log entries, optionally filtered by lead_id, stage, and/or classification."""
    _ensure_log_dir()
    path = os.path.abspath(LOG_PATH)
    if not os.path.exists(path):
        return []
    results = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if lead_id and entry.get("lead_id") != lead_id:
                continue
            if stage and entry.get("stage") != stage:
                continue
            if classification and entry.get("classification") != classification:
                continue
            results.append(entry)
            
            # Apply limit if specified
            if limit and len(results) >= limit:
                break
    
    return results


def sends_without_approval() -> list[dict]:
    """
    Governance check: return any email_send log entries that have no matching
    approval record (same lead_id + matching content hash).
    """
    all_entries = query_log()
    approvals = {
        e["lead_id"]: e.get("output_snapshot", {})
        for e in all_entries
        if e.get("stage") == "gate_approved"
    }
    violations = []
    for e in all_entries:
        if e.get("stage") == "email_send":
            lid = e.get("lead_id")
            sent_hash = (e.get("input_snapshot") or {}).get("content_hash")
            approved_hash = (approvals.get(lid) or {}).get("content_hash")
            if lid not in approvals or sent_hash != approved_hash:
                violations.append(e)
    return violations


def clear_log():
    """Wipe the log — only for use in tests."""
    path = os.path.abspath(LOG_PATH)
    if os.path.exists(path):
        os.remove(path)
