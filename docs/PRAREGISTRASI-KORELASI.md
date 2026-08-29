# Praregistrasi: korelasi partner sebagai pengkondisi, 29 Agustus 2026

> [!IMPORTANT]
> Dokumen ini ditulis **sebelum satu angka pun dihitung**. Tidak ada hasil di
> dalamnya saat ia di-commit. Bagian 7 sengaja kosong sampai run-nya selesai.

## 1. Kenapa studi ini ada

`docs/AUDIT-MENYELURUH.md` bagian 8 menyebut satu gap yang tidak punya angka
sama sekali:

> Korelasi partner sebagai pengkondisi belum pernah diuji. `app/conditions.py`
> sengaja bebas IO dan harness-nya membaca satu deret, jadi pertanyaan "apakah
> SSMT lebih berguna saat partner-nya benar-benar berkorelasi" tidak punya
> angkanya.

Pertanyaan itu bukan karangan auditor. Ia tersirat di docstring `app/ssmt.py`
sendiri, yang menyatakan laju SSMT "tracks correlation exactly": emas lawan
perak berdivergensi di 14,9 persen pembacaan, lawan DXY di 59,5 persen. Kalau
laju divergensi memang ditentukan korelasi, maka NILAI sebuah divergensi juga
mungkin ditentukan olehnya, dan itu belum pernah diperiksa.

Ada alasan kedua yang lebih praktis. `app/portfolio.py` memakai korelasi
sebagai **penjaga risiko** dengan ambang `corr_max = 0.70`, angka yang dipilih
dan bukan diukur. Kalau korelasi ternyata memisahkan hasil, ambang itu punya
kandidat dasar empiris. Kalau tidak, ia tetap boleh ada sebagai pengaman, tapi
tidak boleh dipromosikan jadi sinyal.

## 2. Yang sudah gagal, supaya tidak diulang

| Sudah diuji | Hasil |
|---|---|
| SSMT sebagai sinyal arah | akurasi 51,1 / 50,9 / 47,1 persen lawan null 50 persen |
| SSMT dikondisikan volatilitas | gerbang menyala 0,4 persen waktu, tanda berbalik dengan lebar bracket |
| Sebelas hipotesis arah lain | semuanya nol, lihat `docs/CALIBRATION.md` |
| Lima kolom modul yatim | nol dari lima, lihat `docs/PRAREGISTRASI-YATIM.md` |

Studi ini **bukan** SSMT diuji ulang. Yang diuji adalah kolom pengkondisi baru
di atas populasi trade yang sama seperti praregistrasi sebelumnya, yaitu
sentuhan pertama tiap zona yang lolos gerbang.

## 3. Kolom yang diuji, daftar TERTUTUP

Satu kolom. Menambah kolom setelah melihat hasil menuntut praregistrasi baru
bertanggal baru, aturan yang sama dengan tiga dokumen praregistrasi sebelumnya.

```
CORRELATION_COLUMNS = ("partner_corr_band",)
```

### Definisi `partner_corr_band`

Nilai absolut korelasi Pearson atas **log return** antara simbol chart dan
partner SSMT-nya, dihitung pada bar yang berakhir di bar keputusan trade,
lalu dimasukkan ke pita.

Tujuh keputusan definisi, semuanya ditetapkan sekarang:

1. **Log return, bukan harga.** Dua deret yang sama sama trending berkorelasi
   0,9 tanpa alasan selain sama sama trending. `app/correlation.py` sudah
   memakai log return dan alasannya tertulis di sana; studi ini memakai fungsi
   yang sama, bukan implementasi kedua.
2. **Nilai ABSOLUT.** SSMT adalah soal divergensi antara instrumen yang
   bergerak bersama, dan pasangan di -0,85 sama terkopelnya dengan pasangan di
   +0,85. Menguji korelasi bertanda akan mencampur "seberapa terkopel" dengan
   "ke arah mana", yaitu dua pertanyaan.
3. **Jendela 200 bar**, diakhiri di bar keputusan. Dipilih sebagai jendela yang
   sama dengan `_VOLUME_BASELINE_BARS` di `app/detect/supply_demand.py`, jadi
   ia konvensi repo ini dan bukan angka baru. Bukan hasil pencarian.
