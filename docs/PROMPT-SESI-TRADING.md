# Template prompt sesi trading

Template yang dipakai untuk membuka sesi analisis pasar plus order di
Zonelab. Bagian pertama adalah prompt yang di-copy apa adanya. Bagian kedua
adalah daftar jebakan yang sudah memakan waktu nyata, ditulis di sini supaya
prompt-nya tidak perlu memuat semuanya dan sesi yang membacanya tetap tahu.

> [!IMPORTANT]
> Prompt ini meminta order di akun SUNGGUHAN. Bagian 5 di bawah memuat
> empat hal yang harus diperiksa SEBELUM mengirim apa pun, dan keempatnya sudah
> pernah salah setidaknya sekali.

## 1. Prompt, copy apa adanya

```text
Analisa dan cek kondisi market saat ini. Tarik semua fitur, function, news dan
tools yang ada di Zonelab. Cek juga korelasi XAU. Tentukan order untuk XAU dan
BTC. Kita entry di low timeframe, 30M ke bawah, Risk Reward 1:2. Berikan
advisor: di price berapa, SL berapa, TP berapa.

Jenis order ADAPTIF, tergantung hasil analisa: pending limit kalau harga masih
jauh dari zona, dan boleh langsung market kalau harga sudah mendekat DAN
gerbangnya lolos. Aturan pemilihannya di bagian 3 dokumen ini - jangan
memutuskannya dengan perasaan, karena batas antara keduanya menentukan apakah
trade-nya masih anggota populasi yang diukur.

Aturan yang tidak boleh dilanggar:

1. PISAHKAN apa yang MENYELEKSI order dari apa yang cuma DIBACA. Sebutkan
   secara eksplisit kriteria mana yang memilih tiap order, dan layer mana yang
   hanya konteks. Kalau order-nya dipilih oleh gerbang supply_demand, jangan
   sebut ia berbasis ICT.
2. Jangan berikan klaim arah. Dua belas hipotesis arah praregistrasi mati di
   project ini dan skor checklist tidak memisahkan hasil. Berikan lokasi, jam,
   dan kondisi.
3. Setiap angka harus dari command yang benar-benar dijalankan. Kalau belum
   diukur, tulis bahwa belum diukur.
4. Jam New York dibaca lewat `app/clock.py`, bukan lewat variabel TZ.
5. RR 1:2 harus di-override manual. `app/plan.py` menurunkan target dari
   `profit_zone_rr * tinggi zona`, jadi RR adalah konsekuensi bukan setelan.
6. Sebelum mengirim order, periksa `.autotrade.json`, journal, cap portofolio,
   dan apakah lot minimum melanggar anggaran risiko. Lapor keempatnya.
7. Verifikasi order yang terkirim lewat pembacaan INDEPENDEN dari order book,
   bukan dari output script pengirimnya. Retcode 0 di API MetaTrader 5 berarti
   dua hal berlawanan, jadi ia bukan verifikasi.
8. Sebut TIMEFRAME populasi yang angkanya dipakai. `detectors_costed.json`
   diukur di 1h dan 4h; untuk 30m pakai `lowtf_costed.json` plus kontrol
   resolusinya `lowtf_resolution.json`, dan sebut yang kedua kalau angka
   pertama dikutip. Untuk 15m TIDAK ADA angka: riwayat 1 menit di mesin ini
   cuma 103 hari XAUUSD dan 69 hari BTCUSD.
9. Jangan order `fvg`. Zonanya punya target sejak 2 September 2026, dan
   gerbang departure-nya TERBALIK di rig berbiaya: -0,1005 R dengan t=-4,48.
   `tools/execute.py` menolaknya lewat `ORDERABLE_LAYERS`, dan penolakan itu
   harus tetap disebut alih-alih dilewati diam-diam.
```

## 2. Urutan kerja yang diharapkan

```mermaid
flowchart TD
  A[Jam NY lewat app/clock<br/>plus kuarter day/session/micro/nano] --> B[Korelasi XAU<br/>1h, 15m, 5m]
  B --> C[Draw penuh per simbol<br/>15m dan 30m]
  C --> D[Quarterly: DFR, profil, manipulasi<br/>plus ekstrem tiap kuarter]
  D --> E[News: event di DEPAN, cek Week.error]
  E --> F[Kandidat lolos gerbang<br/>per simbol, bukan basket]
  F --> G[Hitung target 1:2<br/>entry +/- 2 x risiko]
  G --> H[Empat pemeriksaan pra-kirim]
  H --> I[Kirim, lalu verifikasi independen]
```

