"""Parity kotak: detector kita lawan script komunitas di TradingView.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.box_parity

KENAPA PERBANDINGANNYA DI PINE, BUKAN LANGSUNG KE PYTHON. Feed-nya harus sama.
Zonelab membaca terminal MT5 dan TradingView membaca FXCM; harga penutupan
keduanya berbeda beberapa sen, jadi perbandingan lintas feed tidak bisa
membedakan "aturan deteksi berbeda" dari "data berbeda". `Zonelab IFVG` di Pine
adalah cermin baris per baris `app/detect/inversion.py` yang dijalankan pada
feed yang SAMA dengan pembandingnya, jadi selisih apa pun yang tersisa adalah
selisih aturan.

ANGKANYA DISALIN DARI `data_get_pine_boxes`, bukan diambil ulang di sini, dan
itu batas berkas ini: ia menghitung, bukan mengambil. Setiap daftar di bawah
membawa tanggal dan cell-nya supaya bisa diambil ulang.
"""

from __future__ import annotations

import json
import sys

CELL = "FX:XAUUSD 30m, 2026-09-05"
TOL = 0.01  # satu sen, karena kedua daftar dibulatkan ke dua desimal

#: 40 kotak terbaru milik kita, dari `Zonelab IFVG`.
OURS = [
    (4486.03, 4485.20), (4484.10, 4480.85), (4479.67, 4476.80),
    (4478.87, 4472.74), (4476.92, 4449.95), (4472.50, 4469.74),
    (4452.45, 4449.96), (4451.12, 4446.64), (4446.74, 4442.36),
    (4446.30, 4444.75), (4438.99, 4434.64), (4433.90, 4432.64),
    (4433.31, 4429.76), (4433.21, 4430.53), (4432.02, 4429.77),
    (4431.37, 4431.00), (4428.22, 4428.13), (4427.50, 4426.61),
    (4425.89, 4420.07), (4425.34, 4420.46), (4424.13, 4373.57),
    (4419.28, 4415.33), (4412.04, 4383.36), (4400.20, 4397.61),
    (4383.81, 4383.03), (4381.88, 4378.04), (4375.08, 4373.57),
    (4372.05, 4369.53), (4365.97, 4357.47), (4365.74, 4361.94),
    (4361.64, 4359.12), (4352.67, 4349.31), (4352.43, 4351.87),
    (4340.94, 4337.51), (4337.03, 4334.20), (4328.33, 4326.96),
    (4317.54, 4313.93), (4312.47, 4311.74), (4304.53, 4300.68),
    (4293.92, 4291.15),
]

BENCH = {
    "LuxAlgo": [
        (4545.44, 4540.82), (4523.51, 4517.21), (4514.96, 4493.70),
        (4478.87, 4472.74), (4476.92, 4449.95), (4433.31, 4429.76),
        (4412.04, 4383.36), (4340.94, 4337.51), (4262.59, 4255.56),
        (4225.43, 4219.01),
    ],
    "ChartPrime": [
        (4681.71, 4675.56), (4666.52, 4661.31), (4657.44, 4651.36),
        (4632.54, 4625.11), (4616.25, 4610.50), (4598.79, 4580.77),
        (4596.53, 4585.52), (4551.27, 4529.54), (4545.44, 4540.82),
        (4523.66, 4487.46), (4523.51, 4517.21), (4514.96, 4493.70),
        (4478.87, 4472.74), (4432.85, 4425.97), (4412.04, 4383.36),
        (4378.90, 4358.23), (4356.88, 4339.19), (4329.05, 4324.37),
        (4321.61, 4310.70), (4278.30, 4271.38), (4255.99, 4250.13),
        (4228.80, 4206.66), (4203.23, 4198.00), (4188.74, 4180.50),
        (4174.07, 4161.60), (4160.05, 4142.14), (4126.78, 4108.14),
        (4116.83, 4108.85), (4102.08, 4097.52), (4095.59, 4088.62),
        (4077.74, 4073.53), (4060.34, 4055.38), (4051.54, 4044.96),
        (4043.38, 4038.79), (4027.20, 4017.58), (4008.30, 3999.34),
        (3989.88, 3975.70),
    ],
    #: TIDAK MENGGAMBAR BOX SAMA SEKALI. `data_get_pine_boxes` mengembalikan nol
    #: study untuknya: ia menandai inversi dengan garis dan label, bukan
    #: rectangle. Dicatat sebagai "tidak bisa dibandingkan pada geometri kotak",
    #: bukan sebagai nol kecocokan, karena keduanya berbeda arti.
    "TradingFinder": [],
}


