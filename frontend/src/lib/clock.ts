/**
 * The frontend's clock. One module, because there is one hazard.
 *
 * EVERY TIMESTAMP THIS APP HANDLES IS AN EPOCH IN UTC, and two different
 * readings are taken off it: the NAME of a session true open, which is fixed to
 * New York wall time, and the TIME AXIS, which the reader chooses. Both are
 * wrong in the same way if they are done with an offset instead of a zone, so
 * both live here and both go through `Intl.DateTimeFormat` with a named zone.
 *
 * THE TRAP, stated once for the whole file. New York is UTC-5 in winter and
 * UTC-4 in summer. A constant offset is not approximately right, it is EXACTLY
 * RIGHT FOR HALF THE YEAR and silently wrong for the other half, and the wrong
 * half looks perfectly plausible - an hour is a small enough error to read as a
 * real number and a large enough one to move a bar into the wrong session. The
 * browser here runs on Asia/Jakarta, which never shifts, so `getHours()` is not
 * a fallback either: it is a third clock, seven hours from UTC and eleven or
 * twelve from New York. The backend routes every boundary through a DST-aware
 * clock for this reason; this is the same decision on this side of the wire.
 *
 * NOTHING HERE SHIFTS AN EPOCH. Faking a zone by adding an offset to the
 * timestamps handed to the chart would corrupt every coordinate lookup the
 * primitives do - zones, structure, the cycle grid and the ribbon all convert
 * times to x through the chart's own scale - and both pixel harnesses assume
 * those are true epochs. Only the LABEL is converted.
 */

/** The three clocks offered on the time axis, in the order the picker shows
 *  them. UTC first and it stays the default: it is what every screenshot, every
 *  harness expectation and every number written down against this chart was
 *  read in, and moving that silently would invalidate all of them at once. */
export const CLOCK_ZONES = ["UTC", "New York", "WIB"] as const;

export type ClockZone = (typeof CLOCK_ZONES)[number];

const IANA: Record<ClockZone, string> = {
  UTC: "UTC",
  "New York": "America/New_York",
  // Western Indonesian Time. No daylight saving here, which is exactly what
  // makes it a good place to catch a naive local reading and a bad place to
  // trust one.
  WIB: "Asia/Jakarta",
};

/** What the axis calls itself in the corner and on the crosshair label. An axis
 *  reading 05:00 with no zone on it anywhere is how a bar gets read into the
 *  wrong session, so the abbreviation travels with the time. */
export const ZONE_TAG: Record<ClockZone, string> = {
  UTC: "UTC",
  "New York": "NY",
  WIB: "WIB",
};

/** Which part of the date a tick mark stands for. The charting library's own
 *  enum, restated in plain strings so this module owes it nothing: a lib file
 *  that imports the chart cannot be run under bare node, and the test for the
 *  thing below is the whole reason it is worth keeping runnable. */
export type TickKind = "year" | "month" | "day" | "weekday" | "time" | "seconds";

