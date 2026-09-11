/** Which layers are on, and with which knobs, PER TIMEFRAME.
 *
 *  A drawing belongs to the bars it was read off. A supply zone switched on at
 *  1h is a claim about 1h candles, and carrying that switch to M1 draws a
 *  DIFFERENT set of boxes under the same name - the reader turned one thing on
 *  and got another. Measured before this existed, in `docs/TIMEFRAME-AUDIT.md`:
 *  every layer the registry carries, at every interval the app offers, and not
 *  one returns the same price set twice. So the geometry was always the
 *  timeframe's own; only the switch and its knobs followed the reader around.
 *
 *  THE KNOBS TRAVEL WITH THE SWITCH, and that is not tidiness. `impulse_atr`,
 *  `base_max_bars`, `min_gap_atr` are all read in bars and ATRs of the chart's
 *  own timeframe, so a threshold tuned until 15m looked right is a threshold
 *  nobody chose for 1d. Splitting the switch while sharing the knobs would have
 *  left half the drawing following the reader around.
 *
 *  DIBACA LEWAT STORE, tidak disalin ke state saat mount - pola yang sama dengan
 *  `lib/rails.ts` dan `lib/presets.ts`, karena `localStorage` tidak ada saat
 *  server render dan menariknya masuk lewat effect adalah hydration mismatch
 *  yang sudah ditolak `react-hooks/set-state-in-effect` di repo ini.
 */
import { DEFAULT_LAYERS, DEFAULT_LAYER_PARAMS, type LayerParams } from "./types";

const STORAGE = "zonelab.timeframes";

/** The timeframe the app boots on, and the only one seeded with layers on.
 *
 *  Every other interval starts empty ON PURPOSE. Seeding them all with the
 *  defaults would reproduce the original complaint by a different route: supply
 *  and demand would be on at 1h and still on at M15, just because both were
 *  born that way rather than because the switch travelled. */
export const BOOT_INTERVAL = "15m";

export type TimeframeSetup = { layers: string[]; params: LayerParams };
export type TimeframeStore = Record<string, TimeframeSetup>;

/** Nothing on, and the registry's own defaults for the knobs. Frozen and shared
 *  so `useSyncExternalStore`'s `Object.is` comparison cannot see a new object
 *  every render and conclude the store keeps changing. */
const EMPTY: TimeframeSetup = Object.freeze({
  layers: Object.freeze([]) as unknown as string[],
  params: DEFAULT_LAYER_PARAMS,
});

const SEED: TimeframeStore = Object.freeze({
  [BOOT_INTERVAL]: Object.freeze({
    layers: DEFAULT_LAYERS,
    params: DEFAULT_LAYER_PARAMS,
  }),
}) as TimeframeStore;

const listeners = new Set<() => void>();
let cache: TimeframeStore | null = null;

const notify = () => {
  for (const listener of listeners) listener();
};

/** One stored setup, with anything unrecognised replaced by the default.
 *
 *  `localStorage` IS A TRUST BOUNDARY. It is editable by hand, it is written by
 *  whatever version of this app ran last, and it survives every deploy - so a
 *  key renamed in `LayerParams` would otherwise reach the request body as
 *  `undefined` and the backend would answer 422 on a chart the reader never
 *  misconfigured. Layers are filtered to strings and the params blocks are
 *  merged OVER the defaults, per block, so a stale or hostile store degrades to
 *  the default rather than to a broken panel.
 */
function clean(got: unknown): TimeframeSetup | null {
  if (!got || typeof got !== "object") return null;
  const row = got as Partial<TimeframeSetup>;
  const layers = Array.isArray(row.layers)
    ? row.layers.filter((l): l is string => typeof l === "string")
    : [];
  const stored = (row.params ?? {}) as Record<string, unknown>;
  // Built as a loose record and narrowed ONCE at the return. Assigning block by
  // block through `keyof LayerParams` makes TypeScript widen the value to the
  // intersection of all nineteen blocks, which nothing satisfies - the cast
  // belongs at the boundary, not nineteen times inside the loop.
  const defaults = DEFAULT_LAYER_PARAMS as unknown as Record<
    string,
    Record<string, unknown>
  >;
  const merged: Record<string, unknown> = { ...defaults };
  for (const key of Object.keys(defaults)) {
    const block = stored[key];
    if (!block || typeof block !== "object" || Array.isArray(block)) continue;
    // A WHITELIST BY THE DEFAULT'S SHAPE, not a spread. Spreading the stored
    // block over the default keeps every field it carries, whatever it holds -
    // and `{"max_zones_per_side": "nonsense"}` then reaches the request body as
    // a string, the backend answers 422, and the reader gets an error banner
    // and no chart from a store they never edited. Measured: the corrupt-store
    // case in `e2e/timeframe-layers.mjs` failed exactly that way against the
    // first version of this function.
    //
    // So each field is kept only when it MATCHES THE DEFAULT'S TYPE, and a key
    // the defaults have never heard of is dropped rather than forwarded.
    const from = block as Record<string, unknown>;
    const out: Record<string, unknown> = { ...defaults[key] };
    for (const field of Object.keys(defaults[key])) {
      const want = defaults[key][field];
      const got = from[field];
      if (got === undefined) continue;
      if (Array.isArray(want)) {
        if (Array.isArray(got)) out[field] = got;
      } else if (typeof got === typeof want && got !== null) {
        out[field] = got;
      }
    }
    merged[key] = out;
  }
  return { layers, params: merged as unknown as LayerParams };
}

/** The whole map, or the seed. A corrupt store returns the seed rather than
 *  throwing: losing a layout preference is an annoyance, a chart that refuses to
 *  render is not. */
function read(): TimeframeStore {
  try {
    const raw = window.localStorage.getItem(STORAGE);
    if (!raw) return SEED;
    const got = JSON.parse(raw) as Record<string, unknown>;
    if (!got || typeof got !== "object" || Array.isArray(got)) return SEED;
    const out: TimeframeStore = {};
    for (const [interval, row] of Object.entries(got)) {
      const setup = clean(row);
      if (setup) out[interval] = setup;
    }
    return Object.keys(out).length ? out : SEED;
  } catch {
    return SEED;
  }
}

export function subscribeTimeframes(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE) {
      cache = null;
      notify();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

export function timeframesSnapshot(): TimeframeStore {
  if (cache === null) cache = read();
  return cache;
}

export function timeframesServerSnapshot(): TimeframeStore {
  return SEED;
}

/** What is on at one interval, or nothing on with default knobs. */
export function setupAt(store: TimeframeStore, interval: string): TimeframeSetup {
  return store[interval] ?? EMPTY;
}

/** Write one interval's setup, leaving every other interval alone.
 *
 *  `notify()` here as well as through the `storage` event, because that event
 *  fires only in OTHER tabs - without this the tab that clicked the switch is
 *  the one tab that does not see it move. */
export function setSetupAt(interval: string, next: TimeframeSetup): void {
  const store = { ...timeframesSnapshot(), [interval]: next };
  cache = store;
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify(store));
  } catch {
    // A private window throws on this line. Failing to remember a preference is
    // not a reason to fail to apply it for this session.
  }
  notify();
}
