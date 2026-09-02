/**
 * Apakah objek yang BUKAN box tergambar di tempatnya, dan apakah gayanya menyandi maknanya?
 *
 *   node e2e/nonbox-truth.mjs <out-dir> [interval] [bars]
 *
 * `pixel-truth.mjs` membaca kanvas untuk BOX dan hanya box. Setiap objek lain
 * yang engine ini gambar - ray horizontal, garis putus-putus, pita, caption -
 * tidak pernah dibaca balik satu piksel pun, jadi sebuah ray yang tergambar 40
 * piksel dari harganya akan lolos setiap gate yang ada.
 *
 * Yang diperiksa di sini bukan cuma penempatan. `levels-primitive.ts` membuat
 * gaya garisnya MENYANDI MAKNA, dan itu klaim yang bisa jatuh:
 *
 *   - `dashed: !pool.covered` - pool yang sesinya cuma tertutup sebagian
 *     digambar putus-putus, artinya "high ini mungkin bukan high sesinya".
 *   - `faded: pool.taken_at !== null` - level yang sudah ditembus lebih pudar.
 *   - `dashed: level.derived` untuk period level.
 *   - tepi pita tier horizon: `dashed: true` tanpa syarat.
 *
 * Bug yang membalik salah satu boolean itu meninggalkan angka yang benar di
 * API, garis di harga yang benar di kanvas, dan SETIAP gate hijau, sementara
 * chart-nya memberi tahu pembacanya kebalikan dari kebenaran tentang apakah
 * level itu boleh dipercaya. Pengukuran angka tidak bisa melihat kelas cacat
 * itu, karena angkanya memang benar.
 *
 * ============================================================================
 * TIGA HAL YANG DIUKUR
 * ============================================================================
 *
 *   1. PENEMPATAN. Baris piksel yang tercat dikonversi balik ke harga lewat
 *      price scale chart-nya sendiri, lalu dibandingkan dengan harga di API.
 *   2. DUTY CYCLE. Pecahan piksel bertinta sepanjang ray. Solid mendekati 1,0;
 *      dash [4,3] mendekati 4/7. Yang diuji PEMISAHANNYA, bukan angka
 *      absolutnya: kelompok yang seharusnya putus-putus harus punya duty lebih
 *      rendah daripada yang solid, terpisah lebih lebar daripada noise.
 *   3. FADE. Kekuatan tinta rata-rata. Level yang sudah diambil harus lebih
 *      pudar daripada yang belum.
 *
 * Uji 2 dan 3 dinyatakan sebagai PEMISAHAN ANTAR-KELOMPOK dan bukan ambang
 * tetap. Alpha, lebar dash, dan warna boleh berubah karena alasan desain; yang
 * tidak boleh berubah adalah bahwa kedua kelompok masih bisa dibedakan mata.
 * Ambang tetap akan merah setiap kali seseorang memilih abu-abu yang sedikit
 * berbeda, dan gate yang merah karena alasan yang salah akan dimatikan.
 *
 * ============================================================================
 * DIPINDAI DI KANAN CANDLE TERAKHIR, DAN ITU BUKAN KERAPIAN
 * ============================================================================
 *
 * Versi pertama probe ini memindai ray di sepanjang lebarnya, jadi setiap
 * piksel candle yang ray-nya lewati ikut terhitung sebagai tinta ray.
 * Hasilnya: ray yang PUDAR terukur LEBIH KUAT daripada yang penuh, 0,4389
 * lawan 0,4010, karena kebetulan ray pudar itu melintasi lebih banyak badan
 * candle. Angkanya benar, pertanyaannya yang salah. Di kanan candle terakhir
 * tidak ada yang tercat selain ray, jadi tinta di situ adalah tinta ray.
 *
 * ============================================================================
 * TIGA FLAG YANG TIDAK BISA DIUJI DI FEED INI
 * ============================================================================
 *
 * Dilaporkan sebagai TIDAK DIUJI, bukan sebagai lulus. `pool.covered`,
 * `level.derived` dan `gap.approximate` ketiganya KONSTAN di XAUUSD mt5 pada
 * 15m, 1h dan 4h: 12 dari 12 pool covered, 16 dari 16 level tidak derived,
 * 5 dari 5 gap exact. Cabang `dashed` yang bergantung pada ketiganya tidak
 * pernah dijalankan di data ini, jadi tidak ada yang pernah melihat
 * tampilannya. Yang bisa diuji adalah cabang dash tanpa syarat, yaitu tepi
 * pita tier horizon, dan itulah kelompok putus-putusnya.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? ".playwright-shots";
const INTERVAL = process.argv[3] ?? "1h";
const BARS = Number(process.argv[4] ?? 900);
const API = "http://127.0.0.1:8100";

//: Ray digambar di `Math.round(y * ky) + 0.5`, jadi satu stroke 1px terbelah di
//: dua baris bitmap. Dua piksel adalah rasteriser; di atas itu gambarnya yang
//: salah tempat. Angka yang sama dipakai `pixel-truth.mjs`.
const EDGE_TOL_PX = 2.0;

//: Dash [4,3] memberi 4/7 = 0,571 secara teori, jadi jarak ke solid sekitar
//: 0,43. 0,15 adalah sepertiga margin itu: cukup lebar menolak dua kelompok
//: yang keduanya solid, cukup longgar bertahan saat pola dash-nya diganti.
const DUTY_GAP = 0.15;

//: Idem untuk fade, menolak dua kelompok yang alpha-nya sama tanpa menuntut
//: nilai tertentu.
const FADE_GAP = 0.02;

//: Batas antara STROKE dan FILL, dan angkanya dari pengukuran bukan dari
//: selera. Pita tier horizon punya isian ber-alpha rendah, jadi setiap baris di
//: dalamnya membaca duty 1,000 sama seperti sebuah garis penuh - duty tidak
//: bisa membedakan keduanya. Kekuatan bisa: 33 ray yang terselesaikan di
//: XAUUSD 1h membaca 0,380 sampai 0,591, sementara baris isian membaca 0,048.
//: 0,15 duduk di tengah selisih 8 kali lipat itu.
//:
//: Ray yang hit terdekatnya di bawah ini dilaporkan TIDAK TERSELESAIKAN, bukan
//: salah tempat dan bukan benar. Probe ini tidak bisa mengatakan apakah stroke
//: itu ada, dan mengaku begitu lebih berguna daripada menuduh gambarnya
//: meleset 6 piksel atas bukti yang tidak dimilikinya.
const STROKE_FLOOR = 0.15;

//: Lebar kolom label di kanan, dari `structure-primitive.ts:LABEL_GUTTER`.
//: Ray berhenti di situ, jadi memindai lebih jauh mengukur kolom kosong.
const LABEL_GUTTER = 46;

//: Bar kosong yang digeser ke kanan supaya ada wilayah tanpa candle untuk
//: dipindai. 60 memberi sekitar 150 px pada pane 750 px, dua puluh periode
//: pola dash [4,3], jauh di atas lantai 20 px di `__scan`.
const RIGHT_OFFSET_BARS = 60;

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

// WILAYAH BERSIH DIBUAT, TIDAK DIASUMSIKAN. Diukur pada 2 September 2026: pane
// selebar 750 px dengan candle terakhir di x = 710 dan kolom label mulai di
// 704, jadi lebar wilayah tanpa candle di kanan adalah NEGATIF dan probe versi
// pertama mengembalikan nol baris di ketiga pass tanpa mengatakan kenapa.
// `rightOffset` menggeser candle ke kiri; ray tetap berjalan sampai gutter,
// jadi yang tersisa di kanan cuma ray.
await page.evaluate((bars) => {
  window.__zonelabChart.chart.timeScale().applyOptions({ rightOffset: bars });
}, RIGHT_OFFSET_BARS);
await page.waitForTimeout(2500);

const layerSwitch = async (id) => {
  const label = await page.evaluate(
    async ([api, want]) => {
      const cfg = await (await fetch(`${api}/api/config`)).json();
      return cfg.layers.find((l) => l.id === want)?.label ?? null;
    },
    [API, id],
  );
  if (!label) {
    console.error(`tidak ada layer "${id}" di registry yang API layani`);
    await browser.close();
    process.exit(2);
  }
  return page.getByRole("switch", { name: label, exact: true });
};

// Supply and demand dimatikan sekali di depan. Box-nya mengecat wilayah lebar
// dan setiap baris di dalamnya lolos uji tinta, jadi ia mencemari setiap pass.
await (await layerSwitch("supply_demand")).click();
await page.waitForTimeout(2500);

// Disuntik sekali. Tinggal di halaman karena butuh bitmap kanvas, dan mengirim
// ImageData 1400x800 lewat bridge per ray adalah cara lambat menanyakan hal
// yang sama.
await page.evaluate(() => {
  const BG_TOL = 10;

  const surface = () => {
    const all = [...document.querySelectorAll("canvas")];
    // Kanvas TERBESAR adalah pane-nya. Yang pertama adalah sumbu waktu di
    // sebagian layout, dan sumbu waktu tidak pernah memuat ray.
    return all.sort((a, b) => b.width * b.height - a.width * a.height)[0];
  };

  /** Warna latar, dibaca dan bukan dihardcode.
   *
   *  Tema terang dan gelap memberi latar berbeda, dan probe yang menghardcode
   *  salah satunya melaporkan seluruh kanvas bertinta di tema yang lain.
   */
  const background = (img, w) => {
    const counts = new Map();
    for (let x = 0; x < w; x += 7) {
      const i = (2 * w + x) * 4;
      const key = `${img[i]},${img[i + 1]},${img[i + 2]}`;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    let best = null;
    let run = -1;
    for (const [k, v] of counts) if (v > run) [best, run] = [k, v];
    return best.split(",").map(Number);
  };

  window.__frame = () => {
    const cv = surface();
    const ctx = cv.getContext("2d");
    window.__img = ctx.getImageData(0, 0, cv.width, cv.height).data;
    window.__w = cv.width;
    window.__h = cv.height;
    window.__bg = background(window.__img, cv.width);
    return { w: cv.width, h: cv.height, bg: window.__bg };
  };

  window.__scan = (yWant, xFrom, xTo) => {
    const { __img: img, __w: w, __h: h, __bg: bg } = window;
    const a = Math.max(0, Math.round(xFrom));
    const b = Math.min(w - 1, Math.round(xTo));
    // 20 piksel adalah lantai di mana duty cycle masih berarti: pola [4,3]
    // berulang tiap 7 piksel, jadi di bawah tiga periode sebuah jendela bisa
    // jatuh seluruhnya di dalam satu segmen dan melaporkan solid.
    if (b - a < 20) return null;

    const ink = (x, y) => {
      if (y < 0 || y >= h) return 0;
      const i = (y * w + x) * 4;
      const d =
        Math.abs(img[i] - bg[0]) +
        Math.abs(img[i + 1] - bg[1]) +
        Math.abs(img[i + 2] - bg[2]);
      return d > BG_TOL ? d : 0;
    };

    const row = (y) => {
      let hit = 0;
      let sum = 0;
      for (let x = a; x <= b; x++) {
        const v = ink(x, y);
        if (v) {
          hit++;
          sum += v;
        }
      }
      const n = b - a + 1;
      return { duty: hit / n, strength: hit ? sum / hit / 765 : 0 };
    };

    // Stroke 1px di offset setengah piksel terbelah di dua baris, jadi baris
    // bersebelahan DIJUMLAHKAN alih-alih dipilih salah satu. Memilih yang
    // terkuat adalah cacat yang sama yang pernah membuat breaker terbaca
    // meleset 3,58 piksel: probe-nya, bukan gambarnya.
    const scanned = [];
    for (let dy = -6; dy <= 6; dy++) {
      const y = Math.round(yWant) + dy;
      const here = row(y);
      const next = row(y + 1);
      scanned.push({
        dy,
        y,
        duty: Math.min(1, here.duty + next.duty),
        strength: Math.max(here.strength, next.strength),
      });
    }
    const top = Math.max(...scanned.map((r) => r.duty));
    if (top <= 0) return { dy: 0, y: Math.round(yWant), duty: 0, strength: 0 };

    // YANG TERDEKAT, BUKAN YANG TERKUAT, DAN INI DIUKUR. Versi sebelumnya
    // mengambil duty tertinggi. Duty JENUH di 1,000 - pita tier horizon terisi,
    // jadi setiap baris di dalamnya membaca 1,000, dan ray solid juga 1,000.
    // Dengan seri yang diputus oleh urutan loop, jawabannya selalu dy = -6,
    // tepi jendela pencarian. Delapan ray dilaporkan meleset -6 px dengan
    // duty 1,000 persis dan error harga +3,8 yang seragam, yang adalah tanda
    // tangan sebuah artefak dan bukan tanda tangan delapan gambar yang salah.
    //
    // Pertanyaannya memang "apakah ADA garis di y ini", jadi yang dijawab
    // adalah baris BERTINTA yang paling dekat ke y, dengan ambang relatif
    // terhadap yang terkuat supaya ray pudar tidak tersaring habis.
    const floor = Math.max(0.25, top * 0.7);
    const near = scanned
      .filter((r) => r.duty >= floor)
      .sort((a, b) => Math.abs(a.dy) - Math.abs(b.dy) || a.dy - b.dy);
    return near[0];
  };
});

