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

import type { WyckoffPhase, WyckoffRange } from "@/lib/types";
import { ink, monoFont, plateInk } from "./ink";
import { positionsBox, strokeLine } from "./pixel";
import { claimedLabels, labelFree } from "./structure-primitive";

/**
 * WYCKOFF PHASE READINGS, DAN INI JUGA LAYER BREAKOUT.
 *
 * `sos` adalah range breakout naik yang dikonfirmasi close, `sow` yang turun,
 * dan `spring`/`upthrust` adalah false breakout di kedua sisi. Empat kuadran
 * breakout dan fakeout, dinamai dengan vokabuler Wyckoff.
 *
 * SAMPAI 3 SEPTEMBER 2026 YANG DIGAMBAR HANYA HURUFNYA. Satu tag di bar tempat
 * fase itu tercetak, dan tidak ada lagi: range yang dipecah tidak digambar,
 * level yang dipecah tidak diperpanjang, retest tidak ada. Satu dari empat
 * bentuk yang sebuah breakout butuh untuk terbaca. Seorang pembaca yang
 * melihat `SOS` tidak bisa melihat range APA yang ditembus.
 *
 * EMPAT BENTUK SEKARANG, dan tiap satu dibatasi:
 *
 *   1. RANGE YANG SEDANG BERJALAN, satu box, dari `wyckoff_range`. SATU, bukan
 *      satu per fase: pada lookback 20 sebuah deret 500 bar menghasilkan
 *      ratusan fase, dan catatan ink budget di `globals.css` mengukur bahwa
 *      melewati sekitar sepertiga chart box berhenti menganotasi harga dan jadi
 *      background-nya. Window historis tiap fase tetap ada di payload untuk
 *      siapa pun yang mengauditnya; ia hanya tidak dicat.
 *   2. LEVEL YANG DIPECAH, diperpanjang ke depan dari bar event. Ini objek yang
 *      berbeda dari box: sesudah break, tepi itu jadi harga yang bisa diuji
 *      ulang. Berhenti di retest kalau ada, karena ray yang berjalan
 *      selamanya menumpuk.
 *   3. TAG-nya, seperti sebelumnya.
 *   4. RETEST, sebagai tick TERPISAH di bar yang menyentuh level itu kembali.
 *
 * KENAPA RETEST TERPISAH, dan ini bukan pilihan tata letak. Bulkowski mengukur
 * 8.765 pattern breakout turun: pullback terjadi 58 persen dari waktu, dan
 * sesudah harga balik ke breakout price hasilnya 53 lawan 47. Lebih tajam, 97
 * persen tipe pattern dengan breakout naik perform LEBIH BAIK TANPA throwback.
 * Konfirmasi independen: ORB pullback entry di MNQ stop-out 80,7 persen, n=83.
 * Jadi menggambar retest sebagai bagian dari breakout akan menyandikan asumsi
 * yang datanya tolak. Ia objek sendiri yang kebetulan sering hadir.
 *
 * DAN INI TETAP READING, BUKAN BIAS, karena itu hasil ukur bukan kehati-hatian.
 * `docs/wyckoff_outcomes.json`: keempat fase lawan drift instrumennya sendiri
 * di sembilan instrumen, `sos` n=19.667 t=-0,95 dengan 13 dari 36 fold positif,
 * yaitu di bawah kebetulan. Tak ada panah arah digambar di sini, dan tak akan.
 */

const INK = "structure";
const TAG: Record<string, string> = {
  spring: "SPR",
  upthrust: "UT",
  sos: "SOS",
  sow: "SOW",
};

interface Row {
  x: number;
  y: number;
  tag: string;
  /** Ujung kanan ray level, atau null kalau ia tidak digambar. */
  stop: number | null;
  /** Koordinat x retest, atau null. */
  retest: number | null;
}

interface Box {
  x1: number;
  x2: number;
  yTop: number;
  yBottom: number;
}

class WyckoffRenderer implements IPrimitivePaneRenderer {
  constructor(
    private readonly rows: readonly Row[],
    private readonly box: Box | null,
  ) {}

