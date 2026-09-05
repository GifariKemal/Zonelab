"""P/L per trade dari report Strategy Tester, dan uji satu lengan lawan lengan lain.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.mt5_trades \
        --control ZonelabQT_XAUUSD_M15_a0control \
        --arm ZonelabQT_XAUUSD_M15_a1wed

KENAPA INI ADA. `tools/mt5_backtest.py` menyimpan ringkasan report: Profit
Factor, net, expected payoff. Ringkasan tidak bisa diuji. Sebuah lengan yang
memberi PF 1,10 lawan kontrol 1,00 pada 176 trade TERLIHAT lebih baik, dan
tanpa deret per-trade tidak ada cara membedakan itu dari sebaran biasa. Repo
ini sudah menolak beberapa klaim yang persis berbentuk begitu.

Report `.htm` MT5 memuat tabel Deals lengkap, jadi deretnya ADA, cuma tidak
pernah dibaca. Modul ini membacanya.

DEFINISI SATU TRADE, DAN SATU HAL YANG SALAH DI VERSI PERTAMA. Tiap round trip
punya dua deal, `in` lalu `out`. Deal `in` membawa `Comment` berisi id zona dan
SELURUH komisinya; deal `out` membawa profit dan komentar `sl 4342.452` atau
`tp 4317.668`, yaitu alasan penutupan, BUKAN id zona. Jadi memasangkan lewat
komentar gagal diam-diam: jumlah trade-nya benar, totalnya meleset tepat
sebesar seluruh komisi masuk. Terukur pada `a0control` XAUUSD: jumlah trade
450 lawan 450 cocok, tapi total +34,44 lawan net report -100,56, dan selisihnya
persis -135,00, yaitu komisi masuk 450 trade.

Yang dipakai sekarang: seluruh deal diurutkan menurut NOMOR DEAL, yang adalah
urutan eksekusi, lalu tiap `out` menutup `in` tertua yang masih terbuka. Tabel
report diurut menurut nomor ORDER dan bukan waktu maupun nomor deal, jadi
pengurutan ulang itu wajib.

BATAS KETELITIAN PEMASANGAN, DINYATAKAN. FIFO bisa menukar pasangan ketika
beberapa posisi terbuka bersamaan dan tidak tutup dalam urutan bukanya. Yang
tertukar hanyalah KOMISI, karena profit dan swap ada di deal `out` yang sudah
benar; komisi berkisar 0,1 sampai 0,5 unit akun sementara profit per trade
berkisar ratusan. Totalnya tidak terpengaruh sama sekali, dan atribusi per
trade meleset di bawah setengah persen. Itu diterima di sini dan disebut.

APA YANG UJINYA JAWAB, DAN APA YANG TIDAK. Ia membandingkan P/L per trade dalam
mata uang akun. Ukuran lot di EA ini majemuk terhadap equity, jadi dua lengan
menjalani jalur equity yang berbeda dan lot yang berbeda; deretnya karena itu
bukan pasangan. Welch dua sampel adalah bacaan yang benar untuk itu, dan ia
menjawab "apakah rata-rata P/L per trade berbeda", bukan "apakah edge-nya
berbeda per unit risiko". Yang kedua butuh risiko per trade, dan report tidak
menerbitkannya.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from math import sqrt
from pathlib import Path

import numpy as np

REPORTS = Path(__file__).resolve().parent.parent.parent / "mql5" / (
    "ZonelabSupplyDemand") / "reports"

#: Kolom tabel Deals, dalam urutan yang MT5 tulis.
COLUMNS = ("time", "deal", "symbol", "type", "direction", "volume", "price",
           "order", "commission", "swap", "profit", "balance", "comment")


def _cells(row: str) -> list[str]:
    return [re.sub(r"<[^>]+>", "", cell).replace("\xa0", " ").strip()
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]


def _number(text: str) -> float:
    """Angka MT5: spasi sebagai pemisah ribuan, titik sebagai desimal."""
    cleaned = text.replace(" ", "").replace(" ", "").replace(",", "")
    if not cleaned or cleaned in {"-", ""}:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_deals(html: str) -> list[dict]:
    """Tiap baris tabel Deals sebagai dict. Baris `balance` awal ikut dibuang."""
    start = html.rfind("Deals")
    if start < 0:
        return []
    out = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html[start:], re.S):
        cell = _cells(row)
        if len(cell) < len(COLUMNS):
            continue
        deal = dict(zip(COLUMNS, cell[:len(COLUMNS)]))
        if deal["direction"] not in ("in", "out"):
            continue
        for key in ("commission", "swap", "profit", "volume"):
            deal[key] = _number(deal[key])
        out.append(deal)
    return out


def trades(html: str) -> list[float]:
    """P/L per round trip, dipasangkan FIFO menurut nomor deal.

    Hasilnya urut menurut waktu TUTUP, karena itu urutan `out` dieksekusi, dan
    itu pula urutan yang uji paruh sampel butuhkan.

    Sebuah `in` tanpa `out` adalah posisi yang masih terbuka di akhir test; ia
    DIBUANG, bukan dilaporkan sebagai P/L nol, karena nol adalah angka dan
    posisi terbuka bukan hasil.
    """
    deals = sorted(parse_deals(html), key=lambda d: int(d["deal"] or 0))
    open_legs: list[float] = []
    out: list[float] = []
    for deal in deals:
        cost = deal["profit"] + deal["commission"] + deal["swap"]
        if deal["direction"] == "in":
            open_legs.append(cost)
        elif open_legs:
            out.append(open_legs.pop(0) + cost)
        else:
            # `out` tanpa `in` yang terbuka tidak bisa terjadi di report yang
            # utuh. Kalau terjadi, ia dihitung apa adanya dan bukan dibuang:
            # membuang P/L yang nyata lebih buruk daripada atribusi yang aneh.
            out.append(cost)
    return out


def read(tag: str) -> list[float]:
    path = REPORTS / f"{tag}.htm"
    if not path.exists():
        raise SystemExit(f"report tidak ada: {path}")
    raw = path.read_bytes()
    for encoding in ("utf-16", "utf-8", "cp1252"):
        try:
            return trades(raw.decode(encoding))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"tidak bisa membaca encoding {path}")


def welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    if len(a) < 2 or len(b) < 2:
        return float("nan"), float("nan")
    se = sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    delta = float(a.mean() - b.mean())
    return delta, (delta / se if se > 0 else float("nan"))


def compare(control_tag: str, arm_tag: str) -> dict:
    control = np.array(read(control_tag), dtype=np.float64)
    arm = np.array(read(arm_tag), dtype=np.float64)
    delta, t = welch(arm, control)

    # PARUH WAKTU. Deretnya sudah urut waktu karena tabel Deals urut waktu.
    def half_delta(part_arm, part_control):
        if len(part_arm) < 2 or len(part_control) < 2:
            return float("nan")
        return float(part_arm.mean() - part_control.mean())

    halves = [half_delta(arm[:len(arm) // 2], control[:len(control) // 2]),
              half_delta(arm[len(arm) // 2:], control[len(control) // 2:])]
    same = (not any(np.isnan(halves))) and (halves[0] > 0) == (halves[1] > 0)
    return {
        "control": control_tag, "arm": arm_tag,
        "n_control": int(len(control)), "n_arm": int(len(arm)),
        "mean_control": float(control.mean()) if len(control) else None,
        "mean_arm": float(arm.mean()) if len(arm) else None,
        "delta": delta, "welch_t": t,
        "halves_delta": halves, "halves_same_sign": same,
        "sd_control": float(control.std(ddof=1)) if len(control) > 1 else None,
        "sd_arm": float(arm.std(ddof=1)) if len(arm) > 1 else None,
    }


def _selftest() -> None:
    """Cacat yang modul ini ditulis untuk menangkap, disuntikkan lalu diperiksa."""
    head = "<div>Deals</div><table>"
    rows = [
        # baris deposit awal, harus diabaikan
        ("2026.01.01", "1", "", "balance", "", "0", "", "", "0.00", "0.00",
         "0.00", "10 000.00", ""),
        # Deal `in` membawa id zona dan komisinya. Baris sengaja TIDAK urut
        # nomor deal, karena report aslinya juga tidak: ia diurut nomor order.
        ("2026.02.05", "8", "XAUUSD", "buy", "in", "0.05", "4000.0", "6",
         "-0.20", "0.00", "0.00", "10 099.04", "RBR-2"),
        ("2026.01.05", "6", "XAUUSD", "sell", "in", "0.05", "4445.2", "5",
         "-0.18", "0.00", "0.00", "9 999.82", "DBD-1"),
        # Deal `out` membawa ALASAN tutup, bukan id zona, dan komisi nol.
        ("2026.01.06", "7", "XAUUSD", "buy", "out", "0.05", "4400.0", "55",
         "0.00", "-0.40", "100.00", "10 099.24", "sl 4400.000"),
        ("2026.02.06", "9", "XAUUSD", "sell", "out", "0.05", "3900.0", "57",
         "0.00", "0.00", "-50.00", "10 048.84", "tp 3900.000"),
        # posisi yang tidak pernah ditutup: hanya `in`, harus dibuang
        ("2026.03.01", "10", "XAUUSD", "buy", "in", "0.05", "4100.0", "7",
         "-0.20", "0.00", "0.00", "10 048.64", "RBR-3"),
    ]
    html = head + "".join(
        "<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>"
        for row in rows) + "</table>"

    deals = parse_deals(html)
    # Baris `balance` bukan deal, jadi lima dari enam baris yang terhitung.
    assert len(deals) == 5, len(deals)

    got = trades(html)
    # FIFO menurut nomor deal: in 6 tutup di out 7, in 8 tutup di out 9.
    # Trade 1: 100.00 - 0.40 - 0.18 = 99.42. Trade 2: -50.00 - 0.20 = -50.20.
    assert len(got) == 2, got
    assert abs(got[0] - 99.42) < 1e-9, got
    assert abs(got[1] + 50.20) < 1e-9, got
    # TOTALNYA HARUS SAMA DENGAN NET REPORT, dan ini check yang menangkap
    # cacat pemasangan lewat komentar: di sana jumlah trade-nya benar tapi
    # totalnya kehilangan seluruh komisi masuk.
    deals = parse_deals(html)
    net = sum(d["profit"] + d["commission"] + d["swap"] for d in deals
              if d["comment"] != "RBR-3")
    assert abs(sum(got) - net) < 1e-9, (sum(got), net)
    # Posisi terbuka dibuang, bukan dilaporkan nol.
    assert 0.0 not in got

    # Pemisah ribuan MT5 adalah SPASI, dan tanpa penanganannya 10 000.00
    # terbaca gagal lalu jadi nol - biaya yang hilang tanpa suara.
    assert _number("10 000.00") == 10000.0
    assert _number("-1 234.56") == -1234.56
    assert _number("") == 0.0 and _number("-") == 0.0

    # Welch memisahkan dua rata-rata yang jelas berbeda dan tidak memisahkan
    # dua yang sama.
    a, b = np.arange(100.0), np.arange(100.0) + 40
    assert welch(b, a)[1] > 5
    assert abs(welch(a, a.copy())[1]) < 1e-9

    print("mt5_trades selftest ok", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control", default="")
    parser.add_argument("--arm", default="")
    parser.add_argument("--dump", default="", help="cetak P/L per trade satu tag")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        _selftest()
        return 0
    if args.dump:
        values = read(args.dump)
        json.dump({"tag": args.dump, "n": len(values), "trades": values},
                  sys.stdout, indent=2)
        print()
        return 0
    if not args.control or not args.arm:
        raise SystemExit("butuh --control dan --arm, atau --dump")
    json.dump(compare(args.control, args.arm), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
