# Peran review AI Agent

Empat peran yang memeriksa work AI Agent sebelum dikatakan selesai. Satu orang
bisa memegang semua; perannya dipisah supaya pertanyaannya tidak menyatu.

## 1. Fidelity reviewer

Pertanyaan: "apakah agent masih jujur?"

- Prompt system di `backend/app/agent.py` masih memuat empat hukum SOUL.md?
- `grounding.check` dipanggil di jalur balasan, tanpa cabang yang melewatkannya?
- Tidak ada angka yang dilewatkan ke model di luar `digest()`?
- UI menampilkan verdict grounding, termasuk yang gagal?

## 2. Security reviewer

Pertanyaan: "apa yang bisa dilakukan orang lain lewat endpoint ini?"

- api_key tidak pernah kembali utuh dari `GET /api/agent/config` (masker)?
- `backend/.agent.json` di `.gitignore` dan benar-benar tidak ter-track?
- `POST /api/agent/chat` tidak bisa dipakai sebagai proxy bebas: base_url
  hanya dari config tersimpan, bukan dari body request?
- CORS tetap loopback-only?

## 3. UX reviewer

Pertanyaan: "apa yang dilihat orang yang pakai ini tiap hari?"

- Status tanpa key jelas terlihat, bukan diam?
- Reply grounding-gagal ditandai keras, bukan dicampur tenang?
- Chat bisa dibaca sambil chart terbuka (context summary selalu terlihat)?
- Error upstream ditampilkan dengan kata-kata upstream, bukan "gagal"?

## 4. Operator reviewer

Pertanyaan: "kalau ini jalan berjam-jam, apa yang rusak?"

- Stress test (`tools.agent_stress`) lulus dan `/api/health` tetap responsif?
- Chat yang lambat tidak memblok endpoint lain (timeout, tidak menahan GIL)?
- Semua gate di CLAUDE.md hijau dengan exit code dibaca?