## 3. Pending limit lawan market, dan kenapa batasnya bukan selera

Pending limit BUKAN default karena kehati-hatian. Ia default karena populasi
yang seluruh angka di project ini dihitung padanya adalah SENTUHAN PERTAMA, dan
sebuah limit yang duduk di garis proksimal terisi tepat pada sentuhan pertama
itu. Order pending adalah cara menangkap event yang diukur, bukan versi
konservatif dari market order.

`tools/execute.py` baris 343 membuang setiap zona yang `first_test_time`-nya
terisi, dan docstring-nya menyatakan alasannya apa adanya: "the measured
population is a FIRST touch, so a zone price has already visited is not a member
of it and its number does not apply."

Jadi ketiga keadaannya berbeda, dan hanya dua di antaranya diukur:

| Keadaan harga | Jenis order | Status populasi |
|---|---|---|
| Belum menyentuh zona | **pending limit di proksimal** | anggota populasi yang diukur |
| Sedang menyentuh SEKARANG, belum ada bar tutup di dalam | **market boleh**, event-nya sama dengan pengisian limit | anggota, selama bar-nya belum tutup di dalam |
| Sudah ada bar TUTUP di dalam zona | market adalah trade lain | `first_test_time` terisi, BUKAN anggota |

`state` box menyatakan yang mana: `fresh` berarti belum ada sentuhan, `tested`
berarti harga masuk tapi tidak melewati ambang mitigasi, `mitigated` berarti
sudah dimakan melewatinya. `state` dihitung dari bar yang SUDAH TUTUP, jadi
sebuah box yang harganya baru masuk di bar yang masih terbentuk tetap `fresh`
sampai bar itu tutup.

### Kalau memilih market, tiga angka berubah

1. **Entry** jadi harga sekarang, bukan garis proksimal.
2. **Risiko per unit** jadi jarak harga-sekarang ke stop, yang untuk zona demand
   LEBIH KECIL daripada dari proksimal, karena harga sudah di dalam. R-nya
   membaik dan itu bukan keuntungan gratis: zonanya sudah sebagian terpakai.
3. **Target 1:2 ikut bergerak**, karena ia `entry +/- 2 x risiko` dan kedua
   sukunya berubah. Hitung ulang, jangan pakai target yang dihitung untuk entry
   proksimal.

### Yang harus dilaporkan saat memilih market

- `state` box-nya pada saat order, dan apakah ada bar tutup di dalamnya
- entry market, risiko per unit, dan target 1:2 yang DIHITUNG ULANG
- satu kalimat yang menyatakan trade ini masih anggota populasi terukur atau
  bukan, dan kalau bukan, bahwa angka-angka kalibrasi tidak berlaku untuknya

> [!WARNING]
> Jangan pakai `tools/execute.py --send` untuk market entry pada zona yang sudah
> tersentuh: jalur itu akan membuang zonanya di baris 343 dan tidak mengirim apa
> pun. Yang keluar bukan penolakan yang menjelaskan, melainkan zona yang hilang
> dari daftar kandidat tanpa suara.

## 3b. Layer mana yang boleh diorder, dan kenapa daftarnya cuma dua

Sampai 2 September 2026 jalur order tertutup untuk SETIAP detektor ICT, dan
tertutupnya karena dua sebab bertumpuk yang harus dibedakan.

**Sebab pertama, target.** `plan.build` mengambil target dari
`zone.profit_zone_rr`, field itu diisi `mark_profit_zones`, dan fungsi itu cuma
dipanggil di `detect/supply_demand.py` plus jalur refinement `drawing.py`.
Zona FVG, order block, IFVG dan breaker karena itu selalu `None`, dan
`execute.py` mensyaratkan target yang terbaca. Diukur di empat kombinasi
simbol-timeframe: 7, 10, 4 dan 8 zona ICT lolos gerbang DAN masih fresh, NOL
punya target. Sudah ditutup.

**Sebab kedua, dan ini yang mengikat.** `candidates()` memanggil
`DETECTORS["supply_demand"]` dan tidak punya cara memilih yang lain. Menutup
sebab pertama tidak mengubah apa pun sendiri: zona ICT punya target sekarang dan
tetap tidak masuk loop-nya. `--layer` yang membukanya.

