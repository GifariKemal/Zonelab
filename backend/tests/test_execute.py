"""The executor's refusals, tested without a broker anywhere near them.

Everything here is about what must NOT happen. The happy path is one line of
`order_send` and the terminal proves it; these are the four ways a well-meaning
run destroys an account or an audit trail.
"""

from __future__ import annotations

import sys
import types
from datetime import datetime

import pytest

from app.models import Anatomy, Zone, ZoneKind, ZoneSide, ZoneState
from tools import broker, execute


class FakeCheck:
    def __init__(self, retcode=0, comment="Done"):
        self.retcode, self.comment = retcode, comment


class FakeSend:
    """Default `retcode` adalah 10009, karena ITU yang dibalas terminal saat
    sukses. Fixture ini dulu default 0 dan itu menyandi cacatnya: `order_check`
    sukses pada 0, `order_send` TIDAK."""

    def __init__(self, retcode=10009, order=999, comment="ok"):
        self.retcode, self.order, self.comment = retcode, order, comment


class FakeMT5:
    """Only the surface `place` touches, and it records the request it was given."""

    TRADE_ACTION_PENDING = 5
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TIME_GTC = 0
    ORDER_FILLING_RETURN = 2
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008

    #: Digit harga per simbol, karena satu angka tidak bisa mewakili keduanya.
    #: XAUUSD tiga desimal, pasangan FX mayor lima. Fixture lama hanya punya
    #: XAUUSD, jadi ia menyandi cacat yang test-nya justru ada untuk menangkap.
    DIGITS = {"XAUUSD": 3, "EURUSD": 5, "GBPUSD": 5, "USDJPY": 3}

    def __init__(self, check=None, send=None, digits=None, known=True):
        self.sent: list[dict] = []
        self._check = check or FakeCheck()
        self._send = send or FakeSend()
        self._digits = digits
        self._known = known

    def symbol_info(self, symbol):
        if not self._known:
            return None
        digits = self._digits if self._digits is not None else self.DIGITS.get(symbol)
        if digits is None:
            return None
        return types.SimpleNamespace(digits=digits, trade_contract_size=100.0)

    def order_check(self, request):
        self.last_checked = request
        return self._check

    def order_send(self, request):
        self.sent.append(request)
        return self._send

    def last_error(self):
        return (-1, "fake")


def zone(kind=ZoneKind.DBD, side=ZoneSide.SUPPLY, zid="DBD-1787227200") -> Zone:
    return Zone(
        id=zid, kind=kind, side=side, state=ZoneState.FRESH,
        top=4623.28, bottom=4604.31, proximal=4604.31, distal=4623.28,
        time_from=1787227200, time_to=1787299200,
        formation_score=0.0, departure_atr=6.273,
        anatomy=Anatomy(leg_in_from=0, leg_in_to=1, base_run_from=1, base_from=1,
                        base_to=2, leg_out_from=3, leg_out_to=4),
    )


class FakePlan:
    side = ZoneSide.SUPPLY
    entry, stop, target = 4604.2213, 4628.0428, 4489.5667


def test_the_order_comment_is_truncated_to_what_the_terminal_accepts():
    """MetaTrader answers `Invalid "comment" argument` for an over-long comment
    and does not mention length. Measured on the connected terminal: 31 accepted,
    32 refused."""
    mt5 = FakeMT5()
    long_id = "DBD-" + "9" * 60
    ticket, why = execute.place(mt5, zone(zid=long_id), FakePlan(), "XAUUSD", 0.01)
    assert ticket == 999, why
    assert len(mt5.sent[0]["comment"]) <= broker.COMMENT_MAX


def test_prices_are_rounded_to_the_symbol_s_digits():
    """4604.2213 is not a price this symbol can hold. Sending it unrounded is how
    a pending order lands one tick away from the line the plan named."""
    mt5 = FakeMT5()
    execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    request = mt5.sent[0]
    assert request["price"] == 4604.221
    assert request["sl"] == 4628.043
    assert request["tp"] == 4489.567


