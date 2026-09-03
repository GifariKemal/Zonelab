"use client";

import { useSyncExternalStore } from "react";

import {
  CHOICES,
  setTheme,
  subscribeTheme,
  themeServerSnapshot,
  themeSnapshot,
  type ThemeChoice,
} from "@/lib/theme";
import { Icon } from "./icons";

const GLYPH: Record<ThemeChoice, "moon" | "sun" | "auto"> = {
  dark: "moon",
  light: "sun",
  auto: "auto",
};

/** Tiga state, bukan saklar dua posisi.
 *
 *  Saklar sun/moon adalah pola default yang tidak bisa menyatakan "ikut OS", dan
 *  tanpa state ketiga itu satu satunya jalan kembali ke perilaku OS adalah
 *  menghapus localStorage lewat devtools. Tiga tombol juga membuat pilihan yang
 *  sedang aktif terbaca tanpa harus menebak arti ikonnya.
 *
 *  Bentuknya menyalin `Segmented` di toolbox alih alih menemukan kontrol baru:
 *  keduanya menjawab pertanyaan yang sama, satu dari beberapa, dan pola kedua
 *  di header akan jadi pola kedua yang nanti berbeda perilaku.
 */
export function ThemeToggle() {
  const choice = useSyncExternalStore(
    subscribeTheme,
    themeSnapshot,
    themeServerSnapshot,
  );
  return (
    <div
      role="group"
      aria-label="Theme"
      className="flex border border-line-strong"
    >
      {CHOICES.map(([id, text]) => (
        <button
          key={id}
          type="button"
          onClick={() => setTheme(id)}
          aria-pressed={choice === id}
          title={`Theme: ${text}`}
          // `py-1`, BUKAN `py-1.5`, dan selisihnya bisa diukur. Semua kontrol lain
          // di header ini tinggi 26px; 1.5 membuat yang ini 30px, dan empat
          // piksel itu menaikkan tinggi header dari 78 ke 82 lalu memotong
          // tinggi chart dari 591 ke 588. `e2e/labels.mjs` menangkapnya: sebuah
          // caption di y 688,5 setinggi 12px mulai menggantung melewati edge
          // bawah pane, 8/9 lawan 9/9.
          className={`flex items-center px-2 py-1 text-[11px] transition-colors duration-[70ms] active:translate-y-px ${
            choice === id
              ? "bg-accent/15 text-accent"
              : "text-text-faint hover:bg-line/60 hover:text-text-dim"
          }`}
        >
          {/* ICON SAJA, dan labelnya tetap ada untuk screen reader. Tiga label
              terbaca memakan sekitar 200px header yang sudah menampung 14
              kontrol lain, dan header itu sudah membungkus ke baris kedua di
              1600px. Yang aktif dibedakan warna dan background, bukan teks. */}
          <Icon name={GLYPH[id]} className="size-4" />
          <span className="sr-only">{text}</span>
        </button>
      ))}
    </div>
  );
}
