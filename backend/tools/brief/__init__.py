"""Satu perintah yang menarik SELURUH bacaan Zonelab untuk dibaca AI agent.

    python -m tools.brief --symbol mt5:XAUUSD

KENAPA PAKET INI ADA. Menarik gambaran lengkap Zonelab sebelumnya menuntut
lima sampai enam panggilan `/api/draw` dengan set layer dan blok params yang
berbeda beda, dan tiap kali satu layer lupa disebut ia mengembalikan array
kosong yang TERBACA SAMA dengan "tidak ada apa apa di sini". Itu terjadi tiga
kali dalam satu sesi analisis pada 29 Agustus 2026: `projections` dan `gaps`
kosong karena tidak diminta, `chain` None karena window-nya terlalu pendek
untuk memuat satu siklus minggu, dan pembacaan pertama menyimpulkan "tidak ada
zona supply di atas harga" padahal yang menyala cuma satu detector dari lima.

Kesimpulan yang keliru itu bukan kesalahan mesinnya. Ia kesalahan cara
memanggilnya, dan cara memanggil yang mudah salah adalah cacat desain.

APA YANG DIJAMIN PAKET INI:

  - SEMUA layer menyala, dengan blok params yang benar benar dibutuhkan tiap
    layer untuk menggambar sesuatu. Tiga layer menggambar NOL dengan params
    bawaan (cycle grid, defining range, SSMT) dan itu terukur, jadi tiga itu
    diberi params eksplisit di sini.
  - Beberapa timeframe sekaligus, karena bias dan struktur dibaca di derajat
    yang berbeda dari eksekusinya.
  - Setiap angka dibawa BERSAMA provenance-nya. Registry layer punya field
    `evidence` yang wajib, dan brief ini menyalinnya apa adanya supaya agent
    yang membacanya tidak bisa mengutip klausa doktrin sebagai hasil ukur.
  - Kekosongan dibedakan dari ketiadaan. Kalau sebuah layer menggambar nol, itu
    dicatat beserta alasannya, bukan dibiarkan jadi array kosong yang senyap.

TIDAK BERGANTUNG PADA API. Engine-nya dipanggil langsung lewat
`app.drawing.build`. Server di 8100 pernah mati di tengah sesi analisis karena
stress test-nya sendiri, dan brief yang ikut mati bersamanya tidak berguna.
"""
