/**
 * Apakah rail benar-benar hilang, dan apakah chart benar-benar dapat lebarnya?
 *
 *   node e2e/rails.mjs <out-dir>
 *
 * Tiga perubahan UI mendarat pada 2 September 2026 - rail yang bisa
 * disembunyikan, heading family yang dipanjangkan, dan peringatan prasyarat
 * untuk layer yang menggambar nol - dan tidak satu pun dari kelima gate
 * frontend yang ada melihatnya. `wiring.mjs` menghitung objek per layer,
 * `labels.mjs` memetakan tabrakan caption, `sweep.mjs` menyapu control,
 * `pixel-truth.mjs` dan `nonbox-truth.mjs` membaca kanvas. Tidak ada yang
 * menanyakan apakah panelnya hilang saat tombolnya diklik.
 *
 * Yang diukur di sini LEBAR PANE, bukan keberadaan elemen. Fitur ini ada untuk
 * mengembalikan lebar ke tempat harga dibaca, jadi klaimnya angka: pane 750 px
 * dengan kedua rail menyala, dan lebih lebar tanpa mereka. Sebuah test yang
 * cuma memeriksa `aside` sudah tidak ada akan lulus di atas panel yang
 * disembunyikan lewat `visibility: hidden` sambil tetap memakan 232 px.
 *
 * PERSISTENSI DIUJI DENGAN RELOAD SUNGGUHAN. Preferensinya tinggal di
 * localStorage lewat `lib/rails.ts`, dan `useSyncExternalStore` dipakai justru
 * karena membacanya di sebuah effect adalah hydration mismatch yang
 * `npm run check` tolak. Satu-satunya cara memeriksa bahwa store itu bekerja
 * adalah memuat ulang halamannya.
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { chromium } from "playwright";

const OUT = process.argv[2] ?? ".playwright-shots";
const API = "http://127.0.0.1:8100";
const UI = "http://127.0.0.1:3100/";

const results = [];
const check = (n, p, d = "") =>
  results.push(`${p ? "PASS" : "FAIL"}  ${n}${d ? ` :: ${d}` : ""}`);

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ args: ["--no-proxy-server"] });
const page = await browser.newPage({
  viewport: { width: 1400, height: 800 },
  deviceScaleFactor: 1,
});

// PREFERENSI DIBERSIHKAN DI DEPAN. Run kedua di profil yang sama akan mewarisi
// pilihan run pertama, dan sebuah harness yang hasilnya bergantung pada run
// sebelumnya adalah harness yang akan berubah warna tanpa kode berubah - itu
// yang terjadi pada `labels.mjs` sebelum ia dipatok ke synthetic.
await page.goto(UI, { waitUntil: "domcontentloaded" });
await page.evaluate(() => {
  try {
    localStorage.removeItem("zonelab.rails");
  } catch {
    // Tidak tersedia berarti tidak ada yang perlu dibersihkan.
  }
});
await page.goto(UI, { waitUntil: "networkidle" });
await page.waitForTimeout(6000);

const paneWidth = () =>
  page.evaluate(() => window.__zonelabChart.chart.paneSize().width);

const leftBtn = page.getByRole("switch", { name: "Panel kiri", exact: true });
const rightBtn = page.getByRole("switch", { name: "Panel kanan", exact: true });

// ------------------------------------------------------------- 1. DEFAULT
const both = await paneWidth();
check(
  "kedua rail menyala saat pertama dibuka",
  (await leftBtn.getAttribute("aria-checked")) === "true" &&
    (await rightBtn.getAttribute("aria-checked")) === "true",
  `pane ${both}px`,
);

// --------------------------------------------------------- 2. RAIL KIRI
await leftBtn.click();
await page.waitForTimeout(2500);
const noLeft = await paneWidth();
check(
  "menyembunyikan rail kiri melebarkan pane",
  noLeft > both + 100,
  `${both}px jadi ${noLeft}px, tambah ${noLeft - both}px`,
);

// DI-UNMOUNT, BUKAN DISEMBUNYIKAN. Switch layer yang masih ada di
// accessibility tree adalah control yang tidak bisa dilihat siapa pun, dan
// `getByRole("switch")` di harness lain akan menemukannya dan mengkliknya.
const layerSwitchGone = await page
  .getByRole("switch", { name: "Supply and demand", exact: true })
  .count();
check(
  "rail kiri di-unmount, bukan cuma disembunyikan",
  layerSwitchGone === 0,
  `switch layer tersisa di accessibility tree: ${layerSwitchGone}`,
);

// -------------------------------------------------------- 3. RAIL KANAN
await rightBtn.click();
await page.waitForTimeout(2500);
const neither = await paneWidth();
check(
  "menyembunyikan rail kanan melebarkan pane lagi",
  neither > noLeft + 100,
  `${noLeft}px jadi ${neither}px, tambah ${neither - noLeft}px`,
);

// ------------------------------------------------------- 4. PERSISTENSI
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(6000);
const afterReload = await paneWidth();
check(
  "pilihan bertahan setelah reload",
  Math.abs(afterReload - neither) < 20 &&
    (await leftBtn.getAttribute("aria-checked")) === "false",
  `pane ${afterReload}px lawan ${neither}px sebelum reload`,
);

// Dinyalakan kembali, supaya pemeriksaan di bawah punya rail kiri untuk dibaca
// DAN supaya profil tidak ditinggalkan dalam keadaan yang membingungkan run
// berikutnya.
await leftBtn.click();
await rightBtn.click();
await page.waitForTimeout(3000);
const restored = await paneWidth();
check(
  "pane kembali ke lebar semula",
  Math.abs(restored - both) < 20,
  `${restored}px lawan ${both}px`,
);

// ------------------------------------------------- 5. HEADING FAMILY
// Dibandingkan dengan apa yang API LAYANI, bukan dengan string yang dieja di
// sini. Kalau `family` di server berubah, yang harus merah adalah peta nama
// panjangnya, bukan sebuah literal di harness.
const serverFamilies = await page.evaluate(async (api) => {
  const cfg = await (await fetch(`${api}/api/config`)).json();
  return [...new Set(cfg.layers.map((l) => l.family).filter(Boolean))];
}, API);
const headings = await page.evaluate(() =>
  [...document.querySelectorAll("h2, h3, [class*='uppercase']")]
    .map((n) => n.textContent?.trim() ?? "")
    .filter(Boolean),
);
const ictHeading = headings.find((h) => h.startsWith("ICT"));
check(
  "heading ICT memuat kepanjangannya",
  Boolean(ictHeading) && /inner circle trader/i.test(ictHeading ?? ""),
  `heading terbaca "${ictHeading ?? "(tidak ketemu)"}", family dari server: ` +
    serverFamilies.join(", "),
);

// ----------------------------------------- 6. PERINGATAN PRASYARAT
// `psp` menggambar nol tanpa partner SSMT, diukur 0 objek di XAUUSD 1h 900 bar.
// Layer yang menyala tanpa mengubah apa pun di kanvas tidak bisa dibedakan dari
// layer yang rusak, jadi barisnya harus mengatakan apa yang kurang.
const pspSwitch = page.getByRole("switch", {
  name: "Precision swing point",
  exact: true,
});
await pspSwitch.click();
await page.waitForTimeout(4000);
// KATA-KATA SERVER, BUKAN KATA-KATA SAYA. `app/main.py:619` yang memegang
// gate-nya DAN kalimatnya, dan rail-nya cuma me-routing. Mencari prosa yang
// dieja di harness ini akan merah setiap kali copy UI-nya disunting, dan hijau
// kalau seseorang menyalin ulang kondisinya ke TypeScript - dua-duanya jawaban
// yang salah. Yang ditanyakan: apakah alasan yang API kirim benar-benar sampai
// ke mata pembaca.
const reason = await page.evaluate(async (api) => {
  const r = await fetch(`${api}/api/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: "XAUUSD",
      interval: "1h",
      bars: 600,
      layers: ["psp"],
    }),
  });
  return (await r.json()).meta?.ssmt?.reason ?? null;
}, API);
const warned =
  Boolean(reason) &&
  (await page.evaluate((want) => document.body.innerText.includes(want), reason));
check(
  "layer yang menggambar nol menyebut prasyaratnya",
  warned,
  reason
    ? `alasan server "${reason}" ${warned ? "tampil di rail" : "TIDAK sampai ke rail"}`
    : "API tidak mengirim reason, jadi tidak ada yang bisa dirender",
);
await pspSwitch.click();
await page.waitForTimeout(2000);

// -------------------------------------------- 7. PROJECTIONS DUA SESI
// Klaimnya bukan "projections ada", melainkan bahwa DUA sesi tergambar
// sekaligus. Sampai 2 September 2026 slice `[-1:]` menyimpan satu range lintas
// seluruh sesi, jadi memilih London plus New York menggambar yang tutup paling
// akhir saja dan hasilnya terlihat benar.
const stacks = await page.evaluate(async (api) => {
  const r = await fetch(`${api}/api/draw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      symbol: "XAUUSD",
      interval: "1h",
      bars: 900,
      layers: ["projections"],
      projections: {
        sessions: ["london", "ny_am"],
        direction: 0,
        levels: [0, -0.5, -1, -1.5, 2, 2.5],
      },
    }),
  });
  const d = await r.json();
  return (d.drawing.projections ?? []).map((p) => p.label);
}, API);
const sessionsSeen = [...new Set(stacks.map((l) => l.split(" ")[0]))].sort();
check(
  "projections menggambar satu stack per sesi yang dipilih",
  sessionsSeen.length === 2 &&
    sessionsSeen.includes("london") &&
    sessionsSeen.includes("ny_am"),
  `${stacks.length} stack, sesi: ${sessionsSeen.join(", ") || "(kosong)"}`,
);

await page.screenshot({ path: `${OUT}/rails.png` });
writeFileSync(
  `${OUT}/rails.json`,
  JSON.stringify(
    {
      pane: { both, noLeft, neither, afterReload, restored },
      ict_heading: ictHeading ?? null,
      server_families: serverFamilies,
      projection_labels: stacks,
      prerequisite_warned: warned,
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