class FivePlan:
    """Rencana pada pasangan lima desimal, angkanya khas EURUSD."""

    side = ZoneSide.SUPPLY
    entry, stop, target = 1.0823412, 1.0851187, 1.0768934


def test_a_five_digit_pair_keeps_all_five_digits():
    """Fixture yang hanya menjalankan XAUUSD menyandi cacatnya sendiri.

    `place` membulatkan ke 3 desimal mati sampai 29 Agustus 2026, yang kebetulan
    benar untuk emas. Pada EURUSD 1,08234 jadi 1,082: geseran 3,4 pip pada entry
    DAN stop sekaligus, jadi risk yang sudah lolos gerbang berubah setelah
    disetujui. Empat pasangan lima desimal ada di tabel biaya dan terjangkau
    lewat `--symbol`, jadi ini jalur yang bisa dijalankan hari ini.
    """
    mt5 = FakeMT5()
    ticket, why = execute.place(mt5, zone(), FivePlan(), "EURUSD", 0.01)
    assert ticket == 999, why
    request = mt5.sent[0]
    assert request["price"] == 1.08234
    assert request["sl"] == 1.08512
    assert request["tp"] == 1.07689


def test_an_unreadable_symbol_refuses_instead_of_guessing_the_digits():
    """Tanpa `digits` tidak ada cara membulatkan dengan benar.

    Memakai default akan mengirim harga yang salah presisi ke terminal, yaitu
    cara lain untuk mendarat satu tick dari garis yang direncanakan. Menolak
    adalah satu satunya jawaban yang tidak mengarang.
    """
    mt5 = FakeMT5(known=False)
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "digit" in why.lower(), why
    assert not mt5.sent, "tidak boleh ada order yang terkirim"


def test_every_order_carries_the_ownership_magic():
    """`magic` 0 berarti tidak ditandai, dan sampai sekarang ia tidak pernah
    diset. Satu satunya catatan bahwa sebuah order milik Zonelab ada di
    `.journal/`, yang gitignored dan tidak pernah direkonsiliasi dengan broker.
    """
    mt5 = FakeMT5()
    execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert mt5.sent[0]["magic"] == broker.MAGIC
    assert broker.MAGIC != 0


def test_a_supply_zone_becomes_a_sell_limit():
    mt5 = FakeMT5()
    execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert mt5.sent[0]["type"] == FakeMT5.ORDER_TYPE_SELL_LIMIT


def test_a_refused_order_check_never_reaches_order_send():
    """The check exists to stop the send. If a non-zero retcode still sent, the
    check would be decoration."""
    mt5 = FakeMT5(check=FakeCheck(retcode=10015, comment="Invalid price"))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "10015" in why and "Invalid price" in why
    assert mt5.sent == [], "order_send ran after order_check refused"


def test_a_failed_send_reports_the_retcode_rather_than_a_ticket():
    mt5 = FakeMT5(send=FakeSend(retcode=10018, order=0, comment="Market closed"))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "10018" in why


# ------------------------------------------------------------------ the account


def fake_module(trade_mode: int, trade_allowed: bool = True):
    """A stand-in `MetaTrader5` module, injected into sys.modules so the lazy
    import inside `_terminal` finds it."""
    account = types.SimpleNamespace(
        login=1, server="Fake", trade_mode=trade_mode, trade_allowed=trade_allowed,
        equity=1000.0,
    )
    module = types.ModuleType("MetaTrader5")
    module.initialize = lambda: True
    module.account_info = lambda: account
    module.last_error = lambda: (0, "")
    return module


@pytest.mark.parametrize("mode,name", [(1, "contest"), (2, "REAL")])
def test_only_a_demo_account_is_accepted(monkeypatch, mode, name):
    """The one refusal with no flag to override it. A contest account is not
    real money either and is still refused, because the measured population is
    the demo the numbers were checked on and 'nearly demo' is not a category."""
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(mode))
    terminal, why = execute._terminal()
    assert terminal is None
    assert f"trade_mode={mode}" in why and "DEMO" in why