| layer | boleh diorder | angka rig berbiaya (1h dan 4h) |
|---|---|---|
| `supply_demand` | ya, default | -0,0153 R di atas gerbang, selisih +0,1105 t=+7,19 |
| `order_block` | ya, lewat `--layer order_block` | -0,0429 R di atas gerbang (t sendiri -6,21), selisih +0,0764 t=+6,95, 17 dari 18 sel |
| `fvg` | TIDAK | gerbang TERBALIK, selisih -0,1005 t=-4,48, 3 dari 17 sel |
| `ifvg`, `breaker` | TIDAK | belum pernah lewat rig berbiaya sama sekali |

> [!WARNING]
> Tidak satu pun dari ketiganya positif sendiri di rig itu. Gerbang yang
> memisahkan dua populasi yang keduanya kalah tidak memberi trade, ia memberi
> urutan kekalahan. Dan seluruh tabel itu diukur di 1h dan 4h, bukan di
> timeframe yang order-nya dipasang.

Per sel untuk dua instrumen yang benar-benar ditradingkan, `order_block` di atas
gerbang: XAUUSD 1h +0,0661 (t=+1,94), XAUUSD 4h **-0,0720 dengan t=-2,51**,
BTCUSD 1h +0,0045, BTCUSD 4h -0,0311. Campur, dan yang paling negatif signifikan
justru XAU.

### Dan di 30 menit angkanya BERBEDA, karena tabel di atas bukan 30 menit

Setiap sel di tabel itu diukur di 1 jam dan 4 jam. Order dipasang di 30 menit.
`tools/lowtf_costed.py` menutup lubang itu: dua sel yang benar-benar
ditradingkan, XAUUSD dan BTCUSD 30m, dengan biaya, bar halus 5 menit, ambang
Bonferroni 2,498 untuk empat kelompok yang dinilai.

| detektor, 30m | exp atas gerbang | t lawan nol | selisih | welch t | walk-forward |
|---|---|---|---|---|---|
| supply_demand | **+0,1125 R** | +3,07 | +0,2109 | +5,24 | 7 dari 8 |
| order_block | **+0,0858 R** | +4,99 | +0,1192 | +4,52 | 8 dari 8 |

Keduanya lolos H1 dan H2 di 30 menit, sementara keduanya negatif di 1 jam. Itu
populasi tradeable positif pertama di repo ini, dan itu sekaligus alasan untuk
memeriksanya lebih keras.

**Kontrol resolusinya membatalkan separuhnya.** Bar halus 30m adalah 5 menit,
rasio 6, TERKASAR di tabel `FINER`, sementara rig 1 jam memakai rasio 12. Di
project ini resolusi sudah pernah membalik jawaban: edge +0,2 R jadi -0,0153 R
saat diukur halus. `tools/lowtf_resolution.py` menjalankan 30 menit dengan bar
1 MENIT, rasio 30, pada rentang bar-kasar yang SAMA supaya yang dibandingkan
resolusi dan bukan periode.

| sel | exp atas, rasio 6 | exp atas, rasio 30 | selisih, rasio 6 | selisih, rasio 30 |
|---|---|---|---|---|
| supply_demand XAU | +0,1110 | **+0,0549** | +0,1981 | +0,1614 |
| supply_demand BTC | +0,0809 | **+0,0359** | +0,2243 | +0,1889 |
| order_block XAU | +0,0701 | **+0,0107** | +0,1571 | +0,1252 |
| order_block BTC | +0,0576 | **-0,0031** | +0,2133 | +0,1921 |

Dua hal terpisah, dan jawabannya berbeda:

- **Daya pisah gerbang bertahan.** Selisih atas-bawah tetap positif di keempat
  sel di rasio 30. Gerbang departure 2,0 ATR memang memisahkan.
- **Ekspektasi absolut di atas gerbang tidak.** Ia menyusut di keempat sel,
  satu arah. `supply_demand` mempertahankan tanda positifnya, `order_block`
  kehilangannya.

> [!IMPORTANT]
> Ini jawaban terukur untuk "kenapa harus supply demand". Bukan karena ia
> detektor favorit, dan bukan karena ICT lebih lemah sebagai metode. Karena di
> 30 menit, edge `order_block` justru bagian yang dimakan resolusi, dan
> `supply_demand` yang tidak. Dan pada jendela pendek yang dipakai kontrol itu
> tidak satu pun t lawan nol yang signifikan di kedua resolusi, maksimum +1,363,
> jadi yang dinyatakan di sini ARAH penyusutannya dan tandanya, bukan bahwa
> +0,0549 R sudah terbukti di atas nol.

