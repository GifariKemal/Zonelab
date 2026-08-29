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

import types

import json
import sys
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
    monkeypatch.setattr(daemon, "sweep", lambda *a, **k: 0)
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
    monkeypatch.setattr(daemon, "sweep", lambda *a, **k: 0)
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
    monkeypatch.setattr(daemon, "sweep", lambda *a, **k: 0)
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


# ------------------------------------------------- the loop, and what ends it
#
# Everything below drives `tools.autotrade.main` itself, which is the hole the
# 27 August 2026 incident fell through: a signature drift killed the daemon one
# second after arming and 861 tests passed, because not one of them called
# `main`. A gate on the loop has to run the loop.


@pytest.fixture
def daemon_fakes(monkeypatch):
    """Batas I/O daemon di-fake; keputusan, sizing, dan LOOP-nya dibiarkan asli.

    `_terminal`, `lot_specs`, `cycle`, `exits`, dan `beat` adalah tepi tempat
    daemon menyentuh terminal dan disk. `main`, `sizing`, pembentukan basket,
    penghitungan kegagalan, dan gerbang PID sengaja TIDAK di-fake: persis di
    situ cacat yang dikejar file ini hidup.
    """
    from tools import autotrade as daemon

    class FakeAccount:
        login, server, trade_mode, equity = 1, "demo", 0, 1000.0

    calls: list = []
    monkeypatch.setattr(daemon, "_terminal", lambda: ((object(), FakeAccount()), ""))
    monkeypatch.setattr(daemon, "lot_specs", lambda symbols: ({}, []))
    monkeypatch.setattr(daemon, "exits", lambda *a, **k: 0)
    monkeypatch.setattr(daemon, "sweep", lambda *a, **k: 0)
    monkeypatch.setattr(daemon, "cycle", lambda *a, **k: calls.append(a))
    # Heartbeat dimatikan supaya ia tidak menimpa `daemon_pid` yang ditulis
    # test gerbang PID di bawah. Yang diukur di sini loop-nya, bukan detaknya.
    monkeypatch.setattr(daemon.autotrade, "beat", lambda *a, **k: None)
    return daemon, calls


def _argv(monkeypatch, *extra: str) -> None:
    import sys
    monkeypatch.setattr(sys, "argv", [
        "autotrade", "--symbol", "mt5:XAUUSD", "--cycle", "0", *extra])


def test_a_raising_cycle_does_not_end_the_loop_and_escalates_after_five(
    daemon_fakes, monkeypatch, capsys,
):
    """Satu raise TIDAK mengakhiri loop, tapi lima berturut mengakhiri proses.

    27 Agustus 2026 tidak ada `try` sama sekali di sekitar pass keputusan, jadi
    satu `TypeError` dari drift signature mengembalikan `main` sementara saklar
    terus terbaca MENYALA selama `STALE_AFTER = 60` detik. Arah pertama yang
    dijaga di sini: cycle kedua harus tetap terjadi.

    Arah kedua sama pentingnya dan lebih halus. Heartbeat distempel di AWAL
    cycle, sebelum pass keputusan, jadi loop yang menelan semua kegagalan dan
    jalan terus akan berdetak selamanya sambil nol order dianalisa - dan
    `daemon_alive` akan terus membacanya hijau. Menyerah mengubahnya jadi
    kegagalan yang sudah punya alarm.
    """
    daemon, calls = daemon_fakes
    autotrade.arm(True)
    attempts: list[int] = []

    def boom(*a, **k):
        attempts.append(1)
        raise RuntimeError("provider timeout")

    monkeypatch.setattr(daemon, "cycle", boom)
    _argv(monkeypatch)

    assert daemon.main() == daemon.EXIT_TOO_MANY_FAILURES
    assert len(attempts) == daemon.MAX_CONSECUTIVE_FAILURES, (
        "loop berhenti di cycle pertama yang melempar, atau tidak pernah "
        "berhenti sama sekali"
    )
    out = capsys.readouterr().out
    assert "CYCLE GAGAL 1/5" in out and "CYCLE GAGAL 5/5" in out
    # Pesan aslinya, bukan cuma tipe. "RuntimeError" tanpa "provider timeout"
    # adalah baris log yang tidak bisa dipakai mendiagnosa apa pun.
    assert "provider timeout" in out
    # "GAGAL" adalah kata yang dipindai `tools/monitor.py` di log daemon, jadi
    # kegagalan ini menaikkan exit code monitor tanpa gerbang baru di sana.
    assert "MENYERAH setelah 5" in out
    assert calls == []


