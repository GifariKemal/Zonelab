"""Weekly COT (Commitments of Traders) from CFTC reports.

Commodity codes (gold, silver) use the disaggregated report (f_disagg.txt)
which breaks out Managed Money. FX codes (EUR, GBP) use the legacy report
(deafut.txt) which has Commercials/Non-Commercials but covers all contracts.
Non-Commercial is used as the managed_money proxy for FX.

Fetches once per ISO week, caches to .cot_cache.json. Returns None on any
failure - never blocks the draw response.
"""

from __future__ import annotations

import csv
import io
import json
import statistics
from datetime import date
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

_DISAGG_URL = "https://www.cftc.gov/dea/newcot/f_disagg.txt"
_LEGACY_URL = "https://www.cftc.gov/dea/newcot/deafut.txt"
_CACHE = Path(__file__).resolve().parent.parent / ".cot_cache.json"

# MT5 symbol -> (CFTC code, source)
_SYMBOLS: dict[str, tuple[str, str]] = {
    "XAUUSD": ("088691", "disagg"),
    "XAGUSD": ("084691", "disagg"),
    "EURUSD": ("099741", "legacy"),
    "GBPUSD": ("096742", "legacy"),
}

# Column indices: f_disagg.txt (191 cols, no headers)
_D = {
    "date": 2, "code": 3, "oi": 7,
    "prod_l": 8, "prod_s": 9, "mm_l": 13, "mm_s": 14,
    "chg_oi": 55, "chg_prod_l": 56, "chg_prod_s": 57,
    "chg_mm_l": 61, "chg_mm_s": 62,
}
# Column indices: deafut.txt (129 cols, no headers)
_L = {
    "date": 2, "code": 3, "oi": 7,
    "comm_l": 11, "comm_s": 12, "nc_l": 8, "nc_s": 9,
    "chg_oi": 37, "chg_comm_l": 41, "chg_comm_s": 42,
    "chg_nc_l": 38, "chg_nc_s": 39,
}

_MIN_HISTORY = 20  # weeks before computing std dev