/** Nyalakan satu layer, ambil payload-nya, ukur tiap ray yang diminta.
 *
 *  Satu layer per pass, dan itu bukan kehati-hatian berlebih: dua layer yang
 *  sama-sama menggambar ray horizontal saling menimpa, dan ray yang tertimpa
 *  terbaca sebagai gambar yang hilang.
 */
const pass = async (layer, pick) => {
  await (await layerSwitch(layer)).click();
  await page.waitForTimeout(5000);

  const drawn = await page.evaluate(
    async ([api, interval, bars, id]) => {
      const r = await fetch(`${api}/api/draw`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: "XAUUSD",
          interval,
          bars,
          layers: [id],
        }),
      });
      return r.json();
    },
    [API, INTERVAL, BARS, layer],
  );

  const wanted = pick(drawn.drawing);
  const geometry = await page.evaluate((lastTime) => {
    const api = window.__zonelabChart;
    window.__frame();
    const x = api.chart.timeScale().timeToCoordinate(lastTime);
    return { lastX: x, width: api.chart.paneSize().width };
  }, drawn.candles.at(-1).time);

  // Jendela pindai: mulai 6 piksel di kanan candle terakhir, berhenti sebelum
  // kolom label. Kalau candle terakhir tidak punya koordinat (di luar layar
  // kanan), pass ini tidak bisa mengisolasi ray dari candle dan dilewati
  // dengan mengatakan begitu.
  const from = (geometry.lastX ?? 0) + 6;
  const to = geometry.width - LABEL_GUTTER - 6;
  // DILAPORKAN, TIDAK DIDIAMKAN. Pass yang jendelanya menyempit mengembalikan
  // nol baris, dan nol baris yang diam tidak bisa dibedakan dari layer yang
  // memang tidak menggambar apa-apa.
  if (geometry.lastX === null || to - from < 20) {
    console.error(
      `pass ${layer} DILEWATI: jendela pindai [${from}, ${to}] terlalu sempit ` +
        `(lastX ${geometry.lastX}, lebar pane ${geometry.width})`,
    );
    await (await layerSwitch(layer)).click();
    await page.waitForTimeout(1500);
    return { layer, rows: [], window: [from, to], skipped: true };
  }

  const rows = [];
  for (const item of wanted) {
    const got = await page.evaluate(
      async ([price, a, b]) => {
        const api = window.__zonelabChart;
        const y = api.series.priceToCoordinate(price);
        if (y === null) return null;
        const hit = window.__scan(y, a, b);
        return hit
          ? { ...hit, back: api.series.coordinateToPrice(hit.y) }
          : null;
      },
      [item.price, from, to],
    );
    if (!got) continue;
    rows.push({ ...item, layer, ...got, price_err: got.back - item.price });
  }

  await (await layerSwitch(layer)).click();
  await page.waitForTimeout(2000);
  return { layer, rows, window: [from, to] };
};

