/** Apakah garis di canvas mendarat PAS di grid device pixel.
 *
 *  ===========================================================================
 *  KENAPA HARNESS INI TERPISAH DARI YANG LAIN
 *  ===========================================================================
 *
 *  Karena ia harus meluncurkan browser dengan argumen yang berbeda, dan itu
 *  bukan detail. `deviceScaleFactor` per-context milik Playwright melaporkan
 *  `window.devicePixelRatio === 2` ke JS, jadi ia TERLIHAT cukup, tapi ia tidak
 *  memberi fancy-canvas sebuah device-pixel content box - dan itu yang
 *  fancy-canvas baca. Akibatnya bitmap canvas lightweight-charts tetap 1x pada
 *  deviceScaleFactor 1, 2 DAN 3, termasuk di halaman minimal tanpa satu baris
 *  kode Zonelab. `scope.horizontalPixelRatio` selalu 1 dan tidak ada apa pun
 *  yang bisa diukur.
 *
 *  Yang bekerja `--force-device-scale-factor` sebagai ARGUMEN BROWSER. Di sana
 *  ratio bitmap-nya 2,00 dan library-nya menskalakan benar. Sebuah laporan
 *  "retina sudah benar" pernah ditulis di repo ini di atas pengukuran yang
 *  tidak bisa menunjukkan sebaliknya.
 *
 *  ===========================================================================
 *  YANG DIUKUR, DAN KENAPA BUKAN PANJANG RUN
 *  ===========================================================================
 *
 *  Panjang run tidak memutuskan. Rule 1,5px yang memang dipakai project ini SAH
 *  menempati tiga baris di skala 2, jadi "3 baris" bukan bukti kabur.
 *
 *  Yang memutuskan PROFIL ALPHA-nya. Sebuah garis yang mendarat pas punya baris
 *  tepi seterang puncaknya; sebuah garis yang mengangkangi batas device pixel
 *  punya baris tepi sekitar SEPARUH puncaknya. Ukuran itu tidak bergantung
 *  lebar garisnya, dan tepi tepat 0,50 adalah tanda buku teks.
 *
 *  Terukur sebelum diperbaiki, di 14 kolom canvas chart:
 *
 *      skala 1    133 pas,   0 lunak
 *      skala 2     87 pas, 119 lunak, tepi median 0,50
 *
 *  Sesudah `pixel.ts` diadopsi di sembilan file:
 *
 *      skala 1    125 pas,   0 lunak
 *      skala 2    122 pas,   8 lunak, tepi 0,05 sampai 0,18, straddle NOL
 *
 *  Delapan yang tersisa ujung dash dan garis diagonal, yang secara definisi
 *  tidak bisa disejajarkan ke grid. Yang dijaga karena itu bukan "nol garis
 *  lunak" melainkan NOL STRADDLE, yaitu nol garis dengan tepi di sekitar 0,50.
 *
 *  ===========================================================================
 *  KONTROL: LIBRARY-NYA SENDIRI HARUS BERSIH
 *  ===========================================================================
 *
 *  Dengan semua layer Zonelab dimatikan, yang tersisa candle, grid dan sumbu,
 *  semuanya digambar library. Terukur 0 lunak; jumlah garis pas-nya berubah
 *  dengan rentang yang terlihat, jadi yang dijaga hanya nol straddle. Kalau
 *  kontrol itu suatu
 *  saat merah, cacatnya bukan milik kode ini dan mengejarnya di sini akan
 *  membuang waktu.
 */
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";

const SHOTS = process.argv[2] || ".playwright-shots";
const BASE = process.env.ZONELAB_URL || "http://127.0.0.1:3100";
mkdirSync(SHOTS, { recursive: true });

let failed = 0;
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);
  if (!ok) failed += 1;
};

