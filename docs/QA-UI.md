# QA UI, audit dan hasilnya

Ditulis 3 September 2026. Isinya apa yang diukur, angkanya, dan suntikan yang
membuktikan tiap gate baru tidak hampa.

> [!IMPORTANT]
> Semua angka di file ini berasal dari command yang benar benar dijalankan.
> Yang belum diukur ditulis belum diukur.

## Ringkasan

| Yang diminta | Status | Angkanya |
|---|---|---|
| Light mode | Terpasang, default tetap dark | 47 check di `e2e/theme.mjs` hijau |
| Icon interaktif | 40 glyph, digambar tangan | 1 SVG jadi 73 SVG di halaman |
| Interaction state | Hover, press, focus di tiap kontrol | 0 varian `active:` jadi 22 |
| Warna di chrome | Glyph layer memakai ink yang layer itu cat | 0 warna baru, 5 ink family yang sudah ada |
| Retina | Sudah benar sebelum audit | 14 dari 14 primitive pakai DPR |
| Presisi warna | Diturunkan numerik, bukan dipilih | lihat tabel kontras di bawah |

## Yang audit temukan, dan bukan soal selera

Lima cacat. Empat nyata, satu tidak lolos ukur.

### 1. Token yang tidak pernah dideklarasikan

`page.tsx` memakai `text-fg`, `text-fg-dim`, dan `hover:text-fg` pada dua tombol
rail. Tak satu pun dari ketiganya ada di blok `@theme inline`, jadi Tailwind
tidak memancarkan CSS apa pun dan keduanya mewarisi warna dari `body`.

Diukur di browser sebelum diperbaiki: state MENYALA dan state MATI keluar warna
yang **identik**, `rgb(228, 232, 237)`, dan `hover:text-fg` tidak melakukan apa
pun sama sekali.

Kelas cacat yang sama sudah pernah diperbaiki di `posko-panel.tsx` untuk
`bg-panel-elevated`. Ia kembali karena tidak ada yang menjaganya. Sekarang
`e2e/theme.mjs` membandingkan setiap kelas warna Tailwind di `src/` lawan daftar
token yang benar benar dideklarasikan: 12 token, 37 file dipindai.

### 2. Nol state tekan di seluruh aplikasi

Sensus statis atas `src/`: **0** varian `active:`. 55 tombol, 25 switch, 12
slider, 6 select, dan tak satu pun memberi tanda bahwa ia sedang ditekan.

Sembilan tipe kontrol juga hanya punya hover di cabang **mati**: chip degree,
chip bias, chip timeframe, `Segmented`, tombol preset, tombol Live, tombol
interval, tab zona, tombol triad. Sebuah chip yang sudah menyala tidak menjawab
pointer sama sekali.

Tombol `Arm` di panel auto-trade, yang mengarmkan uang sungguhan, tidak punya
hover **maupun** active, dan disabled-nya ditulis lewat ternary `opacity-40`
alih alih varian `disabled:`.

Durasinya 70ms, dan angkanya dipinjam bukan dikarang: token motion IBM Carbon
menamai `duration-fast-01` 70ms dengan komentar peruntukan `micro-interactions
such as button and toggle, instant response to user action`. Apa pun di atas
240ms tidak punya tempat di rail dengan 21 baris.

Yang dianimasikan hanya `transform` dan `opacity`, keduanya dikerjakan
compositor. Menganimasikan `width` atau `background-color` di 115 kontrol
memicu layout atau paint per frame.

### 3. Focus ring setengah dari yang WCAG minta

Aturan global di `globals.css` berbunyi `outline: 1px` dengan `outline-offset:
1px`. WCAG 2.2 SC 2.4.13 Focus Appearance menuntut indicator `at least as large
as the area of a 2 CSS pixel thick perimeter of the unfocused component`. Jadi
ia tepat setengah.

Dua text input juga memakai `focus:outline-none` dengan pengganti berupa
perubahan warna border 1px, dan keduanya memakai `focus:` bukan
`focus-visible:`, jadi keduanya mematikan ring global. Sekarang 2px dengan
offset 2px, dan kedua `outline-none` itu dihapus.

### 4. Accent dipakai untuk status, melanggar kalimatnya sendiri

`globals.css` menyatakan accent punya **satu** makna: `this is the setting you
chose`. Empat banner status dicat dengan accent itu: dua di `page.tsx`, satu di
`zone-panel.tsx`, satu di `autotrade-panel.tsx`. Keduanya bukan setelan.

