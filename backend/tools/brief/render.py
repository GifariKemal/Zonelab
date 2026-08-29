"""Mengubah brief jadi markdown yang bisa dibaca AI agent tanpa salah kutip.

SATU ATURAN MENENTUKAN SELURUH SUSUNANNYA: tiap angka muncul bersama sumbernya,
dan bagian pertama dokumen adalah daftar hal yang TIDAK boleh disimpulkan dari
isinya. Urutan itu disengaja. Agent yang membaca "departure 3,23 ATR" dan
"killzone TIDAK" berturut turut tanpa tahu bahwa yang pertama punya walk-forward
8 dari 8 dan yang kedua tidak punya satu angka pun akan memperlakukan keduanya
sebagai bukti setara, dan itu persis kesalahan yang seluruh registry `evidence`
di repo ini ada untuk mencegahnya.
"""

from __future__ import annotations

from typing import Any



def rank_candidates(per_tf: dict, price: float) -> dict[str, Any]:
    """Rencana yang punya target, diurut menurut jarak ke harga.

    DIGABUNG DARI SEMUA TIMEFRAME, dan itu bukan kenyamanan. Versi pertama
    hanya memeringkat timeframe pertama, yang paling kasar, jadi kandidat
    terdekatnya 81,9 poin dari harga sementara timeframe eksekusi punya satu di
    10,3 poin. Eksekusi terjadi di timeframe halus dan bias dibaca di yang
    kasar; sebuah brief yang cuma memeringkat salah satunya menyembunyikan
    separuh setup yang ada.

    Yang TIDAK punya target dihitung dan dilaporkan, tidak dibuang. Sebuah
    rencana tanpa target berarti tidak ada zona lawan yang masih hidup di depan
    harga, dan `tools/execute.py` menolaknya di gerbang keenam. Itu fakta
    tentang pasarnya. Membuangnya dari brief akan membuat pembaca menyimpulkan
    engine cuma menemukan sedikit setup, padahal ia menemukan banyak dan
    menolak sebagian besar karena alasan yang bisa disebut.
    """
    with_target, without = [], []
    for tf, d in per_tf.items():
        if "error" in d:
            continue
        zmap = {z["id"]: z for z in d["drawing"]["zones"]}
        for p in d.get("plans") or []:
            z = zmap.get(p.get("zone_id"))
            if not z or z.get("state") == "broken":
                continue
            row = dict(p)
            row["timeframe"] = tf
            row["zone_kind"] = z.get("kind")
            row["zone_state"] = z.get("state")
            row["departure_atr"] = z.get("departure_atr")
            row["dealing_range_pos"] = z.get("dealing_range_pos")
            if p.get("target") is None or p.get("entry") is None:
                without.append(row)
            else:
                row["distance_to_price"] = round(abs(p["entry"] - price), 3)
                with_target.append(row)
    with_target.sort(key=lambda r: r["distance_to_price"])
    return {
        "with_target": with_target,
        "without_target_count": len(without),
        "without_target_note": (
            "rencana tanpa target berarti tidak ada zona lawan hidup di depan "
            "harga, dan gerbang keenam di tools/execute.py menolaknya. Itu "
            "penolakan yang bisa disebut, bukan ketiadaan setup."
        ),
    }


def _fmt(v: Any, nd: int = 3) -> str:
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return "n/a" if v is None else str(v)


