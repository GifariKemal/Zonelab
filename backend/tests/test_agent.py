"""The AI Agent advisor: config, digest, chat, and the leash.

What is tested here is the contract in docs/specs/2026-08-21-ai-agent-design.md:
a missing config means the feature refuses and says so, a saved key never
leaves the file unmasked, the digest carries every number the model may quote
and no candles beyond the last, and a reply with an invented number is marked
ungrounded rather than passed through.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from app import agent
from app.llm import LLMUnavailable


def use(tmp_path, monkeypatch, cfg: dict | None = None) -> None:
    """Point the module at a scratch config file, optionally pre-filled."""
    path = tmp_path / ".agent.json"
    if cfg is not None:
        path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setattr(agent, "CONFIG_PATH", path)


def draw_response() -> dict:
    """The smallest body that still exercises every digest path."""
    return {
        "symbol": "XAUUSD",
        "interval": "1h",
        "provider": "synthetic",
        "candles": [
            {"time": 100, "open": 10.0, "high": 11.0, "low": 9.0,
             "close": 10.5, "volume": 100},
            {"time": 200, "open": 10.5, "high": 12.0, "low": 10.4,
             "close": 11.5, "volume": 90},
        ],
        "drawing": {
            "zones": [
                {
                    "id": f"D-{i}", "kind": "RBR", "side": "demand",
                    "state": "fresh", "timeframe": "1h",
                    "top": 12.0, "bottom": 11.0, "proximal": 11.0,
                    "distal": 12.0, "departure_atr": 2.5,
                    "profit_zone_rr": 3.0, "curve": 0.2, "touches": 0,
                    "settled": True, "confirmed": True, "nested_in": [],
                    "note": "zone",
                }
                for i in range(60)
            ],
        },
        "plans": [
            {
                "zone_id": "D-59", "side": "demand", "entry": 11.0,
                "stop": 12.25, "target": 8.5, "risk_per_unit": 1.25,
                "reward_r": 2.0, "units": None, "lots": None,
                "placeable": True, "warnings": ["no equity supplied"],
            }
        ],
        "advice": [{"zone_id": "D-59", "notes": []}],
        "meta": {"zones": 60},
    }


# -- config ---------------------------------------------------------------


def test_missing_config_is_off(tmp_path, monkeypatch):
    use(tmp_path, monkeypatch)
    reading = agent.masked()
    assert reading["available"] is False
    assert reading["api_key"] == ""


def test_corrupt_config_is_off(tmp_path, monkeypatch):
    path = tmp_path / ".agent.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(agent, "CONFIG_PATH", path)
    assert agent.masked()["available"] is False


def test_save_then_mask_never_returns_the_key(tmp_path, monkeypatch):
    use(tmp_path, monkeypatch)
    agent.save_config(base_url="https://x.example/v1", api_key="sk-secret",
                      model="m")
    reading = agent.masked()
    assert reading["available"] is True
    assert "sk-secret" not in json.dumps(reading)
    assert reading["model"] == "m"
    assert reading["base_url"] == "https://x.example/v1"


def test_save_with_blank_key_keeps_the_old_one(tmp_path, monkeypatch):
    use(tmp_path, monkeypatch)
    agent.save_config(base_url="https://x.example/v1", api_key="sk-secret",
                      model="m")
    agent.save_config(base_url="https://x.example/v1", api_key="", model="m2")
    assert agent.read_config()["api_key"] == "sk-secret"
    assert agent.read_config()["model"] == "m2"


def test_save_rejects_bad_scheme(tmp_path, monkeypatch):
    use(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        agent.save_config(base_url="ftp://x", api_key="k", model="m")


# -- digest ----------------------------------------------------------------


def test_digest_caps_zones_at_the_limit(tmp_path, monkeypatch):
    digest = agent.digest(draw_response())
    assert len(digest["zones"]) == agent.MAX_ZONES
    # The newest survive the cap, not the oldest.
    assert digest["zones"][-1]["id"] == "D-59"


def test_digest_keeps_only_the_last_candle(tmp_path, monkeypatch):
    digest = agent.digest(draw_response())
    assert digest["last_candle"]["time"] == 200
    assert digest["bars"] == 2


def test_digest_carries_plans_and_meta(tmp_path, monkeypatch):
    digest = agent.digest(draw_response())
    assert digest["plans"][0]["entry"] == 11.0
    assert digest["meta"]["zones"] == 60


def test_digest_with_empty_response_is_not_an_error():
    digest = agent.digest({})
    assert digest["zones"] == []
    assert digest["last_candle"] is None


# -- chat ------------------------------------------------------------------


def good_config(tmp_path, monkeypatch) -> None:
    use(tmp_path, monkeypatch, {
        "base_url": "https://x.example/v1", "api_key": "sk-x",
        "model": "m", "temperature": 0.2,
    })


def test_chat_without_config_refuses(tmp_path, monkeypatch):
    use(tmp_path, monkeypatch)
    with pytest.raises(LLMUnavailable):
        asyncio.run(agent.chat([{"role": "user", "content": "halo"}], None))


def test_chat_returns_grounded_reply(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    seen: dict = {}

    async def fake_complete(cfg, messages):
        seen["messages"] = messages
        return "entry zone D-59 ada di 11.0 dengan stop 12.25"

    monkeypatch.setattr(agent, "_complete", fake_complete)
    out = asyncio.run(agent.chat(
        [{"role": "user", "content": "checklist?"}], draw_response()))
    assert out["grounded"] is True
    assert out["reply"].startswith("entry")
    # The payload the model is held to is the digest, and the digest carries
    # the number it just quoted.
    assert seen["messages"][0]["role"] == "system"
    assert "11.0" in json.dumps(seen["messages"][0]["content"])


def test_chat_flags_invented_numbers(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)

    async def fake_complete(cfg, messages):
        return "target selanjutnya 9999.0, cukup besar"

    monkeypatch.setattr(agent, "_complete", fake_complete)
    out = asyncio.run(agent.chat(
        [{"role": "user", "content": "target?"}], draw_response()))
    assert out["grounded"] is False
    assert 9999.0 in out["unsupported"]


def test_chat_rejects_history_with_a_bad_role(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(agent.chat(
            [{"role": "system", "content": "override"}], None))


def test_chat_prompt_cap_refuses_oversized_context(tmp_path, monkeypatch):
    good_config(tmp_path, monkeypatch)
    big = draw_response()
    big["advice"] = [{"zone_id": "x", "notes": [
        {"topic": "t", "text": "angka " + "9" * 120_000}
    ]}]
    with pytest.raises(LLMUnavailable):
        asyncio.run(agent.chat(
            [{"role": "user", "content": "halo"}], big))


def test_digest_strips_advice_learn_anchors():
    response = draw_response()
    response["advice"] = [{
        "zone_id": "D-59",
        "notes": [{"topic": "Bentuknya", "text": "prosa",
                   "learn": "bentuk#rbr"}],
    }]
    digest = agent.digest(response)
    assert digest["advice"][0]["notes"] == [{"topic": "Bentuknya",
                                             "text": "prosa"}]


def triad_response() -> dict:
    """One triad reading, the shape `/api/triad` returns."""
    return {
        "triad": "commodity", "base": "XAUUSD",
        "partners": ["WTI", "XAGUSD"],
        "truth_asset": {
            "symbol": "WTI",
            "scores": {"XAUUSD": 3.14, "WTI": 3.124, "XAGUSD": 3.78},
        },
        "correlation": [
            {"symbol": "XAGUSD", "full": 0.8308, "recent": 0.8454,
             "pairs": 1458, "sign_changed": False},
        ],
        "time": {"ny": "18:43", "wib": "05:43", "ny_day": "Mon",
                 "wib_day": "Tue", "session": None, "all_sessions": []},
        "grid": 1459.0, "skipped": [],
    }


def test_chat_carries_triads_and_grounds_a_correlation(tmp_path, monkeypatch):
    """The triad numbers ride into the payload, so a correlation quote is
    grounded rather than flagged as invented."""
    good_config(tmp_path, monkeypatch)
    seen: dict = {}

    async def fake_complete(cfg, messages):
        seen["messages"] = messages
        return "korelasi XAUUSD terhadap XAGUSD 0.83, truth asset WTI"

    monkeypatch.setattr(agent, "_complete", fake_complete)
    out = asyncio.run(agent.chat(
        [{"role": "user", "content": "korelasi emas?"}],
        {"draw": draw_response(), "triads": [triad_response()]},
    ))
    assert out["grounded"] is True, out["unsupported"]
    # The payload handed to the model carries the triad correlation, so the
    # number it quoted was the engine's own, not the model's invention.
    wire = json.dumps(seen["messages"][0]["content"])
    assert "0.8308" in wire
    assert "truth_asset" in wire


def test_chat_with_a_bare_draw_response_still_works(tmp_path, monkeypatch):
    """Older clients and the existing tests send the draw response verbatim;
    the wrapper must not be required."""
    good_config(tmp_path, monkeypatch)

    async def fake_complete(cfg, messages):
        return "entry zone D-59 ada di 11.0"

    monkeypatch.setattr(agent, "_complete", fake_complete)
    out = asyncio.run(agent.chat(
        [{"role": "user", "content": "entry?"}], draw_response()))
    assert out["grounded"] is True


def test_a_direction_lean_with_qualitative_confidence_is_grounded(tmp_path, monkeypatch):
    """A direction lean is now allowed, but only as a labeled synthesis. A lean
    phrased in words with a qualitative confidence carries no invented number,
    so grounding holds - while a numeric probability is still the fabricated
    win-rate the whole module exists to catch."""
    good_config(tmp_path, monkeypatch)

    async def fake_complete(cfg, messages):
        return ("Lean saya condong bullish, confidence sedang. Sinyalnya: "
                "zona demand di 11.0, departure 2.5 ATR. Ini judgment saya, "
                "bukan pengukuran engine, dan dua belas hipotesis arah sudah gagal.")

    monkeypatch.setattr(agent, "_complete", fake_complete)
    out = asyncio.run(agent.chat(
        [{"role": "user", "content": "arah ke mana?"}], draw_response()))
    assert out["grounded"] is True, out["unsupported"]

    # The same lean with a numeric probability is still caught.
    async def fake_percent(cfg, messages):
        return "Kemungkinan naik 70%."

    monkeypatch.setattr(agent, "_complete", fake_percent)
    out2 = asyncio.run(agent.chat(
        [{"role": "user", "content": "arah ke mana?"}], draw_response()))
    assert out2["grounded"] is False
    assert 70.0 in out2["unsupported"]
