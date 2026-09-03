# QA UI, audit dan hasilnya

Ditulis 3 September 2026. Isinya apa yang diukur, angkanya, dan suntikan yang
membuktikan tiap gate baru tidak hampa.

> [!IMPORTANT]
> Semua angka di file ini berasal dari command yang benar benar dijalankan.
> Yang belum diukur ditulis belum diukur.

## Ringkasan

| Yang diminta | Status | Angkanya |
|---|---|---|
| Light mode | Terpasang, default tetap dark | 52 check di `e2e/theme.mjs` hijau |
| Icon interaktif | 40 glyph, digambar tangan | 1 SVG jadi 73 SVG di halaman |
| Interaction state | Hover, press, focus di tiap kontrol | 0 varian `active:` jadi 22 |
| Warna di chrome | Glyph layer memakai ink yang layer itu cat | 0 warna baru, 5 ink family yang sudah ada |
| Retina | **Laporan pertama saya salah**, 58 persen garis kabur di skala 2 | 119 garis straddle jadi 0 |
| Header | Dua band yang disengaja, bukan dua baris yang kebetulan | konten butuh 2.348px, viewport 1.920px |
| Font canvas | 16 deklarasi dalam 4 bentuk jadi 1 | 13 dari 16 tidak pernah sampai ke Plex |
| Presisi warna | Diturunkan numerik, bukan dipilih | lihat tabel kontras di bawah |
| Loading dan error state | Skeleton kerangka plus error yang menyebut langkahnya | loading 645-674ms terukur, tiga run per provider |

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

## Retina, dan koreksi atas laporan saya sendiri

Laporan pertama saya berbunyi "sudah benar sebelum audit", dengan alasan bahwa
**14 dari 14** canvas primitive membaca `scope.horizontalPixelRatio` dan
`scope.verticalPixelRatio` lewat `useBitmapCoordinateSpace`. Klaim tentang
KODE-nya benar dan masih benar. Klaim tentang EFEK-nya salah, dan alat ukurnya
yang membuatnya salah.

### Kenapa pengukuran pertama tidak bisa menunjukkan apa pun

Ia memakai `deviceScaleFactor` per-context milik Playwright. Ia melaporkan
`window.devicePixelRatio` sama dengan 2 ke JS, jadi ia terlihat cukup. Ia tidak
memberi fancy-canvas sebuah device-pixel content box, dan itu yang fancy-canvas
baca.

Sensus bitmap seluruh canvas chart:

| deviceScaleFactor | devicePixelRatio | ratio bitmap canvas |
|---|---|---|
| 1 | 1 | 1,00 |
| 2 | 2 | **1,00** |
| 3 | 3 | **1,00** |

Sama di halaman minimal tanpa satu baris kode Zonelab, jadi bukan cacat kami.
Dan bukan artefak `matchMedia` juga: `(resolution: 2dppx)` menjawab `true`, dan
canvas kontrol yang diskalakan tangan jadi 200x100 untuk CSS 100x50.

Yang bekerja `--force-device-scale-factor=2` sebagai **argumen browser**. Di
sana ratio bitmap-nya 2,00 dan lightweight-charts menskalakan benar. Selama
`scope.horizontalPixelRatio` selalu 1, jalur DPR di 14 primitive itu tidak
pernah dieksekusi sama sekali.

### Cacatnya, sesudah bisa diukur

Setiap garis tipis digambar dengan pola `round(v * k) + 0.5` dan lebar
`max(1, round(k))`. Pada `k = 1` itu **benar**: stroke lebar 1 yang dipusatkan
di setengah pixel menutupi tepat satu baris. Pada `k = 2` stroke lebar 2 yang
dipusatkan di setengah pixel menutupi separuh baris atas, seluruh baris tengah,
dan separuh baris bawah.

Diukur dari profil alpha tiap garis tipis di 14 kolom canvas:

| | garis pas | lunak | tepi |
|---|---|---|---|
| skala 1, sebelum | 133 | 0 | - |
| skala 2, sebelum | 87 | **119** | median **0,50** |
| skala 1, sesudah | 125 | 0 | - |
| skala 2, sesudah | 122 | 8 | 0,05 sampai 0,18 |

Alpha tepi tepat 0,50 adalah tanda buku teks stroke yang mengangkangi batas
device pixel. Delapan yang tersisa ujung dash dan garis diagonal, yang secara
definisi tidak bisa disejajarkan ke grid. Yang dijaga karena itu bukan "nol
garis lunak" melainkan **nol straddle**.

**Panjang run tidak dipakai memutuskan**, dan itu penting: rule 1,5px yang
memang dipakai project ini SAH menempati tiga baris di skala 2. Percobaan
pertama menghitung panjang run dan melaporkan 110 garis di 3 baris, yang tidak
bisa dibedakan dari rule 1,5px yang benar. Profil alpha tidak bergantung lebar.

### Kedua helper itu tidak diekspor package-nya

Docs plugin lightweight-charts menyebut `positionsLine` dan `positionsBox` wajib
dipakai supaya posisi integer-nya konsisten dengan rendering logic internal
library. `grep -r positionsLine node_modules/lightweight-charts/` mengembalikan
**nol** di 5.2.1. Keduanya ditulis ulang di `src/components/pixel.ts` dengan
semantik yang didokumentasikan, plus `strokeLine` untuk garis putus putus yang
tidak bisa memakai `fillRect` karena `setLineDash` hanya berlaku pada path, dan
pola dash adalah encoding identitas detector di repo ini.

`demo()` di file itu mengunci aritmetikanya dan **dijalankan sekali saat modul
dimuat**: hasilnya masuk ke `console.error` kalau gagal, jadi `e2e/sweep.mjs`
yang menuntut nol console error ikut merah, dan ke `window.__pixelDemo` supaya
`e2e/retina.mjs` bisa menegaskannya langsung. Sebuah fungsi verifikasi yang
tidak dipanggil siapa pun adalah dokumentasi.

### Dua bug DPR lain yang ikut ketemu

`zone-primitive.ts` menggambar stroke dalam untuk box terbalik dengan inset 3,5
dan 7 yang dituliskan langsung dalam device pixel. Pada skala 2 stroke itu duduk
3 device pixel dari border luar alih alih 6, dan pada box 9 device pixel ia
menempel ke border luarnya. Satu satunya cue yang selamat di box tiga pixel
adalah "kotak di dalam kotak", dan cue itu hilang kalau kedua kotaknya
bersentuhan.

`rect()` di file yang sama membulatkan awal dan LEBAR secara terpisah, jadi tepi
kanan sebuah box bisa jatuh satu device pixel dari tempat box sebelahnya
membulatkan tepi yang sama. `positionsBox` membulatkan kedua tepi lalu
menyelisihkannya.

## Header, dan kenapa satu baris tidak mungkin

Diukur: 16 kontrol di header butuh **2.348px** konten, dan viewport paling lebar
yang diuji memberi **1.920px**. Satu baris tidak mungkin tanpa membuang sesuatu.
Header-nya sendiri 78px, yaitu 7,4 persen dari viewport 1.050px.

Yang salah bukan jumlah barisnya melainkan pembagiannya. Dengan satu
`flex-wrap` atas 16 anak, tempat putusnya diputuskan lebar konten dan bukan
artinya, dan hasilnya terbaca di sensus: `HTF` mendarat di baris pertama
sementara `Clock` di baris kedua, padahal keduanya kontrol sejenis.

Satu hipotesis saya **tidak terbukti** dan tidak diklaim: saya menduga titik
putusnya bergeser saat jumlah digit harga berubah. Diuji dengan berganti dari
XAUUSD (4.400) ke BTCUSD (77.860): **nol** elemen berpindah baris.

