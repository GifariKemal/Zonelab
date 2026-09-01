# Zonelab, instruksi sesi

File ini ter-load otomatis setiap sesi Claude Code CLI yang berjalan di direktori
ini atau di bawahnya. Isinya dua hal: cara menulis, dan cara memverifikasi.

## WAJIB, sebelum balasan pertama

Load skill `humanize-tone`:

```
Skill(skill="humanize-tone")
```

Sebelum menulis apa pun ke user, ke commit message, atau ke file `.md`.

> [!IMPORTANT]
> Voice target di bawah ini ditulis lengkap **di sini juga**, bukan hanya di
> skill-nya. Alasannya bukan redundansi: kalau load skill gagal atau nama
> skill-nya berubah, sesi yang mengira sudah patuh justru yang paling berbahaya.
> Project ini sudah tiga kali tertipu instrumennya sendiri yang melaporkan hijau
> saat crash. Aturan yang cuma hidup di satu tempat adalah aturan yang bisa hilang
> tanpa ada yang tahu.

## Voice target

Bilingual, dan **English yang dominan untuk semua yang teknis**. Struktur kalimat
Bahasa Indonesia baku KBBI. Noun teknis, tool, command, jargon: tetap English.

Ini bukan preferensi gaya. Kalau di kode namanya `window`, menulis `jendela`
memaksa pembaca translate balik sebelum bisa grep. 233 istilah pernah dibalik di
project ini karena alasan itu.

| Tulis | Jangan |
|---|---|
| `caption zona terpotong di edge kanan` | `terpotong di tepi kanan` |
| `gate-nya dibuktikan tidak kosong` | `gerbangnya dibuktikan tidak kosong` |
| `dua box yang keduanya di tempat benar` | `dua kotak yang keduanya benar` |
| `satu window, kedua server` | `satu jendela, kedua server` |
| `output-nya diarahkan ke file` | `keluarannya diarahkan ke berkas` |

Suffix pakai hyphen: `box-nya`, `gate-nya`, `output-nya`. Bukan `boxnya`.

Kata yang **selalu** English di project ini: window, file, box, gate, edge,
output, ink, picker, layer, launcher, sweep, socket owner, range frame, hold loop,
zone, detector, overlay, repaint, lookahead, harness, gutter, caption, primitive,
provider, endpoint, deploy, throughput, commit, push, tag, screenshot.

## Kill list

Nol toleransi, dan hasilnya bisa dicek:

1. **Em-dash dan en-dash.** Pakai hyphen `-`, koma, atau kurung. Semua `.md` di
   project ini harus 0 em-dash dan 0 en-dash. Cek:
   ```bash
   python -c "import pathlib,glob; [print(f, pathlib.Path(f).read_text(encoding='utf-8').count(chr(8212))) for f in glob.glob('**/*.md', recursive=True)]"
   ```
2. **ASCII saja.** Tanpa smart quote keriting, tanpa glyph fancy. Kutip lurus
   `"` dan `'`. Emoji shortcode GitHub boleh di `.md`, tidak di chat.
3. **Antithesis template.** "bukan sekadar X, tapi Y" dan sejenisnya. Nyatakan
   langsung. Kontras faktual yang membawa informasi boleh, misalnya
   `dibuktikan, bukan diasumsikan`; yang dilarang inflasi retorisnya.
4. **Filler.** delve, moreover, furthermore, leverage sebagai verb, seamless,
   robust, comprehensive, crucial, unlock, elevate, "it's worth noting",
   "pada dasarnya", "perlu dicatat bahwa".
5. **Tricolon refleks.** Tiga item otomatis padahal yang benar satu atau dua.
6. **Forced summary.** "Kesimpulannya", "Secara keseluruhan", "Overall" yang cuma
   mengulang. Potong, kecuali user memang minta ringkasan.
7. **Over-bold.** Bold satu term, kalau memang layak. Bukan setengah kalimat.
8. **Antusiasme kosong.** "Great question", tanda seru, emoji di chat.
9. **Abstrak menggantikan angka.** Bukan `performanya meningkat signifikan`, tapi
   `p99 turun dari 800ms ke 120ms`. Kalau angkanya belum ada, sebut metriknya,
   jangan adjektifnya.

## Yang tidak boleh disunting demi "flow"

Angka, nama API, command, nama file, dan hedge yang memang benar. Kalau sesuatu
belum diukur, kalimatnya harus mengatakan begitu. `belum ditest di prod` tetap.

## Cara memverifikasi, karena di project ini itu bagian dari menulis

Setiap klaim di `.md` dan di chat harus punya angka dari command yang benar-benar
dijalankan. Kalau belum diukur, tulis bahwa belum diukur.

