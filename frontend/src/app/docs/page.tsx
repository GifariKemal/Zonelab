import type { Metadata } from "next";
import Link from "next/link";

/** The handbook.
 *
 *  A route rather than a static file in `public/`, so it is built, type
 *  checked and styled from the same tokens as the instrument it explains. A
 *  second design system for the docs would drift from the first within a week.
 *
 *  Written in Indonesian because the person who has to read it works in
 *  Indonesian, and the panel it explains is the one part of this app that
 *  cannot be understood by looking at it. */

export const metadata: Metadata = {
  title: "Panduan Zonelab",
  description:
    "Bentuk yang dicari Zonelab, setiap tombol di panel kiri, dan apa yang bertahan ketika diukur.",
};

const CONTENTS = [
  ["apa", "Apa ini sebenarnya"],
  ["bentuk", "Satu bentuk yang dicari"],
  ["atr", "ATR, satuan segalanya"],
  ["formasi", "Empat formasi"],
  ["garis", "Dua garis yang tidak setara"],
  ["siklus", "Siklus hidup zona"],
  ["panel", "Panel kiri, tombol per tombol"],
  ["mtf", "Timeframe tinggi dan penyempurnaan"],
  ["jalan", "Jalan di depan zona"],
  ["jejak", "Jejak filter"],
  ["bukti", "Apa yang sudah diukur"],
  ["tidak", "Apa yang tidak diklaim"],
  ["istilah", "Daftar istilah"],
] as const;

