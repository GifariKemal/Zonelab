# Keempat detector di instrumen yang tidak ikut memilihnya, diukur 6 September 2026

Rig dua belas sel yang menopang setiap halaman `QA-*-GATE.md` memakai **dua**
instrumen, XAUUSD dan BTCUSD. Setiap angka di halaman-halaman itu adalah angka
dua instrumen tersebut, dan sampai hari ini tidak ada satu pengukuran pun yang
menanyakan apakah salah satunya berpindah.

Halaman ini menanyakannya. Ia lahir dari pertanyaan yang jauh lebih kecil, yaitu
apakah supply and demand boleh dibatasi ke 15m karena PF-nya terbaik di sana.

> [!IMPORTANT]
> Urutan detector di repo ini terbalik hampir seluruhnya di luar sampel. Yang
> paling jatuh adalah IFVG, yang paling kuat di rig. Yang paling bertahan adalah
> breaker dan supply and demand, dua yang paling lemah di rig.

## Hasilnya

15m, lima instrumen yang tidak pernah ikut memilih apa pun: EURUSD, GBPJPY,
USDJPY, XAGUSD, US30. Semuanya punya riwayat 1m di venue yang sama, jadi
diadili di resolusi halus persis seperti rig utamanya.

| detector | 15m di rig | 15m di luar sampel | exp_r | t | wf |
|---|---|---|---|---|---|
| ifvg | PF **1,634** | PF **0,842** | -0,0841 | **-4,125** | 1/8 |
| order_block | PF 1,294 | PF **0,856** | -0,0800 | **-3,381** | 1/8 |
| supply_demand, gerbang produksi | PF 1,121 | PF 0,930 | -0,0401 | -0,785 | 2/8 |
| breaker | PF 1,345 | PF **1,025** | +0,0141 | +0,499 | 4/8 |
| supply_demand, lengan L | - | PF **1,020** | +0,0122 | +0,229 | 5/8 |

**IFVG dan order block negatif SIGNIFIKAN** di luar sampel, t=-4,125 dan -3,381.
Breaker dan supply and demand tidak, dan keduanya praktis nol.

Perlakuannya sama di kedua sisi untuk tiap detector: ifvg, breaker dan
order_block diukur pada populasi tanpa gerbang di in-sample maupun out-of-sample;
supply and demand diukur dengan gerbang produksinya di keduanya. Jadi tiap baris
membandingkan hal yang sama dengan dirinya sendiri di instrumen berbeda.

## Yang menentukan tanda adalah INSTRUMEN, bukan detector

| instrumen | ifvg | order_block | breaker | S&D lengan L |
|---|---|---|---|---|
| **XAGUSD** | **+0,2107** | **+0,2068** | **+0,1737** | +0,0206 |
| US30 | -0,1475 | -0,1738 | +0,0274 | +0,0361 |
| USDJPY | -0,1870 | -0,1544 | +0,0361 | -0,0269 |
| EURUSD | -0,1153 | -0,1689 | +0,0020 | -0,1734 |
| GBPJPY | -0,1915 | -0,1125 | -0,1644 | +0,2052 |

XAGUSD positif untuk keempatnya, dan itu satu satunya instrumen yang begitu.
Bersama XAUUSD di rig, keduanya logam.

Rig kita berisi satu logam dan satu kripto. Kalau tanda hasil lebih ditentukan
kelas aset daripada metode, maka setiap angka di seluruh halaman QA adalah angka
logam-plus-kripto, dan itu belum pernah dinyatakan sebagai batasnya.

Perhatikan juga bahwa keempat detector bergerak BERSAMA per instrumen. Tiga dari
empat negatif di EURUSD, USDJPY dan US30; keempatnya positif di XAGUSD. Empat
konstruksi yang berbeda tidak sepakat sekuat itu karena metodenya mirip - mereka
sepakat karena yang mereka ukur sebagian besar adalah instrumennya.

## Cacat biaya yang ditemukan di jalan, dan yang mengungkapkannya

Run pertama memasukkan ETHUSD, dan ETHUSD adalah instrumen paling negatif untuk
**keempat** detector sekaligus: -0,3942 ifvg, -0,3834 order_block, -0,3113
breaker, -0,2903 S&D lengan L.

Empat metode berbeda tidak gagal dengan pola sekuat itu karena alasan yang sama,
kecuali penyebabnya bukan metodenya. Dan memang bukan:

| instrumen | commission_bp | slippage_bp |
|---|---|---|
| XAUUSD | 0,152 | 0,5 |
| BTCUSD | 0,899 | 0,5 |
| XAGUSD | 0,203 | 0,5 |
| US30 | 1,314 | 0,5 |
| **ETHUSD** | **20,0** | **2,0** |

ETHUSD tidak ada di `BROKERS["exness_raw"]` di `app/costs.py`, jadi `schedule()`
jatuh ke default generik ala bursa kripto: dua puluh dua kali lipat komisi
BTCUSD. Terminal MEMBAWA simbolnya, `history.load("mt5:ETHUSD", ...)` menjawab
99.998 bar, jadi ini celah tabel biaya dan bukan instrumen yang tidak ada.

ETHUSD dibuang dari kontrol ini sampai barisnya diturunkan dari terminal. Angka
di halaman ini semuanya TANPA ETHUSD.

## Batasnya, dinyatakan bukan dikubur

**Riwayat 1m di terminal ini sekitar 69 hari.** Tiap sel di sini karena itu jauh
lebih pendek daripada sel rig: n per instrumen 140 sampai 232 untuk supply and
demand, dan 564 sampai 961 untuk tiga detector lain. Cukup untuk menolak sebuah
klaim, tidak cukup untuk menegakkan yang baru.

**Hanya 15m.** Timeframe lain butuh riwayat halus yang tidak dimiliki keenam
instrumen ini di kedalaman yang sama.

**Jendelanya satu periode, bukan walk-forward antar rezim.** Kolom wf di tabel
pertama adalah fold posisi relatif di dalam jendela pendek itu.

Jadi halaman ini TIDAK menyatakan bahwa keempat detector tidak punya edge. Ia
menyatakan sesuatu yang lebih sempit dan lebih kuat: **angka yang diterbitkan di
rig dua instrumen tidak berpindah ke lima instrumen lain di timeframe yang
sama**, dan untuk dua detector penurunannya signifikan.

## Kenapa ini penting untuk pertanyaan yang menyebabkannya

Pertanyaan aslinya: bolehkah supply and demand dibatasi ke 15m, karena PF 1,377
di sana adalah angka tertinggi di seluruh sapuannya.

Tiga jawaban, dan yang ketiga adalah halaman ini. Rinciannya di
`docs/QA-SD-GATE.md`. Yang halaman ini tambahkan: memilih timeframe terbaik
adalah masalah yang sama dengan memilih instrumen terbaik, dan rig ini punya dua
instrumen.

Satu hal yang berbalik menguntungkan supply and demand. Ia detector TERLEMAH di
rig, dan ia salah satu dari dua yang paling sedikit rusak di luar sampel. Lengan
L bahkan satu satunya baris yang positif bersama breaker. Itu bukan alasan
mengirim lengan L - t=+0,229 - tetapi ia alasan untuk berhenti menyebut supply
and demand sebagai yang paling buruk.

## Cara mengulang

```bash
cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.oos_symbols
```

---

Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA).