def matches(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= TOL and abs(a[1] - b[1]) <= TOL


#: ORDER BLOCK, 6 September 2026, setelah detector-nya diubah ke body-box plus
#: impuls dari close.
#:
#: PEMBANDINGNYA BERGANTI, DAN ALASANNYA BUKAN SELERA. `Order Block Detector
#: [LuxAlgo]` yang dipakai di putaran pertama ternyata memakai VOLUME PIVOT,
#: bukan definisi adjacency: `ta.pivot` pada seri volume, tanpa syarat struktur
#: dan tanpa syarat impuls, dengan box digambar low ke median. Ia mengukur objek
#: yang berbeda, jadi membandingkan kotaknya dengan kotak kita bukan uji parity
#: melainkan uji apakah dua definisi berbeda kebetulan bertemu.
#:
#: `Order Block Finder (Experimental)` memakai definisi yang SAMA dengan kita,
#: yaitu lilin berlawanan terakhir sebelum sederet lilin searah. Ia menggambar
#: GARIS, tiga per block - top, mid, bottom - dan mid-nya persis rata-rata
#: keduanya, jadi ia memakai RENTANG PENUH lilin.
#:
#: KESAMAAN PERSIS KARENA ITU MUSTAHIL SECARA KONSTRUKSI, dan itu harus
#: dinyatakan alih alih dilaporkan sebagai kegagalan: kita memakai BADAN lilin
#: sejak 6 September 2026. Yang benar diuji adalah CONTAINMENT - kalau keduanya
#: menandai lilin yang sama, badan kita harus duduk di dalam rentang mereka.
OB_THEIRS = [
    (4427.47, 4418.95),   # top/mid/bottom 4427.47 / 4423.21 / 4418.95
    (4330.97, 4321.64),   # 4330.97 / 4326.305 / 4321.64
]

#: 40 kotak terbaru milik kita di sel yang sama, dari `Zonelab OB`.
#:
#: FOTO, BUKAN NILAI HIDUP. Diambil 6 September 2026 pada aturan kotak-badan
#: TANPA lantai tinggi kotak; lantai 0,15 rentang dikirim setelahnya dan
#: memekarkan 17 persen kotak, jadi angka di bawah tidak lagi sama persis dengan
#: yang detector keluarkan hari ini. Yang diuji tetap sah karena ia containment
#: dan bukan kesamaan, dan sejak lantainya di-clamp ke rentang lilin containment
#: itu jadi jaminan STRUKTURAL: pembanding memakai rentang penuh lilin, kotak
#: kita tidak bisa keluar dari rentang lilin yang sama.
OB_OURS = [
    (4610.66, 4607.57), (4605.02, 4603.89), (4605.02, 4552.04),
    (4583.93, 4573.32), (4576.74, 4552.04), (4493.19, 4446.47),
    (4483.35, 4472.50), (4479.86, 4470.48), (4473.71, 4467.67),
    (4472.81, 4471.18), (4471.94, 4466.94), (4471.94, 4393.82),
    (4468.80, 4462.93), (4463.18, 4453.89), (4460.22, 4452.24),
    (4458.32, 4457.51), (4446.95, 4443.13), (4445.81, 4435.75),
    (4445.81, 4418.54), (4440.10, 4426.82), (4440.06, 4435.54),
    (4437.34, 4436.39), (4436.48, 4429.77), (4433.24, 4430.49),
    (4429.56, 4429.07), (4427.47, 4422.46), (4421.51, 4420.61),
    (4384.87, 4364.74), (4384.51, 4382.11), (4380.40, 4378.15),
    (4372.79, 4364.74), (4372.73, 4365.89), (4356.31, 4342.99),
    (4336.23, 4331.27), (4330.77, 4329.37), (4325.67, 4324.53),
    (4317.25, 4315.64), (4309.83, 4309.27), (4308.92, 4308.47),
    (4302.81, 4293.62),
]

#: Jejak filter, Python lawan cermin Pine-nya, pada aturan yang berlaku hari ini.
#: Ini menguji SELURUH jalur keputusan dan bukan cuma koordinat, jadi ia
#: pembanding yang berbeda dari tabel di atas dan keduanya perlu.
OB_FILTER_TRACE = {
    "python_mt5": {"candidates": 61222, "weak": 50293, "not_last": 2573, "drawn": 8356},
    "pine_fxcm": {"candidates": 31635, "weak": 26015, "not_last": 1283, "drawn": 4337},
}


def order_block_parity() -> dict:
    """Containment kotak, plus selisih jejak filter dalam poin persen."""
    inside = []
    for t_hi, t_lo in OB_THEIRS:
        hits = [o for o in OB_OURS if o[0] <= t_hi + TOL and o[1] >= t_lo - TOL]
        inside.append({
            "theirs": [t_hi, t_lo],
            "ours_inside": hits,
            "count": len(hits),
            "top_matches_exactly": any(abs(o[0] - t_hi) <= TOL for o in hits),
        })

    py, pine = OB_FILTER_TRACE["python_mt5"], OB_FILTER_TRACE["pine_fxcm"]
    share = lambda d, k: d[k] / d["candidates"] * 100  # noqa: E731
    trace = {
        k: {
            "python_pct": round(share(py, k), 2),
            "pine_pct": round(share(pine, k), 2),
            "diff_pp": round(share(pine, k) - share(py, k), 2),
        }
        for k in ("weak", "not_last", "drawn")
    }
    return {
        "note": (
            "Pembanding memakai RENTANG PENUH lilin dan kita memakai BADAN, jadi "
            "yang diuji containment, bukan kesamaan persis."
        ),
        "containment": inside,
        "all_contained": all(e["count"] >= 1 for e in inside),
        "filter_trace": trace,
        "max_abs_diff_pp": max(abs(v["diff_pp"]) for v in trace.values()),
    }


def main() -> int:
    lo = min(b for _t, b in OURS)
    hi = max(t for t, _b in OURS)
    out: dict = {
        "cell": CELL,
        "tolerance_price": TOL,
        "our_window": {"low": lo, "high": hi, "n_boxes": len(OURS)},
        "note": (
            "Perbandingan HANYA di dalam jendela harga kita. Kotak pembanding "
            "di luar rentang itu tidak dihitung sebagai selisih aturan, ia di "
            "luar cap tampilan kita."
        ),
        "benchmarks": {},
    }
    for name, zones in BENCH.items():
        if not zones:
            out["benchmarks"][name] = {
                "comparable": False,
                "reason": "tidak menggambar box; menandai inversi dengan garis dan label",
            }
            continue
        inside = [z for z in zones if lo - TOL <= z[1] and z[0] <= hi + TOL]
        hit = [z for z in inside if any(matches(z, o) for o in OURS)]
        miss = [z for z in inside if z not in hit]
        out["benchmarks"][name] = {
            "comparable": True,
            "zones_total": len(zones),
            "zones_in_our_window": len(inside),
            "exact_matches": len(hit),
            "rate": round(len(hit) / len(inside), 4) if inside else None,
            "unmatched": miss,
        }
        print(f"  {name:<14} {len(hit)}/{len(inside)} cocok persis di jendela kita",
              file=sys.stderr)
        for m in miss:
            print(f"      tak cocok: {m[0]} / {m[1]}", file=sys.stderr)

    ob = order_block_parity()
    out["order_block"] = ob
    print(f"  order block: containment {sum(e['count'] >= 1 for e in ob['containment'])}"
          f"/{len(ob['containment'])}, selisih jejak filter maksimum "
          f"{ob['max_abs_diff_pp']} poin persen", file=sys.stderr)

    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selftest() -> None:
    assert matches((100.0, 99.0), (100.005, 98.995))
    assert not matches((100.0, 99.0), (100.05, 99.0))
    # Tiap kotak harus punya top di atas bottom, di kedua daftar.
    for z in OURS + BENCH["LuxAlgo"] + BENCH["ChartPrime"] + OB_OURS + OB_THEIRS:
        assert z[0] > z[1], z
    ob = order_block_parity()
    assert ob["all_contained"], ob["containment"]


if __name__ == "__main__":
    _selftest()
    raise SystemExit(main())
