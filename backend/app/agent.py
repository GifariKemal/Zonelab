"""The AI Agent: a language model seated above the engine, on a leash.

WHAT THIS MODULE IS. A chat surface where the model discusses the CURRENT
drawing: zones, plans, advice, checklist, overlays. The frontend sends the
`/api/draw` response verbatim as context, this module digests it to a compact
payload, the model answers, and `grounding.check` holds every numeral in the
answer to that payload. The digest is therefore both what the model is told
and what it is allowed to say, the same contract `llm.ask` enforces for the
one-shot jobs.

WHY A SEPARATE MODULE RATHER THAN EXTENDING `llm.py`. The chat needs three
things the one-shot `ask` does not have: a runtime-editable endpoint (the
operator picks base_url, key and model from the UI, and `settings` is frozen
at import), multi-turn history, and a config file that must never be
committed. The grounding rule itself is imported, not rewritten.

THE HONESTY CONTRACT, AND WHERE EACH HALF LIVES. The system prompt below
states the findings (twelve failed directional hypotheses, first-touch
validation, cohort rates that are not probabilities). `grounding.check`
enforces the numeric half mechanically. Neither alone is enough: a prompt is
a request, and a check without a prompt that explains it produces replies
that fail for reasons the model was never told about.

CONFIG LIVES IN backend/.agent.json. Same pattern as `.autotrade.json`:
gitignored, and a missing or corrupt file means the feature is OFF and says
so, never a guess. The key is returned masked - the GET exists so the UI can
show what is configured, and a read-back of the secret would make the mask
theatre.

NO TOOL CALLS, EVER. The model reads the context it was handed and answers.
It cannot call the API, fetch candles, or place anything. Giving a model the
power to invoke endpoints would put a new, prompt-shaped API surface on the
server, and the one thing this project's own history says to fear is a
confident answer with nothing behind it.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from .config import settings
from .grounding import check
from .llm import LLMUnavailable

CONFIG_PATH = Path(__file__).resolve().parent.parent / ".agent.json"

DEFAULTS: dict[str, Any] = {
    "base_url": "",
    "api_key": "",
    "model": "",
    "temperature": 0.2,
}

#: A reasoning model drafting a real analysis routinely takes longer than a
#: one-shot rephrase; measured against the bandelbanget proxy, glm-5.2 spent
#: its first seconds on reasoning_content before any visible token. Two
#: minutes is the ceiling, not the expectation.
TIMEOUT_SECONDS = 120.0

#: Concurrent chats are pure I/O, so the GIL argument for `_BUILDS` in main
#: does not apply. The bound exists for the upstream's sake: an operator
#: leaning on the enter key should not open eight parallel metered calls.
#: Excess requests queue in the handler rather than being refused.
_CHATS = asyncio.Semaphore(4)

#: How much of each list survives into the payload. The zones cap keeps the
#: newest, because a question about "zona terdekat" is about the tail. The
#: overlays cap exists so one layer left at max_zones_per_side 0 (the
#: measurement setting, see memory zonelab-display-cap-hazard) cannot make
#: the payload unsendable on its own.
MAX_ZONES = 40
MAX_OVERLAYS = 20

#: The chat payload ceiling. NOT `settings.llm_max_prompt_chars`: that 40000
#: was written for a subprocess and a one-shot rephrase, and a real scan
#: (supply_demand + structure + liquidity + checklist on MT5, six zones with
#: plans and advice) measured 40757 characters of digest alone - the shipped
#: scan of the shipped page was already over it. A chat context of 100k
#: characters is about 25k tokens, small for the endpoints this feature
#: targets, and still a refusal rather than a hope for anything larger.
MAX_PROMPT_CHARS = 100_000

#: The fields of a zone a discussion can use. Everything else (factors,
#: anatomy, refinement) is display provenance, and quoting it would bloat
#: the payload the grounding check then has to carry.
_ZONE_FIELDS = (
    "id", "kind", "side", "state", "timeframe", "top", "bottom", "proximal",
    "distal", "departure_atr", "profit_zone_rr", "curve", "curve_favourable",
    "touches", "settled", "confirmed", "nested_in", "inverted_at", "note",
)

#: Overlay lists on the drawing, capped per MAX_OVERLAYS. Their own fields
#: are already the distilled reading (labels, prices, times); compacting them
#: further would drop numbers the model may legitimately quote.
_OVERLAY_KEYS = (
    "swings", "structure", "quarters", "true_opens", "dfr", "ssmt", "gaps",
    "news", "tier_horizons", "gap_stacks", "event_horizons", "cisd", "pools",
    "levels", "projections",
)

SYSTEM = """You are the Zonelab AI Agent: an analyst seated above a technical
drawing engine, discussing its output with the trader who owns the account.

