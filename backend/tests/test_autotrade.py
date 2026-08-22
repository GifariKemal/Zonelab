"""The switch, and the heartbeat that stops it from lying.

A switch reading ON over a dead daemon is the failure this project keeps a list
of: an instrument reporting green while the thing it measures has crashed. So
`enabled` and `daemon_alive` are two facts here and every test below is about
keeping them apart.

The endpoint tests assert one more thing, and it is the load-bearing one: the API
can arm a daemon and cannot place an order. That is a property of the layout -
order placement lives in `tools/` - and it is checked rather than trusted.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app import autotrade, journal
from app.main import app


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Never touch the real switch or the real journal from a test. The switch
    decides whether an account trades."""
    monkeypatch.setattr(autotrade, "STATE", tmp_path / ".autotrade.json")
    monkeypatch.setattr(journal, "DIRECTORY", tmp_path / ".journal")
    return tmp_path


# ------------------------------------------------------------------- the state


def test_a_missing_file_is_off_and_not_a_crash():
    state = autotrade.read()
    assert state["enabled"] is False
    assert state["daemon_alive"] is False
    assert state["last_seen"] is None


def test_an_unparseable_file_is_off_rather_than_an_exception(isolated):
    """These files are hand-editable. A corrupt one must fail to OFF, because the
    failure mode of this module has to be "not trading"."""
    autotrade.STATE.write_text("{not json", encoding="utf-8")
    assert autotrade.read()["enabled"] is False


def test_arming_sets_enabled_without_inventing_a_daemon():
    """The whole point. Arming is a request; it is not evidence that anything is
    running to honour it."""
    state = autotrade.arm(True)
    assert state["enabled"] is True
    assert state["daemon_alive"] is False, (
        "arming must not imply a live daemon, or the UI will show ON over nothing"
    )


def test_a_heartbeat_makes_the_daemon_alive():
    autotrade.arm(True)
    state = autotrade.beat("mt5:XAUUSD", "1h", 0.03)
    assert state["daemon_alive"] is True
    assert state["symbol"] == "mt5:XAUUSD"
    assert state["interval"] == "1h"
    assert state["risk_pct"] == 0.03


def test_an_old_heartbeat_is_not_alive(isolated):
    autotrade.arm(True)
    autotrade.beat("mt5:XAUUSD", "1h", 0.01)
    raw = json.loads(autotrade.STATE.read_text(encoding="utf-8"))
    raw["last_seen"] = int(time.time()) - autotrade.STALE_AFTER - 1
    autotrade.STATE.write_text(json.dumps(raw), encoding="utf-8")
    state = autotrade.read()
    assert state["enabled"] is True
    assert state["daemon_alive"] is False, "one second past stale must read dead"


def test_disarming_does_not_erase_the_heartbeat():
    """The two writers are the API and the daemon, and neither may erase the
    other's field - or turning the switch off would make a live daemon look dead
    and vice versa."""
    autotrade.beat("mt5:XAUUSD", "1h", 0.01)
    state = autotrade.arm(False)
    assert state["enabled"] is False
    assert state["daemon_alive"] is True


def test_a_heartbeat_does_not_flip_the_switch():
    """The mirror. A daemon reporting in must never arm itself."""
    autotrade.arm(False)
    assert autotrade.beat("mt5:XAUUSD", "1h", 0.01)["enabled"] is False


# --------------------------------------------------------------- the endpoints


@pytest.fixture
def client():
    return TestClient(app)


def test_get_reports_both_facts(client):
    body = client.get("/api/autotrade").json()
    assert body["enabled"] is False
    assert "daemon_alive" in body


def test_post_arms_and_journals_the_decision(client):
    body = client.post("/api/autotrade", json={"enabled": True}).json()
    assert body["enabled"] is True
    events = [e["event"] for e in journal.entries()]
    assert events == ["armed"], (
        "arming is the moment a human let the engine trade unattended, and a "
        "review that cannot see it is reading half the story"
    )


def test_post_disarms_and_journals_that_too(client):
    client.post("/api/autotrade", json={"enabled": True})
    client.post("/api/autotrade", json={"enabled": False})
    assert [e["event"] for e in journal.entries()] == ["armed", "disarmed"]


def test_post_without_a_boolean_is_refused(client):
    for body in ({}, {"enabled": "yes"}, {"enabled": 1}):
        assert client.post("/api/autotrade", json=body).status_code == 422


def test_arming_while_no_daemon_runs_is_allowed_and_says_so(client):
    """Not an error: the operator may arm first and start the daemon second. The
    response has to be honest about it, which is the UI's whole job."""
    body = client.post("/api/autotrade", json={"enabled": True}).json()
    assert body["enabled"] is True and body["daemon_alive"] is False


def test_the_api_cannot_place_an_order():
    """THE PROPERTY THE WHOLE DESIGN RESTS ON, asserted on the import graph rather
    than on behaviour: nothing reachable from `app/` may import the executor, and
    no module in `app/` may call `order_send`.

    A button that placed orders would hand that ability to every HTTP request
    that reaches the server. Keeping the executor in `tools/` is what prevents it,
    and this test is what stops a well-meaning refactor from moving it.
    """
    from pathlib import Path

    root = Path(autotrade.__file__).resolve().parent
    offenders = []
    for path in root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "order_send" in source or "TRADE_ACTION" in source:
            offenders.append(f"{path.name} sends orders")
        if "tools.execute" in source or "tools.flatten" in source:
            offenders.append(f"{path.name} imports the executor")
    assert offenders == [], offenders
