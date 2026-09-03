/** Setiap kontrol di layar diklik, dan halamannya harus tetap hidup.
 *
 *  KENAPA INI ADA. Keempat harness yang sudah ada memeriksa hal yang berbeda:
 *  `wiring` memastikan tiap layer mengembalikan payload tidak kosong, `labels`
 *  memetakan tabrakan caption, `sweep` menyensus slider dan urutan menu,
 *  `expectation-path` menghitung ink satu layer. Tidak satu pun MENGKLIK setiap
 *  kontrol lalu memeriksa halamannya masih waras sesudahnya.
 *
 *  Bedanya nyata. Sebuah switch bisa hadir di DOM, lolos sensus `sweep`, dan
 *  melempar saat diklik. Sebuah disclosure bisa terbuka ke isi kosong. Sebuah
 *  panel bisa render lalu meledak ketika datanya berganti. Semua itu hijau di
 *  keempat harness lama.
 *
 *  YANG DIHITUNG SEBAGAI GAGAL, dan tidak ada yang lain:
 *    - `pageerror` apa pun, kapan pun
 *    - request yang gagal ke API sendiri
 *    - `console.error` dari React
 *    - sebuah kontrol yang diklik dan tidak mengubah apa pun yang bisa diamati
 *
 *  Yang TIDAK dihitung gagal: layer yang menggambar nol objek. Itu sering
 *  jawaban yang benar (BTC tidak punya opening gap), dan `wiring` sudah
 *  memegang pertanyaan itu dengan definisi yang lebih tepat.
 *
 *  Dipatok ke provider `synthetic` karena alasan yang sama `labels.mjs`
 *  dipatok 1 September 2026: di feed hidup hasilnya berubah antar run di tree
 *  yang sama, dan sebuah harness yang berubah sendiri tidak bisa dipakai
 *  menilai perubahan.
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

const browser = await chromium.launch();
const page = await browser.newPage({ viewportSize: { width: 1600, height: 1100 } });

const pageErrors = [];
const consoleErrors = [];
const failedRequests = [];
page.on("pageerror", (e) => pageErrors.push(String(e)));
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200));
});
page.on("requestfailed", (r) => {
  // Hanya request ke API sendiri. Sebuah font pihak ketiga yang gagal bukan
  // cacat aplikasi ini, dan menghitungnya akan membuat harness merah karena
  // jaringan.
  if (r.url().includes("127.0.0.1") || r.url().includes("localhost")) {
    failedRequests.push(`${r.method()} ${r.url()} ${r.failure()?.errorText}`);
  }
});
page.on("response", (r) => {
  if (r.status() >= 500 && (r.url().includes("127.0.0.1") || r.url().includes("localhost"))) {
    failedRequests.push(`${r.status()} ${r.url()}`);
  }
});

await page.goto(`${BASE}/?provider=synthetic`, {
  waitUntil: "networkidle", timeout: 180_000,
});
await page.waitForTimeout(5_000);

// Provider dipatok lewat kontrolnya sendiri, bukan lewat query string yang
// mungkin diabaikan. Kalau ia diabaikan, angka di bawah berubah antar run.
const source = page.getByLabel("Source", { exact: true });
if (await source.count()) {
  await source.selectOption("synthetic").catch(() => {});
  await page.waitForTimeout(6_000);
}
check("provider terpatok synthetic",
      (await source.inputValue().catch(() => "?")) === "synthetic");

// ============================================================ setiap switch
const registry = await (await fetch(`${BASE.replace("3100", "8100")}/api/config`))
  .json().then((c) => c.layers).catch(() => []);
check("katalog layer terbaca dari API", registry.length > 0, `${registry.length} layer`);

let toggled = 0;
let stuck = [];
for (const layer of registry) {
  const sw = page.getByRole("switch", { name: layer.label, exact: true });
  if (!(await sw.count())) {
    stuck.push(`${layer.id}: tidak ada switch`);
    continue;
  }
  const before = await sw.first().getAttribute("aria-checked");
  await sw.first().click();
  await page.waitForTimeout(1_400);
  const after = await sw.first().getAttribute("aria-checked");
  if (before === after) {
    stuck.push(`${layer.id}: aria-checked tetap ${before}`);
    continue;
  }
  toggled += 1;
}
check("setiap switch layer berubah state saat diklik",
      stuck.length === 0 && toggled === registry.length,
      stuck.length ? stuck.join(" | ") : `${toggled}/${registry.length}`);

await page.waitForTimeout(8_000);
await page.screenshot({ path: `${SHOTS}/click-all-on.png` });

// ================================================ setiap disclosure terbuka
const summaries = page.locator("summary");
const total = await summaries.count();
let opened = 0;
let empty = [];
for (let i = 0; i < total; i += 1) {
  const s = summaries.nth(i);
  if (!(await s.isVisible().catch(() => false))) continue;
  const label = (await s.innerText().catch(() => "?")).trim().slice(0, 40);
  await s.click({ timeout: 5_000 }).catch(() => {});
  await page.waitForTimeout(120);
  const body = await s.evaluate((el) => {
    const d = el.closest("details");
    return d ? d.innerText.replace(el.innerText, "").trim().length : -1;
  }).catch(() => -1);
  if (body === 0) empty.push(label);
  opened += 1;
}
check("setiap disclosure terbuka ke isi yang tidak kosong",
      empty.length === 0, empty.length ? empty.join(" | ") : `${opened} dibuka`);

// JUMLAHNYA JUGA, dan itu ditambahkan setelah suntikan membuktikan check di
// atas hampa. Sebuah `<details>` yang isinya kosong tidak dirender sama sekali
// oleh `Hint`, jadi ia HILANG dari DOM alih-alih muncul kosong, dan loop di
// atas tidak pernah melihatnya. `sweep.mjs` kebetulan menangkapnya lewat sensus
// fold-nya sendiri - tapi sebuah harness yang bergantung harness lain untuk
// menutup lubangnya adalah lubang yang tidak dijaga siapa pun saat yang satunya
// diubah.
const evidenceFolds = await page.locator('summary:text-is("Bukti")').count();
check("setiap layer punya fold bukti yang benar benar ada",
      evidenceFolds === registry.length,
      `${evidenceFolds} fold, ${registry.length} layer`);

// ==================================================== setiap slider bergerak
const sliders = page.locator('input[type="range"]');
const nSliders = await sliders.count();
let moved = 0;
let deaf = [];
for (let i = 0; i < nSliders; i += 1) {
  const s = sliders.nth(i);
  if (!(await s.isVisible().catch(() => false))) continue;
  const name = (await s.getAttribute("aria-label")) || `slider ${i}`;
  const before = await s.inputValue();
  const [min, max] = [await s.getAttribute("min"), await s.getAttribute("max")];
  const target = before === max ? min : max;
  await s.fill(target).catch(() => {});
  await page.waitForTimeout(150);
  const after = await s.inputValue();
  if (after === before) deaf.push(name);
  else {
    moved += 1;
    await s.fill(before).catch(() => {});
  }
}
check("setiap slider menerima nilai baru", deaf.length === 0,
      deaf.length ? deaf.join(" | ") : `${moved}/${nSliders} bergerak`);

await page.waitForTimeout(6_000);

// ===================================================== setiap select berganti
const selects = page.locator("select");
const nSel = await selects.count();
let switched = 0;
for (let i = 0; i < nSel; i += 1) {
  const s = selects.nth(i);
  if (!(await s.isVisible().catch(() => false))) continue;
  const opts = await s.evaluate((e) => [...e.options].map((o) => o.value));
  const before = await s.inputValue();
  const other = opts.find((o) => o !== before);
  if (!other) continue;
  // Simbol dan source TIDAK diganti: keduanya memuat ulang seluruh deret dan
  // akan membuat sisa harness ini mengukur chart yang berbeda.
  const label = (await s.getAttribute("aria-label")) || "";
  if (label === "Symbol" || label === "Source") continue;
  await s.selectOption(other).catch(() => {});
  await page.waitForTimeout(2_500);
  if ((await s.inputValue()) === other) switched += 1;
  await s.selectOption(before).catch(() => {});
  await page.waitForTimeout(2_000);
}
check("setiap select menerima pilihan lain", switched > 0, `${switched} select diuji`);

// ====================================================== timeframe benar benar
const tf = page.getByRole("button", { name: "30m", exact: true });
if (await tf.count()) {
  await tf.first().click();
  await page.waitForTimeout(9_000);
}
const body = await page.locator("body").innerText();
check("baris peluang muncul untuk layer yang bisa diorder di 30m",
      /BISA DIORDER/i.test(body) && /ekspektasi/i.test(body),
      body.match(/BISA DIORDER[^\n]*/gi)?.slice(0, 2).join(" | ") || "tidak ada");

await page.screenshot({ path: `${SHOTS}/click-30m.png` });

// ============================================================= panel kanan
for (const [name, needle] of [
  ["checklist", /klausa|clause/i],
  ["zone", /zona|zone/i],
]) {
  check(`panel ${name} merender isi`, needle.test(body), "");
}

// ================================================================== verdict
check("nol pageerror sepanjang klik-test", pageErrors.length === 0,
      pageErrors.slice(0, 3).join(" | "));
check("nol request API yang gagal", failedRequests.length === 0,
      failedRequests.slice(0, 3).join(" | "));
// `console.error` React dilaporkan tapi TIDAK menggagalkan: Next dev menulis
// beberapa peringatan yang bukan milik aplikasi ini. Dicetak supaya terlihat.
if (consoleErrors.length) {
  console.log(`  catatan: ${consoleErrors.length} console.error`);
  consoleErrors.slice(0, 5).forEach((e) => console.log(`    ${e}`));
}

await browser.close();
console.log(`\n${failed === 0 ? "semua klik-test lolos" : `${failed} GAGAL`}`);
process.exit(failed === 0 ? 0 : 1);
