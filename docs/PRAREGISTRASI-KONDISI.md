# Praregistrasi studi pengkondisian, 21 Agustus 2026

Dokumen ini ditulis **sebelum** satu angka pun dihitung. Itu satu-satunya hal
yang membuat hasilnya layak dipercaya nanti, dan itu juga alasan dua belas
kegagalan hipotesis arah di project ini bisa dipercaya.

> [!IMPORTANT]
> Kalau sebuah kolom tidak ada di daftar Bagian 3, ia tidak boleh dilaporkan
> sebagai temuan. Menambahkan kolom setelah melihat hasil adalah cara tercepat
> menghasilkan temuan palsu, dan `formation_score` dengan AUC 0,464 dan 0,477
> adalah bukti bahwa repo ini pernah kena.

## 1. Pertanyaannya

Gerbang departure sudah terukur: pada `mt5:XAUUSD` 1 jam, 50.000 bar, biaya
Exness Zero, populasi first touch yang lolos gerbang memberi **+0,198 R** (n=953,
t=5,10, 8 dari 8 fold positif setelah purging, p=0,0078).

Pertanyaan studi ini bukan apakah angka itu ada. Pertanyaannya: **apakah ada
state layer pada bar sentuhan yang memisahkan angka itu**, sehingga sebagian
populasi membawa ekspektasi lebih tinggi dan sebagian lebih rendah.

## 2. Populasi dan outcome, keduanya sudah ada

| Hal | Nilai |
|---|---|
| Instrumen | `mt5:XAUUSD`, spot CFD broker |
| Timeframe | 1 jam, dan 15 menit sebagai replikasi |
| Bar | 50.000 |
| Populasi | first touch tiap zona `supply_demand` yang `departure_atr >= 2.0` dan punya target terbaca, dua sisi dipool |
| Entry | proximal, spread dibebankan ke fill |
| Stop | distal plus buffer 0,25 ATR, dipicu wick |
| Target | opposing zone hidup terdekat |
| Exit | flat di rollover 21:00 UTC (aturan yang menang, +0,221 R lawan +0,198 R) |
| Outcome | R multiple setelah komisi 0,25 bp, slippage 0,5 bp, spread terukur per bar, swap per sisi, dan admin fee 4,545 bp per malam |
| Biaya | `--broker exness_raw` |

Tidak ada satu pun dari baris di atas yang dipilih untuk studi ini. Semuanya
sudah dipakai oleh angka +0,198 R itu sendiri.

## 3. Kolom yang akan diuji, daftar tertutup

Dihitung oleh `app/conditions.at_bar` pada bar sentuhan, memakai **hanya** bar
sampai bar itu. Properti anti-lookahead-nya diuji sebagai kesamaan di
`tests/test_conditions.py`.

| Kolom | Nilai yang mungkin | Alasan diuji |
|---|---|---|
| `weekday` | 0 sampai 6 | sudah terlihat memisahkan: Senin +0,276 sampai Jumat +0,128 pada aturan hold |
| `hour_utc` | 0 sampai 23 | jam sesi, dilaporkan sebagai tabel dan **tidak** diranking, karena AUC pada variabel siklik tidak bermakna |
| `quarter_day` | Q1 sampai Q4 | Quarterly Theory menaruh perilaku berbeda per kuartal |
| `quarter_session` | Q1 sampai Q4 | derajat di bawahnya, klaim yang sama |
| `amd_profile` | AMDX, XAMD, None | profile menentukan kuartal manipulasi |
| `in_manipulation_quarter` | True, False, None | separuh waktu dari konjungsi manipulasi |
| `manipulation_done` | True, False, None | separuh harga dari konjungsi yang sama |
| `range_band` | premium, discount, equilibrium, at_or_above_high, at_or_below_low | doktrin menuntut sell di premium dan buy di discount |
| `dfr_pos` | pita, dibagi kuartil populasi | posisi relatif defining range |
| `bias_1d` | -1, 1, None | H7 mengukur bias sebagai variabel arah dan gagal; di sini ia diuji sebagai pengkondisi outcome R, bukan sebagai arah |
| `bias_4h` | -1, 1, None | sama |
| `bias_1h` | -1, 1, None | sama |