def test_a_demo_account_with_trading_disabled_is_refused(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(0, trade_allowed=False))
    terminal, why = execute._terminal()
    assert terminal is None
    assert "disabled" in why


def test_a_demo_account_is_accepted(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5", fake_module(0))
    terminal, why = execute._terminal()
    assert terminal is not None and why == ""


# ------------------------------------------------------------------- the grounds


def test_every_ground_carries_a_number():
    """`why` is the record a review reads. A line with no figure in it is an
    opinion, and this file's whole claim is that the engine does not have those."""
    plan = types.SimpleNamespace(age_bars=23, age_held_rate=0.772, target=4489.5667,
                                 reward_r=4.81)
    for line in execute.grounds(zone(), plan):
        assert any(ch.isdigit() for ch in line), line


def test_the_rule_names_the_gate_and_the_exit():
    """A journal line without these two cannot explain why an answer changed
    between one month and the next."""
    assert "departure_atr >=" in execute.RULE["gate"]
    assert "rollover" in execute.RULE["exit_rule"]
    assert execute.RULE["horizon_bars"] > 0


# ------------------------------------------------------------------- the sizing


def test_a_plan_with_no_lot_size_means_nobody_checked_the_risk():
    """The hole this section closes. `plan.build` returns `placeable=True` when it
    was never given equity, because a plan that was not asked to size cannot
    refuse on size. The first version of `tools/execute.py` read that True as
    permission and sent a hardcoded 0.01 lot, so the risk gate its own docstring
    promised was decorative.

    Asserted on the plan rather than on the executor because this is the property
    that made the executor wrong: True and None arriving together.
    """
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600)
    assert plan is not None
    assert plan.placeable is True, "unchanged, and that is exactly the trap"
    assert plan.lots is None, (
        "no equity was supplied, so no lot was computed - and `lots is None` is "
        "the signal the executor must read"
    )


def test_a_plan_given_equity_refuses_when_the_minimum_lot_is_too_big():
    """A 1000-unit account at 1% cannot take a 23-point stop at 0.01 lot on a
    100-ounce contract: the minimum risks 23.7 against a 10.0 budget."""
    from app.models import LotSpec
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600, equity=1000.0, risk_pct=0.01,
                 lot=LotSpec())
    assert plan is not None
    assert plan.placeable is False
    assert plan.lots is None
    assert any("anggaran risiko" in w for w in plan.warnings)


def test_a_bigger_account_sizes_the_same_trade():
    """The mirror, so the refusal above is a limit and not a permanent no."""
    from app.models import LotSpec
    from app.plan import build

    plan = build(zone(), 19.0, 1787299200, 3600, equity=25_000.0, risk_pct=0.01,
                 lot=LotSpec())
    assert plan is not None
    assert plan.placeable is True
    assert plan.lots is not None and plan.lots >= 0.01
    assert plan.realised_risk_pct is not None and plan.realised_risk_pct <= 0.01, (
        "realised risk may sit under the budget but never over it"
    )


# ------------------------------------------- contract size, satu per simbol


def _symbol_module(sizes: dict[str, float]):
    """Terminal palsu yang cuma tahu contract size per simbol."""
    module = fake_module(0)
    module.symbol_info = lambda name: (
        types.SimpleNamespace(trade_contract_size=sizes[name], volume_min=0.01,
                              volume_max=200.0, volume_step=0.01)
        if name in sizes else None
    )
    return module


def test_each_symbol_gets_its_own_contract_size(monkeypatch):
    """Satu contract size untuk seluruh run adalah error 50x.

    XAUUSD 100 unit per lot, XAGUSD 5000. Terukur di terminal 2026-08-27.
    Sampai hari itu `sizing` dipanggil sekali lalu satu LotSpec-nya disebar,
    jadi salah satu dari keduanya salah 50x. Di dry run ia jatuh ke arah yang
    berbahaya: silver dengan stop 0,651 pada 0,01 lot terbaca 0,65 USD,
    sedangkan angka sebenarnya 32,53.
    """
    monkeypatch.setitem(sys.modules, "MetaTrader5",
                        _symbol_module({"XAUUSD": 100.0, "XAGUSD": 5000.0}))
    lots, missing = execute.lot_specs(["mt5:XAUUSD", "mt5:XAGUSD"])

    assert missing == []
    assert lots["XAUUSD"].contract_size == 100.0
    assert lots["XAGUSD"].contract_size == 5000.0


