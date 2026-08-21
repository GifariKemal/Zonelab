"use client";

import { memo } from "react";

import type { DrawOnLiquidity, NamedLevel, RangeLiquidityReport } from "@/lib/types";

/**
 * The two liquidity READINGS, which are numbers rather than shapes and so have
 * never had anywhere on the chart to go.
 *
 * They were computed, shipped in the response and switchable in the panel, and
 * then rendered nowhere: two switches turned on several hundred lines of engine
 * whose output the reader never saw. A control wired to nothing is the failure
 * this project keeps finding in its own instruments rather than in its code.
 *
 * ERL is liquidity resting at the range's own extremes; IRL is the unfilled
 * inefficiency inside it, built from the boxes already drawn.
 *
 * THE DRAW IS NEVER NAMED. Both sides are listed and neither is chosen, because
 * naming the draw is a forecast and twelve pre-registered directional hypotheses
 * have failed in this project. An EMPTY SIDE IS A FACT, not a vote for the other
 * one: price that has run above every previous-period high leaves nothing
 * untaken above it, and that is a statement about what has been swept.
 */

function price(n: number): string {
  return n.toFixed(2);
}

function Levels({ label, levels }: { label: string; levels: NamedLevel[] }) {
  if (!levels.length) return null;
  return (
    <div className="border-t border-line px-3 py-2">
      <div className="mb-1 text-[11px] text-text-dim">{label}</div>
      <div className="space-y-0.5">
        {levels.map((level) => (
          <div
            key={`${level.name}-${level.price}`}
            className="flex items-baseline justify-between gap-2"
          >
            {/* Taken is DIMMED, never hidden. "PDH already got taken" is the
                fact that kills an idea, so removing it would remove the
                reason. */}
            <span
              className={`num text-[11px] ${level.taken_at ? "text-text-faint" : "text-text-dim"}`}
            >
              {level.name}
              {level.taken_at ? (
                <span className="ml-1 text-text-faint">taken</span>
              ) : null}
            </span>
            <span
              className={`num text-[11px] ${level.taken_at ? "text-text-faint" : "text-text"}`}
            >
              {price(level.price)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export const LiquidityPanel = memo(function LiquidityPanel({
  range,
  draw,
}: {
  range: RangeLiquidityReport | null;
  draw: DrawOnLiquidity | null;
}) {
  if (!range && !draw) return null;

  return (
    <section className="border-b border-line-strong">
      <header className="flex items-baseline justify-between gap-2 border-b border-line px-3 py-1">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Liquidity
        </h2>
        {range ? (
          <span className="num text-[11px] text-text-faint">
            {price(range.low)} to {price(range.high)}
          </span>
        ) : null}
      </header>

      {range ? (
        <>
          <Levels label="External, at the range edges" levels={range.external} />
          <Levels label="Internal, unfilled inside it" levels={range.internal} />
          {range.external.length === 0 && range.internal.length === 0 ? (
            <p className="px-3 py-2 text-[11px] leading-relaxed text-text-faint">
              The range produced no levels on either read.
            </p>
          ) : null}
        </>
      ) : null}

      {draw ? (
        <div className="border-t border-line px-3 py-2">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="text-[11px] text-text-dim">Untaken, both sides</span>
            <span className="num text-[11px] text-text-faint">
              at {price(draw.price)}
            </span>
          </div>
          {/* Above first, then below, and both always rendered. The order is the
              chart's, not a ranking. */}
          {(
            [
              ["above", draw.above],
              ["below", draw.below],
            ] as const
          ).map(([where, candidates]) => (
            <div key={where} className="mt-1.5">
              <div className="num text-[11px] text-text-faint">{where}</div>
              {candidates.length ? (
                <div className="space-y-0.5">
                  {candidates.map((c) => (
                    <div
                      key={`${where}-${c.name}-${c.price}`}
                      className="flex items-baseline justify-between gap-2"
                    >
                      <span className="num text-[11px] text-text-dim">{c.name}</span>
                      <span className="num text-[11px] text-text">
                        {price(c.price)}
                        <span className="ml-1.5 text-text-faint">
                          {price(c.distance)} away
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-[11px] leading-relaxed text-text-faint">
                  Nothing untaken {where}. Price has run through everything on
                  this side, which is a fact about what has been swept and not a
                  vote for the other one.
                </p>
              )}
            </div>
          ))}
          <p className="mt-2 text-[11px] leading-relaxed text-text-faint">
            Never resolved to one direction. Naming the draw is a forecast, and
            twelve of those have failed here.
          </p>
        </div>
      ) : null}
    </section>
  );
});
