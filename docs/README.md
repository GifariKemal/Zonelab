# Peta direktori docs

Direktori ini berisi 20 dokumen prosa, 77 file bukti mentah, dan 4 spec desain.
Tanpa peta, pembaca yang membukanya melihat 101 file dan tidak bisa tahu prosa
mana membaca data mana. Itu satu-satunya alasan file ini ada.

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
| [TRIAGE-94.md](TRIAGE-94.md) | Putusan 94 item failed/null/rejected/blocked, dengan referensi akademis per kategori |
| [WALKFORWARD-MT5.md](WALKFORWARD-MT5.md) | Apakah gate-nya bertahan di luar sampel, per fold, termasuk fold yang gagal |
| [AUDIT-MENYELURUH.md](AUDIT-MENYELURUH.md) | Apa Zonelab sebenarnya, apa yang terwire, apa yang terukur, dan jarak antara sistem yang diceritakan dengan sistem yang dibangun. **Mulai dari sini kalau baru membaca repo ini** |
| [QA-PRODUKSI.md](QA-PRODUKSI.md) | Catatan QA/QC menuju produksi, 16 bagian, setiap angka dari perintah yang dijalankan |
| [ALUR-ORDER.md](ALUR-ORDER.md) | Apa yang terjadi, urut, ketika Zonelab memasang order, dan gerbang mana yang menghentikan apa |
| [PRAREGISTRASI-KONDISI.md](PRAREGISTRASI-KONDISI.md) | Kolom mana yang diuji sebagai pengkondisi ekspektasi, ditulis sebelum satu angka dihitung, plus hasilnya |
| [QA-QUANT.md](QA-QUANT.md) | Apakah edge-nya nyata setelah biaya per instrumen dan urutan di dalam bar diselesaikan dengan benar. **Baca ini sebelum CALIBRATION.md** |
| [QA-DETEKTOR.md](QA-DETEKTOR.md) | Apakah supply_demand, order_block, fvg dan ifvg valid, terkalibrasi, dan tergambar di tempat yang benar, di Zonelab MAUPUN di MQL5 yang berjalan di MT5. Termasuk kenapa tiga gate parity lama tidak pernah menjalankan satu baris pun MQL5 |
| [QA-BREAKOUT.md](QA-BREAKOUT.md) | Breakout diukur di MT5 Strategy Tester dengan real tick: 7.847 trade, null, dan ketiga varian yang metodenya resepkan memperburuk. Plus kesepakatan lintas-rig pertama di repo ini |
| [QA-UI.md](QA-UI.md) | Audit UI/UX penuh: lima cacat yang audit temukan, palette light mode yang diturunkan numerik dari floor theme gelap, kenapa tujuh role tidak dapat tujuh warna, dan dua check harness yang versi pertamanya terbukti hampa |
| [PROMPT-SESI-TRADING.md](PROMPT-SESI-TRADING.md) | Template prompt untuk sesi analisis pasar plus pending order, dan empat pemeriksaan pra-kirim yang masing-masing sudah pernah salah |
| [PRAREGISTRASI-KORELASI.md](PRAREGISTRASI-KORELASI.md) | Apakah korelasi partner mengkondisikan hasil SSMT, ditulis sebelum satu angka pun ada. Bagian 7 terisi 29 Agustus 2026: null, `t` terbesar 0,19 lawan kritis 3,48 |
| [PRAREGISTRASI-YATIM.md](PRAREGISTRASI-YATIM.md) | Apakah enam modul yang tidak tersambung ke jalur keputusan memisahkan hasil, ditulis sebelum angkanya ada, plus hasilnya |
| [PRAREGISTRASI-REGIME.md](PRAREGISTRASI-REGIME.md) | Apakah ADX dan BB Width mengkondisikan hasil, ditulis sebelum gerbangnya diwire ke jalur daemon |
| [QT-CHECKLIST.md](QT-CHECKLIST.md) | Apakah QT Entry Checklist v2 bisa dipakai memutuskan entry: skor, tier, aturan ukuran posisi, sebelas kolom builder, lima divergensi antara sumbernya dan repo ini, plus dua item yang terhalang secara struktural |
| [PRAREGISTRASI-EKSEKUSI.md](PRAREGISTRASI-EKSEKUSI.md) | Dua aturan eksekusi yang diuji setelah sinyalnya habis, keduanya ditolak, dan satu ambang praregistrasi yang salah dirancang |

