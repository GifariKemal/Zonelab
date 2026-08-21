/**
 * ONE PALETTE FOR THE CANVAS LAYERS, computed rather than picked.
 *
 * Every primitive used to hold its own grey-blue: 95/104/116, 139/150/165,
 * 151/166/189, 154/166/181, 159/173/194. Five hues that are the same hue. With
 * nine layers on, a reader could not tell a structure caption from a pool ray
 * from a defining range without reading its label - and there are 96 labels on a
 * loaded chart, most of them four characters. The layer families are now
 * distinguishable at a glance, which is what a trader actually does with a
 * chart before reading anything on it.
 *
 * COLOUR TYPES THE FAMILY, NOT THE OBJECT, and that distinction is the whole
 * reason this is safe. The owner's own 51 annotated charts are colour
 * INCONSISTENT - pink means a session box on some and a quarter box on others,
 * orange means a 90-minute timeframe on some and an IFVG fill on others - which
 * is why `levels-primitive.ts` decided that colour cannot say WHICH object this
 * is and the label must. That still holds: inside a family every object shares
 * one ink and its name is what identifies it. What changed is that the five
 * families no longer share one ink with each other.
 *
 * THE CONSTRAINTS, all of them measured against #0b0d10 rather than judged:
 *
 *  - every hue at least 43 degrees from demand-green (154), supply-salmon (5)
 *    and the gold control accent (39), so no layer can read as a direction or as
 *    a control. Those three meanings are spoken for and this file may not touch
 *    them;
 *  - L* stepped about six points per family, grid 44.0 -> dfr 54.0 -> structure
 *    59.9 -> ssmt 65.9 -> levels 72.0, so the families stay separable in
 *    greyscale for the one man in twelve with a red-green deficiency. Greyscale
 *    contrast dimmest against brightest is 2.5:1;
 *  - contrast against the page 3.49:1 for the grid, which is background and
 *    never carries text, and 5.00 to 9.02:1 for the four that do;
 *  - saturation held between 10% and 42%. A saturated stroke on near-black is
 *    the classic eye-strain case on a screen someone watches for a session, and
 *    the ceiling is deliberately below the 64-77% the two semantic colours use -
 *    those two are allowed to shout because they mean something.
 *
 * The ORDER of the L* ladder is a statement too. The grid is dimmest because it
 * is context the candles sit on. DFR is next because it is the weakest-evidenced
 * object on the canvas - one paragraph describing a closed-source indicator,
 * never verified - and it must not look like a measured level. Named price rays
 * are brightest because they are the objects a reader compares a candle against.
 */

/** rgb triples, no alpha. Every caller supplies its own, because the alphas are
 *  separately measured contrast floors and belong with the shapes they draw. */
export const INKS = {
  /** Quarter boxes, session shading, break markers: time-anchored context. */
  grid: [95, 105, 117],
  /** The defining range and its projections. Deliberately the dimmest thing
   *  that still carries a label. */
  dfr: [118, 126, 178],
  /** Swings, BOS, CHoCH, MSS: what the market did to its own structure. */
  structure: [161, 132, 195],
  /** Cross-instrument divergence. The only family that needs a second
   *  instrument, and the only one that is about disagreement. */
  ssmt: [204, 141, 181],
  /** Named price rays and bands: opening gaps, event horizons, CISD levels,
   *  liquidity pools, true opens. Brightest, because these are the prices. */
  levels: [137, 183, 207],
} as const;

export type InkName = keyof typeof INKS;

/** `rgba(...)` for a family at one alpha. A function rather than a table of
 *  pre-built strings, because the alphas are per-shape and there are dozens. */
export function ink(name: InkName, alpha: number): string {
  const [r, g, b] = INKS[name];
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
