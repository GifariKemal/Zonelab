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

/** TANGGA YANG SAMA, DIBALIK ARAHNYA, untuk background terang.
 *
 *  Di atas #0b0d10 yang paling menonjol adalah yang paling TERANG, jadi tangga
 *  L* di atas naik 44,0 -> 72,0 dengan `levels` di puncaknya. Di atas #f1f3f5
 *  yang menonjol adalah yang paling GELAP, jadi tangganya harus turun atau
 *  urutan penekanannya terbalik: grid akan jadi objek paling keras di layar dan
 *  named price ray jadi yang paling samar, yaitu kebalikan dari maksudnya.
 *
 *  Yang dipertahankan persis: HUE tiap family, sampai satu desimal. Yang
 *  dicerminkan: L*-nya, lewat 100 - L* - 8. Hasilnya diukur, bukan dinilai:
 *
 *    family      dark L*  light L*   dark kontras  light kontras   hue
 *    grid           44,0      48,0          3,49:1         4,33:1  212,7
 *    dfr            54,0      38,0          5,00:1         6,26:1  232,0
 *    structure      59,9      32,1          6,12:1         7,78:1  267,6
 *    ssmt           65,9      26,1          7,45:1         9,66:1  321,9
 *    levels         72,0      20,0          9,02:1        11,82:1  200,6
 *
 *  Rentang greyscale paling redup lawan paling tajam 2,73:1 di terang lawan
 *  2,59:1 di gelap, dan tak satu pun dari lima hue jatuh dalam 43 derajat dari
 *  demand, supply atau accent di kedua theme. `e2e/theme.mjs` menghitung ulang
 *  keduanya dari browser.
 */
const INKS_LIGHT = {
  grid: [90, 116, 147],
  dfr: [78, 86, 138],
  structure: [91, 61, 126],
  ssmt: [96, 43, 77],
  levels: [26, 51, 64],
} as const;

export type InkName = keyof typeof INKS;

/** THEME AKTIF, DIPEGANG MODUL INI, dan siapa yang menuliskannya penting.
 *
 *  Canvas tidak bisa membaca kelas CSS, jadi ia tidak ikut berganti sendiri
 *  saat atribut `data-theme` berubah. `chart.tsx` yang berlangganan pergantian
 *  theme lalu memanggil `setInkTheme` DAN memaksa repaint, karena keduanya
 *  harus terjadi bersama: mengubah palette tanpa repaint hanya mengecat ulang
 *  objek berikutnya yang kebetulan digambar, jadi setengah chart tertinggal di
 *  theme lama sampai ada yang menggeser sumbu waktu.
 *
 *  Dibaca dari variabel modul, bukan dari `document` tiap panggilan. `ink()`
 *  dipanggil beberapa ratus kali per frame saat pan, dan satu pembacaan DOM per
 *  panggilan adalah biaya yang tidak perlu dibayar untuk nilai yang berubah
 *  paling sering sekali per sesi.
 *
 *  Kalau wiring itu putus, warnanya BASI dan bukan salah - yaitu kelas cacat
 *  yang paling sulit dilihat. `e2e/theme.mjs` mengganti theme lalu membaca
 *  bitmap canvas-nya kembali dan gagal kalau pikselnya tidak ikut berubah.
 */
let active: "dark" | "light" = "dark";

export function setInkTheme(next: "dark" | "light"): void {
  active = next;
}

/** `rgba(...)` for a family at one alpha. A function rather than a table of
 *  pre-built strings, because the alphas are per-shape and there are dozens. */