Tiga jebakan yang sudah memakan waktu nyata di sini:

1. **Jangan menilai gate dari ringkasan yang lewat `tail` atau proxy.** Baca exit
   code. `eslint` pernah crash sebelum memeriksa satu file dan ringkasannya
   berbunyi `No issues found`. Pakai `npm run check` dan baca exit code-nya.
2. **Kecualikan shell sebelum mempercayai hitungan proses.** Filter command line
   akan match ke command yang sedang memfilter. Itu terjadi empat kali dalam satu
   sesi, dan sekali di antaranya menutup desktop user.
3. **Jangan pernah kill berdasarkan window title saja.** Window File Explorer
   mengambil title dari foldernya, jadi `WINDOWTITLE eq Zonelab*` match ke
   `explorer.exe` dan mematikan desktop. Butuh `IMAGENAME` juga.

Gate yang harus hijau sebelum bilang selesai:

```bash
cd backend  && .venv/Scripts/python.exe -m pytest        # 1104 passed
cd backend  && .venv/Scripts/python.exe -m pyflakes app tools tests
cd frontend && npm run check                            # exit 0
cd frontend && npm run build                            # exit 0
```

> [!WARNING]
> **Empat perintah di atas tidak menjalankan satu pun browser.** Pada 29
> Agustus 2026 sebuah layer baru ditambahkan ke registry, `e2e/wiring.mjs`
> exit 1 selama dua commit, dan keempat gate itu tetap hijau sepanjang waktu
> itu. Laporan "semua gate hijau" ditulis berkali-kali di atas harness yang
> merah.
>
> Kalau perubahannya menyentuh `app/layers.py`, `frontend/src/components/`,
> atau apa pun yang digambar, tambahkan minimal ini, dan baca exit code-nya:
>
> ```bash
> cd frontend && node e2e/wiring.mjs .playwright-shots           # tiap layer terwire
> cd frontend && node e2e/labels.mjs .playwright-shots           # peta tabrakan label (deterministik)
> cd frontend && node e2e/sweep.mjs  .playwright-shots           # sapuan fitur penuh
> cd frontend && node e2e/expectation-path.mjs .playwright-shots # garis path menggambar
> ```
>
> `labels.mjs` dipatok ke provider `synthetic` sejak 1 September 2026. Sebelum
> itu ia membaca ekor MT5 hidup dan berubah hasil antar run di tree yang sama:
> lima run memberi 7/9, 8/9, 8/9, 7/9, 9/9 tanpa satu baris kode berubah, dan
> box straddle yang dituduhkan ke sebuah branch muncul juga di tree tanpa branch
> itu. Kalau ia merah sekarang, itu berarti sesuatu.
>
> **Dan itu terjadi lagi.** Pada 31 Agustus 2026 layer `wyckoff` masuk registry
> membawa slider "Trading range width", sensus slider di `e2e/sweep.mjs` tidak
> ikut diperbarui, dan harness itu exit 1 selama **24 commit** berikutnya sampai
> 1 September. Keempat gate di atas hijau sepanjang waktu itu. Pola yang persis
> sama dengan catatan 29 Agustus di atas, di harness yang berbeda: menambah layer
> berarti menyentuh `wiring.mjs` DAN sensus slider `sweep.mjs`.
>
> Untuk perubahan backend yang menyentuh API, restart dulu server di 8100
> (`start.bat` menjalankan uvicorn TANPA `--reload`, jadi ia membawa kode lama
> sampai di-restart), lalu:
>
> ```bash
> cd backend && PYTHONPATH=. .venv/Scripts/python.exe -m tools.validate_api
> ```
>
> `e2e/autotrade.mjs` menyentuh saklar auto-trade yang sungguhan. Jangan
> dijalankan saat ada daemon hidup kecuali memang itu yang diuji.

Gate baru harus **dibuktikan tidak kosong**: suntikkan kembali cacat yang ia
ditulis untuk menangkap, pastikan ia gagal, lalu kembalikan.

## Menjalankan

Dobel-klik `start.bat`, matikan dengan `stop.bat`. Jangan buat `.ps1`: `assoc .ps1`
di mesin ini menjawab `File association not found`, jadi `.ps1` tidak bisa
sekali-klik. Alasan lengkapnya di `docs/QA-PRODUKSI.md` bagian 16.

## Konteks

Catatan pengukuran ada di `docs/`, dan `docs/README.md` memetakan mana membaca
mana. Sebelum menambah objek gambar baru, baca `docs/BACKLOG.md`: ada empat
penolakan yang sudah terukur di sana supaya tidak diusulkan lagi.