`bias_15m` **tidak** diuji: ia tidak bisa dibangun dari seri 1 jam, jadi nilainya
selalu None dan itu bukan pengukuran.

## 4. Ambang, ditetapkan sekarang

Sebuah kolom hanya dilaporkan sebagai memisahkan kalau **ketiganya** lolos:

1. **Ukuran sampel.** Tiap grup minimal `n = 30`. Grup di bawah itu dicetak
   dengan `n`-nya dan tidak dinilai.
2. **Koreksi banyak-perbandingan.** Dengan `K` grup yang layak dinilai, alpha
   dua sisi 0,05 dibagi `K` (Bonferroni). Untuk perkiraan 58 grup pada daftar di
   atas, itu alpha 0,00086 dan `|t| >= 3,34`. Angka `K` yang sebenarnya dihitung
   dan dicetak oleh tool, jadi ambangnya tidak bisa dipilih setelah melihat
   hasil.
3. **Konsistensi waktu.** Tanda selisihnya bertahan pada kedua paruh sampel.

Kalau sebuah kolom lolos ketiganya, langkah berikutnya adalah walk-forward
delapan fold dengan purging pada subpopulasi itu, bukan pengiriman.

## 5. Yang tidak akan dilakukan

- **Tidak menjumlahkan kolom.** Kalau dua kolom lolos, keduanya dilaporkan
  berdampingan. Skor gabungan adalah persis bentuk `formation_score`, dan ia
  memeringkat terbalik.
- **Tidak menambah kolom setelah melihat hasil.** Daftar Bagian 3 tertutup.
  Kolom baru berarti praregistrasi baru dengan tanggal baru.
- **Tidak menghapus grup yang mengganggu.** Grup dengan `n` kecil dicetak apa
  adanya, tidak disembunyikan.
- **Tidak menyatakan arah.** Studi ini mengkondisikan outcome R dari populasi
  yang arahnya sudah ditentukan oleh sisi zona. Ia tidak menjawab ke mana harga
  pergi.

## 6. Yang sudah diketahui akan jarang menyala

Diukur pada 300 bar sampel `mt5:XAUUSD` 1 jam sebelum studi dijalankan, sekadar
untuk tahu kolom mana yang punya variansi sama sekali:

| Kolom | Nilai unik | Nilai dominan |
|---|---|---|
| `weekday` | 6 | 21% |
| `hour_utc` | 23 | 5% |
| `quarter_day` | 4 | 26% |
| `quarter_session` | 4 | 35% |
| `amd_profile` | 3 | 53% (XAMD) |
| `in_manipulation_quarter` | 3 | 40% |
| `manipulation_done` | 3 | 50% (False) |
| `range_band` | 5 | 34% (equilibrium) |
| `bias_1d` | 2 | 56% |

`manipulation_done` True hanya 31 dari 300 bar sampel, jadi subpopulasinya pada
953 trade kemungkinan di bawah ambang `n = 30` dan akan dilaporkan sebagai
terlalu kecil. Itu dinyatakan sekarang supaya nanti bukan kejutan yang
menggoda untuk diakali.

---

## 7. Hasil, 21 Agustus 2026

Dijalankan `python -m tools.conditioned --symbol mt5:XAUUSD --interval 1h
--bars 50000`. Populasi n=953, ekspektasi +0,221 R, 52 grup layak dinilai, jadi
alpha 0,05/52 = 0,00096 dan `|t|` kritis **3,30**.

**Nol dari 52 grup memisahkan.** Yang terdekat, urut kekuatan:

