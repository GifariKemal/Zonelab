"""The model client, tested offline, because its failure modes are the point.

No network here. What matters is not that an HTTP call works - it is that a
missing key SAYS so, that an unreadable answer SAYS so, and above all that a
reply carrying an invented number comes back marked unusable rather than
reaching the user looking like a measurement.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app import llm
from app.config import settings


PAYLOAD = {"entry": 4377.86, "stop": 4377.44, "age_bars": 23}


def serve(monkeypatch, body: dict | str, status: int = 200):
    """Point the client at a canned response without touching the network."""
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(body, str):
            return httpx.Response(status, text=body)
        return httpx.Response(status, json=body)

    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(llm.httpx, "AsyncClient", factory)
    monkeypatch.setattr(settings, "llm_key", "test-key")


def said(text: str) -> dict:
    return {"choices": [{"message": {"content": text}}]}


def test_no_key_refuses_and_explains_rather_than_returning_nothing(monkeypatch):
    """Same rule as every data provider here: a failure is said out loud. A
    silent empty answer is indistinguishable from a model with no opinion."""
    monkeypatch.setattr(settings, "llm_key", "")
    assert not llm.available()
    with pytest.raises(llm.LLMUnavailable, match="ZONELAB_LLM_KEY"):
        asyncio.run(llm.ask(llm.EXPLAINER, "hello", PAYLOAD))


def test_a_reply_repeating_the_engine_is_usable(monkeypatch):
    serve(monkeypatch, said("Entry di 4377.86 dan zona berumur 23 bar."))
    reply = asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))
    assert reply.usable


def test_an_invented_price_comes_back_unusable(monkeypatch):
    """The failure this whole module exists to prevent: a specific, plausible,
    fabricated number arriving in prose that reads like a measurement."""
    serve(monkeypatch, said("Target berikutnya 4402.10, peluang 78%."))
    reply = asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))
    assert not reply.usable
    assert 4402.10 in reply.verdict.unsupported


def test_an_http_error_names_the_status_instead_of_going_quiet(monkeypatch):
    serve(monkeypatch, "rate limited", status=429)
    with pytest.raises(llm.LLMUnavailable, match="429"):
        asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))


def test_an_unreadable_body_is_reported_not_crashed_through(monkeypatch):
    serve(monkeypatch, {"unexpected": "shape"})
    with pytest.raises(llm.LLMUnavailable, match="unreadable"):
        asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))


def test_an_image_is_sent_as_a_data_uri_part(monkeypatch):
    """Vision is the one job here a model can do that measurement cannot, so
    the image has to actually reach it rather than being dropped silently."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=said("Kotaknya terlihat wajar."))

    real = httpx.AsyncClient
    monkeypatch.setattr(llm.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k,
                                                    "transport": httpx.MockTransport(handler)}))
    monkeypatch.setattr(settings, "llm_key", "test-key")

    asyncio.run(
        llm.ask(llm.CHART_AUDITOR, "audit", PAYLOAD, image_png=b"\x89PNG-fake"))
    parts = seen["messages"][1]["content"]
    assert isinstance(parts, list)
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_the_prompts_forbid_a_directional_call_in_writing():
    """A prompt is a request, not a guarantee - the grounding check is the
    guarantee. But the instruction must still be there, because a model that is
    never told will volunteer a forecast unprompted."""
    for prompt in (llm.CHART_AUDITOR, llm.EXPLAINER):
        low = prompt.lower()
        assert "rise or fall" in low or "which way price will go" in low
