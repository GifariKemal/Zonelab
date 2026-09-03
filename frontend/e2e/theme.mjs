/** Dua theme, dan setiap angka yang dipakai membenarkannya dibaca balik.
 *
 *  KENAPA INI ADA. Tabel kontras di kepala `globals.css` ditulis satu kali dari
 *  sebuah skrip di scratchpad. Sebuah tabel yang tidak pernah dibaca ulang
 *  adalah komentar, dan komentar tidak gagal saat seseorang menaikkan
 *  `--text-faint` setengah stop. Harness ini menghitung ulang seluruh tabel itu
 *  dari browser yang sungguhan, di kedua theme, dan exit 1 kalau meleset.
 *
 *  YANG DIPERIKSA, dan tiap butir menutup cacat yang benar benar sudah terjadi
 *  di repo ini:
 *
 *    1. TOKEN LENGKAP DI KEDUA THEME. Sebuah token yang cuma ada di gelap akan
 *       jatuh ke nilai gelapnya di terang, diam saja, dan cuma satu permukaan
 *       yang salah - persis kelas cacat yang paling sulit dilihat.
 *    2. KELAS TAILWIND YANG TOKEN-NYA TIDAK ADA. `page.tsx` memakai `text-fg`
 *       dan `text-fg-dim` selama entah berapa lama; keduanya tidak pernah
 *       dideklarasikan, Tailwind tidak memancarkan apa apa, dan state MENYALA
 *       dan MATI dua tombol rail keluar warna yang identik. Diukur di browser
 *       sebelum diperbaiki: keduanya rgb(228, 232, 237).
 *    3. FLOOR KONTRAS. Ketiga tier teks, di kedua theme, lawan background-nya
 *       masing masing.
 *    4. PASANGAN SEMANTIK. Jarak L*, kontras greyscale, DAN urutannya. Yang
 *       ketiga yang paling mudah hilang: percobaan pertama palette terang
 *       mematok demand dan supply ke rasio kontras yang sama, yang terdengar
 *       benar dan memberi jarak L* 0,0 - di greyscale keduanya jadi satu warna.
 *    5. CANVAS IKUT BERGANTI. Canvas tidak bisa memakai kelas CSS, jadi ia
 *       berganti hanya kalau `setInkTheme` dipanggil DAN sesuatu memaksa
 *       repaint. Kalau salah satu putus, warnanya BASI dan bukan salah. Ini
 *       diperiksa dengan membaca bitmap chart-nya kembali di kedua theme.
 *    6. SETIAP LAYER PUNYA GLYPH. `LAYER_SWATCH` sudah pernah kehilangan layer
 *       baru tanpa suara, dan `LAYER_ICON` adalah peta kedua dengan bentuk
 *       kegagalan yang sama.
 *    7. SETIAP KONTROL PUNYA STATE. Audit menghitung NOL varian `active:` di
 *       seluruh `src/`: 55 tombol, 25 switch, 12 slider, dan tak satu pun
 *       memberi tanda bahwa ia sedang ditekan.
 *    8. TIDAK ADA KEDIPAN THEME SALAH. Preferensi terang yang tersimpan harus
 *       sudah berlaku di frame pertama, bukan sesudah effect React.
 *
 *  Dipatok ke provider `synthetic`, alasan yang sama dengan `labels.mjs` dan
 *  `clickthrough.mjs`: sebuah harness yang berubah sendiri antar run tidak bisa
 *  dipakai menilai perubahan.
 *
 *  DIBUKTIKAN TIDAK KOSONG. Tiap check di bawah pernah dijalankan dengan
 *  cacatnya disuntikkan kembali, dan hasilnya dicatat di `docs/QA-UI.md`.
 */