// --------------------------------------------------------------- PASS
const poolsPass = await pass("pools", (d) =>
  (d.pools ?? []).map((p) => ({
    tag: `${p.session}/${p.side}`,
    price: p.price,
    covered: p.covered,
    taken: p.taken_at !== null,
    expect: "solid",
  })),
);

const levelsPass = await pass("liquidity", (d) =>
  (d.levels ?? []).map((l) => ({
    tag: l.name,
    price: l.price,
    derived: l.derived,
    taken: l.taken_at !== null,
    expect: l.derived ? "dashed" : "solid",
  })),
);

// `gaps` menggambar KEDUANYA di satu pass yang sama: event horizon solid
// (`dashed: false`) dan tepi pita tier horizon putus-putus (`dashed: true`).
// Itu perbandingan terbersih yang ada di engine ini - warna sekeluarga, satu
// pass cat, satu-satunya yang berbeda pola dash-nya.
const gapsPass = await pass("gaps", (d) => [
  ...(d.event_horizons ?? []).map((h) => ({
    tag: "EH",
    price: h.price,
    taken: false,
    expect: "solid",
  })),
  ...(d.tier_horizons ?? []).flatMap((t) => [
    { tag: `EV-${t.kind}-top`, price: t.top, taken: false, expect: "dashed" },
    { tag: `EV-${t.kind}-bot`, price: t.bottom, taken: true, expect: "dashed" },
    { tag: `CE-${t.kind}`, price: t.ce, taken: true, expect: "dashed" },
  ]),
]);