Sekarang pembagiannya menjawab dua pertanyaan berbeda. Band atas "data apa":
instrumen, sumber, jumlah bar, broker, dan bacaan OHLC yang keempatnya
hasilkan. Band bawah "dilihat bagaimana": timeframe, HTF, clock, plus kontrol
sesi dan dua saklar panel. Terukur muat sampai 1.280px, band atas 1.067px dan
band bawah 1.009px sebelum gap, keduanya satu baris 27px. Di bawah itu keduanya
membungkus lagi, yang memang jawaban yang benar.

## Font, satu deklarasi dari empat

Sensus `ctx.font` di `src/components`, sebelum:

| bentuk | situs | sampai ke Plex |
|---|---|---|
| `round(9 * ky)px ui-monospace, monospace` | 11 | tidak |
| `round(10 * ky)px ui-monospace, monospace` | 2 | tidak |
| `500 ...px "IBM Plex Mono", ui-monospace, monospace` | 2 | ya |
| `9px monoStack()` | 1 | ya |

Jadi **13 dari 16** teks di canvas digambar dengan monospace bawaan sistem, yang
di Windows Consolas, sementara caption zona dan label struktur digambar dengan
Plex. Dua font di satu canvas, di objek yang bersebelahan.

Selisihnya bukan sekadar bentuk huruf. Diukur di browser, string caption
`DBR 4437.556`:

| ukuran | ui-monospace | Plex Mono | selisih |
|---|---|---|---|
| 9px | 59,38px | 64,80px | +9,1% |
| 10px | 65,98px | 72,00px | +9,1% |

Per karakter di 10px: 5,5px jadi 6,0px. `labels.mjs` tetap 9/9 sesudah
perubahan, jadi lebar tambahan itu tidak membuat tabrakan caption baru.

Semuanya sekarang lewat `monoFont(px, ratio, weight)` di `ink.ts`. `weight` ada
karena dua situs memang memakai 500 dan itu disengaja; yang dihapus bukan
pilihannya melainkan empat cara menuliskannya. `chart.tsx` juga berhenti mengeja
stack itu sebagai literal, yang tadinya ejaan keempat.

### Dan angka yang jadi basi karenanya

`LABEL_GUTTER = 46` di `structure-primitive.ts` dibenarkan oleh komentar yang
berbunyi bahwa tag terpanjang enam karakter dan 10px ui-monospace mengukur 5,5px
per karakter, jadi 33px plus 8px padding.

Per karakternya benar. Klaim "enam karakter" **salah, dan sudah salah sebelum
perubahan saya**: `PDH/PDL` tujuh karakter dan mengukur 38,5px, jadi totalnya
46,5px dan sudah melewati 46. Di Plex ia 42px, totalnya 50px.

Yang menjaga kolom itu bukan konstantanya. Tiap tag diukur `measureText` saat
digambar, dan logika penggabungan di `levels-primitive.ts` menjatuhkan tag yang
tidak muat. `e2e/labels.mjs` memeriksanya dari bitmap: nol label mengangkangi
edge pane, 9/9, sesudah font-nya berganti. Konstanta itu lantai kolomnya, bukan
jaminan lebarnya, dan komentarnya sekarang mengatakan begitu.

## Text, sensus duplikat

Dua puluh string muncul lebih dari sekali di satu layar. Sebagian besar penanda
per baris yang memang harus berulang: 22 `Diukur`, 21 `Bukti`, 14 `Apa ini`, 10
`ATR`, 6 `Fresh`. Menghapusnya akan menghapus informasi.

Satu yang benar benar cacat: **`Clock` dipakai dua hal berbeda yang terlihat
sekaligus**. Header punya picker `Clock` yang memilih zona waktu; Presets punya
tombol `Clock` yang menyalakan layer waktu. Seseorang yang mengklik yang kedua
punya alasan bagus untuk mengira ia mengubah setelan yang pertama. Tombol itu
sekarang `Time grid`, dan `id`-nya tetap `clock` karena itu kunci yang tersimpan
di localStorage pembaca.