### Filter CISD-di-dalam-block, pemisahan terkuat yang tidak bisa dipasang

`--no-cisd-in-band` ada di `tools/execute.py` dan defaultnya mati. Pemisahannya
sendiri yang terkuat di repo ini: order block yang memuat level CISD baru
(dalam 50 bar) di dalam band-nya menghasilkan -0,1119 R, tanpanya +0,0244 R,
delta -0,1363 dengan Welch t = -7,07 lawan kritis 2,24 di n=8.170, dan KEDELAPAN
fold walk-forward bertanda sama. Confound efficiency dicek terpisah: -0,1618 di
dalam sel choppy, -0,1324 di dalam clean.

Yang membuatnya tidak terpasang: studinya mengevaluasi kondisinya di **bar
sentuhan**, jalur order berdiri di **bar keputusan**. Sebuah CISD yang lahir
dalam 50 bar duduk dekat harga sekarang, sementara zona yang masih `fresh`
justru yang harga belum datangi. Diukur XAUUSD 30m 2 September 2026: 4 CISD baru
di 4304-4360 dengan harga 4358, 20 order block fresh lolos gerbang di 3991-4139,
NOL persinggungan. Buang batas kebaruannya dan 18 dari 20 kena, yang persis
kondisi degenerate 95 persen yang studinya tolak.

Jadi angka +0,0244 R itu BELUM terpasang, dan flag itu tidak boleh dilaporkan
seolah sudah. `cycle` mencetak saat filter diminta dan tidak mengikat, karena
gerbang yang menyaring nol terbaca sama dengan gerbang yang menyaring.

## 4. Command yang menghasilkan angkanya

| Yang dicari | Command |
|---|---|
| Jam NY plus kuarter | `app.clock.to_ny` dan `app.quarters.quarters` di keempat degree |
| Killzone aktif | `app.pools.killzones_at(epoch)` |
| Korelasi | `app.aligned.load_aligned` lalu `app.correlation.correlations` |
| Semua layer | `POST /api/draw` dengan daftar layer penuh |
| DFR, profil, manipulasi | field `checklist` di response `/api/draw` |
| Ekstrem tiap kuarter | `app.quarterly.profile` plus `manipulation_done` per cycle |
| News di depan | `app.news.read()` lalu saring `e.time > now` |
| Kandidat lolos gerbang | `python -m tools.execute --symbol <satu> --interval 15m` |
| Advisor per zona | field `advice` di response `/api/draw` |
| Akun, posisi, pending | `MetaTrader5.account_info`, `positions_get`, `orders_get` |

Layer yang WAJIB dikirim parameternya, karena tanpa itu keempatnya menggambar
nol dan terlihat seperti layer rusak:

```json
{
  "dfr":      {"degrees": ["day", "session"]},
  "session":  {"quarters": ["day", "session", "micro"],
               "true_opens": ["day", "session"]},
  "checklist": {"ssmt_symbols": ["XAGUSD"], "ssmt_degrees": ["day"]}
}
```

`ssmt` dan `psp` membaca divergensi LINTAS instrumen, jadi tanpa partner
keduanya benar-benar tidak punya apa pun untuk digambar. Diukur 2 September
2026 di XAUUSD 1h 900 bar: ssmt 0 objek, smt 0, psp 0.

## 5. Empat pemeriksaan pra-kirim, dan kenapa masing-masing ada

### 5.1 Saklar auto-trade bisa menyala di atas daemon yang mati

```bash
cat backend/.autotrade.json
```

Periksa `daemon_pid` benar-benar ada di daftar proses. Pada 2 September 2026
`enabled: true` dengan `daemon_pid: 25920` yang **tidak ada**, dan heartbeat
`last_seen` sudah 44,9 jam basi sementara `updated_at` baru 2 jam. Konsekuensinya
dua arah: `tools/mt5_backtest.py:guard_daemon` memblokir setiap tool pengukuran,
dan tidak ada yang menjaga akun.

### 5.2 Lot minimum bisa melanggar anggaran risiko

XAUUSD `trade_contract_size` 100, jadi lot minimum 0,01 pada stop selebar 13
poin sudah berisiko 13 USD. Di akun 1000 USD itu 1,3% dalam satu trade, dan
pada kandidat berstop lebar ia mencapai 35 USD alias 3,5%.

