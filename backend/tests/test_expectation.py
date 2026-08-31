"""The expectation overlay: bucket arithmetic and the live dfr_side match."""

from app.models import ZoneSide
from app.overlays import _dfr_side_key
from tools.expectation import quantile_set, table


def test_dfr_side_key_reads_lower_half_for_demand_and_upper_for_supply():
    assert _dfr_side_key(ZoneSide.DEMAND, 0.3) == "met"
    assert _dfr_side_key(ZoneSide.DEMAND, 0.7) == "failed"
    assert _dfr_side_key(ZoneSide.SUPPLY, 0.7) == "met"
    assert _dfr_side_key(ZoneSide.SUPPLY, 0.3) == "failed"
    assert _dfr_side_key(ZoneSide.DEMAND, None) == "unknown"


def test_quantile_set_is_monotone_and_counts():
    q = quantile_set(list(range(100)))
    assert q["n"] == 100
    assert q["q5"] <= q["q25"] <= q["q50"] <= q["q75"] <= q["q95"]


def test_table_omits_a_thin_bucket_and_keeps_the_base_rate():
    # One trade is below the floor, so the bucket is omitted rather than drawn
    # from noise, while the base rate always exists.
    rows = [{"symbol": "X", "r": 1.0, "dfr_side": True}]
    cells = table(rows)
    assert cells["X"]["base_rate"]["n"] == 1
    assert cells["X"]["buckets"] == {}


def test_table_buckets_a_full_population_by_dfr_side():
    rows = []
    for i in range(120):
        flag = True if i % 3 == 0 else (False if i % 3 == 1 else None)
        r = 1.0 if flag is True else (-1.0 if flag is False else 0.0)
        rows.append({"symbol": "X", "r": r, "dfr_side": flag})
    cell = table(rows)["X"]
    assert cell["base_rate"]["n"] == 120
    assert cell["buckets"]["met"]["q50"] > 0
    assert cell["buckets"]["failed"]["q50"] < 0