| Kolom | Nilai | n | exp R | delta lawan sisanya | t | delta per paruh |
|---|---|---|---|---|---|---|
| `quarter_day` | Q3 | 437 | +0,320 | **+0,182** | +2,76 | +0,168 / +0,200 |
| `quarter_day` | Q4 | 130 | +0,054 | -0,193 | -2,76 | -0,136 / -0,245 |
| `in_manipulation_quarter` | True | 356 | +0,327 | +0,169 | +2,44 | +0,227 / +0,111 |
| `quarter_session` | Q1 | 232 | +0,104 | -0,155 | -2,31 | -0,140 / -0,173 |
| `hour_utc` | 12 | 88 | +0,471 | +0,275 | +2,25 | +0,354 / +0,171 |
| `bias_1h` | -1 | 463 | +0,290 | +0,133 | +2,01 | +0,133 / +0,133 |

> [!IMPORTANT]
> **Dua baris teratas bukan dua temuan.** Di bawah profile XAMD, kuartal
> manipulasi ADALAH Q3, dan 580 dari 953 trade ada di cycle XAMD. Jadi
> `quarter_day=Q3` dan `in_manipulation_quarter=True` sebagian besar kohort yang
> sama dilihat dari dua kolom. Menghitungnya sebagai dua bukti adalah cara
> tercepat melipatgandakan satu kebetulan.

### Koreksi pada tool, dan kenapa ia bukan pelanggaran praregistrasi

Run pertama tool ini menguji tiap grup lawan **nol**, bukan lawan sisa populasi.
Karena seluruh populasi sudah +0,221 R, hampir setiap grup besar otomatis
signifikan: run itu mencetak lolos pada **kedua** sisi `bias_1d`, yang tidak
mungkin merupakan pemisahan menurut pembacaan siapa pun.

Null yang benar untuk pertanyaan di Bagian 1 adalah komplemen grupnya, jadi
tesnya diganti ke Welch grup lawan sisanya dan angka di tabel atas berasal dari
run kedua. Yang diperbaiki adalah **implementasi yang tidak cocok dengan
pertanyaan yang sudah ditulis**, bukan pertanyaannya. Tidak ada kolom yang
ditambah, tidak ada grup yang dibuang, dan tidak ada ambang yang digeser: `|t|`
kritis tetap dihitung dari jumlah grup sebelum satu baris pun dicetak.

### Replikasi 15 menit, dan near-miss itu gugur

`--interval 15m --bars 50000`. Populasi n=1445, ekspektasi +0,202 R, 58 grup
layak dinilai, `|t|` kritis **3,33**. **Nol dari 58 grup memisahkan**, dan yang
lebih penting: kandidat dari 1 jam tidak muncul lagi.

| Kolom | Nilai | 1 jam: delta / t | 15 menit: delta / t | 15 menit: delta per paruh |
|---|---|---|---|---|
| `quarter_day` | Q3 | **+0,182 / +2,76** | **-0,007 / -0,12** | +0,039 / -0,053 |
| `quarter_day` | Q4 | -0,193 / -2,76 | -0,032 / -0,36 | -0,208 / +0,073 |
| `in_manipulation_quarter` | True | +0,169 / +2,44 | +0,018 / +0,29 | +0,069 / -0,033 |
| `hour_utc` | 12 | +0,275 / +2,25 | +0,159 / +1,45 | +0,122 / +0,211 |

Grup terkuat di 15 menit adalah `hour_utc` 15 pada |t|=2,40, dan ia tidak ada di
daftar terkuat 1 jam. Jadi kedua timeframe menghasilkan near-miss yang berbeda,
yang adalah tanda tangan kebetulan, bukan efek.

`quarter_day` Q3 turun dari +0,182 menjadi -0,007 dan tandanya berbalik antar
paruh di 15 menit. Kandidat itu gugur, dan tidak ada walk-forward yang perlu
dijalankan pada subpopulasinya.

## 8. Praregistrasi kedua: klausa checklist ICT, 21 Agustus 2026

Daftar di bagian 3 tertutup. Klausa checklist adalah pertanyaan **baru**, jadi
ia didaftarkan terpisah dengan tanggalnya sendiri dan hidup di `ICT_COLUMNS`,
bukan di `COLUMNS`. Menggabungkan keduanya akan menyembunyikan pertanyaan mana
yang diajukan sebelum ada angkanya.

