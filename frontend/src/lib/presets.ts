import { DEFAULT_LAYER_PARAMS, type LayerParams } from "./types";

/**
 * NAMED LAYER SETS THE READER PICKS. No inference, no phase detection, no
 * automatic switching.
 *
 * THE HONEST HALF OF "FOCUS MODE". The proposal that prompted this was for the
 * UI to detect the market phase and switch layers by itself - and the engine
 * already computes the phase, `checklist.profile` returns things like
 * `{name: "XAMD", manipulation: "Q3"}`. The detection was never the problem. The
 * problem is what an automatic switch would do to the reader: a layer hidden by
 * an inference is indistinguishable from a layer that found nothing, and that
 * distinction is the one property this whole engine is built to protect. It
 * would also be the engine asserting "now is manipulation, so look at SSMT",
 * which is a regime claim with no measurement, in a project where twelve
 * pre-registered directional hypotheses have failed.
 *
 * A preset costs the reader one click and asserts nothing. The cognitive load is
 * the same problem; this solves it without the engine developing an opinion.
 *
 * EVERY PRESET CARRIES THE PARAMS ITS LAYERS NEED TO DRAW, and that is not
 * convenience - it is the difference between a preset and a trap.
 *
 * THREE layers of the seventeen draw NOTHING when switched on with default params,
 * and the number is measured rather than assumed: drawing each layer alone with
 * pure defaults, `session`, `dfr` and `ssmt` come back empty and the other twelve
 * do not. An earlier version of this comment said six and named `pools` and
 * `projections` among them, which was wrong - both ship with sessions and draw
 * immediately.
 *
 * `session` needs a degree, `dfr` needs a degree, `ssmt` needs a partner and a
 * stage. Their defaults are empty deliberately: an overlay that switched itself
 * on would spend an ink budget somebody else had accounted for. But a PRESET
 * that switched them on and left them empty would look like a broken engine, and
 * the reader would be right to distrust it.
 */

export interface Preset {
  id: string;
  label: string;
  /** One line, shown under the row. Says what the set is FOR, not what it is. */
  note: string;
  layers: string[];
  /** Deep-merged over the defaults, never replacing the whole block. */
  params?: Partial<{ [K in keyof LayerParams]: Partial<LayerParams[K]> }>;
}

/** The shipped sets.
 *
 *  Four, and deliberately few. These are opinions about READING ORDER - which is
 *  a workflow question and safe to have an opinion about - and not opinions
 *  about price, which is not. Anything a preset cannot express, the reader saves
 *  themselves with the button beside them. */
export const PRESETS: Preset[] = [
  {
    id: "boxes",
    label: "Boxes",
    note: "The five formation detectors and nothing else. What the shipped gate keeps.",
    layers: ["supply_demand", "fvg", "order_block", "ifvg", "breaker"],
  },
  {
    // LABEL-NYA "Time grid", BUKAN "Clock", dan itu memperbaiki tabrakan nama.
    // Header punya picker `Clock` yang memilih ZONA WAKTU, dan tombol ini
    // menyalakan LAYER waktu. Keduanya terlihat sekaligus di satu layar, dan
    // sensus teks menemukan keduanya: `span@371,48` lawan `button@60,320`.
    // Seseorang yang mengklik "Clock" di Presets punya alasan bagus untuk
    // mengira ia mengubah setelan clock.
    //
    // `id` TETAP "clock", karena ia kunci yang tersimpan di localStorage
    // pembaca. Mengubahnya akan membuat setiap preset tersimpan yang cocok
    // dengan set ini berhenti dikenali, dan label bukan alasan yang cukup.
    id: "clock",
    label: "Time grid",
    note: "Time only: quarters, true opens and the defining range. No price objects.",
    layers: ["session", "dfr"],
    params: {
      // Day and week, not all eight. A month of micro quarters is nearly two
      // thousand objects, and a preset that buries the chart on its first click
      // has taught the reader that presets bury the chart.
      session: { quarters: ["week", "day"], true_opens: ["week", "day"] },
      dfr: { degrees: ["day"] },
    },
  },
  {
    id: "liquidity",
    label: "Liquidity",
    note: "Where the resting orders are: gaps, pools, named levels, delivery shifts.",
    layers: ["gaps", "pools", "liquidity", "cisd"],
    params: {
      pools: { sessions: ["asia", "london"] },
    },
  },
  {
    id: "cross",
    label: "Cross-instrument",
    note: "The only read that needs a second instrument, plus the checklist behind it.",
    layers: ["ssmt", "checklist", "structure"],
    params: {
      // Silver, because the measured divergence rate tracks correlation: gold
      // against silver diverges on 14.9% of readings and against DXY on 59.5%,
      // and an inversely correlated instrument disagreeing on nearly every
      // quarter is a category error rather than a rich seam.
      checklist: { ssmt_symbols: ["XAGUSD"], ssmt_degrees: ["day"] },
    },
  },
];

/** Layers plus params for a preset, merged over the CURRENT params.
 *
 *  Merged over current rather than over the defaults, so a threshold the reader
 *  has tuned survives a preset click. A preset is about which layers are on, and
 *  silently reverting a tuned `departure_min_atr` because somebody wanted to see
 *  the clock would be a preset editing a measurement.
 */