import { chromium } from "playwright";
import { mkdirSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SHOTS = process.argv[2] || ".playwright-shots";
const BASE = process.env.ZONELAB_URL || "http://127.0.0.1:3100";
const API = BASE.replace("3100", "8100");
mkdirSync(SHOTS, { recursive: true });

let failed = 0;
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}${detail ? ` :: ${detail}` : ""}`);
  if (!ok) failed += 1;
};

// ==================================================================== warna
const srgb = (c) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const lum = ([r, g, b]) =>
  0.2126 * srgb(r / 255) + 0.7152 * srgb(g / 255) + 0.0722 * srgb(b / 255);
/** Kontras WCAG. Ia SUDAH hue-blind, jadi ia juga kontras greyscale-nya - dan
 *  itu bukan detail: versi pertama skrip yang menurunkan palette ini menghitung
 *  greyscale lewat langkah tambahan yang me-round luminance ke integer, dan
 *  angkanya meleset dari 1,74 yang `globals.css` catat ke 2,10. */
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const lstar = (c) => {
  const y = lum(c);
  return y > 0.008856 ? 116 * Math.cbrt(y) - 16 : 903.3 * y;
};
const hue = ([r, g, b]) => {
  const [x, y, z] = [r / 255, g / 255, b / 255];
  const max = Math.max(x, y, z);
  const min = Math.min(x, y, z);
  if (max === min) return 0;
  const d = max - min;
  const h =
    max === x ? (y - z) / d + (y < z ? 6 : 0) : max === y ? (z - x) / d + 2 : (x - y) / d + 4;
  return h * 60;
};
const parse = (v) => {
  const t = v.trim();
  const m = t.match(/^#?([0-9a-f]{6})$/i);
  if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
  const r = t.match(/(\d+(?:\.\d+)?)/g);
  return r ? r.slice(0, 3).map(Number) : null;
};
const near = (got, want, tol) => Math.abs(got - want) <= tol;
const arc = (a, b) => {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
};

// ============================================ 2. kelas Tailwind tanpa token
// Statis, karena sebuah kelas yang tidak memancarkan CSS TIDAK ADA di DOM dan
// tidak bisa ditemukan dengan melihat halaman jadinya. Itu sebabnya `text-fg`
// hidup begitu lama: ia tidak salah di layar, ia cuma tidak ada.
const SRC = "src";
const files = [];
(function walk(dir) {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(tsx?|css)$/.test(e)) files.push(p);
  }
})(SRC);

const declared = new Set();
const css = readFileSync("src/app/globals.css", "utf-8");
for (const m of css.matchAll(/--color-([a-z0-9-]+):/g)) declared.add(m[1]);

// Kedua blok theme harus mendeklarasikan kunci yang SAMA PERSIS, dan ini harus
// dibaca dari CSS-nya bukan dari browser. Custom property MEWARIS: sebuah token
// yang hilang di blok terang jatuh diam diam ke nilai gelapnya, dan
// `getComputedStyle` akan melaporkannya ada. Versi pertama check ini memakai
// browser dan tetap hijau saat `--info` dihapus dari blok terang.
const blockKeys = (head) => {
  const at = css.indexOf(head);
  if (at < 0) return null;
  const body = css.slice(at, css.indexOf(String.fromCharCode(10) + "}", at));
  return new Set([...body.matchAll(/^\s{2}--([a-z0-9-]+):/gm)].map((m) => m[1]));
};
const rootKeys = blockKeys(":root {");
const lightKeys = blockKeys(':root[data-theme="light"] {');
{
  // Alpha dan pola dash tidak bergantung theme dan memang hanya ada di `:root`.
  const shared = new Set(["zone-fill-near", "zone-fill-far", "zone-edge-near",
    "zone-edge-hover", "zone-edge-far", "dash-sd", "dash-fvg", "dash-ob",
    "dash-ifvg", "dash-brk"]);
  const onlyDark = rootKeys && lightKeys
    ? [...rootKeys].filter((k) => !lightKeys.has(k) && !shared.has(k)) : ["blok tidak terbaca"];
  const onlyLight = rootKeys && lightKeys
    ? [...lightKeys].filter((k) => !rootKeys.has(k)) : [];
  check("kedua blok theme mendeklarasikan token yang sama",
        onlyDark.length === 0 && onlyLight.length === 0,
        onlyDark.length || onlyLight.length
          ? `hanya gelap: ${onlyDark.join(", ") || "-"} | hanya terang: ${onlyLight.join(", ") || "-"}`
          : `${lightKeys.size} token di kedua blok, ${shared.size} token bersama`);
}
// Palet bawaan Tailwind yang memang sah dipakai, plus kata kunci yang bukan
// warna sama sekali.
const BUILTIN =
  /^(transparent|current|inherit|black|white|slate|gray|grey|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(-|$)/;
const NOT_COLOUR = new Set([
  "center", "left", "right", "start", "end", "justify", "balance", "pretty",
  "wrap", "nowrap", "ellipsis", "clip", "top", "bottom", "middle", "baseline",
  "sub", "super", "xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl",
  "6xl", "7xl", "8xl", "9xl", "\\[11px\\]",
]);
// ============================================= 7. tiap kontrol punya press
// Statis, karena `:active` tidak bisa disimulasikan andal lewat DOM dan sebuah
// kontrol tanpa state tekan tidak terlihat salah - ia cuma terasa mati. Audit
// menghitung NOL varian `active:` di seluruh `src/` sebelum ini: 55 tombol, 25
// switch, 12 slider.
{
  // DUA PENGECUALIAN, keduanya karena press-nya ada DI TEMPAT LAIN.
  const exempt = [
    // Track range input. Thumb-nya punya `:active` di `globals.css`, dan
    // sebuah `active:` di track akan menggeser seluruh slider saat diseret.
    "range h-1 w-full",
    // Pembungkus `<label>` Toggle. Tombol switch di dalamnya yang ditekan.
    "group/toggle flex",
  ];
  const naked = [];
  for (const f of files) {
    if (f.endsWith(".css")) continue;
    const text = readFileSync(f, "utf-8");
    for (const m of text.matchAll(/className=(?:"([^"]*)"|\{`([^`]*)`\})/g)) {
      const cls = (m[1] || m[2] || "").replace(/\s+/g, " ").trim();
      if (!cls.includes("hover:") || cls.includes("active:")) continue;
      if (exempt.some((e) => cls.startsWith(e))) continue;
      naked.push(`${f}:${cls.slice(0, 48)}`);
    }
  }
  check("tiap kontrol yang punya hover juga punya state tekan",
        naked.length === 0,
        naked.length ? naked.slice(0, 4).join(" | ") : `${exempt.length} pengecualian tercatat`);
}

