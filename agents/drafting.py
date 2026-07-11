"""
Drafting Agent — uses llm_call() to compose a personalized first-touch email.
LLM is explicitly instructed to use only verified enrichment facts — no invention.
This agent has NO access to email_send; it only produces a DraftEmail object
that goes into the pending_approval queue.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Callable

from tools.enrichment_lookup import EnrichmentResult
from agents.scoring import ScoreResult
from governance.logger import log_event


@dataclass
class DraftEmail:
    subject: str
    body: str
    facts_used: list[str]   # subset of enrichment fields that grounded the draft

    def to_dict(self) -> dict:
        return asdict(self)


def _fallback_draft(enrichment: EnrichmentResult, score_result: ScoreResult) -> DraftEmail:
    """Deterministic fallback draft — used when LLM is unavailable."""
    facts = [
        f"company={enrichment.company}",
        f"industry={enrichment.industry}",
        f"employee_count={enrichment.employee_count}",
        f"buying_signals={enrichment.buying_signals}",
    ]
    subject = f"Quick question for {enrichment.company}"
    body = (
        f"Hi,\n\n"
        f"I came across {enrichment.company} and noticed you're in the {enrichment.industry} space"
        + (
            f" with some exciting momentum ({', '.join(enrichment.buying_signals)})" 
            if enrichment.buying_signals else ""
        )
        + f".\n\n"
        f"Given your team size (~{enrichment.employee_count} people), "
        f"I think there could be a strong fit with what we offer.\n\n"
        f"Would you be open to a 15-minute call this week?\n\n"
        f"Best regards"
    )
    return DraftEmail(subject=subject, body=body, facts_used=facts)


def draft_email(
    enrichment: EnrichmentResult,
    score_result: ScoreResult,
    lead_id: str = "unknown",
    llm_caller: Callable[[str], str] | None = None,
) -> DraftEmail:
    """
    Draft a personalized first-touch email grounded strictly in enrichment data.
    Uses llm_caller if available, otherwise generates a deterministic fallback.
    """
    facts_used = [
        f"company={enrichment.company}",
        f"industry={enrichment.industry}",
        f"employee_count={enrichment.employee_count}",
        f"buying_signals={enrichment.buying_signals}",
        f"hq_country={enrichment.hq_country}",
    ]

    if llm_caller is not None:
        signals_text = (
            ", ".join(enrichment.buying_signals) if enrichment.buying_signals else "none identified"
        )
        prompt = (
            "You are a B2B sales development rep writing a first-touch outreach email.\n"
            "Use ONLY the verified facts listed below — do NOT invent any information not present.\n"
            "Write a concise, personalized email (subject + body, max 150 words).\n"
            "End with a clear CTA to schedule a brief call.\n\n"
            f"Verified facts:\n"
            f"- Company: {enrichment.company}\n"
            f"- Industry: {enrichment.industry}\n"
            f"- Employee count: {enrichment.employee_count}\n"
            f"- Buying signals: {signals_text}\n"
            f"- HQ country: {enrichment.hq_country}\n"
            f"- ICP score: {score_result.score}/100\n"
            f"- Score rationale: {score_result.reason}\n\n"
            "Format your response as:\n"
            "SUBJECT: <subject line>\n"
            "BODY:\n<email body>\n"
        )
        try:
            raw = llm_caller(prompt).strip()
            lines = raw.splitlines()
            subject = ""
            body_lines: list[str] = []
            in_body = False
            for line in lines:
                if line.startswith("SUBJECT:"):
                    subject = line.replace("SUBJECT:", "").strip()
                elif line.startswith("BODY:"):
                    in_body = True
                elif in_body:
                    body_lines.append(line)
            body = "\n".join(body_lines).strip()
            if not subject:
                subject = f"Quick question for {enrichment.company}"
            if not body:
                raise ValueError("Empty body from LLM")
            draft = DraftEmail(subject=subject, body=body, facts_used=facts_used)
        except Exception:
            draft = _fallback_draft(enrichment, score_result)
    else:
        draft = _fallback_draft(enrichment, score_result)

    log_event(
        lead_id=lead_id,
        stage="drafting",
        input_snapshot={
            "company": enrichment.company,
            "score": score_result.score,
            "facts_used": facts_used,
        },
        output_snapshot=draft.to_dict(),
    )
    return draft
