import type {
  IChartApi,
  IPrimitivePaneRenderer,
  IPrimitivePaneView,
  ISeriesApi,
  ISeriesPrimitive,
  SeriesAttachedParameter,
  Time,
} from "lightweight-charts";
import type { CanvasRenderingTarget2D } from "fancy-canvas";

import type { NewsEvent, SessionQuarter, TrueOpenLevel } from "@/lib/types";
import { cycleWeekday, sessionOpenName } from "@/lib/clock";
import { INKS } from "./ink";
import { LABEL_GUTTER, claimedLabels, labelFree } from "./structure-primitive";

/**
 * The New York cycle grid: quarter boxes and true opens.
 *
 * THE DESIGN IS TAKEN FROM THE OWNER'S OWN 51 ANNOTATED CHARTS, not from taste.
 * Three findings from reading them decided everything here:
 *
 * 1. A NAMED HORIZONTAL RAY WITH ITS LABEL AT THE RIGHT EDGE appears on 24 of 24
 *    of his price charts - every single one - while Fibonacci appears on 12%. It
 *    is the most-used object in his whole practice, so a true open is a ray that
 *    carries its own name, and the name is not optional decoration.
 *
 * 2. A SHADED TIME BOX WITH A DASHED MIDLINE appears on 23 of 25, and it is ONE
 *    family covering both his session boxes and his quarter boxes. The midline is
 *    the point: 50% of a TIME-BOXED range is his dominant measurement, appearing
 *    far more often than any Fibonacci level. So a quarter box draws its own
 *    midline, and that line is a measurement rather than an ornament. An engine
 *    that assumed 50% meant swing-to-swing would draw the wrong line on almost
 *    every chart he has.
 *
 * 3. COLOUR CANNOT TYPE THE OBJECT, and this is his own inconsistency rather
 *    than a preference of mine: pink means a session box on images 27 and 32-37
 *    and a quarter box on 43-51, while orange means the 90-minute timeframe on
 *    some and an IFVG fill on others. Reading his charts requires reading the
 *    LABEL. So this primitive keys everything on the label and uses one neutral
 *    ink, which also keeps the two domain colours - green demand, red supply -
 *    available for the only thing they are allowed to mean.
 *
 * The ink is deliberately colourless for a second reason: the grid is a fact
 * about the clock. It says nothing about price, so giving it a direction colour
 * would assert exactly what eleven failed hypotheses could not.
 */

/** Neutral, and quieter than the structure overlay's own rgb(161, 132, 195):
 *  the grid is context, not an event. The literal here used to read
 *  rgb(154, 166, 181), which was true before `ink.ts` gave each family its own
 *  hue and false afterwards - a comment carrying a stale rgb triple is the exact
 *  failure mode the rest of this sentence goes on to describe.
 *
 *  Stated here rather than read from a CSS variable, because the two theme
 *  tokens that once named these inks were read by nothing and had already
 *  drifted away from the values actually painted. */
const INK = INKS.grid;

/** A TRUE OPEN IS NOT CONTEXT, so it does not get the context ink.
 *
 *  The grid ink is deliberately dark, and that is right for a quarter box: it is
 *  a wash behind the candles. It is wrong for a named horizontal level, which is
 *  the single most-used object in the owner's whole practice - on 24 of his 24
 *  price charts - and which a reader is meant to compare a price against. The
 *  measurement, recomputed against the palette `ink.ts` now owns: the ray at
 *  alpha 0.7 in the grid ink is 2.29:1 against #0b0d10 and its name at 0.95 is
 *  3.26:1. Even at full opacity the grid ink tops out at 3.49:1, so no alpha
 *  available on it can carry 10px text past the 4.5:1 floor. The ink itself had
 *  to change. (This comment shipped with 2.27 / 3.22 / 3.45, measured on the
 *  grey-blue that preceded `INKS.grid`. The conclusion held; the numbers had
 *  moved and nobody had moved them.)
 *
 *  This is the LEVELS overlay's ink, the same rgb(137, 183, 207) an event
 *  horizon and a liquidity pool are drawn in - the old literal here said
 *  rgb(139, 150, 165), from before the five families stopped sharing one hue.
 *  Sharing it is the point rather than a coincidence: a true open belongs to
 *  that family of objects, not to the grid. It is still one neutral ink per
 *  family, so nothing about "colour cannot type the object" changed - inside a
 *  family the label is still the only thing that says which object this is. */