const unknown = new Map();
for (const f of files) {
  if (f.endsWith(".css")) continue;
  // KOMENTAR DIBUANG DULU, dan itu bukan optimasi. Versi pertama check ini
  // melaporkan `text-fg` dan `text-fg-dim` sebagai cacat yang hidup, padahal
  // yang ia baca adalah KOMENTAR di `page.tsx` yang menjelaskan bahwa keduanya
  // sudah dihapus. Sebuah pengukur yang menghitung catatan tentang cacat
  // sebagai cacat akan tetap merah selamanya setelah diperbaiki, dan harness
  // yang tidak bisa jadi hijau adalah harness yang dimatikan orang.
  const text = readFileSync(f, "utf-8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/.*/g, "$1 ");
  for (const m of text.matchAll(
    /(?:^|[\s"'`{])(?:(?:hover|focus|focus-visible|active|group-hover|group-open|enabled|disabled|placeholder|sm|md|lg|xl)[\w/-]*:)*(text|bg|border|fill|stroke|from|via|to|ring|outline|decoration|accent|caret|divide|shadow)-([a-z][a-z0-9-]*?)(?:\/\d+)?(?=[\s"'`}])/g,
  )) {
    const name = m[2];
    if (NOT_COLOUR.has(name) || BUILTIN.test(name)) continue;
    if (declared.has(name)) continue;
    // Nama utilitas yang kebetulan cocok pola tapi bukan warna.
    // `border-l-2` dan `border-t-0` menyebut SISI, bukan warna, dan regex di
    // atas menangkap `l-2` sebagai nama warna. Sama untuk lebar telanjang.
    if (/^([lrtbxyse]|p[xytblr]?|m[xytblr]?)(-\d+)?$/.test(name)) continue;
    if (/^(solid|dashed|dotted|double|none|auto|hidden|collapse|separate|opacity|width|spacing|\d+)$/.test(name)) continue;
    if (!unknown.has(name)) unknown.set(name, []);
    unknown.get(name).push(f);
  }
}
check(
  "tiap kelas warna Tailwind punya token yang dideklarasikan",
  unknown.size === 0,
  unknown.size
    ? [...unknown].map(([k, v]) => `${k} (${v[0]})`).join(" | ")
    : `${declared.size} token, ${files.length} file dipindai`,
);

// ================================================================= browser
const registry = await fetch(`${API}/api/config`)
  .then((r) => r.json())
  .then((c) => c.layers)
  .catch(() => []);
check("katalog layer terbaca", registry.length > 0, `${registry.length} layer`);

// 6. tiap layer punya glyph
const iconSrc = readFileSync("src/components/icons.tsx", "utf-8");
const mapBody = iconSrc.slice(iconSrc.indexOf("export const LAYER_ICON"));
const mapped = new Set(
  [...mapBody.slice(0, mapBody.indexOf("};")).matchAll(/^\s{2}(\w+):/gm)].map((m) => m[1]),
);
const noIcon = registry.map((l) => l.id).filter((id) => !mapped.has(id));
check("tiap layer di registry punya glyph", noIcon.length === 0,
      noIcon.length ? noIcon.join(", ") : `${mapped.size} glyph`);

const roleSrc = iconSrc.slice(iconSrc.indexOf("export const ROLE_ICON"));
const roleMapped = new Set(
  [...roleSrc.slice(0, roleSrc.indexOf("};")).matchAll(/"?([^":\n]+)"?:\s*"role_/g)]
    .map((m) => m[1].trim()),
);
const roles = [...new Set(registry.map((l) => l.role).filter(Boolean))];
const noRole = roles.filter((r) => !roleMapped.has(r));
check("tiap role punya glyph", noRole.length === 0,
      noRole.length ? noRole.join(" | ") : `${roles.length} role`);

const browser = await chromium.launch();

/** Satu theme, dibuka dengan preferensinya sudah tersimpan. */
async function open(theme) {
  const ctx = await browser.newContext({
    viewport: { width: 1600, height: 1050 },
    deviceScaleFactor: 2,
  });
  await ctx.addInitScript((t) => localStorage.setItem("zonelab.theme", t), theme);
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 160)));
  await page.goto(`${BASE}/?provider=synthetic`, {
    waitUntil: "networkidle",
    timeout: 240_000,
  });
  await page.waitForTimeout(9_000);
  return { ctx, page, errs };
}