export default function Docs() {
  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-10 flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-bg/95 px-4 py-2 backdrop-blur">
        <Link
          href="/"
          className="text-[13px] font-semibold tracking-tight text-text transition-colors hover:text-accent"
        >
          Zonelab
        </Link>
        <span className="num text-[11px] uppercase tracking-[0.16em] text-text-faint">
          Panduan
        </span>
        <Link
          href="/"
          className="num ml-auto border border-line px-3 py-1 text-[11px] uppercase tracking-wider text-text-dim transition-colors hover:border-accent hover:text-accent"
        >
          Kembali ke chart
        </Link>
      </header>

      <div className="mx-auto grid max-w-[1180px] grid-cols-1 gap-x-12 px-5 pb-24 lg:grid-cols-[232px_minmax(0,1fr)]">
        <Masthead />

        <nav
          aria-label="Daftar isi"
          className="scroll-thin hidden self-start lg:sticky lg:top-[42px] lg:block lg:max-h-[calc(100dvh-42px)] lg:overflow-y-auto lg:py-10"
        >
          <ol className="num text-[12.5px] leading-[1.9]">
            {CONTENTS.map(([id, label], i) => (
              <li key={id}>
                <a
                  href={`#${id}`}
                  className="flex gap-2 border-l border-line py-px pl-2 pr-1 text-text-dim transition-colors hover:border-accent hover:text-accent"
                >
                  <span className="text-text-faint">
                    {String(i + 1).padStart(2, "0")}
                  </span>
                  <span>{label}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <main className="min-w-0 pt-10 text-[15.5px] leading-[1.7] text-text">
          <Apa />
          <Bentuk />
          <Atr />
          <Formasi />
          <Garis />
          <Siklus />
          <Panel />
          <Mtf />
          <Jalan />
          <Jejak />
          <Bukti />
          <Tidak />
          <Istilah />
        </main>

        <footer className="num col-span-full mt-16 flex flex-wrap gap-x-7 gap-y-2 border-t border-line-strong pt-6 text-[12px] text-text-faint">
          <span>Hak cipta 2026 PT Surya Inovasi Prioritas (SURIOTA)</span>
          <span>Angka lengkap: docs/CALIBRATION.md dan docs/FIDELITY.md</span>
          <span>Jalankan ulang: python -m tools.calibrate</span>
        </footer>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------- primitives */

function Masthead() {
  return (
    <div className="col-span-full border-b border-line-strong pb-10 pt-14">
      <div className="num text-[11px] uppercase tracking-[0.18em] text-text-faint">
        PT Surya Inovasi Prioritas - Zonelab v0.1
      </div>
      <h1 className="mt-3 max-w-[24ch] text-balance text-[clamp(30px,5.5vw,46px)] font-semibold leading-[1.06] tracking-[-0.025em]">
        Buku panduan Zonelab, dan{" "}
        <span className="text-accent">apa saja yang sudah dibuktikan</span>
      </h1>
      <p className="mt-4 max-w-[58ch] text-[17px] leading-[1.6] text-text-dim">
        Zonelab menggambar satu bentuk di chart, lalu memaksa dirinya sendiri
        membuktikan gambar itu berarti sesuatu. Halaman ini menjelaskan
        bentuknya, setiap tombol di panel kiri, dan apa yang bertahan ketika
        diukur.
      </p>
      <div className="num mt-6 flex flex-wrap gap-x-6 gap-y-1 text-[12px] text-text-faint">
        <span>
          Diperbarui <b className="font-medium text-text">15 Agustus 2026</b>
        </span>
        <span>
          Populasi ukur <b className="font-medium text-text">2707 zona</b>
        </span>
        <span>
          Audit gambar <b className="font-medium text-text">28.476 zona</b>
        </span>
      </div>
    </div>
  );
}

/** A section heading sits on a rule with a tag pinned right, the way a chart
 *  labels a price level on its own axis. */
function Level({ id, title, tag }: { id: string; title: string; tag: string }) {
  return (
    <div className="mb-5 mt-14 flex items-center gap-4 border-t border-line-strong pt-3.5">
      <h2
        id={id}
        className="flex-1 scroll-mt-14 text-balance text-[25px] font-semibold tracking-[-0.018em]"
      >
        {title}
      </h2>
      <span className="num shrink-0 border border-accent bg-accent/10 px-2 py-0.5 text-[11px] tracking-[0.1em] text-accent">
        {tag}
      </span>
    </div>
  );
}

function P({ children, lede }: { children: React.ReactNode; lede?: boolean }) {
  return (
    <p
      className={
        lede
          ? "mb-4 max-w-[62ch] text-[17px] leading-[1.6] text-text-dim"
          : "mb-4 max-w-[68ch]"
      }
    >
      {children}
    </p>
  );
}

function K({ children }: { children: React.ReactNode }) {
  return (
    <code className="num whitespace-nowrap border border-line bg-panel-2 px-1.5 py-px text-[0.88em]">
      {children}
    </code>
  );
}

function Note({
  who,
  warn,
  children,
}: {
  who: string;
  warn?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`mb-5 max-w-[68ch] border bg-panel p-4 ${
        warn ? "border-supply" : "border-line-strong"
      }`}
    >
      <span
        className={`num mb-1.5 block text-[11px] uppercase tracking-[0.14em] ${
          warn ? "text-supply" : "text-accent"
        }`}
      >
        {who}
      </span>
      <div className="[&>p:last-child]:mb-0">{children}</div>
    </div>
  );
}

function Table({
  head,
  rows,
}: {
  head: string[];
  rows: React.ReactNode[][];
}) {
  return (
    <div className="mb-5 overflow-x-auto border border-line">
      <table className="w-full border-collapse text-[14.5px]">
        <thead>
          <tr>
            {head.map((h) => (
              <th
                key={h}
                className="num whitespace-nowrap border-b border-line bg-panel px-3.5 py-2.5 text-left text-[11px] font-normal uppercase tracking-[0.12em] text-text-faint"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i}>
              {cells.map((cell, j) => (
                <td
                  key={j}
                  className="border-b border-line px-3.5 py-2.5 align-top last:border-b-0"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const N = ({ children }: { children: React.ReactNode }) => (
  <span className="num whitespace-nowrap text-[13px]">{children}</span>
);
const Yes = ({ children }: { children: React.ReactNode }) => (
  <span className="font-semibold text-demand">{children}</span>
);
const No = ({ children }: { children: React.ReactNode }) => (
  <span className="font-semibold text-supply">{children}</span>
);
const Off = ({ children }: { children: React.ReactNode }) => (
  <span className="text-text-faint">{children}</span>
);

/* ------------------------------------------------------------- 01 */

function Apa() {
  return (
    <section>
      <Level id="apa" title="Apa ini sebenarnya" tag="MULAI" />
      <P lede>
        Zonelab adalah mesin gambar teknikal yang berjalan di mesin lokal. Ia
        memuat data pasar, memindai bar-nya, dan mengembalikan bentuk yang harus
        digambar beserta bukti pembentuknya.
      </P>
      <P>
        Prinsipnya satu kalimat: <b>gambar yang tidak bisa dijelaskan tidak
        layak digambar.</b> Karena itu setiap zona menyimpan asal-usulnya, yaitu
        indeks bar mana yang membentuknya, ukurannya dalam ATR, dan rincian
        skornya. Setiap penyaringan juga dilaporkan. Chart yang kosong karena
        memang tidak ada pola berbeda dari chart yang kosong karena filternya
        terlalu ketat, dan panel kiri membedakan keduanya.
      </P>
      <P>
        Yang tidak dilakukan Zonelab: ia bukan bot, tidak mengirim order, tidak
        menghitung untung rugi, dan tidak memodelkan biaya transaksi. Ia
        menggambar, lalu mengukur apakah gambarnya informatif.
      </P>
    </section>
  );
}

/* ------------------------------------------------------------- 02 */

function Bentuk() {
  return (
    <section>
      <Level id="bentuk" title="Satu bentuk yang dicari" tag="DASAR" />
      <P>
        Seluruh aplikasi ini mencari satu bentuk, dan hanya itu. Bentuknya tiga
        babak yang berurutan.
      </P>

      <figure className="my-7">
        <svg
          viewBox="0 0 720 250"
          role="img"
          aria-label="Tiga babak sebuah zona: kaki masuk berupa candle besar, base berupa candle kecil yang menjadi kotak zona, lalu kaki keluar yang berangkat menjauh"
          className="h-auto w-full max-w-full text-text"
        >
          <defs>
            <marker
              id="ah"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
            </marker>
          </defs>

          <rect
            x="228" y="128" width="150" height="46"
            className="fill-demand/15 stroke-demand" strokeWidth="1.5"
          />
          <text x="234" y="122" className="fill-demand" fontSize="12" fontFamily="monospace">
            kotak zona = base
          </text>

          <g stroke="currentColor" strokeWidth="1.4" fill="currentColor">
            <line x1="58" y1="30" x2="58" y2="72" /><rect x="52" y="36" width="12" height="30" />
            <line x1="88" y1="52" x2="88" y2="98" /><rect x="82" y="58" width="12" height="34" />
            <line x1="118" y1="76" x2="118" y2="126" /><rect x="112" y="82" width="12" height="38" />
            <line x1="148" y1="104" x2="148" y2="150" /><rect x="142" y="110" width="12" height="34" />
            <line x1="178" y1="122" x2="178" y2="166" /><rect x="172" y="128" width="12" height="32" />
            <line x1="208" y1="132" x2="208" y2="172" /><rect x="202" y="138" width="12" height="30" />
          </g>

          <g stroke="currentColor" strokeWidth="1.4" fill="none">
            <line x1="242" y1="136" x2="242" y2="168" /><rect x="236" y="146" width="12" height="10" />
            <line x1="272" y1="134" x2="272" y2="170" /><rect x="266" y="150" width="12" height="9" />
            <line x1="302" y1="138" x2="302" y2="166" /><rect x="296" y="144" width="12" height="11" />
            <line x1="332" y1="132" x2="332" y2="172" /><rect x="326" y="149" width="12" height="10" />
            <line x1="362" y1="136" x2="362" y2="169" /><rect x="356" y="145" width="12" height="10" />
          </g>

          <g stroke="currentColor" strokeWidth="1.4" fill="currentColor">
            <line x1="398" y1="102" x2="398" y2="146" /><rect x="392" y="108" width="12" height="32" />
            <line x1="428" y1="74" x2="428" y2="120" /><rect x="422" y="80" width="12" height="34" />
            <line x1="458" y1="48" x2="458" y2="94" /><rect x="452" y="54" width="12" height="34" />
            <line x1="488" y1="26" x2="488" y2="70" /><rect x="482" y="32" width="12" height="32" />
            <line x1="518" y1="16" x2="518" y2="52" /><rect x="512" y="22" width="12" height="24" />
          </g>

          <line x1="560" y1="151" x2="560" y2="30" className="stroke-accent" strokeWidth="1.4" markerEnd="url(#ah)" />
          <line x1="548" y1="151" x2="572" y2="151" className="stroke-accent" strokeWidth="1.4" />
          <text x="580" y="88" className="fill-accent" fontSize="12" fontFamily="monospace">kaki keluar harus</text>
          <text x="580" y="104" className="fill-accent" fontSize="12" fontFamily="monospace">lari sejauh ini</text>
          <text x="580" y="120" className="fill-accent" fontSize="12" fontFamily="monospace">(Departure gate)</text>

          <line x1="46" y1="206" x2="216" y2="206" stroke="currentColor" strokeWidth="1" opacity="0.45" />
          <line x1="228" y1="206" x2="378" y2="206" className="stroke-demand" strokeWidth="1.5" />
          <line x1="390" y1="206" x2="530" y2="206" stroke="currentColor" strokeWidth="1" opacity="0.45" />
          <text x="131" y="228" fontSize="12.5" fontFamily="monospace" fill="currentColor" textAnchor="middle" opacity="0.75">1. kaki masuk</text>
          <text x="303" y="228" fontSize="12.5" fontFamily="monospace" className="fill-demand" textAnchor="middle">2. base</text>
          <text x="460" y="228" fontSize="12.5" fontFamily="monospace" fill="currentColor" textAnchor="middle" opacity="0.75">3. kaki keluar</text>
        </svg>
        <figcaption className="mt-3 max-w-[62ch] text-[13.5px] leading-[1.6] text-text-dim">
          Harga bergerak keras, berhenti sebentar, lalu bergerak keras lagi.
          Yang digambar adalah babak tengahnya. Candle base sengaja digambar
          kosong di sini karena justru kekecilannya yang membuatnya base.
        </figcaption>
      </figure>

      <P>
        Alasan metodenya: kalau harga berhenti sebentar lalu berangkat dengan
        keras, ada yang belum selesai di titik berhenti itu. Kalau harga kembali
        ke sana, sisa pesanan itu mungkin masih ada dan bereaksi lagi.
      </P>

      <Note who="Perlu diketahui">
        <P>
          Cerita sisa pesanan institusional itu <b>tidak bisa diverifikasi dari
          data harga</b> dan memang diperdebatkan. Yang bisa diuji hanya apakah
          kotaknya informatif. Itulah yang diukur, dan hasilnya ada di bagian
          bukti.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 03 */

function Atr() {
  return (
    <section>
      <Level id="atr" title="ATR, satuan segalanya" tag="SATUAN" />
      <P>
        ATR adalah rata-rata jarak gerak satu candle belakangan ini. Kalau emas
        sedang sepi, ATR-nya mungkin 2 dolar; kalau sedang liar, 8 dolar.
      </P>
      <P>
        <b>Setiap ambang di panel dinyatakan dalam ATR, tidak pernah dalam angka
        absolut.</b> Sebabnya mekanis: candle 5 dolar adalah ledakan di sesi
        sepi dan sekadar derau di sesi liar. Ambang berupa 5 dolar akan salah di
        separuh hari perdagangan.
      </P>
      <P>
        Jadi bila tertulis <K>2 ATR</K>, bacalah sebagai dua kali gerak normal
        saat ini.
      </P>
      <Note who="Detail yang penting">
        <P>
          ATR pembanding selalu dibaca dari bar <b>sebelum</b> objek yang
          diukur. ATR Wilder pada bar ke-i sudah memuat gerak bar itu sendiri,
          jadi membandingkan sebuah candle dengan ATR-nya sendiri justru membuat
          candle terbesar lebih sulit lolos sebagai impuls. Hal yang sama
          berlaku untuk tinggi base.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 04 */

function Formasi() {
  return (
    <section>
      <Level id="formasi" title="Empat formasi" tag="NAMA" />
      <P>
        Nama yang muncul di chart hanyalah singkatan arah kedua kakinya. Arah
        kaki masuk dan kaki keluar menentukan namanya, dan apakah zonanya demand
        atau supply.
      </P>
      <P>
        Dua kode lain muncul kalau kamu menyalakan lapisannya di menu Layers,
        panel kiri. <K>FVG</K> adalah fair value gap: tiga bar berurutan yang wick
        luarnya tidak pernah bertemu, jadi ada pita harga yang dilompati. Itu
        satu-satunya objek di seluruh kosakata SMC yang definisinya tidak
        menyisakan ruang tafsir. <K>OB</K> adalah order block: candle
        berlawanan warna terakhir sebelum gerakan impulsif. Yang itu
        diperdebatkan, dan pilihan yang diambil di sini dinyatakan di kodenya
        alih-alih disamarkan sebagai doktrin.
      </P>
      <Table
        head={["Kode", "Kaki masuk", "Kaki keluar", "Sisi", "Watak"]}
        rows={[
          [<N key="a">DBR</N>, "turun", "naik", <Yes key="b">demand</Yes>, "pembalikan"],
          [<N key="c">RBR</N>, "naik", "naik", <Yes key="d">demand</Yes>, "penerusan"],
          [<N key="e">RBD</N>, "naik", "turun", <No key="f">supply</No>, "pembalikan"],
          [<N key="g">DBD</N>, "turun", "turun", <No key="h">supply</No>, "penerusan"],
        ]}
      />
      <P>
        <K>D</K> untuk Drop, <K>R</K> untuk Rally, <K>B</K> untuk Base di
        tengahnya. Zona demand digambar hijau di bawah harga, supply merah di
        atasnya.
      </P>
    </section>
  );
}

/* ------------------------------------------------------------- 05 */

function Garis() {
  return (
    <section>
      <Level id="garis" title="Dua garis yang tidak setara" tag="GEOMETRI" />
      <P>
        Kotaknya punya dua tepi dan keduanya berbeda peran. Ini bagian yang
        paling sering salah digambar, dan salahnya mahal.
      </P>

      <figure className="my-7">
        <svg
          viewBox="0 0 700 268"
          role="img"
          aria-label="Anatomi zona demand: proximal di atas sebagai titik masuk, distal di bawah pada ujung wick terendah, dan stop diletakkan di luar distal"
          className="h-auto w-full max-w-full text-text"
        >
          <line x1="60" y1="24" x2="60" y2="214" stroke="currentColor" strokeWidth="1" opacity="0.25" />
          <rect x="90" y="96" width="330" height="72" className="fill-demand/12 stroke-demand" strokeWidth="1" />

          <g stroke="currentColor" strokeWidth="1.5" fill="none">
            <line x1="140" y1="104" x2="140" y2="150" /><rect x="133" y="112" width="14" height="16" />
            <line x1="200" y1="100" x2="200" y2="166" /><rect x="193" y="116" width="14" height="14" />
            <line x1="260" y1="108" x2="260" y2="142" /><rect x="253" y="114" width="14" height="15" />
            <line x1="320" y1="102" x2="320" y2="158" /><rect x="313" y="110" width="14" height="18" />
            <line x1="380" y1="106" x2="380" y2="146" /><rect x="373" y="115" width="14" height="14" />
          </g>

          <line x1="90" y1="96" x2="470" y2="96" className="stroke-accent" strokeWidth="2" />
          <text x="478" y="93" fontSize="12.5" fontFamily="monospace" className="fill-accent">PROXIMAL</text>
          <text x="478" y="109" fontSize="11.5" fontFamily="monospace" fill="currentColor" opacity="0.7">tepi yang harga temui</text>
          <text x="478" y="123" fontSize="11.5" fontFamily="monospace" fill="currentColor" opacity="0.7">lebih dulu, titik masuk</text>

          <line x1="90" y1="168" x2="470" y2="168" className="stroke-supply" strokeWidth="2" />
          <text x="478" y="165" fontSize="12.5" fontFamily="monospace" className="fill-supply">DISTAL</text>
          <text x="478" y="181" fontSize="11.5" fontFamily="monospace" fill="currentColor" opacity="0.7">selalu ujung wick,</text>
          <text x="478" y="195" fontSize="11.5" fontFamily="monospace" fill="currentColor" opacity="0.7">tidak pernah badan</text>

          <line x1="110" y1="196" x2="420" y2="196" stroke="currentColor" strokeWidth="1.5" strokeDasharray="5 4" opacity="0.75" />
          <text x="110" y="214" fontSize="12" fontFamily="monospace" fill="currentColor" opacity="0.75">stop diletakkan DI LUAR distal</text>

          <line x1="110" y1="140" x2="420" y2="140" className="stroke-supply" strokeWidth="1.2" strokeDasharray="3 3" opacity="0.6" />
          <text x="110" y="256" fontSize="12" fontFamily="monospace" className="fill-supply">garis putus merah = distal di badan candle. Stop jatuh DI DALAM base.</text>
        </svg>
        <figcaption className="mt-3 max-w-[62ch] text-[13.5px] leading-[1.6] text-text-dim">
          Zona demand. Proximal boleh berpindah antara ujung wick dan ujung
          badan, itulah pilihan agresif lawan konservatif. Distal tidak pernah
          berpindah, karena stop diletakkan di luarnya dan distal yang digambar
          di badan candle menaruh stop di dalam base yang seharusnya ia
          lindungi.
        </figcaption>
      </figure>

      <Note who="Cacat yang pernah ada di sini">
        <P>
          Parameter lama menggeser <b>kedua</b> tepi sekaligus, jadi mode body
          bukan varian konservatif maupun agresif, melainkan varian yang tidak
          ada dalam metode mana pun. Sudah diperbaiki dan diverifikasi pada
          28.476 zona: <b>nol pelanggaran</b>.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 06 */

function Siklus() {
  return (
    <section>
      <Level id="siklus" title="Siklus hidup zona" tag="STATUS" />
      <P>
        Setelah zona lahir, setiap bar sesudahnya diputar ulang untuk melihat
        apa yang harga lakukan padanya.
      </P>

      <figure className="my-7">
        <svg
          viewBox="0 0 700 176"
          role="img"
          aria-label="Empat status zona: fresh menjadi tested saat harga masuk, tested menjadi mitigated saat harga memakan separuh zona, dan status mana pun menjadi broken saat sebuah bar menutup melewati distal"
          className="h-auto w-full max-w-full text-text"
        >
          <defs>
            <marker id="ah2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
            </marker>
            <marker id="ah3" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" className="fill-supply" />
            </marker>
          </defs>

          <g fontSize="12.5" fontFamily="monospace">
            <rect x="16" y="26" width="126" height="40" fill="none" className="stroke-demand" strokeWidth="1.5" />
            <text x="79" y="51" className="fill-demand" textAnchor="middle">fresh</text>
            <rect x="216" y="26" width="126" height="40" fill="none" stroke="currentColor" strokeWidth="1.5" />
            <text x="279" y="51" fill="currentColor" textAnchor="middle">tested</text>
            <rect x="416" y="26" width="126" height="40" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
            <text x="479" y="51" fill="currentColor" textAnchor="middle" opacity="0.6">mitigated</text>
            <rect x="288" y="126" width="126" height="40" fill="none" className="stroke-supply" strokeWidth="1.5" />
            <text x="351" y="151" className="fill-supply" textAnchor="middle">broken</text>
          </g>

          <line x1="142" y1="46" x2="210" y2="46" stroke="currentColor" strokeWidth="1.4" markerEnd="url(#ah2)" />
          <text x="176" y="38" fontSize="11" fontFamily="monospace" fill="currentColor" textAnchor="middle" opacity="0.8">harga masuk</text>

          <line x1="342" y1="46" x2="410" y2="46" stroke="currentColor" strokeWidth="1.4" markerEnd="url(#ah2)" />
          <text x="376" y="38" fontSize="11" fontFamily="monospace" fill="currentColor" textAnchor="middle" opacity="0.8">termakan 50%</text>

          <path d="M 79 66 L 79 146 L 282 146" fill="none" className="stroke-supply" strokeWidth="1.4" markerEnd="url(#ah3)" />
          <path d="M 479 66 L 479 146 L 420 146" fill="none" className="stroke-supply" strokeWidth="1.4" markerEnd="url(#ah3)" />
          <text x="351" y="112" fontSize="11" fontFamily="monospace" className="fill-supply" textAnchor="middle">sebuah bar MENUTUP melewati distal</text>
        </svg>
        <figcaption className="mt-3 max-w-[62ch] text-[13.5px] leading-[1.6] text-text-dim">
          Yang mematikan zona adalah penutupan melewati distal, bukan sekadar
          wick yang menusuk lewat. Bar berurutan yang berdiam di dalam zona
          dihitung sebagai satu kunjungan, bukan lima.
        </figcaption>
      </figure>
    </section>
  );
}

/* ------------------------------------------------------------- 07 */

function Panel() {
  return (
    <section>
      <Level id="panel" title="Panel kiri, tombol per tombol" tag="RUJUKAN" />
      <P lede>
        Panel kiri sekarang satu menu: tiap lapisan punya satu sakelar, dan
        knob-nya baru muncul di bawahnya kalau lapisan itu menyala. Daftarnya
        dibaca dari registry backend, bukan diketik di frontend, jadi urutannya
        adalah urutan gambar. Yang di bawah ini knob milik supply dan demand
        beserta overlay struktur; jujurnya hanya dua yang perlu kamu sentuh, dan
        kolom terakhir menandai mana yang punya bukti di belakangnya.
      </P>

      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Knob supply dan demand, menentukan apa yang dianggap gerakan keras
      </h3>
      <Table
        head={["Kontrol", "Artinya", "Kalau digeser", "Bukti"]}
        rows={[
          [
            <N key="a">Proximal line</N>,
            "Tepi mana yang jadi titik masuk. Wick adalah ujung bayangan, Body ujung badan candle.",
            "Wick memberi kotak lebih lebar sehingga lebih mudah tersentuh. Body lebih sempit. Distal tidak ikut bergerak.",
            <Off key="b">doktrin tidak memutuskan</Off>,
          ],
          [
            <N key="c">Impulse size</N>,
            "Rentang sebuah candle harus melebihi sekian ATR untuk disebut kaki.",
            "Turunkan untuk menemukan lebih banyak zona berkaki lemah. Naikkan untuk sedikit zona berkaki meyakinkan.",
            <Off key="d">belum diukur</Off>,
          ],
          [
            <N key="e">Impulse body</N>,
            "Badan sebagai porsi rentang candle itu sendiri.",
            "Memisahkan candle tegas dari doji. Doji besar bukan gerakan, ia keraguan.",
            <Off key="f">belum diukur</Off>,
          ],
          [
            <N key="g">Departure gate</N>,
            "Kaki keluar harus lari sejauh ini dari zona.",
            "Di bawah ambang, zonanya dibuang. Bawaan 2,0 ATR.",
            <Yes key="h">TERVALIDASI</Yes>,
          ],
          [
            <N key="i">Profit margin</N>,
            "Perjalanan kaki keluar sebagai kelipatan tinggi kotaknya sendiri. Aturan 3:1 milik doktrin.",
            "Di atas 0 ia menyaring. Bawaannya 0, jadi mati.",
            <No key="j">tidak bertahan</No>,
          ],
          [
            <N key="k">Road ahead</N>,
            "Jarak kosong dari zona ke zona lawan hidup terdekat, dalam satuan tinggi zona sendiri.",
            "Di atas 0 ia menyaring dan menandai zona yang terkurung. Bawaannya 0.",
            <Off key="l">memeringkat, gagal jadi gerbang</Off>,
          ],
        ]}
      />

      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Knob supply dan demand, menentukan apa yang dianggap berhenti
      </h3>
      <Table
        head={["Kontrol", "Artinya", "Kalau digeser", "Bukti"]}
        rows={[
          [
            <N key="a">Max base bars</N>,
            "Jeda maksimal berapa candle.",
            "Konsolidasi lebih panjang dipotong ke ekornya, karena dari bar-bar itulah gerakan benar-benar berangkat.",
            <Off key="b">-</Off>,
          ],
          [
            <N key="c">Max base height</N>,
            "Jeda yang lebih tinggi dari sekian ATR ditolak.",
            "Diukur terhadap volatilitas sebelum base, supaya base tinggi tidak bisa membela dirinya sendiri.",
            <Off key="d">-</Off>,
          ],
          [
            <N key="e">Max base drift</N>,
            "Perjalanan satu arah melintasi base sebagai porsi tingginya sendiri.",
            "Membuang tangga yang menyamar jadi base. Setel 1,0 untuk mematikan.",
            <Yes key="f">NYALA, atas dasar kesetiaan</Yes>,
          ],
          [
            <N key="g">ATR period</N>,
            "Berapa candle dipakai menghitung ATR.",
            "Jarang perlu disentuh. Bawaan 14 sama dengan MetaTrader dan TradingView.",
            <Off key="h">-</Off>,
          ],
        ]}
      />

      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Knob supply dan demand, daur hidup dan tampilan
      </h3>
      <Table
        head={["Kontrol", "Artinya"]}
        rows={[
          [<N key="a">Mitigation depth</N>, "Seberapa dalam harga boleh memakan zona sebelum dianggap habis terpakai."],
          [<N key="b">Show mitigated</N>, "Tampilkan zona yang sudah termakan sebagian. Nyala secara bawaan."],
          [<N key="c">Show broken</N>, "Tampilkan zona yang sudah ditembus. Mati secara bawaan."],
          [<N key="d">Zones per side</N>, "Berapa banyak digambar per sisi, terbaru lebih dulu. Berlaku per detektor DAN per sisi, jadi dengan tiga detektor menyala angka 6 mengizinkan 36 kotak. Default diturunkan dari 12 ke 6 pada 2026-08-16 karena 12 mengecat 39,6% chart rata-rata, dan kotak yang mengecat separuh chart bukan anotasi lagi."],
          [<N key="e">Merge overlap</N>, "Dua zona yang bertumpuk lebih dari ini digabung jadi satu. Hanya tampilan."],
        ]}
      />

      <Note who="Jebakan yang pernah memakan korban" warn>
        <P>
          <K>Zones per side</K> memilih berdasarkan <b>waktu</b>, bukan mutu. Ia
          menyimpan yang terbaru. Itu benar untuk chart, tetapi setiap
          pengukuran yang lewat batas ini diam-diam berubah menjadi pengukuran
          ekor riwayat. Bug itu pernah membuat seluruh angka kalibrasi dihitung
          pada 9,6% terakhir tiap deret sambil mengklaim 20.000 bar. Sekarang
          nilai <K>0</K> berarti tanpa batas, dan hanya nol yang berarti mati.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 08 */

function Mtf() {
  return (
    <section>
      <Level id="mtf" title="Timeframe tinggi dan penyempurnaan" tag="HTF" />
      <P>
        Metodenya bersifat atas ke bawah: <b>zona milik timeframe lebih tinggi,
        entri milik yang lebih rendah.</b> Picker <K>HTF</K> di header menghitung
        zona dari bar hasil agregasi lalu memproyeksikannya ke chart.
      </P>
      <P>
        <b>Lima detektor kotak bisa dibaca di timeframe lebih tinggi</b>, bukan
        satu: supply dan demand, fair value gap, order block, inverted FVG, dan
        breaker. Layer yang tidak bisa - cycle grid, defining range, opening gap -
        sudah membawa derajatnya sendiri, jadi tidak ada timeframe lebih tinggi
        untuk membacanya, dan panel mengatakan itu daripada diam.
      </P>
      <ul className="mb-4 max-w-[68ch] list-disc space-y-2 pl-5">
        <li>
          <b>Bucket ditambatkan ke epoch, bukan ke bar pertama di jendela.</b>{" "}
          Kalau ditambatkan ke jendela, setiap zona HTF akan bergeser saat kamu
          mengubah jumlah bar, dan itu terlihat persis seperti bug detektor.
        </li>
        <li>
          <b>Bar HTF terakhir dibuang bila belum selesai.</b> Bar yang masih
          terbentuk high dan low-nya masih bergerak, jadi zona di atasnya akan
          berpindah sendiri.
        </li>
        <li>
          <b>Bucket kosong tidak diciptakan.</b> Akhir pekan meninggalkan lubang
          pada emas dan FX. Mengisinya dengan bar datar akan mengarang justru
          bentuk konsolidasi yang dicari detektor ini.
        </li>
        <li>
          <b>Bar mingguan digeser fasenya ke hari Minggu.</b> Jangkar epoch benar
          untuk 4h dan 1d dan salah fasenya untuk 1w: 1 Januari 1970 hari Kamis,
          jadi pekan tanpa koreksi berjalan Kamis ke Rabu sementara seri W1 broker
          mulai Minggu. Sebelum dikoreksi, setiap zona mingguan salah empat hari.
        </li>
      </ul>

      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Picker Session
      </h3>
      <P>
        Broker yang harinya mulai pukul 22:00 atau 01:00 menaruh candle H4 dan
        D1-nya di grid berbeda dari agregat berbasis UTC. Akibatnya zona
        tergambar <b>satu candle meleset</b> dari zona yang sama di terminalnya.
        Ini penyebab paling umum keluhan zona H4-nya geser satu, dan tidak
        terlihat kecuali kedua chart dibandingkan berdampingan.
      </P>

      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Picker Refine
      </h3>
      <P>
        Base H4 selebar empat candle H1, dan harga jarang berbalik dari
        keempatnya. Ia berbalik dari segelintir bar timeframe rendah tempat
        gerakan benar-benar berhenti. Refinement mengganti kotak kasar itu
        dengan jeda di dalamnya, memakai bar chart yang sudah ada.
      </P>
      <Table
        head={["Reward", "Digambar", "Disempurnakan", "Selisih", "Uji eksak"]}
        rows={[
          ["0,5 ATR", <N key="a">84,2%</N>, <N key="b">80,1%</N>, <N key="c"><No>-4,2 pp</No></N>, <N key="d">p&lt;0,0001</N>],
          ["1,0 ATR", <N key="e">68,4%</N>, <N key="f">62,6%</N>, <N key="g"><No>-5,8 pp</No></N>, <N key="h">p&lt;0,0001</N>],
          ["2,0 ATR", <N key="i">47,7%</N>, <N key="j">37,9%</N>, <N key="k"><No>-9,9 pp</No></N>, <N key="l">p&lt;0,0001</N>],
        ]}
      />
      <P>
        Jarak stop menyusut ke <b>48,6%</b> dari aslinya, jadi reward per satuan
        risiko naik ke sekitar <b>2,2 kali</b>. Refinement membeli leverage dan
        membayarnya dengan tingkat bertahan.
      </P>
      <Note who="Kenapa penurunan itu bukan berarti lebih buruk">
        <P>
          Tinggi kotak sendiri meramalkan hasil: kuartil terpendek bertahan
          52,4% dan tertinggi 61,4%, semata karena stop yang jauh lebih jarang
          tersentuh. Refinement memotong tinggi ke 48,6%, yaitu memindahkan zona
          ke kuartil terpendek, dan selisih 9,9 poin persen itu <b>hampir
          persis</b> rentang yang dijelaskan geometri bracket. Tidak ada
          informasi yang hilang, hanya risiko yang dipindahkan.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 09 */

function Jalan() {
  return (
    <section>
      <Level id="jalan" title="Jalan di depan zona" tag="RUANG" />
      <P>
        Zona demand yang bagus dengan zona supply segar menempel 1,5 kali
        tingginya di atas bukanlah peluang, sebersih apa pun ia terbentuk.
        Slider <K>Road ahead</K> mengukur ruang itu.
      </P>
      <P>
        Yang membuatnya berbeda dari semua status lain: jalan bisa tertutup{" "}
        <b>tanpa harga bergerak sama sekali</b>, cukup ada zona lawan baru
        terbentuk di jalurnya. Artinya validitas harus dievaluasi ulang pada
        peristiwa yang belum pernah didengarkan kode ini, yaitu <b>zona lain
        lahir</b>. Zona yang terkurung digambar lebih redup dan inspekturnya
        mencatat kapan jalannya tertutup.
      </P>
      <Note who="Ini formalisasi kami, bukan doktrin" warn>
        <P>
          Penelusuran sumber tidak menemukan <b>satu pun sumber primer</b> yang
          menyatakan zona menjadi tidak valid ketika zona lawan baru terbentuk.
          Paten Online Trading Academy, yang merupakan kodifikasi algoritmik
          penuh metode ini, tidak memuat logika itu dan tidak memuat ambang
          reward banding risk sama sekali. Setiap kriteria invalidasi yang
          diterbitkan digerakkan harga.
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 10 */

function Jejak() {
  return (
    <section>
      <Level id="jejak" title="Jejak filter" tag="DIAGNOSA" />
      <P>
        Bagian paling berguna di panel dan paling sering dilewat. Ia menjawab
        satu pertanyaan: chart ini kosong karena memang tidak ada pola, atau
        karena filternya terlalu ketat?
      </P>
      <Table
        head={["Baris", "Artinya"]}
        rows={[
          [<N key="a">Formations found</N>, "Berapa kandidat tiga babak yang ditemukan sebelum penyaringan apa pun."],
          [<N key="b">Base too tall</N>, "Dibuang karena jedanya lebih tinggi dari batas."],
          [<N key="c">Base drifted</N>, "Dibuang karena jedanya ternyata tangga menanjak atau menurun."],
          [<N key="d">Weak departure</N>, "Dibuang karena kaki keluarnya tidak lari cukup jauh. Biasanya baris terbesar."],
          [<N key="e">Thin profit margin</N>, "Dibuang oleh aturan 3:1, kalau kamu menyalakannya."],
          [<N key="f">Road shut</N>, "Dibuang karena jalan ke zona lawan terlalu sempit."],
          [<N key="g">Merged as duplicate</N>, "Digabung karena bertumpuk dengan zona lain di harga yang sama."],
          [<N key="h">Hidden by state</N>, "Ada, tetapi disembunyikan karena statusnya broken atau mitigated."],
          [<N key="i">Drawn</N>, "Yang akhirnya tergambar."],
        ]}
      />
    </section>
  );
}

/* ------------------------------------------------------------- 11 */

function Bukti() {
  return (
    <section>
      <Level id="bukti" title="Apa yang sudah diukur" tag="BUKTI" />
      <P lede>
        Diukur pada 20.000 bar untuk masing-masing dari lima deret, dengan skor
        dibaca sebagaimana diketahui tepat sebelum harga menyentuh zona, bukan
        sesudahnya.
      </P>
      <Table
        head={["Klaim", "Putusan"]}
        rows={[
          [
            "Kotaknya digambar persis di ekstrem base-nya",
            <span key="a"><Yes>Terbukti.</Yes> Galat tepi terburuk 0,000 pada 28.476 zona, nol pelanggaran aturan.</span>,
          ],
          [
            "Zona bertahan lebih sering daripada level di harga acak",
            <span key="b"><Yes>Terbukti.</Yes> +19 sampai +35 poin persen di tiga geometri.</span>,
          ],
          [
            "Gerbang departure menyaring sesuatu yang nyata",
            <span key="c">
              <Yes>Terbukti, sebagai penyortir.</Yes> Di instrumen yang benar-benar
              ditradingkan, di bar 5 menit: 43,0% lawan 40,2%, dan selisih
              ketahanan itu <b>tidak</b> signifikan. Yang signifikan ekspektansinya,
              +0,124 R dengan t=+4,82. Pasangan 85,8% lawan 64,4% yang dulu ada di
              sini diukur pada PAXG, BTC dan ETH dari Binance, jadi ia milik pasar
              lain.
            </span>,
          ],
          [
            "Gerbang itu bertahan di bar yang belum pernah dilihat",
            <span key="d"><Yes>Terbukti.</Yes> Benar arah di 8 dari 8 potongan waktu, di ketiga geometri.</span>,
          ],
          [
            "Tinggi kotak sendiri meramalkan hasil",
            <span key="e"><No>Terbukti, dan itu masalah.</No> 52,4% lawan 61,4% dari kuartil terpendek ke tertinggi. Itu geometri, bukan pasar.</span>,
          ],
          [
            "Skor komposit memeringkat zona yang akan bertahan",
            <span key="f"><No>Terbantah.</No> AUC 0,46 dan 0,48, yaitu memeringkat terbalik.</span>,
          ],
          [
            "Odds enhancer doktrin memeringkat sesuatu",
            <span key="g"><No>Terbantah untuk hampir semuanya.</No> Kerapatan base, kepadatan, irisan antar bar, volume kaki keluar dan posisi kurva semuanya berbalik tanda ketika target diubah, yang hanya bisa terjadi bila yang diukur adalah tinggi kotak.</span>,
          ],
          [
            "Zona bersarang di timeframe tinggi lebih kuat",
            <span key="h"><No>Tidak ada manfaat terukur.</No> +0,2 sampai +0,9 poin persen, tidak signifikan, pada 2707 zona.</span>,
          ],
          [
            "Harga berbalik di zona lebih sering daripada di kotak acak",
            <span key="i"><No>Terbantah.</No> Pembalikannya nyata, tetapi kotak acak melakukannya sama banyak (p=0,73), dan tetap begitu ketika besar lari masuk disamakan.</span>,
          ],
          [
            "Zona meramalkan arah 40 bar ke depan",
            <span key="j"><No>Terbantah.</No> Perpindahan bersihnya nol di semua kelompok.</span>,
          ],
          [
            "Jalan di depan zona meramalkan arah",
            <span key="k"><No>Terbantah.</No> Jalan terpanjang dikurangi terpendek +0,053 ATR, p=0,88. Faktor itu meramalkan ketahanan, bukan arah.</span>,
          ],
          [
            "Zona yang sudah beberapa kali disentuh jadi lebih lemah",
            <span key="l"><No>Terbantah setelah tampak sangat kuat.</No> Mentahnya -27 poin persen. Di dalam pita umur yang sama: 77,2%, 77,2%, 77,1% untuk sentuhan 1, 2, 3. Peluruhannya ada di waktu, bukan di sentuhan.</span>,
          ],
          [
            "FVG dan Order Block menandai sesuatu yang nyata",
            <span key="n"><Yes>Terbukti terhadap placebo.</Yes> +10 sampai +25 poin persen di ketiga geometri, n antara 12.700 dan 21.600. Tetapi itu standar yang lebih rendah: kontrol berat dan walk-forward hanya ada untuk Supply dan Demand.</span>,
          ],
          [
            "Harga meneruskan arah yang membuat kotaknya",
            <span key="o"><No>Terbantah.</No> Horizon utama 12 bar ditetapkan di depan: t = 1,01 untuk FVG, 0,13 untuk Order Block, 0,27 untuk Supply dan Demand. Kriterianya menuntut t di atas 3,0. Ini hipotesis arah keempat yang gagal.</span>,
          ],
          [
            "Struktur pasar (BOS, CHoCH) membawa bias arah",
            <span key="p"><No>Tidak dikonfirmasi.</No> Pada swing besar DELTA +0,549 ATR dengan t = 2,27, hasil arah terkuat yang pernah ada di sini. Paruhnya membunuhnya: +1,02 lalu +0,08. Itu tanda tangan window fit.</span>,
          ],
          [
            "Zona searah bias struktur lebih baik daripada yang melawan",
            <span key="q"><No>Tidak dikonfirmasi, tetapi cara gagalnya yang penting.</No> FVG lolos ketiga kriteria: demand +0,405 (t = 4,63), supply +0,266 (t = 3,06), kedua paruh positif. Lalu kontrolnya jalan, dan bar acak tanpa kotak apa pun sudah memisah +0,271 dan +0,184. Yang ditambahkan zonanya cuma +0,134 (t = 1,25), dan negatif untuk dua detektor lain.</span>,
          ],
          [
            "Kotak yang sudah ditembus bekerja terbalik (breaker block)",
            <span key="r"><No>Terbantah.</No> Uji arah pertama yang mengganti populasinya, bukan cuma variabel pengkondisinya. Dibanding kontrol yang cuma tahu gerak 20 bar terakhir, kotaknya menambah -0,179, -0,165, dan -0,274; ketiganya signifikan negatif. Tahu kotaknya terbalik membuat tebakan arah lebih buruk daripada tidak tahu.</span>,
          ],
          [
            "Sweep lalu MSS membawa arah",
            <span key="s"><No>Terbantah.</No> t = -0,79 dan -0,12, tanda berbalik antar paruh, dan sweep-nya menambah negatif atas break biasa. Pada struktur besar konjungsinya cuma terjadi 7 dan 43 kali, terlalu langka untuk diuji sama sekali.</span>,
          ],
          [
            "Umur zona memisahkan hasil",
            <span key="m"><Yes>Terbukti.</Yes> 93,6% pada zona berumur di bawah 10 bar lawan 77,2% di atas 59 bar, pada sentuhan pertama yang sama. Ini satu-satunya temuan arah-hasil yang selamat, dan ia sejalan dengan literatur akademik.</span>,
          ],
        ]}
      />
      <Note who="Hipotesis yang lolos, sampai kontrolnya dijalankan">
        <P>
          H7 menguji satu-satunya klaim arah yang benar-benar dibuat doktrin
          ICT: <b>timeframe tinggi menetapkan bias, timeframe rendah menetapkan
          entri</b>. Zona demand yang disentuh saat struktur bullish seharusnya
          objek yang berbeda dari zona yang sama saat struktur bearish.
          Perbandingannya dibuat <b>di dalam sisi</b>, sisi zona ditahan tetap
          dan hanya biasnya diubah, supaya drift sampelnya batal sendiri.
        </P>
        <P>
          Dan ia lolos. FVG pada swing besar: kedua sisi positif, kedua paruh
          positif, besarannya justru tumbuh. Setelah enam nol, ini hasil pertama
          yang melewati semua kriteria yang ditetapkan di depan.
        </P>
        <P>
          Masalahnya, <b>&quot;zona demand saat struktur bullish&quot; juga
          berarti &quot;koreksi di dalam tren naik&quot;</b>, dan membeli itu
          adalah momentum deret waktu, efek mapan yang tidak ada hubungannya
          dengan kotak mana pun. Jadi kontras yang sama dihitung ulang pada 4000
          bar acak yang cuma membawa bias, dengan sisi palsu yang diundi
          terpisah. Bar-bar itu memisah +0,271 dan +0,184. Yang tersisa untuk
          zonanya tidak signifikan, dan untuk supply/demand maupun order block
          justru negatif.
        </P>
        <P>
          Satu hal jujur yang tetap berdiri: <b>biasnya sendiri memisahkan
          return</b>. Itu bukan temuan baru, itu momentum, dan ia sama sekali
          tidak membutuhkan gambar apa pun.
        </P>
      </Note>
      <h3 className="mb-3 mt-8 text-[17px] font-semibold tracking-[-0.01em]">
        Bacaan pentingnya
      </h3>
      <P>
        Yang sebenarnya dilakukan gerbang departure bukan memilih zona yang
        bekerja, melainkan <b>membuang formasi yang aktif gagal</b>. Pada
        formasi yang ditolak gerbang, harga justru menembus terus dan kedua sisi
        menunjuk arah yang salah dengan p=0,0001. Ia mengurangi negatif, bukan
        menambah positif. Itu konsisten dengan selisih +11 sampai +21 poin
        persen terhadap kelompok yang ditolak, dan menjelaskan mekanismenya.
      </P>
    </section>
  );
}

/* ------------------------------------------------------------- 12 */

function Tidak() {
  return (
    <section>
      <Level id="tidak" title="Apa yang tidak diklaim" tag="BATAS" />
      <ul className="mb-4 max-w-[68ch] list-disc space-y-2 pl-5">
        <li>
          <b>Ini bukan hasil dagang.</b> Tidak ada biaya transaksi, spread,
          maupun slippage di mana pun dalam proyek ini.
        </li>
        <li>
          <b>Hanya sentuhan pertama.</b> Semua pengukuran hasil berhenti di
          sana. Klaim bahwa zona segar lebih baik daripada zona yang sudah diuji
          belum diuji di sini.
        </li>
        <li>
          <b>Zona yang tidak pernah disentuh tidak punya hasil</b>, jadi tidak
          masuk sampel. Ini seleksi yang disengaja dan disebutkan terbuka.
        </li>
        <li>
          <b>Emas hanya diwakili PAXG.</b> Tiga dari lima deret adalah kripto.
        </li>
        <li>
          <b>Satu riwayat adalah satu lintasan.</b> Walk-forward menunjukkan
          efeknya stabil di seluruh riwayat ini; ia tidak bisa menunjukkan
          efeknya bertahan ke depan.
        </li>
        <li>
          <b>Premis mekaniknya sendiri tidak bisa diverifikasi</b> dari data
          harga.
        </li>
      </ul>
      <Note who="Kenapa tidak ada panah arah di chart">
        <P>
          Dua belas hipotesis arah pre-registered didaftarkan sebelum diukur,
          dua belas kali sumbangan gambarnya nol. Yang paling meyakinkan sempat menunjukkan peluruhan 27
          poin persen menurut jumlah sentuhan, lalu runtuh jadi <b>77,2%, 77,2%,
          77,1%</b> begitu dibandingkan pada umur zona yang sama. Yang meluruh
          adalah waktu, bukan sentuhan. Yang terakhir, H7, bahkan lolos semua
          kriterianya sebelum kontrolnya menunjukkan bahwa biasnya yang bekerja,
          bukan kotaknya.
        </P>
        <P>
          Dua studi peer-reviewed yang benar-benar menghitung sentuhan
          sebelumnya justru menemukan tanda yang <b>berlawanan</b> dengan
          doktrin. Dan paten Online Trading Academy, kodifikasi algoritmik penuh
          metode ini, tidak memuat konsep kesegaran sama sekali.
        </P>
      </Note>

      <Note who="Pelajaran metodologis yang paling mahal">
        <P>
          Sebuah faktor bernama umur zona lolos uji lintas-bracket, lalu lolos
          walk-forward <b>8 dari 8 potongan di ketiga geometri</b> dengan ambang
          nyaris bulat. Lebih meyakinkan daripada apa pun yang pernah ada di
          sini. Ia ternyata gerbang departure yang menyamar, karena departure
          diukur sampai bar sentuhan sehingga keduanya terikat secara
          konstruksi.
        </P>
        <P>
          <b>Walk-forward membuktikan sebuah efek stabil. Ia tidak bisa
          membuktikan efek itu bukan sesuatu yang sudah kita punya.</b>
        </P>
      </Note>
    </section>
  );
}

/* ------------------------------------------------------------- 13 */

function Istilah() {
  return (
    <section>
      <Level id="istilah" title="Daftar istilah" tag="KAMUS" />
      <Table
        head={["Istilah", "Arti dalam Zonelab"]}
        rows={[
          [<N key="a">ATR</N>, "Rata-rata jarak gerak satu candle belakangan ini. Satuan untuk semua ambang."],
          [<N key="b">base</N>, "Babak tengah, tempat harga berhenti. Inilah kotaknya."],
          [<N key="c">leg-in, leg-out</N>, "Kaki masuk dan kaki keluar. Gerakan keras sebelum dan sesudah base."],
          [<N key="d">proximal</N>, "Tepi kotak yang harga temui lebih dulu saat kembali. Titik masuk."],
          [<N key="e">distal</N>, "Tepi jauh. Stop diletakkan di luarnya. Selalu ekstrem wick."],
          [<N key="f">departure</N>, "Seberapa jauh kaki keluar lari dari zona, dalam ATR."],
          [<N key="g">drift</N>, "Perjalanan satu arah melintasi base. Tinggi berarti itu tangga, bukan jeda."],
          [<N key="h">mitigated</N>, "Harga sudah memakan sebagian besar zona. Sisanya tinggal sedikit."],
          [<N key="i">bracket</N>, "Cara hasil diukur: target sekian jauh, stop di distal. Mana yang tercapai lebih dulu."],
          [<N key="j">AUC</N>, "Ukuran apakah sebuah angka bisa memeringkat hasil. 0,5 berarti tidak bisa sama sekali."],
          [<N key="k">walk-forward</N>, "Uji pada potongan waktu yang belum pernah dilihat saat ambangnya dipilih."],
          [<N key="l">placebo</N>, "Zona palsu berukuran dan bersisi sama, dipindah ke harga acak. Kontrol."],
          [<N key="m">DFR</N>, "Defining range. Q1 dari satu derajat siklus dibagi tiga, sepertiga pertama dibuang, ekstrem sisanya. Bukti paling lemah di kanvas: satu paragraf tentang indikator tertutup, belum pernah diuji. Karena itu tintanya paling redup dan proyeksinya digambar di KEDUA sisi setiap kelipatan, sebab sumbernya tidak menyebut arah."],
          [<N key="n">SSMT</N>, "Divergensi lintas instrumen: dua instrumen di kuartal yang sama, satu mengambil level sebelumnya dan satu gagal. Satu-satunya overlay yang butuh panggilan provider kedua, dan venue basketnya dipilih terpisah dari chart."],
          [<N key="o">STACK</N>, "Dua opening gap dari JENIS berbeda yang bandnya bertumpang. Persentasenya adalah tinggi tumpangan dibagi band yang lebih KECIL, dan penyebut itu rekonstruksi dari satu angka terbitan, bukan kutipan."],
          [<N key="p">gutter</N>, "Kolom 46 piksel di tepi kanan yang hanya milik nama. Setiap garis horizontal berhenti di situ, jadi tidak ada garis yang menembus nama milik layer lain."],
          [<N key="q">keluarga tinta</N>, "Lima warna kanvas: grid paling redup, lalu DFR, structure, SSMT, dan levels paling cerah. Warna menyatakan KELUARGA, nama menyatakan objeknya. Hijau dan merah hanya untuk demand dan supply; emas hanya untuk kontrol."],
          [<N key="r">quadrennial</N>, "Siklus empat tahun, satu tahun per kuartal, dan Q2 adalah tahun Pilpres Amerika - jadi 2024 dan 2028 Q2, dan 2026 Q4. Jangkarnya fakta, bukan angka yang dicocokkan. Siklus kuartalan Jan-Mar sampai Okt-Des sudah ada sebelumnya dengan nama derajat year."],
          [<N key="s">T4YO~</N>, "True open kuadrennial, dan tildenya wajib: Q2-nya dibuka 1 Januari, pasar tutup 1 Januari setiap tahun, jadi di bawah aturan ketat level ini terukur nol kali pada sepuluh tahun emas 1 jam. Dengan approximate menyala ia diambil dari bar pertama setelah batas, digambar putus-putus, dalam jangkauan 120 jam."],
          [<N key="u">preset</N>, "Satu set layer bernama yang Anda pilih sendiri, plus params minimum yang dibutuhkan layernya untuk menggambar - tiga dari tujuh belas layer menggambar nol dengan params bawaan, dan angkanya terukur: cycle grid, defining range, dan SSMT. Bukan deteksi fase otomatis: layer yang disembunyikan inferensi tidak bisa dibedakan dari layer yang tidak menemukan apa-apa, dan pembedaan itu yang dijaga seluruh engine ini."],
          [<N key="v">snapshot</N>, "Respons yang sedang tampil, disimpan apa adanya dengan catatan dan empat angka lag. Tidak digambar ulang, karena satu tick mendarat antara apa yang benar sekarang dan apa yang Anda lihat - jadi snapshot yang digambar ulang adalah snapshot chart yang tidak pernah dilihat siapa pun."],
          [<N key="w">overdue lawan intra-bar</N>, "feed_lag_seconds saja BUKAN staleness: ia now dikurangi bar_closed_at, jadi di chart 15 menit ia berjalan 0 sampai 900 semata karena waktu berjalan di dalam bar yang terbentuk. Yang melebihi satu bar penuh itu staleness sungguhan."],
          [<N key="t">P / D / EQ</N>, "Huruf di ekor tag SSMT: posisi ekstremnya di dealing range yang bisa diketahui saat ia tercetak. P premium (kuartil teratas), D discount (terbawah), EQ dua kuartil tengah. Tidak ada huruf berarti rentangnya belum terkonfirmasi - bukan 0,5 yang dikarang. Dilaporkan, tidak diskor."],
        ]}
      />
    </section>
  );
}