const LEVEL_INK = INKS.levels;

function levelInk(alpha: number): string {
  return `rgba(${LEVEL_INK[0]}, ${LEVEL_INK[1]}, ${LEVEL_INK[2]}, ${alpha})`;
}

/** How loud each degree is. A month box and a micro box are the same object at
 *  different scales, and drawing them alike makes the larger one invisible - so
 *  the bigger the cycle, the more ink it gets. */
const WEIGHT: Record<string, { line: number; fill: number; label: number }> = {
  // EVERY degree in `ALL_DEGREES` needs a row here, coarsest first, and the
  // omission is not cosmetic. `Object.keys` of this map is read twice below: as
  // the paint order, and as the label's ROW INDEX. A degree missing from it gets
  // `indexOf === -1`, so its label row lands at a negative y and draws above the
  // top of the pane - present in the collision map, invisible to the reader.
  // Both of the degrees that live outside `DEGREES` were missing when they
  // shipped, and `e2e/labels.mjs` counted them as off-pane claims rather than
  // failing, because a claim wholly outside the pane is normally harmless.
  quadrennial: { line: 0.55, fill: 0.055, label: 0.9 },
  year: { line: 0.5, fill: 0.05, label: 0.85 },
  month: { line: 0.45, fill: 0.045, label: 0.8 },
  week: { line: 0.4, fill: 0.04, label: 0.75 },
  day: { line: 0.35, fill: 0.035, label: 0.7 },
  session: { line: 0.28, fill: 0.022, label: 0.55 },
  micro: { line: 0.2, fill: 0, label: 0 },
  // Unlabelled and unfilled, like micro. A nano quarter is 337 seconds; on any
  // timeframe that can draw it there are thousands on screen.
  nano: { line: 0.15, fill: 0, label: 0 },
};

function ink(alpha: number): string {
  return `rgba(${INK[0]}, ${INK[1]}, ${INK[2]}, ${alpha})`;
}

/** Short tags, his own vocabulary. TDO is the true daily open, TWO the weekly,
 *  and so on - the labels that appear on his charts, not spelled-out prose which
 *  would not fit beside a price axis.
 *
 *  THE SESSION ENTRY IS A FALLBACK NOW, not the label a reader normally sees.
 *  He does not call them TSO: the session degree's four true opens are Asia,
 *  London, NY AM and NY PM, and `sessionOpenName` names each one from the New
 *  York wall clock of its own timestamp. TSO is what is left when a session
 *  level lands on none of those four instants, which on this engine's own data
 *  never happens - and if it ever does, a vague tag beats a wrong name. */
const OPEN_TAG: Record<string, string> = {
  // T4YO, DAN INI KOREKSI. Tag ini "TQO" sampai 2 September 2026, dan komentar
  // di tempatnya sudah menyebut tabrakannya sebagai risiko: praktisi yang minta
  // degree ini memakai "quarterly cycle" untuk grid kuarter kalender yang
  // degree `year` sudah gambar sebagai TYO. Risiko itu jadi kenyataan begitu
  // referensi kedua masuk. `quarter-sequence.vercel.app` memakai tabel
  // `TO_NAME` di mana TQO adalah cycle 91 hari dan yang empat tahun dinamai
  // T4YO - jadi satu tag yang sama menamai dua cycle yang berbeda di dua chart
  // yang pembacanya sama orang.
  //
  // Referensi yang diikuti, bukan kita, karena TQO di sana punya rumah yang
  // masuk akal (Q untuk quarterly) sementara di sini ia harus dijelaskan tiap
  // kali. Dan itu membebaskan TQO untuk degree QUARTERLY kalau nanti diport -
  // engine ini belum punya cycle 91 hari sama sekali.
  quadrennial: "T4YO",
  year: "TYO",
  month: "TMO",
  week: "TWO",
  day: "TDO",
  session: "TSO",
  micro: "T90mO",
  nano: "TnO",
};

