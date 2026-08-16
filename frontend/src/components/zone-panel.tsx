"use client";

import Link from "next/link";
import { memo, useState } from "react";

import type { Advice, TradePlan, Zone } from "@/lib/types";

const STATE_LABEL: Record<Zone["state"], string> = {
  fresh: "Fresh",
  tested: "Tested",
  mitigated: "Mitigated",
  broken: "Broken",
};

const KIND_MEANING: Record<Zone["kind"], string> = {
  DBR: "Drop, base, rally",
  RBR: "Rally, base, rally",
  RBD: "Rally, base, drop",
  DBD: "Drop, base, drop",
  FVG: "Fair value gap",
  OB: "Order block",
};

/** Titles of the /docs sections the advisor links into. The handbook owns the
 *  anchors; this only names them, so a link says where it goes. */
const DOC_TITLES: Record<string, string> = {
  apa: "Apa ini sebenarnya",
  bentuk: "Satu bentuk yang dicari",
  atr: "ATR, satuan segalanya",
  formasi: "Empat formasi",
  garis: "Dua garis yang tidak setara",
  siklus: "Siklus hidup zona",
  panel: "Panel kiri, tombol per tombol",
  mtf: "Timeframe tinggi dan penyempurnaan",
  jalan: "Jalan di depan zona",
  jejak: "Jejak filter",
};

const TABS = [
  ["zone", "Zone"],
  ["plan", "Plan"],
  ["advice", "Advisor"],
] as const;

type Tab = (typeof TABS)[number][0];

