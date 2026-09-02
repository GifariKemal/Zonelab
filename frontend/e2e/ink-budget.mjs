/**
 * Berapa tinta yang tiap layer tambahkan DI ATAS candle, dalam piksel?
 *
 *   node e2e/ink-budget.mjs <out-dir> [interval] [bars]
 *
 * `app/overlays.py` menulis "this project has measured what happens to a chart
 * past about a third ink coverage" dan angka itu dipakai untuk membenarkan
 * keputusan tampilan di beberapa tempat - satu range projection alih-alih
 * empat, satu DFR per cycle, cap 16 named level. Tapi tidak ada satu pun
 * harness yang pernah mengukur berapa tinta yang sebuah layer benar-benar
 * tambahkan, jadi setiap keputusan itu berdiri di atas angka yang tidak bisa
 * ditunjuk siapa pun.
 *
 * Ini yang membuatnya bisa ditunjuk, dan ia lahir dari keluhan pembaca yang
 * spesifik: "Liquidity pools dan Named levels kok ada garis yg kenak bar ya".
 * Keluhan itu tentang tinta di atas harga, jadi yang diukur tinta di atas
 * harga.
 *
 * CARANYA DIFF, BUKAN AMBANG WARNA. Bitmap diambil dengan SEMUA overlay mati,
 * lalu sekali lagi per layer, dan yang dihitung piksel yang BERUBAH. Itu
 * atribusi yang tepat: tidak ada tebak-tebakan warna mana milik layer mana, dan
 * warna candle yang kebetulan sama dengan warna layer tidak bisa ikut terhitung.
 * `pixel-truth.mjs` sudah kena masalah itu - warna badan candle IDENTIK dengan
 * warna zona, jadi probe-nya tidak bisa mengisolasi zona sendirian.
 *
 * DIBATASI KE WILAYAH CANDLE. Tinta di kolom kosong sebelah kanan tidak menutupi
 * apa pun dan tidak ada yang mengeluhkannya; yang dikeluhkan garis yang melintas
 * di atas bar. Jadi jendelanya dari bar pertama sampai bar terakhir, dan kolom
 * label dibuang.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? ".playwright-shots";
const INTERVAL = process.argv[3] ?? "1h";
const BARS = Number(process.argv[4] ?? 900);
const API = "http://127.0.0.1:8100";

//: Layer yang diukur. Bukan seluruh registry: yang menarik di sini layer yang
//: menggambar RAY horizontal panjang, karena itu yang dikeluhkan. `structure`
//: dan `session` ikut sebagai pembanding - keduanya menggambar banyak sekali
//: objek, jadi kalau pools terlihat besar, angka itu butuh tetangga untuk
//: dibaca.
const LAYERS = ["pools", "liquidity", "gaps", "projections", "structure", "session"];

//: Layer yang menggambar NOL dengan setelan default, dan hitungannya diukur -
//: bukan didaftar dari ingatan. `e2e/wiring.mjs` menemukannya dengan
//: menggambar tiap layer sendirian: `session`, `dfr`, `ssmt` dan `psp` kembali
//: kosong dan dua belas lainnya tidak. Harness ini mengukurnya lagi lewat diff
//: piksel dan `session` memang menambahkan nol.
//:
//: DUA ARAH, dan itu yang membuatnya tetap mengikat. Kalau daftar ini hanya
//: dipakai untuk MEMAAFKAN, sebuah layer yang berhenti menggambar akan diam-diam
//: masuk ke sini dan gate-nya tetap hijau. Jadi yang di luar daftar HARUS
//: menggambar, dan yang di dalam daftar harus TETAP kosong: sebuah default yang
//: berubah tanpa ada yang memutuskannya juga merah.
const EMPTY_BY_DEFAULT = new Set(["session", "dfr", "ssmt", "psp"]);

//: Ambang yang sudah dikutip di repo ini tanpa pernah diukur, dinyatakan di sini
//: sebagai apa adanya: sebuah RUJUKAN, bukan gerbang. Tidak ada satu pun angka
//: di repo ini yang membuktikan sepertiga adalah tempat chart jadi tak terbaca,
//: jadi harness ini MELAPORKAN dan tidak menghakimi.
const CITED_CEILING = 1 / 3;

const results = [];
const check = (n, p, d = "") =>
  results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({
  viewport: { width: 1400, height: 800 },
  deviceScaleFactor: 1,
});
await page.goto("http://127.0.0.1:3100/", { waitUntil: "networkidle" });
await page.waitForTimeout(6000);
await page
  .locator(`div[aria-label="Timeframe"] button:text-is("${INTERVAL}")`)
  .click();
await page.waitForTimeout(2500);

const labelOf = async (id) =>
  page.evaluate(
    async ([api, want]) => {
      const cfg = await (await fetch(`${api}/api/config`)).json();
      return cfg.layers.find((l) => l.id === want)?.label ?? null;
    },
    [API, id],
  );

const switchOf = async (id) => {
  const label = await labelOf(id);
  if (!label) {
    console.error(`tidak ada layer "${id}" di registry`);
    await browser.close();
    process.exit(2);
  }
  return page.getByRole("switch", { name: label, exact: true });
};

// SEMUA MATI DULU. Baseline yang masih memuat satu layer akan mengurangi tinta
// layer itu dari setiap pengukuran berikutnya, dan hasilnya terlihat masuk akal.
const on = await page.evaluate(async (api) => {
  const cfg = await (await fetch(`${api}/api/config`)).json();
  return cfg.layers.map((l) => l.id);
}, API);
const live = [];
for (const id of on) {
  const sw = await switchOf(id).catch(() => null);
  if (!sw) continue;
  if ((await sw.getAttribute("aria-checked")) === "true") live.push(id);
}
for (const id of live) {
  await (await switchOf(id)).click();
  await page.waitForTimeout(700);
}
await page.waitForTimeout(4000);

await page.evaluate(() => {
  const surface = () =>
    [...document.querySelectorAll("canvas")].sort(
      (a, b) => b.width * b.height - a.width * a.height,
    )[0];

  window.__grab = () => {
    const cv = surface();
    const ctx = cv.getContext("2d");
    return {
      data: [...ctx.getImageData(0, 0, cv.width, cv.height).data],
      w: cv.width,
      h: cv.height,
    };
  };

  /** Piksel yang BERBEDA antara dua bitmap, di jendela x yang diberikan.
   *
   *  Toleransi 8 per kanal: kompositing alpha memindahkan nilai satu atau dua
   *  langkah di piksel yang tidak ada layer menyentuhnya, dan menghitung itu
   *  sebagai tinta akan melaporkan seluruh kanvas berubah.
   */
  window.__diff = (a, b, xFrom, xTo) => {
    let changed = 0;
    let total = 0;
    for (let y = 0; y < a.h; y++) {
      for (let x = xFrom; x <= xTo; x++) {
        const i = (y * a.w + x) * 4;
        total++;
        if (
          Math.abs(a.data[i] - b.data[i]) > 8 ||
          Math.abs(a.data[i + 1] - b.data[i + 1]) > 8 ||
          Math.abs(a.data[i + 2] - b.data[i + 2]) > 8
        ) {
          changed++;
        }
      }
    }
    return { changed, total };
  };
});

