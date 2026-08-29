"use client";

import { memo, useCallback, useEffect, useState } from "react";

import { fetchTriad } from "@/lib/api";
import type { TriadResponse } from "@/lib/types";

/** Four named triads, each with a label and a short description. The keys
 *  match `TRIAD_FAMILIES` in `backend/app/triad.py`, and the descriptions
 *  match the assets listed there. */
const TRIADS = [
  { key: "monetary", label: "Monetary", desc: "XAU · DXY · EUR" },
  { key: "commodity", label: "Commodity", desc: "XAU · WTI · XAG" },
  { key: "risk", label: "Risk", desc: "XAU · NAS · US30" },
  { key: "fx", label: "FX", desc: "XAU · JPY · XPT" },
];

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
}: {
  symbol: string;
  interval: string;
  bars: number;
  provider?: string;
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
        {TRIADS.map((t) => (
          <button
            key={t.key}
            onClick={() => pick(t.key)}
            className={`flex-1 rounded px-1.5 py-1 text-[10px] font-medium transition-colors ${
              triad === t.key
                ? "bg-accent text-white"
                : "bg-panel-2 text-text-dim hover:text-text"
            }`}
            title={t.desc}
          >
            {t.label}
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
              {data.truth_asset.symbol}
            </span>
            <span className="num text-[11px] text-text-faint">
              {data.time.session ?? "no session"}
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
                  {sym}
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
                    {c.symbol}
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