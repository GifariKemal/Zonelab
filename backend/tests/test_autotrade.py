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


def test_daemon_calls_the_executor_with_the_signature_it_actually_has(monkeypatch):
    """Satu cycle daemon, dengan `sizing` yang ASLI. Ini gerbang anti-drift.

    27 Agustus 2026 `execute.sizing` jadi tiga argumen dan return `float`,
    sementara `tools/autotrade.py` masih memanggilnya dengan empat dan
    membongkar tuple. Saklar terbaca MENYALA, daemon mati di cycle pertama
    dengan TypeError, dan 861 test lolos - karena tidak satu pun memanggil
    `tools.autotrade.main`. Itu bentuk kegagalan yang sama yang dikejar seluruh
    file ini: instrumen melaporkan hijau di atas proses yang crash.

    Yang di-fake cuma batas I/O - terminal dan pass keputusan. `sizing` dan
    pembentukan basket dibiarkan asli, karena persis di situ drift-nya hidup.
    """
    import sys
    from tools import autotrade as daemon

    class FakeAccount:
        login, server, trade_mode, equity = 1, "demo", 0, 1000.0

    seen: dict = {}

    monkeypatch.setattr(daemon, "_terminal", lambda: ((object(), FakeAccount()), ""))
    monkeypatch.setattr(daemon, "lot_specs", lambda symbols: ({}, []))
    monkeypatch.setattr(daemon, "cycle",
                        lambda *a, **k: seen.update(equity=a[7], symbols=a[1]))
    monkeypatch.setattr(daemon, "exits", lambda *a, **k: seen.setdefault("exits", []).append(a[1]))
    monkeypatch.setattr(daemon.autotrade, "beat", lambda *a, **k: None)
    monkeypatch.setattr(daemon.autotrade, "read", lambda: {"enabled": True})
    monkeypatch.setattr(sys, "argv",
                        ["autotrade", "--once", "--symbol", "mt5:XAUUSD,mt5:XAGUSD"])

    assert daemon.main() == 0
    assert seen["equity"] == 1000.0
    # SATU BASKET, BUKAN SATU STRING. `"mt5:XAUUSD,mt5:XAGUSD".split(":")[-1]`
    # menghasilkan 'XAUUSD,mt5:XAGUSD', yang adalah cacat contract-size 50x.
    assert seen["symbols"] == ["mt5:XAUUSD", "mt5:XAGUSD"]
    assert seen["exits"] == ["XAUUSD", "XAGUSD"]


def test_monitor_reports_each_event_once_and_names_armed_without_daemon(
    tmp_path, monkeypatch, capsys,
):
    """Watermark maju, dan saklar-menyala-tanpa-daemon terbaca sebagai perhatian.

    Dua kegagalan diam yang dijaga di sini. Yang pertama: monitor yang tidak
    memajukan watermark akan melaporkan order yang sama tiap sepuluh menit
    sampai alarm berhenti dibaca. Yang kedua adalah kegagalan khas project ini
    dalam bentuk aslinya - saklar terbaca MENYALA di atas daemon yang mati, dan
    tidak ada satu order pun yang dikirim.
    """
    import sys
    from tools import monitor as mon

    monkeypatch.setattr(mon, "WATERMARK", tmp_path / ".monitor.json")
    # Log daemon diarahkan ke file yang tidak ada, supaya test ini mengukur
    # watermark journal dan bukan isi log mesin yang kebetulan sedang jalan.
    monkeypatch.setattr(mon, "DAEMON_LOG", tmp_path / "tidak-ada.log")
    monkeypatch.setattr(mon, "_probe", lambda url, timeout=8.0: (True, "HTTP 200"))
    monkeypatch.setattr(mon, "_account", lambda: {"reachable": False, "why": "no terminal"})
    monkeypatch.setattr(mon.autotrade, "read", lambda: {
        "enabled": True, "daemon_alive": False, "heartbeat_age_seconds": 900,
        "symbol": "mt5:XAUUSD", "interval": "1h", "risk_pct": 0.03,
    })
    monkeypatch.setattr(mon.journal, "entries", lambda: [
        {"at": 100, "event": "placed", "symbol": "mt5:XAUUSD", "zone_id": "z",
         "ticket": 1, "why": ["lama"], "blockers": []},
        {"at": 10**10, "event": "placed", "symbol": "mt5:XAUUSD", "zone_id": "z",
         "ticket": 2, "why": ["baru"], "blockers": []},
    ])
    monkeypatch.setattr(sys, "argv", ["monitor"])

    assert mon.main() == 1
    first = capsys.readouterr().out
    assert "ticket 1" in first and "ticket 2" in first
    assert "saklar MENYALA tapi daemon tidak berdetak" in first

    # Cycle kedua: watermark sudah lewat event `at=100`, jadi ticket 1 hilang.
    # `at=10**10` sengaja jauh di masa depan supaya ia TETAP muncul - kalau
    # keduanya hilang, test ini lulus karena alasan yang salah.
    assert mon.main() == 1
    second = capsys.readouterr().out
    assert "ticket 1" not in second
    assert "ticket 2" in second


