/** Mirrors backend/app/models/. Kept hand-written and small on purpose: a
 *  generated client would be more machinery than four interfaces are worth. */

/** IFVG and BRK are an existing box read from the other side after price closed
 *  through it, not new geometry. `side` is the side the box BECAME. */
export type ZoneKind = "RBR" | "DBR" | "DBD" | "RBD" | "FVG" | "OB" | "IFVG" | "BRK";
type ZoneSide = "demand" | "supply";
export type ZoneState = "fresh" | "tested" | "mitigated" | "broken";

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface Anatomy {
  leg_in_from: number;
  leg_in_to: number;
  /** Start of the WHOLE consolidation. Differs from base_from when a long
   *  pause was clipped to the bars the move actually left from. */
  base_run_from: number;
  base_from: number;
  base_to: number;
  leg_out_from: number;
  leg_out_to: number;
}

export interface Refinement {
  /** Interval of the candles the refined box was cut from. */
  timeframe: string;
  from_top: number;
  from_bottom: number;
  /** Refined height as a fraction of the original, 0..1. */
  shrank_to: number;
  bars: number;
  time_from: number;
  time_to: number;
}

/** The leg that qualified an imbalance box, reported as an object rather than
 *  reduced to the threshold it passed. On FVG, OB, IFVG and BRK only. */
export interface Displacement {
  time_from: number;
  time_to: number;
  /** Size of the leg in ATR before the box. */
  atr: number;
  /** Null means NOT TESTED - no structure was computed for this request - which
   *  is not the same as false and must never be rendered as it. ICT states
   *  displacement structurally; this engine has only ever tested it as a size. */
  broke_structure: boolean | null;
  left_gap: boolean;
}

export type StructureScale = "swing" | "internal";
type StructureKind = "BOS" | "CHoCH" | "SWEEP" | "MSS";

/** A cross-instrument divergence, positioned on THIS symbol's own price so it
 *  can be drawn. The same event appears in the checklist as `SSMTHit`, which is
 *  the reading; this is the shape. The partner's two prices ride along as
 *  evidence and must never be plotted on this axis - they belong to a different
 *  instrument's price scale. */
/** One projected level off a defining range. The source gives the multiples and
 *  NOT a direction, so both sides are computed and each level says which it is
 *  on - picking one would be inventing the half nobody published. */
export interface DFRExtension {
  multiple: number;
  side: "above" | "below";
  price: number;
}

/** The defining range as a SHAPE: Q1's final two thirds, its midpoint, and its
 *  projections. The checklist reports the same object as a READING, without
 *  projections. Bounded in time as well as price, unlike a gap band. */
export interface DefiningRangeBand {
  degree: string;
  cycle_start: number;
  time_from: number;
  time_to: number;
  high: number;
  low: number;
  equilibrium: number;
  extensions: DFRExtension[];
}

export interface SSMTDivergence {
  degree: string;
  side: "high" | "low";
  partner: string;
  /** True when the CHART's symbol took the previous quarter's extreme and the
   *  partner failed. The whole direction of the reading; the label means
   *  nothing without it. */
  self_took: boolean;
  time_from: number;
  price_from: number;
  time_to: number;
  price_to: number;
  partner_prior: number;
  partner_now: number;
  /** Close of the second quarter. Drawing the segment back at `time_from` is
   *  correct; ACTING on it before this is hindsight. */
  knowable_at: number;
  /** Where this divergence's own extreme sat in the dealing range knowable at
   *  the bar it printed on: 0 at the range low, 1 at the high. Null until both
   *  sides of the range have confirmed - never a substituted 0.5.
   *
   *  The reading a practitioner named as the one that decides whether a
   *  divergence is tradeable at all: FVG, OB, REQH, REQL and CISD have to be in
   *  premium to sell and in discount to buy, and a divergence OUTSIDE those
   *  zones is evidence about where the draw is rather than a trade. Reported and
   *  never scored - the raw range position looked like this project's strongest
   *  finding until it was split by side, and then it was upward drift. */
  range_pos: number | null;
  /** True when the candle that printed the new extreme follows the practitioner's
   *  rule: bullish SSMT needs a bearish candle, bearish needs a bullish one.
   *  Null when the candle could not be found. */
  candle_valid: boolean | null;
  /** The kill zone active at the quarter close. Asia is weaker than London/NY. */
  session: string | null;
}

/** Regular SMT: non-sequential, running-extreme comparison. Liquidity reading. */
export interface SMTDivergence {
  degree: string;
  side: "high" | "low";
  partner: string;
  self_took: boolean;
  time_at: number;
  price_at: number;
  partner_price: number;
  knowable_at: number;
  session: string | null;
}

export interface SwingPoint {
  time: number;
  price: number;
  high: boolean;
  /** The bar this pivot became KNOWABLE on, always later than `time`. The marker
   *  belongs at `time`, but nothing in the UI may imply the swing was available
   *  before this: that single rule is what separates the overlay from hindsight,
   *  and the backend asserts it in tests rather than trusting it. */
  confirmed_at: number;
  scale: StructureScale;
}

export interface StructureEvent {
  /** Open time of the bar that broke or swept. */
  time: number;
  kind: StructureKind;
  /** +1 broke or swept upward, -1 downward. A fact about the bar, not a forecast:
   *  H6 and H9 tested exactly these objects for direction and both were null. */
  direction: number;
  level: number;
  swing_time: number;
  bias_before: number;
  scale: StructureScale;
  /** Three-valued and null is NOT false. Null means the question has no answer:
   *  a swing-scale event, where it does not apply, or no major structure
   *  established yet. False means the major structure pointed the OTHER way. */
  aligned_with_swing: boolean | null;
  /** SWEEP only: bars until price closed back inside the swept level, null if it
   *  never did. The sources describe a sweep as liquidity taken AND rejected, so
   *  null is the taking without the rejection rather than a missing number. */
  reversed_within: number | null;
  /** MSS only: the sweep that qualified this break. An MSS is emitted ALONGSIDE
   *  the break it was carved out of, so one bar can carry two events. */
  swept_at: number | null;
}

/** Knobs for the structure OVERLAY. Not a detector: it draws no boxes, so it
 *  cannot be capped per side. Membership in `layers` is what switches it on -
 *  it used to carry its own `enabled`, which was a second spelling of the same
 *  intent and the reason the UI had to know which drawings were which. */
export interface StructureParams {
  swing_n: number;
  internal_n: number;
  sweep_reversal_bars: number;
  mss_window: number;
  /** Newest events kept, for readability. 0 means no cap, and any MEASUREMENT
   *  must pass 0 - a recency cap silently confines a sample to the tail of the
   *  history, which has already cost this project one round of calibration. */
  max_events: number;
}

