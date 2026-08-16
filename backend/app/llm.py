"""A language model that may phrase and may look, and may never decide.

WHAT IT IS FOR, AND WHAT IT IS BANNED FROM
Ten pre-registered directional hypotheses failed in this project. A model asked
"is this bullish" will answer, fluently and immediately, and its answer will be
better written than the truth. So the model is given jobs where being wrong is
cheap and checkable, and is structurally prevented from the one job where being
wrong is expensive:

    ALLOWED   phrasing findings the engine already computed
              reading a CHART IMAGE and reporting what it sees
              answering questions out of the project's own documents
              proposing hypotheses for the measurement harness to judge

    BANNED    deciding direction, rating a zone, producing any number

The ban is not a prompt instruction, because a prompt is a request and this
needs a guarantee. Every reply passes `grounding.check`, which rejects any
numeral that does not appear in the payload the model was given. A model cannot
smuggle a price target past it, because the price target is a number and the
number is not in the data.

WHY VISION EARNS ITS PLACE
Everything else here could be done without a model. Vision could not. This
project audits its drawing by measurement - pixel positions against the price
scale, box edges against base candles, ink coverage, collisions - and every one
of those checks had to be THOUGHT OF before it could be written. A model looking
at the rendered chart is the only component that can report a defect nobody
predicted. It is a second pair of eyes with no stake in the result, and its
output is a claim to be verified, never a measurement.

FAILURE IS SAID
No key means the feature refuses and explains itself. That is the same rule
every data provider here follows, for the same reason: silence and a guess are
indistinguishable to the person reading the screen.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx

from .config import settings
from .grounding import Verdict, check

CHART_AUDITOR = """You are auditing a chart drawing for defects.

You will be shown a chart image and the exact list of shapes the engine says it
drew on it. Your job is to report DISAGREEMENTS between the picture and the
list, and anything a reader would find misleading.

Look for: boxes whose edges do not sit where the list says; shapes that overlap
so heavily the chart is unreadable; labels that collide or are cut off; a zone
drawn over a region with no candles; anything that looks wrong.

Rules you must follow:
- Report only what you can SEE. If you cannot tell, say you cannot tell.
- Do not state any number that is not in the data you were given.
- Do not comment on whether the market will rise or fall. You have no basis for
  that and neither does the engine.
"""

EXPLAINER = """You rephrase measurements for a reader who is not a quant.

You will be given findings the engine computed. Restate them plainly in
Indonesian. You may simplify wording. You may NOT add numbers, add conclusions,
or say which way price will go - the engine has measured that it cannot know,
and saying otherwise would be inventing.
"""


class LLMUnavailable(RuntimeError):
    """No key, or upstream refused. Carries a message meant for the user."""


@dataclass(frozen=True)
class Reply:
    """What the model said, and whether it was allowed to say it."""

    text: str
    verdict: Verdict

    @property
    def usable(self) -> bool:
        return self.verdict.grounded


def available() -> bool:
    return bool(settings.llm_key)


def _content(prompt: str, image_png: bytes | None) -> list[dict] | str:
    if image_png is None:
        return prompt
    encoded = base64.b64encode(image_png).decode()
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url",
         "image_url": {"url": f"data:image/png;base64,{encoded}"}},
    ]


async def ask(
    system: str, prompt: str, payload, image_png: bytes | None = None
) -> Reply:
    """One call, checked before it is returned.

    `payload` is both what the model is told and what it is held to: every
    number in the reply must appear in it. Passing a payload that does not
    contain the facts being discussed would make the check vacuous, so the
    caller must pass the real computed values, not a summary of them.
    """
    if not available():
        raise LLMUnavailable(
            "No language model key is configured, so the advisor cannot phrase "
            "or look. Set ZONELAB_LLM_KEY. Everything the engine measures works "
            "without it - the model only rewords and inspects."
        )

    body = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _content(prompt, image_png)},
        ],
        "temperature": 0.2,
    }
    try:
        async with httpx.AsyncClient(
            timeout=settings.llm_timeout_seconds,
            headers={"Authorization": f"Bearer {settings.llm_key}"},
        ) as client:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions", json=body
            )
    except httpx.HTTPError as exc:
        # The class name matters: httpx.ConnectTimeout stringifies to the empty
        # string, and a message promising a cause then giving none is the same
        # swallowed failure this project refuses elsewhere.
        why = str(exc) or type(exc).__name__
        raise LLMUnavailable(f"could not reach the language model: {why}") from exc

    if response.status_code != 200:
        raise LLMUnavailable(
            f"the language model returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )
    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMUnavailable(
            f"the language model returned an unreadable body: {exc}"
        ) from exc

    return Reply(text=text, verdict=check(text, payload))