def test_a_recovered_cycle_resets_the_count_and_ctrl_c_exits_zero(
    daemon_fakes, monkeypatch, capsys,
):
    """Empat gagal, satu sukses, empat gagal lagi: sembilan kegagalan, nol exit.

    Hitungannya BERTURUT, bukan kumulatif. Daemon yang menghitung total akan
    mati setelah lima jeda harian broker yang tersebar sepanjang seminggu,
    padahal tiap satu pulih sendiri. Kalau reset-nya hilang, escalation menyala
    di cycle keenam dan `main` menjawab 3.

    Ctrl-C ikut diukur di sini karena ia jalur keluar yang didokumentasikan:
    `KeyboardInterrupt` turunan `BaseException`, jadi ia lewat dari
    `except Exception` per-cycle dan harus keluar bersih dengan 0, bukan
    traceback.
    """
    daemon, _ = daemon_fakes
    autotrade.arm(True)
    seen: list[int] = []

    def scripted(*a, **k):
        seen.append(len(seen) + 1)
        turn = len(seen)
        if turn == 10:
            raise KeyboardInterrupt
        if turn != 5:
            raise RuntimeError(f"gagal ke-{turn}")

    monkeypatch.setattr(daemon, "cycle", scripted)
    _argv(monkeypatch)

    # Ditangkap DI SINI juga, supaya `KeyboardInterrupt` yang lolos dari `main`
    # jadi satu test gagal dan bukan seluruh sesi pytest dibatalkan. Sebuah
    # gerbang yang membunuh runner-nya sendiri menjawab exit 2, dan exit code
    # itu tidak bisa dibedakan dari operator yang menekan Ctrl-C sendiri.
    try:
        code = daemon.main()
    except KeyboardInterrupt:
        pytest.fail("KeyboardInterrupt lolos dari main: Ctrl-C keluar lewat "
                    "traceback, bukan lewat jalur berhenti yang bersih")
    assert code == 0
    assert len(seen) == 10, (
        "escalation menyala terlalu cepat: hitungan kegagalan tidak dinolkan "
        "oleh cycle yang berhasil"
    )
    out = capsys.readouterr().out
    assert "pulih setelah 4 cycle gagal berturut" in out
    assert "berhenti atas Ctrl-C" in out
    assert "MENYERAH" not in out


def test_one_shot_smoke_test_does_not_answer_zero_after_a_raise(
    daemon_fakes, monkeypatch,
):
    """`--once` yang cycle-nya melempar harus menjawab bukan-nol.

    `--once` ada untuk smoke test, dan smoke test yang menjawab 0 di atas cycle
    yang crash adalah instrumen-hijau-di-atas-proses-mati dalam bentuknya yang
    paling murni.
    """
    daemon, _ = daemon_fakes
    autotrade.arm(True)

    def boom(*a, **k):
        raise ValueError("history.load meledak")

    monkeypatch.setattr(daemon, "cycle", boom)
    _argv(monkeypatch, "--once")

    assert daemon.main() == 1


# -------------------------------------------------------- one daemon, not two


