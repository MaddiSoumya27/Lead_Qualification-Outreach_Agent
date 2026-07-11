"""
test_approval_gate.py — Human gate layer
1. Draft created -> edited -> approval record written -> THEN email_send succeeds.
2. Calling email_send before an approval record exists raises PermissionError and logs a violation.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from orchestrator import LeadState, run_pipeline
from tools.email_send import (
    email_send, register_approval, get_sent_emails,
    get_approval, clear_email_store,
)
from governance.logger import clear_log, query_log, sends_without_approval


@pytest.fixture(autouse=True)
def reset():
    clear_email_store()
    clear_log()
    yield
    clear_email_store()
    clear_log()


def make_hot_lead() -> LeadState:
    return LeadState(
        first_name="Jordan",
        last_name="Kim",
        email="jordan@acmecorp.com",
        company="Acme Corp",
        role_title="VP Sales",
        free_text="",
    )


def test_send_blocked_without_approval():
    """email_send must raise PermissionError when no approval record exists."""
    lead = run_pipeline(make_hot_lead())
    assert lead.draft is not None

    with pytest.raises(PermissionError):
        email_send(
            lead_id=lead.lead_id,
            subject=lead.draft.subject,
            body=lead.draft.body,
        )


def test_send_blocked_logs_violation():
    """The blocked send attempt must be logged in the governance log."""
    lead = run_pipeline(make_hot_lead())
    try:
        email_send(lead.lead_id, lead.draft.subject, lead.draft.body)
    except PermissionError:
        pass
    entries = query_log(lead_id=lead.lead_id, stage="email_send_blocked")
    assert entries, "Blocked send attempt must be logged as 'email_send_blocked'"


def test_send_succeeds_after_approval():
    """After register_approval, email_send must succeed with the same content."""
    lead = run_pipeline(make_hot_lead())
    assert lead.draft is not None

    register_approval(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=lead.draft.body,
        approver="TestApprover",
        timestamp="2026-01-01T00:00:00Z",
    )
    result = email_send(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=lead.draft.body,
    )
    assert result["success"] is True
    sent = get_sent_emails()
    assert len(sent) == 1
    assert sent[0]["lead_id"] == lead.lead_id


def test_edited_draft_requires_matching_hash():
    """Approving original draft then sending edited content must fail."""
    lead = run_pipeline(make_hot_lead())
    assert lead.draft is not None

    # Approve original
    register_approval(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=lead.draft.body,
        approver="TestApprover",
        timestamp="2026-01-01T00:00:00Z",
    )

    # Try to send edited content (different hash) — must be blocked
    with pytest.raises(PermissionError):
        email_send(
            lead_id=lead.lead_id,
            subject=lead.draft.subject,
            body=lead.draft.body + " INJECTED EXTRA CONTENT",
        )


def test_edited_draft_approved_correctly():
    """Approving the edited version then sending it must succeed."""
    lead = run_pipeline(make_hot_lead())
    edited_body = lead.draft.body + " Best wishes!"

    register_approval(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=edited_body,
        approver="TestApprover",
        timestamp="2026-01-01T00:00:00Z",
    )
    result = email_send(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=edited_body,
    )
    assert result["success"] is True


def test_zero_sends_without_approval_after_clean_run():
    """Governance check: after a clean approved send, no violations reported."""
    lead = run_pipeline(make_hot_lead())
    register_approval(
        lead_id=lead.lead_id,
        subject=lead.draft.subject,
        body=lead.draft.body,
        approver="TestApprover",
        timestamp="2026-01-01T00:00:00Z",
    )
    email_send(lead.lead_id, lead.draft.subject, lead.draft.body)
    assert sends_without_approval() == [], "Governance check must return zero violations"