interface QuarterBox {
  quarter: SessionQuarter;
  x1: number;
  x2: number;
}

/** A scheduled release, drawn as a vertical mark.
 *
 *  It lives in THIS primitive rather than a third one because it is the same
 *  kind of object as a quarter boundary: a fact about the clock, drawn as a
 *  vertical line, carrying a label that has to compete for the same space. A
 *  separate primitive would give it an independent label-collision map, and two
 *  maps that do not know about each other is how labels start overprinting. */
interface NewsMark {
  event: NewsEvent;
  x: number;
}

interface OpenRay {
  level: TrueOpenLevel;
  x: number;
  y: number;
}

class SessionRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly boxes: readonly QuarterBox[],
    private readonly rays: readonly OpenRay[],
    private readonly news: readonly NewsMark[],
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;
      const width = scope.bitmapSize.width;

      // THE FRAME'S LABEL MAP IS NOT RESET HERE ANY MORE, and the line that
      // used to do it is worth a note rather than a silent deletion. This pass
      // held `resetLabels` while the grid really was the frame's first pass;
      // then `break-primitive.ts` was attached ahead of it, also at `bottom`,
      // and the reset stayed put. The break primitive's weekend caption was
      // therefore claimed and then wiped by this pass on every single frame -
      // the DFR incident again, one primitive further along. The reset now lives
      // in whichever pass is genuinely first, which is that one.
      //
      // Nothing else changes here: this pass still claims the attribution mark
      // below and its own labels, and it still runs on frames where the grid is
      // switched off.

      // AND THE ONE RECTANGLE NOTHING MAY PAINT UNDER: the library's own
      // attribution mark. It is a DOM anchor - `#tv-attr-logo`, 35x19 flush to
      // the bottom of the pane with a 14px left margin, measured in the browser
      // rather than guessed - so it sits ABOVE the canvas and wins every overlap
      // it is in, and nothing in this codebase could see it.
      //
      // PREVENTION, not a repair. Checked at maximum density - eight layers,
      // every cap lifted, 1149 claims on one frame - and no label had landed
      // there yet; the bottom-left corner is simply where few prices are. But
      // the corner it occupies is the same corner an opening gap's tag uses when
      // its birthplace is the leftmost visible bar, that tag is clamped to x=3
      // by design, and a label the mark covers is not a quiet label, it is a
      // missing one with a white glyph on top.
      //
      // Claimed rather than removed. The mark IS the attribution this library is
      // licensed on, and the alternative - `layout.attributionLogo: false` plus a
      // visible credit elsewhere in the product - is a licensing decision for the
      // owner to make and not a rendering one. Two pixels of padding on each
      // side, because a label touching it is as unreadable as a label under it.
      //
      // TWO THINGS WERE WRONG HERE and the vision audit in `e2e/chart-audit.mjs`
      // found them by looking at a screenshot and saying a caption plate was
      // sitting on the logo. The collision map said that space was free.
      //
      // 1. THE UNITS. `claimedLabels` holds bitmap coordinates throughout - a zone
      //    plate is built at `box.left * kx`, a level tag at
      //    `bitmapSize.width - LABEL_GUTTER * kx` - and this one entry was pushed
      //    in CSS pixels, divided by `ky` in the y term and unscaled in the other
      //    three. At devicePixelRatio 1 the two spaces coincide and it was right
      //    by accident; at 2 it covered CSS 6 to 25.5 of a mark spanning 10 to 45,
      //    less than half of it.
      // 2. THE MARK IS NOT FLUSH TO THE BOTTOM, which the old comment asserted.
      //    It sits 10 CSS pixels above the canvas floor, so a rectangle anchored
      //    at the floor missed it upward as well.
      //
      // Every number below is measured in the browser rather than guessed, and
      // measured at five viewports and two pixel ratios because a library
      // constant that moves with the pane would make all of this useless:
      //
      //   1600x900@1  canvas  950x768   x=10 w=35 h=19  gap=10
      //   1600x900@2  canvas  950x768   x=10 w=35 h=19  gap=10
      //   1280x720@1  canvas  630x562   x=10 w=35 h=19  gap=10
      //   1920x1200@1 canvas 1270x1078  x=10 w=35 h=19  gap=10
      //   1024x768@1  canvas  474x552   x=10 w=35 h=19  gap=10
      //
      // Identical in all five, so it is a fixed constant of the library's layout.
      const LOGO = { x: 10, w: 35, h: 19, bottomGap: 10, pad: 2 };
      claimedLabels.push({
        x: (LOGO.x - LOGO.pad) * kx,
        y: height - (LOGO.bottomGap + LOGO.h + LOGO.pad) * ky,
        w: (LOGO.w + 2 * LOGO.pad) * kx,
        h: (LOGO.h + 2 * LOGO.pad) * ky,
      });

      ctx.save();
      ctx.font = `${Math.round(10 * ky)}px ui-monospace, monospace`;
      ctx.textBaseline = "top";

      // The right-hand column that belongs to ray names. Every horizontal line
      // in this file and in `levels-primitive.ts` stops here, so no line can be
      // painted through a name.
      const gutter = width - LABEL_GUTTER * kx;

      // --- quarter boxes, largest degree first so the small ones sit on top ---
      const order = Object.keys(WEIGHT);
      const sorted = [...this.boxes].sort(
        (a, b) => order.indexOf(a.quarter.degree) - order.indexOf(b.quarter.degree),
      );

      // LABELLED OR NOT IS DECIDED ONCE PER DEGREE ROW, from that row's median
      // segment width, never per segment. This is the rule `cycle-ribbon.tsx`
      // already runs and the reasoning is the same one: deciding it per segment
      // produces a ragged mix where a few wide quarters carry text and their
      // neighbours do not, and a ragged mix reads as missing data rather than as
      // a scale too small for names. Measured off the row's own widest tag, not
      // a constant, because a path label grows a component per degree.
      //
      // Only the quarters that will actually be PAINTED are measured. Counting
      // off-screen ones is how the ribbon's first version talked itself into
      // "too dense to read" on a row of eight perfectly readable segments.
      const labelled = new Set<string>();
      for (const degree of order) {
        if ((WEIGHT[degree] ?? WEIGHT.day).label <= 0) continue;
        const spans = sorted
          .filter((b) => b.quarter.degree === degree && b.x2 * kx > 0 && b.x1 * kx < width)
          .map((b) => Math.min(b.x2 * kx, width) - Math.max(b.x1 * kx, 0))
          .sort((a, b) => a - b);
        if (!spans.length) continue;
        const median = spans[Math.floor(spans.length / 2)];
        const widest = Math.max(
          ...sorted
            .filter((b) => b.quarter.degree === degree)
            .map((b) => ctx.measureText(b.quarter.label).width),
        );
        if (median > widest + 9 * kx) labelled.add(degree);
      }

      for (const box of sorted) {
        const w = WEIGHT[box.quarter.degree] ?? WEIGHT.day;
        const left = Math.round(box.x1 * kx);
        const right = Math.round(box.x2 * kx);
        if (right - left < 2) continue;

        if (w.fill > 0) {
          ctx.fillStyle = ink(w.fill);
          ctx.fillRect(left, 0, right - left, height);
        }

        // The opening edge only. Drawing both edges of every quarter doubles the
        // vertical lines for no information, because one quarter's close IS the
        // next one's open - the grid tiles time exactly, which the accuracy
        // harness checks on 73,956 quarters.
        ctx.strokeStyle = ink(w.line);
        ctx.lineWidth = Math.max(1, Math.round(kx));
        ctx.beginPath();
        ctx.moveTo(left + 0.5, 0);
        ctx.lineTo(left + 0.5, height);
        ctx.stroke();

        // THE MIDLINE, dashed, which is the measurement rather than the frame:
        // 50% of a time-boxed range is what he reads on 23 of 25 charts.
        if (w.fill > 0) {
          const mid = Math.round((left + right) / 2);
          ctx.setLineDash([3 * kx, 3 * kx]);
          ctx.strokeStyle = ink(w.line * 0.9);
          ctx.beginPath();
          ctx.moveTo(mid + 0.5, 0);
          ctx.lineTo(mid + 0.5, height);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // ONE ROW PER DEGREE, which is his own convention rather than a
        // refinement of mine: a coded ribbon with a row per degree - Micro, 90M,
        // Daily, Weekly, Monthly - appears on 21 of his 26 annotated charts, and
        // 20 of them carry the Q1..Q4 labels on the price chart itself.
        //
        // The first version of this file wrote every degree's label on the same
        // top line, and the screenshot showed why that fails: day and session
        // labels interleaved into "Q1 Q2 Q3 Q4 Q2 Q3 Q4 Q1", a sequence that
        // reads as a bug in the grid when the grid was correct. Two scales
        // sharing one row cannot be told apart, and the label is the only thing
        // that types the object here, since colour deliberately does not.
        if (labelled.has(box.quarter.degree)) {
          // A WEEKLY QUARTER CARRIES ITS WEEKDAY, because that is what it IS.
          // These boxes are 24-hour cycles running 18:00 to 18:00 New York, so Q1
          // is Monday's cycle and Q4 is Thursday's - measured, not assumed - and
          // the reference charts label exactly these boxes `Mon` to `Fri` on 13 of
          // 51, more often than the four imbalance detectors combined. The
          // geometry was already right; only the name was missing, and `Q2` left
          // the reader doing the arithmetic. Derived from the box's own end
          // timestamp rather than from its index, so if the clock ever produces a
          // span this mapping does not expect, the label says what is true.
          const text =
            box.quarter.degree === "week"
              ? `${box.quarter.label} ${cycleWeekday(box.quarter.time_to)}`
              : box.quarter.label;
          const tw = ctx.measureText(text).width;
          const pad = 3 * kx;
          // CLAMPED TO THE PANE, the same fix `levels-primitive` already carries
          // for a gap band's tag and for the same reason: a box whose left edge
          // is off-screen put its label at a negative x, so the widest and most
          // prominent boxes were the ones drawn with half a name. It surfaced the
          // moment the quadrennial degree shipped - a four-year box begins long
          // before any intraday window - and `e2e/labels.mjs` failed it as a word
          // cut in half rather than anyone noticing it in a screenshot.
          const lx = Math.max(left, 0) + pad;
          const ly = pad + order.indexOf(box.quarter.degree) * 13 * ky;
          const rect = { x: lx, y: ly, w: tw + pad, h: 12 * ky };
          // CLAIMED, not merely tested. The test was here from the start and the
          // push was not, so every quarter label checked a map it never wrote
          // to: two quarter labels on one row could not see each other, and
          // nothing downstream could see either of them.
          if (labelFree(rect, claimedLabels)) {
            claimedLabels.push(rect);
            ctx.fillStyle = ink(w.label);
            ctx.fillText(text, lx, ly);
          }
        }
      }

      // --- true opens: a ray, and its name at the right edge ------------------
      for (const ray of this.rays) {
        const y = Math.round(ray.y * ky) + 0.5;
        const x = Math.round(ray.x * kx);
        // The session degree says the NAME of the session it opens; every other
        // degree keeps its tag. `tw` is measured from whatever comes back, so a
        // six-character "London" moves the ray's stop and its claimed rectangle
        // with it rather than overrunning the price axis.
        // A `~` on an approximate level, the same mark an approximate gap band
        // carries. The suffix is inside `tag` before the width is measured, so
        // the ray's stop and its claimed rectangle both account for it rather
        // than the extra character overrunning the price axis.
        const tag =
          ((ray.level.degree === "session" ? sessionOpenName(ray.level.time) : null) ??
            OPEN_TAG[ray.level.degree] ??
            ray.level.degree) + (ray.level.approximate ? "~" : "");
        const tw = ctx.measureText(tag).width;
        const pad = 4 * kx;
        // ONE stop for every ray on the chart, not one per tag. A per-tag stop
        // let a short-tagged ray run further right than a long-tagged one and
        // straight through its neighbour's name - see LABEL_GUTTER.
        const stop = gutter;

        // DASHED AND DIMMER WHEN APPROXIMATE. The price came from a bar after
        // the boundary rather than on it - 18 to 19 hours after, at the
        // quadrennial degree, because 1 January is a holiday every year - and a
        // solid line would claim a precision the feed cannot support. Exactly
        // the move an approximate gap band already makes, for the same reason.
        ctx.setLineDash(ray.level.approximate ? [4 * kx, 3 * kx] : []);
        ctx.strokeStyle = levelInk(ray.level.approximate ? 0.55 : 0.85);
        ctx.lineWidth = Math.max(1, Math.round(kx));
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(Math.max(x, stop), y);
        ctx.stroke();
        ctx.setLineDash([]);

        const rect = { x: stop, y: y - 6 * ky, w: tw + pad, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          ctx.fillStyle = levelInk(ray.level.approximate ? 0.75 : 1);
          ctx.textBaseline = "middle";
          ctx.fillText(tag, stop + pad / 2, y);
          ctx.textBaseline = "top";
        }
      }

      // --- scheduled releases: a vertical mark and its own name -------------
      // Dashed, and in the accent rather than the grid's neutral ink, because
      // unlike a quarter boundary this is not something the clock guarantees -
      // it is a third party's published schedule and it can move or be wrong.
      for (const mark of this.news) {
        const x = Math.round(mark.x * kx) + 0.5;
        ctx.setLineDash([2 * ky, 5 * ky]);
        ctx.strokeStyle = "rgba(217, 164, 65, 0.55)";
        ctx.lineWidth = Math.max(1, Math.round(kx));
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
        ctx.setLineDash([]);

        // Currency plus a short title. The currency first because a gold trader
        // scanning the chart needs to know WHOSE release it is before caring
        // what it is called.
        const tag = `${mark.event.currency} ${mark.event.title}`.slice(0, 26);
        const tw = ctx.measureText(tag).width;
        const pad = 3 * kx;
        // Flipped to the left of its line when the right side would run off the
        // canvas - which is the LIVE case, since the release nearest now sits
        // nearest the right edge. Unflipped it was drawn off-screen, which
        // looks exactly like never having been drawn.
        //
        // Flipping is not a promise that it appears: a flipped label can land
        // on the one before it, and then the collision rule below drops it, on
        // purpose. Two names in the same pixels are less readable than one.
        const left = x + pad + tw > width;
        const tx = left ? x - pad - tw : x + pad;
        const rect = { x: tx, y: height - 26 * ky, w: tw + pad, h: 12 * ky };
        if (labelFree(rect, claimedLabels)) {
          claimedLabels.push(rect);
          ctx.fillStyle = "rgba(217, 164, 65, 0.9)";
          ctx.fillText(tag, tx, height - 26 * ky);
        }
      }

      ctx.restore();
    });
  }
}

