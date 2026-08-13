import type { DrawResponse, ServerConfig, SupplyDemandParams } from "./types";

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

export function fetchDrawing(request: {
  symbol: string;
  interval: string;
  bars: number;
  provider: string;
  htf: string | null;
  session_offset_hours: number;
  supply_demand: SupplyDemandParams;
  signal?: AbortSignal;
}): Promise<DrawResponse> {
  const { signal, ...body } = request;
  return call<DrawResponse>("/api/draw", {
    method: "POST",
    body: JSON.stringify({ ...body, detectors: ["supply_demand"] }),
    signal,
  });
}
