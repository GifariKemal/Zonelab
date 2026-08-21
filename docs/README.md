# Peta direktori docs

Direktori ini berisi 6 dokumen prosa dan 21 file bukti mentah. Tanpa peta,
pembaca yang membukanya melihat 27 file dan tidak bisa tahu prosa mana membaca
data mana. Itu satu-satunya alasan file ini ada.

> [!NOTE]
> Semua di sini adalah catatan pengukuran, bukan dokumentasi produk. Untuk cara
> menjalankan dan membaca Zonelab, mulailah dari [README di akar](../README.md).

## Dokumen prosa

| Dokumen | Pertanyaan yang dijawabnya |
|---|---|
| [CALIBRATION.md](CALIBRATION.md) | Apakah zonanya membedakan hasil, dan apa yang tersisa setelah dibebani biaya |
| [FIDELITY.md](FIDELITY.md) | Di mana mesin ini menyimpang dari metodenya, dan apakah penyimpangannya disengaja |
| [ADOPSI.md](ADOPSI.md) | Apa yang diadopsi dari sumber luar, apa yang ditolak, dan pengukuran di belakang tiap keputusan |
| [BACKLOG.md](BACKLOG.md) | Apa yang belum dikerjakan, dan apa yang sudah ditolak supaya tidak diusulkan lagi |
| [WALKFORWARD-MT5.md](WALKFORWARD-MT5.md) | Apakah gate-nya bertahan di luar sampel, per fold, termasuk fold yang gagal |
| [QA-PRODUKSI.md](QA-PRODUKSI.md) | Catatan QA/QC menuju produksi, 16 bagian, setiap angka dari perintah yang dijalankan |

## File bukti, dan tool yang menghasilkannya

Konvensinya nama, bukan mekanisme: setiap tool mencetak ke stdout dan hasilnya
dialihkan ke `docs/<nama>.json`. Jadi `docs/mss.json` datang dari
`python -m tools.mss`, dan **tidak ada apa pun yang menegakkan itu** selain
konvensi ini. Diperiksa 21 Agustus 2026: ke-21 file punya tool yang cocok, tidak
ada yang orphan.

Tanda hubung lawan garis bawah adalah artefak sejarah dan bukan makna:
`smt-volatility.json` datang dari `tools/smt_volatility.py`.

| Bukti | Dihasilkan oleh | Dibaca prosa | Isi |
|---|---|---|---|
| `alignment.json` | `tools.alignment` | - | 26 kunci |
| `calibration.json` | `tools.calibrate` | CALIBRATION.md | 7 kunci, 54 KB |
| `collisions.json` | `tools.collisions` | CALIBRATION.md | 6 kunci |
| `continuation.json` | `tools.continuation` | - | 3 kunci |
| `costed.json` | `tools.costed` | - | 43 kunci |
| `costed-mt5.json` | `tools.costed` | - | 43 kunci, sumber MT5 |
| `costed-mt5-exness.json` | `tools.costed` | - | 43 kunci, profil broker Exness |
| `detectors.json` | `tools.detectors` | BACKLOG.md | 3 kunci |
| `drawing_accuracy.json` | `tools.drawing_accuracy` | - | 14 baris |
| `inversion.json` | `tools.inversion` | - | 13 kunci |
| `momentum.json` | `tools.momentum` | - | 21 kunci |
| `mss.json` | `tools.mss` | - | 17 kunci |
| `reaction.json` | `tools.reaction` | CALIBRATION.md | 13 kunci |
| `refinement.json` | `tools.refinement` | - | 9 kunci |
| `smt-volatility.json` | `tools.smt_volatility` | CALIBRATION.md | 6 kunci |
| `structure_bias.json` | `tools.structure_bias` | - | 12 kunci |
| `three-pushes.json` | `tools.three_pushes` | - | 3 kunci |
| `touches.json` | `tools.touches` | - | 5 kunci |
| `true_day_open.json` | `tools.true_day_open` | - | 4 kunci |
| `walkforward.json` | `tools.walkforward` | CALIBRATION.md | 15 kunci, 44 KB |
| `walkforward-mt5.json` | `tools.walkforward` | WALKFORWARD-MT5.md | 15 kunci, sumber MT5 |

> [!IMPORTANT]
> Kolom "dibaca prosa" kosong **bukan** berarti file-nya mati. Ia output mentah
> yang disimpan supaya sebuah angka bisa direproduksi, dan beberapa pengukuran
> menghasilkan angka yang masuk ke prosa dengan kata-kata alih-alih dengan nama
> file. Menghapus salah satunya akan memutus provenance sebuah klaim yang sudah
> diterbitkan, jadi tidak ada yang dihapus dari sini.
>
> Alasan yang sama berlaku untuk `backend/tools/`. Tool pengukuran dipanggil
> **manusia**, bukan kode, jadi mencari referensi `tools.<nama>` di dalam kode
> akan melaporkan tujuh tool sebagai tak terpakai - dan lima di antaranya
> menghasilkan tabel di atas, sementara `tools/base_quality.py` adalah asal-usul
> `base_drift` dan `base_overlap` yang dikirim di **setiap** zona. Grep itu tes
> yang salah.

## Cara mereproduksi sebuah angka

```powershell
cd backend
.\.venv\Scripts\python.exe -m tools.walkforward > ..\docs\walkforward.json
```

Pengukuran lawan terminal lokal memakai prefiks `mt5:` di `tools/history.py`, dan
output-nya diarahkan ke file bersuffiks `-mt5` supaya kedua venue tidak saling
menimpa. Keduanya disimpan karena keduanya benar tentang venue-nya masing-masing:
emas spot CFD dan kontrak depan COMEX bukan instrumen yang sama.
