"""Kontrak antara sisi MQL5 dan tool Python yang mengemudikannya.

Dua hal di seam ini gagal DIAM-DIAM, dan keduanya sudah pernah terjadi:

  1. MT5 mengabaikan key yang tidak dikenal di sebuah `.set` tanpa satu pesan
     pun, dan memakai compiled default untuk input yang tidak disebut. Jadi
     sebuah `.set` yang kurang satu baris menghasilkan run yang hijau dengan
     input yang TIDAK tercatat - yang persis lubang reproducibility yang
     `tools/mt5_backtest.py` dibangun untuk menutupnya.
  2. Sebuah gate yang mencetak vonis tanpa exit code melaporkan merah sebagai
     hijau ke setiap pembungkus yang membacanya. Ketiga `ea_parity*` melakukan
     itu sampai 1 September 2026, dan terbukti: mencabut test "last" dari port
     referensi order block memberi 414 dari 415 mismatch dan exit 0.

Diperiksa dari Python karena Python yang memegang daftarnya. Tidak ada compiler
MQL5 di jalur test, jadi yang dibaca teks source-nya, sama seperti
`test_frontend_defaults.py` membaca TypeScript.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

MQL5 = Path(__file__).resolve().parents[2] / "mql5" / "ZonelabSupplyDemand"
TOOLS = Path(__file__).resolve().parents[1] / "tools"

#: Gate yang mencetak vonis dan karena itu harus menutupnya dengan exit code.
GATES = ("ea_parity.py", "ea_parity_ob.py", "ea_parity_fvg.py", "mqh_parity.py")


def _inputs(expert: str) -> set[str]:
    source = (MQL5 / f"{expert}.mq5").read_text(encoding="utf-8")
    return set(re.findall(r"^input\s+\w+\s+(Inp\w+)", source, re.M))


def test_every_ea_input_is_recorded_in_the_set_file():
    """`SHIPPED` must name every input its EA declares, and no others.

    An input the dict omits is an input the `.set` omits, and MT5 then silently
    uses the compiled default - so the run happens at a setting nobody wrote
    down. An input the dict invents is written to the `.set` and silently
    ignored, so the run happens at a setting that looks recorded and was not.
    Both directions produce a green run and a false record, which is why both
    are asserted.
    """
    from tools.mt5_backtest import SHIPPED

    problems = []
    for expert, declared in SHIPPED.items():
        real = _inputs(expert)
        missing = sorted(real - set(declared))
        invented = sorted(set(declared) - real)
        if missing:
            problems.append(f"{expert}: tidak tercatat di SHIPPED {missing}")
        if invented:
            problems.append(f"{expert}: di SHIPPED tapi tidak ada di EA {invented}")
    assert not problems, "\n".join(problems)


def test_every_expert_the_driver_knows_about_exists():
    """A name in `SHIPPED` with no .mq5 beside it fails at run time, not here.

    `tools/mt5_backtest.py` writes the ini before it launches anything, so an
    expert that does not exist produces a tester that starts, finds nothing, and
    times out after an hour with "NO REPORT" - which reads exactly like a cell
    that crashed.
    """
    from tools.mt5_backtest import SHIPPED

    missing = sorted(e for e in SHIPPED if not (MQL5 / f"{e}.mq5").exists())
    assert not missing, f"terdaftar di driver, file .mq5-nya tidak ada: {missing}"


@pytest.mark.parametrize("name", GATES)
def test_a_gate_that_prints_a_verdict_also_exits_on_it(name):
    """Printing PARITY FAIL and returning 0 is worse than not checking.

    The three `ea_parity*` gates did exactly that until 1 September 2026, and
    the defect was not theoretical: with the "last" test removed from the order
    block reference port they reported 414 mismatches out of 415 and still
    exited 0, so every wrapper reading the status saw green on a red run.
    """
    source = (TOOLS / name).read_text(encoding="utf-8")
    assert "PARITY FAIL" in source or "MQH PARITY FAIL" in source, (
        f"{name} tidak lagi mencetak vonis gagal; kalau memang begitu, hapus "
        "ia dari GATES supaya test ini tidak lolos secara hampa"
    )
    assert re.search(r"raise SystemExit\(", source), (
        f"{name} mencetak vonis gagal tanpa exit code, jadi run merah "
        "terlaporkan hijau"
    )


def test_every_registered_detector_is_ported_or_written_down_as_not():
    """A sixth detector cannot slip into the registry unmeasured and unnoticed.

    `app/detect/__init__.py` warns at its own bottom that a second list of layer
    ids drifts silently, and this project has paid for exactly that twice: a
    layer added to `app/layers.py` left `e2e/wiring.mjs` red for two commits,
    and the `wyckoff` slider left `e2e/sweep.mjs` red for twenty four.
    `tools/mqh_parity.py` holds such a list - which detectors have an MQL5 dump
    to compare against - so it is the same hazard in a third place.

    What this does NOT demand is that every detector be ported. Zonelab may
    legitimately draw things MT5 does not. What it demands is that the decision
    be WRITTEN: a new detector lands in PORTED with a dump file, or in UNPORTED
    with a reason. "Its precision was never measured" and "its precision was
    measured and passed" must not look the same from the outside.
    """
    from app.layers import LAYERS
    from tools.mqh_parity import PORTED, PORTED_EVENTS, UNPORTED

    accounted = set(PORTED) | set(PORTED_EVENTS) | set(UNPORTED)
    ict = {layer.id for layer in LAYERS if layer.family == "ICT"}

    unaccounted = sorted(ict - accounted)
    assert not unaccounted, (
        "layer ICT yang tidak ada di PORTED, PORTED_EVENTS maupun UNPORTED, "
        "jadi presisinya tidak diukur dan tidak ada yang mencatatnya: "
        f"{unaccounted}"
    )
    known = {layer.id for layer in LAYERS}
    stale = sorted(accounted - known)
    assert not stale, f"tercatat di mqh_parity tapi bukan layer: {stale}"

    # Sebuah nama tidak boleh muncul di dua daftar: "diport" dan "sengaja tidak
    # diport" adalah pernyataan yang saling meniadakan, dan sebuah nama di
    # keduanya berarti salah satunya sudah basi tanpa ada yang tahu yang mana.
    pairs = (
        ("PORTED", "PORTED_EVENTS", set(PORTED) & set(PORTED_EVENTS)),
        ("PORTED", "UNPORTED", set(PORTED) & set(UNPORTED)),
        ("PORTED_EVENTS", "UNPORTED", set(PORTED_EVENTS) & set(UNPORTED)),
    )
    for left, right, overlap in pairs:
        assert not overlap, f"ada di {left} DAN {right}: {sorted(overlap)}"

    # Setiap alasan harus benar-benar sebuah alasan. Sebuah string kosong lolos
    # dict tapi tidak memberi tahu pembaca apa pun, yang mengembalikan keadaan
    # yang test ini ada untuk mencegah.
    thin = sorted(n for n, why in UNPORTED.items() if len(why.strip()) < 40)
    assert not thin, f"terdaftar tidak diport tanpa alasan yang bisa dibaca: {thin}"
