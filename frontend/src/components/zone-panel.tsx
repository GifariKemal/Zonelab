"use client";

import Link from "next/link";
import { memo, useState } from "react";

import type { Advice, TradePlan, Zone } from "@/lib/types";
import { clockStamp, type ClockZone } from "@/lib/clock";

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
  // Named as what happened to the box, not as what it predicts. Both are an
  // existing box read from the other side after price closed through it.
  IFVG: "Inversion fair value gap",
  BRK: "Breaker block",
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
  /** Which clock every timestamp in this panel prints in. */
  clock: ClockZone;
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
  /** Where the number came from, in words, or null when a human typed it. A
   *  figure read from a terminal and one typed by hand size identically and mean
   *  different things, and the panel has to say which it is holding. */
  equityFrom: string | null;
  onReadAccount: () => void;
  /** Only a broker connection can answer for an account. Offered where it can
   *  work rather than offered everywhere and failing, because a button that
   *  answers 501 teaches the reader to distrust the panel. */
  canReadAccount: boolean;
  /** Drawn zones that fall entirely outside the price range on screen. "Found"
   *  and "can currently be seen" are two different numbers, and this panel used
   *  to print only the first - which is what let six zones read as one. */
  clipped: { above: number; below: number };
}

/** Indonesian decimal comma, so a measured rate reads here exactly as it does
 *  in the advisor sentence beside it and in docs/CALIBRATION.md. */
function pct(value: number): string {
  return `${(value * 100).toFixed(1).replace(".", ",")}%`;
}

/** Epoch seconds in the clock the chart is currently showing.
 *
 *  It used to be hardcoded UTC. That was fine while the chart axis was also
 *  hardcoded UTC, and became a trap the moment the axis could be set to New
 *  York or WIB: the app would then print two different clocks on one screen
 *  with no way to tell which was which. Misreading a session by seven hours is
 *  the single most expensive mistake this app can cause, so there is one
 *  picker and everything that prints a time obeys it.
 *
 *  `clockStamp` always ends in the zone tag, which is what makes the reading
 *  safe rather than merely consistent. */
const stampIn = (epoch: number, clock: ClockZone) => clockStamp(epoch, clock);

/** Memoised: the crosshair sets hovered state on every mouse move over the
 *  chart, and re-sorting the whole zone list to answer a mouse move is work
 *  nobody asked for. None of these props change while hovering. */