`e2e/theme.mjs` menjaganya per **pasangan tipe kontrol**, bukan per string,
supaya penanda per baris tidak dihitung sebagai tabrakan.

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
cd frontend && node e2e/theme.mjs .playwright-shots        # 54 check
cd frontend && node e2e/retina.mjs .playwright-shots       # 10 check, 2 skala device
cd frontend && npm run e2e:pixels                          # 7/7 geometri zona
cd frontend && node e2e/click-everything.mjs .playwright-shots  # 223/223 setelah saklar rail dilewati
cd frontend && node e2e/clock.mjs .playwright-shots        # 42/42 setelah pola bulan dilebarkan
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
| Skeleton versi 15 kolom dikembalikan | FAIL, `15 elemen berlatar lebih tinggi dari sepertiga pane` |
| Pola `round(v*k)+0.5` dikembalikan di `levels-primitive` | FAIL, `straddle 116`, tepi 0,47 sampai 0,50 |
| `ctx.font` bentuk lama dikembalikan di `psp-primitive` | FAIL, file dan bentuknya disebut |
| Label preset dikembalikan ke `Clock` | FAIL, tabrakan nama terdeteksi |
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

## Loading dan error state

**Diukur dulu sebelum dibangun**, karena skeleton untuk 200ms lebih buruk
daripada tidak ada: ia berkedip. Waktu dari `domcontentloaded` sampai chart
pertama muncul, tiga run per provider di mesin ini:

| provider | run | median |
|---|---|---|
| synthetic | 663, 645, 674 ms | 663 ms |
| mt5 | 645, 667, 633 ms | 645 ms |

Itu di atas ambang 100ms yang Nielsen sebut sebagai batas "terasa seketika",
jadi ia terlihat, dan di bawah satu detik, jadi spinner terasa salah.

Yang ada di sana sebelumnya teks `Loading candles.` terpusat di pane, yang
membuat layout **melompat** saat data datang karena tidak ada yang menahan
tempatnya.

**Percobaan pertama skeleton gugur karena screenshot-nya.** Ia menggambar 15
kolom setinggi 38 sampai 74 persen, dan hasilnya terbaca sebagai **bar chart
yang sungguhan**. Sebuah placeholder yang bisa disalahbaca sebagai harga lebih
buruk daripada tidak ada placeholder, karena satu detik pertama seseorang
mungkin membacanya sebagai harga. Yang digambar sekarang hanya sumbu dan
gridline: tidak mungkin dibaca sebagai harga, tetap menahan tempat yang sama,
dan separuh jumlah elemennya.

Check yang menjaga itu juga salah di versi pertamanya: ia melaporkan 4
pelanggaran yang ternyata **gridline vertikal**, lebar 1px dan tinggi penuh.
Garis 1px tidak bisa dibaca sebagai bar harga. Predikatnya sekarang menuntut
tinggi **dan** lebar. Diuji dengan versi bar dikembalikan: 15 pelanggaran,
merah.

Error state-nya dulu `No data to chart.` di tengah pane: benar, dan jalan
buntu. Ia tidak menyebut provider mana yang gagal, tidak menyebut simbol mana,
dan tidak menawarkan satu pun langkah, padahal pesan error-nya sudah ada di
state dan cuma tidak ditampilkan. Sekarang ia menyebut simbol, provider, kode
HTTP-nya, dan tiga langkah yang benar benar memperbaiki kegagalan ini di mesin
ini.

Keduanya dijaga dengan **memicu**, bukan menunggu: request drawing-nya ditahan
tanpa dijawab untuk loading, dan dipalsukan 503 untuk error. Screenshot yang
dikejar `waitForTimeout` akan menangkap keadaan yang berbeda tiap run. Tidak
ada jalur normal yang melewati kedua state itu, jadi sebuah cacat di sana bisa
hidup berbulan bulan tanpa ada yang tahu.

## Sensus harness, karena delapan dari dua puluh lima tidak cukup

Pekerjaan di atas dijalankan atas delapan harness. Repo ini punya **25**.
Menjalankan sisanya menemukan tiga hal, dan dua di antaranya cacat harness yang
membuat pengukuran lain berhenti berarti.

### `click-everything.mjs` menutup dua panel lalu mencari isinya