const TOKENS = [
  "bg", "panel", "panel-2", "line", "line-strong",
  "text", "text-dim", "text-faint",
  "demand", "supply", "accent", "info",
  "chart-grid", "chart-cross", "chart-axis",
];

const seen = {};
for (const theme of ["dark", "light"]) {
  const { ctx, page, errs } = await open(theme);

  // 8. frame pertama sudah benar
  check(`${theme}: atribut theme terpasang`,
        (await page.evaluate(() => document.documentElement.dataset.theme)) === theme);
  check(`${theme}: nol pageerror`, errs.length === 0, errs.slice(0, 2).join(" | "));

  const vals = await page.evaluate((names) => {
    const cs = getComputedStyle(document.documentElement);
    const out = {};
    for (const n of names) out[n] = cs.getPropertyValue(`--${n}`).trim();
    return out;
  }, TOKENS);

  // 1. token lengkap
  const missing = TOKENS.filter((t) => !vals[t]);
  check(`${theme}: 15 token warna terdeklarasi`, missing.length === 0,
        missing.length ? missing.join(", ") : Object.values(vals).join(" "));
  if (missing.length) { await ctx.close(); continue; }

  const rgb = Object.fromEntries(TOKENS.map((t) => [t, parse(vals[t])]));
  seen[theme] = rgb;
  const bg = rgb.bg;

  // 3. floor kontras. Angkanya dari tabel di kepala globals.css.
  for (const [tok, want] of [["text", 15.8], ["text-dim", 7.85], ["text-faint", 5.29]]) {
    const got = ratio(rgb[tok], bg);
    check(`${theme}: --${tok} kontras ${got.toFixed(2)}:1`, near(got, want, 0.25),
          `target ${want}, selisih ${(got - want).toFixed(2)}`);
  }

  // 4. pasangan semantik
  const dl = Math.abs(lstar(rgb.demand) - lstar(rgb.supply));
  const grey = ratio(rgb.demand, rgb.supply);
  check(`${theme}: jarak L* pasangan ${dl.toFixed(1)}`, dl >= 15.5, "floor 15,5, dark 16,6");
  check(`${theme}: kontras greyscale pasangan ${grey.toFixed(2)}:1`, grey >= 1.7,
        "floor 1,70, dark 1,74");
  check(`${theme}: supply lebih terang dari demand`,
        lstar(rgb.supply) > lstar(rgb.demand),
        `supply L* ${lstar(rgb.supply).toFixed(1)}, demand ${lstar(rgb.demand).toFixed(1)}`);
  for (const side of ["demand", "supply"]) {
    const c = ratio(rgb[side], bg);
    check(`${theme}: --${side} ${c.toFixed(2)}:1 lawan bg`, c >= 4.5, "floor AA 4,5");
  }
  check(`${theme}: --info ${ratio(rgb.info, bg).toFixed(2)}:1`,
        ratio(rgb.info, bg) >= 4.5, "ia membawa teks banner");
  // `--info` harus jauh dari demand, atau sebuah banner status akan terbaca
  // sebagai arah. 43 derajat adalah pagar yang sama dengan `ink.ts`.
  check(`${theme}: --info ${arc(hue(rgb.info), hue(rgb.demand)).toFixed(0)} derajat dari demand`,
        arc(hue(rgb.info), hue(rgb.demand)) >= 42, "pagar 43 derajat");

  // 5. canvas ikut berganti
  const shot = await page.locator("canvas").first().screenshot();
  seen[`${theme}_canvas`] = shot;

  // 7. sensus state kontrol
  const states = await page.evaluate(() => {
    const sel = 'button,[role="switch"],summary,select,a[href],input[type="range"]';
    const all = [...document.querySelectorAll(sel)].filter((e) => e.offsetParent !== null);
    let noTransition = 0;
    for (const e of all) {
      if (getComputedStyle(e).transitionDuration === "0s"
          && getComputedStyle(e).transitionProperty === "all") noTransition += 1;
    }
    return { total: all.length, noTransition };
  });
  check(`${theme}: ${states.total} kontrol terlihat`, states.total > 80,
        `tanpa transition ${states.noTransition}`);

  // CHROME TIDAK BOLEH MEMAKAN CHART, dan ini diukur setelah dua percobaan
  // yang lebih pintar gagal.
  //
  // Yang terjadi: theme toggle masuk dengan `py-1.5` dan jadi empat piksel
  // lebih tinggi dari 14 kontrol header lain. Header naik dari 78 ke 82,
  // tinggi chart turun dari 591 ke 588, dan sebuah caption di y 688,5 setinggi
  // 12px mulai menggantung melewati edge bawah pane. `e2e/labels.mjs` jatuh ke
  // 8/9. Tidak ada yang terlihat salah di layar, dan tiga piksel bukan sesuatu
  // yang bisa dilihat mata.
  //
  // Percobaan pertama menuntut semua kontrol header SETINGGI SAMA. Ia menolak
  // keadaan yang benar: kontrol di sana memang 24 sampai 27px karena font,
  // border dan padding-nya berbeda.
  //
  // Percobaan kedua menuntut RENTANGNYA <= 4px. Ia lolos dengan cacatnya
  // disuntikkan: toggle jadi 28px dan seluruh klaster bergeser ke 25-28, jadi
  // rentangnya tetap 3. Diukur, bukan dikira.
  //
  // Yang mengikat karena itu hal yang sesungguhnya rusak: TINGGI CHART. Ia
  // diperiksa lawan tinggi viewport, jadi ambangnya tidak bergantung ukuran
  // window, dan pesannya menunjuk langsung ke chrome yang tumbuh.
  const layout = await page.evaluate(() => {
    const ws = document.querySelector("[data-workstation]");
    const main = ws?.querySelector("main");
    const head = ws?.querySelector("header");
    if (!ws || !main || !head) return null;
    const above = [...ws.children]
      .filter((e) => e !== main.parentElement && e.tagName !== "DIV")
      .reduce((n, e) => n + Math.round(e.getBoundingClientRect().height), 0);
    return {
      chart: Math.round(main.getBoundingClientRect().height),
      chrome: above,
      header: Math.round(head.getBoundingClientRect().height),
      viewport: window.innerHeight,
    };
  });
  {
    // 130px pada viewport 1000: header 78 plus dua banner 26. Ambangnya 132
    // supaya dua piksel gerakan font tidak membuatnya merah, dan cacat 4px
    // yang sudah terjadi tetap tertangkap.
    const ok = layout && layout.chrome <= 132;
    check(`${theme}: chrome di atas chart ${layout?.chrome}px`, Boolean(ok),
          `header ${layout?.header}, chart ${layout?.chart} dari viewport `
          + `${layout?.viewport}, ambang 132`);
  }

  await page.screenshot({ path: `${SHOTS}/theme-${theme}.png` });
  await ctx.close();
}