export const ZonePanel = memo(function ZonePanel({
  clock,
  zones,
  selectedId,
  onSelect,
  lastPrice,
  chartInterval,
  plans,
  advice,
  equity,
  onEquity,
  equityFrom,
  onReadAccount,
  canReadAccount,
  clipped,
}: Props) {
  const [tab, setTab] = useState<Tab>("zone");
  const hidden = clipped.above + clipped.below;
  const selected = zones.find((z) => z.id === selectedId) ?? null;

  // Grouped by side, nearest-first inside each group, supply above demand so the
  // list reads down the price axis the way the chart does.
  //
  // The question a trader brings to this panel is "what is nearest to price,
  // above and below" - not "what exists". One flat list of 35 rows answers the
  // second question only: it takes a scan of every row to find out whether the
  // nearest supply is 0,1% away or 4%. Nearest-first was already the order; the
  // grouping and the printed distance are what make it legible.
  const groups = (["supply", "demand"] as const).map((side) => ({
    side,
    rows: zones
      .filter((z) => z.side === side)
      // Falls back to newest-first before any price is known.
      .sort((a, b) =>
        lastPrice === null
          ? b.time_from - a.time_from
          : distance(a, lastPrice) - distance(b, lastPrice),
      ),
  }));

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-baseline justify-between border-b border-line px-3 py-2">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Zones
        </h2>
        {/* Two numbers, because they are two facts. The backend already
            separates zones FOUND from zones surviving the display cap; the same
            distinction has to hold at the last step, since a zone the price
            scale hides is drawn and invisible at the same time. */}
        <span className="num text-[11px] text-text-faint">
          {hidden > 0 ? (
            <>
              {zones.length - hidden} visible of {zones.length}
            </>
          ) : (
            <>{zones.length} drawn</>
          )}
        </span>
      </header>

      {hidden > 0 ? (
        <p className="border-b border-accent/40 bg-accent/10 px-3 py-1.5 text-[11px] leading-relaxed text-accent">
          {hidden} {hidden === 1 ? "zone is" : "zones are"} off the price range on
          screen
          {clipped.above > 0 && clipped.below > 0
            ? `, ${clipped.above} above and ${clipped.below} below`
            : clipped.above > 0
              ? ", above it"
              : ", below it"}
          . They are in the list; the chart cannot show them at this zoom.
        </p>
      ) : null}

      <div className="scroll-thin min-h-0 flex-1 overflow-y-auto">
        {zones.length === 0 ? (
          <p className="px-3 py-6 text-[12px] leading-relaxed text-text-faint">
            {/* Hedged, because the trace is only drawn while supply and demand
                is running, and this line used to point at an empty space. */}
            No zones survived the current filters. With supply and demand on,
            the filter trace in the left panel shows which gate removed them.
          </p>
        ) : (
          groups
            .filter(({ rows }) => rows.length > 0)
            .map(({ side, rows }, group) => (
              <section key={side}>
                {/* Sticky, because the group a row belongs to is the first thing
                    you lose scrolling 35 of them. A plain div rather than a
                    `header`: the panel's own header is located by tag in
                    e2e/offscreen-zones.mjs. */}
                <div className="sticky top-0 z-10 flex items-baseline justify-between gap-2 border-b border-line bg-panel px-3 py-1">
                  <h3 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
                    {side === "supply" ? "Supply" : "Demand"}
                    {/* Said once. The ordering rule is the same for both groups,
                        and repeating it on the second one is four words of
                        redundancy on a panel with no room for any. */}
                    {group === 0 ? (
                      <span className="ml-2 tracking-normal normal-case">
                        nearest price first
                      </span>
                    ) : null}
                  </h3>
                  <span className="num text-[11px] text-text-faint">
                    {rows.length}
                  </span>
                </div>
                {rows.map((zone) => (
                  <ZoneRow
                    key={zone.id}
                    zone={zone}
                    lastPrice={lastPrice}
                    chartInterval={chartInterval}
                    selected={zone.id === selectedId}
                    onSelect={onSelect}
                  />
                ))}
              </section>
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
              <Inspector zone={selected} lastPrice={lastPrice} clock={clock} />
            ) : tab === "plan" ? (
              <PlanPanel
                plan={plans.find((p) => p.zone_id === selected.id) ?? null}
                equity={equity}
                equityFrom={equityFrom}
                onReadAccount={onReadAccount}
                canReadAccount={canReadAccount}
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

function ZoneRow({
  zone,
  lastPrice,
  chartInterval,
  selected,
  onSelect,
}: {
  zone: Zone;
  lastPrice: number | null;
  chartInterval: string;
  selected: boolean;
  onSelect: (id: string | null) => void;
}) {
  return (
    <button
      onClick={() => onSelect(selected ? null : zone.id)}
      className={`flex w-full items-center gap-2 border-b border-line px-3 py-2 text-left transition-colors ${
        selected ? "bg-panel-2" : "hover:bg-panel-2/60"
      }`}
    >
      <span
        aria-hidden
        className="h-6 w-[3px] shrink-0"
        style={{
          // `--demand` / `--supply`, see globals.css for why the pair differs in
          // lightness and for the five files that hold it.
          background: zone.side === "demand" ? "#1f8f5f" : "#ef8f86",
          opacity: zone.state === "broken" ? 0.3 : 1,
        }}
      />
      <span className="min-w-0 flex-1">
        <span className="flex items-baseline gap-2">
          <span className="num text-[12px] font-medium text-text">{zone.kind}</span>
          {zone.timeframe && zone.timeframe !== chartInterval ? (
            <span className="num shrink-0 border border-line-strong px-1 text-[10px] text-accent">
              {zone.timeframe}
            </span>
          ) : null}
          {/* Two flags, two different claims, and the row used to show
              only the first. "forming" means the BOX may still shift;
              "unsettled" means the box is fixed but the departure window
              that decided the gate has not finished printing, so a zone
              shown as passing can still fail. An audit measured a
              confirmed zone's departure_atr growing on 101 of 599 bar
              formations and its state changing 24 times. */}
          <span
            className="truncate text-[11px] text-text-faint"
            title={
              !zone.confirmed
                ? "The leg-out is still the newest run, so the box may still shift"
                : zone.settled
                  ? "Final given closed bars"
                  : "The box is fixed but the departure window is still printing, so the gate verdict can still move"
            }
          >
            {STATE_LABEL[zone.state]}
            {!zone.confirmed ? ", forming" : zone.settled ? "" : ", unsettled"}
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
      {/* Distance leads, ATR follows. Both are measurements and both are
          therefore --text: the ATR figure used to be painted in the accent,
          which put the brightest colour on screen on the least actionable
          number in the row and made a measurement look like a control. */}
      <span className="shrink-0 text-right">
        {lastPrice === null ? null : (
          <span
            className="num block text-[12px] text-text"
            title="Distance from the last close to the nearest edge of this zone, as a share of price. Positive is above price."
          >
            {away(zone, lastPrice)}
          </span>
        )}
        <span
          className="num block text-[10px] text-text-faint"
          title="How far the leg-out ran from this zone, in ATR. The one filter with evidence behind it."
        >
          {zone.departure_atr.toFixed(1)} ATR
        </span>
      </span>
    </button>
  );
}

/** Geometry and risk for the selected zone, and nothing that reads as a call.
 *  The panel leads with what it is NOT, because a box of entry, stop and target
 *  looks like a signal whatever the numbers say. */
function PlanPanel({
  plan,
  equity,
  onEquity,
  equityFrom,
  onReadAccount,
  canReadAccount,
}: {
  plan: TradePlan | null;
  equity: string;
  onEquity: (value: string) => void;
  equityFrom: string | null;
  onReadAccount: () => void;
  canReadAccount: boolean;
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

      {/* READ IT RATHER THAN TYPE IT, where the source can answer. A typed
          account size is stale the moment a position opens, and the percentage
          the plan reports is then a percentage of an account that no longer
          exists - wrong in the direction that hurts, because equity falls in
          drawdown and a stale larger figure sizes UP. */}
      {canReadAccount ? (
        <div className="border-b border-line px-3 py-2">
          <button
            type="button"
            onClick={onReadAccount}
            className="num w-full border border-line-strong px-2 py-1 text-[11px] uppercase tracking-wider text-text-faint transition-colors hover:border-accent hover:text-accent"
          >
            Read from terminal
          </button>
          {equityFrom ? (
            <p className="mt-1 text-[11px] leading-relaxed text-text-faint">
              {equityFrom}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* THE ANSWER "this account cannot take this trade", which the panel used
          to swallow: every plan rendered identically whether or not it could be
          placed, so a size that floors below the venue's minimum looked like a
          tradeable one. Rounding up would risk more than the budget by
          construction, so a refusal is the only honest output. */}
      {plan.placeable ? null : (
        <p
          role="status"
          className="border-b border-supply/40 bg-supply/10 px-3 py-2 text-[11px] leading-relaxed text-supply"
        >
          Akun ini tidak bisa mengambil trade tersebut. Ukuran 1% risikonya jatuh
          DI BAWAH minimum venue, dan membulatkannya ke atas berarti mengambil
          risiko lebih besar dari anggaran - jadi tidak ada lot yang diberikan.
        </p>
      )}

      <dl className="px-3 py-2">
        <Row label="Entry" value={plan.entry.toFixed(2)} />
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
            look authoritative while meaning nothing.

            THREE numbers, not one, and they diverge on small accounts. `units`
            is what the 1% budget implies, `lots` is what the venue will actually
            accept once the size is floored to its step, and `realised_risk` is
            what that floored size really risks. Showing only the first is the
            frictionless reading of position size, the same mistake the cost
            fields below were added to end. */}
        {plan.units !== null ? (
          <Row label="Size at 1% risk" value={`${plan.units} unit`} />
        ) : null}
        {plan.lots !== null ? (
          <Row label="Placeable size" value={`${plan.lots} lot`} />
        ) : null}
        {plan.realised_risk !== null ? (
          <Row
            label="Risk that size really carries"
            value={
              plan.realised_risk.toFixed(2) +
              (plan.realised_risk_pct !== null
                ? ` (${pct(plan.realised_risk_pct)})`
                : "")
            }
          />
        ) : null}
        {plan.margin_required !== null ? (
          <Row
            label="Margin required"
            value={
              plan.margin_required === 0
                ? "none, leverage unlimited"
                : plan.margin_required.toFixed(2)
            }
          />
        ) : null}
        {plan.spread_charged !== null ? (
          <Row label="Spread charged" value={plan.spread_charged.toFixed(2)} />
        ) : null}
        {/* Costs are charged INTO the plan for the first time here; until this
            field existed they lived only in the measurement harness and the
            reward on screen was the frictionless one.

            Never hidden when null, unlike `units` and `spread_charged` above.
            Absent size means "you gave no account", which is the user's own
            doing. Absent cost means "nobody has researched what this symbol
            costs", which is the instrument's gap and reads as free trading
            unless it is said out loud. */}
        <Row
          label="Cost charged"
          value={
            plan.cost_charged === null
              ? "nothing charged, no schedule"
              : plan.cost_charged.toFixed(2)
          }
        />
        <Row
          label="Cost as share of reward"
          value={
            plan.cost_share_of_reward === null
              ? "tidak terukur"
              : pct(plan.cost_share_of_reward)
          }
        />
        <Row
          label="Carry per night"
          value={
            plan.carry_per_night === null
              ? "tidak terukur"
              : plan.carry_per_night.toFixed(5)
          }
        />
      </dl>

      <p className="border-t border-line px-3 py-2 text-[11px] leading-relaxed text-text-faint">
        {plan.cost_charged === null
          ? "Tidak ada jadwal biaya untuk simbol ini, jadi TIDAK ADA yang dibebankan. Itu bukan berarti gratis, itu berarti belum diukur - reward di atas adalah reward tanpa gesekan."
          : "Angka biaya inilah yang menentukan sebuah edge bertahan atau tidak. Pada jadwal komisi emas yang benar-benar bisa diambil, biaya memakan 20,5% dari R dan walk-forward out-of-sample-nya jatuh dari 8 dari 8 slice menjadi 4 dari 8. Malam yang ditahan adalah asumsi, bukan ukuran - kalikan sendiri carry di atas."}
      </p>

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

function Inspector({
  zone,
  lastPrice,
  clock,
}: {
  zone: Zone;
  lastPrice: number | null;
  /** The one clock the whole app prints in, chosen beside the chart. */
  clock: ClockZone;
}) {
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
        <Row label="Proximal" value={zone.proximal.toFixed(2)} />
        <Row label="Distal" value={zone.distal.toFixed(2)} />
        <Row label="Height" value={height.toFixed(2)} />
        {away ? <Row label="Distance from price" value={`${away}%`} /> : null}
        <Row label="Departure" value={`${zone.departure_atr.toFixed(2)} ATR`} />
        {/* Shown only when false, next to the number it qualifies: departure is
            what the gate reads, and until the window has printed in full this
            zone's verdict is provisional even though its box is fixed. */}
        {zone.settled ? null : (
          <Row label="Settled" value="no, departure still printing" />
        )}
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
          <Row label="Road shut" value={`${stampIn(zone.crowded_at, clock)}`} />
        ) : null}
        {/* Two range readings, and they are NOT the same reading twice. `curve`
            is the Seiden one: a rolling 200-bar range split in thirds and frozen
            when the zone was born. `dealing_range_pos` is the ICT one: the
            position at the moment price ARRIVES, on a range anchored to the last
            confirmed swing high and low. Both are labelled with which school and
            which moment they belong to, because a reader who sees two
            percentages next to each other will otherwise take one for a stale
            copy of the other. */}
        <Row
          label="Curve, at birth, 200 bars"
          value={`${(zone.curve * 100).toFixed(0)}%${zone.curve_favourable ? ", favourable" : ""}`}
        />
        <Row
          label="Dealing range, at first touch"
          value={
            zone.dealing_range_pos === null
              ? "not touched yet"
              : `${(zone.dealing_range_pos * 100).toFixed(0)}%`
          }
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

      {/* Deliberately not coloured, not ranked and not called favourable, unlike
          the `curve` row above it. On one series both sides read high - demand
          0,603 and supply 0,560 - which is the same drift pattern that exposed
          `curve` itself as an artefact. Until that is resolved a premium/discount
          reading is a description of where price was, not a mark out of ten. */}
      <p className="border-b border-line px-3 pb-2 text-[11px] leading-relaxed text-text-faint">
        Dua bacaan rentang, bukan satu angka yang diulang. Curve dibekukan saat
        zona lahir; dealing range dibaca saat harga benar-benar datang. Keduanya
        deskripsi, bukan nilai - jangan dibaca sebagai bagus atau buruk.
      </p>

      {zone.inverted_at !== null ? (
        <div className="border-t border-line px-3 py-2">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
            Peran berbalik
          </h4>
          <dl>
            <Row label="Closed through" value={`${stampIn(zone.inverted_at, clock)}`} />
            <Row
              label="Band is now"
              value={zone.side === "demand" ? "demand" : "supply"}
            />
          </dl>
          {/* The honesty requirement, stated where the box is, not in a handbook
              nobody opens mid-session. H8 built the one subsample this project
              never had - 11.469 first touches all approach a box from the near
              side and ZERO come through it - and measured the forward move after
              a post-inversion touch against a control that knows only the
              trailing 20-bar move and has no box at all. */}
          <p className="mt-1.5 border-l-2 border-supply pl-2 text-[11px] leading-relaxed text-text-dim">
            Yang berubah cuma PERAN kotak ini, bukan arah harga. Diukur, tahu
            sebuah kotak sudah berbalik membuat tebakan arah LEBIH BURUK
            ketimbang cuma tahu ke mana harga baru saja bergerak: -0,179 (S&amp;D),
            -0,165 (FVG) dan -0,274 (OB), ketiganya negatif signifikan. Jadi
            kotak ini bukan kotak yang lebih kuat dan bukan sinyal.
          </p>
        </div>
      ) : null}

      {zone.displacement ? (
        <div className="border-t border-line px-3 py-2">
          <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
            Displacement
          </h4>
          <dl>
            <Row label="Size" value={`${zone.displacement.atr.toFixed(2)} ATR`} />
            <Row
              label="Leg"
              value={`${stampIn(zone.displacement.time_from, clock)} to ${stampIn(zone.displacement.time_to, clock)}`}
            />
            <Row label="Left a gap" value={zone.displacement.left_gap ? "yes" : "no"} />
            {/* Three states, not two. Null means the test was never run because
                no structure was computed for this request, and rendering that as
                "no" would report a check that never happened as a check the leg
                failed. ICT states displacement STRUCTURALLY; this engine has
                only ever tested it as a size, which is the departure this object
                exists to make visible. */}
            <Row
              label="Broke structure"
              value={
                zone.displacement.broke_structure === null
                  ? "not tested"
                  : zone.displacement.broke_structure
                    ? "yes"
                    : "no"
              }
            />
          </dl>
          {zone.displacement.broke_structure === null ? (
            <p className="mt-1.5 border-l-2 border-line-strong pl-2 text-[11px] leading-relaxed text-text-faint">
              &quot;Not tested&quot; bukan &quot;tidak&quot;. Kotak ini lolos
              ambang UKURAN saja; syarat strukturnya tidak pernah diuji karena
              overlay struktur tidak dihitung untuk permintaan ini.
            </p>
          ) : null}
        </div>
      ) : null}

      {zone.kind === "OB" || zone.kind === "BRK" ? (
        <div className="border-t border-line px-3 py-2">
          <dl>
            <Row
              label="Structure break required"
              value={
                zone.structure_break_time === null
                  ? "no, admitted without one"
                  : `${stampIn(zone.structure_break_time, clock)}`
              }
            />
          </dl>
          {zone.structure_break_time === null ? (
            <p className="mt-1.5 border-l-2 border-line-strong pl-2 text-[11px] leading-relaxed text-text-faint">
              Gerbang <span className="num">require_structure_break</span> mati,
              jadi blok ini masuk tanpa syarat struktural apa pun. Ini default
              mesin dan sekaligus penyimpangan terbesarnya dari ICT.
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="border-t border-line px-3 py-2">
        <h4 className="mb-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-text-faint">
          Formation
        </h4>
        <p className="mb-2 text-[11px] leading-relaxed text-text-faint">
          How cleanly the zone was built. Tested against outcomes and it does not
          predict them: on 2707 resolved zones across five series it ranks
          BACKWARDS, AUC 0.464 and 0.477, so a higher score goes with a slightly
          worse outcome. It orders the display and nothing else - read it as
          description, never as a rating and never as opportunity.
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
                scores on. Each factor caps at one third. Drawn in a hairline
                rather than in the accent for the same reason the total below is
                the quietest number here: it is a share of a figure that ranks
                backwards, and a bright bar reads as a rating. */}
            <div
              className="mt-0.5 h-[2px] bg-line-strong"
              style={{ width: `${Math.min(100, contribution * 300)}%` }}
            />
          </div>
        ))}
        {/* The quietest number on the panel, deliberately, and it used to be the
            loudest. `formation_score` measures how cleanly a zone was BUILT and
            its own field description in backend/app/models/zone.py says it is worse
            than useless as a ranking - AUC 0.464 and 0.477 on 2707 resolved
            zones, i.e. backwards. Painting it in the brightest colour on screen
            was the interface arguing against the measurement. */}
        <div className="mt-2 flex items-baseline justify-between border-t border-line pt-2">
          <span className="text-[11px] text-text-faint">Formation score</span>
          <span className="num text-[11px] text-text-faint">
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

/** Every row in every dl on this panel is a MEASUREMENT, so every row is
 *  --text-dim and there is no way to make one of them gold. The prop existed
 *  and picked out Entry, Proximal and the cost share; the accent means "the
 *  setting you chose" and none of the three is a setting. */
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 py-[3px]">
      <dt className="text-[11px] text-text-faint">{label}</dt>
      <dd className="num text-[12px] text-text-dim">{value}</dd>
    </div>
  );
}

/** Signed distance from the last price to the zone, as a share of price: `+` is
 *  above price, `-` is below, and price inside the box is said in words because
 *  "0.00%" reads as a rounding artefact when it is the most actionable row on
 *  the panel. A share rather than points, so the column means the same thing on
 *  gold at 4400 and on a pair at 1.09. */
function away(zone: Zone, price: number): string {
  const gap = distance(zone, price);
  if (gap === 0) return "at price";
  return `${zone.bottom > price ? "+" : "-"}${((gap / price) * 100).toFixed(2)}%`;
}

function distance(zone: Zone, price: number): number {
  if (price > zone.top) return price - zone.top;
  if (price < zone.bottom) return zone.bottom - price;
  return 0;
}
