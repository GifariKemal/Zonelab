/** Posisi yang mendarat PAS di grid device pixel.
 *
 *  ===========================================================================
 *  KENAPA INI ADA, DAN ANGKANYA
 *  ===========================================================================
 *
 *  Sampai 3 September 2026 setiap garis tipis di canvas ini digambar dengan
 *  pola `Math.round(v * k) + 0.5` dan lebar `Math.max(1, Math.round(k))`. Pada
 *  `k = 1` itu BENAR: stroke lebar 1 yang dipusatkan di setengah pixel menutupi
 *  tepat satu baris. Pada `k = 2` ia SALAH, dan salahnya tidak kelihatan di
 *  mesin pengembang mana pun yang layarnya 1x: stroke lebar 2 yang dipusatkan
 *  di setengah pixel menutupi separuh baris atas, seluruh baris tengah, dan
 *  separuh baris bawah. Tiga baris, tepi pada alpha 0,5.
 *
 *  Diukur di canvas chart yang sungguhan, dengan menghitung profil alpha tiap
 *  garis tipis di 14 kolom:
 *
 *      skala 1    133 garis pas,   0 lunak
 *      skala 2     87 garis pas, 119 lunak (58 persen), alpha tepi median 0,50
 *
 *  Alpha tepi tepat 0,50 adalah tanda buku teks stroke yang mengangkangi batas
 *  device pixel. `e2e/retina.mjs` menghitung ulang kedua baris itu.
 *
 *  ===========================================================================
 *  DAN PENGUKURANNYA SENDIRI SEMPAT SALAH, yang bagian pentingnya
 *  ===========================================================================
 *
 *  Usaha pertama memakai `deviceScaleFactor` per-context milik Playwright. Ia
 *  melaporkan `window.devicePixelRatio === 2` ke JS, jadi terlihat benar, tapi
 *  ia TIDAK memberi fancy-canvas sebuah device-pixel content box - dan itu yang
 *  fancy-canvas baca. Hasilnya bitmap canvas tetap 1x pada DPR 2 dan 3, jadi
 *  `scope.horizontalPixelRatio` selalu 1 dan tidak ada apa pun yang bisa
 *  diukur. Sensus bitmap membuktikannya: ratio 1,00 di deviceScaleFactor 1, 2
 *  DAN 3, termasuk di halaman minimal tanpa satu baris kode Zonelab.
 *
 *  Yang bekerja `--force-device-scale-factor=2` sebagai ARGUMEN BROWSER. Di
 *  sana ratio bitmap-nya 2,00 dan library-nya menskalakan benar. Sebuah laporan
 *  "retina sudah benar" pernah ditulis di atas pengukuran yang tidak bisa
 *  menunjukkan sebaliknya.
 *
 *  ===========================================================================
 *  KEDUANYA DISALIN DARI DOKUMENTASI, BUKAN DIIMPOR
 *  ===========================================================================
 *
 *  Docs plugin lightweight-charts menyebut `positionsLine` dan `positionsBox`
 *  sebagai helper yang wajib dipakai supaya posisi integer-nya konsisten dengan
 *  rendering logic internal library. Keduanya TIDAK diekspor package-nya:
 *  `grep -r positionsLine node_modules/lightweight-charts/` mengembalikan nol
 *  di 5.2.1. Jadi keduanya ditulis ulang di sini dengan semantik yang
 *  didokumentasikan, dan `demo()` di bawah mengunci aritmetikanya.
 */

export interface BitmapPositionLength {
  /** Awal, dalam device pixel. */
  position: number;
  /** Panjang, dalam device pixel. */
  length: number;
}

/** Sebuah garis yang TERPUSAT di satu koordinat, dengan lebar tertentu.
 *
 *  Dipakai untuk `fillRect`, bukan untuk `stroke`: `fillRect` mengambil tepi
 *  dan panjang, jadi tidak ada pertanyaan pemusatan sama sekali. Itu sebabnya
 *  docs-nya memakai pola ini alih-alih `moveTo`/`lineTo`.
 *
 *  `widthIsBitmap` untuk lebar yang sudah dalam device pixel, misalnya sebuah
 *  garis yang harus tetap satu device pixel apa pun skalanya.
 */
export function positionsLine(
  positionMedia: number,
  pixelRatio: number,
  desiredWidthMedia = 1,
  widthIsBitmap = false,
): BitmapPositionLength {
  const scaledPosition = Math.round(pixelRatio * positionMedia);
  const lineBitmapWidth = widthIsBitmap
    ? desiredWidthMedia
    : Math.round(desiredWidthMedia * pixelRatio);
  const offset = Math.floor(lineBitmapWidth * 0.5);
  return { position: scaledPosition - offset, length: lineBitmapWidth };
}

/** Sebuah shape ANTARA dua koordinat: box zona, band gap, body candle.
 *
 *  Kedua tepinya dibulatkan LALU diselisihkan, dan urutan itu yang penting.
 *  Pola lama di repo ini membulatkan awalnya dan LEBARNYA secara terpisah -
 *  `round(a * k)` dan `round((b - a) * k)` - jadi tepi kanannya bisa jatuh satu
 *  device pixel dari tempat shape sebelahnya membulatkan tepi yang sama, dan
 *  dua box yang berbagi edge meninggalkan celah atau bertumpuk.
 */
export function positionsBox(
  position1Media: number,
  position2Media: number,
  pixelRatio: number,
): BitmapPositionLength {
  const scaled1 = Math.round(pixelRatio * position1Media);
  const scaled2 = Math.round(pixelRatio * position2Media);
  return {
    position: Math.min(scaled1, scaled2),
    length: Math.abs(scaled2 - scaled1) + 1,
  };
}

