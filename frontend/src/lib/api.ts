import type {
  Candle,
  DrawResponse,
  LayerParams,
  ServerConfig,
  SnapshotSummary,
  AccountReading,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_ZONELAB_API ?? "http://127.0.0.1:8100";

/** The backend answers provider failures with a 502 and the upstream's own
 *  wording. Surfacing that text is the whole point - "no data" tells the user
 *  nothing, "twelvedata error: API key is invalid" tells them what to fix. */
async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      // A bare fetch waits forever. A local API that hangs would otherwise
      // leave the UI showing "loading" indefinitely, which is a lie.
      signal: init?.signal
        ? AbortSignal.any([init.signal, AbortSignal.timeout(25_000)])
        : AbortSignal.timeout(25_000),
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    if (cause instanceof DOMException && cause.name === "TimeoutError") {
      throw new Error(`The Zonelab API at ${BASE} did not answer within 25s.`);
    }
    throw new Error(`Cannot reach the Zonelab API at ${BASE}. Is it running?`);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body) => body?.detail)
      .catch(() => null);
    throw new Error(detail ?? `API returned HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchConfig(): Promise<ServerConfig> {
  return call<ServerConfig>("/api/config");
}

/** The bar still being built, for the CHART only.
 *
 *  Deliberately NOT part of `fetchDrawing`: this is polled once a second while
 *  live is on, and a drawing is the expensive call. `candle` is null when the
 *  newest bar has already closed, which means the chart is already current. */
export function fetchForming(
  request: { symbol: string; interval: string; provider: string; signal?: AbortSignal },
): Promise<{ candle: Candle | null; provider: string }> {
  const query = new URLSearchParams({
    symbol: request.symbol,
    interval: request.interval,
    provider: request.provider,
  });
  return call<{ candle: Candle | null; provider: string }>(`/api/forming?${query}`, {
    signal: request.signal,
  });
}

/** `layers` names every drawing to produce and is the ONLY enable. There used to
 *  be two mechanisms - a `detectors` array plus an `enabled` boolean inside each
 *  overlay's own params block - so the knobs below are now knobs and nothing
 *  else: sending `gaps` does not draw gaps, naming "gaps" in `layers` does. */
export function fetchDrawing(
  request: LayerParams & {
    symbol: string;
    interval: string;
    bars: number;
    provider: string;
    htf: string | null;
    /** Null means no account was supplied, and the plan then reports no position
     *  size. Never send 0: the backend rejects it rather than guess. */
    equity: number | null;
    /** Named profile from `app/costs.py` BROKERS. Empty is the generic
     *  per-instrument row. Prices the plan at the venue orders fill on. */
    broker: string;
    refine: boolean;
    session_offset_hours: number;
    layers: string[];
    signal?: AbortSignal;
  },
): Promise<DrawResponse> {
  const { signal, ...body } = request;
  return call<DrawResponse>("/api/draw", {
    method: "POST",
    body: JSON.stringify(body),
    signal,
  });
}


/** Write down what is on screen right now.
 *
 *  THE RESPONSE THE CLIENT IS HOLDING IS POSTED BACK, verbatim, and the backend
 *  does not redraw. That is the whole design: `/api/draw` answers "what is true
 *  now", a snapshot answers "what did the reader see", and between the two a
 *  tick lands. A redrawn snapshot would be of a chart nobody looked at, and
 *  indistinguishable from one that was real.
 *
 *  `draw` is the caller's own nomination of where liquidity is being drawn, and
 *  it exists because Zonelab refuses to infer it - `liquidity.dol_candidates`
 *  reports both sides and chooses neither. Passing it is what lets the stored
 *  deduction record which premise was measured and which was a human's. */
export function saveSnapshot(
  response: DrawResponse,
  note: string,
  options: { deduce?: boolean; draw?: "higher" | "lower" | "unnominated" } = {},
): Promise<SnapshotSummary> {
  return call<SnapshotSummary>("/api/snapshot", {
    method: "POST",
    body: JSON.stringify({
      response,
      note,
      deduce: options.deduce ?? false,
      draw: options.draw ?? "unnominated",
    }),
  });
}

export function fetchSnapshots(): Promise<{ snapshots: SnapshotSummary[] }> {
  return call<{ snapshots: SnapshotSummary[] }>("/api/snapshots");
}


/** Account size from the source, when the source is a broker connection.
 *
 *  Answers 501 for a price feed, which is a fact about that feed and not a
 *  failure: yahoo cannot know anybody's equity. The caller is expected to offer
 *  this only where it can work. */
export function fetchAccount(provider: string): Promise<AccountReading> {
  return call<AccountReading>(`/api/account?provider=${encodeURIComponent(provider)}`);
}
