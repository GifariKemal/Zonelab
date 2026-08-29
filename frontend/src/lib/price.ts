/**
 * How many decimals an instrument actually quotes. One module, because there
 * has to be ONE answer.
 *
 * The chart's price axis and the OHLC readout in the header describe the same
 * bar. When they disagree the app is telling the reader two different prices
 * for one candle, and neither is obviously the wrong one - which is exactly the
 * complaint that produced this file: the axis said 4489.621 and the header said
 * 4489.62. So the rule lives here and both import it.
 *
 * READ FROM THE DATA, not declared per symbol. Every provider quotes the same
 * instrument differently - MT5 gives gold three decimals, Binance gives its
 * PAXG proxy two - so a table of tick sizes would be one more thing to keep
 * true against six feeds. The prices are already in hand and they are the
 * authority.
 */

import type { Candle } from "./types";

/** Decimals in one number's own decimal representation, or 0 for a tail long
 *  enough to be an encoding artefact rather than a quote.
 *
 *  THE GUARD IS THE POINT. Yahoo ships float32, so its silver arrives as
 *  65.18499755859375 and its gold as 4515.7998046875. Counting those digits
 *  would ask a price scale for fifteen decimals of a series that has one, and
 *  since the maximum is taken across every bar, a single such value would
 *  decide the whole axis. Nothing real quotes past eight places, so a longer
 *  tail contributes nothing instead of poisoning the result. */
function decimals(value: number): number {
  const text = String(value);
  const dot = text.indexOf(".");
  if (dot < 0) return 0;
  const tail = text.length - dot - 1;
  return tail > 8 ? 0 : tail;
}

/** The most decimals any bar in the window quotes, floored at 2.
 *
 *  Two is a floor and not an answer: a stretch where every bar happens to close
 *  on a round figure must not shrink the axis to whole units and then grow it
 *  back on the next poll, which would move every gridline for no reason. */
export function priceDecimals(candles: Candle[]): number {
  let most = 0;
  for (const candle of candles) {
    most = Math.max(
      most,
      decimals(candle.open),
      decimals(candle.high),
      decimals(candle.low),
      decimals(candle.close),
    );
  }
  return Math.max(2, most);
}

/** One price, printed at the count `priceDecimals` returned.
 *
 *  A one-line wrapper over `toFixed`, and it exists so that a panel printing a
 *  price has to IMPORT the rule rather than re-decide it. Both panels in the
 *  right rail had `toFixed(2)` typed inline - 33 call sites between them - which
 *  is the same defect this module was written for, one file further along: on a
 *  5-decimal FX pair the axis read 1.09234 and the panel read 1.09, and neither
 *  number was obviously the wrong one. `grep -r "toFixed(2)" src/components` is
 *  now the check, and it should only ever match money in the account currency,
 *  never an instrument price.
 *
 *  The count is PASSED IN rather than derived here, because the panels never
 *  hold the candles - `app/page.tsx` does, it already calls `priceDecimals` once
 *  for the header readout, and computing it a second and a third time per render
 *  would be the same fact stored three ways. */
export function formatPrice(value: number, decimals: number): string {
  return value.toFixed(decimals);
}