Percobaan menambah `--warn` amber **gagal diukur**, bukan gagal selera. Pada
kontras 5,0:1 hue amber yang terbaca sebagai peringatan jatuh di 27 derajat,
yaitu 12 derajat dari accent emas (38) dan 22 derajat dari supply merah (5).
Separuh hangat roda warna sudah habis dipegang dua makna.

Jadi satu warna status saja, `--info` cyan di 197 derajat, tepat 43 derajat dari
demand yaitu pagar yang sama yang `ink.ts` pakai. Bedanya info dan peringatan
dibawa **bentuk dan bobot**: glyph lingkaran lawan glyph segitiga, plus satu
baris bold. Itu channel yang sama yang detector pakai untuk identitasnya, yaitu
pola dash dan bukan warna.

Catatan jujur: ink family `levels` ada di hue 200,6 dan hanya 3,6 derajat dari
`--info`. Keduanya tidak pernah bersebelahan, `levels` digambar di canvas dan
`--info` selalu di bar full-width. Kalau suatu saat ada yang menaruh badge info
di ATAS chart, itu tabrakan pertama yang akan muncul.

### 5. Font ribbon tidak pernah sampai ke Plex

`cycle-ribbon.tsx` menulis `ctx.font = "9px ui-monospace, monospace"`, jadi ia
satu satunya teks di aplikasi yang digambar dengan font berbeda dari setiap
angka lain di layar.

### Yang TIDAK lolos ukur

Audit menandai `chart.tsx:291` sebagai risiko: ia memakai nama family mentah
`"IBM Plex Mono"` alih alih `var(--font-plex-mono)`, dan `next/font` biasanya
memancarkan nama yang di-hash.

Diukur di browser dengan probe lebar teks: **240px** lewat nama mentah, **240px**
lewat `var()`, **219,9px** lewat fallback `ui-monospace`. Ketiganya berbeda, dan
dua yang pertama identik. Nama mentahnya resolve. Bukan cacat.

## Palette light, diturunkan bukan dipilih

Constraint-nya bukan karangan: keempatnya sudah tertulis sebagai angka di
`globals.css` dan `ink.ts` untuk theme gelap. Tugasnya memenuhi angka yang sama
di atas background terang.

| Yang dijaga | dark | light |
|---|---|---|
| `--text` lawan bg | 15,81:1 | 15,85:1 |
| `--text-dim` lawan bg | 7,87:1 | 7,83:1 |
| `--text-faint` lawan bg | 5,28:1 | 5,30:1 |
| `--demand` lawan bg | 4,77:1 | 8,45:1 |
| `--supply` lawan bg | 8,29:1 | 4,59:1 |
| jarak L\* pasangan | 16,6 | 16,5 |
| kontras greyscale pasangan | 1,74:1 | 1,84:1 |
| supply lebih terang dari demand | ya | ya |
| jarak L\* accent ke supply | 1,4 | 9,0 |
| rentang greyscale ink family | 2,59:1 | 2,73:1 |
| ink family di dalam 43 derajat dari makna terpakai | 0 | 0 |

### Dua percobaan yang gugur, dan keduanya berguna

**Percobaan pertama mematok demand dan supply ke rasio kontras yang SAMA.** Itu
terdengar benar dan menghasilkan `#247b56` lawan `#be4337`, keduanya 4,77:1,
jarak L\* **0,0** dan kontras greyscale **1,00:1**. Di greyscale keduanya jadi
satu warna, persis cacat yang catatan di `globals.css` bilang sudah diperbaiki
untuk theme gelap (pasangan lama 1,25:1). Yang harus dijaga jarak L\*-nya, bukan
kontrasnya.

**Percobaan kedua salah mengukur greyscale-nya.** Fungsi `grey_ratio` yang saya
tulis me-round luminance ke integer lalu menghitung ulang lewat sRGB, dan
memberi 2,10:1 untuk pasangan gelap. `globals.css` mencatat 1,74:1. Kontras
WCAG sudah hue-blind, jadi `ratio()` itu sendiri **adalah** kontras
greyscale-nya, dan `8,29 / 4,77 = 1,74` cocok. Langkah tambahannya yang salah.

### Urutannya dipertahankan, dan itu bukan kosmetik

