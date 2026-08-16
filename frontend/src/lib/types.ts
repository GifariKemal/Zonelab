/** Mirrors backend/app/models.py. Kept hand-written and small on purpose: a
 *  generated client would be more machinery than four interfaces are worth. */

export type ZoneKind = "RBR" | "DBR" | "DBD" | "RBD" | "FVG" | "OB";
export type DetectorId = "supply_demand" | "fvg" | "order_block";
export type ZoneSide = "demand" | "supply";
export type ZoneState = "fresh" | "tested" | "mitigated" | "broken";

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Anatomy {
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
  /** How hard price travelled in before the first touch, in ATR. Null until
   *  touched. Sources disagree on whether fast is good; measured, it is
   *  indistinguishable either way. */
  arrival_atr: number | null;
  touches: number;
  penetration_pct: number;
  first_test_time: number | null;
  confirmed: boolean;
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

/** Shared by the fvg and order_block detectors. Deliberately small: neither
 *  carries a score, so there is nothing to weight and nothing to retract. */
export interface ImbalanceParams {
  atr_period: number;
  min_gap_atr: number;
  displacement_atr: number;
  displacement_bars: number;
  mitigation_pct: number;
  arrival_bars: number;
  show_broken: boolean;
  show_mitigated: boolean;
  max_zones_per_side: number;
}

export const DEFAULT_IMBALANCE: ImbalanceParams = {
  atr_period: 14,
  min_gap_atr: 0.1,
  displacement_atr: 1.5,
  displacement_bars: 5,
  mitigation_pct: 0.5,
  arrival_bars: 6,
  show_broken: false,
  show_mitigated: true,
  max_zones_per_side: 6,
};

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
  /** Only when an account equity was supplied. */
  units: number | null;
  age_bars: number;
  /** Measured survival of the cohort this zone belongs to, not this trade's
   *  probability, and it excludes costs. */
  departure_held_rate: number;
  /** Same kind of number for the age band. Not independent of
   *  `departure_held_rate`, so the two must never be multiplied. */
  age_held_rate: number;
  /** Null when the feed publishes no spread, so nothing was charged. */
  spread_charged: number | null;
  /** Always null. Nine pre-registered hypotheses failed to get a sign out of
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

export interface DrawResponse {
  symbol: string;
  interval: string;
  provider: string;
  htf?: string | null;
  candles: Candle[];
  drawing: { zones: Zone[] };
  /** One per drawn zone, in the same order as `drawing.zones`. */
  plans: TradePlan[];
  advice: Advice[];
  meta: {
    bars_returned?: number;
    supply_demand?: Record<string, number>;
    fvg?: Record<string, number>;
    order_block?: Record<string, number>;
    htf?: Record<string, number>;
  };
}

export interface ServerConfig {
  providers: { id: string; available: boolean; needs_key: boolean }[];
  default_provider: string;
  symbols: { id: string; providers: string[] }[];
  intervals: string[];
  detectors: string[];
}

export const DEFAULT_PARAMS: SupplyDemandParams = {
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
};