def test_monitor_names_a_heartbeating_daemon_that_finished_no_cycle(
    tmp_path, monkeypatch, capsys,
):
    """Berdetak tapi nol cycle. Bukan hal yang sama dengan daemon mati.

    Heartbeat distempel di AWAL cycle, sebelum saklar dibaca, supaya cycle yang
    mati di tengah pass keputusan tetap sempat bilang "saya di sini". Sisi
    lainnya: sebuah daemon yang pass-nya tidak pernah selesai akan berdetak
    selamanya sambil tidak menganalisa apa pun, dan `daemon_alive` akan terus
    membacanya hijau. Itu bentuk kegagalan yang sama yang dikejar seluruh file
    ini, cuma satu lapis lebih dalam.

    Ambangnya diikat ke waktu berlalu, jadi test ini juga menjaga arah
    sebaliknya: dua pemeriksaan berturut TIDAK boleh membunyikan alarm.
    """
    import sys
    import time as clock
    from tools import monitor as mon

    watermark = tmp_path / ".monitor.json"
    monkeypatch.setattr(mon, "WATERMARK", watermark)
    monkeypatch.setattr(mon, "DAEMON_LOG", tmp_path / "kosong.log")
    monkeypatch.setattr(mon, "_probe", lambda url, timeout=8.0: (True, "HTTP 200"))
    monkeypatch.setattr(mon, "_account", lambda: {
        "reachable": True, "login": 1, "server": "demo", "trade_mode": 0,
        "equity": 1000.0, "balance": 1000.0, "positions": [], "orders": [],
    })
    monkeypatch.setattr(mon.autotrade, "read", lambda: {
        "enabled": True, "daemon_alive": True, "heartbeat_age_seconds": 3,
        "symbol": "mt5:XAUUSD", "interval": "1h", "risk_pct": 0.03,
    })
    monkeypatch.setattr(mon.journal, "entries", list)
    monkeypatch.setattr(sys, "argv", ["monitor"])

    watermark.write_text(
        json.dumps({"seen_at": int(clock.time()) - 900, "log_offset": 0}),
        encoding="utf-8")
    assert mon.main() == 1
    assert "nol cycle selesai" in capsys.readouterr().out

    # Watermark barusan dimajukan ke sekarang, jadi pemeriksaan kedua ada di
    # dalam jendela diam dan harus tenang.
    assert mon.main() == 0
    assert "nol cycle selesai" not in capsys.readouterr().out


def test_daemon_can_enforce_doctrine_clauses_like_the_manual_tool(monkeypatch):
    """`--require` sampai ke `cycle` sebagai `Rules`, bukan `None`.

    Sampai 27 Agustus 2026 daemon memanggil `cycle(..., None, ...)`, jadi
    `Rules()` default yang dipakai dan `required` kosong. Akibatnya jalur
    tak-ditunggui adalah satu-satunya jalur order yang TIDAK BISA menegakkan
    klausa mana pun: killzone, discount_or_premium, ote, cisd_in_band, dan
    two_stage_confirmed semuanya dihitung, dilaporkan di checklist, lalu tidak
    memblokir apa-apa. `tools/execute.py` punya pilihan itu sejak awal.

    Yang dijaga di sini asimetrinya, bukan nilainya. Klausa doctrine memang
    belum terukur dan default-nya tetap kosong; yang salah adalah operator tidak
    punya cara menyalakannya di jalur yang trading sendirian.
    """
    import sys
    from tools import autotrade as daemon

    class FakeAccount:
        login, server, trade_mode, equity = 1, "demo", 0, 1000.0

    seen: dict = {}
    monkeypatch.setattr(daemon, "_terminal", lambda: ((object(), FakeAccount()), ""))
    monkeypatch.setattr(daemon, "lot_specs", lambda symbols: ({}, []))
    monkeypatch.setattr(daemon, "cycle", lambda *a, **k: seen.update(rules=a[9]))
    monkeypatch.setattr(daemon, "exits", lambda *a, **k: 0)
    monkeypatch.setattr(daemon.autotrade, "beat", lambda *a, **k: None)
    monkeypatch.setattr(daemon.autotrade, "read", lambda: {"enabled": True})
    monkeypatch.setattr(sys, "argv", [
        "autotrade", "--once", "--symbol", "mt5:XAUUSD",
        "--require", "killzone,discount_or_premium",
        "--killzones", "ny_am", "--min-families", "3", "--max-conflicts", "1",
    ])

    assert daemon.main() == 0
    rules = seen["rules"]
    assert rules is not None, "cycle masih menerima None, klausa tidak bisa mengikat"
    assert rules.required == ("killzone", "discount_or_premium")
    assert rules.killzones == ("ny_am",)
    assert rules.min_families == 3
    assert rules.max_conflicts == 1


