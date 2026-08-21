"use client";

import { memo } from "react";

import { clockStamp } from "@/lib/clock";
import type { ChecklistReport, DrawResponse } from "@/lib/types";

/**
 * The owner's own pre-trade checklist, answered with its evidence.
 *
 * His five questions, verbatim:
 *   DFR Consolidation udah terjadi?  Manipulation sudah?  In discount?
 *   SSMT stage 1?  SSMT stage 2?
 *
 * THERE IS NO OVERALL VERDICT HERE, and that is the whole design.
 * `ChecklistReport` deliberately carries no pass or fail, and this panel must
 * not invent one. The five items have different provenance and different
 * confidence: the defining range is single-sourced and not yet verified against
 * its own course material, manipulation is a clean conjunction of a time phase
 * and a sweep, and the SSMT rate depends entirely on which instruments were
 * paired. A single green tick would hide which item is carrying the weight, and
 * would present a checklist its owner ticks BY HAND as something this engine had
 * validated. Nothing in it has been measured against outcomes by anyone.
 *
 * ABSENT IS NOT FALSE. "No profile because Q1 has not closed yet" is a fact
 * about the clock, not a failed check, and the two are rendered differently: an
 * unmet item is quiet, an unknowable one carries its reason.
 *
 * AND NOTHING HERE IS A SIGNAL. Twelve pre-registered directional hypotheses
 * have failed in this project, market structure specifically three times (H6, H9
 * and H11). No arrows, no probability, no green-means-buy.
 */

const YES = "✓";
const NO = "·";

function Row({
  label,
  state,
  detail,
}: {
  label: string;
  /** met, unmet, or unknowable - three states, because absent is not false. */
  state: "met" | "unmet" | "unknowable";
  detail?: string;
}) {
  const mark = state === "met" ? YES : NO;
  const tone =
    state === "met"
      ? "text-text"
      : state === "unknowable"
        ? "text-text-faint"
        : "text-text-dim";
  return (
    <div className="flex items-baseline gap-2 px-3 py-1.5">
      <span className={`num w-3 shrink-0 text-[12px] ${tone}`} aria-hidden>
        {mark}
      </span>
      <span className={`flex-1 text-[12px] ${tone}`}>
        {label}
        {detail ? <span className="num ml-1 text-[11px] text-text-faint">{detail}</span> : null}
      </span>
    </div>
  );
}

function price(n: number): string {
  return n.toFixed(2);
}

