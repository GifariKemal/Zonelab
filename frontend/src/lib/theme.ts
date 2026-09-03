/** Theme gelap atau terang, satu preferensi per browser.
 *
 *  POLA-NYA DISALIN DARI `lib/rails.ts`, yang sudah menyelesaikan pertanyaan
 *  yang sama di repo ini: `localStorage` tidak ada saat server render, dan
 *  menariknya masuk lewat effect adalah hydration mismatch. Menemukan pola
 *  kedua di sini akan berarti dua store yang nanti berbeda perilaku.
 *
 *  TIGA NILAI, BUKAN DUA. "auto" mengikuti OS; "dark" dan "light" adalah
 *  pilihan yang menang atas OS. Tanpa "auto" satu-satunya cara kembali ke
 *  perilaku OS adalah menghapus localStorage lewat devtools.
 *
 *  DEFAULT-NYA "dark", BUKAN "auto", dan itu keputusan yang disengaja. Kalimat
 *  yang dulu mengunci file CSS ini berbunyi bahwa chart yang membalik di tengah
 *  sesi merusak adaptasi gelap. Kalau default-nya mengikuti OS, sebuah laptop
 *  yang berpindah ke mode terang jam enam sore akan membalik chart orang tanpa
 *  diminta - persis hal yang penguncian itu cegah. Jadi OS baru didengar kalau
 *  pembacanya memilih "auto" secara sadar.
 */
const STORAGE = "zonelab.theme";

export type ThemeChoice = "auto" | "dark" | "light";
export type Resolved = "dark" | "light";

export const CHOICES: readonly [ThemeChoice, string][] = [
  ["dark", "Gelap"],
  ["light", "Terang"],
  ["auto", "Ikut OS"],
];

const listeners = new Set<() => void>();
let cache: ThemeChoice | null = null;

const notify = () => {
  for (const listener of listeners) listener();
};

function read(): ThemeChoice {
  try {
    const raw = window.localStorage.getItem(STORAGE);
    return raw === "light" || raw === "auto" || raw === "dark" ? raw : "dark";
  } catch {
    return "dark";
  }
}

/** Apa yang benar benar dipakai sekarang, sesudah "auto" diselesaikan. */
export function resolve(choice: ThemeChoice): Resolved {
  if (choice !== "auto") return choice;
  try {
    return window.matchMedia("(prefers-color-scheme: light)").matches
      ? "light"
      : "dark";
  } catch {
    return "dark";
  }
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE) {
      cache = null;
      apply();
      notify();
    }
  };
  // OS BERGANTI SAAT "auto" AKTIF harus ikut terdengar. Tanpa ini pilihan
  // "Ikut OS" hanya berlaku sampai reload berikutnya, yang membuat namanya
  // bohong.
  const mq = window.matchMedia("(prefers-color-scheme: light)");
  const onMedia = () => {
    if (themeSnapshot() === "auto") {
      apply();
      notify();
    }
  };
  window.addEventListener("storage", onStorage);
  mq.addEventListener("change", onMedia);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
    mq.removeEventListener("change", onMedia);
  };
}

export function themeSnapshot(): ThemeChoice {
  if (cache === null) cache = read();
  return cache;
}

export function themeServerSnapshot(): ThemeChoice {
  return "dark";
}

/** Tulis atributnya ke `<html>`. CSS membaca dari sana dan tidak dari mana pun
 *  lagi, jadi ini satu satunya tempat theme benar benar berlaku. */
export function apply(): void {
  document.documentElement.dataset.theme = resolve(themeSnapshot());
}

export function setTheme(next: ThemeChoice): void {
  cache = next;
  try {
    window.localStorage.setItem(STORAGE, next);
  } catch {
    // Private window melempar di sini. Gagal menyimpan preferensi bukan alasan
    // untuk gagal menerapkannya di sesi ini.
  }
  apply();
  notify();
}