// ================================================== canvas benar benar beda
if (seen.dark_canvas && seen.light_canvas) {
  const a = seen.dark_canvas, b = seen.light_canvas;
  const same = a.length === b.length && a.equals(b);
  check("canvas benar di kedua theme saat dimuat dari awal", !same,
        same ? "bitmap IDENTIK di dua load terpisah" : `${a.length} vs ${b.length} byte`);
}

// SATU HALAMAN, SAKLARNYA DIKLIK. Perbandingan di atas memuat dua halaman
// terpisah, dan masing masing membaca theme-nya sekali sebelum chart dibuat -
// jadi ia hijau bahkan kalau SELURUH handler pergantian theme dihapus. Itu
// dibuktikan dengan menghapusnya. Yang menguji wiring-nya hanya mengklik
// saklarnya di halaman yang sudah hidup.
{
  const { ctx, page, errs } = await open("dark");
  // LUMINANCE, BUKAN BYTE. Versi pertama membandingkan panjang buffer PNG-nya
  // dan lolos dengan seluruh handler repaint dihapus: 84071 lalu 84072 byte,
  // satu byte yang datang dari harga yang bergerak dan bukan dari theme.
  // Sebuah check yang lulus karena noise adalah check yang tidak mengukur apa
  // pun. Yang diukur sekarang rata rata luminance seluruh canvas, dan ia harus
  // MELEWATI 0,5 - bukan sekadar berubah.
  const meanLum = async () =>
    await page.evaluate(() => {
      const c = [...document.querySelectorAll("canvas")]
        .sort((a, b) => b.width * b.height - a.width * a.height)[0];
      const ctx = c.getContext("2d");
      if (!ctx) return null;
      const step = 16;
      const d = ctx.getImageData(0, 0, c.width, c.height).data;
      let sum = 0, n = 0;
      for (let i = 0; i < d.length; i += 4 * step) {
        sum += (0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2]) / 255;
        n += 1;
      }
      return n ? sum / n : null;
    });
  const before = await meanLum();
  await page.getByRole("group", { name: "Theme" })
    .getByRole("button", { name: "Terang" }).click();
  await page.waitForTimeout(2_500);
  const after = await meanLum();
  const now = await page.evaluate(() => document.documentElement.dataset.theme);
  check("saklar theme benar benar berganti", now === "light", `atribut ${now}`);
  check("canvas dicat ulang saat saklar theme diklik",
        before !== null && after !== null && before < 0.35 && after > 0.6,
        `luminance rata rata ${before?.toFixed(3)} lalu ${after?.toFixed(3)}`
        + (before !== null && after !== null && after - before < 0.25
           ? " - setInkTheme atau repaint-nya putus" : ""));
  // Ribbon punya canvas sendiri di luar sistem primitive dan langganannya
  // sendiri, jadi ia bisa putus terpisah dari yang di atas.
  const ribbons = await page.locator("canvas").count();
  check("nol pageerror sesudah berganti theme hidup", errs.length === 0,
        errs.slice(0, 2).join(" | ") || `${ribbons} canvas`);

  // GLYPH LAYER DI RAIL juga membawa warna ink, dan ia punya jalur kegagalan
  // SENDIRI: tabelnya dibaca per render, tapi `Toolbox` di-memo dan prop-nya
  // tidak berubah saat theme berganti. Tanpa langganan di dalamnya panel
  // bertahan di warna lama sementara canvas di sebelahnya sudah berganti, dan
  // tidak ada error apa pun. Diukur pada `structure`, satu satunya ink family
  // yang glyph-nya tidak dua warna dan mudah ditunjuk.
  const glyphColour = async () =>
    await page.evaluate(() => {
      const row = [...document.querySelectorAll("label")]
        .find((l) => l.textContent?.trim().startsWith("Market structure"));
      const svg = row?.querySelector("svg");
      return svg ? getComputedStyle(svg).color : null;
    });
  await page.getByRole("group", { name: "Theme" })
    .getByRole("button", { name: "Gelap" }).click();
  await page.waitForTimeout(600);
  const glyphDark = await glyphColour();
  await page.getByRole("group", { name: "Theme" })
    .getByRole("button", { name: "Terang" }).click();
  await page.waitForTimeout(600);
  const glyphLight = await glyphColour();
  check("glyph layer di rail ikut berganti warna ink",
        Boolean(glyphDark) && Boolean(glyphLight) && glyphDark !== glyphLight,
        `${glyphDark} lalu ${glyphLight}`
        + (glyphDark === glyphLight
           ? " - tabel swatch beku atau Toolbox tidak berlangganan theme" : ""));
  await page.screenshot({ path: `${SHOTS}/theme-switched.png` });
  await ctx.close();
}

