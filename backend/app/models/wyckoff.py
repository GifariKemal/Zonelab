"""The wire shape of a Wyckoff phase reading.

The detector in `app/wyckoff.py` works in bar indices; the wire speaks in times.
A reading, never a bias: the structure primitives these map onto are measured
null in H6 and H9.
"""

from __future__ import annotations

from pydantic import BaseModel


class WyckoffPhaseModel(BaseModel):
    kind: str  # "spring", "upthrust", "sos", "sow"
    at: int    # open time of the event bar
    level: float
    tr_low: float
    tr_high: float
    #: Open time bar pertama window range, supaya box-nya bisa digambar tanpa
    #: frontend menurunkan ulang `lookback`. Menurunkannya di sana berarti dua
    #: tempat memegang lebar window, dan yang kedua akan melenceng saat slider
    #: default berubah.
    tr_from: int
    #: Open time bar pertama yang memperdagangkan kembali `level`, atau None.
    #: Digambar sebagai objek SENDIRI, bukan bagian dari break-nya - lihat
    #: `app/wyckoff.py` untuk angka yang membuat itu wajib.
    retested_at: int | None = None


class WyckoffRangeModel(BaseModel):
    """Trading range yang SEDANG berjalan, satu per response.

    SATU BOX, DAN ITU KEPUTUSAN INK BUDGET BUKAN KEMALASAN. Tiap fase membawa
    window range-nya sendiri, dan pada `lookback` 20 sebuah deret 500 bar
    menghasilkan ratusan fase - menggambar box untuk masing-masing akan
    menutupi chart dengan kotak yang saling menumpuk, yaitu persis apa yang
    catatan ink budget di `globals.css` ukur dan tolak: "past about a third of
    the chart the boxes stop annotating price and become its background".

    Yang dibaca orang dari sebuah range breakout adalah range yang harga
    SEKARANG berdiri terhadapnya. Itu satu box: `lookback` bar terakhir.
    Window historis tiap event tetap ada di payload fase-nya untuk siapa pun
    yang mengauditnya, ia hanya tidak dicat.
    """

    time_from: int   # open time bar pertama window
    time_to: int     # open time bar terakhir yang masuk window
    low: float
    high: float