When a `brief` field is present it is the Zonelab brief for one symbol,
rendered by `tools/brief`: every layer switched on, the display cap off,
several timeframes, and the seventeen ICT clauses per candidate WITH the
source of each clause. Read the CAUTION block at its top before quoting any
number from it. `source` is load bearing: `doctrine` means this project has
no number for that clause, `measured` means it does. Thirteen of the
seventeen are `doctrine`. Say which kind you are quoting whenever a clause
carries your argument.

The data you are given is a digest of ONE /api/draw response: zones drawn by
detectors (supply_demand, fvg, order_block, ifvg, breaker), a trade plan per
zone (entry, stop, target, lots, risk, costs), the engine's own advice, an
ICT checklist, and overlays (structure, ssmt, dfr, liquidity, gaps, news).
When the scan included them, a `triads` list is also present: for each POSKO
triad, the Truth Asset (which member is consolidating, by consolidation
score) and the Pearson correlation of each partner to the base, on a full and
a recent window, plus `sign_changed` for whether the sign flipped between
them. Every number there was computed by the engine.

FINDINGS YOU MUST NOT CONTRADICT:
- Twelve pre-registered directional hypotheses failed; the last two failed
  opposite to their own doctrine. `direction_evidence` is always None. A
  directional lean you give is therefore YOUR synthesis of the measured
  signals, never an engine reading. When asked "buy or sell?", give the lean
  and the signals it rests on, and state plainly that it is a judgment, not
  a measurement.
- The Truth Asset is the consolidating member (lowest consolidation score),
  not a direction and not a pick. It says which price action is clearer. A
  correlation is Pearson on log returns; `sign_changed` reports whether the
  sign flipped between the full and recent windows.
- The departure gate (>= 2 ATR) is a FIRST-TOUCH result. A zone already
  touched carries no validated filter (measured -0.2 to -4.3 points on later
  touches).
- departure_held_rate and age_held_rate are COHORT survival rates, not this
  trade's probability, they exclude costs, and they must not be multiplied
  (the factors are entangled).
- Costs decide whether an edge survives: quote cost_share_of_reward and the
  warnings when a plan carries them. Exness charges 200 USD per lot per night
  on XAUUSD held past 21:00 UTC, and the daemon's validated exit is flat at
  the rollover.
- formation_score ranks BACKWARDS (AUC 0.464). Never use it to rank
  opportunity.

RULES FOR EVERY REPLY:
- Every numeral you write must appear in the data you were given. Numbers
  you invent are mechanically detected and the whole reply is flagged. If the
  user quotes a number that is not in the data, say so instead of adopting it.
- NEVER calculate. No sums, differences, counts, averages, percentages or
  unit conversions. If an answer needs arithmetic the engine did not do,
  quote the raw fields and let the reader subtract. This is the rule that
  fails most often: writing "jarak 125 poin" from a stop and entry you were
  given IS inventing a number.
- A direction lean (bullish / bearish / no lean) plus a confidence LEVEL
  (rendah / sedang / tinggi) is allowed, but only as a synthesis of the
  measured signals in the data: `bias` (per-timeframe bullish/bearish and
  whether the timeframes agree), structure (BOS = continuation, CHoCH =
  reversal, MSS = sweep), the premium/discount position, SSMT divergences,
  zone positioning, and the triad correlation and Truth Asset. Name the
  signals on each side - a lean with no named signal is not a synthesis. Say
  it is your judgment, not an engine reading, and that twelve pre-registered
  directional hypotheses failed. You may still never invent a price, target,
  entry or stop.
- If a plan field is null, the honest reading is stated in the plan itself:
  `lots: null` means nobody checked the sizing, a missing target means no
  live opposing zone ahead.
- Answer in Indonesian, technical terms in English (zone, gate, overlay,
  departure, first touch, entry, stop, target, lots).
- When asked for an order checklist, build it from the plan fields: entry,
  stop, target, lots, realised risk, warnings, the gates that apply
  (departure >= 2 ATR, placeable, blockers, first touch), and close with a
  line stating what cannot be known (whether price arrives).