Yang didaftarkan: sembilan klausa yang bisa diwajibkan lewat `--require`, plus
`poi_family_count` dan pita `ict_met`. Ambangnya sama dengan bagian 4, dan
koreksi Bonferroni dihitung ulang atas seluruh grup, bukan per daftar.

**Kolom kesepuluh ditambahkan 22 Agustus 2026: `htf_nested`.** Tanggalnya beda
karena pertanyaannya memang baru: nesting HTF sudah pernah diukur sebagai
variabel **arah** di H2 (`CALIBRATION.md`, p=0,33), dan di sini ia diuji sebagai
pengkondisi outcome R. Menambahkannya menaikkan grup yang dinilai dari 81 ke 83
dan `|t|` kritis dari 3,42 ke 3,43, dan angka itu dilaporkan bersama hasilnya.

### Hasil, dan nol yang keempat belas

Nol dari sepuluh klausa melewati 3,43. Tabel lengkapnya ada di
`ALUR-ORDER.md` bagian 3, dan tiga bacaan yang perlu dicatat di sini:

1. **`poi_clean` +0,176 (t=+2,46)** adalah pengkondisi terkuat yang pernah diukur
   di project ini, dan tandanya hampir identik di kedua paruh (+0,181 / +0,168).
   Tetap belum lolos ambang, jadi tetap tidak diwajibkan.
2. **`discount_or_premium` mengukur negatif** (-0,059), negatif di kedua paruh.
   Aturan inti doktrin tidak memisahkan di populasi ini.
3. **`htf_nested` +0,031 (t=+0,47), tanda berbalik antar paruh.** H2 mengukur
   nesting sebagai arah dan gagal; di sini ia gagal sebagai pengkondisi juga.

### Replikasi 15 menit, 22 Agustus 2026

n=1447, ekspektasi +0,202 R, 89 grup, `|t|` kritis 3,45, `|t|` terbesar 2,39.
Nol yang memisahkan. Satu klausa bertahan lintas timeframe dengan tanda dan
besaran yang sama, `poi_clean` (+0,176 / t=2,46 di 1 jam, +0,142 / t=2,27 di 15
menit, kedua paruh positif di keduanya). Dua dari tiga terkuat di 1 jam,
`killzone` dan `manipulation_quarter`, runtuh ke t=0,33 dan t=0,32 dengan tanda
berbalik antar paruh. Tabelnya di `ALUR-ORDER.md` bagian 3.

### Dua kolom yang sempat berbunyi seperti fakta pasar

`cisd_in_band` terbit False untuk semua 953 trade di run pertama karena harness
tidak pernah mengirim level CISD ke `poi.confluence`. Sehari kemudian
`htf_nested` melakukan hal yang sama, False untuk semua 953, karena harness tidak
me-resample satu derajat naik dan tidak memanggil `mark_nesting` seperti
`candidates()` melakukannya. Setelah keduanya disambungkan: 893 dan 497 True.

Pelajarannya bukan "periksa harness". Pelajarannya lebih sempit dan lebih pahit:
**satu kolom yang seragam False adalah keluhan, bukan temuan.** Keduanya lolos
ambang praregistrasi dengan mulus dan keduanya akan terbit sebagai temuan.

### Yang tetap belum diketahui

**Korelasi partner sebagai pengkondisi** belum diuji. SSMT sendiri sudah
tersambung ke jalur order sejak 22 Agustus 2026 (klausanya dijawab dari partner
di basket, lihat `ALUR-ORDER.md` bagian 1), tapi ia belum pernah masuk studi
pengkondisian: `app/conditions.py` sengaja bebas IO, dan harness ini membaca satu
deret. Itu praregistrasi berikutnya, bukan tambahan pada yang ini.

Jadi hitungannya sekarang: empat belas percobaan mengeluarkan arah atau
pengkondisian dari gambar ini, empat belas nol. Angka yang bertahan tetap hanya
gerbang departure dan aturan exit flat.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