def test_a_symbol_the_terminal_does_not_carry_is_named_rather_than_guessed(monkeypatch):
    monkeypatch.setitem(sys.modules, "MetaTrader5",
                        _symbol_module({"XAUUSD": 100.0}))
    lots, missing = execute.lot_specs(["mt5:XAUUSD", "mt5:XAGUSD"])

    assert missing == ["XAGUSD"]
    assert "XAGUSD" not in lots


def test_no_terminal_means_no_contract_size_rather_than_the_gold_default(monkeypatch):
    """Default `LotSpec` memegang angka XAUUSD, dan itu bukan default yang aman."""
    module = types.ModuleType("MetaTrader5")
    module.initialize = lambda: False
    module.last_error = lambda: (1, "no terminal")
    monkeypatch.setitem(sys.modules, "MetaTrader5", module)

    lots, missing = execute.lot_specs(["mt5:XAUUSD", "mt5:XAGUSD"])
    assert lots == {}
    assert missing == ["XAUUSD", "XAGUSD"]


# ------------------------------------------------- retcode 0, dua arti berbeda


def test_a_successful_send_is_10009_and_not_zero():
    """Terukur 27 Agustus 2026, dan biayanya dua order yang salah dicatat.

    Terminal membalas `order_send` dengan 10009 TRADE_RETCODE_DONE saat pending
    berhasil ditempatkan. Kode lama menguji `retcode != 0`, jadi ticket
    4609944538 dan 4609944542 benar-benar hidup di broker sementara tool
    mencetak "GAGAL" dan menulis dua record `refused`.
    """
    mt5 = FakeMT5(send=FakeSend(retcode=10009, order=4609944538))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket == 4609944538, why
    assert why == ""


def test_a_pending_accepted_as_placed_is_also_success():
    mt5 = FakeMT5(send=FakeSend(retcode=10008, order=7))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket == 7, why


def test_retcode_zero_from_order_send_is_not_success():
    """0 adalah sukses untuk `order_check` dan BUKAN untuk `order_send`."""
    mt5 = FakeMT5(send=FakeSend(retcode=0, order=0))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "retcode=0" in why


def test_a_partial_fill_is_not_counted_as_a_placed_order():
    """10010 DONE_PARTIAL berarti ukurannya lebih kecil dari yang disizing."""
    mt5 = FakeMT5(send=FakeSend(retcode=10010, order=8))
    ticket, why = execute.place(mt5, zone(), FakePlan(), "XAUUSD", 0.01)
    assert ticket is None
    assert "10010" in why