Ia mengklik **setiap** tombol, termasuk dua saklar rail. Mengklik keduanya
menyembunyikan panel kiri dan kanan, jadi sisa crawl mencari kontrol di panel
yang baru saja ia tutup. Dua kegagalan yang berdiri di file itu melaporkan panel
yang rusak:

```
FAIL  reset button is reachable :: no button matched /reset parameters/i
FAIL  zone row opens the inspector :: panel says "(no header)"
```

Panelnya baik. Yang tidak baik jangkauannya:

| | check dijalankan |
|---|---|
| sebelum | 65 dari 67 |
| sesudah kedua saklar dilewati | **223 dari 223** |

Jadi sebuah harness bernama "click everything" menjangkau **kurang dari
sepertiga** kontrol app dan melaporkannya sebagai lengkap. Kedua saklar itu
punya harness sendiri, `e2e/rails.mjs` 9/9, yang memang memeriksa panel hilang
lalu kembali.

Satu run memberi **210 dari 223** sementara lima run lain memberi 223/223.
Daftar kegagalannya tidak tertangkap ke file dan tidak tereproduksi dalam lima
percobaan berikutnya, jadi sebabnya belum diketahui. Ia crawler dengan 223
langkah yang bergantung timing di atas dev server yang saat itu sudah menerima
sekitar empat puluh peluncuran browser, tapi itu dugaan dan bukan pengukuran.
Dicatat di sini supaya tidak hilang; kalau ia muncul lagi, arahkan output-nya ke
file sebelum menyimpulkan.

Dibuktikan tidak hampa: `onChange` di saklar layer diganti no-op, dan harness
itu jatuh ke 163/165 dengan tangkapan yang benar, `panel says "0 drawn"`.

### `clock.mjs` merah satu bulan dalam setahun

Tiga kegagalan berbunyi `no crosshair stamp was painted`. App-nya **melukis**
stamp-nya; diukur dengan membungkus `fillText`, yang keluar `02 Sept 19:45 UTC`.

Pola harness-nya `/^\d{2} \w{3} (\d{2}):(\d{2}) (UTC|NY|WIB)$/`. `clock.ts`
memformat dengan `en-GB` dan `month: "short"`, dan en-GB memberi **tiga huruf
untuk sebelas bulan lalu EMPAT untuk September**: `Sept`. Dijalankan atas dua
belas bulan, panjangnya 3 dan 4.

Jadi harness itu merah sepanjang September dan hijau sendiri pada 1 Oktober
tanpa ada yang menyentuh satu baris. Itu bentuk kegagalan terburuk yang bisa
dipunyai sebuah harness: warnanya ditentukan kalender, jadi yang melihatnya
merah mencari cacat yang tidak ada, dan yang melihatnya hijau tidak tahu ia baru
berhenti memeriksa apa pun.

| | |
|---|---|
| sebelum | 36 dari 39 |
| sesudah pola dilebarkan ke `\w{3,4}` | **42 dari 42** |

Tiga check yang bergantung pada stamp itu selama ini tidak pernah dijalankan.
Dibuktikan tidak hampa: tag zona dihapus dari `clockStamp`, dan harness itu
jatuh ke 34/39 dengan lima kegagalan termasuk `got 15 Jan 07:30, want 15 Jan
07:30 NY`.

### `nonbox-truth.mjs` masih merah, dan saya tidak menyelesaikannya

```
FAIL  garis putus-putus benar-benar putus :: duty solid 1.000 (n=23) lawan
      dashed 0.893 (n=4), selisih 0.107 butuh >= 0.15
```

Yang sudah dipastikan:

- **Bukan dari sesi ini.** Identik byte per byte di commit pra-sesi `e6c0e73`.
- **Bukan penjumlahan baris bersebelahan** di probe-nya. Komentar di sana
  menjelaskan penjumlahan itu mengompensasi stroke yang terbelah setengah
  pixel; dimatikan sebagai eksperimen, angkanya **tetap 0,893**.
- Ray tier horizon memang digambar dash `[4, 3]`, jadi duty seharusnya
  4/7 = **0,571**, bukan 0,893.

