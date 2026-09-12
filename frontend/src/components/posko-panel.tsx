"use client";

import { memo, useCallback, useEffect, useState } from "react";

import { fetchTriad } from "@/lib/api";
import type { ServerConfig, TriadResponse } from "@/lib/types";
import { vendorName } from "@/lib/vendor";

/** Display order and button text, keyed by the family names the server sends.
 *
 *  THE MEMBERS ARE NOT LISTED HERE ANY MORE. This file used to carry its own
 *  copy of all seven families with hand-written descriptions like
 *  "XAU - 10Y - 30Y", which is exactly the drift `/api/config` exists to
 *  prevent - and it drifted the day `metals` was added, because that took one
 *  edit to the backend tuple and two more to lists in this folder. The members
 *  now come from `config.triads`, which also lets them be named in whatever the
 *  feed actually calls them. A family the server adds and this map has not
 *  heard of still renders, under its own name. */
const TRIAD_LABELS: Record<string, string> = {
  monetary: "Monetary",
  commodity: "Commodity",
  risk: "Risk",
  fx: "FX",
  bonds: "Bonds",
  energy: "Energy",
  metals: "Metals",
};

const titleCase = (key: string) => key.charAt(0).toUpperCase() + key.slice(1);

/**
 * POSKO 618 panel — the triad framework in the right rail.
 *
 * Shows four triad presets, the Truth Asset (the consolidating one), and the
 * correlation matrix that backs it. Fetches from `/api/triad` independently
 * so it stays live even when the chart is not drawing.
 *
 * THE TRUTH ASSET IS NEVER A DIRECTION. It says which asset is consolidating
 * and therefore showing the real premium and discount; it does not say buy or
 * sell. Twelve pre-registered directional hypotheses have failed in this
 * project and this panel adds no thirteenth.
 */
export const PoskoPanel = memo(function PoskoPanel({
  symbol,
  interval,
  bars,
  provider,
  config,
}: {
  symbol: string;
  interval: string;
  bars: number;
  provider?: string;
  /** For naming instruments as the serving feed names them. */
  config: ServerConfig | null;
}) {
  const [triad, setTriad] = useState<string | null>(null);
  const [data, setData] = useState<TriadResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!triad) {
      setData(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchTriad(symbol, interval, bars, triad, provider)
      .then((d) => {
        if (!cancelled) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [triad, symbol, interval, bars, provider]);

  const pick = useCallback(
    (key: string) => setTriad((prev) => (prev === key ? null : key)),
    [],
  );

  return (
    <section className="border-b border-line-strong">
      <header className="flex items-baseline justify-between gap-2 border-b border-line px-3 py-1">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          POSKO 618
        </h2>
        {data?.time ? (
          <span className="num text-[11px] text-text-faint">
            NY {data.time.ny} &middot; WIB {data.time.wib}
          </span>
        ) : null}
      </header>

      {/* Triad buttons, one row, four presets, toggle on/off.

          `bg-panel-2` FOR THE INACTIVE STATE, and the class it replaces is the
          point: `bg-panel-elevated` was never defined. `globals.css` declares
          `--panel` and `--panel-2` and exposes them through `@theme inline` as
          `--color-panel` and `--color-panel-2`, so Tailwind emits nothing at all
          for `bg-panel-elevated` - the three unpicked triads rendered fully
          transparent, sitting straight on the rail's own `bg-panel`, and read as
          three gaps rather than as three buttons. #131820 against the rail's
          #0f1216 is the one step of elevation this theme has, which is what the
          state needs to say: pickable, not picked. */}
      <div className="flex gap-1 px-2 py-1.5">
        {Object.keys(config?.triads ?? TRIAD_LABELS).map((key) => (
          <button
            key={key}
            onClick={() => pick(key)}
            // `text-white` adalah SATU SATUNYA kelas palet Tailwind tetap di
            // seluruh `src/`, dan di theme terang ia mencetak putih di atas
            // accent emas gelap: 2,1:1, di bawah floor mana pun. `--bg` selalu
            // permukaan yang paling kontras dengan accent theme-nya sendiri.
            className={`flex-1 rounded px-1.5 py-1 text-[10px] font-medium transition-colors duration-[70ms] active:translate-y-px ${
              triad === key
                ? "bg-accent text-bg hover:bg-accent/85"
                : "bg-panel-2 text-text-dim hover:bg-line/60 hover:text-text"
            }`}
            // Named in the feed's own vocabulary, and by the feed that will
            // actually SERVE this triad - `data.provider`, which the route
            // substitutes when the chart's source cannot carry all three legs.
            // Before a reading lands there is no such answer yet, so the
            // chart's provider stands in.
            title={(config?.triads?.[key] ?? [])
              .map((member: string) => vendorName(config, data?.provider ?? provider, member))
              .join(" · ")}
          >
            {TRIAD_LABELS[key] ?? titleCase(key)}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="px-3 py-2 text-[11px] text-text-faint">Loading...</p>
      ) : data?.truth_asset ? (
        <div className="border-t border-line px-3 py-2">
          <div className="mb-1 text-[11px] text-text-dim">Truth Asset</div>
          <div className="flex items-baseline justify-between gap-2">
            <span className="num text-[13px] font-semibold text-accent">
              {vendorName(config, data.provider, data.truth_asset.symbol)}
            </span>
            <span className="num text-[11px] text-text-faint">
              {data.time.session ?? "between sessions"}
            </span>
          </div>
          {/* Consolidation scores — lower is more consolidated */}
          <div className="mt-1.5 space-y-0.5">
            {Object.entries(data.truth_asset.scores).map(([sym, score]) => (
              <div
                key={sym}
                className="flex items-baseline justify-between gap-2"
              >
                <span
                  className={`num text-[11px] ${
                    sym === data.truth_asset!.symbol
                      ? "text-accent"
                      : "text-text-dim"
                  }`}
                >
                  {vendorName(config, data.provider, sym)}
                </span>
                <span className="num text-[11px] text-text-faint">
                  {score.toFixed(1)}
                </span>
              </div>
            ))}
          </div>
          {/* Correlation matrix — the measured relationship */}
          {data.correlation.length ? (
            <div className="mt-2 border-t border-line pt-1.5">
              <div className="text-[10px] text-text-faint">
                Pearson, {data.correlation[0].pairs} pairs
              </div>
              {data.correlation.map((c) => (
                <div
                  key={c.symbol}
                  className="flex items-baseline justify-between gap-2"
                >
                  <span className="num text-[11px] text-text-dim">
                    {vendorName(config, data.provider, c.symbol)}
                  </span>
                  <span className="num text-[11px] text-text">
                    {c.full === null ? "—" : c.full.toFixed(3)}
                    {c.sign_changed ? " ⚡" : ""}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : data?.skipped?.length ? (
        <p className="px-3 py-2 text-[11px] leading-relaxed text-text-faint">
          Not loaded: {data.skipped.join("; ")}
        </p>
      ) : triad ? (
        <p className="px-3 py-2 text-[11px] leading-relaxed text-text-faint">
          No truth asset measurable on this window.
        </p>
      ) : (
        <p className="px-3 py-2 text-[11px] leading-relaxed text-text-faint">
          Pick a triad to see the Truth Asset.
        </p>
      )}
    </section>
  );
});