def test_partners_are_read_for_ssmt_but_never_traded(monkeypatch):
    """Partner masuk ke `series`, dan TIDAK PERNAH masuk ke loop kandidat.

    Satu daftar untuk dua tujuan berlawanan adalah cacatnya. SSMT butuh partner
    yang BERKORELASI - XAGUSD terhadap XAUUSD terukur r +0,851 pada 1953 bar 1h -
    sementara cap portofolio dan guard korelasi menginginkan yang TIDAK
    berkorelasi. Selama `--symbol` melayani keduanya, operator hanya punya dua
    pilihan sama buruknya: mematikan SSMT dengan satu simbol, atau diam-diam
    melebarkan universe yang bisa diorder demi mengaktifkan SSMT.

    Yang dijaga di sini arahnya, dan arah ini yang berbahaya: sebuah partner
    yang bocor ke daftar scan adalah instrumen yang diorder tanpa ada yang
    memintanya.
    """
    from tools import execute

    loaded: list[str] = []
    scanned: list[str] = []

    def fake_load(symbol, interval, bars):
        loaded.append(symbol)
        return []

    def fake_candidates(symbol, interval, bars, equity, risk_pct, lot, rules, series):
        scanned.append(symbol)
        return [], {"interval": interval, "candles": [], "meta": {}}, 0.0

    monkeypatch.setattr(execute.history, "load", fake_load)
    monkeypatch.setattr(execute, "candidates", fake_candidates)
    monkeypatch.setattr(execute, "blockers", lambda response: [])

    ranked, blocked, series = execute.gather(
        ["mt5:XAUUSD"], ["1h"], 100, 1000.0, 0.01, None, execute.Rules(),
        ["mt5:XAGUSD", "mt5:XPTUSD"],
    )

    assert scanned == ["mt5:XAUUSD"], (
        f"partner bocor ke daftar yang bisa diorder: {scanned}"
    )
    assert loaded == ["mt5:XAUUSD", "mt5:XAGUSD", "mt5:XPTUSD"], loaded
    # `series` adalah yang dioper ke `candidates` sebagai partners, jadi ketiganya
    # harus ada di sana atau SSMT tetap tidak dievaluasi.
    assert sorted(series) == ["XAGUSD", "XAUUSD", "XPTUSD"], sorted(series)
    assert ranked == [] and blocked == []


