"""A language model that may phrase and may look, and may never decide.

WHAT IT IS FOR, AND WHAT IT IS BANNED FROM
Twelve pre-registered directional hypotheses failed in this project. A model asked
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

TWO WAYS TO REACH IT, AND WHY THE SECOND ONE EXISTS
The HTTP backend needs a key. This machine has none, so for a year the vision
job above was a paragraph in a docstring and nothing else - the one component
that could catch an unpredicted defect had never been run. The CLI backend
spawns the Claude Code binary already installed here, which carries its own
login, and that is the whole reason it exists: it makes the untested claim
testable. It is not a better transport. It is slower, chattier, and its cost
shows up on a subscription rather than an invoice.

The CLI cannot be handed an image on the command line, so the PNG is written to
a private temporary directory and the model is pointed at it with a read-only
tool allowance. Nothing variable is ever put in argv: the prompt goes in on
stdin and the system prompt goes in as a file, because the resolved binary on
Windows is `claude.CMD` and argv to a batch file is parsed by cmd.exe before
Python's quoting can protect it. The reply is untrusted text that gets read by
`grounding.check` and printed, and by nothing else.

FAILURE IS SAID
No key and no CLI means the feature refuses and explains itself. That is the
same rule every data provider here follows, for the same reason: silence and a
guess are indistinguishable to the person reading the screen.
"""

from __future__ import annotations

import asyncio
import base64
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

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
- Do not state any number that is not in the data you were given. That includes
  numbers you read off the chart's own axis, and it includes rounding one of the
  given numbers to fewer digits than it has - write it exactly or not at all.
- Use "-" bullets, never a numbered list. Every numeral in your reply is checked
  against the data, and a list marker is a numeral, so "1." would be reported as
  an invented number and bury the findings underneath it.
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


def _cli() -> str | None:
    """Where the Claude Code binary is, or None. Resolved rather than assumed:
    on Windows PATH this is `claude.CMD`, and a bare "claude" handed to
    create_subprocess_exec is not a file that exists."""
    return shutil.which(settings.llm_cli_command)