export interface Zone {
  id: string;
  kind: ZoneKind;
  side: ZoneSide;
  state: ZoneState;
  /** Which timeframe's candles formed this zone. Higher than the chart's own
   *  interval means it was projected down from a top-down pass. */
  timeframe: string;
  /** Higher timeframes whose same-side zone encloses this one and predates it.
   *  Measured and found not to help; reported because it is the one MTF rule
   *  every school of the method asserts. */
  nested_in: string[];
  /** One-way travel across the base as a fraction of its height. Near 1 means
   *  the base was a staircase rather than a pause. Reported, not filtered. */
  base_drift: number;
  base_overlap: number;
  top: number;
  bottom: number;
  proximal: number;
  distal: number;
  time_from: number;
  time_to: number;
  /** How cleanly the zone was built. Calibration says it does not predict what
   *  price does on the return, so it orders the display and nothing else. */
  formation_score: number;
  departure_atr: number;
  /** Leg-out travel as a multiple of the zone's own height. The doctrine's own
   *  test, which asks for 3; calibration puts the knee nearer 2. */
  profit_margin: number;
  /** Position in the prevailing range, 0 at the low and 1 at the high. The
   *  doctrine's "curve". Measured: its side-adjusted form does not predict. */
  curve: number;
  curve_favourable: boolean;
  /** Distance to the nearest live opposing zone, in units of this zone's own
   *  height. Null when nothing stands in the way. */
  profit_zone_rr: number | null;
  /** When a newly formed OPPOSING zone first shut the road, epoch seconds.
   *  Driven by other zones rather than by price, which is why it is not a
   *  `state`. Null unless the road check is switched on and did fire. */
  crowded_at: number | null;
  /** Set when the box was shrunk to the lower-timeframe base inside it. Carries
   *  the geometry it had before, so the change can be audited. */
  refinement: Refinement | null;
  /** IFVG and BRK only: when price closed through the ORIGINAL box, so the band
   *  changed role. A fact about the drawing and nothing more - H8 measured the
   *  forward move after a post-inversion touch against a control that knows only
   *  the trailing 20-bar move, and all three detectors came out significantly
   *  NEGATIVE. Knowing a box had inverted made a directional guess worse. */
  inverted_at: number | null;
  /** ICT premium/discount at the FIRST TOUCH, on a range anchored to the last
   *  confirmed swing high and low. Null until touched. NOT `curve`, which is the
   *  Seiden reading on a rolling 200-bar range frozen at birth - both are shown
   *  because a reader who sees one will otherwise take the other for a duplicate.
   *  Never scored or coloured: on one series both sides read high (demand 0.603,
   *  supply 0.560), the same drift pattern that exposed `curve` as an artefact. */
  dealing_range_pos: number | null;
  /** Null for detectors that have no displacement concept. */
  displacement: Displacement | null;
  /** Order block only, and only when `require_structure_break` was on. Null means
   *  the block was admitted with NO structural requirement, which is this
   *  engine's default and its largest remaining ICT departure. */
  structure_break_time: number | null;
  /** How hard price travelled in before the first touch, in ATR. Null until
   *  touched. Sources disagree on whether fast is good; measured, it is
   *  indistinguishable either way. */
  arrival_atr: number | null;
  touches: number;
  penetration_pct: number;
  first_test_time: number | null;
  /** False while the leg-out is still the newest run, so the BOX may still
   *  shift. Not finality: read it as `leg_out_open`, inverted. */
  confirmed: boolean;
  /** Every reported field is final given closed bars: the leg-out has ended AND
   *  the departure window that decided the gate has fully printed. A zone can be
   *  confirmed and not settled, and then its GATE VERDICT can still move. */
  settled: boolean;
  anatomy: Anatomy;
  factors: Record<string, number>;
  note: string;
}

export interface SupplyDemandParams {
  atr_period: number;
  impulse_body_ratio: number;
  impulse_atr: number;
  base_max_bars: number;
  base_max_atr: number;
  max_base_drift: number;
  departure_min_atr: number;
  departure_lookahead: number;
  proximal_basis: "wick" | "body";
  min_profit_margin: number;
  /** Clear road a zone needs ahead of it, in units of its own height. Above 0
   *  it also filters. Ships at 0, i.e. reported only: it ranks in sample but
   *  does not survive walk-forward. */
  min_profit_zone_rr: number;
  zone_min_atr: number;
  mitigation_pct: number;
  show_broken: boolean;
  show_mitigated: boolean;
  max_zones_per_side: number;
  merge_overlap_pct: number;
}

/** Shared by the fvg, order_block, ifvg and breaker detectors, which is why the
 *  menu renders these knobs ONCE under the first of them that is on: an IFVG is
 *  an FVG plus one more event, and a second gap threshold for it would let the
 *  two populations drift apart. Deliberately small: none of them carries a
 *  score, so there is nothing to weight and nothing to retract. */
export interface ImbalanceParams {
  atr_period: number;
  min_gap_atr: number;
  displacement_atr: number;
  displacement_bars: number;
  mitigation_pct: number;
  arrival_bars: number;
  /** Order block only: demand that the block's impulse CLOSE beyond a confirmed
   *  swing rather than merely travel `displacement_atr`. The contested rule and
   *  the engine's biggest ICT departure, and it ships OFF because the figures
   *  usually quoted to justify requiring it (52% against 65-68% on 2,400 setups)
   *  are untraceable, so neither camp has evidence. Measured here on 600 hourly
   *  gold bars it cut the order block from 23 boxes to 10 and rejected 84
   *  candidates - two thirds of the drawing, on a rule nobody has tested against
   *  outcomes. The three fields below it were on the wire and absent from this
   *  type, so the switch could not be sent at all. */
  require_structure_break: boolean;
  /** Bars after the block candle in which the qualifying break must happen. The
   *  same window the size test uses, so switching the gate on changes the TEST
   *  and not the window. Read only when `require_structure_break` is on. */
  structure_break_bars: number;
  /** Fractal width of the swings that break is tested against. Read only when
   *  `require_structure_break` is on. */
  structure_n: number;
  show_broken: boolean;
  show_mitigated: boolean;
  max_zones_per_side: number;
}

/** What a trade at one zone would look like, with no view on whether to take
 *  it. Every price is geometry; nothing here says which way price goes. */
export interface TradePlan {
  zone_id: string;
  /** Which side the zone is, NOT a recommendation. */
  side: ZoneSide;
  entry: number;
  stop: number;
  /** The nearest live opposing zone. Null when there is no wall ahead, and left
   *  null rather than filled with a conventional R multiple. */
  target: number | null;
  risk_per_unit: number;
  reward_r: number | null;
  /** Only when an account equity was supplied. NOMINAL: the size the budget
   *  implies before the venue's step and minimum are applied. `lots` is what an
   *  order can actually carry and `realised_risk` is what it actually risks. */
  units: number | null;
  /** The size an order can actually carry: floored to the venue's step and
   *  clamped to its maximum. Null when no equity was given, or when the trade is
   *  not placeable at all. */
  lots: number | null;
  /** False when the size floors BELOW the venue's minimum, i.e. this account
   *  cannot take this trade. Rounding up instead would risk more than the budget
   *  by construction, so the honest answer is a refusal. The panel used to show
   *  a plan and never mention that it could not be placed. */
  placeable: boolean;
  /** What the FLOORED size actually risks, including commission. Not the
   *  budget: one step is a large fraction of a small account's budget, so
   *  nominal and realised diverge sharply there and only this figure is true. */
  realised_risk: number | null;
  realised_risk_pct: number | null;
  /** At the stated leverage. Zero when leverage is unlimited. */
  margin_required: number | null;
  age_bars: number;
  /** Measured survival of the cohort this zone belongs to, not this trade's
   *  probability, and it excludes costs. */
  departure_held_rate: number;
  /** Same kind of number for the age band. Not independent of
   *  `departure_held_rate`, so the two must never be multiplied. */
  age_held_rate: number;
  /** Null when the feed publishes no spread, so nothing was charged. */
  spread_charged: number | null;
  /** Everything a round turn costs in price units: spread, commission, slippage
   *  and carry. Null means NO COST SCHEDULE EXISTS for this symbol, so nothing
   *  was charged - which is not free trading, it is unmeasured, and `warnings`
   *  says so. Until this field existed the reward on screen was frictionless. */
  cost_charged: number | null;
  /** `cost_charged` as a fraction of the distance to target: the number that
   *  decides whether an edge survives. At the retrievable gold commission
   *  schedule it took 20.5% of R and the walk-forward fell from 8 of 8 slices to
   *  4 of 8. Null when there is no cost schedule or no measurable target. */
  cost_share_of_reward: number | null;
  /** Charged per rollover held. Separate because the number of nights is an
   *  assumption, not a measurement. */
  carry_per_night: number | null;
  /** Always null. Twelve pre-registered hypotheses failed to get a sign out of
   *  these drawings, so the field is a finding rather than a gap. */
  direction_evidence: null;
  warnings: string[];
}

/** One thing the advisor can say, with the doc section that explains it. */
export interface Note {
  topic: string;
  text: string;
  /** Anchor of the /docs section that teaches this, or null when the note is a
   *  warning specific to this zone rather than a concept. */
  learn: string | null;
}