def test_the_order_path_hands_confluence_its_cisd_levels_and_stamps_the_range(
    monkeypatch,
):
    """Dua wiring yang hilang di `candidates`, diuji di titik panggilnya.

    KEDUANYA MEMBUAT SEBUAH KLAUSA MUSTAHIL LOLOS, bukan sekadar kurang akurat,
    dan keduanya terbaca sebagai fakta pasar:

      `cisd_in_band` -> `poi.confluence` menghitung apa yang diberikan, dan jalur
      order tidak memberi apa-apa, jadi `stack.cisd` selalu 0. Cacat yang sama
      persis sudah pernah ditemukan di `tools/conditioned.py`, yang docstring-nya
      mencatat kolomnya kembali False untuk 953 trade.

      `ote` -> `mark_dealing_range` membaca di `first_test_time`, sementara loop
      ini membuang setiap zona yang punya `first_test_time`. Terukur 28 Agustus
      2026 pada jalur order sungguhan: 23 dari 23 kandidat tanpa bacaan.

    Yang di-fake di sini adalah detector, plan, biaya, dan checklist, karena
    tidak satu pun dari mereka yang rusak. `mark_dealing_range_now` dan filter
    level dibiarkan ASLI, karena persis di situ cacatnya hidup. Recorder-nya
    diperiksa PERNAH dipanggil, supaya stub yang melenceng gagal keras alih-alih
    membuat test ini lulus tanpa menguji apa pun.
    """
    from types import SimpleNamespace

    from app.models import Candle
    from app.poi import Confluence

    step = 3600
    # Gelombang segitiga dengan kaki LEBIH PANJANG DARI `swing_n`, yang default
    # 50 di `mark_dealing_range_now`. Versi pertama fixture ini berkaki 11 bar,
    # jadi tidak satu pun swing pernah confirmed, `range_at` menjawab (None,
    # None), dan assertion di bawah gagal karena fixture-nya, bukan karena
    # kodenya. Kaki 61 bar memberi ruang 50 bar di kedua sisi.
    prices: list[float] = []
    for _ in range(4):
        prices += list(range(100, 161)) + list(range(160, 99, -1))
    # MULAI TEPAT DI TENGAH MALAM NEW YORK, bukan di epoch bulat. `true_opens`
    # menolak menginterpolasi: ia mengembalikan level hanya kalau ada bar yang
    # membuka PERSIS di batas kuartal. Versi pertama fixture ini mulai di
    # 1_700_000_000, yaitu menit :13:20, jadi tidak satu pun batas pernah jatuh
    # di atas sebuah bar dan `true_open_prices` kosong karena fixture-nya, bukan
    # karena kodenya.
    from app.clock import NY

    origin = int(datetime(2026, 1, 5, 0, 0, tzinfo=NY).timestamp())
    rows = [
        Candle(time=origin + i * step, open=float(p), high=float(p) + 0.5,
               low=float(p) - 0.5, close=float(p), volume=100.0)
        for i, p in enumerate(prices)
    ]
    box = zone(kind=ZoneKind.RBR, side=ZoneSide.DEMAND, zid="RBR-1")
    box.top, box.bottom, box.proximal, box.distal = 122.0, 118.0, 122.0, 118.0
    box.first_test_time = None
    box.departure_atr = 9.0
    box.dealing_range_pos = None

    last_time = rows[-1].time
    inside = 120.0            # di dalam box, dan sudah lampau
    outside_box = 200.0       # lampau tapi di luar box
    from_the_future = 121.0   # di dalam box, tapi belum knowable

    seen: dict = {}

    def recorder(zone_, others, as_of, born_from, born_to, cisd_levels=None,
                 true_open_prices=None):
        seen["cisd_levels"] = list(cisd_levels or [])
        seen["true_open_prices"] = list(true_open_prices or [])
        seen["calls"] = seen.get("calls", 0) + 1
        return Confluence(supports={}, conflicts=0,
                          cisd=sum(1 for x in (cisd_levels or [])
                                   if zone_.bottom <= x <= zone_.top))

    monkeypatch.setattr(execute.history, "load", lambda s, i, b: rows)
    monkeypatch.setattr(execute, "DETECTORS",
                        {"supply_demand": lambda candles, params: ([box], {})})
    monkeypatch.setattr(execute, "other_boxes", lambda candles: {})
    monkeypatch.setattr(execute, "cisds", lambda candles: ([
        SimpleNamespace(time=last_time - step, level=inside),
        SimpleNamespace(time=last_time - step, level=outside_box),
        SimpleNamespace(time=last_time + step, level=from_the_future),
    ], []))
    monkeypatch.setattr(execute, "confluence", recorder)
    monkeypatch.setattr(execute, "cost_to_risk", lambda *a, **k: (0.0, {}))
    monkeypatch.setattr(execute, "build", lambda *a, **k: SimpleNamespace(
        entry=122.0, stop=118.0, target=140.0, risk_per_unit=4.0, reward_r=4.5,
        placeable=True, lots=0.1, warnings=[]))
    monkeypatch.setattr(execute, "ict_setup",
                        lambda *a, **k: SimpleNamespace(met=0, conditions=[]))

    out, _, _ = execute.candidates("mt5:FAKE", "1h", len(rows))

    assert seen.get("calls") == 1, (
        "confluence tidak pernah dipanggil, jadi test ini tidak menguji apa pun"
    )
    assert len(out) == 1
    # LEVEL DIKIRIM, dan yang belum knowable DIBUANG. Tanpa potongan itu klausa
    # cisd_in_band akan dilewati oleh level yang belum ada saat keputusan dibuat.
    assert seen["cisd_levels"] == [inside, outside_box], seen["cisd_levels"]
    assert from_the_future not in seen["cisd_levels"]
    # DAN RANGE-NYA TERSTEMPEL, pada zona yang first_test_time-nya None, yang
    # adalah satu-satunya jenis zona yang pernah sampai ke sini.
    assert box.dealing_range_pos is not None, (
        "kandidat tanpa dealing_range_pos membuat klausa ote menjawab "
        "'no dealing range' selamanya"
    )
    # DAN TRUE OPEN IKUT DIOPER. `poi.confluence` menerima `true_open_prices`
    # sejak lama dan jalur order tidak pernah mengisinya, jadi `stack.true_opens`
    # selalu 0 - cacat yang sama persis dengan `cisd_levels`. Delapan baris
    # tabel PAPAN WAKTU di `Buku=Pegangan.txt` semuanya True Open, jadi nol di
    # sini berarti pusat metodenya tidak sampai ke keputusan.
    assert seen["true_open_prices"], (
        "true_open_prices kosong: stack.true_opens akan selalu 0"
    )
