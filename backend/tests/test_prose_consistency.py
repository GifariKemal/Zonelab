"""The claims this codebase repeats about itself must agree with each other.

There is exactly one of these, and it guards the sentence the project's whole
epistemic posture rests on: how many pre-registered directional hypotheses have
failed here. That count appears in more than twenty files, in Python docstrings
and in TypeScript comments, and it is the reason every module can say "this is
not a signal" with a straight face.

An audit found it stated FOUR different ways at once - nine, ten, eleven and
twelve - because each site was written on a different day and none of them knew
about the others. At most one could be right, and a reader had no way to tell
which. That is worse than an uncommented codebase: it makes the project look
like it is quoting a measurement when it is quoting a memory.

This test does not know the right number and deliberately does not hardcode one.
It asserts only that every site says the SAME thing, which is the property that
actually broke, and which a human updating the count will otherwise break again
on their first try.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ("backend/app", "backend/tools", "backend/tests", "frontend/src")
SUFFIXES = {".py", ".ts", ".tsx"}

#: The wrapped docstrings break the phrase across lines, so the gap has to allow
#: a newline and whatever comment furniture starts the next line.
#:
#: BOTH LANGUAGES, and that is not decoration. The English half of this codebase
#: agreed on "twelve" across 35 files while the two Indonesian user-facing sites
#: - `app/advisor.py` and `frontend/src/app/docs/page.tsx` - said "Sembilan",
#: and this guard could not see them because it only read English. The sites a
#: READER actually sees are the Indonesian ones, so the one drift that reached a
#: user was the one drift the test was blind to. The Indonesian numerals still
#: need the English anchor `pre-registered` beside them, for the same reason the
#: English ones do: "sembilan" appears in ordinary prose all over the place, and
#: a bare numeral match would find nine of them per file.
PHRASE = re.compile(
    r"\b(nine|ten|eleven|twelve|sembilan|sepuluh|sebelas|dua belas)\b"
    r"[\s\n#*/]*(?:hipotesis arah )?pre-registered",
    re.I,
)

#: Numerals normalised across languages, so "twelve" and "dua belas" count as
#: agreement rather than as the disagreement this file exists to find.
SAME = {
    "nine": "9",
    "sembilan": "9",
    "ten": "10",
    "sepuluh": "10",
    "eleven": "11",
    "sebelas": "11",
    "twelve": "12",
    "dua belas": "12",
}


def _sources() -> list[Path]:
    return [
        path
        for base in SOURCES
        for path in (ROOT / base).rglob("*")
        if path.suffix in SUFFIXES and "__pycache__" not in path.parts
    ]


def test_the_failed_hypothesis_count_is_stated_identically_everywhere():
    found: dict[str, list[str]] = {}
    for path in _sources():
        text = path.read_text(encoding="utf-8")
        for match in PHRASE.finditer(text):
            word = SAME[match.group(1).lower()]
            found.setdefault(word, []).append(str(path.relative_to(ROOT)))

    assert found, "the phrase vanished entirely, which means this guard stopped guarding"
    assert len(found) == 1, (
        "the failed-hypothesis count disagrees with itself: "
        + "; ".join(
            f"{word} in {len(set(files))} file(s) e.g. {sorted(set(files))[0]}"
            for word, files in sorted(found.items())
        )
    )


def test_the_count_is_repeated_widely_enough_to_be_worth_guarding():
    """If it survives in only one or two places the guard above is vacuous.

    Stated as a floor rather than an exact number so that adding a module does
    not fail the suite - the point is that this is a REPEATED claim, which is
    what makes agreement between the copies matter.
    """
    files = {
        str(path.relative_to(ROOT))
        for path in _sources()
        if PHRASE.search(path.read_text(encoding="utf-8"))
    }
    assert len(files) >= 15, sorted(files)


# ------------------------------- a string that lost its f prefix


#: Route templates and other places where braces are the POINT rather than a lost
#: placeholder. FastAPI path parameters are the whole reason this needs an
#: allowlist: `"/api/snapshots/{snapshot_id}"` is a plain string on purpose and
#: formatting it would be the bug.
BRACES_ON_PURPOSE = re.compile(r"^/api/|^\{[a-z_]+\}$")

#: What a format field looks like: a name, optionally dotted or subscripted, with
#: an optional format spec. Deliberately narrower than "anything in braces" -
#: prose about `{"key": value}` shapes, TypeScript generics and CSS all put braces
#: in strings, and matching those would make this test noise.
FORMAT_FIELD = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_]*(?:[.\[][^{}]*)?(?::[^{}]*)?)\}"
)


def test_no_string_literal_looks_like_an_f_string_that_lost_its_prefix():
    """A silent failure pyflakes cannot see, and one I caused in this repo.

    `pyflakes` reports the opposite mistake - an f-string with no placeholders -
    and a mechanical sweep to fix thirteen of those stripped the `f` from a
    LEGITIMATE f-string four lines away. `tools/blind_gate.py` then printed the
    literal text `SECOND HALF at the blindly chosen {gate:.1f} ATR` into a
    measurement report, where a reader would see braces where a threshold should
    be and have no way to know which number the run had actually chosen.

    Nothing catches this. It compiles, it passes every type check, pyflakes is
    quiet because a plain string with braces is perfectly legal, and the test
    suite is green because no test reads that line of output. Only the printed
    report is wrong, and only a human looking at it would notice.

    Python files only: a TypeScript template literal has different syntax and the
    same mistake there is a backtick, not a prefix.
    """
    import ast

    offenders: list[str] = []
    for path in _sources():
        if path.suffix != ".py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:  # pragma: no cover - a parse failure is its own bug
            offenders.append(f"{path.name} does not parse: {exc}")
            continue
        # DOCSTRINGS ARE PROSE AND ARE SKIPPED BY IDENTITY, not by length. One in
        # this repo reads `"""{multiple: price} for the standard range..."""` -
        # it is describing a dict shape, which is exactly the thing this pattern
        # is looking for, and no length rule separates the two. Collected first so
        # the walk below can recognise them.
        prose = {
            id(ast.get_docstring(scope, clean=False) and scope.body[0].value)
            for scope in ast.walk(tree)
            if isinstance(
                scope, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            )
            and scope.body
            and isinstance(scope.body[0], ast.Expr)
            and isinstance(scope.body[0].value, ast.Constant)
        }
        for node in ast.walk(tree):
            if id(node) in prose:
                continue
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            text = node.value
            # Docstrings and long prose legitimately discuss braces; a lost
            # placeholder lives in a short message.
            if len(text) > 200 or BRACES_ON_PURPOSE.search(text):
                continue
            field = FORMAT_FIELD.search(text)
            if field:
                offenders.append(
                    f"{path.relative_to(ROOT)}:{node.lineno} has {field.group(0)} "
                    f"in a plain string: {text[:60]!r}"
                )

    assert not offenders, (
        "plain string literals containing what looks like a format field, so an "
        "f prefix was probably lost:\n  " + "\n  ".join(offenders)
    )