/** Profil alpha tiap garis tipis di 14 kolom canvas terbesar. */
const PROBE = () => {
  const c = [...document.querySelectorAll("canvas")]
    .sort((a, b) => b.width * b.height - a.width * a.height)[0];
  const box = c.getBoundingClientRect();
  const d = c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
  const at = (x, y) => {
    const i = (y * c.width + x) * 4;
    return 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
  };
  const cols = [];
  for (let x = 80; x < c.width - 80; x += Math.floor(c.width / 14)) cols.push(x);
  let crisp = 0;
  const edges = [];
  for (const x of cols) {
    let y = 4;
    while (y < c.height - 5) {
      const base = Math.min(at(x, y - 2), at(x, y - 3));
      if (at(x, y) > base + 12) {
        const rows = [];
        let n = 0;
        while (y + n < c.height - 4 && at(x, y + n) > base + 6) {
          rows.push(at(x, y + n));
          n += 1;
        }
        if (n >= 1 && n <= 8 && Math.abs(at(x, y + n) - base) < 12) {
          const amp = Math.max(...rows) - base;
          if (amp > 10) {
            const lo = Math.min(
              (rows[0] - base) / amp,
              (rows[n - 1] - base) / amp,
            );
            if (lo < 0.7) edges.push(+lo.toFixed(2));
            else crisp += 1;
          }
        }
        y += Math.max(n, 1);
      } else y += 1;
    }
  }
  edges.sort((a, b) => a - b);
  return {
    ratio: +(c.width / box.width).toFixed(2),
    bitmap: `${c.width}x${c.height}`,
    crisp,
    edges,
    // Tepi antara 0,35 dan 0,65 adalah stroke yang mengangkangi batas device
    // pixel. Yang di bawah 0,2 ujung dash atau diagonal.
    straddle: edges.filter((v) => v >= 0.35 && v <= 0.65).length,
  };
};

async function open(scale, { off = false } = {}) {
  const browser = await chromium.launch({
    args: [`--force-device-scale-factor=${scale}`],
  });
  const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 } });
  await ctx.addInitScript(() => localStorage.setItem("zonelab.theme", "dark"));
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 140)));
  await page.goto(`${BASE}/?provider=synthetic`, {
    waitUntil: "networkidle",
    timeout: 240_000,
  });
  await page.waitForTimeout(7_000);
  const names = off
    ? ["Supply and demand"]
    : ["Named levels", "Liquidity pools", "Opening gaps"];
  for (const name of names) {
    const sw = page.getByRole("switch", { name, exact: true });
    if (await sw.count()) {
      await sw.first().click();
      await page.waitForTimeout(2_500);
    }
  }
  await page.waitForTimeout(2_500);
  return { browser, page, errs };
}

// ============================================ aritmetika `pixel.ts` sendiri
// Dijalankan DI BROWSER, karena tidak ada test frontend di repo ini dan
// `pixel.ts` adalah TypeScript yang butuh loader. Halaman-nya sudah memuat
// modulnya, jadi ia dipanggil lewat sana. Kalau `demo()` melempar, seluruh
// pengukuran di bawah berdiri di atas aritmetika yang salah.
{
  const { browser, page } = await open(1);
  const said = await page.evaluate(() => window.__pixelDemo?.() ?? null);
  check("self-check aritmetika pixel.ts lolos di browser",
        said?.includes("OK") === true,
        said ?? "window.__pixelDemo tidak ada, lihat bagian bawah pixel.ts");
  await browser.close();
}

// ============================================================ skala 1 dan 2
for (const scale of [1, 2]) {
  const { browser, page, errs } = await open(scale);
  const got = await page.evaluate(PROBE);
  check(`skala ${scale}: bitmap canvas benar benar ${scale}x`,
        got.ratio === scale, `ratio ${got.ratio}, ${got.bitmap}`);
  check(`skala ${scale}: nol garis mengangkangi batas device pixel`,
        got.straddle === 0,
        `${got.crisp} pas, ${got.edges.length} lunak, straddle ${got.straddle}`
        + (got.edges.length ? `, tepi ${got.edges.join(" ")}` : ""));
  check(`skala ${scale}: ada cukup garis untuk diukur`, got.crisp > 40,
        `${got.crisp} garis pas`);
  check(`skala ${scale}: nol pageerror`, errs.length === 0, errs.slice(0, 2).join(" | "));
  await page.screenshot({ path: `${SHOTS}/retina-${scale}x.png` });
  await browser.close();
}

// ================================================ kontrol: library apa adanya
{
  const { browser, page } = await open(2, { off: true });
  const got = await page.evaluate(PROBE);
  check("kontrol: canvas library sendiri bersih di skala 2",
        got.straddle === 0,
        `${got.crisp} pas, ${got.edges.length} lunak - kalau ini merah, cacatnya `
        + "bukan milik kode kami");
  await browser.close();
}

console.log(`\n${failed === 0 ? "canvas mendarat di grid di kedua skala" : `${failed} GAGAL`}`);
process.exit(failed === 0 ? 0 : 1);