export interface Advice {
  zone_id: string;
  /** The final note is always what CANNOT be known, and the backend enforces
   *  that ordering with a test. */
  notes: Note[];
}

/** One quarter of one cycle in the New York grid. A fact about the clock: it
 *  says nothing about what price did inside it. */
export interface SessionQuarter {
  degree: string;
  label: "Q1" | "Q2" | "Q3" | "Q4";
  time_from: number;
  /** Exclusive. One quarter's close IS the next one's open, which is why the
   *  chart draws only opening edges. */
  time_to: number;
}

/** The opening price of a cycle's Q2, which is what a true open IS - not the
 *  first bar of the cycle. The daily true open is midnight New York precisely
 *  because midnight is the day cycle's Q2.
 *
 *  A level exists only where a bar opened exactly on the boundary. Over weekends
 *  and holidays none did, and then there is no level: nothing is carried forward
 *  and nothing interpolated. `meta.session.true_opens_missing` counts those, so a
 *  reader can tell "the feed had no bar" from "the engine forgot". */
export interface TrueOpenLevel {
  degree: string;
  /** The Q2 boundary this level belongs to. */
  time: number;
  price: number;
  /** Open time of the bar the price came from. Equal to `time` unless
   *  `approximate`. */
  bar: number;
  /** True when no bar opened on the boundary and the first bar after it was used
   *  instead. Drawn DASHED and tagged with a ~, the same convention an
   *  approximate gap band uses, because an approximate level and a measured one
   *  must not look alike. Only ever set when the request asked for it. */
  approximate: boolean;
}

/** Which parts of the cycle grid to draw. An OVERLAY like structure: it produces
 *  no boxes and cannot be capped per side. It used to switch ITSELF on by having
 *  a non-empty degree list, which was a third spelling of "enabled" - naming
 *  `session` in `layers` is now the only switch, and empty lists here mean the
 *  layer is on and drawing nothing. */
export interface SessionParams {
  quarters: string[];
  true_opens: string[];
  /** Let a true open be read from the first bar AFTER its boundary when no bar
   *  opened on it, flagged and drawn dashed. Off by default. Required for the
   *  quadrennial degree to produce anything at all. */
  approximate_true_opens: boolean;
  max_quarters: number;
}

/** Seven, which is his own nesting list: Yearly, Monthly, Weekly, Daily, 90M,
 *  Micro, Nano. `nano` sits outside the backend's `DEGREES` tuple on purpose -
 *  the accuracy harness iterates that tuple and would need its documented-hole
 *  table extended in the same commit - but `quarters()` accepts it, so the UI
 *  can offer it today. */
/** The eight cycle degrees, coarsest first.
 *
 *  `quadrennial` is the four-year cycle whose Q2 is the United States
 *  presidential election year, so 2024 and 2028 are Q2 and 2026 is Q4. It was
 *  added because a practitioner named the omission directly: the quarterly cycle
 *  he named alongside it was already here under the name `year`, which cuts at 1
 *  January, 1 April, 1 July and 1 October - Q1 Jan-Mar through Q4 Oct-Dec. Only
 *  the cycle above it was missing.
 *
 *  Its true open needs `approximate_true_opens`, and that is not a detail: the
 *  quadrennial Q2 boundary is 1 January, the market is shut on 1 January every
 *  year, and under the strict rule the level therefore never exists. */
export const DEGREES = [
  "quadrennial", "year", "month", "week", "day", "session", "micro", "nano",
] as const;

/** The owner's own pre-trade checklist, computed rather than asserted.
 *
 *  OFF BY DEFAULT, and that is a cost decision as much as a caution: the zone
 *  detectors read bars already fetched, these do not. Bias costs one provider
 *  call per timeframe and SSMT one per instrument, so a fully specified request
 *  turns one call into eight. The response reports how many it made. */
/** The defining range. Its own block rather than a corner of the cycle grid:
 *  the grid is a fact about the clock and this is a reading of the price
 *  inside one quarter of it. Single-sourced and never verified. */
export interface DFRParams {
  degrees: string[];
  /** The source's own numbers, -0.5 and -1, drawn on BOTH sides because it
   *  gives no direction for them. */
  extensions: number[];
  equilibrium: boolean;
  /** Newest bands drawn. Each band carries its own extension levels, so this
   *  multiplies: 20 bands with two multiples is 100 objects. */
  max_ranges: number;
}

export interface ChecklistParams {
  degree: string;
  /** Which range "In discount?" is measured against. All three are computed and
   *  returned regardless; this only picks which one is `chosen`. */
  discount_anchor: string;
  /** Degrees to read the quarter chain at, outermost first. His examples are
   *  three digits but never name the degrees, so there is no default worth
   *  inventing. Empty skips it and costs nothing. */
  chain_degrees: string[];
  bias_timeframes: string[];
  bias_bars: number;
  ssmt_symbols: string[];
  ssmt_degrees: string[];
  /** Source for the SSMT basket, the chart's own symbol included in it. null is
   *  the chart's source. Set it when the venue you trade and the complex you
   *  read divergence across are not the same one: charting the local MT5
   *  terminal reads gold as the broker's spot CFD, and "yahoo" reads the whole
   *  basket as COMEX instead (GC=F, SI=F, HG=F, PL=F, PA=F). Either way the
   *  basket is ONE venue, because gold from one against silver from another
   *  diverges on two session calendars rather than on the market. */
  /** Newest divergences DRAWN. The count is multiplicative - partners times
   *  degrees times two sides - so this fills faster than any other overlay's
   *  cap: two partners and two degrees on 2000 bars produced 1312 segments.
   *  0 draws them all, and a measurement must pass 0. */
  ssmt_max: number;
  ssmt_provider: string | null;
}

interface DegreeBias {
  timeframe: string;
  /** -1, 0 or null. THREE different facts: null is "too few bars to say", 0 is
   *  "no break has happened yet", and neither may be read as agreement. */
  bias: number | null;
  bars: number;
  needs: number;
  last_break: "BOS" | "CHoCH" | null;
  /** True on a CHoCH, false on a BOS, null when nothing has broken. */
  reversal_confirmed: boolean | null;
  reason: string | null;
}

interface BiasAlignment {
  degrees: DegreeBias[];
  aligned: boolean;
  direction: number | null;
  disagreeing: string[];
}

/** The band between one session's last traded price and the next session's first.
 *
 *  NDOG is the 17:00-to-18:00 New York gap on a Monday through Thursday evening;
 *  NWOG is the same geometry across the weekend. `ce` is the consequent
 *  encroachment, the midpoint, and it is the measurement rather than the frame -
 *  the same reason a quarter box draws its own midline.
 *
 *  READ `approximate`. ICT requires 1m or 5m bars for these and forbids reading
 *  them off a daily chart, because a daily bar's close is the SETTLEMENT price
 *  and settlement is a different number from the last price that actually traded
 *  before 17:00. Hourly bars come out exact; 4-hour bars never do. */
export interface OpeningGap {
  kind: "NDOG" | "NWOG";
  top: number;
  bottom: number;
  ce: number;
  close_time: number;
  /** Also when the band became knowable: its second price printed here. */
  open_time: number;
  approximate: boolean;
}

/** One price: the average of a gap's top and the bottom of the next gap UP.
 *
 *  A LEVEL, not a band. The name collides in the wild - the script the owner
 *  works from uses "event horizon" for the gap ZONE - and this is the ICT
 *  reading. Adjacency is in PRICE order, not time, so N gaps give N-1 levels.
 *
 *  This is the ONLY object the chart draws whose value is not fixed at birth: a
 *  new gap appearing between two existing ones re-sorts the pairing and moves a
 *  level already on screen without a single price changing. */
/** One zone per gap kind, reduced from the latest few gaps of that kind.
 *
 *  The reference indicator draws these rather than one per gap. THREE PER KIND
 *  is the owner's own number, confirmed directly.
 *
 *  But HOW three become one top and one bottom is UNRESOLVED: none of the four
 *  reductions tried reproduces the reference's published table, on data that
 *  agrees with it on price to 5 points. So `reduction` travels on every zone,
 *  and a reader must not treat the drawn band as the reference's band. */