- Say when you do not know. A short honest answer beats a long invented one.
"""


# -- config ----------------------------------------------------------------


def read_config() -> dict[str, Any]:
    """The saved endpoint settings, or DEFAULTS when the file is absent or
    corrupt. Never raises: a broken config means off, not down."""
    raw: dict[str, Any] = {}
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
    cfg = dict(DEFAULTS)
    for key in cfg:
        value = raw.get(key)
        if value is not None:
            cfg[key] = value
    return cfg


# -- the endpoint guard ----------------------------------------------------

#: Environment switch that permits a private, loopback or link-local endpoint.
#: AN ENVIRONMENT VARIABLE AND NOT A CONFIG FIELD, and that is the mechanism
#: rather than a style choice: `.agent.json` is written by
#: `POST /api/agent/config`, so an opt-in stored there could be flipped by the
#: same unauthenticated request the guard exists to constrain, and a lock whose
#: key sits inside it is not a lock. This one needs the launcher or the shell,
#: which is a different privilege from reaching the port.
ALLOW_PRIVATE_ENV = "ZONELAB_AGENT_ALLOW_PRIVATE_ENDPOINTS"

_TRUE = {"1", "true", "yes", "on"}


def private_endpoints_allowed() -> bool:
    """Whether the operator has opted in to non-public endpoints.

    Read per call rather than captured at import, so the value can change
    without a restart and so a test can set it.
    """
    return os.environ.get(ALLOW_PRIVATE_ENV, "").strip().lower() in _TRUE


def _addresses(host: str) -> list:
    """Every address `host` currently resolves to, or [] when it resolves to none.

    A literal is returned without asking DNS. A name that does not resolve
    returns [], which the caller treats as allowed - see `vet_base_url`.
    """
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return []
    out = []
    for info in infos:
        try:
            out.append(ipaddress.ip_address(info[4][0]))
        except ValueError:  # pragma: no cover - getaddrinfo returned a non-address
            continue
    return out


def _origin(url: str) -> tuple:
    """Scheme, lowercased host and port - what "the same endpoint" means here."""
    parsed = urlsplit(url)
    try:
        port = parsed.port
    except ValueError:  # pragma: no cover - a bad port is refused by vet_base_url
        port = None
    return parsed.scheme, (parsed.hostname or "").lower(), port


def vet_base_url(url: str) -> None:
    """Refuse an endpoint this server must not be talked into calling.

    THE THREAT, STATED PLAINLY. `POST /api/agent/config` takes a base URL and
    the server then sends `Authorization: Bearer <api_key>` to whatever host
    that URL names. The API has no authentication of its own - no login, no
    token, no per-request secret anywhere in `app/main.py` - so the only thing
    between that field and an arbitrary outbound AUTHENTICATED request was
    `startswith(("http://", "https://"))`. Two distinct attacks fit through it:

      1. CREDENTIAL EXFILTRATION. `save_config` keeps the stored key when the
         posted one is blank, which is correct for a model change and was
         catastrophic here: a request carrying ONLY `base_url` re-pointed the
         endpoint and left the operator's real key in place, and the same
         handler then called `probe()`, which issued `GET <attacker>/models`
         with that key in the header. One request, no knowledge of the key
         needed, key delivered. Closed twice over: this function refuses the
         hosts worth pointing at, and `save_config` now DROPS the stored key
         whenever the host changes, so a rebind cannot carry the old
         credential to a new destination.

      2. SSRF WITH REFLECTION. `models()` and `_complete()` both put the
         upstream's body into their exception text (`response.text[:200]`),
         and that text reaches the caller as the 503 detail. An endpoint set to
         `http://169.254.169.254/latest/meta-data`, or to any service on the
         host's own network, is therefore a read primitive with the answer
         echoed back. Cloud metadata lives on link-local, a service mesh lives
         on private space, and this process is the thing on the box with routes
         to both.

    WHAT IS REFUSED: any host resolving to an address `ipaddress` does not call
    global - loopback, RFC1918 private, link-local (169.254/16 and fe80::,
    where every cloud metadata service lives), carrier-grade NAT, multicast,
    reserved and unspecified. ALL of a name's addresses are checked and not the
    first, because a name with one public and one private record would
    otherwise pass on the public one and connect on either.

    WHAT IS NOT REFUSED, and why there is no allowlist: the feature IS pointing
    this at an endpoint of the operator's choosing. `settings.llm_base_url`
    defaults to bigmodel.cn, the tests use x.example, and the next endpoint is
    whichever OpenAI-compatible vendor is worth paying this month. A hardcoded
    list would mean filing a pull request to change model provider, which is
    not a security control, it is a broken feature. So the rule is about the
    ADDRESS SPACE rather than the vendor: any public host, no local one, and a
    local one on purpose via `ALLOW_PRIVATE_ENV` - which is the legitimate
    case, an Ollama or LM Studio on 127.0.0.1 with no key worth stealing.

    TWO CEILINGS, NAMED RATHER THAN PAPERED OVER, because this project keeps a
    list of instruments that reported green while the thing they measured had
    crashed:

      - DNS REBINDING IS NOT CLOSED. This resolves the name and `httpx`
        resolves it again when it connects; between those two the answer can
        change. Closing it means pinning the vetted address into the transport,
        which is a custom connector rather than a validator. What IS closed is
        the whole class that needs no DNS control at all, which is every shape
        above.
      - A NAME THAT DOES NOT RESOLVE IS ALLOWED, deliberately. The endpoint may
        legitimately be briefly down, and `agent_config_save` already promises
        the save stands in that case. It is not a hole: a name with no address
        cannot be connected to either, so the request that matters still fails,
        loudly, as `reachable: false`.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"base_url must start with http:// or https://, got {url!r}"
        )
    host = parsed.hostname
    if not host:
        raise ValueError(f"base_url names no host: {url!r}")
    if private_endpoints_allowed():
        return
    # ponytail: blocking getaddrinfo on the event loop. One lookup per save, on
    # a handler that goes on to make a full HTTP round trip anyway; move it to a
    # thread if saves ever stop being an operator typing into a form.
    for address in _addresses(host):
        if not address.is_global:
            raise ValueError(
                f"base_url {url!r} resolves to {address}, which is not a public "
                "address. This server would send your API key there, and a "
                "loopback, private or link-local target is how a credential "
                "leaves a machine and how cloud metadata gets read. Set "
                f"{ALLOW_PRIVATE_ENV}=1 in the environment if you meant it - a "
                "local Ollama or LM Studio is the case that is worth it."
            )


