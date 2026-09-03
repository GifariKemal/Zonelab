import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import "./globals.css";

// Plex is drawn for engineering documentation: narrow, unfussy, and its mono
// has genuinely distinct 0/O and 1/l - which matters when the glyphs are prices.
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Zonelab",
  description: "Automatic technical drawing engine for chart analysis",
};

/** Theme dipasang SEBELUM paint pertama, dan itu sebabnya ia sebuah string.
 *
 *  Kalau `data-theme` baru ditulis oleh effect React, halaman sudah dicat sekali
 *  dengan default gelap dan pembaca yang memilih terang melihat kedipan hitam
 *  penuh layar di setiap navigasi. Skrip di `<head>` berjalan sebelum body ada,
 *  jadi tidak ada frame yang salah.
 *
 *  Dibungkus try supaya localStorage yang dilarang di private window tidak
 *  menjatuhkan seluruh dokumen: gagal membaca preferensi berarti default, bukan
 *  halaman kosong.
 *
 *  Nilainya harus cocok dengan `lib/theme.ts`. Dua tempat, dan itu disengaja:
 *  yang satu harus berjalan tanpa modul, yang satu tidak bisa jadi string.
 *  `tests`-nya ada di `e2e/theme.mjs`, yang memuat halaman dengan preferensi
 *  tersimpan dan gagal kalau frame pertamanya salah theme. */
const PREPAINT = `try{
var c=localStorage.getItem("zonelab.theme");
if(c!=="light"&&c!=="dark"&&c!=="auto")c="dark";
document.documentElement.dataset.theme=c==="auto"
  ?(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"):c;
}catch(e){document.documentElement.dataset.theme="dark"}`;

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${plexSans.variable} ${plexMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: PREPAINT }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