def available() -> bool:
    return bool(_cli()) if settings.llm_backend == "cli" else bool(settings.llm_key)


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

    Which transport carries it is `settings.llm_backend`. The check runs here,
    once, on whatever came back - a backend that could skip it would be a hole
    in the only guarantee this module has.
    """
    if len(prompt) > settings.llm_max_prompt_chars:
        raise LLMUnavailable(
            f"the prompt is {len(prompt)} characters, over the "
            f"{settings.llm_max_prompt_chars} cap. Send fewer shapes rather "
            f"than trusting the far end to cope."
        )
    speak = _ask_cli if settings.llm_backend == "cli" else _ask_http
    text = await speak(system, prompt, image_png)
    return Reply(text=text, verdict=check(text, payload))


async def _ask_cli(system: str, prompt: str, image_png: bytes | None) -> str:
    """Spawn the local Claude Code binary, headless, and read its one reply.

    Verified against `claude --help` (2.1.222) rather than assumed: `-p` is
    print mode, `--output-format json` wraps the answer in an object whose
    `result` key holds the text and whose `is_error` flag says whether it is an
    answer at all, and `--tools`/`--allowedTools` bound what it may touch.
    `--safe-mode` drops this machine's CLAUDE.md, skills, hooks and plugins, so
    the auditor sees the prompt written here and not a user's global config.

    Two flags carry the security, not a convention: `--tools` is the only tool
    it CAN use and `--allowedTools` is the only one it may use without asking.
    With no image, both are empty - a rephrasing job has no business reading
    files. Never Bash, at either setting, at any time.
    """
    exe = _cli()
    if exe is None:
        raise LLMUnavailable(
            f"No language model key is configured and {settings.llm_cli_command!r} "
            f"is not on PATH, so the advisor cannot phrase or look. Either set "
            f"ZONELAB_LLM_KEY, or install the Claude Code CLI and leave "
            f"ZONELAB_LLM_BACKEND=cli. Everything the engine measures works "
            f"without it - the model only rewords and inspects."
        )

    # A private directory, deleted on the way out, holding the two things that
    # must not travel in argv and the image the CLI has no other way to receive.
    with tempfile.TemporaryDirectory(prefix="zonelab-llm-") as work:
        Path(work, "system.txt").write_text(system, encoding="utf-8")
        if image_png is None:
            tools = ""
        else:
            Path(work, "chart.png").write_bytes(image_png)
            tools = "Read"
            prompt = (
                f"{prompt}\n\nThe chart image is the file chart.png in your "
                f"working directory. Read it, then answer."
            )

        proc = await asyncio.create_subprocess_exec(
            exe, "-p",
            "--output-format", "json",
            "--safe-mode",
            "--system-prompt-file", "system.txt",
            "--tools", tools,
            "--allowedTools", tools,
            cwd=work,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(prompt.encode("utf-8")),
                timeout=settings.llm_cli_timeout_seconds,
            )
        except (asyncio.TimeoutError, TimeoutError) as exc:
            proc.kill()
            await proc.wait()
            raise LLMUnavailable(
                f"the language model CLI did not answer within "
                f"{settings.llm_cli_timeout_seconds}s and was killed"
            ) from exc

    if proc.returncode != 0:
        raise LLMUnavailable(
            f"the language model CLI exited {proc.returncode}: "
            f"{err.decode('utf-8', 'replace').strip()[:200] or 'it said nothing'}"
        )
    try:
        reply = json.loads(out.decode("utf-8", "replace"))
        text = reply["result"]
        failed = reply.get("is_error")
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMUnavailable(
            f"the language model CLI returned an unreadable body: {exc}"
        ) from exc
    if failed or not isinstance(text, str):
        raise LLMUnavailable(f"the language model CLI reported an error: {text!r:.200}")
    return text


async def _ask_http(system: str, prompt: str, image_png: bytes | None) -> str:
    if not settings.llm_key:
        raise LLMUnavailable(
            "No language model key is configured, so the advisor cannot phrase "
            "or look. Set ZONELAB_LLM_KEY, or set ZONELAB_LLM_BACKEND=cli to "
            "use the Claude Code CLI on this machine. Everything the engine "
            "measures works without it - the model only rewords and inspects."
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
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMUnavailable(
            f"the language model returned an unreadable body: {exc}"
        ) from exc


def audit(image_png: bytes, shapes) -> Reply:
    """Show the auditor a chart and the shapes the engine says are on it.

    `shapes` is both the question and the leash: it is what the model is told
    was drawn, and the only source of numbers it is allowed to repeat.
    """
    prompt = (
        "This is the exact list of shapes the engine says it drew on the "
        "chart:\n\n" + json.dumps(shapes, indent=1, default=str)
    )
    return asyncio.run(ask(CHART_AUDITOR, prompt, shapes, image_png=image_png))


def _main(argv: list[str] | None = None) -> int:
    """`python -m app.llm audit --image chart.png --payload shapes.json`

    A module entry point rather than an HTTP route, because the harness that
    needs it is a node script and an endpoint would put an unauthenticated
    model call on the API surface. The grounding check therefore stays on this
    side of the boundary, where it cannot be skipped by a caller.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="python -m app.llm")
    sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("audit", help="report what the model sees on a chart")
    one.add_argument("--image", required=True, help="path to the chart PNG")
    one.add_argument("--payload", required=True, help="path to the shapes JSON")
    args = parser.parse_args(argv)

    try:
        reply = audit(
            Path(args.image).read_bytes(),
            json.loads(Path(args.payload).read_text(encoding="utf-8")),
        )
    except LLMUnavailable as exc:
        # stderr, and a distinct exit code: the caller has to be able to tell
        # "the auditor could not run" from "the auditor ran and said something".
        print(f"the chart auditor refused: {exc}", file=sys.stderr)
        return 3

    print(json.dumps({
        "text": reply.text,
        "grounded": reply.verdict.grounded,
        "reason": reply.verdict.reason(),
        "unsupported": list(reply.verdict.unsupported),
    }, indent=1))
    # Zero even when ungrounded. An ungrounded reply is a model caught inventing
    # a number, which is this module working, not the harness breaking.
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