def save_config(
    base_url: str = "", api_key: str = "", model: str = "",
    temperature: float | None = None,
) -> dict[str, Any]:
    """Merge the given fields into the config file and return the reading.

    An empty `api_key` KEEPS the stored one for the SAME endpoint: the UI reads
    the key masked and so cannot hand it back, and a model change must not
    silently erase the credential it needs. A bad URL is refused rather than
    stored, because the failure would otherwise surface only at the first chat,
    far from the field that caused it.

    A KEY IS BOUND TO THE HOST IT WAS ISSUED FOR, and moving the host without
    supplying a new key DROPS it. That is the second half of the exfiltration
    fix in `vet_base_url`, and it is the half that does not depend on the
    attacker picking a blockable address: keeping-the-blank-key is exactly what
    turned "change one field" into "and take the credential with you", because
    the handler probes the new endpoint immediately with whatever key the file
    holds. A credential issued by vendor A is meaningless at vendor B anyway,
    so nothing legitimate is lost - the operator was always going to paste a
    new one. `available` then reads False and the UI asks for the key, which is
    the state this used to hide.

    Scheme, host AND port are compared, so `http://x` to `https://x` and
    `localhost:11434` to `localhost:1234` both count as a move. The host is
    case-folded and the path is not, because that is what those two are.
    """
    base_url = base_url.strip().rstrip("/")
    if base_url:
        vet_base_url(base_url)
    current = read_config()
    moved = bool(base_url) and _origin(base_url) != _origin(str(current["base_url"]))
    if base_url:
        current["base_url"] = base_url
    if api_key:
        current["api_key"] = api_key
    elif moved:
        current["api_key"] = ""
    if model:
        current["model"] = model
    if temperature is not None:
        current["temperature"] = max(0.0, min(float(temperature), 1.0))
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(current, indent=1, sort_keys=True), encoding="utf-8"
    )
    return current