def _iso_week(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(data: dict) -> None:
    try:
        _CACHE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass  # ponytail: cache write failure is not fatal


def _int(row: list[str], idx: int) -> int | None:
    if idx >= len(row):
        return None
    try:
        return int(row[idx].strip().replace(",", ""))
    except ValueError:
        return None


def _fetch_csv(url: str) -> list[list[str]]:
    req = Request(url, headers={"User-Agent": "Zonelab/1.0"})
    with urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return list(csv.reader(io.StringIO(text)))


def _parse_disagg(rows: list[list[str]], codes: set[str]) -> dict[str, dict]:
    """Parse disaggregated report for commodity codes."""
    out: dict[str, dict] = {}
    c = _D
    for row in rows:
        if len(row) <= c["chg_mm_s"]:
            continue
        code = row[c["code"]].strip()
        if code not in codes:
            continue
        pl, ps = _int(row, c["prod_l"]), _int(row, c["prod_s"])
        ml, ms = _int(row, c["mm_l"]), _int(row, c["mm_s"])
        oi = _int(row, c["oi"])
        if any(v is None for v in (pl, ps, ml, ms, oi)):
            continue
        assert pl is not None and ps is not None
        assert ml is not None and ms is not None and oi is not None
        cpl, cps = _int(row, c["chg_prod_l"]), _int(row, c["chg_prod_s"])
        cml, cms = _int(row, c["chg_mm_l"]), _int(row, c["chg_mm_s"])
        out[code] = {
            "report_date": row[c["date"]].strip(),
            "commercial_net": pl - ps,
            "commercial_change": (cpl - cps) if cpl is not None and cps is not None else None,
            "managed_money_net": ml - ms,
            "managed_money_change": (cml - cms) if cml is not None and cms is not None else None,
            "open_interest": oi,
            "oi_change": _int(row, c["chg_oi"]),
        }
    return out


def _parse_legacy(rows: list[list[str]], codes: set[str]) -> dict[str, dict]:
    """Parse legacy report for FX codes. Non-Commercial proxies Managed Money."""
    out: dict[str, dict] = {}
    c = _L
    for row in rows:
        if len(row) <= c["chg_nc_s"]:
            continue
        code = row[c["code"]].strip()
        if code not in codes:
            continue
        cl, cs = _int(row, c["comm_l"]), _int(row, c["comm_s"])
        nl, ns = _int(row, c["nc_l"]), _int(row, c["nc_s"])
        oi = _int(row, c["oi"])
        if any(v is None for v in (cl, cs, nl, ns, oi)):
            continue
        assert cl is not None and cs is not None
        assert nl is not None and ns is not None and oi is not None
        ccl, ccs = _int(row, c["chg_comm_l"]), _int(row, c["chg_comm_s"])
        cnl, cns = _int(row, c["chg_nc_l"]), _int(row, c["chg_nc_s"])
        out[code] = {
            "report_date": row[c["date"]].strip(),
            "commercial_net": cl - cs,
            "commercial_change": (ccl - ccs) if ccl is not None and ccs is not None else None,
            "managed_money_net": nl - ns,
            "managed_money_change": (cnl - cns) if cnl is not None and cns is not None else None,
            "open_interest": oi,
            "oi_change": _int(row, c["chg_oi"]),
        }
    return out


def _signal(commercial_net: int, mm_values: list[int]) -> tuple[str, bool]:
    """Commercial direction + managed money extreme flag.

    Returns ("buy"|"sell"|"neutral", extreme_positioning). Strong signals
    need price discount context from outside this module.
    """
    # ponytail: strong_buy/strong_sell requires discount alignment from
    # checklist; add when the checklist passes its discount reading here
    if commercial_net > 0:
        sig = "buy"
    elif commercial_net < 0:
        sig = "sell"
    else:
        sig = "neutral"

    extreme = False
    if len(mm_values) >= _MIN_HISTORY:
        try:
            mu = statistics.mean(mm_values)
            sd = statistics.stdev(mm_values)
            if sd > 0:
                extreme = abs((mm_values[-1] - mu) / sd) > 2.0
        except statistics.StatisticsError:
            pass

    return sig, extreme


def _from_cache(entry: dict) -> dict | None:
    """Reconstruct a summary from a cache entry, or None."""
    data = entry.get("data")
    if data is None:
        return None
    mm = [h["v"] for h in entry.get("mm_history", []) if isinstance(h, dict)]
    sig, ext = _signal(data["commercial_net"], mm)
    return {**data, "signal": sig, "extreme_positioning": ext}


def cot_summary(symbol: str) -> dict | None:
    """Weekly COT summary for a symbol. Returns None if unavailable."""
    spec = _SYMBOLS.get(symbol.upper())
    if spec is None:
        return None
    code, source = spec

    cache = _load_cache()
    week = _iso_week(date.today())
    entry = cache.get(code, {})

    # Fresh cache -> skip fetch
    if entry.get("week") == week and "data" in entry:
        return _from_cache(entry)

    # Fetch the right report
    try:
        url = _DISAGG_URL if source == "disagg" else _LEGACY_URL
        csv_rows = _fetch_csv(url)
        if source == "disagg":
            parsed = _parse_disagg(csv_rows, {code})
        else:
            parsed = _parse_legacy(csv_rows, {code})
    except (URLError, OSError, UnicodeDecodeError):
        # Stale cache is better than nothing
        return _from_cache(entry) if "data" in entry else None

    data = parsed.get(code)
    if data is None:
        return None

    # Append to managed money history (one entry per report date)
    history: list[dict] = entry.get("mm_history", [])
    last_d = history[-1]["d"] if history else None
    if data["report_date"] != last_d:
        history.append({"d": data["report_date"], "v": data["managed_money_net"]})
        history = history[-52:]  # keep one year

    cache[code] = {"week": week, "data": data, "mm_history": history}
    _save_cache(cache)

    mm = [h["v"] for h in history if isinstance(h, dict)]
    sig, ext = _signal(data["commercial_net"], mm)
    return {**data, "signal": sig, "extreme_positioning": ext}