Supply tetap yang lebih terang dari demand di kedua theme. Kalau dibalik, dua
screenshot chart yang sama dari dua theme akan terbaca berlawanan di greyscale,
dan greyscale itulah yang dibaca satu dari dua belas pria dengan defisiensi
merah-hijau.

### Riset menyarankan sebaliknya, dan alasan menolaknya sebuah angka

Riset atas TradingView Advanced Charts dan lightweight-charts menemukan keduanya
memisahkan chrome dari semantik secara struktural: candle `upColor`/`downColor`
tidak ada di sistem theme sama sekali, dan default library tidak punya varian
terang. Sarannya mengunci warna candle di luar theme.

Saran itu tidak diambil, dan angkanya: supply salmon `#ef8f86` hanya **1,60:1**
lawan background terang `#f1f3f5`. Sebuah candle turun pada kontras 1,6:1 tidak
terbaca. Saran itu mengasumsikan background chart bernada tengah seperti punya
TradingView, bukan kertas. Yang dikunci di sini bukan nilainya melainkan
hubungannya: hue tetap, urutan lightness tetap, jarak L\* tetap.

## Kenapa tujuh role tidak dapat tujuh warna

Riset mengukur plafonnya, memakai CIEDE2000 di atas simulasi dichromacy Vienot
1999 (deuteranopia dan protanopia), dengan hijau, merah, dan emas sudah dipesan
di aplikasi ini.

| jumlah kategori | separasi minimum, bg gelap | bg terang |
|---|---|---|
| 3 | 22,2 | 23,4 |
| 4 | 20,8 | 19,2 |
| 5 | 13,3 | 17,1 |
| 6 | 11,1 | 13,0 |

Plafonnya **empat**. Di lima separasinya jatuh di bawah 15 dan mulai tidak
andal; di enam sudah 11.

Dan warna yang paling sering direkomendasikan sebagai aman gugur di sini:
`#CC79A7` reddish purple dari palette Okabe-Ito berjarak **dE 2,7** dari demand
green di bawah deuteranopia, praktis tidak bisa dibedakan. Grey `#999999` lebih
parah di protanopia, **1,9**. Orange `#E69F00` bertabrakan dengan accent emas
bahkan untuk penglihatan normal, **5,0**.

Konsekuensinya langsung: 21 layer butuh 21 **icon** berbeda, bukan 21 warna
berbeda. Itu juga yang `ink.ts` sudah simpulkan sendiri untuk lima family-nya.

## Icon, dan kenapa digambar tangan

Cakupan lima library, dihitung dari git tree repo resminya:

| Library | Glyph | Punya fair value gap, IFVG, breaker, SSMT, PSP, DFR, CISD |
|---|---|---|
| Tabler | 5.130 outline | tidak |
| Lucide | 1.798 | tidak |
| Phosphor | 1.512 x 6 weight | tidak |
| Radix | 332 | tidak |
| Heroicons | 324 | tidak |

Tujuh dari 21 layer tidak punya glyph di library mana pun. Jadi pertanyaannya
bukan library mana, melainkan apakah 21 layer itu dapat glyph generik atau
miniatur objeknya sendiri.

Yang dipilih yang kedua. Glyph di `src/components/icons.tsx` bukan metafora, ia
gambar objek yang layer itu cat di chart: glyph gap benar benar dua bar dengan
ruang di antaranya, glyph order block benar benar body candle padat dengan wick,
glyph divergence benar benar dua garis yang berpisah. Sebuah `Layers` generik
untuk supply and demand tidak membawa informasi itu, dan biaya 31,7 MB unpacked
untuk 40 glyph generik yang tujuh di antaranya tetap harus digambar tangan bukan
tukar yang menguntungkan.

Satu keluarga, grid 16, stroke 1,5, `currentColor` saja. Fill hanya di dua
tempat dan keduanya membawa arti: body candle yang memang padat, dan zona yang
memang punya isi.

## Retina, yang sudah benar sebelum audit

**14 dari 14** canvas primitive sudah menghitung DPR lewat
`useBitmapCoordinateSpace` dan `scope.horizontalPixelRatio` /
`scope.verticalPixelRatio`. Tidak ada satu pun yang menggambar di CSS pixel saja.
`cycle-ribbon.tsx` adalah satu satunya canvas di luar sistem primitive dan ia
mengurus DPR-nya sendiri.