export const ChecklistPanel = memo(function ChecklistPanel({
  report,
  stats,
}: {
  report: ChecklistReport;
  stats?: DrawResponse["meta"]["checklist"];
}) {
  const { dfr, profile, manipulation, discount, chain, stacked, bias, ssmt } = report;

  return (
    <section className="border-b border-line-strong">
      <header className="flex items-baseline justify-between gap-2 border-b border-line px-3 py-1">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Checklist
        </h2>
        <span className="num text-[11px] text-text-faint">{report.degree} cycle</span>
      </header>

      <Row
        label="Defining range formed"
        state={dfr ? "met" : "unknowable"}
        detail={
          dfr
            ? `${price(dfr.low)} to ${price(dfr.high)}, eq ${price(dfr.equilibrium)}`
            : undefined
        }
      />
      <Row
        label="Cycle profile read"
        state={profile ? "met" : "unknowable"}
        detail={profile ? `${profile.name}, manipulation in ${profile.manipulation}` : undefined}
      />
      <Row
        label="Manipulation seen"
        state={manipulation ? "met" : "unmet"}
        detail={
          manipulation
            ? `${manipulation.quarter_label}, took ${price(manipulation.level)}`
            : undefined
        }
      />
      {/* "In discount?", and the one item that can answer itself three ways at
          once. The row shows the CHOSEN anchor's word; the line below names the
          others when they disagree, because an item that can contradict itself
          must not be reduced to one tick - the anchor is single-sourced, so the
          disagreement is the honest part of the answer rather than a footnote. */}
      <Row
        label="In discount"
        state={
          discount?.chosen
            ? discount.chosen.reading === "discount"
              ? "met"
              : "unmet"
            : "unknowable"
        }
        detail={
          discount?.chosen
            ? `${discount.chosen.reading}, ${Math.round(discount.chosen.position * 100)}% of ${discount.chosen.degree}`
            : undefined
        }
      />
      {discount?.disagree ? (
        <p className="px-3 pb-1.5 text-[11px] leading-relaxed text-text-faint">
          {discount.readings.map((r) => `${r.anchor} says ${r.reading}`).join(", ")}.
          The anchor is single-sourced, so none of these three outranks the others.
        </p>
      ) : null}

      {/* ONE ROW PER HIT, and it names both instruments and all four prices.
          This used to be one row per stage saying "3 divergences", which read
          eight of the nine fields off the wire and threw them away - the only
          item on this panel drawn as a bare count, in a repo whose stated rule
          is that a drawing carries the evidence that produced it. A count cannot
          be checked; "SILVER took the low at 3394.00 where XAUUSD stopped at
          3396.34" can.

          Still one row per hit rather than a tally, because a stage IS a degree
          and nothing here requires two: the same source ships a one-SSMT model
          beside the two-stage one, so counting to two would be this panel
          inventing a rule its own backend refuses to enforce.

          The stamp is UTC because this panel is not given the clock the axis is
          drawn in - `clockStamp` puts the zone tag on every time it renders, so
          a reading taken from here can never be mistaken for a New York one. */}
      {ssmt.length ? (
        ssmt.map((hit) => (
          <Row
            key={`${hit.degree}-${hit.side}-${hit.took}-${hit.knowable_at}`}
            label={`SSMT at ${hit.degree}: ${hit.took} took the ${hit.side}, ${hit.failed} did not`}
            state="met"
            detail={`${hit.took} ${price(hit.took_prior)} to ${price(hit.took_now)}, ${hit.failed} ${price(hit.failed_prior)} to ${price(hit.failed_now)}, known at ${clockStamp(hit.knowable_at, "UTC")}`}
          />
        ))
      ) : (
        <Row label="SSMT" state="unmet" />
      )}

      {/* His precondition, counted rather than judged: at least two true opens
          must point the same way. The row shows the larger side, because that is
          the number his rule is about, and never says whether it is enough. */}
      {stacked ? (
        <Row
          label="True opens agreeing"
          state={
            Math.max(stacked.above.length, stacked.below.length) >= 2
              ? "met"
              : "unmet"
          }
          detail={`${stacked.above.length} above, ${stacked.below.length} below`}
        />
      ) : null}

      {/* A CLOCK FACT, and the base rate rides with it. Ten of the sixty-four
          three-digit chains is 15.6%, so being in his list is not rare, and
          nobody has measured whether the listed chains behave differently from
          the rest. Showing the flag without the base rate would turn a
          transcription into a claim. */}
      {chain ? (
        <div className="border-t border-line px-3 py-2">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-[11px] text-text-dim">Quarter chain</span>
            <span className="num text-[12px] text-text">{chain.text}</span>
          </div>
          <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
            {chain.degrees.join(" / ")}.{" "}
            {chain.in_his_list
              ? `In your list of ten. So are ${Math.round(chain.base_rate * 100)}% of all chains.`
              : "Not in your list of ten."}{" "}
            No one has measured whether the listed chains behave differently.
          </p>
        </div>
      ) : null}

      {bias ? (
        <div className="border-t border-line px-3 py-2">
          <div className="mb-1 flex items-baseline justify-between gap-2">
            <span className="text-[11px] text-text-dim">Timeframes agree</span>
            <span className={`num text-[11px] ${bias.aligned ? "text-text" : "text-text-dim"}`}>
              {bias.aligned ? "yes" : "no"}
            </span>
          </div>
          {/* All four, each with its own reading. His rule is that ALL must
              agree, so showing only the verdict would hide the one that broke
              it - and `disagreeing` names it precisely for that reason. */}
          <div className="space-y-0.5">
            {bias.degrees.map((d) => {
              const broke = bias.disagreeing.includes(d.timeframe);
              const word =
                d.bias === null
                  ? "not enough bars"
                  : d.bias === 0
                    ? "no break yet"
                    : d.bias > 0
                      ? "bullish"
                      : "bearish";
              return (
                <div key={d.timeframe} className="flex items-baseline justify-between gap-2">
                  <span className="num text-[11px] text-text-faint">{d.timeframe}</span>
                  <span
                    className={`text-[11px] ${broke ? "text-text" : "text-text-dim"}`}
                    title={d.reason ?? undefined}
                  >
                    {word}
                    {d.last_break ? (
                      <span className="num ml-1 text-text-faint">
                        {d.reversal_confirmed ? "CHoCH" : "BOS"}
                      </span>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>
          {bias.disagreeing.length ? (
            <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
              Broken by {bias.disagreeing.join(", ")}. Neither an unknown reading nor
              &quot;no break yet&quot; counts as agreement.
            </p>
          ) : null}
        </div>
      ) : null}

      {/* The reasons. An item can be absent because the clock has not got there
          yet, which is not the same as a check that failed, and a reader who
          cannot tell those apart will read the clock as a verdict. */}
      {report.notes.length ? (
        <ul className="border-t border-line px-3 py-2 text-[11px] leading-relaxed text-text-faint">
          {report.notes.map((note) => (
            <li key={note} className="mb-1 last:mb-0">
              {note}
            </li>
          ))}
        </ul>
      ) : null}

      <p className="border-t border-line px-3 py-2 text-[11px] leading-relaxed text-text-faint">
        Your rule, computed. Not a reading of what price will do: none of these five
        items has been measured against outcomes, and the eleven directional
        hypotheses this project did pre-register all failed.
        {stats?.extra_fetches
          ? ` This cost ${stats.extra_fetches} extra provider call${stats.extra_fetches === 1 ? "" : "s"}.`
          : null}
      </p>
    </section>
  );
});