def test_daemon_defaults_leave_every_clause_reporting_only(monkeypatch):
    """Tanpa `--require`, nol klausa mengikat. Default itu disengaja.

    `app/ict.py:Rules` menulis alasannya: menyalakan gerbang penuh akan
    menghidupkan sembilan filter yang belum terukur sekaligus dan mengubah
    populasi yang setiap angka di project ini dihitung padanya. Test ini menjaga
    arah itu supaya flag baru di atas tidak diam-diam mengubah default.
    """
    import sys
    from tools import autotrade as daemon

    class FakeAccount:
        login, server, trade_mode, equity = 1, "demo", 0, 1000.0

    seen: dict = {}
    monkeypatch.setattr(daemon, "_terminal", lambda: ((object(), FakeAccount()), ""))
    monkeypatch.setattr(daemon, "lot_specs", lambda symbols: ({}, []))
    monkeypatch.setattr(daemon, "cycle", lambda *a, **k: seen.update(rules=a[9]))
    monkeypatch.setattr(daemon, "exits", lambda *a, **k: 0)
    monkeypatch.setattr(daemon.autotrade, "beat", lambda *a, **k: None)
    monkeypatch.setattr(daemon.autotrade, "read", lambda: {"enabled": True})
    monkeypatch.setattr(sys, "argv", ["autotrade", "--once", "--symbol", "mt5:XAUUSD"])

    assert daemon.main() == 0
    assert seen["rules"].required == ()


def test_monitor_raises_its_exit_code_when_the_engine_refused_to_act(
    tmp_path, monkeypatch, capsys,
):
    """BLOCKER di log daemon HARUS menaikkan exit code, bukan cuma dicetak.

    Terjadi sungguhan 28 Agustus 2026 jam 05:03. Broker tidak mencetak bar
    21:00 UTC sama sekali - jeda harian - jadi `as_of` tertahan sementara jam
    berjalan dan `actionable.blockers` menolak seluruh pass. Monitor mencetak
    empat belas baris BLOCKER lalu menjawab `exit 0, tidak ada yang perlu
    dilihat`, karena baris itu tidak pernah masuk ke `attention`.

    Sebuah monitor yang mencetak masalah lalu mengembalikan exit code sehat
    lebih berbahaya daripada monitor yang diam: cron di sesi ini membaca exit
    code, dan operator diajari bahwa exit code-nya bisa dipercaya.

    Arah sebaliknya ikut dijaga di bawah, karena alarm yang menyala pada operasi
    normal adalah alarm yang akan diabaikan justru saat ia benar.
    """
    import sys
    from tools import monitor as mon

    log = tmp_path / "daemon.log"
    monkeypatch.setattr(mon, "WATERMARK", tmp_path / ".monitor.json")
    monkeypatch.setattr(mon, "DAEMON_LOG", log)
    monkeypatch.setattr(mon, "_probe", lambda url, timeout=8.0: (True, "HTTP 200"))
    monkeypatch.setattr(mon, "_account", lambda: {
        "reachable": True, "login": 1, "server": "demo", "trade_mode": 0,
        "equity": 1000.0, "balance": 1000.0, "positions": [], "orders": [],
    })
    monkeypatch.setattr(mon.autotrade, "read", lambda: {
        "enabled": True, "daemon_alive": True, "heartbeat_age_seconds": 3,
        "symbol": "mt5:XAUUSD", "interval": "1h", "risk_pct": 0.03,
    })
    monkeypatch.setattr(mon.journal, "entries", list)
    monkeypatch.setattr(sys, "argv", ["monitor"])

    log.write_text(
        "mt5:XAUUSD 1h  price 4600.87  12 kandidat  BLOCKED: 1\n"
        "  BLOCKER: feed is 3603s behind on a 3600s interval\n"
        "tidak ada kandidat\n"
        "  BLOCKER: feed is 3624s behind on a 3600s interval\n"
        "tidak ada kandidat\n",
        encoding="utf-8")
    assert mon.main() == 1
    out = capsys.readouterr().out
    assert "3603s behind" in out
    # DUA CYCLE, BUKAN NOL. Cycle yang berakhir di blocker tetap cycle, dan
    # menghitungnya nol membuat jeda harian broker terbaca sebagai daemon mati.
    assert "analisa: 2 cycle" in out
    # SATU ALARM, BUKAN DUA. Satu penyebab yang bertahan mencetak satu baris per
    # cycle dengan angka yang bergerak; dedup-nya pada bentuk kalimat.
    assert out.count("- BLOCKER") == 1, out

    log.write_text("  ringkas: 12 kandidat, 0 dikirim, 0 ditolak\n", encoding="utf-8")
    assert mon.main() == 0
    assert "BLOCKER" not in capsys.readouterr().out
