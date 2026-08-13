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
  top: number;
  bottom: number;
  proximal: number;
  distal: number;
  time_from: number;
  time_to: number;
  strength: number;
  departure_atr: number;
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
  zone_basis: "wick" | "body";
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
  zone_basis: "wick",
  zone_min_atr: 0.05,
  mitigation_pct: 0.5,
  show_broken: false,
  show_mitigated: true,
  max_zones_per_side: 12,
  merge_overlap_pct: 0.6,
};
