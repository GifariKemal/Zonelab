/** Rail kiri dan kanan: terlihat atau tidak, satu preferensi per browser.
 *
 *  DIBACA LEWAT STORE, tidak disalin ke state saat mount. `localStorage` tidak
 *  ada saat server render, dan menariknya masuk dengan sebuah effect adalah
 *  hydration mismatch yang ditolak `react-hooks/set-state-in-effect` - persis
 *  lint error yang versi pertama fitur ini kena. Pola ini disalin dari
 *  `lib/presets.ts`, yang sudah menyelesaikan pertanyaan yang sama di repo ini,
 *  alih-alih menemukan pola kedua yang nanti berbeda perilaku.
 *
 *  Efek sampingnya berguna: tab kedua yang menulis kunci yang sama akan
 *  memperbarui tab ini juga, jadi dua window tidak melayang ke tata letak yang
 *  berbeda sampai salah satunya di-reload.
 */
const STORAGE = "zonelab.rails";

export type Rails = { left: boolean; right: boolean };

/** Satu referensi beku, supaya server snapshot tidak pernah terlihat berubah. */
const BOTH: Rails = Object.freeze({ left: true, right: true });

const listeners = new Set<() => void>();
let cache: Rails | null = null;

const notify = () => {
  for (const listener of listeners) listener();
};

/** Isi store, atau keduanya terlihat.
 *
 *  Store yang korup atau disunting tangan mengembalikan default, bukan
 *  melempar. Kehilangan preferensi tata letak itu gangguan; panel yang menolak
 *  render bukan.
 */
function read(): Rails {
  try {
    const raw = window.localStorage.getItem(STORAGE);
    if (!raw) return BOTH;
    const got = JSON.parse(raw) as Partial<Rails>;
    return {
      left: typeof got.left === "boolean" ? got.left : true,
      right: typeof got.right === "boolean" ? got.right : true,
    };
  } catch {
    return BOTH;
  }
}

export function subscribeRails(listener: () => void): () => void {
  listeners.add(listener);
  const onStorage = (e: StorageEvent) => {
    if (e.key === STORAGE) {
      cache = null;
      notify();
    }
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** SATU REFERENSI PER ISI, dan itu wajib bukan optimasi.
 *
 *  `useSyncExternalStore` membandingkan snapshot dengan `Object.is`, jadi
 *  mengembalikan objek baru tiap panggilan membuat React menyimpulkan store-nya
 *  berubah terus dan me-render tanpa henti. Cache-nya dibuang hanya saat ada
 *  yang menulis.
 */
export function railsSnapshot(): Rails {
  if (cache === null) cache = read();
  return cache;
}

export function railsServerSnapshot(): Rails {
  return BOTH;
}

/** Simpan, lalu beri tahu pembaca di tab ini.
 *
 *  Event `storage` hanya menyala di tab LAIN, jadi tanpa `notify()` di sini tab
 *  yang mengklik tombolnya adalah satu-satunya yang tidak melihat hasilnya.
 */
export function setRails(next: Rails): void {
  cache = next;
  try {
    window.localStorage.setItem(STORAGE, JSON.stringify(next));
  } catch {
    // Private window melempar di baris ini. Gagal menyimpan preferensi bukan
    // alasan untuk gagal menerapkannya di sesi ini.
  }
  notify();
}