Riset mengonfirmasi ini pendekatan yang benar, dan mengutip SKILL.md resmi
lightweight-charts: `Mixing these causes blur or sub-pixel jitter on HiDPI
displays`.

Satu hal yang **belum** dipakai dan bisa: docs lightweight-charts menyediakan
helper `positionsLine(positionMedia, pixelRatio, desiredWidthMedia)` dan
`positionsBox(position1Media, position2Media, pixelRatio)` supaya posisi
integer-nya konsisten dengan rendering logic internal library. Primitive di sini
menghitung sendiri. Belum diukur apakah ada selisih yang terlihat.

## Gate

```bash
cd backend  && .venv/Scripts/python.exe -m pytest          # 1224 passed
cd backend  && .venv/Scripts/python.exe -m pyflakes app tools tests
cd frontend && npm run check                               # exit 0
cd frontend && npm run build                               # exit 0
cd frontend && node e2e/wiring.mjs .playwright-shots       # exit 0
cd frontend && node e2e/labels.mjs .playwright-shots       # 9/9
cd frontend && node e2e/sweep.mjs .playwright-shots        # 158/158
cd frontend && node e2e/expectation-path.mjs .playwright-shots
cd frontend && node e2e/clickthrough.mjs .playwright-shots
cd frontend && node e2e/theme.mjs .playwright-shots        # 47 check
```

## Suntikan yang membuktikan `theme.mjs` tidak hampa

Tiap cacat dikembalikan, harness dijalankan, lalu dicabut lagi.

| Cacat yang disuntikkan | Hasil |
|---|---|
| `text-text` jadi `text-fg` di `page.tsx` | FAIL `fg (src\app\page.tsx)` |
| `wyckoff` dihapus dari `LAYER_ICON` | FAIL `wyckoff` |
| Hue `structure` digeser di tabel ink terang | FAIL, plus dua check turunan ikut merah |
| `--info` dihapus dari blok terang | FAIL `hanya gelap: info` |
| Urutan demand/supply dibalik di terang | FAIL `supply L* 29,8, demand 46,4` |
| Seluruh handler repaint theme dihapus | FAIL `luminance rata rata 0,080 lalu 0,080` |
| `active:translate-y-px` dihapus dari tab zona | FAIL, file dan kelasnya disebut |
| Langganan theme dihapus dari `Toolbox` | FAIL, `rgba(161,132,195,.95)` lalu `rgba(161,132,195,.95)` |
| Theme toggle dinaikkan ke `py-1.5` | FAIL, `chrome di atas chart 134px` |
| Nilai `SIDE.light.demand` di `ink.ts` diubah | FAIL pytest, `At index 0 diff: 31 != 21` |
| Heks pasangan dikembalikan ke `zone-panel.tsx` | FAIL pytest, `mengeja ulang pasangan itu` |

### Dua check yang versi pertamanya HAMPA, dan suntikan yang membuktikannya

Ini bagian yang paling berguna dari seluruh latihan.

**Kelengkapan token.** Versi pertama membaca token lewat `getComputedStyle` di
browser. `--info` dihapus dari blok terang dan check itu tetap **hijau**: custom
property **mewaris**, jadi token yang hilang di blok terang jatuh diam diam ke
nilai gelapnya dan browser melaporkannya ada. Cacatnya tertangkap check LAIN
(kontras `--info` jatuh ke 3,48:1), yang berarti check itu bekerja karena
kebetulan. Sekarang kunci kedua blok dibaca dari CSS-nya sendiri.

**Repaint canvas.** Versi pertama membandingkan panjang buffer PNG canvas dari
dua page load terpisah. Seluruh isi handler pergantian theme dihapus, dan check
itu tetap **hijau**: 84071 lalu 84072 byte. Satu byte, dan byte itu datang dari
harga yang bergerak. Dua kesalahan sekaligus, keduanya terungkap oleh suntikan
yang sama:

1. Dua page load terpisah masing masing membaca theme-nya sekali **sebelum**
   chart dibuat, jadi keduanya benar bahkan tanpa handler apa pun. Yang menguji
   wiring-nya hanya mengklik saklarnya di halaman yang sudah hidup.
2. Kesetaraan byte lolos karena noise. Yang diukur sekarang rata rata luminance
   seluruh canvas, dan ia harus **melewati** 0,5, bukan sekadar berubah. Terukur
   sesudah diperbaiki: **0,080 lalu 0,912**.

