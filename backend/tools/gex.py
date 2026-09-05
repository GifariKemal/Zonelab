"""Membaca gamma exposure hidup untuk sebuah simbol, sekali, sebagai JSON.

    PYTHONPATH=. .venv/Scripts/python.exe -m tools.gex --symbol XAUUSD

KENAPA CLI DAN BUKAN FIELD DI `/api/draw`, dan ini keputusan bukan kelalaian.

`app/gex.py` menjelaskan bahwa tidak ada riwayat option chain di sumber ini,
jadi angkanya TIDAK BISA diukur lawan outcome dan karena itu tidak boleh jadi
gerbang. Yang tersisa adalah panel yang melaporkan. Tapi Bagian 2 nomor 6 di
`docs/BACKLOG.md` mencatat cacat yang sudah pernah terjadi di repo ini persis
di titik itu: `news_error` dikirim ke jalur tipe yang salah dan TIDAK PERNAH
dirender, jadi backend mengirim sesuatu yang tidak pernah sampai ke mata siapa
pun. Menambah field kelima belas ke `ChecklistReport` tanpa panel yang
menggambarnya akan mengulanginya.

Jadi ia dikirim sebagai tool, tempat outputnya PASTI terbaca, dan jalur API
menunggu sampai ada yang benar-benar menggambarnya. Gap-nya dinyatakan di
`docs/QT-CHECKLIST.md`, bukan disembunyikan.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from app.gex import PROXIES, read


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="XAUUSD",
                        help=f"salah satu dari {sorted(PROXIES)}")
    parser.add_argument("--top", type=int, default=12)
    args = parser.parse_args()

    found, caveat = read(args.symbol, top=args.top)
    if found is None:
        # Alasannya ADALAH produknya di sini. Chain yang tidak terjangkau
        # dicetak sebagai alasan dan keluar merah, bukan sebagai GEX nol.
        json.dump({"symbol": args.symbol, "gex": None, "reason": caveat},
                  sys.stdout, indent=2)
        print()
        return 1

    json.dump({"symbol": args.symbol, "proxy_caveat": caveat,
               **asdict(found)}, sys.stdout, indent=2, default=str)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
