"""The PSP layer draws, and this says it cannot do anything else.

`docs/psp_outcomes.json` graded 48 cells on 1 September 2026 - four pairs, three
bracket widths, both directions, two hypotheses - and not one separated. The
largest |z| in the whole run was 2,10 against a Bonferroni bar of 3,28, and the
run is powered to about 10,6 points of hit rate at those n, so this is a null
with teeth rather than a shrug about sample size.

Both halves of the doctrine's claim were asked, and the second is the one that
matters. H1 asked whether a PSP after an SSMT beats a bar with no PSP on it.
H2 asked whether the SSMT in front of it adds anything at all over a PSP
standing alone. A pass on H1 alone would have said nothing about the sequential
SMT, which is the thing the pairing is supposed to contribute.

So the object is drawn as a reading and barred from the order path by a test
rather than by an intention, the same treatment `tests/test_vortex.py` gives the
3-6-9 dial and for a better-evidenced reason: the dial has no hypothesis, this
one has a measured null.
"""

from __future__ import annotations

import pathlib


def test_no_execution_module_can_read_the_psp():
    """Checked by SOURCE TEXT, not by import graph.

    An import graph check passes the moment someone reads `drawing.psp` off a
    response dict, which needs no import. Any mention of the module, the field
    or the layer id inside these files fails here.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    # The files that decide, size, gate or send. Named one by one rather than
    # globbed, so adding an execution module is a decision someone writes down
    # here instead of quietly falling outside the guard.
    guarded = [
        root / "app" / "ict.py",
        root / "app" / "portfolio.py",
        root / "app" / "advisor.py",
        root / "app" / "confluence.py",
        root / "app" / "plan.py",
        root / "tools" / "execute.py",
        root / "tools" / "autotrade.py",
        root / "tools" / "flatten.py",
    ]
    missing = [p.name for p in guarded if not p.exists()]
    assert not missing, f"guard points at files that are gone: {missing}"

    for path in guarded:
        source = path.read_text(encoding="utf-8")
        for banned in ("psp", "precision_swing", "precision swing"):
            assert banned not in source.lower(), (
                f"{path.name} mentions {banned!r}. A PSP is measured null in "
                "docs/psp_outcomes.json across 48 cells, on both the question "
                "of whether it separates and the question of whether the SSMT "
                "in front of it adds anything, so it must not reach anything "
                "that decides, sizes or sends."
            )


def test_the_checklist_does_not_carry_a_psp_clause():
    """The other door into a decision, and it is a different one.

    `app/checklist.py` scores clauses and `app/ict.py` weighs them; the guard
    above covers the second. This covers the first, because a clause added here
    would reach the gate through the score without any execution module naming
    the layer at all.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    source = (root / "app" / "checklist.py").read_text(encoding="utf-8").lower()
    assert "psp" not in source, (
        "app/checklist.py names psp. A measured-null reading must not become a "
        "clause: the score is read by the gate, so a clause is a decision path."
    )
