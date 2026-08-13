/** Mirrors backend/app/models.py. Kept hand-written and small on purpose: a
 *  generated client would be more machinery than four interfaces are worth. */

export type ZoneKind = "RBR" | "DBR" | "DBD" | "RBD";
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
  base_from: number;
  base_to: number;
  leg_out_from: number;
  leg_out_to: number;
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
  departure_min_atr: number;
  departure_lookahead: number;
  proximal_basis: "wick" | "body";
  min_profit_margin: number;
  zone_min_atr: number;
  mitigation_pct: number;
  show_broken: boolean;
  show_mitigated: boolean;
  max_zones_per_side: number;
  merge_overlap_pct: number;
}

export interface DrawResponse {
  symbol: string;
  interval: string;
  provider: string;
  htf?: string | null;
  candles: Candle[];
  drawing: { zones: Zone[] };
  meta: {
    bars_returned?: number;
    supply_demand?: Record<string, number>;
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
  departure_min_atr: 2.0,
  departure_lookahead: 20,
  proximal_basis: "wick",
  min_profit_margin: 0,
  zone_min_atr: 0.05,
  mitigation_pct: 0.5,
  show_broken: false,
  show_mitigated: true,
  max_zones_per_side: 12,
  merge_overlap_pct: 0.6,
};
