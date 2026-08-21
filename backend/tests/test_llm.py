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


class FakeProc:
    """A `claude` that never ran. Stands in for the subprocess so the CLI
    backend's own logic is what gets tested - not whether a binary happens to
    be installed on the machine running the suite, and not the network."""

    def __init__(self, out: bytes, code: int = 0, err: bytes = b"", hang: bool = False):
        self._out, self.returncode, self._err, self._hang = out, code, err, hang
        self.killed = False

    async def communicate(self, stdin: bytes | None = None):
        if self._hang:
            await asyncio.sleep(3600)
        return self._out, self._err

    def kill(self):
        self.killed = True

    async def wait(self):
        return self.returncode


def spawn(monkeypatch, proc: FakeProc, *, on_path: str | None = "C:/fake/claude.CMD"):
    """Select the CLI backend and hand it a canned subprocess."""
    seen: dict = {}

    async def fake_exec(*argv, **kwargs):
        seen["argv"] = argv
        seen["cwd"] = kwargs.get("cwd")
        return proc

    monkeypatch.setattr(settings, "llm_backend", "cli")
    monkeypatch.setattr(llm.shutil, "which", lambda _: on_path)
    monkeypatch.setattr(llm.asyncio, "create_subprocess_exec", fake_exec)
    return seen


def said_cli(text: str, **extra) -> bytes:
    import json
    return json.dumps({"result": text, "is_error": False, **extra}).encode()


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


def test_the_cli_backend_is_chosen_by_configuration_not_by_a_missing_key(monkeypatch):
    """A key present and the backend set to cli must still go to the CLI. If the
    choice were "http unless the key is empty", nobody could test the CLI path
    on a machine that has a key, and the fallback would fire by accident."""
    seen = spawn(monkeypatch, FakeProc(said_cli("Kotaknya wajar.")))
    monkeypatch.setattr(settings, "llm_key", "test-key")

    reply = asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))

    assert reply.usable
    assert seen["argv"][1] == "-p"
    assert "--output-format" in seen["argv"] and "json" in seen["argv"]


def test_the_cli_gets_no_tools_at_all_when_there_is_no_image(monkeypatch):
    """A rephrasing job has no business reading files, and the reply is
    untrusted text either way. Bash must never appear at any setting."""
    seen = spawn(monkeypatch, FakeProc(said_cli("Zona berumur 23 bar.")))
    asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))

    argv = list(seen["argv"])
    for flag in ("--tools", "--allowedTools"):
        assert argv[argv.index(flag) + 1] == ""
    assert not any("Bash" in a for a in argv)


def test_an_image_reaches_the_cli_as_a_file_it_is_allowed_to_read(monkeypatch):
    """The CLI cannot be handed bytes on the command line, so vision only works
    if the PNG is written down and the model is told where and allowed to look.
    A silently dropped image looks exactly like a model with nothing to say."""
    from pathlib import Path

    seen = spawn(monkeypatch, FakeProc(said_cli("Border bawah tertutup lilin.")))
    asyncio.run(
        llm.ask(llm.CHART_AUDITOR, "audit", PAYLOAD, image_png=b"\x89PNG-fake"))

    argv = list(seen["argv"])
    assert argv[argv.index("--tools") + 1] == "Read"
    assert argv[argv.index("--allowedTools") + 1] == "Read"
    # The system prompt travels as a FILE, never as argv: the resolved binary is
    # a .CMD and cmd.exe reads metacharacters out of argv before Python's
    # quoting gets a say.
    assert argv[argv.index("--system-prompt-file") + 1] == "system.txt"
    assert not any(llm.CHART_AUDITOR[:40] in a for a in argv)
    # And the directory it was written in is gone afterwards.
    assert not Path(seen["cwd"]).exists()


def test_an_invented_price_from_the_cli_is_rejected_exactly_as_over_http(monkeypatch):
    """The guarantee cannot be per-transport. A second way in that skipped the
    grounding check would be a hole in the only thing this module promises."""
    spawn(monkeypatch, FakeProc(said_cli("Target berikutnya 4402.10, peluang 78%.")))
    reply = asyncio.run(llm.ask(llm.CHART_AUDITOR, "audit", PAYLOAD))
    assert not reply.usable
    assert 4402.10 in reply.verdict.unsupported


