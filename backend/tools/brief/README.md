# tools/brief

Satu perintah yang menarik seluruh bacaan Zonelab ke satu folder, dibuat untuk
dikonsumsi AI agent (Claude Code CLI atau lainnya).

```bash
cd backend
PYTHONPATH=. .venv/Scripts/python.exe -m tools.brief
```

Keluaran default ke `../brief/`:

| File | Untuk siapa | Isi |
|---|---|---|
| `brief.json` | mesin | seluruh bacaan mentah, sekitar 3 MB |
| `BRIEF.md` | agent dan manusia | ringkasan berurut, sekitar 15 KB |

## Kenapa ini ada

Menarik gambaran lengkap Zonelab sebelumnya menuntut lima sampai enam panggilan
`/api/draw` dengan set layer dan blok params berbeda, dan tiap kali satu layer
lupa disebut ia mengembalikan array kosong yang **terbaca sama** dengan "tidak
ada apa apa di sini".

Itu terjadi tiga kali dalam satu sesi analisis pada 29 Agustus 2026:

1. `projections` dan `gaps` kosong karena tidak diminta.
2. `chain` `None` karena window terlalu pendek untuk memuat satu siklus minggu.
3. Kesimpulan "tidak ada zona supply di atas harga" ditarik padahal yang menyala
   cuma satu detector dari lima. Dengan kelimanya menyala ada 25 zona supply.

Kesimpulan keliru itu bukan kesalahan mesinnya. Ia kesalahan cara memanggilnya,
dan cara memanggil yang mudah salah adalah cacat desain.

## Yang dijamin

- **Semua layer menyala**, dengan blok params yang benar benar dibutuhkan tiap
  layer untuk menggambar sesuatu. Tiga layer menggambar nol dengan params bawaan
  (cycle grid, defining range, SSMT) dan itu terukur, jadi ketiganya diberi
  params eksplisit.
- **Cap display dimatikan.** `max_zones_per_side=100` terbaca seperti "mati" dan
  ia maksimum schema, padahal ia memilih menurut kebaruan. Cap itu sudah empat
  kali diam diam merusak pengukuran di repo ini; hanya `0` yang berarti tanpa cap.
- **Beberapa timeframe sekaligus**, dan kandidat diperingkat lintas timeframe.
  Eksekusi terjadi di timeframe halus dan bias dibaca di yang kasar.
- **Rencana ikut dibangun.** `app/drawing.build` menggambar bentuk; entry, stop,
  target, RR, lot dan biaya lahir di `app/main._annotate`. Brief memanggil
  keduanya, karena versi pertamanya memanggil `build` saja lalu melaporkan "nol
  rencana" pada bar yang sebenarnya punya tiga belas.
- **Kekosongan dibedakan dari ketiadaan.** Layer yang menggambar nol dicatat di
  `empty_because` beserta stats-nya.
- **Tidak bergantung API.** Engine dipanggil langsung. Server di 8100 pernah mati
  di tengah sesi analisis karena stress test-nya sendiri.

## Cara agent membacanya

> [!IMPORTANT]
> Baca blok `[!CAUTION]` di awal `BRIEF.md` lebih dulu, sebelum satu angka pun
> dikutip. Ia berisi daftar hal yang **tidak boleh** disimpulkan dari isinya.

Aturan kutip:

1. **Selalu bawa `source` klausa.** Tiga belas dari tujuh belas klausa ICT
   bersumber `doctrine`, artinya sumbernya menyatakan dan project ini belum
   punya angka. Tiga bersumber `measured`, dan ketiganya nol. Mengutip klausa
   doktrin sebagai hasil pengukuran adalah kesalahan yang seluruh registry
   `evidence` di repo ini ada untuk mencegahnya.
2. **`measured_against` lebih kuat daripada `doctrine`.** Kalau sebuah klausa
   muncul di sana, ada angkanya dan angkanya menunjuk ke arah lain.
3. **Jangan kutip margin gerbang sendirian.** Tiga kalimat berlaku bersamaan:
   seluruh populasi zona null lawan tanpa-box, kohort yang lolos gerbang
   memisahkan, dan ekspektansi kohort itu sendiri tidak bisa dibedakan dari nol.
4. **`feed_stale_for_execution: true` berarti angka bolehnya dibaca, bukan
   ditradingkan.** Di akhir pekan ini normal dan berarti pasar tutup.

## Argumen

| Flag | Default | Arti |
|---|---|---|
| `--symbol` | `mt5:XAUUSD` | prefix provider ikut dibaca |
| `--intervals` | `4h,1h,15m` | kasar ke halus; yang pertama dipakai untuk siklus dan bias |
| `--bars` | `2000` | per timeframe |
| `--partners` | `mt5:XAGUSD,mt5:XPTUSD` | pasangan SSMT dan triad |
| `--out` | `../brief` | folder keluaran, relatif ke `backend/` |

Exit code `1` kalau ada bagian yang gagal ditarik, dan yang gagal disebut di
`failures` serta di `BRIEF.md`. Brief yang kehilangan satu timeframe tanpa
mengatakannya terbaca sebagai timeframe yang tidak punya apa apa.

## Yang TIDAK ada di sini

- **Checklist async** (`app/checklist.py`) butuh provider call per bias
  timeframe dan per simbol SSMT, jadi ia hidup di jalur async API. Brief ini
  sengaja sinkron supaya tidak ikut mati saat server mati.
- **Triad dan korelasi** (`/api/triad`) untuk alasan yang sama.

Keduanya bisa ditambahkan, dan kalau ditambahkan harus dengan penanganan
kegagalan per partner, karena `load_aligned` melaporkan partner yang di-skip dan
brief harus meneruskan laporan itu alih alih menelannya.
