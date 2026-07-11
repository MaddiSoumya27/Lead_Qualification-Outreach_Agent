"""
test_hot_lead.py — Output layer
Strong ICP match -> HOT, non-empty cited reason, draft exists,
status == pending_approval, email_send never called.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from orchestrator import LeadState, run_pipeline
from tools.email_send import get_sent_emails, clear_email_store
from governance.logger import clear_log


@pytest.fixture(autouse=True)
def reset():
    clear_email_store()
    clear_log()
    yield
    clear_email_store()
    clear_log()


def make_hot_lead(**overrides) -> LeadState:
    """Strong ICP match: SaaS company, ideal size, VP Sales role, positive buying signals."""
    defaults = dict(
        first_name="Alex",
        last_name="Rivera",
        email="alex@acmecorp.com",
        company="Acme Corp",
        role_title="VP Sales",
        free_text="Looking forward to connecting.",
    )
    defaults.update(overrides)
    return LeadState(**defaults)


def test_hot_classification():
    lead = run_pipeline(make_hot_lead())
    assert lead.classification is not None
    assert lead.classification.label == "HOT", (
        f"Expected HOT, got {lead.classification.label} (score={lead.score_result.score})"
    )


def test_hot_has_cited_reason():
    lead = run_pipeline(make_hot_lead())
    assert lead.classification.reason, "Reason string must be non-empty"
    assert len(lead.classification.reason) > 10, "Reason must be substantive"


def test_hot_draft_exists():
    lead = run_pipeline(make_hot_lead())
    assert lead.draft is not None, "Draft must be created for HOT leads"
    assert lead.draft.subject, "Draft subject must be non-empty"
    assert lead.draft.body, "Draft body must be non-empty"
    assert lead.draft.facts_used, "facts_used must list at least one grounding fact"


def test_hot_status_pending_approval():
    lead = run_pipeline(make_hot_lead())
    assert lead.status == "pending_approval", (
        f"Expected status 'pending_approval', got '{lead.status}'"
    )


def test_email_never_sent_without_approval():
    run_pipeline(make_hot_lead())
    sent = get_sent_emails()
    assert sent == [], (
        f"email_send must NOT be called during pipeline — {len(sent)} sent emails found"
    )
