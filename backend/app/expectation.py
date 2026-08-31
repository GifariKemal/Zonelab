"""The expectation overlay's data source: a precomputed table, looked up per cell.

The table lives in `docs/expectation.json`, written once by `tools.expectation`.
This module loads it lazily and answers one question: for a symbol, what is the
measured distribution of resolved R, and which `dfr_side` bucket exists. No
provider call and no lookahead: the table is a static measurement, so a chart
render cannot be slower or wronger than the file it reads.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_TABLE_PATH = Path(__file__).resolve().parents[2] / "docs" / "expectation.json"


@lru_cache(maxsize=1)
def _load() -> dict:
    try:
        return json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def cell(symbol: str) -> dict | None:
    """The measured cell for a symbol, or None when it was never measured."""
    return _load().get("cells", {}).get(symbol.upper())


def verdict() -> str:
    return _load().get("verdict", "")


def buckets(cell: dict) -> dict[str, dict]:
    return cell.get("buckets", {}) if cell else {}


def base_rate(cell: dict) -> dict | None:
    return cell.get("base_rate") if cell else None