def markdown(b: dict) -> str:
    out: list[str] = []
    w = out.append

    w(f"# Brief Zonelab: {b['symbol']}")
    w("")
    w(f"Dibuat {b['generated_at_ny']}. Pasar tutup: **{b['market_shut']}**. "
      f"Harga acuan {_fmt(b.get('price'))} pada timeframe {b.get('base_timeframe')}.")
    w("")

    # ---------------------------------------------------------------- pagar
    w("> [!CAUTION]")
    w("> **Yang TIDAK boleh disimpulkan dari dokumen ini.** Zonelab menggambar")
    w("> struktur, bukan sinyal dagang, dan itu kalimat repo-nya sendiri di")
    w("> `README.md`. Dua belas hipotesis arah yang dipraregistrasi sudah gagal")
    w("> semua. Setelah resolusi intrabar yang jujur tidak ada satu pun bagian")
    w("> sistem ini yang punya ekspektansi positif, tereplikasi, dan di luar")
    w("> sampel.")
    w("> ")
    w("> Yang bertahan satu: gerbang departure 2,0 ATR memisahkan populasi")
    w("> (+0,1105 R, Welch t=+7,19, positif di 17 dari 18 sel), dan kohort yang")
    w("> lolos gerbang mengalahkan baseline bebas sinyal (+0,125 R, t=+4,28, 8")
    w("> dari 8 sel). Tapi ekspektansi kohort itu sendiri +0,0294 R dengan")
    w("> t=+1,22, tidak bisa dibedakan dari nol.")
    w("> ")
    w("> Ringkasnya: **box mengalahkan tanpa-box, dan belum mengalahkan")
    w("> tidak-trading.** Kutip ketiganya atau jangan kutip satu pun.")
    w("")

    if b.get("failures"):
        w("> [!WARNING]")
        w("> Ada bagian yang gagal ditarik, jadi brief ini TIDAK lengkap:")
        for f in b["failures"]:
            w(f"> - `{f}`")
        w("")

    # ------------------------------------------------------------- per TF
    w("## Ringkasan per timeframe")
    w("")
    w("| TF | bar | close | lag feed | basi untuk eksekusi | zona | struktur |")
    w("|---|---:|---:|---:|---|---:|---:|")
    for tf, d in b["timeframes"].items():
        if "error" in d:
            w(f"| {tf} | - | - | - | - | - | GAGAL: {d['error']} |")
            continue
        c = d["counts"]
        w(f"| {tf} | {d['bars_returned']} | {_fmt(d['last_bar']['close'])} | "
          f"{d['feed_lag_seconds']}s | {d['feed_stale_for_execution']} | "
          f"{c.get('zones', 0)} | {c.get('structure', 0)} |")
    w("")

    for tf, d in b["timeframes"].items():
        if "error" in d:
            continue
        if d["empty_because"]:
            w(f"**{tf}, layer yang menggambar nol dan sebabnya:**")
            w("")
            for field, why in d["empty_because"].items():
                w(f"- `{field}`: {why}")
            w("")

    # -------------------------------------------------------------- siklus
    cyc = b.get("cycle", {})
    st = cyc.get("conditioning_state", {})
    if st:
        w("## Siklus, jam New York")
        w("")
        w("| Kunci | Nilai |")
        w("|---|---|")
        for k in ("amd_profile", "quarter_week", "quarter_day", "quarter_session",
                  "in_manipulation_quarter", "manipulation_done", "range_band",
                  "range_pos", "dfr_pos", "hour_utc"):
            if k in st:
                w(f"| `{k}` | {st[k]} |")
        w("")
        bias = {k: v for k, v in st.items() if k.startswith("bias_")}
        if bias:
            w("Bias per derajat: " + ", ".join(f"`{k}`={v}" for k, v in sorted(bias.items())))
            w("")
            w("> H7 mengukur kontribusi zona DI ATAS bias dan hasilnya nol, jadi")
            w("> bias di sini konteks, bukan sinyal yang berdiri sendiri.")
            w("")

    v = cyc.get("vortex")
    if v:
        w("### Dial 3-6-9")
        w("")
        w("| Ring | Sector | Root | Menyala |")
        w("|---|---:|---:|---|")
        for r in v["rings"]:
            w(f"| {r['label']} | {r['sector']}/{v['sectors']} | {r['root']} | "
              f"{'ya' if r['root'] in v['lit'] else 'tidak'} |")
        w("")
        w("Navigasi murni. Ia membaca kalender dan bukan harga, dan sebuah test")
        w("melarangnya menyentuh jalur keputusan.")
        w("")

    # ----------------------------------------------------------- fibonacci
    fib = b.get("fibonacci", {})
    w("## Fibonacci dan OTE")
    w("")
    if not fib.get("present"):
        w(f"Tidak ada: {fib.get('why')}")
    else:
        w(f"Swing {_fmt(fib['swing_low'])} ke {_fmt(fib['swing_high'])}, "
          f"rentang {_fmt(fib['span'])}. Harga di retracement "
          f"**{fib['price_retracement']}**.")
        w("")
        w("| Level | Harga |")
        w("|---|---:|")
        for name, price in fib["levels"].items():
            w(f"| {name} | {_fmt(price)} |")
        w("")
        w(f"> {fib['note']}")
    w("")

    # ----------------------------------------------------------- kandidat
    cand = b.get("candidates", {})
    w("## Kandidat dengan target")
    w("")
    rows = cand.get("with_target", [])
    if not rows:
        w("Nol rencana punya zona lawan hidup di depan harga.")
    else:
        w("| TF | jarak | sisi | kind | state | entry | stop | target | RR | departure |")
        w("|---|---:|---|---|---|---:|---:|---:|---:|---:|")
        for r in rows[:15]:
            w(f"| {r.get('timeframe')} | {_fmt(r['distance_to_price'], 1)} | "
              f"{r.get('side')} | {r.get('zone_kind')} | {r.get('zone_state')} | "
              f"{_fmt(r.get('entry'))} | {_fmt(r.get('stop'))} | {_fmt(r.get('target'))} | "
              f"{_fmt(r.get('reward_r'), 2)} | {_fmt(r.get('departure_atr'), 2)} |")
    w("")
    w(f"Rencana TANPA target: **{cand.get('without_target_count', 0)}**. "
      f"{cand.get('without_target_note', '')}")
    w("")

    # ---------------------------------------------------------------- ICT
    if b.get("ict"):
        w("## Checklist ICT untuk kandidat terdekat")
        w("")
        for r in b["ict"]:
            w(f"### `{r['zone_id']}`, met {r['met']} dari {r['total']}")
            w("")
            w(f"POI stack: supports `{r['poi_stack']['supports']}`, "
              f"conflicts {r['poi_stack']['conflicts']}, "
              f"families {r['poi_stack']['families']}")
            w("")
            w("| Klausa | Terpenuhi | Sumber | Keterangan |")
            w("|---|---|---|---|")
            for c in r["conditions"]:
                met = {True: "ya", False: "tidak", None: "tidak diketahui"}[c["met"]]
                detail = str(c["detail"]).replace("|", "/")[:90]
                w(f"| `{c['name']}` | {met} | {c['source']} | {detail} |")
            w("")

    # ---------------------------------------------------------- provenance
    prov = b.get("clause_provenance", {})
    if prov:
        w("## Provenance klausa")
        w("")
        w(f"> {prov.get('note', '')}")
        w("")
        w("**Doktrin, belum ada angkanya:** "
          + ", ".join(f"`{c}`" for c in prov.get("doctrine_clauses", [])))
        w("")
        for name, why in (prov.get("measured_against") or {}).items():
            w(f"**`{name}` sudah diukur dan hasilnya berlawanan:** {why}")
            w("")

    w("## Bukti per layer, disalin dari registry")
    w("")
    w("| Layer | Jenis | Bukti |")
    w("|---|---|---|")
    for layer in b.get("layer_evidence", []):
        ev = layer["evidence"].replace("|", "/").replace("\n", " ")
        w(f"| `{layer['id']}` | {layer['kind']} | {ev[:220]} |")
    w("")

    w("---")
    w("")
    w("Dihasilkan `python -m tools.brief`. Setiap angka di sini berasal dari")
    w("engine yang dipanggil langsung, bukan dari API, supaya brief tidak ikut")
    w("mati saat server mati.")
    return "\n".join(out) + "\n"