4. **Grid hasil irisan ketat**, tanpa fill dan tanpa interpolasi, lewat
   `app/aligned.load_aligned`. Korelasi atas lubang yang diisi maju adalah
   korelasi dengan data karangan di dalamnya.
5. **Minimal 30 pasang return**, mengikuti `correlation.MIN_PAIRS`. Di bawah
   itu nilainya `unknown`, dan `unknown` adalah pita tersendiri, bukan nol dan
   bukan dibuang.
6. **Partner diambil dari pasangan SSMT bawaan simbolnya**, bukan dipilih per
   run. Untuk `mt5:XAUUSD` partnernya `mt5:XAGUSD`. Memilih partner setelah
   melihat hasil adalah pencarian yang menyamar jadi replikasi.
7. **Anti-lookahead.** Korelasi dihitung dari bar yang berakhir di bar
   keputusan, tidak termasuk bar sesudahnya. Ini disyaratkan sama seperti tiap
   pengkondisi lain di `app/conditions.py`, dan harus dibuktikan dengan test
   yang menyuntikkan bar masa depan lalu memastikan angkanya tidak berubah.

### Pita, ditetapkan sekarang

```
"<0.30"        korelasi lemah
"0.30-0.60"    sedang
"0.60-0.80"    kuat
">=0.80"       sangat kuat
"unknown"      kurang dari 30 pasang return
```

Batas pita dipilih supaya `0.70`, ambang penjaga portofolio yang sudah ada,
jatuh di DALAM pita `0.60-0.80` dan bukan di tepinya. Batas yang jatuh persis
di ambang yang sedang dipertimbangkan akan membuat hasilnya bergantung pada
sisi mana angka itu dibulatkan.

## 4. Syarat lulus, ketiganya sekaligus

Sama persis dengan `docs/PRAREGISTRASI-KONDISI.md` dan
`docs/PRAREGISTRASI-YATIM.md`. Tidak ada yang dilonggarkan.

1. `n >= 30` per pita. Di bawah itu pita dicetak dengan n-nya dan tidak dinilai.
2. `|t|` Welch melewati nilai kritis dua sisi terkoreksi Bonferroni, dengan
   alpha 0,05 dibagi K, di mana K adalah jumlah pita yang layak dinilai di
   SELURUH run. K dihitung dan dicetak **sebelum** satu baris hasil pun keluar.
3. Tanda sama di kedua paruh, dan paruhnya dipotong menurut **waktu**
   (`cut = rows[len(rows)//2]["at"]`), bukan menurut jumlah anggota. Memotong
   menurut jumlah anggota menanyakan pertanyaan yang berbeda dan lebih longgar.

Lolos ketiganya berhak atas walk-forward. Ia **tidak** berhak dikirim, dan
tidak berhak masuk `--require`.

## 5. Yang membatalkan studi ini

Ditulis sekarang supaya tidak bisa dirasionalkan nanti.

- Kalau `unknown` melebihi 20 persen populasi, jendela 200 bar terlalu panjang
  untuk data yang ada dan hasilnya dilaporkan sebagai tidak dapat diukur, bukan
  sebagai nol.
- Kalau satu pita memuat lebih dari 80 persen populasi, kolom ini tidak
  memisahkan apa pun secara konstruksi dan itu dilaporkan apa adanya.
- Kalau test anti-lookahead gagal, seluruh run dibuang. Angka dari kolom yang
  melihat masa depan bukan angka yang lebih lemah, ia angka yang salah.

## 6. Yang TIDAK dijanjikan

- Ini satu instrumen, satu partner, satu timeframe. Nol di sini bukan nol di
  mana mana, pelajaran yang sudah dibayar dua kali di repo ini.
- Sebuah hasil positif tidak akan mempromosikan `corr_max` dari pengaman jadi
  sinyal. Ia hanya akan memberi kandidat dasar empiris untuk ambang yang
  sekarang dipilih.
- Populasi trade-nya sama dengan praregistrasi sebelumnya, jadi ia mewarisi
  batas yang sama: angka ekspektansinya dihitung dengan konvensi intrabar yang
  menggelembungkan, kecuali dijalankan lewat lengan yang sudah dikoreksi.

## 7. Hasil

Belum dijalankan. Bagian ini diisi setelah run-nya selesai, dan diisi apa
adanya termasuk kalau jawabannya nol.

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