/** One scheduled economic release. A fact about the CLOCK, like a quarter
 *  boundary, not a fact about price.
 *
 *  `impact` is the FEED'S OWN LABEL for how much attention an event draws. It is
 *  not a forecast and not a measured effect - and with this source it cannot
 *  become one, because only the current week is published and there is no
 *  history to test against.
 *
 *  `forecast` and `previous` are empty when the feed gave none. Empty means the
 *  feed said nothing, never zero. The feed publishes no actual value at all,
 *  which is what makes it safe to draw on a live chart: it cannot leak an
 *  outcome backwards onto a bar. */
export interface NewsEvent {
  time: number;
  title: string;
  currency: string;
  /** The feed's own label, verbatim. Not a union: the source also publishes
   *  rows like `Holiday`, and narrowing here would discard real calendar data. */
  impact: string;
  forecast: string;
  previous: string;
  /** Open time of the bar the release happened DURING, which is what the chart
   *  can ask the time scale about. `time` itself usually cannot be asked: 08:30
   *  New York is 12:30 UTC and no hourly bar opens then. */
  bar: number;
  /** How far into that bar the release fell, 0 at its open and 1 at the next.
   *  Multiplied by the bar spacing, so 08:30 lands between the 12:00 and 13:00
   *  candles instead of being dropped. */
  offset: number;
}

export interface NewsParams {
  /** High only by default: the sampled week held 75 Low rows against 8 High. */
  impacts: string[];
  /** Empty keeps every currency, which is the honest default cross-asset. */
  currencies: string[];
}

export const NEWS_IMPACTS = ["High", "Medium", "Low"] as const;

export interface TierHorizon {
  kind: "NDOG" | "NWOG";
  reduction: string;
  top: number;
  bottom: number;
  ce: number;
  knowable_at: number;
  open_times: number[];
}

/** Two gaps of DIFFERENT kinds whose bands overlap, and by how much.
 *
 *  The reference indicator renders this as `EV STACK W+D` with a percentage. It
 *  was computed and shipped on every gaps response for a while with no
 *  declaration here at all, which meant the chart could not read a construct the
 *  backend was measuring - extra JSON keys do not break TypeScript, so nothing
 *  ever complained.
 *
 *  `fraction` is the overlap height over the SMALLER band's height, and the
 *  backend's own docstring records that this denominator is a RECONSTRUCTION
 *  from one rendered figure rather than a citation: the union and the larger
 *  band would have given 29% and 30% where the label said 91%. */
export interface GapStack {
  top: number;
  bottom: number;
  /** 0 to 1, over the smaller band. */
  fraction: number;
  kinds: string[];
  open_times: number[];
  /** The later of the two gaps'. The stack is anchored here, because this is
   *  when it became knowable. */
  knowable_at: number;
}

export interface EventHorizonLevel {
  price: number;
  knowable_at: number;
  lower_open_time: number;
  upper_open_time: number;
}

/** A close beyond the OPENING price of the last opposing delivery run.
 *
 *  The level is the open of the FIRST candle of that run, not the last, which is
 *  the usual way this construct is coded wrong. First construct here keyed to a
 *  candle's open rather than its extremes, and that matters: on 495 shared gold
 *  bars a 3.84% disagreement about opens became a 29% disagreement about which
 *  bars carry a CISD, because one flipped sign splits or merges a whole run.
 *
 *  Predictive value is UNMEASURED. No arrows, and `direction` says which side of
 *  the level the close landed on, nothing more. */
export interface CISDEvent {
  time: number;
  direction: number;
  level: number;
  run_from: number;
  run_to: number;
  run_length: number;
}

/** A named session's extreme, as a candidate target. BSL is the high, SSL the low.
 *
 *  A taken pool is still drawn. "London high already got taken" is the fact that
 *  kills a trade idea, so hiding it would hide the reason. `covered` is a fact
 *  about the FEED and `taken_at` a fact about the market: a partial window's high
 *  is not the session high, and the two must not read alike. */
export interface LiquidityPool {
  session: string;
  side: "BSL" | "SSL";
  price: number;
  window_from: number;
  window_to: number;
  bars: number;
  covered: boolean;
  knowable_at: number;
  taken_at: number | null;
}

/** Where price sits in one candidate range, and which range that was. */
/** A named horizontal level: PDH, PWL, FRIDAY_HIGH and the rest.
 *
 *  A named ray with its label at the right edge is on 24 of 24 of his own
 *  annotated charts, so every one of these arrives as one shape with one
 *  vocabulary and the NAME types it. Colour deliberately does not.
 *
 *  `boundary` matters more than it looks: a previous-day high measured
 *  18:00-to-18:00 New York is a DIFFERENT number from one measured
 *  midnight-to-midnight, so the choice travels with the level. */
export interface NamedLevel {
  name: string;
  price: number;
  knowable_at: number;
  taken_at: number | null;
  /** Null on a level that rests on neither side, which the internal range
   *  liquidity produces. Nothing in the UI branches on it, so there is no null
   *  arm to write - but a non-null type here would be a lie about the payload. */
  side: "BSL" | "SSL" | null;
  /** True where the price is ARITHMETIC ON OTHER LEVELS rather than one the market
   *  printed - the dealing range's equilibrium and its two quartile boundaries.
   *  The canvas draws these dashed and printed levels solid, which is the
   *  reference set's own convention.
   *
   *  Its own field rather than a reading of `boundary`: the range's high and low
   *  carry `boundary: "range"` too and they ARE printed prices, so the first
   *  version of this rule dashed two lines that should have been solid. */
  derived: boolean;
  boundary: string;
  window_from: number;
  window_to: number;
  /** Seconds of the window with no bars. NOT a covered flag: a day cycle always
   *  ends in a market closure, so a boolean would read False on every correct
   *  level. */
  gap_at_open: number;
  gap_at_close: number;
}

export interface RangeLiquidityReport {
  at: number;
  high: number;
  low: number;
  high_time: number;
  low_time: number;
  knowable_at: number;
  /** Resting at the range's own extremes. */
  external: NamedLevel[];
  /** The unfilled inefficiency inside it, built from the zones already drawn. */
  internal: NamedLevel[];
}

export interface DrawCandidate {
  name: string;
  price: number;
  distance: number;
  knowable_at: number;
}

/** The untaken liquidity above and below, and deliberately never one answer.
 *
 *  Naming the draw is a forecast, and twelve pre-registered directional
 *  hypotheses have failed in this project.
 *
 *  EITHER SIDE MAY BE EMPTY. Price that has run above every previous-period high
 *  leaves nothing untaken above it, and that emptiness is a fact about what has
 *  been swept rather than a vote for the other side. */
export interface DrawOnLiquidity {
  at: number;
  price: number;
  above: DrawCandidate[];
  below: DrawCandidate[];
}

interface ProjectionLevel {
  multiple: number;
  price: number;
  taken_at: number | null;
}

/** A range and the multiples of its own height projected past it.
 *
 *  `price = origin - direction * multiple * height`, with `origin` the range
 *  edge in the direction of travel. The geometry was recovered from image 27 in
 *  `Referensi grup dan Bg Nas` and agrees with that chart's own price tags to 0.4 USD.
 *
 *  DIRECTION IS NEVER INFERRED. On his charts it is read from where price went
 *  after the range, which is hindsight, so the engine draws both ways unless
 *  told which. */
export interface RangeProjection {
  time_from: number;
  time_to: number;
  high: number;
  low: number;
  height: number;
  direction: number;
  origin: number;
  bars: number;
  knowable_at: number;
  label: string;
  levels: ProjectionLevel[];
}