## File bukti, dan tool yang menghasilkannya

Konvensinya nama, bukan mekanisme: setiap tool mencetak ke stdout dan hasilnya
dialihkan ke `docs/<nama>.json`. Jadi `docs/mss.json` datang dari
`python -m tools.mss`, dan **tidak ada apa pun yang menegakkan itu** selain
konvensi ini. Diperiksa 21 Agustus 2026 pada 21 file, diperiksa ulang
29 Agustus 2026 setelah `baseline.json` masuk, dan diperbarui 4 September
2026: ke-66 file punya tool yang cocok atau dihasilkan dari skrip manual
(Wyckoff MT5 backtest), tidak ada yang orphan.

Tanda hubung lawan garis bawah adalah artefak sejarah dan bukan makna:
`smt-volatility.json` datang dari `tools/smt_volatility.py`.

| Bukti | Dihasilkan oleh | Dibaca prosa | Isi |
|---|---|---|---|
| `alignment.json` | `tools.alignment` | - | 26 kunci |
| `baseline.json` | `tools.baseline` | CALIBRATION.md | 9 kunci, 8 sel plus gabungan, kontrol bebas-sinyal |
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
| `quarter_placement.json` | `tools.quarter_placement` | - | 9 deret, penempatan kuarter |
| `checklist_outcomes.json` | `tools.checklist_outcomes` | - | 17 klausa lawan outcome, n=1855 di 8 instrumen, resolusi bar 5m. `dfr_side` memisahkan dengan tanda TERBALIK |
| `detectors_costed.json` | `tools.detectors_costed` | - | gerbang departure pada populasi `fvg` dan `order_block` setelah biaya dan intrabar, venue MT5. fvg FAIL, order_block PASS |
| `detectors_costed_binance.json` | skrip replikasi di riwayat sesi 30 Agustus 2026 | - | replikasi venue kedua, Binance, 3 sel crypto. order_block 7 dari 8 fold, di bawah bar 8 dari 8 yang ditulis di depan; tanda `fvg` BERBALIK |
| `dfr_outcomes.json` | `tools.dfr_outcomes` | - | level ekstensi DFR lawan kontrol jitter per-event, 10 grup, null |
| `reality_check.json` | `tools.reality_check` | - | White's RC, Hansen's SPA, Romano-Wolf StepM pada 4 universe aturan yang sudah diuji |
| `ssmt_outcomes.json` | `tools.ssmt_outcomes` | - | divergensi SSMT lawan bar non-divergensi instrumennya sendiri, 24 sel, null |
| `conditioned_gaps.json` | `tools.conditioned_gaps` | - | `gaps` dan `liquidity` sebagai PENGKONDISI kohort zona, 12 instrumen, n=2757, 20 grup, null |
| `conditioned_structure.json` | `tools.conditioned_structure` | - | `structure` dan `projections` sebagai PENGKONDISI kohort zona, 8 instrumen, n=1855, 30 grup, null |
| `wyckoff_outcomes.json` | `tools.wyckoff_outcomes` | - | forward move arah 4 fase Wyckoff lawan drift per-instrumen, 9 instrumen, null |
| `csid_ob_outcomes.json` | `tools.csid_ob_outcomes` | - | CISD di dalam order block lawan drift (arah), 9 instrumen, null, hampir degenerat |
| `orphan_filters.json` | `tools.orphan_filters` | PRAREGISTRASI-YATIM.md | menurunkan tiga klaim Bagian 5 yang sumbernya transkrip jadi angka yang bisa dijalankan ulang. tCISD sebagai filter ternyata baseline salah label; tCISD sebagai entry mandiri tidak punya jalur kode; quant arahnya bertahan, rentangnya tiga kali lebih lebar |
| `olhc_outcomes.json` | `tools.olhc_outcomes` | PRAREGISTRASI-YATIM.md | modul yatim terakhir yang belum punya angka. classify() terbukti pelabelan ulang (open_pos, close_pos) sehingga pertanyaan urutannya ditarik; klaim arahnya null, t=+0,29 dan +0,005 |
| `gap_outcomes.json` | `tools.gap_outcomes` | - | lima objek gap yang digambar dan belum pernah diukur: breakaway, measuring, opening, ifvg, breaker. breakaway n=0 (cabangnya tak tercapai). measuring unggul lawan mirror (-2,70 bar, t=-3,65) tapi GUGUR lawan kontrol matched (-0,69 bar, t=-1,06). ifvg dan breaker dicapai LEBIH LAMBAT dari kontrol matched (+0,65 t=+3,63 dan +1,24 t=+5,83), tanda terbalik. Tiga kontrol yang gugur ikut dilaporkan |
| `psp_outcomes.json` | `tools.psp_outcomes` | - | PSP sesudah SSMT lawan bar tanpa PSP (H1) dan lawan PSP tanpa SSMT (H2). 48 sel, 4 pasangan, 3 lebar bracket, dua arah. NULL semua, |z| terbesar 2,10 lawan bar Bonferroni 3,28 |
| `instrument_scan.json` | `tools.instrument_scan` | - | hold rate zona lawan placebo geser di 12 instrumen, 9 di antaranya belum pernah punya satu angka pun. TANPA BIAYA, jadi klaim lokasi dan bukan klaim edge tradeable. 10 dari 12 MEMISAHKAN, 4/4 lipatan. Null: NAS100 (z +2,66) dan WTI (z +1,54) |
| `mt5-backtest.json` | `tools.mt5_backtest` | QA-DETEKTOR.md | matriks Strategy Tester, empat detektor lawan dua instrumen lawan lima timeframe. Tiap sel menulis `.set`-nya sendiri dan menyalin `.htm`-nya ke `mql5/ZonelabSupplyDemand/reports/`, karena sampai 1 September 2026 repo ini punya NOL artifact backtest dan `ReplaceReport=1` membuat tiap run menghapus run sebelumnya |
| `mt5-walkforward.json` | `tools.mt5_backtest`, empat kali dengan rentang tanggal berbeda | QA-DETEKTOR.md | stabilitas antar-periode 64 sel di 2023, 2024, 2025 dan Jan-Agu 2026. NOL dari 16 sel menang di keempat periode |
| `csid_ob_intrabar.json` | `tools.csid_ob_intrabar` | - | CISD fresh (recency 50 bar) di dalam order block lawan resolved R (intrabar 5m, biaya), 8174 trade, delta -0,136 R t=-7,04, walk-forward 8/8 negatif, MEMISAHKAN tanda terbalik |
| `expectation.json` | `tools.expectation` | - | expected path evaluation |
| `event_backtest.json` | `tools.event_backtest` | - | event-driven backtest harness |
| `order_key.json` | `tools.order_key` | - | tie-breaker order key evaluation, `near_close` t=-4,64 wf 0/8 |
| `phase_targets.json` | `tools.phase_targets` | - | quarterly phase target evaluation |
| `lowtf_costed.json` | `tools.lowtf_costed` | - | 30m edge setelah biaya |
| `lowtf_resolution.json` | `tools.lowtf_resolution` | - | kontrol resolusi 1m untuk edge 30m |
| `continuation_backtest.json` | `tools.continuation_backtest` | - | continuation entry backtest |
| `continuation_exits.json` | `tools.continuation_exits` | - | continuation exit variants |
| `continuation_backtest_30m.json` | `tools.continuation_backtest` | - | continuation di 30m |
| `fvg_inverted.json` | `tools.fvg_inverted` | - | FVG inverted gate, +0,2188 R 8/8 fold |
| `fvg_resolution.json` | `tools.lowtf_resolution` | - | FVG resolusi kontrol |
| `volume_imbalance.json` | `tools.volume_imbalance` | BACKLOG.md 3b | DITOLAK: median 0,0058 ATR, n akhir 18, t=+0,32 |
| `shelf_conditioned.json` | `tools.shelf_conditioned` | BACKLOG.md 3c | S&R sebagai kondisi zona, tak terukur karena n=1 |
| `shelf_proximity.json` | `tools.shelf_proximity` | - | kedekatan shelf ke zona |
| `mt5_python_parity.json` | `tools.mt5_python_parity` | QA-DETEKTOR.md | parity check Python lawan MQL5, 6 dari 8 sel tidak sepakat |
| `entry_probability.json` | `tools.entry_probability` | - | probabilitas entry per kondisi |
| `stop-scale-sensitivity.txt` | manual | - | sensitivitas parameter skala stop |
| `mt5-backtest-atrlast-m30.json` | `tools.mt5_backtest` | - | MT5 backtest dengan ATR last di M30 |
| `mt5-wyk-arm0.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff arm 0 (vanilla breakout) |
| `mt5-wyk-arm1.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff arm 1 (retest) |
| `mt5-wyk-arm2.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff arm 2 (tick count filter) |
| `mt5-wyk-arm3.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff arm 3 (fade the fakeout) |
| `mt5-wyk-arm0-matrix.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff arm 0 sensitivity matrix |
| `mt5-wyk-h4.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff XAUUSD H4, 129 trade, PF 1,34 tidak bereplikasi |
| `qt_outcomes.json` | `tools.qt_outcomes` | QT-CHECKLIST.md | skor checklist Quarterly Theory lawan outcome: monotonisitas, tren, split median, kontras gate, aturan ukuran posisi, plus sebelas kolom builder satu per satu. Populasinya DIIMPOR dari `tools/checklist_outcomes.py:rows_for` tanpa satu baris diubah, supaya hasilnya sebanding dengan studi kelima |
| `htf_gate_outcomes.json` | `tools.htf_gate_outcomes` | ALUR-ORDER.md bagian 3b | apakah `--htf-gate` layak memblokir order. n=1828, delapan instrumen. Kohort yang ia buang punya ekspektansi LEBIH TINGGI daripada yang ia simpan, jadi flag-nya dicabut dari `start.bat` |
| `qt_clock_parity.json` | `tools.qt_clock_parity` | QT-CHECKLIST.md | jam Quarterly Theory di MQL5 lawan Python pada 17.520 titik waktu sepanjang 2026, termasuk kedua transisi DST New York. Nol ketidaksepakatan |
| `mt5-qt-a0control.json` sampai `mt5-qt-a5_333.json` | `tools.mt5_backtest` dengan `--experts ZonelabQT` | QT-CHECKLIST.md | enam lengan gerbang waktu QT, M15 real tick, XAUUSD dan BTCUSD. a0control adalah lengan tanpa filter dan harus sama dengan ZonelabSD |
| `mt5-qt-clockdump.json` | `tools.mt5_backtest` dengan `--experts ZonelabQTDump` | - | run yang menulis `zonelab_qt_clock.csv` ke folder Common, satu-satunya masukan `qt_clock_parity` |
| `qt_outcomes_seven.json` | `tools.qt_outcomes` | QT-CHECKLIST.md | bacaan konteks studi QT pada tujuh instrumen praregistrasi, n=1608. USOIL tidak ikut karena lingkupnya dipersempit ke XAU dan BTC, dan arah biasnya dinyatakan di prosanya |
| `mt5-wyk-h4-btc.json` | `tools.mt5_backtest` | QA-BREAKOUT.md | Wyckoff BTCUSD H4 replikasi, PF 1,01 |

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

