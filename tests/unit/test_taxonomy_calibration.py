"""Taxonomy and calibration tests."""

from __future__ import annotations

from agentevalops.diagnostics.taxonomy import TAXONOMY, humanize, is_model_behavior
from agentevalops.grading.calibration import calibrate
from agentevalops.schemas.diagnosis import FailureCategory


def test_taxonomy_covers_all_categories() -> None:
    roots = {c.value.split(".")[0] for c in FailureCategory}
    assert set(TAXONOMY.keys()) == roots


def test_taxonomy_humanize() -> None:
    assert "Model Behavior" in humanize(FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION)


def test_is_model_behavior() -> None:
    assert is_model_behavior(FailureCategory.MODEL_BEHAVIOR_UNSAFE_ACTION)
    assert not is_model_behavior(FailureCategory.ENVIRONMENT_NETWORK_FAILURE)


def test_calibrate_perfect_agreement() -> None:
    r = calibrate([True, False, True], [True, False, True])
    assert r.agreement_rate == 1.0
    assert r.cohens_kappa == 1.0
    assert r.precision == 1.0
    assert r.recall == 1.0


def test_calibrate_imperfect() -> None:
    r = calibrate([True, True, False, False], [True, False, True, False])
    assert r.agreement_rate == 0.5
    assert r.confusion == {"tp": 1, "fp": 1, "fn": 1, "tn": 1}


def test_calibrate_empty() -> None:
    r = calibrate([], [])
    assert r.agreement_rate is None
    assert r.n == 0