/** Which quarter of each nested degree a bar sits in, as his three-digit chain.
 *
 *  `in_his_list` says the chain is one of the ten he wrote down. It is NOT a
 *  probability: ten of the 64 chains is 15.6%, and nobody has measured whether
 *  the listed ones behave differently. Quote the base rate beside the flag.
 *
 *  And on hourly bars only 28 to 30 of the 64 chains can occur at all, because a
 *  micro quarter is 1350 seconds and an hour is 3600. Six of his ten are then
 *  structurally unreachable rather than rare. */
interface QuarterChain {
  at: number;
  degrees: string[];
  quarters: number[];
  text: string;
  compact: string;
  in_his_list: boolean | null;
  base_rate: number;
}

/** How many true opens price sits above and below. His precondition is that at
 *  least two agree before he acts; this counts them and says nothing more. */
interface OpenStack {
  price: number;
  above: TrueOpenLevel[];
  below: TrueOpenLevel[];
}

export interface LiquidityParams {
  periods: string[];
  boundary: string;
  range_liquidity: boolean;
  /** Draws the dealing range on the CHART: both extremes, the 50% equilibrium and
   *  the two quartile boundaries, as five levels with `boundary: "range"`.
   *
   *  The range has always been computed - `dealing_range_pos` on every box comes
   *  from it, and the zone panel prints that as a percentage - and it only ever
   *  reached a side panel as two numbers. So the frame a reader's zones were being
   *  judged against was the one thing they could not see. Across the 51 reference
   *  charts a dashed 50% line inside a range appears on 36 of them.
   *
   *  Exempt from `max_levels` on purpose: that cap exists to stop forty
   *  previous-period extremes burying the price, and these five describe the
   *  window all forty are read inside. */
  range_frame: boolean;
  /** Relative equal highs and lows, as `REQH 3x` and `REQL 2x`: two or more swings
   *  that printed at almost the same price, where stops rest.
   *
   *  THE CHECKLIST HAS BEEN ASKING FOR THIS OBJECT. The practitioner rule quoted
   *  in the backend's `models/cycle.py` names it beside the ones the engine does
   *  draw - "FVG/OB/REQL/REQH/CISD semuanya harus dalam premium kalo mau sell" -
   *  and nothing drew it.
   *
   *  Fidelity only, the same footing the structure overlay ships on: nothing here
   *  has been measured against outcomes, and there is no score field. */
  equal_levels: boolean;
  /** How far apart two swings may be and still count as equal, in ATR. 0.1 is
   *  what the surveyed open-source implementations use. The other rule in
   *  circulation - a fraction of the LOADED WINDOW's range - is refused, because
   *  it makes the tolerance depend on how many bars the reader picked. */
  equal_tolerance_atr: number;
  draw_candidates: boolean;
  max_levels: number;
}

export interface ProjectionParams {
  sessions: string[];
  /** +1 up, -1 down, 0 draws BOTH and is the default. */
  direction: number;
  levels: number[];
}

export const LIQUIDITY_PERIODS = ["day", "week", "friday", "monday"] as const;
export const TIER_REDUCTIONS = ["envelope", "ce_span", "newest", "eh_span"] as const;

export const DAY_BOUNDARIES = ["cycle", "midnight"] as const;

interface RangeReading {
  anchor: string;
  /** The PARENT degree the window came from, never the one being traded. */
  degree: string;
  time_from: number;
  time_to: number;
  complete: boolean;
  bars: number;
  high: number;
  low: number;
  equilibrium: number;
  /** 0 at the low, 1 at the high, deliberately NOT clipped. */
  position: number;
  reading: "premium" | "discount" | "equilibrium";
}

/** The TIME-anchored premium and discount read, which is the third one here.
 *
 *  `Zone.curve` is anchored to swings and frozen at birth; `dealing_range_pos` to
 *  the last swing pair; this one to a CLOCK, the cycle one degree above the one
 *  being traded. That is the whole point, and it is SINGLE-SOURCED - so every
 *  candidate anchor is returned rather than only the chosen one, and `disagree`
 *  says when they do not agree. Quoting one anchor while another said the
 *  opposite is being misled by the engine rather than by the market. */
interface PremiumDiscount {
  degree: string;
  anchor: string;
  at: number;
  price: number;
  chosen: RangeReading | null;
  readings: RangeReading[];
  /** One entry per anchor that produced nothing, WITH its reason. */
  absent: string[];
  disagree: boolean;
}

/** Opening gaps and the levels between them. An overlay: no boxes, no sides. */
export interface GapParams {
  /** Newest gaps retained before the levels are paired. ICT prefers five; a
   *  common port keeps ten. This does not merely trim the picture - dropping a
   *  gap DELETES a level and re-pairs its neighbours. 0 keeps everything. */
  keep: number;
  /** Gaps per kind behind each tier zone. The owner's own number. */
  tier_keep: number;
  /** envelope, ce_span, newest or eh_span. See TierHorizon: unresolved. */
  tier_reduction: string;
  event_horizons: boolean;
}

export interface CISDParams {
  /** Shortest run allowed to arm a level. 1 makes almost every bar a CISD. */
  min_run: number;
  /** Opposing closes a run absorbs before it ends. Raising it merges runs, which
   *  moves both the level and the bar, so the count is not stable under it. */
  interrupt_tolerance: number;
  /** Newest events DRAWN, matching `StructureParams.max_events` because these are
   *  the same class of object. At the shipped floor, 1200 bars of hourly gold
   *  produce 131 - one on every ninth bar. 0 draws them all. */
  max_events: number;
}

export interface PoolParams {
  sessions: string[];
  /** Newest pools DRAWN, a display limit like `SessionParams.max_quarters`. Two
   *  sessions over 50 days of hourly gold is 212 named rays, which stops being a
   *  chart. At equal age a standing pool outranks a taken one. 0 draws all. */
  max_pools: number;
}

/** Both of ICT's own windows, in New York wall time. London opens at 02:00, which
 *  on the spring-forward day is an hour that does not exist - the backend maps it
 *  to 03:00 and that day's killzone is two real hours. */
export const POOL_SESSIONS = ["asia", "london"] as const;

export const DISCOUNT_ANCHORS = [
  "parent_cycle",
  "parent_previous",
  "previous_quarter",
] as const;

interface DefiningRange {
  degree: string;
  cycle_start: number;
  time_from: number;
  time_to: number;
  high: number;
  low: number;
  /** Midpoint of the range. Part of the object as its source states it - Bucko's
   *  own description gives the DFR a 50% equilibrium line - and it shipped
   *  without one, so the panel showed two numbers and left the reader to halve
   *  them by eye. Derived, never measured, and it makes no claim about price. */
  equilibrium: number;
}

interface CycleProfile {
  degree: string;
  cycle_start: number;
  name: "AMDX" | "XAMD";
  manipulation: "Q2" | "Q3";
  knowable_at: number;
}

interface ManipulationEvent {
  degree: string;
  cycle_start: number;
  profile: "AMDX" | "XAMD";
  quarter_label: "Q1" | "Q2" | "Q3" | "Q4";
  time_from: number;
  time_to: number;
  level: number;
  swing_level: number;
  direction: number;
  sweep_time: number;
}

/** NOT orphaned, despite being imported by nothing: `ChecklistReport.ssmt` is a
 *  list of these and the checklist panel renders one row per hit, with the four
 *  prices as the evidence for it. Only the `export` went.
 *
 *  `quarter_from` and `quarter_to` were declared here after `models/cycle.py`
 *  deleted them, and it documents the deletion: they were written on every hit
 *  and read by nothing, which is provenance that proves nothing because no
 *  reader ever checked it. The quarter is recoverable from `knowable_at`. */
interface SSMTHit {
  degree: string;
  side: "high" | "low";
  /** Instrument that took the previous quarter's extreme, and the one that did
   *  not. Two names, and the four prices below are what makes the disagreement
   *  checkable rather than asserted. */
  took: string;
  failed: string;
  /** The close of the second quarter. A quarter's extreme is not settled until
   *  that quarter has ended, so nothing here was knowable before this. */
  knowable_at: number;
  took_prior: number;
  took_now: number;
  failed_prior: number;
  failed_now: number;
}