// ============================================== ink family dibaca dari kode
// Dari sumbernya, bukan dari halaman: kelima tabel itu konstanta modul dan
// tidak pernah muncul sebagai properti CSS di mana pun.
const inkSrc = readFileSync("src/components/ink.ts", "utf-8");
const grab = (name) => {
  const at = inkSrc.indexOf(`const ${name} = {`);
  if (at < 0) return null;
  const body = inkSrc.slice(at, inkSrc.indexOf("} as const", at));
  return Object.fromEntries(
    [...body.matchAll(/(\w+):\s*\[(\d+),\s*(\d+),\s*(\d+)\]/g)]
      .map((m) => [m[1], [+m[2], +m[3], +m[4]]]),
  );
};
const inkDark = grab("INKS");
const inkLight = grab("INKS_LIGHT");
check("dua tabel ink terbaca", Boolean(inkDark && inkLight),
      `${Object.keys(inkDark || {}).length} lawan ${Object.keys(inkLight || {}).length}`);

if (inkDark && inkLight && seen.dark && seen.light) {
  const names = Object.keys(inkDark);
  check("kedua tabel ink punya family yang sama",
        names.length === Object.keys(inkLight).length
          && names.every((n) => inkLight[n]),
        names.join(", "));

  // Hue tiap family dipertahankan antar theme. Itu yang membuat sebuah layer
  // tetap layer yang sama saat theme berganti.
  const drift = names
    .map((n) => [n, arc(hue(inkDark[n]), hue(inkLight[n]))])
    .filter(([, d]) => d > 1.5);
  check("hue tiap ink family dipertahankan antar theme", drift.length === 0,
        drift.length ? drift.map(([n, d]) => `${n} bergeser ${d.toFixed(1)}`).join(" | ")
                     : "kelima hue sama");

  // Pagar 43 derajat dari ketiga makna yang sudah terpakai, di kedua theme.
  const breaches = [];
  for (const [theme, table] of [["dark", inkDark], ["light", inkLight]]) {
    for (const n of names) {
      for (const sem of ["demand", "supply", "accent"]) {
        const d = arc(hue(table[n]), hue(seen[theme][sem]));
        if (d < 42) breaches.push(`${theme} ${n} ${d.toFixed(0)} dari ${sem}`);
      }
    }
  }
  check("tiap ink family >= 43 derajat dari demand, supply dan accent",
        breaches.length === 0, breaches.join(" | ") || "10 family-theme lolos");

  // Tangga L* harus tetap MEMISAHKAN, dan arahnya boleh terbalik: di atas
  // kertas terang yang menonjol adalah yang paling gelap.
  for (const [theme, table] of [["dark", inkDark], ["light", inkLight]]) {
    const ls = names.map((n) => lstar(table[n])).sort((a, b) => a - b);
    const gaps = ls.slice(1).map((v, i) => v - ls[i]);
    check(`${theme}: tangga L* ink terpisah minimal 4 poin`,
          Math.min(...gaps) >= 4,
          `terkecil ${Math.min(...gaps).toFixed(1)}, rentang ${ls[0].toFixed(1)} ke ${ls.at(-1).toFixed(1)}`);
    const span = ratio(
      table[names[ls.indexOf(Math.min(...ls))] ?? names[0]],
      table[names[0]],
    );
    void span;
  }
}

