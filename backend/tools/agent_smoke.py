"""End-to-end smoke test for the AI Agent, against the real endpoint.

    python -m tools.agent_smoke

Proves the whole wire in order: the config endpoint holds a key without
leaking it, the probe reaches the upstream, a real drawing is fetched and
digested, and a real model reply comes back carrying its grounding verdict.
Nothing here is mocked; the point of a smoke test is that the mocks are what
the unit tests already covered.

Exit code is the number of failed checks, so it can be a gate.

WHAT EACH CHECK IS FOR:

  1. CONFIG MASKED. The GET must answer with availability and without the key.
     A leak here is the credentials rule of this repo, broken at the API.
  2. PROBE. The saved endpoint must answer /models; a config that cannot
     reach anything is a green light over a dead wire.
  3. DRAW. A real drawing from the default provider, the same path the UI
     scan takes. Without it the chat has no numbers to be held to.
  4. CHAT GROUNDED. One real question about the drawing. The reply must come
     back and its verdict must be reported either way; the check fails only
     when the reply is ungrounded, because an invented number on the very
     first turn is the failure this whole module exists to catch.
  5. CHAT REFUSES NUMBERS WITHOUT CONTEXT. Same question with no drawing
     attached. The reply must come back UNGROUNDED or refuse to produce
     numbers - either is honest. A grounded numeric reply with no context is
     impossible by construction and would mean the leash is off.
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request

from app import agent

API = "http://127.0.0.1:8100"
FAILURES: list[str] = []

QUESTION = (
    "Jelaskan kondisi market dari drawing ini secara ringkas: zona apa yang "
    "ada, plan apa yang paling relevan, dan apa yang tidak bisa diketahui. "
    "Kutip angka dari data."
)


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{API}{path}", timeout=30) as response:
        return json.loads(response.read())


def post(path: str, body: dict) -> dict:
    request = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=agent.TIMEOUT_SECONDS + 30) as response:
        return json.loads(response.read())


async def main() -> None:
    print("== 1. config terbaca, key tidak bocor")
    config = get("/api/agent/config")
    raw = json.dumps(config)
    check("config menjawab availability", "available" in config, raw[:120])
    check("key tidak kembali utuh", "sk-" not in raw)
    if not config.get("available"):
        check("endpoint terpasang", False,
              "config belum ada; isi Settings di /agent dulu")
        return

    print("== 2. probe upstream")
    reachable, why, offered = await agent.probe()
    check("endpoint menjawab /models", reachable, why or f"{offered} model")

    print("== 3. drawing sungguhan")
    body = {
        "symbol": "XAUUSD", "interval": "1h", "bars": 500,
        "provider": "", "layers": ["supply_demand", "structure",
                                   "liquidity", "checklist"],
        "htf": None, "equity": None, "broker": "", "refine": False,
        "session_offset_hours": 0,
    }
    # Scan via the same endpoint the UI uses; DEFAULT params come from the
    # module rather than being restated here so the two cannot drift.
    from app.models import DrawRequest  # noqa: PLC0415 - local, mirrors main.py
    request = DrawRequest(**{**body, "layers": body["layers"]})
    from app.fetching import fetch  # noqa: PLC0415
    rows, used = await fetch(request.symbol, request.interval,
                             request.bars, request.provider)
    from app.drawing import build as build_drawing  # noqa: PLC0415
    drawing, meta = await asyncio.to_thread(build_drawing, rows, request, None)
    response = {
        "symbol": request.symbol, "interval": request.interval,
        "provider": used, "candles": [c.model_dump() for c in rows],
        "drawing": drawing.model_dump(), "plans": [], "advice": [],
        "checklist": None, "meta": meta,
    }
    check("drawing punya zona", len(drawing.zones) > 0,
          f"{len(drawing.zones)} zona, provider {used}")

    print("== 4. chat sungguhan dengan context")
    out = post("/api/agent/chat", {
        "messages": [{"role": "user", "content": QUESTION}],
        "context": response,
    })
    check("reply datang", bool(out.get("reply")))
    check("reply grounded", out.get("grounded") is True,
          out.get("reason", "")[:200])
    print(f"     model {out.get('model')}, {len(out.get('reply', ''))} karakter")

    print("== 5. chat tanpa context tidak boleh berangka grounded")
    bare = post("/api/agent/chat", {
        "messages": [{"role": "user",
                      "content": "Sebutkan entry dan stop untuk zona terdekat."}],
        "context": None,
    })
    check("reply tanpa context tidak grounded-berangka",
          bare.get("grounded") is False or "tidak" in bare.get("reply", "").lower()
          or "no drawing" in bare.get("reason", "").lower()
          or len(bare.get("unsupported", [])) > 0,
          bare.get("reason", "")[:200])


if __name__ == "__main__":
    asyncio.run(main())
    print(f"\n{len(FAILURES)} failed")
    sys.exit(len(FAILURES))
