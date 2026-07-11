"""
Enrichment Agent — wraps the enrichment_lookup tool.
Deterministic, no LLM needed.
"""
from tools.enrichment_lookup import EnrichmentResult, enrichment_lookup


def enrich(company: str, email_domain: str, lead_id: str = "unknown") -> EnrichmentResult:
    """
    Look up firmographic data for a lead.
    Returns an EnrichmentResult (found=False when no match).
    """
    return enrichment_lookup(company=company, domain=email_domain, lead_id=lead_id)