/** Koordinat pusat untuk `moveTo`/`lineTo`, untuk garis yang HARUS di-stroke.
 *
 *  Garis putus putus tidak bisa dibuat dengan `fillRect` karena `setLineDash`
 *  hanya berlaku pada path, dan repo ini memakai pola dash sebagai encoding
 *  identitas detector. Jadi untuk garis itu stroke tetap, dan yang harus benar
 *  PUSATNYA: lebar genap harus dipusatkan di integer, lebar ganjil di setengah
 *  integer. Keduanya diturunkan dari `positionsLine` dan bukan dihitung ulang,
 *  supaya tidak ada aritmetika kedua yang bisa melenceng.
 *
 *  Nilai kembaliannya juga membawa `width`, karena pemanggil harus memakai
 *  lebar YANG SAMA dengan yang dipakai menghitung pusatnya. Memisahkan keduanya
 *  adalah cara cacat ini kembali.
 */
export function strokeLine(
  positionMedia: number,
  pixelRatio: number,
  desiredWidthMedia = 1,
): { centre: number; width: number } {
  const { position, length } = positionsLine(
    positionMedia,
    pixelRatio,
    desiredWidthMedia,
  );
  return { centre: position + length / 2, width: length };
}

/** Aritmetikanya dikunci di sini, karena seluruh ketajaman canvas bergantung
 *  padanya dan tidak ada test frontend di repo ini.
 *
 *  DIJALANKAN SEKALI SAAT MODUL DIMUAT, lihat bagian bawah file. Sebuah
 *  fungsi verifikasi yang tidak dipanggil siapa pun adalah dokumentasi, dan
 *  dokumentasi tidak gagal saat seseorang menyederhanakan `positionsLine`.
 */
export function demo(): string {
  const eq = (got: unknown, want: unknown, what: string) => {
    const a = JSON.stringify(got);
    const b = JSON.stringify(want);
    if (a !== b) throw new Error(`${what}: ${a} bukan ${b}`);
  };

  // Skala 1, garis 1px: satu baris, dan pusatnya di setengah pixel. Itu pola
  // lama, dan pada skala 1 pola lama memang benar.
  eq(positionsLine(100, 1, 1), { position: 100, length: 1 }, "1x lebar 1");
  eq(strokeLine(100, 1, 1), { centre: 100.5, width: 1 }, "1x pusat");

  // Skala 2, garis 1px: DUA baris, dan pusatnya di INTEGER. Pola lama memakai
  // 200,5 di sini, yang menyebar ke tiga baris dengan tepi 0,5 - cacat yang
  // seluruh file ini ada untuk memperbaikinya.
  eq(positionsLine(100, 2, 1), { position: 199, length: 2 }, "2x lebar 1");
  eq(strokeLine(100, 2, 1), { centre: 200, width: 2 }, "2x pusat");

  // Skala 2, garis 1,5px: tiga baris, pusat di setengah pixel. Jadi rule 1,5px
  // yang memang dipakai project ini SAH menempati tiga baris, dan itu sebabnya
  // panjang run saja tidak bisa memutuskan mana yang kabur.
  eq(positionsLine(100, 2, 1.5), { position: 199, length: 3 }, "2x lebar 1,5");
  eq(strokeLine(100, 2, 1.5), { centre: 200.5, width: 3 }, "2x pusat 1,5");

  // Skala 3, garis 1px: tiga baris, pusat di setengah pixel.
  eq(positionsLine(100, 3, 1), { position: 299, length: 3 }, "3x lebar 1");

  // Lebar yang sudah dalam device pixel tidak diskalakan lagi.
  eq(positionsLine(100, 2, 1, true), { position: 200, length: 1 }, "bitmap width");

  // Box: kedua tepi dibulatkan LALU diselisihkan. Pola lama membulatkan awal
  // dan lebar terpisah, jadi dua box yang berbagi edge bisa berselisih satu
  // device pixel di tempat yang sama.
  eq(positionsBox(10.4, 20.6, 1), { position: 10, length: 12 }, "box 1x");
  eq(positionsBox(10.4, 20.6, 2), { position: 21, length: 21 }, "box 2x");
  // Urutan argumen tidak boleh mengubah hasilnya.
  eq(positionsBox(20.6, 10.4, 2), { position: 21, length: 21 }, "box terbalik");
  // Dua box bersebelahan berbagi tepi yang PERSIS sama.
  const a = positionsBox(10, 20, 2);
  const b = positionsBox(20, 30, 2);
  eq(a.position + a.length - 1, b.position, "tepi bersama");

  return "pixel.ts demo OK";
}

// ==========================================================================
// DIJALANKAN SEKALI, DAN HASILNYA TERLIHAT DI DUA TEMPAT.
//
// `console.error` supaya `e2e/sweep.mjs`, yang menuntut nol console error di
// seluruh sapuannya, ikut merah kalau aritmetika di atas rusak. Dan
// `window.__pixelDemo` supaya `e2e/retina.mjs` bisa menegaskannya langsung.
//
// TIDAK melempar: aritmetika yang salah membuat garis kabur, bukan membuat
// chart tidak bisa digambar, dan menjatuhkan seluruh halaman untuk itu akan
// menukar cacat kecil dengan cacat besar.
// ==========================================================================
if (typeof window !== "undefined") {
  (window as unknown as { __pixelDemo?: () => string }).__pixelDemo = () => {
    try {
      return demo();
    } catch (e) {
      return `GAGAL: ${e instanceof Error ? e.message : String(e)}`;
    }
  };
  try {
    demo();
  } catch (e) {
    console.error(
      "pixel.ts self-check gagal, garis canvas tidak akan mendarat di grid:",
      e,
    );
  }
}
