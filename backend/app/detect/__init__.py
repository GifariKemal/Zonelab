"""Detector registry.

One entry per drawing type. The API and the frontend dispatch off this dict, so
adding a drawing means writing a module beside the others and adding a line
here.

The entries are not equals, and the difference is measured rather than asserted.
`supply_demand` has a validated gate behind it; `fvg` and `order_block` were
added afterwards and go through the same rig in `tools/detectors.py`. Whatever
that rig says about them is what the docs say about them.

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