Yang belum diuji: apakah dua ray dash dengan **fase berbeda** mendarat di harga
berdekatan sehingga gabungannya terbaca hampir solid. Tiga tier dikali dua kind
memberi sampai enam ray, dan probe-nya menyapu 6 baris ke atas dan bawah lalu
mengambil yang terdekat. Kalau itu sebabnya, yang harus diperbaiki isolasi ray
di probe-nya, bukan gambarnya.

Diserahkan begitu, bukan ditebak. File itu sendiri membawa komentar tentang tiga
cacat probe sebelumnya, jadi menulis ulang scan intinya tanpa mengukur sebabnya
adalah cara cacat probe keempat masuk.

### `labels.mjs` deterministik terhadap kode, bukan terhadap waktu

Ia hijau 9/9 dua kali di sesi ini lalu merah 8/9 beberapa jam kemudian dengan
straddle di edge **atas**, `y: -1.5`. Dijalankan di commit pra-sesi `e6c0e73`
pada saat yang sama: **merah juga, di posisi identik**, hanya lebarnya beda
(24,99 lawan 27, yang justru mengonfirmasi perubahan font di atas aktif).

Jadi bukan dari sesi ini. Tapi catatan yang ada menyebut harness ini
"deterministik sejak dipatok ke synthetic", dan itu lebih sempit dari yang
tertulis: provider synthetic tetap maju dengan wall-clock, jadi caption yang
muat pada pukul delapan bisa menggantung pada pukul dua belas. Ia deterministik
untuk membandingkan dua tree **pada saat yang sama**, yang memang gunanya, tapi
merah telanjang di sana bukan bukti cacat kode.

### Keadaan seluruh 25 harness

Hijau, 20: `wiring`, `labels` (lihat catatan waktu di atas), `sweep` 158/158,
`expectation-path`, `clickthrough`, `theme` 54, `retina` 10, `pixel-truth` 7/7,
`rails` 9/9, `ink-budget` 3/3, `ribbon` 8/8, `clock` 42/42, `zone-audit`,
`chart-audit`, `viewports` 25/25, `visual-audit`, `posko-fibonacci` 30/30,
`vortex` 21/21, `offscreen-zones` 3/3, `click-everything` 223/223, `agent` 7/7.

Merah, 3, semuanya pra-sesi dan diverifikasi identik di `e6c0e73`:
`nonbox-truth` 4/5, `pixels-ifvg` 6/7, `pixels-brk` 5/7.

Tidak dijalankan, 2, dan keduanya disengaja: `autotrade.mjs` menyentuh saklar
auto-trade yang sungguhan dan CLAUDE.md melarangnya saat ada daemon;
`resilience.mjs` sengaja menjatuhkan backend.

## Audit statis awal, mana yang masih berdiri

| Klaim audit awal | Status sesudah diperiksa |
|---|---|
| `app/ssmt.py:485 intermarket` nol pemanggil | **Benar.** Nol di app, tools, tests, frontend, harness. 15 baris kode mati. Tidak dihapus: itu backend di luar lingkup UI yang diminta, dan fungsi yang menyandi aturan praktisi tidak dibuang tanpa ditanya |
| `app/expectation.py:40 base_rate` diduplikat inline di `overlays.py:475` | **Benar,** dan kecil. Satu fungsi satu baris lawan satu `cell.get()` inline |
| `judas.py` dan `m4.py` nol referensi test | **Salah.** `tools/conditioned.py` mengimpor `judas_classify`, dan `tools/quant.py` plus `tools/conditioned.py` mengimpor `in_judas_window` |
| 10 field params tanpa kontrol UI | **Salah sekarang.** Diukur lawan registry hidup: nol field tanpa jejak di `toolbox.tsx`, nol di `types.ts` tanpa jejak |
| `LAYER_SWATCH` bisa kehilangan layer baru tanpa suara | **Sudah dijaga.** `checklist` satu satunya tanpa swatch dan itu disengaja, dijaga `wiring.mjs` dengan check terpisah |
| `toolbox.tsx default: return null` seam | **Berdiri, tapi tidak bocor.** Satu blok params tanpa `case`, `chart_gaps`, dan `ChartGapParams` punya nol field jadi memang tidak ada kontrol untuk dicari. `wiring.mjs` menulis pengecualiannya |
| `test_overlay_api.py ASYNC_DISPATCHED` seam | **Berdiri.** Set literal empat id yang mengecualikan diri dari check "registered but never drawn". Butuh seseorang menambahinya untuk bocor |
| `test_frontend_defaults.py OWNERS` tidak terikat registry | **Berdiri sebagian.** Ia diikat ke `types.ts`, dan `types.ts` diikat ke registry oleh test lain di file yang sama, jadi rantainya utuh lewat dua langkah. `wiring.mjs` sendiri menulis bahwa `OWNERS`-nya "gagal sunyi" |

