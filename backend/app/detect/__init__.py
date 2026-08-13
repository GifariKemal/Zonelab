"""Detector registry.

One entry per drawing type. Adding FVG, order blocks or liquidity sweeps later
means writing a module beside `supply_demand` and adding a line here - the API
and the frontend dispatch off this dict and need no change.
"""

from __future__ import annotations

from . import supply_demand

DETECTORS = {
    "supply_demand": supply_demand.detect,
}

__all__ = ["DETECTORS", "supply_demand"]