const all = [...poolsPass.rows, ...levelsPass.rows, ...gapsPass.rows];
const inked = all.filter((r) => r.duty > 0.05);
const fillOnly = inked.filter((r) => r.strength < STROKE_FLOOR);
const found = inked.filter((r) => r.strength >= STROKE_FLOOR);

// --------------------------------------------------------- 1. PENEMPATAN
// LANTAI ABSOLUT, bukan hanya pecahan. `found >= ceil(0 * 0.5)` adalah
// `0 >= 0`, jadi versi pertama gate ini melaporkan LULUS pada run yang tidak
// menemukan satu ray pun - persis bentuk gate hampa yang seluruh file ini ada
// untuk mencegah, di dalam file itu sendiri.
check(
  "ray ketemu di kanvas",
  all.length >= 6 && found.length >= Math.ceil(all.length * 0.5),
  `${found.length}/${all.length} ray punya tinta di barisnya ` +
    `(pools ${poolsPass.rows.length}, levels ${levelsPass.rows.length}, ` +
    `gaps ${gapsPass.rows.length})`,
);
// TIDAK TERSELESAIKAN DILAPORKAN TERPISAH, dan gate-nya mengikat pada
// JUMLAHNYA. Membuang ray yang membingungkan lalu melaporkan sisanya lulus
// adalah cara sebuah probe jadi hampa satu ray pada satu waktu.
check(
  "tiap ray terselesaikan sebagai stroke, bukan fill",
  fillOnly.length <= 1,
  fillOnly.length
    ? fillOnly
        .map((r) => `${r.layer}/${r.tag} kekuatan ${r.strength.toFixed(3)}`)
        .join("; ")
    : `${found.length} ray, semua di atas ${STROKE_FLOOR}`,
);

