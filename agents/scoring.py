"""
Scoring Agent — deterministic, rule-based scoring against icp_config.json.
Score is computed purely from firmographic/buying-signal data.
Excluded fields (name, email local-part, demographics) are NEVER touched here.
LLM is used ONLY to phrase the human-readable reason string from the
precomputed factor breakdown.
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional

from tools.enrichment_lookup import EnrichmentResult
from governance.logger import log_event

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "icp_config.json")


def _load_config() -> dict:
    with open(os.path.abspath(_CONFIG_PATH), "r") as f:
        return json.load(f)

@dataclass
class ScoreResult:
    score: int                  # 0–100
    factors: dict               # factor-name -> contribution (int)
    reason: str                 # human-readable summary (LLM-phrased or fallback)
    excluded_fields_used: list  # always empty — assertion target in tests

    def to_dict(self) -> dict:
        return asdict(self)


# ── Deterministic scoring helpers ────────────────────────────────────────────

def _score_company_size(employee_count: int, cfg: dict) -> tuple[int, str]:
    size_cfg = cfg["company_size"]
    ideal_min = size_cfg["ideal_min"]
    ideal_max = size_cfg["ideal_max"]
    weight = size_cfg["weight"]
    if ideal_min <= employee_count <= ideal_max:
        contribution = weight
        label = f"size {employee_count} in ideal range [{ideal_min}-{ideal_max}]"
    elif employee_count > ideal_max:
        contribution = weight // 2
        label = f"size {employee_count} above ideal max {ideal_max}"
    elif employee_count > 0:
        contribution = weight // 4
        label = f"size {employee_count} below ideal min {ideal_min}"
    else:
        contribution = 0
        label = "company size unknown"
    return contribution, label


def _score_industry(industry: str, cfg: dict) -> tuple[int, str]:
    ind_cfg = cfg["industries"]
    weight = ind_cfg["weight"]
    if industry in ind_cfg["ideal"]:
        return weight, f"industry '{industry}' is ideal"
    if industry in ind_cfg["acceptable"]:
        return weight // 2, f"industry '{industry}' is acceptable"
    if industry in ind_cfg["disqualifying"]:
        return -weight, f"industry '{industry}' is disqualifying"
    return 0, f"industry '{industry}' not in ICP list"


def _score_role(role_title: str, cfg: dict) -> tuple[int, str]:
    role_cfg = cfg["roles"]
    weight = role_cfg["weight"]
    title_lower = role_title.lower()
    for t in role_cfg["ideal_titles"]:
        if t.lower() in title_lower:
            return weight, f"role '{role_title}' matches ideal title"
    for t in role_cfg["acceptable_titles"]:
        if t.lower() in title_lower:
            return weight // 2, f"role '{role_title}' matches acceptable title"
    for t in role_cfg["disqualifying_titles"]:
        if t.lower() in title_lower:
            return -weight, f"role '{role_title}' is disqualifying"
    return 0, f"role '{role_title}' not matched"


def _score_buying_signals(signals: list[str], cfg: dict) -> tuple[int, str]:
    bs_cfg = cfg["buying_signals"]
    weight = bs_cfg["weight"]
    positive_hits = [s for s in signals if s in bs_cfg["positive"]]
    negative_hits = [s for s in signals if s in bs_cfg["negative"]]
    contribution = len(positive_hits) * (weight // 2) - len(negative_hits) * (weight // 2)
    contribution = max(-weight, min(weight, contribution))
    label = (
        f"positive signals: {positive_hits or 'none'}; "
        f"negative signals: {negative_hits or 'none'}"
    )
    return contribution, label


def _score_email_domain(domain: str, cfg: dict) -> tuple[int, str]:
    personal = cfg["email_domain"]["personal_domains"]
    if domain.lower() in personal:
        penalty = cfg["email_domain"]["weight"]  # negative
        return penalty, f"personal email domain '{domain}'"
    return 0, f"business email domain '{domain}'"


# ── Public scoring function ───────────────────────────────────────────────────

def score(
    enrichment: EnrichmentResult,
    role_title: str,
    icp_config: Optional[dict] = None,
    lead_id: str = "unknown",
    llm_caller=None,           # injected in prod; omit for pure determinism
) -> ScoreResult:
    """
    Score a lead deterministically.
    `role_title` is the only non-enrichment field we use (it's job function, not identity).
    `llm_caller` is an optional callable(prompt)->str used only to phrase the reason.
    """
    cfg = icp_config or _load_config()

    factors: dict[str, int] = {}
    labels: list[str] = []

    # 1. Company size
    c, l = _score_company_size(enrichment.employee_count, cfg)
    factors["company_size"] = c
    labels.append(l)

    # 2. Industry
    c, l = _score_industry(enrichment.industry, cfg)
    factors["industry"] = c
    labels.append(l)

    # 3. Role / seniority
    c, l = _score_role(role_title, cfg)
    factors["role"] = c
    labels.append(l)

    # 4. Buying signals
    c, l = _score_buying_signals(enrichment.buying_signals, cfg)
    factors["buying_signals"] = c
    labels.append(l)

    # 5. Email domain penalty
    c, l = _score_email_domain(enrichment.domain, cfg)
    factors["email_domain"] = c
    labels.append(l)

    raw_score = sum(factors.values())
    final_score = max(0, min(100, raw_score))

    # Reason string — LLM phrasing if available, else deterministic fallback
    factor_text = "; ".join(labels)
    if llm_caller is not None:
        prompt = (
            f"You are a sales ops analyst. Summarise the following ICP scoring "
            f"factors into one concise human-readable sentence (max 40 words). "
            f"Do not invent any information beyond what is listed.\n\nFactors: {factor_text}\n"
            f"Score: {final_score}/100\n\nSummary:"
        )
        try:
            reason = llm_caller(prompt).strip()
        except Exception:
            reason = f"Score {final_score}/100. Factors: {factor_text}."
    else:
        reason = f"Score {final_score}/100. Factors: {factor_text}."

    result = ScoreResult(
        score=final_score,
        factors=factors,
        reason=reason,
        excluded_fields_used=[],   # always empty — identity fields never enter scoring
    )

    log_event(
        lead_id=lead_id,
        stage="scoring",
        input_snapshot={
            "company": enrichment.company,
            "industry": enrichment.industry,
            "employee_count": enrichment.employee_count,
            "buying_signals": enrichment.buying_signals,
            "role_title": role_title,
            "domain": enrichment.domain,
        },
        output_snapshot=result.to_dict(),
    )
    return result