def _hold_the_switch(pid: int, age: int = 0) -> None:
    """Tulis saklar seolah daemon `pid` memegangnya dan berdetak `age` detik lalu."""
    autotrade.arm(True)
    raw = json.loads(autotrade.STATE.read_text(encoding="utf-8"))
    raw["daemon_pid"] = pid
    raw["last_seen"] = int(time.time()) - age
    autotrade.STATE.write_text(json.dumps(raw), encoding="utf-8")


@pytest.fixture
def live_python():
    """PID python asli yang BUKAN PID test ini, dan yang benar-benar hidup."""
    import subprocess
    import sys as _sys
    child = subprocess.Popen([_sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        yield child.pid
    finally:
        child.kill()
        child.wait()


WINDOWS_ONLY = pytest.mark.skipif(
    sys.platform != "win32",
    reason="pemeriksaan proses lewat tasklist; daemon ini Windows-only karena "
           "provider terminalnya begitu")


@WINDOWS_ONLY
def test_a_second_daemon_refuses_to_start_beside_a_live_one(
    daemon_fakes, live_python, monkeypatch, capsys,
):
    """Dua daemon pada satu saklar ditolak, dan alasannya disebut dengan PID.

    Terjadi sungguhan 29 Agustus 2026: PID 12948 dan 19912 keduanya hidup pada
    `mt5:XAUUSD --risk-pct 0.03`. Saklar punya satu field `daemon_pid`, jadi ia
    menamai 19912 dan tidak ada apa pun yang tahu tentang 12948, sementara
    `tools/monitor.py` melaporkan "daemon hidup" dan terbaca sehat. Keduanya dry
    run, dan itu satu-satunya alasan ia tidak berbiaya: dua pengirim akan
    balapan di idempotency check journal dan cap `--max-orders` yang sama, dan
    masing-masing lolos pemeriksaan yang sebentar lagi dibatalkan yang lain.
    """
    daemon, calls = daemon_fakes
    _hold_the_switch(live_python)
    _argv(monkeypatch, "--once")

    assert daemon.main() == daemon.EXIT_ALREADY_RUNNING
    assert calls == [], "daemon kedua tetap menjalankan pass keputusan"
    out = capsys.readouterr().out
    assert "MENOLAK START" in out and str(live_python) in out


@WINDOWS_ONLY
def test_a_stale_pid_from_a_crashed_daemon_does_not_block_a_fresh_start(
    daemon_fakes, live_python, monkeypatch,
):
    """PID basi TIDAK boleh memblokir. Ini arah yang membuat gerbang bisa dipakai.

    Daemon yang crash meninggalkan nomornya di saklar dan tidak ada apa pun yang
    membersihkannya - itu justru kondisi saat operator paling perlu start ulang.
    PID di sini sengaja dipilih yang BENAR-BENAR hidup, jadi yang diukur murni
    umur heartbeat: kalau gerbangnya cuma melihat nomor, test ini gagal.
    """
    daemon, calls = daemon_fakes
    _hold_the_switch(live_python, age=autotrade.STALE_AFTER + 1)
    _argv(monkeypatch, "--once")

    assert daemon.main() == 0
    assert len(calls) == 1


@WINDOWS_ONLY
def test_a_reused_pid_that_is_no_longer_python_does_not_block(
    daemon_fakes, live_python, monkeypatch,
):
    """PID hidup, heartbeat segar, tapi prosesnya bukan python: tidak memblokir.

    PID didaur ulang. Nomor yang ditinggalkan daemon yang crash diberikan OS ke
    apa pun yang start berikutnya, dan kalau ia mendarat di notepad.exe maka
    gerbang yang cuma membaca nomor akan menolak start yang sah selamanya.

    `tasklist` di-fake DI SINI dan tidak di test sebelahnya, supaya kedua
    setengah gerbang terukur terpisah: yang satu nomor plus umur heartbeat, yang
    ini nama image.
    """
    daemon, calls = daemon_fakes
    _hold_the_switch(live_python)

    class Fake:
        stdout = f'"notepad.exe","{live_python}","Console","1","9.000 K"'

    monkeypatch.setattr(autotrade.subprocess, "run", lambda *a, **k: Fake())
    _argv(monkeypatch, "--once")

    assert daemon.main() == 0
    assert len(calls) == 1


@WINDOWS_ONLY
def test_the_operator_can_override_and_is_told_that_it_was_overridden(
    daemon_fakes, live_python, monkeypatch, capsys,
):
    """`--allow-second-daemon` lewat, dan mencatat bahwa ia lewat.

    Gerbang tanpa jalan keluar akan dicabut orang pertama yang terhalang olehnya
    pada jam tiga pagi. Yang tidak boleh adalah lewat dengan diam.
    """
    daemon, calls = daemon_fakes
    _hold_the_switch(live_python)
    _argv(monkeypatch, "--once", "--allow-second-daemon")

    assert daemon.main() == 0
    assert len(calls) == 1
    assert "PERINGATAN: start dipaksakan" in capsys.readouterr().out


def test_the_gate_never_reads_our_own_heartbeat_as_another_daemon(
    daemon_fakes, monkeypatch,
):
    """Daemon yang restart cepat tidak boleh terhalang oleh jejaknya sendiri.

    Sebuah PID yang sama dengan PID kita bukan konflik menurut definisi, dan
    tanpa klausa itu satu-satunya proses yang paling pasti terhalang adalah
    daemon yang baru saja menulis heartbeat itu.
    """
    import os
    daemon, calls = daemon_fakes
    _hold_the_switch(os.getpid())
    _argv(monkeypatch, "--once")

    assert autotrade.owner() is None
    assert daemon.main() == 0
    assert len(calls) == 1


# ---------------------------------------------------------------- sizing risk


def test_risk_above_the_documented_number_is_warned_about_and_not_clamped(
    daemon_fakes, monkeypatch, capsys,
):
    """3% mencetak 40,97%, dan tetap ditradingkan pada 3%.

    `docs/QA-QUANT.md` bagian 8 menghitung risk 3% pada 40,97% peluang
    kehilangan separuh akun dalam 500 trade kalau edge-nya nol, dan bagian 6
    menunjukkan kolom edge-nol itulah yang berlaku. Default yang di-ship 1%;
    kedua daemon yang hidup 29 Agustus 2026 berjalan pada 3% dan tidak ada satu
    baris pun di log yang menyebutkannya.

    Clamp diam-diam ditolak dan itu bagian yang dijaga di paruh kedua test ini:
    operator yang mengetik 3% lalu diperdagangkan pada 1% akan punya journal
    yang menjawab pertanyaan berbeda dari yang ia kira ia tanyakan.
    """
    daemon, calls = daemon_fakes
    autotrade.arm(True)
    _argv(monkeypatch, "--once", "--risk-pct", "0.03")

    assert daemon.main() == 0
    out = capsys.readouterr().out
    assert "RISK DI ATAS ANGKA YANG DIDOKUMENTASIKAN" in out
    assert "40,97%" in out, out
    assert "1,00%" in out
    assert "QA-QUANT" in out
    # `cycle(mt5, symbols, intervals, bars, risk_pct, ...)`: argumen kelima.
    assert calls[0][4] == 0.03, "risk operator diam-diam di-clamp"


def test_risk_at_or_below_the_documented_number_says_nothing(
    daemon_fakes, monkeypatch, capsys,
):
    """Default 1% diam. Alarm yang menyala pada operasi normal adalah alarm yang
    akan diabaikan justru saat ia benar."""
    daemon, _ = daemon_fakes
    autotrade.arm(True)
    _argv(monkeypatch, "--once")

    assert daemon.main() == 0
    assert "RISK DI ATAS" not in capsys.readouterr().out


def test_the_quoted_ruin_figure_is_a_floor_never_an_exaggeration():
    """Risk di antara dua baris tabel mengutip baris DI BAWAHNYA.

    Angka yang dicetak harus bisa ditunjuk di `docs/QA-QUANT.md`, jadi ia tidak
    diinterpolasi. Membulatkan ke baris di atas akan membuat log menyebut angka
    yang lebih menakutkan daripada yang terukur, dan sekali itu ketahuan seluruh
    peringatannya berhenti dibaca.
    """
    from tools import autotrade as daemon

    assert daemon.risk_warning(0.01) == []
    assert daemon.risk_warning(0.005) == []
    between = "\n".join(daemon.risk_warning(0.025))
    assert "16,20%" in between and "2,0%" in between
    assert "DI ATAS baris itu" in between
    assert "40,97%" in "\n".join(daemon.risk_warning(0.03))
    assert "93,83%" in "\n".join(daemon.risk_warning(0.25))


# ---------------------------------------------------------- sapuan pending


class _SweepMT5:
    """Cukup permukaan untuk `sweep`, dan ia mencatat apa yang dikirim."""

    def __init__(self, orders=()):
        self._orders = list(orders)
        self.sent: list[dict] = []
        self.TRADE_ACTION_REMOVE = 2
        self.TRADE_RETCODE_DONE = 10009
        self.TRADE_RETCODE_PLACED = 10008

    def orders_get(self, **kw):
        return self._orders

    def order_send(self, request):
        self.sent.append(request)
        return types.SimpleNamespace(retcode=10009, comment="ok", order=1)

    def last_error(self):
        return (-1, "fake")


class _Pending:
    def __init__(self, ticket, magic, age_seconds, now):
        self.ticket, self.magic = ticket, magic
        self.time_setup = now - age_seconds


def test_a_dry_run_sweep_never_cancels_anything(capsys, monkeypatch):
    """Aturan yang sama dengan seluruh jalur order: tanpa `--send`, nol yang
    menyentuh broker. Sapuan yang membatalkan order di dry run akan jadi satu
    satunya tempat di repo ini yang menulis ke broker tanpa flag itu."""
    from tools import autotrade as daemon
    from tools.flatten import STALE_PENDING_SECONDS

    now = 1_800_000_000
    monkeypatch.setattr("tools.autotrade.time.time", lambda: now)
    mt5 = _SweepMT5([_Pending(11, 618, STALE_PENDING_SECONDS + 60, now)])

    cancelled = daemon.sweep(mt5, send=False, rule={})

    assert cancelled == 0
    assert mt5.sent == [], "dry run tidak boleh mengirim apa pun"
    assert "DRY RUN" in capsys.readouterr().out


def test_the_sweep_cancels_only_our_own_stale_pendings(monkeypatch, tmp_path):
    """Tiga order, satu yang boleh disentuh.

    Milik orang lain dikenali dari `magic`, bukan dari journal: journal-nya
    lokal, gitignored, dan tidak pernah direkonsiliasi dengan broker, jadi satu
    file yang terhapus akan membuat sapuan ini menyentuh order tangan.
    """
    from tools import autotrade as daemon
    from tools.broker import MAGIC, RULE
    from tools.flatten import STALE_PENDING_SECONDS

    now = 1_800_000_000
    monkeypatch.setattr("tools.autotrade.time.time", lambda: now)
    monkeypatch.setattr("app.journal.DIRECTORY", tmp_path)
    mt5 = _SweepMT5([
        _Pending(11, MAGIC, STALE_PENDING_SECONDS + 60, now),   # milik kita, basi
        _Pending(22, MAGIC, 3600, now),                          # milik kita, segar
        _Pending(33, 0, STALE_PENDING_SECONDS * 10, now),        # bukan milik kita
    ])

    cancelled = daemon.sweep(mt5, send=True, rule=dict(RULE))

    assert cancelled == 1
    assert [r["order"] for r in mt5.sent] == [11]
    assert all(r["action"] == mt5.TRADE_ACTION_REMOVE for r in mt5.sent)