/** Every item with its evidence, and deliberately NO overall pass or fail.
 *
 *  The five items have different provenance and different confidence: the
 *  defining range is single-sourced and unverified, manipulation is a clean
 *  conjunction, and the SSMT rate depends entirely on which instruments were
 *  paired. One boolean would hide which item is carrying the weight, and would
 *  present a checklist its owner ticks by hand as something the engine had
 *  validated. Nothing here has been measured against outcomes. */
export interface ChecklistReport {
  degree: string;
  dfr: DefiningRange | null;
  profile: CycleProfile | null;
  manipulation: ManipulationEvent | null;
  /** His third question, "In discount?", and the one item that can answer itself
   *  three ways at once. Read `disagree` before quoting it. */
  discount: PremiumDiscount | null;
  /** A clock fact. Read `base_rate` before quoting `in_his_list`. */
  chain: QuarterChain | null;
  stacked: OpenStack | null;
  bias: BiasAlignment | null;
  ssmt: SSMTHit[];
  /** Why an item is absent, when it is absent for a reason. */
  notes: string[];
}

export interface DrawResponse {
  symbol: string;
  interval: string;
  provider: string;
  htf?: string | null;
  candles: Candle[];
  drawing: {
    zones: Zone[];
    /** Empty unless structure was requested. */
    swings: SwingPoint[];
    structure: StructureEvent[];
    /** The two swing anchors the Fibonacci/OTE grid is drawn over. */
    fibonacci: {
      low: number | null;
      low_at: number | null;
      high: number | null;
      high_at: number | null;
    } | null;
    /** Empty unless a degree was requested. */
    quarters: SessionQuarter[];
    true_opens: TrueOpenLevel[];
    /** Empty unless the ssmt layer was requested. The only overlay that costs a
     *  provider call, because a divergence needs a second instrument. */
    ssmt: SSMTDivergence[];
    smt: SMTDivergence[];
    /** Empty unless the dfr layer was requested. Read off the bars already
     *  fetched, so it costs no provider call. */
    dfr: DefiningRangeBand[];
    /** Empty unless the matching overlay was requested. */
    gaps: OpeningGap[];
    news: NewsEvent[];
    tier_horizons: TierHorizon[];
    gap_stacks: GapStack[];
    event_horizons: EventHorizonLevel[];
    cisd: CISDEvent[];
    pools: LiquidityPool[];
    levels: NamedLevel[];
    projections: RangeProjection[];
  };
  /** One per drawn zone, in the same order as `drawing.zones`. */
  plans: TradePlan[];
  advice: Advice[];
  /** Readings rather than shapes, so they ride here beside the checklist. */
  range_liquidity: RangeLiquidityReport | null;
  draw_on_liquidity: DrawOnLiquidity | null;
  /** Present only when the checklist was requested and enabled. */
  checklist: ChecklistReport | null;
  meta: {
    /** Every DETECTOR's counters arrive keyed by the layer's own registry id -
     *  the five named below, plus whatever the backend adds next - so the filter
     *  trace can be driven by `config.layers` instead of by a detector list
     *  typed here. `unknown` rather than `Record<string, number>` because the
     *  named blocks below are not all flat number maps, and an index signature
     *  has to cover every one of them. */
    [block: string]: unknown;
    /** Both numbers, always: vendors cap a page at their own limit, and a short
     *  answer is otherwise indistinguishable from a quiet market. */
    bars_requested?: number;
    bars_returned?: number;
    truncated_by_provider?: boolean;
    /** Open time of the NEWEST BAR the drawing describes, its close, and when
     *  the bar after it is due. A live chart that cannot say which bar it
     *  describes is asking to be trusted on nothing. */
    as_of?: number;
    bar_closed_at?: number;
    next_close_at?: number;
    /** Seconds between that bar's close and the moment the server answered. The
     *  gap is real and varies by provider - binance is seconds behind, dukascopy
     *  up to 59 minutes - and the two look identical on screen without a number.
     *  A live call returned 3531 here, and the chart said nothing. */
    feed_lag_seconds?: number;
    fetched_at?: number;
    supply_demand?: Record<string, number>;
    fvg?: Record<string, number>;
    order_block?: Record<string, number>;
    ifvg?: Record<string, number>;
    breaker?: Record<string, number>;
    /** The top-down pass, nested per layer.
     *
     *  FLAT UNTIL HTF REACHED MORE THAN ONE DETECTOR. Projection lived inside the
     *  supply-and-demand handler alone, so a reader with only Fair value gap on
     *  could pick HTF 4h in the header and get a 200 with no `htf` key at all -
     *  no zones from up there, no warning, a chart identical to the one before.
     *  Five box detectors answer now, and a flat bucket would let the last one
     *  overwrite the four before it.
     *
     *  `note` is what fires when HTF is on and NOTHING can use it. The cycle grid,
     *  the defining range and the opening gaps already carry their own degree, so
     *  there is no higher timeframe to read them on - and saying nothing looked
     *  exactly like a broken feature. */
    htf?: {
      interval?: string;
      note?: string;
      layers?: Record<string, Record<string, number | string>>;
    };
    structure?: Record<string, number>;
    checklist?: {
      /** Provider calls this block added, counted where a caller can see it. */
      extra_fetches?: number;
      notes?: number;
      ssmt_grid?: number;
    };
    /** The SSMT layer's own counters. TYPED LATE, and nothing rendered them for
     *  a while: `main.py` has assigned `meta["ssmt"]` since the layer shipped,
     *  the frontend declared no shape for it, and extra JSON keys do not break
     *  TypeScript - so the one overlay that can fail for an external reason (a
     *  partner the provider does not carry) was the one overlay whose failure
     *  the panel could not show. */
    ssmt?: {
      /** Before the display cap. `drawn` is what reached the canvas. */
      found?: number;
      drawn?: number;
      /** Bars the aligned grid kept. Four partners discard about 30% of the
       *  window, and this is where that cost is stated rather than hidden. */
      grid?: number;
      /** Which provider the basket was read from, which need not be the chart's:
       *  one symbol id is a different instrument per source. */
      source?: string;
      /** The upstream's own words when a partner could not be fetched. The
       *  drawing survives and says so. */
      error?: string;
      /** Why nothing was drawn, when the reason is a missing choice rather than
       *  a failure. */
      reason?: string;
      /** Where in the dealing range the drawn divergences sat. The canvas puts
       *  one letter on each segment; this is the same reading for the SET, which
       *  is what a reader looks at before deciding whether the layer is saying
       *  anything. `unknown` is the warm-up, counted rather than folded into
       *  equilibrium. */
      range?: {
        premium?: number;
        equilibrium?: number;
        discount?: number;
        unknown?: number;
      };
      /** Partners the provider could not serve, in the provider's own words.
       *
       *  This list could not exist before: one unavailable partner cancelled every
       *  sibling fetch, so asking for seven partners where the broker lacked one
       *  bond contract returned a single error and nothing else. It is the
       *  difference between "gold and silver did not diverge" and "silver never
       *  loaded". */
      skipped?: string[];
      /** HOW CORRELATED EACH PARTNER ACTUALLY IS, on the same aligned grid the
       *  divergences were read from.
       *
       *  This layer's measured hit rate tracks correlation - gold diverges from
       *  silver on 14.9% of readings and from the dollar index on 59.5% - and until
       *  this arrived the only thing standing between a reader and a meaningless
       *  pairing was a hardcoded list of three tickers in the toolbox. That list is
       *  gone. Measured on 1067 paired hourly log returns of gold: silver +0.856,
       *  DXY -0.588, copper +0.536, Nasdaq +0.397, WTI -0.332, bitcoin +0.277,
       *  USDJPY -0.275 - and the guess had named neither WTI nor the yen.
       *
       *  Pearson on LOG RETURNS, never on prices: two trending series correlate
       *  near +1 for no reason other than both trending. `full` is the whole
       *  window, `recent` its last quarter, and `sign_changed` fires when the two
       *  disagree - which is the finding a single number would have hidden. Null
       *  where there were too few paired returns to say anything. */
      correlation?: {
        symbol: string;
        full: number | null;
        recent: number | null;
        pairs: number;
        recent_pairs: number;
        sign_changed: boolean;
      }[];
    };
    /** TOP LEVEL, because `main.py` assigns `meta["news"]` there - the overlay
     *  runs in the async handler rather than in the synchronous build, since it
     *  is the one layer that talks to the network. These keys used to be
     *  declared inside `overlays`, a path that does not exist on the wire, so
     *  the only overlay that can FAIL had no counters and no error on screen.
     *  The keys keep the `news_` prefix the overlay writes them with. */
    news?: {
      news?: number;
      news_found?: number;
      /** Releases that fell while the market was shut - a weekend or holiday row
       *  - dropped rather than nailed to the last bar before them. */
      news_market_shut?: number;
      /** Read from the feed, never assumed to be seven days: the live source came
       *  back covering 4.65 days on the day this was written. */
      news_window?: string;
      /** Set when the ForexFactory feed failed. Then an empty week IS the error,
       *  and drawing nothing without saying so reads as a quiet calendar. */
      news_error?: string;
    };
    session?: {
      quarters_found?: number;
      quarters_drawn?: number;
      true_opens?: number;
      /** How many of those were read from a bar after their boundary rather than
       *  on it. Reported separately because the two are not the same object. */
      true_opens_approximate?: number;
      /** Per degree: Q2 boundaries in this window that had no bar to open on. */
      true_opens_missing?: Record<string, number>;
      unknown_degrees?: string[];
    };
    overlays?: {
      /** Before the display cap. `gaps` is what was drawn. */
      gaps_found?: number;
      /** Bars the gap layer actually read, which is NOT the chart's bar count:
       *  it fetches its own history because a gap's closing price often sits
       *  outside the window while the gap is on screen. */
      gap_history_bars?: number;
      /** Boundaries where the market never shut, so there is no gap. The whole
       *  answer on a 24/7 instrument, and it must not read as a failure. */
      gaps_traded_through?: number;
      /** Boundaries whose closing session is still outside the window. The
       *  opposite remedy to the one above: more history, not a different one. */
      gaps_no_bars?: number;
      gaps?: number;
      /** Bands whose edges are the nearest prices the feed could offer rather
       *  than the ones the definition asks for. On 4h bars this equals `gaps`. */
      gaps_approximate?: number;
      event_horizons?: number;
      tier_horizons?: number;
      /** Overlaps between two gaps of different kinds. Drawn as a framed region
       *  with its percentage, on the gaps layer. */
      gap_stacks?: number;
      tier_reduction?: string;
      /** Before the display cap. `cisd` is what was drawn. */
      cisd_found?: number;
      cisd?: number;
      /** The population the CISDs were selected from, so the ratio shows how
       *  selective `min_run` was on this series. */
      delivery_runs?: number;
      /** Before the display cap. `dfr` is what was drawn. The cap multiplies
       *  here, so the gap between the two is wider than it looks: each band
       *  dropped takes its projection levels with it. */
      dfr_found?: number;
      dfr?: number;
      /** Degrees picked that the cycle module has no quarters for on this
       *  window. They drew nothing, and before this they did it silently. */
      dfr_unknown_degrees?: number;
      /** Before the display cap. `pools` is what was drawn. */
      pools_found?: number;
      pools?: number;
      pools_standing?: number;
      /** Windows the feed did not fully span. A partial high is not the high. */
      pools_partial?: number;
      unknown_sessions?: string[];
      levels_found?: number;
      levels?: number;
      levels_standing?: number;
      boundary?: string;
      unknown_periods?: string[];
      external?: number;
      internal?: number;
      /** How many dealing-range lines were drawn, or WHY none were.
       *
       *  A number or a sentence, and the union is the point: a range needs a
       *  confirmed swing on both sides, so a short window or a one-directional run
       *  legitimately has none. Reporting 0 would make "no range here" and "the
       *  frame is broken" look identical, which is the one thing this engine is
       *  built not to do. */
      range_frame?: number | string;
      range_height?: number;
      /** Shelves found, how many still stand, and the fractal width they were
       *  built from - the STRUCTURE layer's own `swing_n`, not a second knob, so a
       *  shelf can never sit between two swings the structure overlay does not
       *  consider swings. */
      equal_levels?: number;
      equal_levels_standing?: number;
      equal_levels_swing_n?: number;
      projections?: number;
      projection_levels?: number;
      unknown_projection_sessions?: string[];
    };
  };
}