## Kode mati yang saya sendiri tinggalkan, dan dihapus

- `sideRgb()` di `ink.ts`: nol pemanggil. Saya menambahkannya bersama
  `sideRgba()` "untuk nanti".
- `inkTheme()` di `ink.ts`: nol pemanggil, sama.
- `const seen = {}` di `e2e/retina.mjs`: ditulis, tidak pernah dibaca.

`positionsLine()` tetap meski tidak dipanggil langsung dari luar `pixel.ts`:
`strokeLine()` dan `positionsBox()` keduanya diturunkan darinya, dan
memindahkan aritmetikanya ke dalam pemanggil adalah cara dua salinan muncul.

## Yang belum dikerjakan, dinyatakan bukan disembunyikan

- **Prose auto-trade masih terbuka.** `Off means no new orders. Pending orders
  already at the broker keep their stop and target` tiga baris dan selalu
  terlihat. Ia tidak dilipat dengan sengaja: itu pernyataan tentang uang yang
  sudah dipasang di broker, dan melipat informasi keselamatan di balik fold
  bukan perbaikan. Prose Presets yang dilipat, dan itu deskripsi fitur.
- **Tiga harness merah, semuanya pra-sesi.** Rinciannya di bagian sensus
  harness di atas: `nonbox-truth` 4/5 dengan dua hipotesis sudah digugurkan,
  `pixels-ifvg` 6/7 dan `pixels-brk` 5/7 dari 8 box breaker yang bertumpuk di
  harga sehingga probe tidak bisa mengisolasi tepinya.
- **`app/ssmt.py:485 intermarket` kode mati,** nol pemanggil di seluruh repo.
  Tidak dihapus karena itu backend di luar lingkup UI yang diminta, dan sebuah
  fungsi yang menyandi aturan praktisi tidak dibuang tanpa ditanya.
- **`ASYNC_DISPATCHED` di `test_overlay_api.py` masih escape hatch manual.**
  Set literal empat id yang mengecualikan diri dari check
  `registered but never drawn`. Bocor hanya kalau seseorang menambahinya.
- **Jumlah check `sweep.mjs` tidak stabil terhadap suntingan saya sendiri.** Ia
  158 sebelum sesi ini, terbaca 159 sekali di tengah sesi, dan 158 lagi
  sekarang. Nama seluruh check identik antara HEAD dan tree kerja, jadi tidak
  ada yang hilang diam diam, tapi kenapa sempat 159 belum ditelusuri.

- **`--info` dan ink family `levels` berjarak 3,6 derajat.** Aman sekarang
  karena keduanya di permukaan berbeda. Belum diukur kalau itu berubah.
- **Jarak L\* accent ke supply di theme GELAP masih 1,4 poin** dengan hue hanya
  34 derajat berjarak. Itu kelemahan yang sudah ada sebelum audit ini dan tidak
  diperbaiki: memindahkan accent berarti memindahkan satu satunya warna kontrol
  di aplikasi. Di theme terang jaraknya 9,0 poin, jadi versi terangnya lebih
  baik, dan itu kebetulan dari constraint-nya bukan tujuan.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