/**
 * Attached BEFORE the structure and zone primitives, so the grid paints beneath
 * both. The library draws `normal` views in attach order onto one pane bitmap,
 * and the grid is context: a quarter divider crossing a zone border must lose,
 * because the border's position is verified to the pixel and the divider's is
 * not load-bearing.
 */
export class SessionSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;
  private quarters: readonly SessionQuarter[] = [];
  private opens: readonly TrueOpenLevel[] = [];
  private boxes: QuarterBox[] = [];
  private rays: OpenRay[] = [];
  private news: NewsEvent[] = [];
  private marks: NewsMark[] = [];

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "bottom",
      renderer: () => new SessionRenderer(this.boxes, this.rays, this.marks),
    },
  ];

  attached(param: SeriesAttachedParameter<Time>): void {
    this.chart = param.chart;
    this.series = param.series as ISeriesApi<"Candlestick", Time>;
    this.requestUpdate = param.requestUpdate;
  }

  detached(): void {
    this.chart = null;
    this.series = null;
    this.requestUpdate = null;
    this.boxes = [];
    this.rays = [];
  }

  setSession(
    quarters: readonly SessionQuarter[],
    opens: readonly TrueOpenLevel[],
    news: readonly NewsEvent[] = [],
  ): void {
    this.quarters = quarters;
    this.opens = opens;
    this.news = [...news];
    this.requestUpdate?.();
  }

  /** Recomputed on every pan, zoom and data change. A cached pixel position is a
   *  boundary detached from the bar it describes. */
  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    if (!chart || !series) {
      this.boxes = [];
      this.rays = [];
      this.marks = [];
      return;
    }
    const timeScale = chart.timeScale();

    // Built with pushes rather than map-then-filter. `timeToCoordinate` returns
    // a branded `Coordinate`, so a `b is QuarterBox` predicate over a nullable
    // union does not narrow - the branded type is not assignable back to the
    // plain `number` the interface declares, and the compiler is right about it.
    // HALF A BAR EACH SIDE, the same correction `zone-primitive.ts` carries and
    // for the same measured reason: `timeToCoordinate` answers a bar's CENTRE,
    // so anchoring straight to it draws the box from the middle of its first bar
    // to the middle of its last. Half of each end bar then sits outside the box
    // that describes it, and the left border lands on that candle's own
    // x-position where the candle - drawn on top - hides it. The news mark below
    // has always corrected for this; the quarter box did not, and no pixel
    // harness covered it because `pixel-truth.mjs` only reads box detectors.
    const halfBar = timeScale.options().barSpacing / 2;
    this.boxes = [];
    for (const quarter of this.quarters) {
      const x1 = timeScale.timeToCoordinate(quarter.time_from as Time);
      const x2 = timeScale.timeToCoordinate(quarter.time_to as Time);
      if (x1 !== null && x2 !== null) {
        this.boxes.push({ quarter, x1: x1 - halfBar, x2: x2 + halfBar });
      }
    }

    this.marks = [];
    const spacing = timeScale.options().barSpacing;
    for (const event of this.news) {
      // Asked for the bar the release happened DURING, never for the release's
      // own minute: 08:30 New York is 12:30 UTC and no hourly bar opens then,
      // so `timeToCoordinate` answers null and three releases in five would
      // silently vanish. The coordinate it does answer is the bar's CENTRE, so
      // the offset is measured from the bar's left edge - half a spacing back.
      const centre = timeScale.timeToCoordinate(event.bar as Time);
      if (centre !== null) {
        this.marks.push({ event, x: centre + (event.offset - 0.5) * spacing });
      }
    }

    this.rays = [];
    for (const level of this.opens) {
      // POSITIONED AT `bar`, NOT AT `time`. The time scale is indexed by BAR, so
      // it answers null for any instant no bar opened on - and `time` is the
      // quarter boundary, which for an approximate level is by definition an
      // instant no bar opened on. Asking for the boundary silently dropped every
      // approximate ray: eight true opens came back from the API on a weekly
      // chart and the price pane drew none of them.
      //
      // This is the same defect the news marks already carry a `bar` field to
      // avoid - 08:30 New York is 12:30 UTC, no hourly bar opens then, and three
      // releases in five went missing without a word. The fix is the same one:
      // the backend, which has the bar times, says which bar; the canvas does
      // not try to re-derive it. `bar` equals `time` on every exact level, so
      // nothing about the strict case changes.
      const x = timeScale.timeToCoordinate(level.bar as Time);
      const y = series.priceToCoordinate(level.price);
      if (x !== null && y !== null) this.rays.push({ level, x, y });
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