const geometry = await page.evaluate(async ([api, interval, bars]) => {
  const r = await fetch(`${api}/api/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol: "XAUUSD", interval, bars, layers: [] }),
  });
  const d = await r.json();
  const chart = window.__zonelabChart.chart;
  const scale = chart.timeScale();
  const first = scale.timeToCoordinate(d.candles[0].time);
  const last = scale.timeToCoordinate(d.candles.at(-1).time);
  return { first, last, width: chart.paneSize().width };
}, [API, INTERVAL, BARS]);

// Jendela CANDLE, dan kolom label dibuang. Kalau bar pertama di luar layar
// kiri, dipakai tepi pane: yang diukur wilayah tempat harga tergambar.
const xFrom = Math.max(0, Math.round(geometry.first ?? 0));
const xTo = Math.min(
  geometry.width - 46 - 1,
  Math.round(geometry.last ?? geometry.width),
);

const baseline = await page.evaluate(() => window.__grab());
const rows = [];
for (const id of LAYERS) {
  const sw = await switchOf(id);
  await sw.click();
  await page.waitForTimeout(4500);
  const withLayer = await page.evaluate(() => window.__grab());
  const got = await page.evaluate(
    ([a, b, f, t]) => window.__diff(a, b, f, t),
    [baseline, withLayer, xFrom, xTo],
  );
  await sw.click();
  await page.waitForTimeout(1500);
  rows.push({
    layer: id,
    ink_px: got.changed,
    region_px: got.total,
    coverage: got.changed / got.total,
  });
  console.log(
    `  ${id.padEnd(12)} ${String(got.changed).padStart(7)} px  ` +
      `${((got.changed / got.total) * 100).toFixed(2)}% dari wilayah candle`,
  );
}

// -------------------------------------------------------------- VONIS
// TIDAK ADA LAYER YANG BOLEH MENUTUPI SELURUH WILAYAH. Itu satu-satunya klaim
// yang bisa ditegakkan tanpa angka yang belum ada: sepertiga adalah rujukan
// yang dikutip di repo ini dan tidak pernah diukur, jadi ia DILAPORKAN dan
// tidak dijadikan gerbang. Yang dijadikan gerbang cuma hal yang jelas rusak.
const worst = rows.reduce((m, r) => (r.coverage > m.coverage ? r : m), rows[0]);
check(
  "tidak ada layer yang menutupi lebih dari separuh wilayah candle",
  worst.coverage < 0.5,
  `terberat ${worst.layer} pada ${(worst.coverage * 100).toFixed(2)}%`,
);
const shouldDraw = rows.filter((r) => !EMPTY_BY_DEFAULT.has(r.layer));
const shouldNot = rows.filter((r) => EMPTY_BY_DEFAULT.has(r.layer));
const mute = shouldDraw.filter((r) => r.ink_px === 0);
const loud = shouldNot.filter((r) => r.ink_px > 0);
check(
  "layer yang punya default menggambar sesuatu",
  mute.length === 0,
  mute.map((r) => `${r.layer} nol piksel`).join("; ") ||
    `${shouldDraw.length} layer, semuanya menggambar`,
);
check(
  "layer yang kosong-default tetap kosong",
  loud.length === 0,
  loud.map((r) => `${r.layer} ${r.ink_px} px`).join("; ") ||
    `${shouldNot.length} layer, dan diamnya sudah disuarakan di rail ` +
      "lewat meta reason",
);

const total = rows.reduce((s, r) => s + r.coverage, 0);
console.log(
  `\njumlah kasar kalau keenamnya menyala: ${(total * 100).toFixed(2)}% ` +
    `(rujukan yang dikutip repo ini: ${(CITED_CEILING * 100).toFixed(0)}%, ` +
    `dan rujukan itu sendiri belum pernah diukur)`,
);

writeFileSync(
  `${OUT}/ink-budget.json`,
  JSON.stringify(
    {
      interval: INTERVAL,
      bars: BARS,
      candle_region: { x_from: xFrom, x_to: xTo, px: rows[0]?.region_px ?? 0 },
      cited_ceiling: CITED_CEILING,
      rows: rows.sort((a, b) => b.coverage - a.coverage),
      sum_coverage_if_all_on: total,
    },
    null,
    2,
  ),
);

await browser.close();
for (const line of results) console.log(line);
const failed = results.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${results.length - failed}/${results.length} lolos`);
process.exit(failed ? 1 : 0);
