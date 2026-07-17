"""
Enrichment lookup tool — firmographic data with a real-API-first, mock-fallback strategy.

Provider resolution order (controlled by ENRICHMENT_PROVIDER env var or icp_config.json):
  1. clearbit  — Clearbit Enrichment API  (requires CLEARBIT_API_KEY)
  2. pdl        — People Data Labs Company API (requires PDL_API_KEY)
  3. mock       — local 6-company dataset (always available, used as final fallback)

Enhanced with Redis caching to reduce API calls and improve performance.

When a live provider is configured but returns no result for a domain, the chain
continues to the next provider, then the mock, and finally a zero-value 'not-found'
record.  A network or auth error from a live provider is caught, logged, and the
chain continues — the pipeline never hard-fails because of an enrichment outage.

Environment variables:
  ENRICHMENT_PROVIDER   one of  clearbit | pdl | mock  (default: mock)
  CLEARBIT_API_KEY      secret key for Clearbit
  PDL_API_KEY           secret key for People Data Labs
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from governance.logger import log_event
from cache import get_enrichment_cache, set_enrichment_cache
from database.connection import get_session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# EnrichmentResult dataclass — public contract; shape is unchanged from v1
# ---------------------------------------------------------------------------

@dataclass
class EnrichmentResult:
    company: str
    domain: str
    industry: str
    employee_count: int
    hq_country: str
    buying_signals: list[str]
    found: bool          # False when every provider returned nothing
    provider: str = "mock"  # which provider ultimately supplied the data

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    """Return the enrichment sub-block from icp_config.json, or {} if absent."""
    cfg_path = Path(__file__).parent.parent / "config" / "icp_config.json"
    try:
        with cfg_path.open() as fh:
            return json.load(fh).get("enrichment", {})
    except Exception:
        return {}


def _resolve_provider() -> str:
    """
    Determine the active provider.
    Priority: ENRICHMENT_PROVIDER env var → icp_config.json enrichment.provider → 'mock'
    """
    env_val = os.getenv("ENRICHMENT_PROVIDER", "").strip().lower()
    if env_val in ("clearbit", "pdl", "mock"):
        return env_val
    cfg_val = _load_config().get("provider", "mock").strip().lower()
    return cfg_val if cfg_val in ("clearbit", "pdl", "mock") else "mock"


# ---------------------------------------------------------------------------
# Mock dataset (always available as fallback)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------

def _lookup_clearbit(domain: str) -> Optional[dict]:
    """
    Query Clearbit Company Enrichment API.
    Docs: https://dashboard.clearbit.com/docs#enrichment-api-company-api
    Returns a normalised dict on success, None when not found or on error.
    """
    api_key = os.getenv("CLEARBIT_API_KEY", "").strip()
    if not api_key:
        logger.debug("Clearbit: CLEARBIT_API_KEY not set — skipping.")
        return None

    try:
        import requests  # lazy import; not required if mock-only
        resp = requests.get(
            "https://company.clearbit.com/v2/companies/find",
            params={"domain": domain},
            auth=(api_key, ""),
            timeout=5,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            logger.warning("Clearbit: invalid API key (401).")
            return None
        resp.raise_for_status()
        data = resp.json()

        # Map Clearbit fields → internal schema
        metrics = data.get("metrics") or {}
        geo = data.get("geo") or {}
        tags = data.get("tags") or []

        # Derive buying signals from Clearbit metadata
        buying_signals: list[str] = []
        if data.get("crunchbase", {}) and data["crunchbase"].get("handle"):
            buying_signals.append("recently_funded")  # has Crunchbase entry → funded company
        if any(t in tags for t in ("hiring", "growth")):
            buying_signals.append("hiring_sales_roles")

        return {
            "company": data.get("name") or domain,
            "domain": data.get("domain") or domain,
            "industry": (data.get("category") or {}).get("industry") or "Unknown",
            "employee_count": metrics.get("employees") or 0,
            "hq_country": geo.get("countryCode") or "Unknown",
            "buying_signals": buying_signals,
        }

    except Exception as exc:
        logger.warning("Clearbit lookup failed for %s: %s", domain, exc)
        return None


def _lookup_pdl(domain: str) -> Optional[dict]:
    """
    Query People Data Labs Company Enrichment API.
    Docs: https://docs.peopledatalabs.com/docs/company-enrichment-api
    Returns a normalised dict on success, None when not found or on error.
    """
    api_key = os.getenv("PDL_API_KEY", "").strip()
    if not api_key:
        logger.debug("PDL: PDL_API_KEY not set — skipping.")
        return None

    try:
        import requests
        resp = requests.get(
            "https://api.peopledatalabs.com/v5/company/enrich",
            params={"website": domain},
            headers={"X-Api-Key": api_key},
            timeout=5,
        )
        if resp.status_code == 404:
            return None
        if resp.status_code == 401:
            logger.warning("PDL: invalid API key (401).")
            return None
        resp.raise_for_status()
        data = resp.json()

        # Map PDL fields → internal schema
        size_raw: str = data.get("size") or ""          # e.g. "51-200"
        employee_count = _parse_pdl_size(size_raw)

        buying_signals: list[str] = []
        tags: list[str] = data.get("tags") or []
        if any("fund" in t.lower() for t in tags):
            buying_signals.append("recently_funded")
        if any("hiring" in t.lower() for t in tags):
            buying_signals.append("hiring_sales_roles")

        return {
            "company": data.get("name") or domain,
            "domain": data.get("website") or domain,
            "industry": data.get("industry") or "Unknown",
            "employee_count": employee_count,
            "hq_country": (data.get("location") or {}).get("country") or "Unknown",
            "buying_signals": buying_signals,
        }

    except Exception as exc:
        logger.warning("PDL lookup failed for %s: %s", domain, exc)
        return None


def _parse_pdl_size(size_str: str) -> int:
    """Convert PDL size band (e.g. '51-200') to an integer midpoint."""
    if not size_str:
        return 0
    try:
        if "-" in size_str:
            lo, hi = size_str.split("-", 1)
            return (int(lo.strip()) + int(hi.strip())) // 2
        # handles '10001+' style
        return int("".join(filter(str.isdigit, size_str)))
    except (ValueError, AttributeError):
        return 0


def _lookup_mock(domain: str, company: str) -> Optional[dict]:
    """Return a record from the local mock dataset, or None."""
    record = _MOCK_DB.get(domain.lower().strip())
    if record is None:
        # Fallback: fuzzy company name match
        for val in _MOCK_DB.values():
            if val["company"].lower() == company.lower().strip():
                record = val
                break
    return record


# ---------------------------------------------------------------------------
# Provider chain
# ---------------------------------------------------------------------------

def _resolve_chain(provider: str) -> list[str]:
    """
    Return the ordered provider chain based on the selected provider.
    The mock is always the last entry so the chain never ends empty.
    """
    if provider == "clearbit":
        return ["clearbit", "pdl", "mock"]
    if provider == "pdl":
        return ["pdl", "mock"]
    return ["mock"]


def _fetch(domain: str, company: str, chain: list[str]) -> tuple[Optional[dict], str]:
    """
    Walk the provider chain until a result is found.
    Returns (record_dict_or_None, provider_name_that_matched).
    """
    for prov in chain:
        record: Optional[dict] = None
        if prov == "clearbit":
            record = _lookup_clearbit(domain)
        elif prov == "pdl":
            record = _lookup_pdl(domain)
        elif prov == "mock":
            record = _lookup_mock(domain, company)

        if record is not None:
            return record, prov

    return None, "none"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def enrichment_lookup(company: str, domain: str, lead_id: str = "unknown") -> EnrichmentResult:
    """
    Look up firmographic data for a company by domain (primary) or name (fallback).

    Resolution order:
      cache_check → configured_provider → fallback_providers → mock → not-found zero-value

    Enhanced with Redis caching to reduce API calls and improve performance.
    Always logs the call to the governance log.
    Never raises — provider errors are caught and the chain continues.
    """
    # Check cache first
    try:
        with get_session() as db:
            cached_result = get_enrichment_cache(domain, company, db)
            if cached_result:
                logger.info(f"Using cached enrichment for domain: {domain}")
                # Convert cached dict back to EnrichmentResult
                return EnrichmentResult(
                    company=cached_result.get("company", company),
                    domain=cached_result.get("domain", domain),
                    industry=cached_result.get("industry", "Unknown"),
                    employee_count=cached_result.get("employee_count", 0),
                    hq_country=cached_result.get("hq_country", "Unknown"),
                    buying_signals=cached_result.get("buying_signals", []),
                    found=cached_result.get("found", False),
                    provider=cached_result.get("provider", "cache")
                )
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}, proceeding with API lookup")

    provider = _resolve_provider()
    chain = _resolve_chain(provider)

    record, matched_provider = _fetch(domain, company, chain)

    if record:
        result = EnrichmentResult(
            company=record["company"],
            domain=record["domain"],
            industry=record["industry"],
            employee_count=record["employee_count"],
            hq_country=record["hq_country"],
            buying_signals=record["buying_signals"],
            found=True,
            provider=matched_provider,
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
            provider="none",
        )

    # Cache the result for future use
    if result.found or matched_provider != "none":
        try:
            with get_session() as db:
                set_enrichment_cache(domain, result.to_dict(), company, db)
                logger.info(f"Cached enrichment result for domain: {domain}")
        except Exception as e:
            logger.warning(f"Failed to cache enrichment result: {e}")

    log_event(
        lead_id=lead_id,
        stage="enrichment_lookup",
        input_snapshot={"company": company, "domain": domain, "provider_chain": chain},
        output_snapshot=result.to_dict(),
    )
    return result
