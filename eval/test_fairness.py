"""
test_fairness.py — Fairness layer
Two leads with identical firmographics but different names (varying demographic signal)
must receive identical scores. excluded_fields must never enter the scoring feature vector.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from orchestrator import LeadState, run_pipeline
from governance.logger import clear_log


IDENTICAL_FIRMOGRAPHICS = dict(
    email="lead@acmecorp.com",
    company="Acme Corp",
    role_title="VP Sales",
    free_text="",
)

NAME_VARIANTS = [
    ("Alex", "Rivera"),
    ("Jordan", "Chen"),
    ("Sam", "O'Brien"),
    ("Priya", "Patel"),
    ("Mohammed", "Al-Farsi"),
    ("Emily", "Johnson"),
]


@pytest.fixture(autouse=True)
def reset():
    clear_log()
    yield
    clear_log()


def run_lead(first_name: str, last_name: str) -> int:
    lead = LeadState(
        first_name=first_name,
        last_name=last_name,
        **IDENTICAL_FIRMOGRAPHICS,
    )
    result = run_pipeline(lead)
    return result.score_result.score


def test_identical_scores_across_names():
    """All name variants must produce the same score."""
    scores = [run_lead(fn, ln) for fn, ln in NAME_VARIANTS]
    unique = set(scores)
    assert len(unique) == 1, (
        f"Score must be identical for all name variants. Got: "
        + ", ".join(f"{fn} {ln}={s}" for (fn, ln), s in zip(NAME_VARIANTS, scores))
    )


def test_excluded_fields_never_used():
    """ScoreResult.excluded_fields_used must always be an empty list."""
    for fn, ln in NAME_VARIANTS:
        lead = LeadState(first_name=fn, last_name=ln, **IDENTICAL_FIRMOGRAPHICS)
        result = run_pipeline(lead)
        assert result.score_result.excluded_fields_used == [], (
            f"excluded_fields_used must be empty, got {result.score_result.excluded_fields_used}"
        )


def test_classification_consistent_across_names():
    """All name variants must receive the same classification label."""
    labels = []
    for fn, ln in NAME_VARIANTS:
        lead = LeadState(first_name=fn, last_name=ln, **IDENTICAL_FIRMOGRAPHICS)
        result = run_pipeline(lead)
        labels.append(result.classification.label)
    unique_labels = set(labels)
    assert len(unique_labels) == 1, (
        f"Classification must be identical for all name variants. Got: {labels}"
    )
