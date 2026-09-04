# AI Agent, instruksi sesi

Folder ini mendefinisikan AI Agent advisor Zonelab. Kode yang berjalan ada di
`backend/app/agent.py` (backend), `frontend/src/app/agent/page.tsx` (UI),
dan `backend/tools/agent_smoke.py` + `agent_stress.py` (pengujian). Folder ini
adalah definisi dan dokumentasinya, bukan kode yang dieksekusi.

## Aturan pertama

Sebelum menyunting apa pun di sini, baca `SOUL.md`. Empat hukumnya
(arah bukan milik model, angka hanya dari engine, cohort rate bukan
probabilitas, first touch) bukan gaya menulis; keduanya ditegakkan
`backend/app/grounding.py` dan dijanjikan ke user di UI. Dokumen yang
melonggarkan hukum itu adalah bug dokumentasi.

## Batas suntingan

- Prompt system yang berjalan = konstanta `SYSTEM` di `backend/app/agent.py`.
  Sunting di sana, lalu sinkronkan `SOUL.md`. Jangan sebaliknya.
- Config runtime (base_url, api_key, model) TIDAK PERNAH ditulis ke file
  ter-track git. Lokasinya `backend/.agent.json`, sudah di `.gitignore`.
  Kredensial bocor di commit pernah terjadi di grup ini (2026-05-28) dan
  aturannya sejak itu mutlak.
- `app/` tidak boleh mengirim order. Agent juga tidak: chat endpoint tidak
  menyentuh `tools/execute`, `tools/autotrade`, atau MT5.

## Gate sebelum bilang selesai

```bash
cd backend  && .venv/Scripts/python.exe -m pytest
cd backend  && .venv/Scripts/python.exe -m pyflakes app tools tests
cd frontend && npm run check
cd frontend && npm run build
cd backend  && .venv/Scripts/python.exe -m tools.agent_smoke
cd frontend && node e2e/agent.mjs
```

Baca exit code, bukan ringkasan. Gate baru harus dibuktikan tidak kosong:
suntikkan cacat yang ia tangkap, pastikan gagal, lalu kembalikan.

## Gaya penulisan

Sama dengan CLAUDE.md di akar repo: tanpa em-dash dan en-dash, ASCII saja,
kutip lurus, Bahasa Indonesia baku, istilah teknis English. Setiap klaim
berangka dari command yang benar-benar dijalankan.