const offset = found.filter((r) => Math.abs(r.dy) > EDGE_TOL_PX);
check(
  "ray tergambar di harga yang API laporkan",
  offset.length === 0,
  offset.length
    ? offset.map((r) => `${r.layer}/${r.tag} meleset ${r.dy}px`).slice(0, 6).join("; ")
    : `${found.length} ray, semua dalam ${EDGE_TOL_PX}px`,
);

// --------------------------------------------------------------- 2. DASH
const mean = (xs) =>
  xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null;
const solid = found.filter((r) => r.expect === "solid");
const dashed = found.filter((r) => r.expect === "dashed");
const dutySolid = mean(solid.map((r) => r.duty));
const dutyDashed = mean(dashed.map((r) => r.duty));

if (solid.length < 2 || dashed.length < 2) {
  // DINYATAKAN, TIDAK DIDIAMKAN. Run yang kebetulan cuma punya satu kelompok
  // tidak bisa menguji pemisahan, dan melaporkannya lulus adalah bagaimana
  // sebuah gate jadi hampa.
  check(
    "garis putus-putus benar-benar putus",
    false,
    `tidak bisa diuji: solid=${solid.length} dashed=${dashed.length}, ` +
      "butuh minimal 2 di tiap kelompok",
  );
} else {
  check(
    "garis putus-putus benar-benar putus",
    dutySolid - dutyDashed >= DUTY_GAP,
    `duty solid ${dutySolid.toFixed(3)} (n=${solid.length}) lawan dashed ` +
      `${dutyDashed.toFixed(3)} (n=${dashed.length}), selisih ` +
      `${(dutySolid - dutyDashed).toFixed(3)} butuh >= ${DUTY_GAP}`,
  );
}