const OPTIONS: Record<TickKind, Intl.DateTimeFormatOptions> = {
  year: { year: "numeric" },
  month: { month: "short" },
  day: { day: "numeric" },
  // NOT USED ON THE AXIS. It names a weekly quarter, which is a 24-hour cycle
  // whose whole identity is which weekday it belongs to - see `cycleWeekday`.
  weekday: { weekday: "short" },
  // `hourCycle` rather than `hour12: false`, which renders midnight as 24:00 in
  // some locales - an hour that would sit in the axis reading as a plain wrong
  // number.
  time: { hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
  seconds: { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" },
};

/** Formatters are built once per zone and shape. Both callers below run inside
 *  a paint loop - a tick formatter is called for every mark on every frame -
 *  and constructing an `Intl.DateTimeFormat` is the expensive half of using
 *  one. */
const cache = new Map<string, Intl.DateTimeFormat>();

function formatter(zone: ClockZone, key: string, options: Intl.DateTimeFormatOptions) {
  const id = `${zone}|${key}`;
  let f = cache.get(id);
  if (!f) {
    // en-GB, not the visitor's locale: day-before-month and a 24-hour clock, so
    // an axis does not silently change shape with the browser it is opened in.
    f = new Intl.DateTimeFormat("en-GB", { timeZone: IANA[zone], ...options });
    cache.set(id, f);
  }
  return f;
}

/**
 * One tick mark on the time axis, in the chosen zone.
 *
 * READ THE CAVEAT BEFORE TRUSTING A DATE TICK. The library decides WHICH ticks
 * are day, month and year marks from the UTC calendar, and that decision cannot
 * be moved without shifting the epochs, which is forbidden above. So the label
 * is the true date of that instant IN THE CHOSEN ZONE - on a New York axis the
 * tick at 00:00 UTC correctly reads as the previous day - but a date mark sits
 * where UTC rolls over, not where New York or Jakarta does. The hour labels,
 * which are the reading that decides which session a move happened in, are
 * exactly right in every zone, and the crosshair stamp below carries the full
 * date, the time and the zone together.
 */
export function clockTick(timeSeconds: number, zone: ClockZone, kind: TickKind): string {
  return formatter(zone, kind, OPTIONS[kind]).format(timeSeconds * 1000);
}

/** The crosshair's time label: date, time, and WHICH CLOCK, always. This is the
 *  reading a person takes when they want to know when a specific bar happened,
 *  and it is the one place the zone can never be inferred from context. */
export function clockStamp(timeSeconds: number, zone: ClockZone): string {
  const text = formatter(zone, "stamp", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  })
    .format(timeSeconds * 1000)
    // en-GB puts a comma between the date and the time. The label is narrow.
    .replace(",", "");
  return `${text} ${ZONE_TAG[zone]}`;
}

/**
 * What a SESSION-degree true open is CALLED, read off the New York wall clock.
 *
 * The owner does not call these TSO. His own time board names four of them, and
 * it was checked row by row against what the engine emits, in both daylight
 * saving states:
 *
 *     LEVEL     New York   WIB (Mar-Nov)   WIB (Nov-Mar)
 *     Asia      19:30      06:30 next day  07:30 next day
 *     London    01:30      12:30           13:30
 *     NY AM     07:30      18:30           19:30
 *     NY PM     13:30      00:30 next day  01:30 next day
 *
 * Each is 90 minutes past a day-quarter boundary - 18:00, 00:00, 06:00, 12:00
 * New York - because a session true open is the Q2 of the 90-minute cycle that
 * opens each six-hour day quarter. The engine already puts a level on exactly
 * those instants; this only supplies the name, and a name on a clock is not a
 * claim about price.
 *
 * The two WIB columns are the trap in the file header, written out as data: the
 * same New York instant lands an hour apart in Jakarta depending on the season,
 * so the New York reading is the only one that can be fixed.
 *
 * Returns null when the level is on none of the four instants, and null is
 * honest rather than defensive: the caller falls back to the generic degree tag,
 * because a tag that lies is worse than one that is vague. If this ever returns
 * null on real data it is saying something true about the grid, not about this
 * table.
 */
/**
 * Which weekday a New York cycle belongs to, from the instant it ENDS.
 *
 * A weekly quarter in this engine is a 24-hour cycle running 18:00 to 18:00 New
 * York, and its identity is the weekday - the reference charts label these boxes
 * `Mon` through `Fri` on 13 of 51, more often than the order block, breaker,
 * inverted gap and fair value gap boxes put together. Measured on this engine's
 * own grid, the four weekly quarters run:
 *
 *     Q1  Sun 18:00 -> Mon 18:00
 *     Q2  Mon 18:00 -> Tue 18:00
 *     Q3  Tue 18:00 -> Wed 18:00
 *     Q4  Wed 18:00 -> Thu 18:00
 *
 * so they ARE the day boxes, already, at the right geometry. Only the name was
 * missing, and a reader looking at `Q2` had to do the arithmetic themselves.
 *
 * FROM THE END RATHER THAN THE START, because that is this engine's own cycle
 * convention: `app/liquidity.py` states it as "the cycle is labelled by the
 * calendar date it ENDS on - 18:00 Monday opens Tuesday's cycle". Reading the
 * start would name every box the day before.
 *
 * NEW YORK REGARDLESS OF THE CLOCK PICKER, the same rule `sessionOpenName`
 * follows. The cycle is DEFINED in New York; which zone the reader has chosen for
 * the axis changes how they read the time, not which day the cycle is.
 *
 * Friday is deliberately unreachable here: the week has four quarters and Friday
 * is in none of them, which `app/liquidity.py` also documents.
 */
export function cycleWeekday(endSeconds: number): string {
  return clockTick(endSeconds, "New York", "weekday");
}

export function sessionOpenName(timeSeconds: number): string | null {
  const clock = clockTick(timeSeconds, "New York", "time");
  return SESSION_AT[clock] ?? null;
}

/** Six characters at the longest, which is the tag budget: these are drawn at
 *  the right edge beside the price axis, and the ray stops short of its own
 *  label rather than running under it. */
const SESSION_AT: Record<string, string> = {
  "19:30": "Asia",
  "01:30": "London",
  "07:30": "NY AM",
  "13:30": "NY PM",
};