// ======================================== skeleton dan error state, keduanya
// KEDUANYA DIPICU, TIDAK DITUNGGU. Loading berlangsung 645 sampai 674 ms di
// mesin ini, jadi sebuah screenshot yang dikejar `waitForTimeout` akan
// menangkap keadaan yang berbeda tiap run. Request drawing-nya ditahan dan
// dipalsukan gagal, jadi kedua state itu dipegang selama yang dibutuhkan.
//
// Keduanya dijaga karena keduanya adalah hal pertama yang dilihat orang dan
// yang paling mudah membusuk tanpa ada yang tahu: tidak ada jalur normal yang
// melewatinya, jadi sebuah cacat di sini bisa hidup berbulan bulan.
for (const [label, status, want] of [
  ["skeleton", null, /MEMUAT CANDLE/i],
  ["error", 503, /Tidak ada chart untuk/i],
]) {
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on("pageerror", (e) => errs.push(String(e).slice(0, 120)));
  // Tanpa `fulfill` dan tanpa `abort`, request-nya menggantung - yang persis
  // keadaan loading yang panjang.
  await page.route("**/api/draw**", (r) => {
    if (status) r.fulfill({ status, body: "provider probe down" });
  });
  await page.goto(`${BASE}/?provider=synthetic`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(status ? 7000 : 4000);
  const body = await page.locator("main").innerText().catch(() => "");
  check(`state ${label} merender isinya`, want.test(body),
        body.replace(/\s+/g, " ").slice(0, 90) || "(kosong)");
  if (label === "skeleton") {
    // BUKAN DERET HARGA. Versi pertama skeleton ini menggambar 15 kolom
    // setinggi 38 sampai 74 persen, dan screenshot-nya terbaca sebagai bar
    // chart sungguhan. Sebuah placeholder yang bisa disalahbaca sebagai harga
    // lebih buruk daripada tidak ada placeholder, karena satu detik pertama
    // seseorang mungkin membacanya sebagai harga. Yang diperiksa: tak satu pun
    // elemen berlatar di dalamnya lebih tinggi dari sepertiga pane.
    const tall = await page.evaluate(() => {
      const main = document.querySelector("main");
      const h = main.getBoundingClientRect().height;
      // LEBARNYA IKUT DIHITUNG, dan versi pertama check ini lupa: ia
      // melaporkan 4 pelanggaran yang ternyata GRIDLINE VERTIKAL, lebar 1px
      // dan tinggi penuh. Sebuah garis 1px tidak bisa dibaca sebagai bar
      // harga. Yang bar-like harus tinggi DAN lebar.
      return [...main.querySelectorAll("div")].filter((e) => {
        const r = e.getBoundingClientRect();
        return r.height > h / 3 && r.width > 6
               && getComputedStyle(e).backgroundColor !== "rgba(0, 0, 0, 0)";
      }).length;
    });
    check("skeleton tidak bisa disalahbaca sebagai deret harga", tall === 0,
          `${tall} elemen berlatar lebih tinggi dari sepertiga pane`);
  }
  check(`state ${label} nol pageerror`, errs.length === 0, errs.slice(0, 2).join(" | "));
  await page.screenshot({ path: `${SHOTS}/state-${label}.png` });
  await ctx.close();
}

await browser.close();
console.log(`\n${failed === 0 ? "kedua theme lolos" : `${failed} GAGAL`}`);
process.exit(failed === 0 ? 0 : 1);