**Tinggi chrome, dan dua percobaan yang gagal sebelum yang ketiga mengukur.**
Theme toggle masuk dengan `py-1.5` dan jadi empat piksel lebih tinggi dari 14
kontrol header lain. Header naik dari 78 ke 82, tinggi chart turun dari 591 ke
588, dan sebuah caption di y 688,5 setinggi 12px mulai menggantung melewati
edge bawah pane. `e2e/labels.mjs` jatuh dari 9/9 ke 8/9 dengan box yang sama di
dua run berurutan, jadi bukan flaky. Tidak ada yang terlihat salah di layar, dan
tiga piksel bukan sesuatu yang bisa dilihat mata.

Percobaan pertama menuntut semua kontrol header **setinggi sama**. Ia menolak
keadaan yang benar: kontrol di sana memang 24 sampai 27px karena font, border
dan padding-nya berbeda.

Percobaan kedua menuntut **rentangnya** paling banyak 4px. Ia **lolos dengan
cacatnya disuntikkan**: toggle jadi 28px dan seluruh klaster bergeser ke 25-28,
jadi rentangnya tetap 3. Diukur, bukan dikira.

Yang mengikat akhirnya hal yang sesungguhnya rusak: tinggi chrome di atas chart,
diperiksa lawan tinggi viewport. 130px lolos, 134px merah.

Satu jebakan lagi, dan ia sudah tercatat di memori project ini: suntikan pertama
untuk cacat itu **tidak pernah terjadi**. Pola `sed` saya tidak cocok, dan
`grep -c "py-1.5"` yang saya percaya menghitung `py-1.5` di dalam komentar yang
saya sendiri baru tulis. Harness-nya hijau karena kodenya tidak pernah berubah,
bukan karena check-nya lemah. Suntikan kedua memakai `assert` atas jumlah
kecocokan sebelum menulis, lalu menunggu 35 detik recompile Next.

Dan scanner statisnya sendiri sempat merah karena alasan yang salah: ia membaca
`text-fg` dari **komentar yang menjelaskan bahwa `text-fg` sudah dihapus**.
Sebuah pengukur yang menghitung catatan tentang cacat sebagai cacat akan tetap
merah selamanya sesudah diperbaiki, dan harness yang tidak bisa jadi hijau
adalah harness yang dimatikan orang. Komentar sekarang dibuang sebelum dipindai.

## Yang belum dikerjakan, dinyatakan bukan disembunyikan

- **Prose auto-trade masih terbuka.** `Off means no new orders. Pending orders
  already at the broker keep their stop and target` tiga baris dan selalu
  terlihat. Ia tidak dilipat dengan sengaja: itu pernyataan tentang uang yang
  sudah dipasang di broker, dan melipat informasi keselamatan di balik fold
  bukan perbaikan. Prose Presets yang dilipat, dan itu deskripsi fitur.
- **Header masih membungkus ke dua baris di 1600px.** Ada 16 kontrol di sana,
  tingginya 78px, dan itu 130px chrome bersama dua banner. Belum diukur apakah
  pengelompokan bisa mengembalikannya ke satu baris tanpa menyembunyikan
  sesuatu. Ambang 132px di `theme.mjs` menjaga supaya ia tidak tumbuh lagi
  tanpa ada yang tahu.
- **Jumlah check `sweep.mjs` tidak stabil terhadap suntingan saya sendiri.** Ia
  158 sebelum sesi ini, terbaca 159 sekali di tengah sesi, dan 158 lagi
  sekarang. Nama seluruh check identik antara HEAD dan tree kerja, jadi tidak
  ada yang hilang diam diam, tapi kenapa sempat 159 belum ditelusuri.
- **Helper `positionsLine` / `positionsBox` belum dipakai.** Lihat bagian
  Retina.
- **`--info` dan ink family `levels` berjarak 3,6 derajat.** Aman sekarang
  karena keduanya di permukaan berbeda. Belum diukur kalau itu berubah.
- **Jarak L\* accent ke supply di theme GELAP masih 1,4 poin** dengan hue hanya
  34 derajat berjarak. Itu kelemahan yang sudah ada sebelum audit ini dan tidak
  diperbaiki: memindahkan accent berarti memindahkan satu satunya warna kontrol
  di aplikasi. Di theme terang jaraknya 9,0 poin, jadi versi terangnya lebih
  baik, dan itu kebetulan dari constraint-nya bukan tujuan.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
