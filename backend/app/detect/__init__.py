"""Detector registry.

One entry per drawing type. The API and the frontend dispatch off this dict, so
adding a drawing means writing a module beside the others and adding a line
here.

The entries are not equals, and the difference is measured rather than asserted.
The ranking BELOW IS NOT THE ORDER THEY WERE WRITTEN IN, and it reversed on
6 September 2026. Twelve cells, walk-forward 8 folds, each detector as production
runs it:

    ifvg           +0.3450   PF 1.652   wf 8/8
    breaker        +0.2631   PF 1.566   wf 8/8
    order_block    +0.1633   PF 1.330   wf 8/8
    supply_demand  +0.0532   PF 1.121   wf 6/8

This paragraph said `supply_demand` had a validated gate behind it while `fvg`
and `order_block` did not, until that day. It is now the WEAKEST of the four and
the only one that fails the pre-registered walk-forward rule. Worse: without its
departure gate it measures exp_r -0.0514 with t = -5.61 against zero, so the
positive number belongs to the gate rather than to the leg-base-leg pattern. The
gate separates hard at every threshold - Welch +7.36 against a 2.9137 Bonferroni
- and not one threshold reaches 8/8. Twenty-one detection-rule arms were swept
and none beat production: docs/QA-SD-GATE.md.

`ifvg` and `breaker` are the two that carry an explicit directional claim in
their own doctrine, and that claim was measured and came out SIGNIFICANTLY
NEGATIVE against a trailing-move control (H8, docs/CALIBRATION.md). They are
registered as drawings, not as signals; see `inversion.py`.
"""

from __future__ import annotations

from . import imbalance, inversion, supply_demand

DETECTORS = {
    "supply_demand": supply_demand.detect,
    "fvg": imbalance.detect_fvg,
    "order_block": imbalance.detect_order_block,
    "ifvg": inversion.detect_ifvg,
    "breaker": inversion.detect_breaker,
}

# Which parameter block each detector reads lives in `app/layers.py`, on the
# layer entry that also carries the label, the kind and the evidence. It was
# duplicated here as a `PARAMS_FOR` dict and the two said the same thing, which
# is one source too many: a detector pointed at the wrong block still returns a
# 200 and still draws, just from the wrong knobs, so the drift would be silent.
#
# The inversion pair shares the imbalance block on purpose - an IFVG is an FVG
# plus one more event, and a second gap threshold for it would let the two
# populations drift apart. That reasoning now lives beside the entries it
# governs.

__all__ = ["DETECTORS", "imbalance", "inversion", "supply_demand"]