/** One drawable thing, as `backend/app/layers.py` serves it.
 *
 *  THE POINT OF THIS TYPE is that it is the ONLY place the frontend learns what
 *  can be drawn. There is no id union here, no detector list, no overlay list
 *  and no per-id label table: a layer added to the backend registry appears in
 *  the menu, in draw order, with its own note and evidence, with no edit here.
 *  Only a layer that also introduces a brand-new `params` block needs frontend
 *  work, and then only to draw its knobs - it still gets a working switch. */
export interface LayerInfo {
  id: string;
  label: string;
  /** "detector" | "overlay" | "report" today, and read as an opaque string on
   *  purpose: the menu groups by whatever kinds come back rather than by three
   *  it was told about. */
  kind: string;
  /** Which key of `LayerParams` holds this layer's knobs. Several detectors
   *  share one on purpose. */
  params: string;
  /** One line. Shown under the switch. */
  note: string;
  /** What has been MEASURED, which for most of these is nothing, and for two of
   *  them is a significantly NEGATIVE result. Long, so it lives behind the
   *  disclosure - but every row advertises that it is there, because a menu
   *  that made all thirteen look equally endorsed would be the most misleading
   *  thing on the screen. */
  evidence: string;
}

export interface ServerConfig {
  providers: { id: string; available: boolean; needs_key: boolean }[];
  default_provider: string;
  symbols: { id: string; providers: string[] }[];
  intervals: string[];
  /** Researched broker profiles the plan can be priced at. Empty pick is the
   *  generic per-instrument row, which is what every plan used until the
   *  picker existed - a venue nobody here trades. */
  brokers?: string[];
  /** Every drawing the engine can produce, in DRAW ORDER. Replaces the old
   *  `detectors` and `overlays` pair, which forced the UI to know which of the
   *  two mechanisms each id belonged to. */
  layers: LayerInfo[];
}

/** Every layer's knobs in one record, keyed by the registry's own `params`
 *  name, so a `DrawRequest` body is `{ ...params, layers }` and nothing has to
 *  be listed twice. Replaces nine `useState` hooks and nine patch callbacks. */
export interface LayerParams {
  supply_demand: SupplyDemandParams;
  imbalance: ImbalanceParams;
  structure: StructureParams;
  session: SessionParams;
  dfr: DFRParams;
  gaps: GapParams;
  news: NewsParams;
  cisd: CISDParams;
  pools: PoolParams;
  liquidity: LiquidityParams;
  projections: ProjectionParams;
  checklist: ChecklistParams;
}

/** THE DEFAULT CHART IS ONE DETECTOR. Everything else is opt-in, and that is a
 *  measurement rather than a taste: five detectors alone paint 31.6% of the
 *  chart, and past about a third the boxes stop annotating price and become its
 *  background. Mirrors `layers.DEFAULT_LAYERS`. */
export const DEFAULT_LAYERS = ["supply_demand"];

