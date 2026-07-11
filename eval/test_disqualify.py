"""
test_disqualify.py — Governance layer
Personal email + no company signal -> DISQUALIFY, archived with reason,
zero calls to email_send or sequence_enroll.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from orchestrator import LeadState, run_pipeline
from tools.email_send import get_sent_emails, clear_email_store
from tools.sequence_enroll import get_enrolled, clear_enrolled
from tools.archive_lead import get_archived, clear_archive
from governance.logger import clear_log, query_log


@pytest.fixture(autouse=True)
def reset():
    clear_email_store()
    clear_enrolled()
    clear_archive()
    clear_log()
    yield
    clear_email_store()
    clear_enrolled()
    clear_archive()
    clear_log()


def make_disqualify_lead(**overrides) -> LeadState:
    """Personal email, non-profit industry, intern role -> should DISQUALIFY."""
    defaults = dict(
        first_name="Sam",
        last_name="Nobody",
        email="sam@gmail.com",          # personal domain → penalty
        company="Umbrella Corp",        # non-profit in mock DB
        role_title="Intern",
        free_text="",
    )
    defaults.update(overrides)
    return LeadState(**defaults)


def test_disqualify_classification():
    lead = run_pipeline(make_disqualify_lead())
    assert lead.classification.label == "DISQUALIFY", (
        f"Expected DISQUALIFY, got {lead.classification.label} (score={lead.score_result.score})"
    )


def test_disqualify_archived_with_reason():
    lead = run_pipeline(make_disqualify_lead())
    archived = get_archived()
    assert len(archived) >= 1, "Lead must be archived"
    entry = next((a for a in archived if a["lead_id"] == lead.lead_id), None)
    assert entry is not None, "Archived entry must match lead_id"
    assert entry["reason"], "Archived reason must be non-empty"


def test_disqualify_no_email_sent():
    run_pipeline(make_disqualify_lead())
    assert get_sent_emails() == [], "email_send must not be called for DISQUALIFY leads"


def test_disqualify_no_sequence_enrolled():
    run_pipeline(make_disqualify_lead())
    assert get_enrolled() == [], "sequence_enroll must not be called for DISQUALIFY leads"


def test_disqualify_logged():
    lead = run_pipeline(make_disqualify_lead())
    entries = query_log(lead_id=lead.lead_id, stage="archive_lead")
    assert entries, "archive_lead stage must be logged in governance log"