Diukur 2 September 2026: pada risiko 1%, **nol dari tujuh** kandidat XAU 1h bisa
dipasang. Engine melaporkannya dengan benar - "dinaikkan ke lot minimum justru
melanggar batas risikonya sendiri" - dan yang salah adalah menganggap nol
kandidat berarti nol setup.

### 5.3 Journal mengunci zona atas ticket yang sudah dibatalkan

Journal append-only dan pemeriksaannya "sudah pernah diorder". Ia TIDAK
membedakan placed-dan-hidup dari placed-dan-dibatalkan. Pada 2 September 2026
empat zona BTC terkunci atas ticket 4626368007-010, keempatnya `state=2`
(canceled) sejak 30 Agustus. Periksa `history_orders_get(ticket=...)` sebelum
menyimpulkan sebuah zona memang sudah dipegang.

### 5.4 Cap portofolio berlaku PER PASS, dan urutannya alfabetis

`tools/execute.py:by_method_ranked` mengurutkan `(symbol, zone.id)`, jadi
"BTCUSD" selalu mendahului "XAUUSD". Di run basket dengan 6 slot, keenamnya
habis di BTC dan XAU tidak pernah dilihat sama sekali.

> [!WARNING]
> Jalankan **satu simbol per pass** untuk melihat kandidatnya, lalu jumlahkan
> risikonya sendiri terhadap cap 6%. Basket gabungan akan menyembunyikan
> kandidat simbol kedua.

Dan sizing ke anggaran risiko memakan cap jauh lebih cepat daripada lot
minimum: dua order BTC yang di lot minimum berisiko 4,25 dan 4,90 USD memakan
59,21 dari cap 60,01 begitu di-size ke 3%.

## 6. Yang harus muncul di jawabannya

- [ ] Jam UTC dan New York, plus kuarter di keempat degree dan sisa menitnya
- [ ] Killzone yang aktif dan kapan yang berikutnya mulai
- [ ] Korelasi XAU lawan BTC di tiga timeframe, plus partner terketat
- [ ] Per simbol: hitungan detector, box yang memuat harga, gerbang yang lolos
- [ ] Per simbol: DFR, profil AMDX/XAMD, status manipulasi, ekstrem tiap kuarter
- [ ] Level terdekat, dan mana yang MASIH BERDIRI lawan sudah ditembus
- [ ] Event news di DEPAN dengan jarak menitnya, plus catatan kalau feed gagal
- [ ] Tabel order: entry, SL, TP 1:2, risiko dalam USD dan persen equity
- [ ] Jenis order per baris (pending limit atau market) plus `state` box-nya,
      dan untuk market: target 1:2 yang sudah dihitung ulang
- [ ] Kriteria yang MENYELEKSI tiap order, dipisah dari layer yang cuma dibaca
- [ ] Empat pemeriksaan pra-kirim, masing-masing dengan hasilnya
- [ ] Verifikasi independen order book setelah kirim
- [ ] Layer yang menyeleksi, plus timeframe populasi angkanya diukur, plus
      kalimat kalau itu ekstrapolasi
- [ ] Satu kalimat tentang apa yang angka-angka itu TIDAK katakan

## 7. Dua hal yang bergantung timeframe, dan sering disalahbaca

**`manipulation_done` bergantung lebar fraktal.** Ia memanggil
`structure.breaks(candles, n, n)` dengan `n=2`, sementara layer `structure` di
API memakai `StructureParams` yang berbeda. Pada 2 September 2026 pukul 11:57
UTC harga XAU sudah menembus high Q2 sebesar 1,226 poin, layer `structure`
sudah melaporkan `SWEEP +1`, dan `manipulation_done` masih BELUM - karena bar
yang mencetak high itu adalah bar terakhir dan sebuah swing fraktal butuh 2 bar
di kanannya untuk confirmed.

Konsekuensinya: flag manipulasi bisa BELUM di 15m dan SUDAH di 1h pada instrumen
dan cycle yang sama. Itu bukan bug, itu knob, dan docstring-nya menyatakan
`n` adalah knob bukan angka dari sumber mana pun.

**Dan ia hanya menghitung SWEEP, bukan CHoCH.** `app/quarterly.py:390`
menyaring `event.kind != "SWEEP"`, jadi sebuah CHoCH di kuarter manipulasi
TIDAK menyalakan flag itu betapa pun jelasnya di chart. Ini terpisah dari lebar
fraktal di atas, dan gampang tertukar dengannya: yang pertama soal KAPAN sebuah
swing confirmed, yang kedua soal JENIS event apa yang dihitung. Pada 2 September
2026 saya salah menjelaskan flag XAU yang belum menyala sebagai lag konfirmasi;
sebabnya yang benar adalah event Q3-nya CHoCH, bukan SWEEP.

