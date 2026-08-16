"""The rule that lets a language model near this project at all.

A model asked about a chart will produce a fluent, confident, plausible answer
whether or not anything supports it, and the single most damaging thing it could
produce here is a directional call. Ten pre-registered hypotheses failed to get
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
    """How many decimal places the model chose to write."""
    tail = re.split(r"[.,]", token.replace(" ", ""))[-1]
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
        places = _decimals(token)
        written = abs(value)
        if any(abs(round(abs(ok), places) - written) <= EPSILON for ok in allowed):
            continue
        unsupported.append(value)

    return Verdict(grounded=not unsupported, unsupported=tuple(unsupported))