def test_a_missing_cli_binary_refuses_out_loud(monkeypatch):
    """No key and no binary is the same failure every provider here has, and it
    gets the same treatment: a sentence naming both ways to fix it, not an
    empty string that reads as a model with no findings."""
    spawn(monkeypatch, FakeProc(said_cli("never reached")), on_path=None)
    monkeypatch.setattr(settings, "llm_key", "")
    assert not llm.available()
    with pytest.raises(llm.LLMUnavailable, match="not on PATH") as exc:
        asyncio.run(llm.ask(llm.CHART_AUDITOR, "audit", PAYLOAD))
    assert "ZONELAB_LLM_KEY" in str(exc.value)


def test_a_hung_cli_is_killed_and_the_timeout_is_named(monkeypatch):
    """An agent that boots and then stalls holds the harness open forever, and
    a harness that never returns is indistinguishable from a slow one."""
    proc = FakeProc(b"", hang=True)
    spawn(monkeypatch, proc)
    monkeypatch.setattr(settings, "llm_cli_timeout_seconds", 0.05)
    with pytest.raises(llm.LLMUnavailable, match="did not answer within"):
        asyncio.run(llm.ask(llm.CHART_AUDITOR, "audit", PAYLOAD))
    assert proc.killed


def test_a_nonzero_exit_and_an_unreadable_body_both_say_so(monkeypatch):
    spawn(monkeypatch, FakeProc(b"", code=1, err=b"not logged in"))
    with pytest.raises(llm.LLMUnavailable, match="exited 1: not logged in"):
        asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))

    spawn(monkeypatch, FakeProc(b"this is not json"))
    with pytest.raises(llm.LLMUnavailable, match="unreadable body"):
        asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))

    spawn(monkeypatch, FakeProc(said_cli("credit balance too low", is_error=True)))
    with pytest.raises(llm.LLMUnavailable, match="reported an error"):
        asyncio.run(llm.ask(llm.EXPLAINER, "jelaskan", PAYLOAD))


def test_an_oversized_prompt_is_refused_before_anything_is_spawned(monkeypatch):
    """The cap is on this side. Handing an unbounded payload to a subprocess and
    hoping is how a harness that loops over every timeframe hangs."""
    spawn(monkeypatch, FakeProc(said_cli("never reached")))
    monkeypatch.setattr(settings, "llm_max_prompt_chars", 100)
    with pytest.raises(llm.LLMUnavailable, match="over the 100 cap"):
        asyncio.run(llm.ask(llm.EXPLAINER, "x" * 101, PAYLOAD))


def test_the_module_entry_point_prints_the_reply_and_its_verdict(tmp_path, monkeypatch):
    """What the node harness actually calls. It has to be able to tell an
    ungrounded reply from a refusal, so one is exit 0 with grounded false and
    the other is exit 3 with nothing on stdout."""
    import json

    image = tmp_path / "chart.png"
    image.write_bytes(b"\x89PNG-fake")
    shapes = tmp_path / "shapes.json"
    shapes.write_text(json.dumps(PAYLOAD), encoding="utf-8")
    argv = ["audit", "--image", str(image), "--payload", str(shapes)]

    spawn(monkeypatch, FakeProc(said_cli("Target 4402.10.")))
    assert llm._main(argv) == 0

    spawn(monkeypatch, FakeProc(b"", code=1, err=b"not logged in"))
    assert llm._main(argv) == 3


def test_the_prompts_forbid_a_directional_call_in_writing():
    """A prompt is a request, not a guarantee - the grounding check is the
    guarantee. But the instruction must still be there, because a model that is
    never told will volunteer a forecast unprompted."""
    for prompt in (llm.CHART_AUDITOR, llm.EXPLAINER):
        low = prompt.lower()
        assert "rise or fall" in low or "which way price will go" in low