export function ink(name: InkName, alpha: number): string {
  const [r, g, b] = active === "light" ? INKS_LIGHT[name] : INKS[name];
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** PELAT DI BAWAH LABEL, satu definisi untuk lima belas tempat yang memakainya.
 *
 *  Sampai sekarang tiap primitive menulis `rgba(11, 13, 16, a)` sendiri, yaitu
 *  `--bg` dieja ulang dalam desimal, di 15 baris tersebar di 13 file. Di theme
 *  terang setiap satu dari lima belas itu akan mengecat pelat HITAM di bawah
 *  teks gelap, dan labelnya hilang. Satu fungsi, jadi ada satu tempat yang
 *  harus benar.
 */
const PLATE = { dark: "11, 13, 16", light: "241, 243, 245" } as const;

export function plateInk(alpha: number): string {
  return `rgba(${PLATE[active]}, ${alpha})`;
}

/** Pasangan semantik untuk canvas, dari tabel yang sama dengan CSS.
 *
 *  `globals.css` memperingatkan bahwa LIMA TEMPAT memegang pasangan ini dan
 *  harus bergerak bersama. Ini yang keenam kalau ditulis sebagai literal lagi,
 *  jadi ia tidak ditulis sebagai literal: `zone-primitive.ts` dan `chart.tsx`
 *  memanggil ke sini, dan lima tempat itu turun jadi tiga.
 */
const SIDE = {
  dark: { demand: [31, 143, 95], supply: [239, 143, 134] },
  light: { demand: [21, 80, 55], supply: [186, 73, 62] },
} as const;

export function sideRgba(side: "demand" | "supply", alpha: number): string {
  const [r, g, b] = SIDE[active][side];
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/** Nilai token CSS apa adanya, untuk yang bukan canvas.
 *
 *  `chart.tsx` mengonfigurasi lightweight-charts dengan string warna biasa dan
 *  bukan lewat canvas kita, jadi ia bisa membaca token yang sesungguhnya alih
 *  alih menyalin heksanya. Enam belas heks literal di file itu turun jadi nol.
 */
export function token(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  const got = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return got || fallback;
}

/** Family mono yang benar benar terpasang, untuk canvas yang di luar sistem
 *  primitive.
 *
 *  `next/font` memancarkan nama family-nya ke `--font-plex-mono` di `<html>`,
 *  dan sebuah canvas tidak bisa memakai kelas CSS jadi ia harus membacanya.
 *  `cycle-ribbon.tsx` selama ini menulis `9px ui-monospace, monospace` dan
 *  karena itu satu satunya teks di app yang digambar dengan font berbeda dari
 *  setiap angka lain di layar.
 */
export function monoStack(): string {
  return token("--font-plex-mono", "ui-monospace") + ", ui-monospace, monospace";
}

/** SATU deklarasi font untuk seluruh canvas, dan alasannya sebuah sensus.
 *
 *  Sebelum ini ada 16 `ctx.font` di 15 file, dalam EMPAT bentuk berbeda:
 *
 *    11 situs  `${round(9 * ky)}px ui-monospace, monospace`
 *     2 situs  `${round(10 * ky)}px ui-monospace, monospace`
 *     2 situs  `500 ${...}px "IBM Plex Mono", ui-monospace, monospace`
 *     1 situs  `9px ${monoStack()}`
 *
 *  Jadi 13 dari 16 teks di canvas TIDAK PERNAH sampai ke IBM Plex Mono, dan 3
 *  sampai. Caption zona dan label struktur digambar dengan Plex; caption gap,
 *  pool, divergence, DFR, quarter dan sisanya digambar dengan monospace bawaan
 *  sistem, yang di Windows Consolas. Dua font di satu canvas, di objek yang
 *  bersebelahan.
 *
 *  `weight` ada karena dua situs itu memang memakai 500 dan itu disengaja: label
 *  struktur dan caption zona adalah teks yang paling sering dibaca di chart.
 *  Yang dihapus bukan pilihannya, melainkan empat cara menuliskannya.
 */
export function monoFont(px: number, ratio: number, weight = 400): string {
  return `${weight} ${Math.round(px * ratio)}px ${monoStack()}`;
}

/** Empat peran quarter, satu tabel per theme.
 *
 *  `cycle-ribbon.tsx` memegang palette-nya sendiri dan itu palette keenam di
 *  app ini. Ia pindah ke sini bukan demi kerapian: keempat warna itu dipilih
 *  untuk background gelap dan ketiganya di atas L* 60, jadi di atas kertas
 *  terang ribbon-nya akan hilang sama sekali. Versi terangnya dicerminkan
 *  dengan cara yang sama dengan `INKS_LIGHT`, hue dipertahankan dan L*
 *  dibalik.
 */
const ROLE_INK = {
  dark: {
    Q1: "168, 162, 148", Q2: "192, 138, 130",
    Q3: "156, 184, 156", Q4: "134, 152, 176",
  },
  light: {
    Q1: "92, 85, 68", Q2: "120, 62, 54",
    Q3: "62, 96, 62", Q4: "58, 78, 106",
  },
} as const;

export function roleInk(quarter: string): string {
  const table = ROLE_INK[active];
  return (table as Record<string, string>)[quarter] ?? table.Q1;
}

/** Token warna sebagai `rgba(...)` dengan alpha sendiri, untuk canvas.
 *
 *  Sebuah canvas butuh alpha per stroke dan token CSS-nya heks tanpa alpha,
 *  jadi tiga tempat di `cycle-ribbon.tsx` mengeja `--text-faint`, `--text` dan
 *  `--accent` dalam desimal. Ketiganya diam saat theme berganti. Fungsi ini
 *  membaca token yang sebenarnya lalu memasang alpha-nya.
 */
export function tokenRgba(name: string, alpha: number, fallback: string): string {
  const hex = token(name, fallback).replace("#", "");
  if (hex.length !== 6) return fallback;
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(hex.slice(i, i + 2), 16));
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