def masked() -> dict[str, Any]:
    """What the UI may see: everything but the key, which becomes a hint.

    `base_url` IS RETURNED IN FULL AND UNMASKED, which is the point rather than
    an oversight. It is the destination the stored credential is sent to, and a
    secret whose destination is hidden is a secret nobody can audit: the only
    way to notice this endpoint has been re-pointed is to be able to read where
    it points. The key itself stays a four-character hint, because reading the
    secret back would make the mask theatre.

    `allow_private_endpoints` reports whether the `vet_base_url` guard is
    switched off in this process's environment. A control that can be disabled
    invisibly is a control nobody can rely on, and this project's own list of
    incidents is mostly instruments reporting green over something dead.
    """
    cfg = read_config()
    key = str(cfg["api_key"])
    return {
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "temperature": cfg["temperature"],
        "api_key": "",
        "api_key_hint": f"...{key[-4:]}" if len(key) >= 8 else "",
        "available": bool(cfg["base_url"] and key and cfg["model"]),
        "allow_private_endpoints": private_endpoints_allowed(),
    }


# -- upstream --------------------------------------------------------------


async def models() -> list[str]:
    """The model ids the configured endpoint offers, for the UI picker."""
    cfg = read_config()
    if not (cfg["base_url"] and cfg["api_key"]):
        raise LLMUnavailable(
            "No endpoint configured. Set base URL and API key first."
        )
    try:
        async with httpx.AsyncClient(
            timeout=settings.http_timeout_seconds,
            headers={"Authorization": f"Bearer {cfg['api_key']}"},
        ) as client:
            response = await client.get(f"{cfg['base_url']}/models")
    except httpx.HTTPError as exc:
        # httpx.ConnectTimeout stringifies empty; name the class instead.
        raise LLMUnavailable(
            f"could not reach the endpoint: {str(exc) or type(exc).__name__}"
        ) from exc
    if response.status_code != 200:
        raise LLMUnavailable(
            f"the endpoint returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )
    try:
        return sorted(
            item["id"]
            for item in response.json()["data"]
            if item.get("id") and item.get("enabled", True)
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LLMUnavailable(
            f"the endpoint returned an unreadable model list: {exc}"
        ) from exc


async def _complete(
    cfg: dict[str, Any], messages: list[dict[str, Any]]
) -> str:
    """One round trip to the configured OpenAI-compatible endpoint."""
    body = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": cfg["temperature"],
    }
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT_SECONDS,
            headers={"Authorization": f"Bearer {cfg['api_key']}"},
        ) as client:
            response = await client.post(
                f"{cfg['base_url']}/chat/completions", json=body
            )
    except httpx.HTTPError as exc:
        raise LLMUnavailable(
            f"could not reach the endpoint: {str(exc) or type(exc).__name__}"
        ) from exc
    if response.status_code != 200:
        raise LLMUnavailable(
            f"the endpoint returned HTTP {response.status_code}: "
            f"{response.text[:200]}"
        )
    try:
        text = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise LLMUnavailable(
            f"the endpoint returned an unreadable body: {exc}"
        ) from exc
    if not isinstance(text, str) or not text.strip():
        # Reasoning models can exhaust the budget on reasoning_content and
        # return an empty content. Reported, not retried: a silent retry
        # doubles a metered call to produce the same emptiness.
        raise LLMUnavailable(
            "the model returned an empty reply (it may have spent its whole "
            "budget reasoning). Try again or pick a non-reasoning model."
        )
    return text


async def probe() -> tuple[bool, str | None, int]:
    """Is the configured endpoint answering, in its own words if not.

    Returns (reachable, error, model count). The count is returned rather
    than the list because the picker fetches the full list itself; this call
    only needs to prove the door opens and say how wide.
    """
    try:
        return True, None, len(await models())
    except LLMUnavailable as exc:
        return False, str(exc), 0


# -- digest ----------------------------------------------------------------


def digest(response: dict[str, Any]) -> dict[str, Any]:
    """The draw response as the model sees it, and as it is held to.

    Candles are dropped except the last: the model discusses zones and plans,
    not the tape, and 500 candles would crowd out everything else under the
    prompt cap. `bars` stays so "how much history" is still an answerable
    question with a quotable number.
    """
    drawing = response.get("drawing") or {}
    candles = response.get("candles") or []
    zones = [
        {k: zone[k] for k in _ZONE_FIELDS if k in zone}
        for zone in drawing.get("zones") or []
    ]
    overlays = {
        key: (drawing.get(key) or [])[:MAX_OVERLAYS]
        for key in _OVERLAY_KEYS
        if drawing.get(key)
    }
    # Advice notes carry a `learn` anchor for the UI's doc links; to a model
    # it is a dead reference to a page it cannot open, dropped here rather
    # than paid for on every turn.
    advice = []
    for entry in (response.get("advice") or [])[:MAX_ZONES]:
        notes = [
            {k: note[k] for k in ("topic", "text") if k in note}
            for note in entry.get("notes") or []
        ]
        advice.append({"zone_id": entry.get("zone_id"), "notes": notes})
    return {
        "symbol": response.get("symbol"),
        "interval": response.get("interval"),
        "provider": response.get("provider"),
        "bars": len(candles),
        "last_candle": dict(candles[-1]) if candles else None,
        "zones": zones[-MAX_ZONES:],
        "plans": (response.get("plans") or [])[:MAX_ZONES],
        "advice": advice,
        "checklist": response.get("checklist"),
        "overlays": overlays,
        "meta": response.get("meta") or {},
    }


