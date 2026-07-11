"""
Mock enrichment lookup tool.
Returns firmographic data from a local dataset.
Logs every call to the governance log.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Optional
from governance.logger import log_event

# ── Mock dataset ──────────────────────────────────────────────────────────────
_MOCK_DB: dict[str, dict] = {
    "acmecorp.com": {
        "company": "Acme Corp",
        "domain": "acmecorp.com",
        "industry": "SaaS",
        "employee_count": 320,
        "hq_country": "US",
        "buying_signals": ["recently_funded", "hiring_sales_roles"],
    },
    "globex.io": {
        "company": "Globex",
        "domain": "globex.io",
        "industry": "FinTech",
        "employee_count": 1200,
        "hq_country": "US",
        "buying_signals": ["new_product_launch", "expanding_to_new_markets"],
    },
    "initech.net": {
        "company": "Initech",
        "domain": "initech.net",
        "industry": "Consulting",
        "employee_count": 80,
        "hq_country": "US",
        "buying_signals": [],
    },
    "umbrella.org": {
        "company": "Umbrella Corp",
        "domain": "umbrella.org",
        "industry": "Non-profit",
        "employee_count": 15,
        "hq_country": "US",
        "buying_signals": [],
    },
    "hooli.co": {
        "company": "Hooli",
        "domain": "hooli.co",
        "industry": "MarTech",
        "employee_count": 750,
        "hq_country": "US",
        "buying_signals": ["recently_funded"],
    },
    "piedpiper.com": {
        "company": "Pied Piper",
        "domain": "piedpiper.com",
        "industry": "SaaS",
        "employee_count": 45,
        "hq_country": "US",
        "buying_signals": ["new_product_launch"],
    },
}


@dataclass
class EnrichmentResult:
    company: str
    domain: str
    industry: str
    employee_count: int
    hq_country: str
    buying_signals: list[str]
    found: bool  # False when no match in dataset

    def to_dict(self) -> dict:
        return asdict(self)


def enrichment_lookup(company: str, domain: str, lead_id: str = "unknown") -> EnrichmentResult:
    """
    Look up firmographic data by domain (primary) or company name (fallback).
    Always logs the call. Returns a 'not-found' result when no match.
    """
    domain_key = domain.lower().strip()
    record = _MOCK_DB.get(domain_key)

    # Fallback: fuzzy company name match
    if record is None:
        for key, val in _MOCK_DB.items():
            if val["company"].lower() == company.lower().strip():
                record = val
                break

    if record:
        result = EnrichmentResult(
            company=record["company"],
            domain=record["domain"],
            industry=record["industry"],
            employee_count=record["employee_count"],
            hq_country=record["hq_country"],
            buying_signals=record["buying_signals"],
            found=True,
        )
    else:
        result = EnrichmentResult(
            company=company,
            domain=domain,
            industry="Unknown",
            employee_count=0,
            hq_country="Unknown",
            buying_signals=[],
            found=False,
        )

    log_event(
        lead_id=lead_id,
        stage="enrichment_lookup",
        input_snapshot={"company": company, "domain": domain},
        output_snapshot=result.to_dict(),
    )
    return result