// --------------------------------------------------------------- 3. FADE
// Diuji di dalam SATU layer, bukan lintas layer. Alpha dasar tiap layer
// berbeda karena palet, jadi mencampurnya mengukur palet dan bukan fade.
const fadeRows = found.filter((r) => r.layer === "pools" || r.layer === "liquidity");
const standing = fadeRows.filter((r) => !r.taken);
const takenRows = fadeRows.filter((r) => r.taken);
const sStanding = mean(standing.map((r) => r.strength));
const sTaken = mean(takenRows.map((r) => r.strength));

if (standing.length < 2 || takenRows.length < 2) {
  check(
    "level yang sudah diambil digambar lebih pudar",
    false,
    `tidak bisa diuji: standing=${standing.length} taken=${takenRows.length}`,
  );
} else {
  check(
    "level yang sudah diambil digambar lebih pudar",
    sStanding - sTaken >= FADE_GAP,
    `kekuatan standing ${sStanding.toFixed(4)} (n=${standing.length}) lawan ` +
      `taken ${sTaken.toFixed(4)} (n=${takenRows.length}), selisih ` +
      `${(sStanding - sTaken).toFixed(4)} butuh >= ${FADE_GAP}`,
  );
}

// ------------------------------------------- 4. FLAG YANG TIDAK TERUJI
// BUKAN kegagalan, dan BUKAN kelulusan. Sebuah cabang gambar yang datanya tidak
// pernah menyalakannya belum pernah dilihat siapa pun, dan diamnya harus
// terbaca di output alih-alih hilang.
const constant = [];
const spread = (list, key) => new Set(list.map((r) => r[key])).size;
if (poolsPass.rows.length && spread(poolsPass.rows, "covered") === 1)
  constant.push(`pool.covered konstan ${poolsPass.rows[0].covered}`);
if (levelsPass.rows.length && spread(levelsPass.rows, "derived") === 1)
  constant.push(`level.derived konstan ${levelsPass.rows[0].derived}`);
if (constant.length)
  console.log(
    `\nCABANG GAMBAR YANG TIDAK TERUJI DI FEED INI: ${constant.join("; ")}`,
  );

await page.screenshot({ path: `${OUT}/nonbox-truth.png` });
writeFileSync(
  `${OUT}/nonbox-truth.json`,
  JSON.stringify(
    {
      interval: INTERVAL,
      bars: BARS,
      scan_window: poolsPass.window,
      n_rays: all.length,
      n_found: found.length,
      n_fill_only: fillOnly.length,
      stroke_floor: STROKE_FLOOR,
      duty_solid: dutySolid,
      duty_dashed: dutyDashed,
      strength_standing: sStanding,
      strength_taken: sTaken,
      untested_branches: constant,
      rows: all,
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