export function applyPreset(
  preset: Preset,
  current: LayerParams,
): { layers: string[]; params: LayerParams } {
  // ONE CAST, AT THE BOUNDARY, and it is here rather than per-key on purpose.
  // `LayerParams[keyof LayerParams]` is a UNION of twelve unrelated blocks, so
  // writing `params[key] = {...}` asks TypeScript to prove the value satisfies
  // every one of them at once - which it cannot, and which is not what the code
  // means. Widening to a record of records says exactly what this loop does:
  // merge a partial block over the block of the same name.
  const merged = { ...current } as unknown as Record<string, Record<string, unknown>>;
  const base = current as unknown as Record<string, Record<string, unknown>>;
  for (const [block, patch] of Object.entries(preset.params ?? {})) {
    merged[block] = { ...base[block], ...(patch as Record<string, unknown>) };
  }
  return { layers: [...preset.layers], params: merged as unknown as LayerParams };
}

const STORAGE = "zonelab.presets.v1";

/**
 * SAVED PRESETS AS AN EXTERNAL STORE, not as state copied in on mount.
 *
 * The obvious version was `useEffect(() => setSaved(loadSaved()), [])`, and
 * eslint refused it - `react-hooks/set-state-in-effect` - correctly. Reading a
 * mutable browser store into state during an effect means the first paint shows
 * one thing and the second shows another, which is the hydration mismatch the
 * rule exists to prevent, and this repo has already been told off for the same
 * shape once with the forming candle.
 *
 * `useSyncExternalStore` is the primitive built for exactly this: a value that
 * lives outside React, needs a server snapshot, and changes only when something
 * writes it. The catch is that its snapshot must be REFERENTIALLY STABLE - a
 * function returning a fresh array on every call sends React into an infinite
 * re-render - so the parsed list is cached here and replaced only on a write.
 */
let cache: Preset[] | null = null;
const listeners = new Set<() => void>();

/** Frozen and shared, so the server snapshot is one stable reference forever. */
const EMPTY: Preset[] = Object.freeze([] as Preset[]) as Preset[];

function notify(): void {
  for (const listener of listeners) listener();
}

export function subscribeSaved(listener: () => void): () => void {
  listeners.add(listener);
  // Another tab writing the same key is a real event, and without this the two
  // views drift until one of them reloads.
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

/** The cached list. Stable between writes, which is what the store contract
 *  requires - see the note above. */
export function savedSnapshot(): Preset[] {
  if (cache === null) cache = loadSaved();
  return cache;
}

/** What the server renders: nothing, because there is no browser store there.
 *  One frozen reference so it never looks like a change. */
export function savedServerSnapshot(): Preset[] {
  return EMPTY;
}

/** Presets the reader saved, from localStorage.
 *
 *  CLIENT SIDE ONLY. A layer set is a reading preference, not a measurement:
 *  putting it on the server would mean a migration, an endpoint and a shape to
 *  keep in step, for something that belongs to one browser.
 *
 *  A corrupt or hand-edited store yields an empty list rather than throwing. The
 *  shipped presets keep working, which is the behaviour that matters - losing a
 *  saved set is an annoyance and a panel that will not render is not.
 */
export function loadSaved(): Preset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (p): p is Preset =>
        typeof p?.id === "string" &&
        typeof p?.label === "string" &&
        Array.isArray(p?.layers),
    );
  } catch {
    return [];
  }
}

/** Save one, replacing any with the same label. Returns the new list.
 *
 *  Replacing by label rather than appending, because "save" on a name that
 *  already exists means "update it" to everyone who has ever used a preset, and
 *  a second entry with the same name is a list the reader cannot use.
 */
export function saveCurrent(
  label: string,
  layers: string[],
  params: LayerParams,
): Preset[] {
  const trimmed = label.trim().slice(0, 40);
  if (!trimmed) return loadSaved();
  // ONLY THE BLOCKS THAT DIFFER FROM THE DEFAULTS are stored. A snapshot of all
  // twelve params blocks would pin every threshold in the app to the moment the
  // preset was saved, so recalling it months later would silently revert
  // anything that had been re-measured since.
  // Same widening as `applyPreset`, and for the same reason.
  const mineAll = params as unknown as Record<string, Record<string, unknown>>;
  const baseAll = DEFAULT_LAYER_PARAMS as unknown as Record<
    string,
    Record<string, unknown>
  >;
  const diff: Record<string, Record<string, unknown>> = {};
  for (const block of Object.keys(mineAll)) {
    const mine = mineAll[block] ?? {};
    const base = baseAll[block] ?? {};
    const changed: Record<string, unknown> = {};
    for (const field of Object.keys(mine)) {
      if (JSON.stringify(mine[field]) !== JSON.stringify(base[field])) {
        changed[field] = mine[field];
      }
    }
    if (Object.keys(changed).length) diff[block] = changed;
  }
  const next: Preset = {
    id: `saved:${trimmed}`,
    label: trimmed,
    note: "Saved from this browser.",
    layers: [...layers],
    params: diff as Preset["params"],
  };
  const kept = loadSaved().filter((p) => p.label !== trimmed);
  const all = [...kept, next];
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify(all));
  } catch {
    // A full or blocked store is not worth an error path: the preset simply
    // does not persist, and the reader finds out by it not being there.
  }
  cache = all;
  notify();
  return all;
}

export function removeSaved(label: string): Preset[] {
  const kept = loadSaved().filter((p) => p.label !== label);
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify(kept));
  } catch {
    /* see saveCurrent */
  }
  cache = kept;
  notify();
  return kept;
}
