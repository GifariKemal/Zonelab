"use client";

import { useCallback, useEffect, useState } from "react";

import { fetchAutotrade, setAutotrade } from "@/lib/api";
import type { AutotradeState } from "@/lib/types";
import { Icon } from "./icons";

/** How often the switch is re-read. Shorter than the daemon's 20-second cycle so
 *  a death is visible here within one cycle of it becoming true, and long enough
 *  that an idle tab is not polling a local API every second. */
const POLL_MS = 5000;

function elapsed(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

/**
 * The auto-trade switch, and the three states it can honestly be in.
 *
 * THE BUTTON DOES NOT TRADE. It writes a flag; `backend/tools/autotrade.py` reads
 * that flag and trades. Order placement lives outside the API on purpose - a
 * button wired straight to `order_send` would give every HTTP request that
 * reaches the server the ability to trade, and `tests/test_autotrade.py` asserts
 * on the import graph that it has not crept back in.
 *
 * WHICH MEANS THE HARD PART IS HONESTY, NOT WIRING. Armed with no daemon running
 * trades nothing at all, and a switch showing ON over a dead daemon is the same
 * class of defect as a test suite reporting green after crashing before it ran -
 * something this project has been bitten by three times. So `enabled` and
 * `daemon_alive` are rendered as two separate facts, and the armed-but-dead case
 * gets the loudest treatment of the three rather than the quietest.
 */
export function AutoTradePanel() {
  const [state, setState] = useState<AutotradeState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      setState(await fetchAutotrade());
      setError(null);
    } catch (cause) {
      // The API's own wording, not a generic failure. "Cannot reach the Zonelab
      // API" and "the terminal carries no symbol" are different problems and the
      // reader is the one who can tell them apart.
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }, []);

  useEffect(() => {
    // The first read is deferred by a tick rather than called in the effect
    // body. `react-hooks/set-state-in-effect` refuses the direct call, and the
    // rule is right about the shape even though `refresh` is async: a timer at 0
    // says "read once, then on a schedule" without pretending the read is part
    // of rendering.
    const first = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), POLL_MS);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, [refresh]);

  async function flip() {
    if (!state) return;
    setBusy(true);
    try {
      setState(await setAutotrade(!state.enabled));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    } finally {
      setBusy(false);
    }
  }

  const enabled = state?.enabled ?? false;
  const alive = state?.daemon_alive ?? false;
  // ARMED BUT DEAD IS ITS OWN STATE and it is the one that has to shout. The
  // other two are self-evident from the button; this one is a switch that looks
  // like it is working and is not.
  const orphaned = enabled && !alive;

  return (
    <section className="border-b border-line px-3 py-3">
      <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
        Auto trade
      </h3>

      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 flex-col">
          <span className="truncate text-[12px] text-text-dim">
            {enabled ? "Armed" : "Off"}
          </span>
          <span className="truncate text-[11px] text-text-faint">
            {alive
              ? `daemon alive, last beat ${elapsed(state?.heartbeat_age_seconds ?? 0)} ago`
              : state?.last_seen
                ? `daemon last seen ${elapsed(state.heartbeat_age_seconds ?? 0)} ago`
                : "no daemon has ever run"}
          </span>
        </span>
        <button
          type="button"
          onClick={() => void flip()}
          disabled={busy || !state}
          aria-pressed={enabled}
          // Tombol yang MENGARMKAN uang sungguhan, dan sampai sekarang ia satu
          // satunya kontrol besar di app tanpa hover sama sekali. Audit
          // menghitungnya: tidak ada hover, tidak ada active, dan disabled-nya
          // ditulis lewat ternary `opacity-40` dan bukan varian `disabled:`,
          // jadi ia tidak ikut kalau `disabled` datang dari tempat lain.
          className={`shrink-0 rounded-[2px] border px-2 py-1 text-[11px] transition-colors duration-[70ms] enabled:active:translate-y-px disabled:cursor-not-allowed disabled:opacity-40 ${
            enabled
              ? "border-accent text-accent enabled:hover:bg-accent/15"
              : "border-line-strong text-text-dim enabled:hover:border-text-faint enabled:hover:text-text"
          }`}
        >
          {enabled ? "Disarm" : "Arm"}
        </button>
      </div>

      {orphaned ? (
        // ALARM PALING KERAS DI APP INI, dan ia TIDAK dapat hue sendiri.
        // Merah sudah berarti supply dan amber cuma berjarak 12 derajat dari
        // accent emas, jadi warna ketiga di sini akan terbaca sebagai arah atau
        // sebagai kontrol. Yang membawa urgensinya bentuk dan bobot: glyph
        // segitiga, rule 2px, dan satu satunya teks bold di panel.
        <p className="mt-3 flex items-start gap-2 border-l-2 border-info bg-info/10 py-1 pl-2 text-[11px] leading-relaxed text-info">
          <Icon name="alert" className="mt-0.5 size-3.5 shrink-0" />
          <span>
          Armed, and <strong>nothing is trading</strong>: no daemon has stamped a
          heartbeat in the last minute. The switch only writes a flag - the API
          cannot place orders. Start the daemon:
          <br />
          <code className="num">python -m tools.autotrade --send</code>
          </span>
        </p>
      ) : null}

      {enabled && alive ? (
        <p className="mt-3 border-l border-line-strong pl-2 text-[11px] leading-relaxed text-text-faint">
          Trading <span className="num">{state?.symbol ?? "?"}</span> on{" "}
          <span className="num">{state?.interval ?? "?"}</span> at{" "}
          <span className="num">
            {state?.risk_pct == null ? "?" : `${(state.risk_pct * 100).toFixed(1)}%`}
          </span>{" "}
          risk per trade. These come from the daemon rather than from this panel,
          so they say what is actually running.
        </p>
      ) : null}

      {!enabled ? (
        <p className="mt-3 border-l border-line-strong pl-2 text-[11px] leading-relaxed text-text-faint">
          Off means no new orders. Pending orders already at the broker keep their
          stop and target - the broker holds those, not the daemon.
        </p>
      ) : null}

      {error ? (
        <p className="mt-3 border-l-2 border-accent pl-2 text-[11px] leading-relaxed text-accent">
          {error}
        </p>
      ) : null}
    </section>
  );
}
