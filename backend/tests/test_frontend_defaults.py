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
    # Not an assertion. An omitted key falls back to the model's own default,
    # which is correct - but the list is worth printing, because a knob absent
    # from the copy is usually a knob absent from the UI too.
    if omitted:
        print(f"\n{len(omitted)} model defaults the frontend does not send: "
              + ", ".join(sorted(omitted)))


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
