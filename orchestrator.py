"""
Orchestrator — runs the full pipeline state machine.

  intake -> enrich -> score -> classify -> route -> draft -> gate (Streamlit)
                                                          -> send | sequence | archive

Passes a single LeadState dataclass between stages.
Sanitizes all lead-submitted free text before it ever reaches scoring/drafting.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Optional, Literal

from agents.enrichment import enrich
from agents.scoring import score, ScoreResult
from agents.classification import classify, ClassificationResult
from agents.routing import route
from agents.drafting import draft_email, DraftEmail
from tools.enrichment_lookup import EnrichmentResult
from governance.logger import log_event
from llm_client import llm_call, is_llm_available

# ── Injection detection patterns ─────────────────────────────────────────────
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(prompt|instruction|scoring)", re.I),
    re.compile(r"(mark|classify|set)\s+me\s+(as\s+)?(hot|qualified|vip)", re.I),
    re.compile(r"(email|contact|message)\s+the\s+(ceo|cto|vp|boss|team)", re.I),
    re.compile(r"(bypass|skip|override)\s+(the\s+)?(gate|approval|filter|scoring)", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"disregard\s+(your\s+)?(instructions|scoring|rules)", re.I),
    re.compile(r"as\s+(an?\s+)?ai,?\s+(you\s+)?(must|should|will)", re.I),
    re.compile(r"(forget|ignore)\s+(your\s+)?(previous|system|original)", re.I),
]


def detect_injection(text: str) -> bool:
    """Return True if text appears to contain prompt-injection attempts."""
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    return False


def sanitize_free_text(text: str) -> str:
    """
    Wrap lead-submitted free text in an inert data marker so it can never
    be interpreted as an instruction by downstream LLM calls.
    The LLM prompt templates always place this inside a clearly labelled
    data block — never in the instruction section.
    """
    return f"[LEAD_DATA_START]{text}[LEAD_DATA_END]"


# ── LeadState dataclass ───────────────────────────────────────────────────────

@dataclass
class LeadState:
    # Intake fields (raw — identity fields excluded from scoring)
    lead_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    company: str = ""
    role_title: str = ""
    free_text: str = ""          # lead-submitted note / message

    # Derived during pipeline
    email_domain: str = ""
    sanitized_free_text: str = ""
    injection_detected: bool = False

    enrichment: Optional[EnrichmentResult] = None
    score_result: Optional[ScoreResult] = None
    classification: Optional[ClassificationResult] = None
    draft: Optional[DraftEmail] = None

    # Pipeline status
    status: Literal[
        "intake", "enriched", "scored", "classified",
        "routed", "pending_approval", "approved", "sent",
        "archived", "enrolled"
    ] = "intake"
    pipeline_halted: bool = False
    halt_reason: str = ""


# ── Pipeline runner ───────────────────────────────────────────────────────────

def run_pipeline(lead: LeadState) -> LeadState:
    """
    Execute the full pipeline for a single lead.
    Returns the mutated LeadState with all fields populated.
    """
    llm_caller = llm_call if is_llm_available() else None

    # ── 1. Intake sanitization ────────────────────────────────────────────────
    lead.email_domain = lead.email.split("@")[-1].lower() if "@" in lead.email else lead.email.lower()
    lead.injection_detected = detect_injection(lead.free_text)
    lead.sanitized_free_text = sanitize_free_text(lead.free_text) if lead.free_text else ""

    log_event(
        lead_id=lead.lead_id,
        stage="intake",
        input_snapshot={
            "company": lead.company,
            "role_title": lead.role_title,
            "email_domain": lead.email_domain,
        },
        output_snapshot={"injection_detected": lead.injection_detected},
        injection_detected=lead.injection_detected,
    )

    if lead.injection_detected:
        log_event(
            lead_id=lead.lead_id,
            stage="injection_blocked",
            input_snapshot={"free_text_preview": lead.free_text[:120]},
            output_snapshot={"action": "free_text_quarantined_scoring_continues_from_real_signals"},
            injection_detected=True,
        )
        # Scoring still proceeds normally from enrichment — injection text is quarantined

    # ── 2. Enrich ─────────────────────────────────────────────────────────────
    lead.enrichment = enrich(
        company=lead.company,
        email_domain=lead.email_domain,
        lead_id=lead.lead_id,
    )
    lead.status = "enriched"

    # ── 3. Score ──────────────────────────────────────────────────────────────
    lead.score_result = score(
        enrichment=lead.enrichment,
        role_title=lead.role_title,
        lead_id=lead.lead_id,
        llm_caller=llm_caller,
    )
    lead.status = "scored"

    # ── 4. Classify ───────────────────────────────────────────────────────────
    lead.classification = classify(
        score_result=lead.score_result,
        lead_id=lead.lead_id,
    )
    lead.status = "classified"

    # ── 5. Route ──────────────────────────────────────────────────────────────
    is_hot = route(classification=lead.classification, lead_id=lead.lead_id)

    if not is_hot:
        label = lead.classification.label
        lead.status = "archived" if label == "DISQUALIFY" else "enrolled"
        lead.pipeline_halted = True
        lead.halt_reason = f"Lead {label}: {lead.classification.reason}"
        return lead

    # ── 6. Draft ──────────────────────────────────────────────────────────────
    lead.draft = draft_email(
        enrichment=lead.enrichment,
        score_result=lead.score_result,
        lead_id=lead.lead_id,
        llm_caller=llm_caller,
    )
    lead.status = "pending_approval"

    log_event(
        lead_id=lead.lead_id,
        stage="pending_approval",
        input_snapshot={"score": lead.score_result.score, "label": lead.classification.label},
        output_snapshot={
            "subject": lead.draft.subject,
            "body_length": len(lead.draft.body),
        },
    )
    return lead
