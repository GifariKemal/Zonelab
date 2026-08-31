"""The consolidation-quality verdict: original vs staircase, from two base fields."""

from app.models import Zone


def _zone(base_drift: float, base_overlap: float) -> Zone:
    # `model_construct` sets the two fields the verdict reads without validating
    # the fields the verdict never touches.
    return Zone.model_construct(base_drift=base_drift, base_overlap=base_overlap)


def test_a_staircase_base_is_fake():
    assert _zone(0.9, 0.1).consolidation_quality == "staircase"


def test_a_base_that_revisits_its_prices_is_original():
    assert _zone(0.1, 0.8).consolidation_quality == "original"


def test_a_low_drift_low_overlap_base_is_borderline():
    assert _zone(0.1, 0.2).consolidation_quality == "borderline"