  draw(target: CanvasRenderingTarget2D): void {
    target.useBitmapCoordinateSpace((scope) => {
      const ctx = scope.context;
      const kx = scope.horizontalPixelRatio;
      const ky = scope.verticalPixelRatio;
      const height = scope.bitmapSize.height;
      const width = scope.bitmapSize.width;

      ctx.save();
      ctx.font = monoFont(9, ky);
      ctx.textBaseline = "middle";

      // --- 1. range yang sedang berjalan ------------------------------------
      // Putus-putus dan tanpa fill. Tanpa fill karena ia satu satunya box di
      // layer ini dan tetap harus lewat di bawah candle tanpa mewarnainya;
      // putus-putus karena tepi range adalah harga yang DIHITUNG dari window,
      // bukan level yang seseorang tempatkan, dan pola dash adalah cara repo
      // ini sudah membedakan keduanya.
      if (this.box) {
        const h = positionsBox(this.box.x1, this.box.x2, kx);
        const v = positionsBox(this.box.yTop, this.box.yBottom, ky);
        const rule = strokeLine(0, kx, 1).width;
        ctx.setLineDash([4 * kx, 3 * kx]);
        ctx.strokeStyle = ink(INK, 0.55);
        ctx.lineWidth = rule;
        ctx.strokeRect(
          h.position + rule / 2,
          v.position + rule / 2,
          Math.max(h.length - rule, 1),
          Math.max(v.length - rule, 1),
        );
        ctx.setLineDash([]);
      }

      // --- 2. level yang dipecah, diperpanjang ------------------------------
      for (const row of this.rows) {
        if (row.stop === null) continue;
        if (row.y < 0 || row.y * ky > height) continue;
        const rule = strokeLine(row.y, ky, 1);
        const x1 = Math.round(row.x * kx);
        const x2 = Math.min(Math.round(row.stop * kx), width);
        if (x2 - x1 < 2) continue;
        ctx.setLineDash([2 * kx, 3 * kx]);
        ctx.strokeStyle = ink(INK, 0.5);
        ctx.lineWidth = rule.width;
        ctx.beginPath();
        ctx.moveTo(x1, rule.centre);
        ctx.lineTo(x2, rule.centre);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      // --- 4. retest, tick vertikal pendek ---------------------------------
      // Digambar SEBELUM tag, supaya tag yang mengklaim ruang label menang
      // atas tick kalau keduanya berebut - tag membawa nama fase, tick hanya
      // membawa "di sini".
      for (const row of this.rows) {
        if (row.retest === null) continue;
        if (row.y < 0 || row.y * ky > height) continue;
        const rule = strokeLine(row.retest, kx, 1);
        const y = Math.round(row.y * ky);
        const reach = Math.round(4 * ky);
        ctx.strokeStyle = ink(INK, 0.8);
        ctx.lineWidth = rule.width;
        ctx.beginPath();
        ctx.moveTo(rule.centre, y - reach);
        ctx.lineTo(rule.centre, y + reach);
        ctx.stroke();
      }

      // --- 3. tag ----------------------------------------------------------
      for (const row of this.rows) {
        if (row.y < 0 || row.y * ky > height) continue;
        const x = Math.round(row.x * kx);
        const y = Math.round(row.y * ky);
        const pad = Math.round(3 * kx);
        const w = ctx.measureText(row.tag).width + pad * 2;
        const h = Math.round(12 * ky);
        const box = { x: x / kx, y: (y - h / 2) / ky, w: w / kx, h: h / ky };
        if (!labelFree(box, claimedLabels)) continue;
        claimedLabels.push(box);
        ctx.fillStyle = plateInk(0.78);
        ctx.fillRect(x, y - h / 2, w, h);
        ctx.fillStyle = ink(INK, 0.85);
        ctx.fillText(row.tag, x + pad, y);
      }
      ctx.restore();
    });
  }
}

export class WyckoffSeriesPrimitive implements ISeriesPrimitive<Time> {
  private chart: IChartApi | null = null;
  private series: ISeriesApi<"Candlestick", Time> | null = null;
  private requestUpdate: (() => void) | null = null;

  private source: readonly WyckoffPhase[] = [];
  private range: WyckoffRange | null = null;
  private rows: Row[] = [];
  private box: Box | null = null;

  private readonly views: readonly IPrimitivePaneView[] = [
    {
      zOrder: () => "normal",
      renderer: () => new WyckoffRenderer(this.rows, this.box),
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
    this.rows = [];
    this.box = null;
  }

  setPhases(
    phases: readonly WyckoffPhase[],
    range: WyckoffRange | null = null,
  ): void {
    this.source = phases;
    this.range = range;
    this.requestUpdate?.();
  }

  updateAllViews(): void {
    const chart = this.chart;
    const series = this.series;
    this.rows = [];
    this.box = null;
    if (!chart || !series) return;
    const scale = chart.timeScale();

    if (this.range) {
      const x1 = scale.timeToCoordinate(this.range.time_from as Time);
      const x2 = scale.timeToCoordinate(this.range.time_to as Time);
      const yTop = series.priceToCoordinate(this.range.high);
      const yBottom = series.priceToCoordinate(this.range.low);
      if (x1 !== null && x2 !== null && yTop !== null && yBottom !== null) {
        this.box = { x1, x2, yTop, yBottom };
      }
    }

    for (const p of this.source) {
      const x = scale.timeToCoordinate(p.at as Time);
      const y = series.priceToCoordinate(p.level);
      if (x === null || y === null) continue;
      // Ray berhenti di retest kalau ada. Kalau tidak ada, ia berhenti di bar
      // terakhir range yang sedang berjalan - bukan di tepi kanan pane, karena
      // level yang berjalan ke tak hingga menumpuk sampai chart-nya jadi kisi.
      const retest =
        p.retested_at === null
          ? null
          : scale.timeToCoordinate(p.retested_at as Time);
      const end =
        retest ??
        (this.box
          ? this.box.x2
          : scale.timeToCoordinate(p.at as Time));
      this.rows.push({
        x,
        y,
        tag: TAG[p.kind] ?? p.kind,
        stop: end !== null && end > x ? end : null,
        retest,
      });
    }
  }

  paneViews(): readonly IPrimitivePaneView[] {
    return this.views;
  }
}
