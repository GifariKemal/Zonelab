"""The rule that lets a language model near this project at all.

A model asked about a chart will produce a fluent, confident, plausible answer
whether or not anything supports it, and the single most damaging thing it could
produce here is a directional call. Twelve pre-registered hypotheses failed to get
direction out of these drawings; a model that says "this looks bullish" would
undo all of that in one sentence, and it would sound better than the truth.

So the model is not trusted to be right. It is CHECKED.

THE RULE
A model may only speak about numbers the engine computed. Every numeral in its
output must appear in the payload it was given. A number it invented - a price,
a percentage, a probability, a target - is by construction unsupported, because
the engine is the only thing here entitled to produce numbers.

This is a weaker guarantee than "the model is correct", and it is deliberately
the strongest one that can be MECHANICALLY ENFORCED. It cannot stop a model
being wrong in prose. It can stop the specific failure that matters: a
confident, specific, numeric claim with nothing behind it.

WHAT IT DELIBERATELY DOES NOT CATCH
Ordinal words ("higher", "stronger"), hedged prose, and a wrong reading of a
right number. Those need a human or a second model, and pretending otherwise
would be the same overclaiming this module exists to prevent.

AND ONE MORE, WHICH USED TO BE MISSING FROM THIS LIST. The system prompt tells
the model to NEVER calculate, and calls that the rule that fails most often.
Nothing here enforces it. A computed value is caught only when the result happens
not to be in the payload, so most arithmetic is caught by luck rather than by
rule - and arithmetic whose answer lands in `_FREE` is never caught at all:
given entry 102 and stop 100, "the distance is 2 points" passes, because 2 is a
free numeral. Enforcing it properly needs the model to say WHICH field each
numeral came from, which is a different contract than this one. Until then the
gap is written down here rather than implied away, and pinned by
`test_arithmetic_that_lands_in_the_free_set_is_a_known_hole`.

TOLERANCE, AND WHY IT IS NOT A PERCENTAGE
A model rounds: given 0.2483 it writes 0.25, and rejecting that would make the
check useless within a day. The obvious implementation is a relative tolerance,
and it is wrong - 2% of a gold price is 87 points, so an invented 4402.10 sails
past a real 4377.86. That was the first version, and its own test caught it.

The rule that actually holds is: **the model may write FEWER digits, not
DIFFERENT digits.** A numeral passes if some allowed value, rounded to the
precision the model chose to write, equals what it wrote. So 4377.9 matches
4377.86 and 4402.10 matches nothing, at any magnitude, without a tolerance
parameter to tune.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Matches numbers a model actually writes: 4377.86, -0.25, 85,8%, 1 234.5, 2.4R.
# The comma alternative is needed because the advisor writes Indonesian decimals.
_NUMERAL = re.compile(r"-?\d[\d\s.,]*\d|-?\d")

# Numbers so common that requiring them in the payload would reject ordinary
# prose: counts, small ordinals, and the years this project keeps citing.
_FREE = {0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 10.0, 100.0}

EPSILON = 1e-9  # float noise only; the precision rule does the real work


def _decimals(token: str) -> int:
    """How many decimal places the model chose to write.

    NO SEPARATOR MEANS ZERO, and the guard is the whole fix. `re.split` on a
    token with no `.` or `,` returns the token itself, so `_decimals("125")` used
    to answer 3 - as though the model had written three decimal places. That made
    the simplest case of this module's own promise fail: "the model may write
    FEWER digits" was refused for the plainest form of fewer, an integer. Given a
    payload value of 150.4, a reply saying 150 was flagged as an invented number
    and the reader got a red badge on an honest answer.
    """
    flat = token.replace(" ", "")
    if "." not in flat and "," not in flat:
        return 0
    tail = re.split(r"[.,]", flat)[-1]
    return len(tail) if tail.isdigit() and len(tail) <= 6 else 0


@dataclass(frozen=True)
class Verdict:
    """What survived the check, and what did not."""

    grounded: bool
    unsupported: tuple[float, ...]

    def reason(self) -> str:
        if self.grounded:
            return "every number in the reply appears in the data it was given"
        listed = ", ".join(f"{v:g}" for v in self.unsupported)
        return (
            f"the reply contains {len(self.unsupported)} number(s) the engine "
            f"never produced: {listed}. A model may explain the measurements; "
            f"it may not add to them."
        )


def _parse(raw: str) -> float | None:
    """Read a numeral the way a reader would, or give up rather than guess.

    Both decimal conventions appear in this codebase - prices use a point and
    Indonesian prose uses a comma - so a token carrying both is a thousands
    separator plus a decimal, and a token carrying one is ambiguous. Ambiguity
    resolves toward DECIMAL, because reading "85,8" as 858 would invent a
    magnitude, which is the exact failure being guarded against.
    """
    token = raw.replace(" ", "")
    if "." in token and "," in token:
        token = (token.replace(",", "")
                 if token.rindex(".") > token.rindex(",")
                 else token.replace(".", "").replace(",", "."))
    elif "," in token:
        token = token.replace(",", ".", 1) if token.count(",") == 1 else token.replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


def numbers_in(payload) -> set[float]:
    """Every numeric value anywhere in a nested payload, plus its round forms.

    Percentages are added in both conventions because the engine stores 0.858
    and the prose says 85,8 - the same fact wearing two magnitudes, and a check
    that knew only one would reject the correct sentence.
    """
    found: set[float] = set()

    def walk(node) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            value = float(node)
            found.add(value)
            found.add(abs(value))
            if 0.0 < abs(value) <= 1.0:
                found.add(round(value * 100, 6))
        elif isinstance(node, str):
            for match in _NUMERAL.finditer(node):
                parsed = _parse(match.group())
                if parsed is not None:
                    found.add(parsed)
                    found.add(abs(parsed))
        elif isinstance(node, dict):
            for key, item in node.items():
                walk(key)
                walk(item)
        elif isinstance(node, (list, tuple, set)):
            for item in node:
                walk(item)

    walk(payload)
    return found


def check(reply: str, payload) -> Verdict:
    """Does every number in `reply` come from `payload`?"""
    allowed = numbers_in(payload) | _FREE
    unsupported: list[float] = []

    for match in _NUMERAL.finditer(reply):
        token = match.group()
        value = _parse(token)
        if value is None:
            continue
        # Rounded to the precision the MODEL wrote, not to a fixed tolerance.
        # A relative tolerance scales with magnitude and therefore stops
        # protecting exactly where it matters most - on a four-figure price.
        written = abs(value)
        # Exact first, and this line is a bug fix rather than an optimisation.
        # `_decimals` reports 0 places for a tail longer than six digits, so a
        # model quoting a raw float32 price back PERFECTLY - 4476.2998046875 -
        # was compared as round(4476.2998046875, 0) and rejected. The rule this
        # module states is "fewer digits, not different digits", and writing
        # every digit is the trivially allowed case of it. The first real chart
        # audit came back UNUSABLE for quoting nine of its own prices correctly.
        if any(abs(abs(ok) - written) <= EPSILON for ok in allowed):
            continue
        # Then the rounding rule, at the precision the MODEL wrote. A relative
        # tolerance scales with magnitude and therefore stops protecting exactly
        # where it matters most - on a four-figure price.
        places = _decimals(token)
        if any(abs(round(abs(ok), places) - written) <= EPSILON for ok in allowed):
            continue
        unsupported.append(value)

    return Verdict(grounded=not unsupported, unsupported=tuple(unsupported))
