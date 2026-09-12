import type { ServerConfig } from "./types";

/**
 * What a feed CALLS an instrument, for labelling only.
 *
 * The app id - `XAUUSD` - is the identity everything is keyed by: params,
 * presets, snapshots, the draw request itself. It is deliberately NOT what the
 * chart is drawing. On TradingView that id resolves to `COMEX:GC1!`, the
 * exchange's front-month gold future; on MT5 to the broker's spot CFD. Those
 * two were measured 51.7 points apart on 12 September 2026, so a screen that
 * shows one name over both is showing a real price under a name that is not
 * its own.
 *
 * LABEL AGAINST THE FEED THAT SERVED THE DATA, not the one the chart is on.
 * `/api/triad` substitutes a provider when the chart's cannot carry all three
 * legs, and it reports which one it used - so the triad panel passes that, not
 * the chart's source, and the two can legitimately differ on screen.
 *
 * Falls back to the app id when the table has no entry, which is the honest
 * answer for a feed that passes a ticker through untouched.
 */
export function vendorName(
  config: ServerConfig | null,
  provider: string | null | undefined,
  appSymbol: string,
): string {
  if (!config || !provider) return appSymbol;
  const row = config.symbols.find((s) => s.id === appSymbol);
  return row?.vendor?.[provider] ?? appSymbol;
}