interface Props {
  zones: Zone[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  lastPrice: number | null;
  /** The chart's own timeframe, so projected zones can be badged. */
  chartInterval: string;
  /** One per drawn zone, matched by id rather than by position so a filtered
   *  list cannot silently pair a plan with the wrong box. */
  plans: TradePlan[];
  advice: Advice[];
  /** Held as the raw field text, because "" has to stay distinguishable from 0:
   *  empty means no account was given, and the plan then shows no size. */
  equity: string;
  onEquity: (value: string) => void;
}

/** Indonesian decimal comma, so a measured rate reads here exactly as it does
 *  in the advisor sentence beside it and in docs/CALIBRATION.md. */
function pct(value: number): string {
  return `${(value * 100).toFixed(1).replace(".", ",")}%`;
}

/** Memoised: the crosshair sets hovered state on every mouse move over the
 *  chart, and re-sorting the whole zone list to answer a mouse move is work
 *  nobody asked for. None of these props change while hovering. */
export const ZonePanel = memo(function ZonePanel({
  zones,
  selectedId,
  onSelect,
  lastPrice,
  chartInterval,
  plans,
  advice,
  equity,
  onEquity,
}: Props) {
  const [tab, setTab] = useState<Tab>("zone");
  const selected = zones.find((z) => z.id === selectedId) ?? null;

  // Nearest-first: the zone price has to travel least far to reach is the one
  // that matters next. Falls back to newest-first before any price is known.
  const ordered = [...zones].sort((a, b) =>
    lastPrice === null
      ? b.time_from - a.time_from
      : distance(a, lastPrice) - distance(b, lastPrice),
  );

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-baseline justify-between border-b border-line px-3 py-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Zones
        </h2>
        <span className="num text-[11px] text-text-faint">
          {zones.length} drawn
        </span>
      </header>

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {ordered.length === 0 ? (
          <p className="px-3 py-6 text-[12px] leading-relaxed text-text-faint">
            {/* Hedged, because the trace is only drawn while supply and demand
                is running, and this line used to point at an empty space. */}
            No zones survived the current filters. With supply and demand on,
            the filter trace in the left panel shows which gate removed them.
          </p>
        ) : (
          ordered.map((zone) => (
            <button
              key={zone.id}
              onClick={() => onSelect(zone.id === selectedId ? null : zone.id)}
              className={`flex w-full items-center gap-2 border-b border-line px-3 py-2 text-left transition-colors ${
                zone.id === selectedId ? "bg-panel-2" : "hover:bg-panel-2/60"
              }`}
            >
              <span
                aria-hidden
                className="h-6 w-[3px] shrink-0"
                style={{
                  background: zone.side === "demand" ? "#2ea36f" : "#d4574f",
                  opacity: zone.state === "broken" ? 0.3 : 1,
                }}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="num text-[12px] font-medium text-text">
                    {zone.kind}
                  </span>
                  {zone.timeframe && zone.timeframe !== chartInterval ? (
                    <span className="num shrink-0 border border-line-strong px-1 text-[10px] text-accent">
                      {zone.timeframe}
                    </span>
                  ) : null}
                  <span className="truncate text-[11px] text-text-faint">
                    {STATE_LABEL[zone.state]}
                    {zone.confirmed ? "" : ", forming"}
                  </span>
                </span>
                {/* The side is named, not only coloured. The bar beside it is
                    red against green, which is the commonest colour blindness
                    there is, and it was the row's only carrier of the side. */}
                <span className="block text-[11px] text-text-dim">
                  {zone.side === "demand" ? "Demand" : "Supply"}{" "}
                  <span className="num">
                    {zone.bottom.toFixed(2)} to {zone.top.toFixed(2)}
                  </span>
                </span>
              </span>
              <span
                className="num shrink-0 text-[12px] text-accent"
                title="How far the leg-out ran from this zone, in ATR. The one filter with evidence behind it."
              >
                {zone.departure_atr.toFixed(1)}
                <span className="ml-0.5 text-[10px] text-text-faint">ATR</span>
              </span>
            </button>
          ))
        )}
      </div>

      {/* The plan and the advice describe the SELECTED zone, exactly like the
          inspector does, so they share its space rather than taking a fourth
          column off the chart. */}
      {selected ? (
        <section className="flex max-h-[60%] shrink-0 flex-col border-t border-line-strong bg-panel-2">
          <div
            className="flex shrink-0 border-b border-line"
            role="group"
            aria-label="Zone detail"
          >
            {TABS.map(([id, label]) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                aria-pressed={tab === id}
                className={`flex-1 px-2 py-1.5 text-[11px] uppercase tracking-wider transition-colors ${
                  tab === id
                    ? "bg-accent/15 text-accent"
                    : "text-text-faint hover:text-text-dim"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {tab === "zone" ? (
              <Inspector zone={selected} lastPrice={lastPrice} />
            ) : tab === "plan" ? (
              <PlanPanel
                plan={plans.find((p) => p.zone_id === selected.id) ?? null}
                equity={equity}
                onEquity={onEquity}
              />
            ) : (
              <AdvicePanel
                advice={advice.find((a) => a.zone_id === selected.id) ?? null}
              />
            )}
          </div>
        </section>
      ) : null}
    </div>
  );
});

/** Geometry and risk for the selected zone, and nothing that reads as a call.
 *  The panel leads with what it is NOT, because a box of entry, stop and target
 *  looks like a signal whatever the numbers say. */
function PlanPanel({
  plan,
  equity,
  onEquity,
}: {
  plan: TradePlan | null;
  equity: string;
  onEquity: (value: string) => void;
}) {
  if (plan === null) {
    return (
      <p className="px-3 py-6 text-[12px] leading-relaxed text-text-faint">
        Zona ini tidak punya geometri yang bisa dijadikan rencana: tingginya nol
        atau ATR-nya nol, jadi tidak ada jarak stop untuk dihitung.
      </p>
    );
  }

  const way = plan.side === "demand" ? "long" : "short";

  return (
    <div>
      <p className="border-b border-line px-3 py-2 text-[11px] leading-relaxed text-text-faint">
        <span className="text-text-dim">Ini geometri, bukan rekomendasi.</span>{" "}
        Rencana di zona {plan.side} adalah bentuk sebuah {way} SEANDAINYA
        alasannya sudah kamu punya. Alasan itu tidak ada di gambar ini.
      </p>

      <label className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <span className="text-[11px] text-text-dim">
          Equity
          <span className="ml-1 text-text-faint">opsional</span>
        </span>
        <input
          type="number"
          min="0"
          step="any"
          inputMode="decimal"
          value={equity}
          onChange={(e) => onEquity(e.target.value)}
          placeholder="kosong"
          className="num w-24 border border-line-strong bg-panel px-1.5 py-1 text-right text-[12px] text-text"
        />
      </label>

      <dl className="px-3 py-2">
        <Row label="Entry" value={plan.entry.toFixed(2)} accent />
        <Row label="Stop" value={plan.stop.toFixed(2)} />
        <Row
          label="Target"
          value={plan.target === null ? "tidak terukur" : plan.target.toFixed(2)}
        />
        <Row label="Risk per unit" value={plan.risk_per_unit.toFixed(2)} />
        <Row
          label="Reward"
          value={plan.reward_r === null ? "tidak terukur" : `${plan.reward_r.toFixed(2)}R`}
        />
        {/* Absent, not zero, when no equity was given. A size shown against an
            account nobody supplied is the fastest way to make a risk number
            look authoritative while meaning nothing. */}
        {plan.units !== null ? (
          <Row label="Size at 1% risk" value={`${plan.units} unit`} />
        ) : null}
        {plan.spread_charged !== null ? (
          <Row label="Spread charged" value={plan.spread_charged.toFixed(2)} />
        ) : null}
      </dl>

      {plan.warnings.length ? (
        <div className="border-t border-line px-3 py-2">
          <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-supply">
            Perhatian
          </h4>
          {plan.warnings.map((warning) => (
            <p
              key={warning}
              className="mb-1.5 border-l-2 border-supply pl-2 text-[11px] leading-relaxed text-text-dim"
            >
              {warning}
            </p>
          ))}
        </div>
      ) : null}

      <div className="border-t border-line px-3 py-2">
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Cohort survival
        </h4>
        {/* Two rates, never one. Multiplying them would treat age and departure
            as independent, and age turned out to be the departure gate wearing
            a different name. */}
        <p className="mb-2 text-[11px] leading-relaxed text-text-faint">
          Seberapa sering zona SEPERTI ini bertahan saat diuji, diukur pada
          ribuan zona lama. Ini angka kelompok, bukan peluang trade ini, dan
          belum dipotong biaya. Jangan dikalikan satu sama lain.
        </p>
        <Row label="Departure cohort" value={pct(plan.departure_held_rate)} />
        <Row
          label={`Age cohort, ${plan.age_bars} bar`}
          value={pct(plan.age_held_rate)}
        />
      </div>
    </div>
  );
}

/** The advisor's sentences in the order the backend emitted them. The last one
 *  is always what cannot be known, and it is the one that must survive a reader
 *  who skims: marked in the accent, never folded away. */
function AdvicePanel({ advice }: { advice: Advice | null }) {
  if (advice === null || advice.notes.length === 0) {
    return (
      <p className="px-3 py-6 text-[12px] leading-relaxed text-text-faint">
        Belum ada penjelasan untuk zona ini.
      </p>
    );
  }

  const last = advice.notes.length - 1;

  return (
    <div className="px-3 py-2">
      {advice.notes.map((note, i) => (
        // Index keys: several notes share the topic "Perhatian", so position is
        // the only thing that identifies one.
        <div
          key={i}
          className={`mb-3 border-l-2 pl-2 ${
            i === last
              ? "border-accent"
              : note.learn === null
                ? "border-supply"
                : "border-line-strong"
          }`}
        >
          <h4
            className={`text-[10px] font-semibold uppercase tracking-[0.14em] ${
              i === last ? "text-accent" : "text-text-faint"
            }`}
          >
            {note.topic}
          </h4>
          <p className="mt-0.5 text-[11px] leading-relaxed text-text-dim">
            {note.text}
          </p>
          {note.learn ? (
            <Link
              href={`/docs#${note.learn}`}
              className="mt-1 inline-block text-[11px] text-text-faint underline underline-offset-2 transition-colors hover:text-accent"
            >
              Pelajari: {DOC_TITLES[note.learn] ?? note.learn}
            </Link>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function Inspector({ zone, lastPrice }: { zone: Zone; lastPrice: number | null }) {
  const height = zone.top - zone.bottom;
  const away =
    lastPrice === null ? null : ((distance(zone, lastPrice) / lastPrice) * 100).toFixed(2);

  return (
    <div>
      <header className="border-b border-line px-3 py-2">
        <h3 className="text-[13px] font-medium text-text">
          {zone.kind}
          <span className="ml-2 text-[11px] font-normal text-text-faint">
            {KIND_MEANING[zone.kind]}
          </span>
        </h3>
        <p className="mt-0.5 text-[11px] text-text-dim">{zone.note}</p>
      </header>

      <dl className="px-3 py-2">
        <Row label="Proximal" value={zone.proximal.toFixed(2)} accent />
        <Row label="Distal" value={zone.distal.toFixed(2)} />
        <Row label="Height" value={height.toFixed(2)} />
        {away ? <Row label="Distance from price" value={`${away}%`} /> : null}
        <Row label="Departure" value={`${zone.departure_atr.toFixed(2)} ATR`} />
        <Row label="Profit margin" value={`${zone.profit_margin.toFixed(1)}x zone`} />
        <Row
          label="Profit zone"
          value={
            zone.profit_zone_rr === null
              ? "clear ahead"
              : `${zone.profit_zone_rr.toFixed(1)}x to the wall`
          }
        />
        {zone.crowded_at !== null ? (
          <Row
            label="Road shut"
            value={`${new Date(zone.crowded_at * 1000)
              .toISOString()
              .slice(0, 16)
              .replace("T", " ")} UTC`}
          />
        ) : null}
        <Row
          label="Curve"
          value={`${(zone.curve * 100).toFixed(0)}%${zone.curve_favourable ? ", favourable" : ""}`}
        />
        {zone.refinement ? (
          <Row
            label="Refined"
            value={`${(zone.refinement.shrank_to * 100).toFixed(0)}% of ${(
              zone.refinement.from_top - zone.refinement.from_bottom
            ).toFixed(2)}, from ${zone.refinement.bars} ${zone.refinement.timeframe} bars`}
          />
        ) : null}
        {zone.arrival_atr !== null ? (
          <Row label="Arrival" value={`${zone.arrival_atr.toFixed(1)} ATR`} />
        ) : null}
        {zone.nested_in.length ? (
          <Row label="Nested in" value={zone.nested_in.join(", ")} />
        ) : null}
        <Row
          label="Base drift"
          value={
            zone.base_drift > 0.7
              ? `${zone.base_drift.toFixed(2)}, drifted`
              : zone.base_drift.toFixed(2)
          }
        />
        <Row label="Tests" value={String(zone.touches)} />
        <Row
          label="Eaten"
          value={`${(zone.penetration_pct * 100).toFixed(0)}%`}
        />
      </dl>

      <div className="border-t border-line px-3 py-2">
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Formation
        </h4>
        <p className="mb-2 text-[11px] leading-relaxed text-text-faint">
          How cleanly the zone was built. Tested against outcomes and it does not
          predict them, so read it as description, not as a rating.
        </p>
        {Object.entries(zone.factors).map(([name, contribution]) => (
          <div key={name} className="mb-1.5">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] capitalize text-text-dim">{name}</span>
              <span className="num text-[11px] text-text-dim">
                {contribution.toFixed(3)}
              </span>
            </div>
            {/* Share of the composite, so the longest bar names what this zone
                scores on. Each factor caps at one third. */}
            <div
              className="mt-0.5 h-[2px] bg-accent"
              style={{ width: `${Math.min(100, contribution * 300)}%` }}
            />
          </div>
        ))}
        <div className="mt-2 flex items-baseline justify-between border-t border-line pt-2">
          <span className="text-[11px] text-text">Formation score</span>
          <span className="num text-[12px] text-accent">
            {zone.formation_score.toFixed(3)}
          </span>
        </div>
      </div>

      <div className="border-t border-line px-3 py-2">
        <h4 className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Bars that formed it
        </h4>
        <p className="num text-[11px] leading-relaxed text-text-dim">
          leg in {zone.anatomy.leg_in_from} to {zone.anatomy.leg_in_to}
          <br />
          base {zone.anatomy.base_from} to {zone.anatomy.base_to}
          <br />
          leg out {zone.anatomy.leg_out_from} to {zone.anatomy.leg_out_to}
        </p>
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-[3px]">
      <dt className="text-[11px] text-text-faint">{label}</dt>
      <dd className={`num text-[12px] ${accent ? "text-accent" : "text-text-dim"}`}>
        {value}
      </dd>
    </div>
  );
}

function distance(zone: Zone, price: number): number {
  if (price > zone.top) return price - zone.top;
  if (price < zone.bottom) return zone.bottom - price;
  return 0;
}