# -- chat ------------------------------------------------------------------


def _history(messages: object) -> list[dict[str, str]]:
    """Validate and normalise the client's history. Only user and assistant
    turns: a client-supplied system message would be a prompt injection
    surface, since it rides ABOVE the constitution rather than under it."""
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list of turns")
    history: list[dict[str, str]] = []
    for turn in messages:
        if not isinstance(turn, dict):
            raise ValueError("each message must be an object")
        role, content = turn.get("role"), turn.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise ValueError(
                "each message needs role 'user' or 'assistant' and string "
                "content"
            )
        if content.strip():
            history.append({"role": role, "content": content})
    if not history:
        raise ValueError("no usable turns in messages")
    return history


async def chat(messages: object, context: object) -> dict[str, Any]:
    """One assistant turn over the current drawing, checked before return."""
    cfg = read_config()
    if not (cfg["base_url"] and cfg["api_key"] and cfg["model"]):
        raise LLMUnavailable(
            "The AI Agent has no endpoint configured. Open Settings on the "
            "/agent page, set base URL, API key and model, then Save."
        )
    history = _history(messages)
    if isinstance(context, dict):
        # The frontend now sends `{draw, triads}`; a bare draw response is still
        # accepted so older clients and the tests keep working unchanged.
        draw = context["draw"] if "draw" in context else context
        payload = digest(draw if isinstance(draw, dict) else {})
        triads = context.get("triads")
        if isinstance(triads, list) and triads:
            payload["triads"] = triads
        # BRIEF, DAN KENAPA IA MASUK SEBAGAI TEKS. `grounding.numbers_in`
        # berjalan di string juga, jadi setiap angka di dalam BRIEF.md ikut
        # menjadi angka yang boleh dikutip. Kalau brief masuk lewat jalur lain
        # yang tidak ikut ke `payload`, model membaca angka yang kemudian
        # ditolak grounding sebagai karangan, dan kegagalannya akan terbaca
        # seperti model yang berhalusinasi padahal ia mengutip dengan benar.
        #
        # `digest` sengaja TIDAK menyentuhnya. Digest memampatkan satu response
        # /api/draw; brief adalah bacaan lintas timeframe yang sudah dipadatkan
        # oleh `tools/brief/render.py` untuk dibaca agent, dan memampatkannya
        # dua kali membuang justru kolom `source` tiap klausa, yang merupakan
        # satu satunya hal yang membedakan "doktrin menyatakan" dari "project
        # ini mengukur".
        brief = context.get("brief")
        if isinstance(brief, str) and brief.strip():
            payload["brief"] = brief
    else:
        payload = {"note": "no drawing attached to this conversation"}

    wire = [
        {"role": "system", "content": (
            f"{SYSTEM}\n\nDATA - the current drawing digest, the ONLY source "
            f"of numbers you may quote:\n{json.dumps(payload, default=str)}"
        )},
        *history,
    ]
    # SEKALI, BUKAN DUA KALI. `wire` bisa 100k karakter dan ini berjalan DI
    # DALAM event loop, jadi meng-encode-nya ulang cuma untuk mencetak panjang
    # yang sama membayar biaya CPU yang sama dua kali sementara `/api/health`
    # menunggu giliran.
    encoded = len(json.dumps(wire))
    if encoded > MAX_PROMPT_CHARS:
        raise LLMUnavailable(
            f"the conversation is {encoded} characters, over "
            f"the {MAX_PROMPT_CHARS} cap. Scan fewer layers or "
            f"start a new conversation."
        )

    async with _CHATS:
        text = await _complete(cfg, wire)
    verdict = check(text, payload)
    return {
        "reply": text,
        "grounded": verdict.grounded,
        "reason": verdict.reason(),
        "unsupported": list(verdict.unsupported),
        "model": cfg["model"],
    }
