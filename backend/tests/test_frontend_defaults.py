"""The frontend's copy of every default must agree with the model that owns it.

`frontend/src/lib/types.ts` holds `DEFAULT_LAYER_PARAMS`, roughly seventy values
hand-copied out of `app/models/params.py`, and it ships every one of them on
every `/api/draw` call. So a backend default that moves without its copy moving
does not fall back to the backend value - the stale copy overrides it, on every
request, silently.

It is not hypothetical and it is not old. The `dfr` block landed with
`max_ranges: 20` in the model and `4` in the copy, chosen minutes apart, and the
only reason anyone noticed is that both numbers were written in the same hour.
`DrawRequest` has `extra="forbid"`, so a RENAME fails loudly with a 422; a
changed VALUE is exactly the case nothing catches.

This test does not argue about where the defaults should live - `/api/config`
already exists to stop this class of duplication and could serve them. It only
makes the duplication honest: as long as the copy exists, it has to agree.

Two asymmetries are deliberate:

  - a key the frontend OMITS is fine. It sends nothing, the model's own default
    applies, and that is the behaviour you want. Reported, not failed.
  - a key the frontend has and the model does not is failed. Under
    `extra="forbid"` on the parent it would 422, and on a params block that
    allows extras it would be silently dropped - a control that looks wired and
    is not, which is the defect class this project has already shipped twice.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.models import (
    CISDParams,
    ChecklistParams,
    DFRParams,
    GapParams,
    ImbalanceParams,
    LiquidityParams,
    NewsParams,
    PoolParams,
    ProjectionParams,
    SessionParams,
    StructureParams,
    SupplyDemandParams,
    ExpectationParams,
    ChartGapParams,
    WyckoffParams,
    PSPParams,
)

TYPES_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "types.ts"

#: params-block name in `LayerParams` -> the model that owns those defaults.
OWNERS = {
    "supply_demand": SupplyDemandParams,
    "imbalance": ImbalanceParams,
    "structure": StructureParams,
    "dfr": DFRParams,
    "session": SessionParams,
    "gaps": GapParams,
    "news": NewsParams,
    "cisd": CISDParams,
    "pools": PoolParams,
    "liquidity": LiquidityParams,
    "projections": ProjectionParams,
    "checklist": ChecklistParams,
    "expectation": ExpectationParams,
    "chart_gaps": ChartGapParams,
    "wyckoff": WyckoffParams,
    "psp": PSPParams,
}


def _default_layer_params() -> dict:
    """`DEFAULT_LAYER_PARAMS` out of the TypeScript source, as a dict.

    Braces are counted rather than matched by regex, because the block is nested
    and a greedy pattern would stop at the first `};` inside it. The literal is
    plain data - numbers, strings, booleans, arrays - so once the trailing commas
    are gone and the keys are quoted it IS JSON.
    """
    source = TYPES_TS.read_text(encoding="utf-8")
    start = source.index("export const DEFAULT_LAYER_PARAMS")
    open_brace = source.index("{", start)
    depth = 0
    for i in range(open_brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                body = source[open_brace : i + 1]
                break
    else:  # pragma: no cover - a malformed literal is a syntax error upstream
        raise AssertionError("DEFAULT_LAYER_PARAMS is not brace-balanced")

    body = re.sub(r"//[^\n]*", "", body)
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"(^|[{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def test_the_typescript_copy_matches_every_model_default():
    parsed = _default_layer_params()
    assert set(parsed) == set(OWNERS), (
        "the frontend params blocks and the model registry disagree about which "
        f"blocks exist: only in TS {sorted(set(parsed) - set(OWNERS))}, only in "
        f"Python {sorted(set(OWNERS) - set(parsed))}"
    )

    wrong: list[str] = []
    unknown: list[str] = []
    omitted: list[str] = []

    for block, model in OWNERS.items():
        theirs = parsed[block]
        ours = model().model_dump()
        for key, value in theirs.items():
            if key not in ours:
                unknown.append(f"{block}.{key}")
                continue
            mine = ours[key]
            # Lists compare elementwise; a tuple default and a JSON array are the
            # same value written two ways.
            if isinstance(mine, (list, tuple)):
                if list(mine) != list(value):
                    wrong.append(f"{block}.{key}: python {list(mine)!r} vs ts {value!r}")
            elif isinstance(mine, float) or isinstance(value, float):
                if mine != pytest.approx(value):
                    wrong.append(f"{block}.{key}: python {mine!r} vs ts {value!r}")
            elif mine != value:
                wrong.append(f"{block}.{key}: python {mine!r} vs ts {value!r}")
        omitted.extend(f"{block}.{k}" for k in ours if k not in theirs)

    assert not unknown, (
        "the frontend ships knobs no model has, so they are dropped or rejected: "
        + ", ".join(sorted(unknown))
    )
    assert not wrong, (
        "a default moved on one side only, and the stale copy WINS because the "
        "frontend sends it on every request: " + "; ".join(sorted(wrong))
    )
    # SEBUAH ASSERT SEKARANG, DAN SEBELUMNYA CUMA PRINT. Komentar lama menyebut
    # ketiadaan itu "benar" karena key yang hilang jatuh ke default model, lalu
    # mengakui sendiri di kalimat berikutnya bahwa knob yang hilang dari salinan
    # biasanya juga hilang dari UI - dan tetap tidak meng-assert-nya.
    #
    # Akibatnya bisa diperiksa: `supply_demand.curve_lookback` dan
    # `supply_demand.arrival_bars` hilang dari `types.ts`, dicetak ke stdout
    # pytest setiap run, dan suite tetap hijau. Itu persis kelas cacat yang
    # CLAUDE.md peringatkan, di gerbang yang ditulis untuk mencegahnya.
    #
    # KENAPA INI BUKAN KOSMETIK. Key yang hilang memang jatuh ke default model
    # HARI INI. Besok default itu bergeser dan tidak ada yang memberi tahu,
    # karena kedua cek di atas hanya membandingkan key yang HADIR di kedua sisi.
    # Salinan yang lengkap adalah yang membuat keduanya mengikat untuk seluruh
    # model, bukan untuk sebagiannya.
    assert not omitted, (
        "the frontend copy is missing model defaults, so the two checks above "
        "cannot bind for them and a default that moves later moves silently: "
        + ", ".join(sorted(omitted))
    )


def test_every_degree_has_an_ink_weight_on_the_canvas():
    """A degree with no row in the canvas `WEIGHT` map draws its label off-pane.

    `Object.keys(WEIGHT)` is read twice in `session-primitive.ts`: as the paint
    order, and as the label's ROW INDEX. A degree missing from it gets
    `indexOf === -1`, so its label lands at a negative y - claimed in the
    collision map, invisible to the reader. Both degrees that live outside
    `DEGREES` were missing when they shipped, and `e2e/labels.mjs` could not fail
    it because a claim wholly outside the pane is normally harmless.

    Checked from Python against the TypeScript source, the same seam
    `test_the_typescript_copy_matches_every_model_default` uses, because the
    authority on which degrees exist is `app/quarters.py` and nothing on the
    canvas can know that.
    """
    import re

    from app.quarters import ALL_DEGREES

    source = (
        TYPES_TS.parent.parent / "components" / "session-primitive.ts"
    ).read_text(encoding="utf-8")
    start = source.index("const WEIGHT")
    body = source[start : source.index("};", start)]
    keys = set(re.findall(r"^\s{2}([a-z]+):\s*\{", body, re.M))

    missing = sorted(set(ALL_DEGREES) - keys)
    assert not missing, f"degrees with no ink weight, so their labels draw off-pane: {missing}"
    extra = sorted(keys - set(ALL_DEGREES))
    assert not extra, f"ink weights for degrees that do not exist: {extra}"


def test_one_place_owns_the_demand_and_supply_colours():
    """Every hard-coded copy of the zone colour pair must equal globals.css.

    `globals.css` already carries the warning: "FIVE PLACES HOLD THIS PAIR and
    they must move together, or zones and candles end up different reds". On
    2026-08-21 the pair moved from #2ea36f/#d4574f to #1f8f5f/#ef8f86 in
    globals.css and zone-primitive.ts, and `e2e/pixel-truth.mjs` kept the old
    values. That harness computes its edge-detection threshold FROM the colour,
    so a stale copy does not fail the run - it mis-calibrates the probe and the
    run stays green. It sat wrong for eleven days.

    The warning was already written and was not enough, which is the whole
    point of turning it into a test. `pixel-truth.mjs` now reads the tokens off
    the page instead of holding a copy, so it is checked here for the ABSENCE
    of one; the rest are checked for agreement.
    """
    web = TYPES_TS.parents[2]
    css = (web / "src" / "app" / "globals.css").read_text(encoding="utf-8")
    want = {
        name: re.search(rf"--{name}:\s*(#[0-9a-f]{{6}});", css).group(1)
        for name in ("demand", "supply")
    }

    primitive = (
        web / "src" / "components" / "zone-primitive.ts"
    ).read_text(encoding="utf-8")
    block = primitive[primitive.index("const RGB = {") :][:200]
    for name, hex_value in want.items():
        triple = [int(hex_value[i : i + 2], 16) for i in (1, 3, 5)]
        found = re.search(rf"{name}:\s*\[(\d+),\s*(\d+),\s*(\d+)\]", block)
        assert found, f"zone-primitive.ts has no RGB triple for {name}"
        assert [int(g) for g in found.groups()] == triple, (
            f"zone-primitive.ts {name} is {found.groups()}, "
            f"globals.css says {hex_value} = {triple}"
        )

    for relative in (
        "src/components/chart.tsx",
        "src/components/zone-panel.tsx",
    ):
        source = (web / relative).read_text(encoding="utf-8")
        stale = [
            found
            for found in re.findall(r"#[0-9a-f]{6}", source)
            # Only the two roles this pair fills. Any other hex in these files
            # is a different colour with a different owner.
            if found in {"#2ea36f", "#d4574f"}
        ]
        assert not stale, f"{relative} still carries the pre-2026-08-21 pair: {stale}"

    harness = (web / "e2e" / "pixel-truth.mjs").read_text(encoding="utf-8")
    assert 'hex("--demand")' in harness and 'hex("--supply")' in harness, (
        "pixel-truth.mjs must READ the palette off the page; a copy here goes "
        "stale silently because the harness derives its threshold from it"
    )
    assert not re.search(r"RGB\s*=\s*\{\s*demand:\s*\[", harness), (
        "pixel-truth.mjs has a hard-coded RGB table again"
    )
