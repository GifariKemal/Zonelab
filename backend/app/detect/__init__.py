"""Detector registry.

One entry per drawing type. The API and the frontend dispatch off this dict, so
adding a drawing means writing a module beside the others and adding a line
here.

The three entries are not equals, and the difference is measured rather than
asserted. `supply_demand` has a validated gate behind it; `fvg` and
`order_block` were added afterwards and go through the same rig in
`tools/detectors.py`. Whatever that rig says about them is what the docs say
about them.
"""

from __future__ import annotations

from . import imbalance, supply_demand

DETECTORS = {
    "supply_demand": supply_demand.detect,
    "fvg": imbalance.detect_fvg,
    "order_block": imbalance.detect_order_block,
}

# Which parameter block on the request each detector reads. Kept beside the
# registry so a new detector cannot be wired into one and forgotten in the
# other.
PARAMS_FOR = {
    "supply_demand": "supply_demand",
    "fvg": "imbalance",
    "order_block": "imbalance",
}

__all__ = ["DETECTORS", "PARAMS_FOR", "imbalance", "supply_demand"]
