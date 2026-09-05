"""Parity kotak IFVG: detector kita lawan tiga script komunitas di TradingView.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.ifvg_parity

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

    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print(file=sys.stdout)
    return 0


def _selftest() -> None:
    assert matches((100.0, 99.0), (100.005, 98.995))
    assert not matches((100.0, 99.0), (100.05, 99.0))
    # Tiap kotak harus punya top di atas bottom, di kedua daftar.
    for z in OURS + BENCH["LuxAlgo"] + BENCH["ChartPrime"]:
        assert z[0] > z[1], z


if __name__ == "__main__":
    _selftest()
    raise SystemExit(main())