**`gaps` dan `event_horizons` kosong di instrumen 24/7.** BTC tidak pernah tutup,
jadi ia tidak punya interval tanpa perdagangan dan tidak punya opening gap. Nol
di situ adalah gambar yang BENAR, bukan layer yang gagal.

## 7b. Tiga hal di jalur order yang berubah 2 September 2026

Sesi yang membaca dokumen ini sebelum tanggal itu akan salah pada ketiganya.

**Slot order tidak lagi ditentukan abjad.** `by_method_ranked` mengembalikan
`(symbol, zone.id)` dan `cycle` memotong daftarnya di `max_orders`, jadi
"BTCUSD" mendahului "XAUUSD" dan KEDUA slot daemon selalu jatuh ke BTC. Diukur:
BTC punya 9 kandidat di 30m dan 10 di 15m, jadi ambang "BTC punya kurang dari
dua" tidak pernah tercapai dan XAU tidak akan pernah diorder daemon.
`round_robin` menghapus prioritas itu. Ia BUKAN kunci seleksi: tujuh kandidat
kunci urut sudah dipraregistrasi di `tools/order_key.py` dan tidak satu pun
memisahkan hasil.

**"SUDAH pernah diorder" sekarang bisa dipercaya.** Gate idempotensi menyaring
`event == "placed"` saja, dan tidak ada apa pun yang membatalkan sebuah
`placed`, jadi zona yang order-nya sudah dibatalkan tetap ditolak SELAMANYA.
Diukur: 35 zona punya record `placed`, gate lama mengunci 35, dan cuma 6
ticket yang masih hidup di broker. Sekarang dua sumber dipakai, dan angkanya
menunjukkan kenapa keduanya perlu: pengetahuan journal sendiri melepas 2 saja
karena 16 ticket hilang dari broker tanpa pernah tercatat di sini, dan
pemotongan lewat order book membawanya dari 33 ke 6. 29 zona terlepas.

**Cek cap harus membandingkan TERKOMITMEN plus BARU.** Sebuah script yang
membandingkan risiko order baru saja lawan cap akan meloloskan order yang
membawa total melewatinya, sambil melaporkan angka yang terlihat kecil.
`tools/execute.py` sudah benar soal ini lewat `Book`, dan ia juga mencetak
"POSISI TERBUKA TIDAK TERBACA, jadi ini LANTAI" saat terminalnya tidak
menjawab. Script ad-hoc yang ditulis di dalam sesi tidak otomatis benar, dan
yang ini pernah salah.

## 8. Batas yang harus disebut, bukan disembunyikan

Yang terukur positif di rig ARAH ada tiga: `fvg` (+10 sampai +25 poin lawan
placebo, walk-forward 8/8), `order_block` (rig sama, hasil sama), dan box
`supply_demand` mengalahkan tanpa-box (8/8, t = +4,28).

> [!IMPORTANT]
> Ketiga angka itu dari rig ARAH, poin lawan placebo, dan bukan dari rig R
> teresolusi berbiaya. Di rig kedua jawabannya berbeda untuk salah satunya:
> `fvg` GAGAL negatif dan signifikan, -0,1005 R dengan t=-4,48, artinya gerbang
> departure-nya terbalik. Satu detektor bisa memenangkan pertanyaan arah dan
> kalah pertanyaan trade, dan yang menentukan order adalah yang kedua. Lihat
> bagian 3b.

Enam layer terukur NULL, dua terukur NEGATIF signifikan sebagai klaim arah
(`ifvg`, `breaker`), satu dari tujuh belas klausa checklist memisahkan dan ia
memisahkan ke arah SEBALIKNYA (`dfr_side`, t = -3,543), dan skor agregat
checklist tidak memisahkan sama sekali. Rinciannya di
[QA-DETEKTOR.md](QA-DETEKTOR.md) bagian 11 sampai 15.

Jadi sebuah pending order di Zonelab adalah pernyataan tentang LOKASI dan JAM.
Tidak ada satu angka pun di repo ini yang mengatakan harga akan datang ke situ,
atau ke mana ia pergi sesudahnya. Advisor bawaan engine menutup setiap zona
dengan kalimat itu, dan jawaban sesi tidak boleh melampauinya.

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)