export const DEFAULT_LAYER_PARAMS: LayerParams = {
  supply_demand: {
    atr_period: 14,
    impulse_body_ratio: 0.5,
    impulse_atr: 1.0,
    base_max_bars: 6,
    base_max_atr: 2.5,
    max_base_drift: 0.6,
    departure_min_atr: 2.0,
    departure_lookahead: 20,
    proximal_basis: "wick",
    min_profit_margin: 0,
    min_profit_zone_rr: 0,
    zone_min_atr: 0.05,
    mitigation_pct: 0.5,
    show_broken: false,
    show_mitigated: true,
    max_zones_per_side: 6,
    merge_overlap_pct: 0.6,
  },
  imbalance: {
    atr_period: 14,
    min_gap_atr: 0.1,
    displacement_atr: 1.5,
    displacement_bars: 5,
    mitigation_pct: 0.5,
    arrival_bars: 6,
    require_structure_break: false,
    structure_break_bars: 5,
    structure_n: 5,
    show_broken: false,
    show_mitigated: true,
    max_zones_per_side: 6,
  },
  structure: {
    swing_n: 50,
    internal_n: 5,
    sweep_reversal_bars: 3,
    mss_window: 5,
    max_events: 40,
  },
  dfr: {
    degrees: [],
    extensions: [-0.5, -1],
    equilibrium: true,
    max_ranges: 4,
  },
  session: {
    quarters: [],
    true_opens: [],
    approximate_true_opens: false,
    max_quarters: 200,
  },
  gaps: { keep: 5, tier_keep: 3, tier_reduction: "envelope", event_horizons: true },
  news: { impacts: ["High"], currencies: [] },
  cisd: { min_run: 2, interrupt_tolerance: 0, max_events: 40 },
  pools: { sessions: ["asia", "london"], max_pools: 12 },
  liquidity: {
    periods: ["day", "week"],
    boundary: "cycle",
    range_liquidity: false,
    range_frame: false,
    equal_levels: false,
    equal_tolerance_atr: 0.1,
    draw_candidates: false,
    max_levels: 16,
  },
  projections: {
    sessions: ["london"],
    direction: 0,
    levels: [0, -0.5, -1, -1.5, 2, 2.5],
  },
  checklist: {
    degree: "day",
    discount_anchor: "parent_cycle",
    chain_degrees: [],
    bias_timeframes: [],
    bias_bars: 400,
    ssmt_symbols: [],
    ssmt_degrees: [],
    // null, not "yahoo". The default has to be "whatever the chart is on",
    // because a shipped default of one named venue would silently read the
    // basket somewhere the user never chose - and would break outright on a
    // machine where that source is unavailable.
    ssmt_max: 40,
    ssmt_provider: null,
  },
};


/** One stored observation, as the review index sees it.
 *
 *  THE LAG IS FOUR NUMBERS AND THAT IS THE POINT. `feed_seconds` alone is not
 *  staleness: it is `now - bar_closed_at`, so on a 15-minute chart it runs 0 to
 *  900 purely because time passes inside the bar being formed - a live reading of
 *  769 was a perfectly healthy feed twelve minutes into a bar. `overdue_seconds`
 *  is the real signal, and `total_seconds` is overdue plus the reader's own
 *  delay, deliberately EXCLUDING the intra-bar part. */
export interface SnapshotLag {
  feed_seconds: number;
  intra_bar_seconds: number;
  overdue_seconds: number;
  screen_seconds: number;
  total_seconds: number;
}

export interface SnapshotSummary {
  id: string;
  taken_at: number;
  note: string;
  symbol: string | null;
  interval: string | null;
  provider: string | null;
  /** Only the layers that actually drew something. An overlay that was on and
   *  found nothing is not listed, because "it was on" and "it drew" are
   *  different facts and the second is the one an audit needs. */
  layers: string[];
  objects: number;
  plans: number;
  lag: SnapshotLag;
  /** Present only when the snapshot was taken with a rule attached. */
  deduction: Deduction | null;
}

/** The verdict of a stated rule, applied to one snapshot.
 *
 *  `status` is "RULE MET" or "NO SETUP" and never the word "valid": it states
 *  that the caller's conditions are satisfied, not that the rule works. The rule
 *  has no walk-forward, no placebo and no base rate. */
export interface Deduction {
  status: "RULE MET" | "NO SETUP";
  side: string;
  /** One line per clause, each tagged `[measured]` or `[nominated]`. */
  deduction_path: string[];
  stopped_at: string | null;
  failed_conditions: string[];
  evidence: Record<string, string | number | null>;
  caveat: string;
}


/** What the broker connection says the account is, right now.
 *
 *  BOTH BALANCE AND EQUITY, because they diverge by the floating result of
 *  whatever is already open and sizing on the wrong one is wrong in the
 *  direction that hurts: equity falls in drawdown, so a stale balance sizes UP
 *  exactly when it should size down.
 *
 *  No login and no server name. The account number identifies a real account and
 *  sizing does not need it, so the backend never sends it and it cannot end up in
 *  a screenshot or a snapshot. */
export interface AccountReading {
  provider: string;
  currency: string;
  balance: number;
  equity: number;
  free_margin: number;
  leverage: number;
  /** When the terminal was read. A lot suggestion built on this is only as
   *  current as this instant, and the UI says so rather than implying live. */
  read_at: number;
}

/** The auto-trade switch, and whether anything is running to honour it.
 *
 *  TWO FACTS, NEVER ONE. `enabled` is a human's request; `daemon_alive` is
 *  whether `tools/autotrade.py` has stamped a heartbeat inside the last minute.
 *  A UI that showed only the first would read ON over a dead daemon, which is
 *  the same class of defect as an instrument reporting green over a crashed
 *  process - and this project keeps a list of those.
 *
 *  `symbol`, `interval` and `risk_pct` are written by the DAEMON, not by the
 *  switch, so they say what is actually being traded rather than what somebody
 *  typed. A daemon started on 15m while the chart shows 1h becomes visible here. */
export interface AutotradeState {
  enabled: boolean;
  /** Unix seconds the switch was last flipped. 0 means never. */
  updated_at: number;
  note: string;
  symbol: string | null;
  interval: string | null;
  risk_pct: number | null;
  /** Unix seconds of the last heartbeat, or null if a daemon has never run. */
  last_seen: number | null;
  /** Seconds since that heartbeat. Null when there has never been one. */
  heartbeat_age_seconds: number | null;
  daemon_pid: number | null;
  daemon_alive: boolean;
}

/** The AI Agent's endpoint settings, as the UI may see them. `api_key` is
 *  always empty on the way OUT (the backend masks it); an empty key on the
 *  way IN means "keep the stored one", because the UI cannot hand back what
 *  it was never shown. */
export interface AgentConfig {
  base_url: string;
  model: string;
  temperature: number;
  api_key: string;
  /** Last four characters of the stored key, so the operator can see WHICH
 *  key is configured without seeing it. Empty when no key is stored. */
  api_key_hint: string;
  available: boolean;
}

/** The response to saving agent settings: what was stored, plus whether the
 *  upstream actually answered when probed. A save with `reachable: false`
 *  stands (the operator may be pre-configuring), but the UI must not paint
 *  it green. */
export interface AgentConfigSaveResponse extends AgentConfig {
  reachable: boolean;
  error: string | null;
  models: number;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  role: ChatRole;
  content: string;
  /** Assistant messages only: did every number in the reply come from the
 *  drawing digest. Server-side verdict, not a client-side guess. */
  grounded?: boolean;
  reason?: string;
  /** The specific invented numbers the grounding check caught, if any. */
  unsupported?: number[];
}

export interface AgentChatResponse {
  reply: string;
  grounded: boolean;
  reason: string;
  unsupported: number[];
  model: string;
}

/** The chat context: the drawing the agent discusses, plus the POSKO triad
 *  readings (correlation and Truth Asset) so it can answer "korelasi emas". */
export interface AgentContext {
  draw: DrawResponse;
  triads: TriadResponse[];
}

/** POSKO 618 — one triad, three symbols, and which is the Truth Asset. */
export interface TriadResponse {
  triad: string;
  base: string;
  partners: string[];
  truth_asset: { symbol: string; scores: Record<string, number> } | null;
  correlation: {
    symbol: string;
    full: number | null;
    recent: number | null;
    pairs: number;
    sign_changed: boolean;
  }[];
  time: {
    ny: string;
    wib: string;
    ny_day: string;
    wib_day: string;
    session: string | null;
    all_sessions: string[];
  };
  grid: number;
  skipped: string[];
}