## Spec desain

Empat dokumen di `docs/specs/`, ditulis sebelum kode-nya, dan direferensikan
oleh kode yang mengimplementasikan kontraknya.

| Spec | Status | Direferensikan oleh |
|---|---|---|
| [ai-agent-design](specs/2026-08-21-ai-agent-design.md) | terbangun | `test_agent.py` |
| [wyckoff-design](specs/2026-08-31-wyckoff-design.md) | terbangun | `wyckoff.py`, `layers.py` |
| [zonelab-ea-mql5-design](specs/2026-08-31-zonelab-ea-mql5-design.md) | terbangun | `mql5/ZonelabSupplyDemand/` |
| [expectation-overlay-design](specs/2026-08-31-expectation-overlay-design.md) | menunggu review | - |

## Cara mereproduksi sebuah angka

```powershell
cd backend
.\.venv\Scripts\python.exe -m tools.walkforward > ..\docs\walkforward.json
```

Pengukuran lawan terminal lokal memakai prefiks `mt5:` di `tools/history.py`, dan
output-nya diarahkan ke file bersuffiks `-mt5` supaya kedua venue tidak saling
menimpa. Keduanya disimpan karena keduanya benar tentang venue-nya masing-masing:
emas spot CFD dan kontrak depan COMEX bukan instrumen yang sama.
