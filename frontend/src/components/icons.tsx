/** SATU SET GLYPH, DIGAMBAR TANGAN, DAN ALASANNYA BUKAN SELERA.
 *
 *  Riset atas lima icon library membandingkan cakupannya untuk rail ini:
 *  Lucide 1.798 glyph, Tabler 5.130 outline, Phosphor 1.512, Radix 332,
 *  Heroicons 324. Ketiganya yang besar punya `chart-candlestick`,
 *  `trending-up` dan `crosshair`. Tak satu pun punya fair value gap, inverted
 *  fair value gap, breaker block, SSMT, precision swing point, defining range,
 *  atau change in state of delivery - yaitu tujuh dari 21 layer di sini.
 *
 *  Jadi pertanyaannya bukan library mana, melainkan apakah 21 layer itu dapat
 *  glyph GENERIK dari library atau miniatur objeknya sendiri. Yang dipilih yang
 *  kedua, dan itu keputusan yang bisa dibela: glyph di bawah bukan metafora,
 *  ia GAMBAR objek yang layer itu cat di chart. Glyph gap benar benar dua bar
 *  dengan ruang di antaranya; glyph order block benar benar body candle dengan
 *  wick; glyph divergence benar benar dua garis yang berpisah. Pembaca yang
 *  sudah melihat chart-nya tahu bentuknya sebelum membaca satu label.
 *
 *  Sebuah `Layers` generik dari library untuk supply and demand tidak membawa
 *  informasi itu, dan biaya 31,7 MB untuk 40 glyph generik yang tujuh di
 *  antaranya tetap harus digambar tangan bukan tukar yang menguntungkan.
 *
 *  ATURAN YANG BERLAKU UNTUK SEMUANYA, dan pelanggarannya kelihatan langsung:
 *    - grid 16, satu stroke weight 1,5, `currentColor` saja
 *    - tanpa fill kecuali fill itu MEMBAWA arti, yaitu body candle yang memang
 *      padat dan zona yang memang punya isi
 *    - warna TIDAK PERNAH dari sini. Warna adalah sisi, demand hijau dan supply
 *      merah, dan itu satu satunya hal yang warna katakan di app ini. Icon
 *      mewarisi warna barisnya.
 *    - satu keluarga, jadi tidak ada glyph yang terbaca lebih tebal dari
 *      tetangganya di rail yang sama.
 */

const P = {
  // ----------------------------------------------------------------- zona
  /** Dua band, satu di atas satu di bawah: sisi supply dan sisi demand. */
  supply_demand: (
    <>
      <rect x="2" y="2.5" width="12" height="4" />
      <rect x="2" y="9.5" width="12" height="4" />
    </>
  ),
  /** Tiga bar dengan celah yang tidak diperdagangkan di tengah. Putus putus,
   *  encoding yang sama dengan `--dash-fvg` di canvas: sebuah ketiadaan. */
  fvg: (
    <>
      <path d="M2.5 2.5v4M2.5 11v2.5" />
      <rect x="5.5" y="5.5" width="8" height="5" strokeDasharray="1.6 1.6" />
      <path d="M13.5 2.5v3M13.5 10.5v3" />
    </>
  ),
  /** Body candle yang padat dengan wick. Padat karena order block memang satu
   *  candle sungguhan, lawan fvg yang sebuah ketiadaan. */
  order_block: (
    <>
      <path d="M8 1.5v3M8 11.5v3" />
      <rect x="4" y="4.5" width="8" height="7" fill="currentColor" fillOpacity="0.28" />
    </>
  ),
  /** Gap yang dibaca terbalik: kotak yang sama dengan panah membalik lewatnya. */
  ifvg: (
    <>
      <rect x="2.5" y="4.5" width="11" height="7" strokeDasharray="2.4 1.8" />
      <path d="M4.5 10.5L11.5 5.5M9.5 5.5h2v2" />
    </>
  ),
  /** Level lama yang tertembus: kotak dengan garis menembusnya. */
  breaker: (
    <>
      <rect x="2.5" y="5" width="11" height="6" strokeDasharray="2.4 1.8" />
      <path d="M1 12.5L15 3.5" />
    </>
  ),

  // -------------------------------------------------- struktur dan momentum
  structure: <path d="M1.5 12L5 6.5L8 9.5L11 3L14.5 7.5" />,
  /** Range mendatar lalu keluar ke atas: bentuk fase Wyckoff. */
  wyckoff: (
    <>
      <rect x="1.5" y="5" width="8" height="6" />
      <path d="M3 8.5h5" strokeDasharray="1.5 1.5" />
      <path d="M9.5 8.5l3-4.5M11 4h1.8v1.8" />
    </>
  ),
  /** Satu level, lalu candle yang membalik menembusnya. */
  cisd: (
    <>
      <path d="M1.5 8.5h13" strokeDasharray="2 1.6" />
      <path d="M4.5 12.5V8.5M4.5 4.5v.5" />
      <rect x="9" y="3.5" width="4" height="5" fill="currentColor" fillOpacity="0.28" />
      <path d="M11 1.5v2M11 8.5v2" />
    </>
  ),

  // ------------------------------------------------------------------ waktu
  /** Grid waktu: pita vertikal berulang. */
  session: (
    <>
      <path d="M1.5 2.5v11M6 2.5v11M10.5 2.5v11M15 2.5v11" />
      <path d="M6 5h4.5" strokeDasharray="1.4 1.4" />
    </>
  ),
  /** Sebuah range dengan bracket di kedua ujungnya. */
  dfr: (
    <>
      <path d="M2.5 3.5v9M13.5 3.5v9" />
      <path d="M2.5 8h11" />
      <path d="M5.5 6l-3 2 3 2M10.5 6l3 2-3 2" />
    </>
  ),
  news: (
    <>
      <rect x="2" y="3" width="12" height="11" />
      <path d="M2 6.5h12M5 1.5v3M11 1.5v3" />
      <circle cx="8" cy="10.5" r="1.4" fill="currentColor" stroke="none" />
    </>
  ),

  // ------------------------------------------------------------ celah harga
  /** Dua bar dengan celah harga di antaranya, dan celah itu yang diberi nama. */
  gaps: (
    <>
      <path d="M1.5 3.5h5M9.5 12.5h5" />
      <path d="M4 3.5v2.5M12 10v2.5" />
      <path d="M2 6.5h12M2 9.5h12" strokeDasharray="2 1.6" />
    </>
  ),
  /** Celah yang sama dengan panah lari darinya: breakaway lawan measuring. */
  chart_gaps: (
    <>
      <path d="M1.5 11.5h4" />
      <path d="M1.5 8.5h12M1.5 5.5h12" strokeDasharray="2 1.6" />
      <path d="M8 13L13.5 3M11.5 3h2.4v2.4" />
    </>
  ),

  // -------------------------------------------------- likuiditas dan level
  /** Beberapa level bertumpuk, tempat stop menumpuk. */
  pools: (
    <>
      <path d="M1.5 4h13M1.5 8h13M1.5 12h13" strokeDasharray="2.6 1.6" />
      <circle cx="12" cy="4" r="1.1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  /** Satu ray harga dengan label di ujungnya. */
  liquidity: (
    <>
      <path d="M1.5 8h8" />
      <rect x="9.5" y="5.5" width="5" height="5" />
    </>
  ),
  /** Satu titik yang memancar ke beberapa target. */
  projections: (
    <>
      <circle cx="2.5" cy="8" r="1.3" fill="currentColor" stroke="none" />
      <path d="M4 8h10M4 7l9-3.5M4 9l9 3.5" strokeDasharray="2.2 1.6" />
    </>
  ),

  // ---------------------------------------------- divergensi lintas instrumen
  /** Dua deret yang berpisah. Itu seluruh isi konsepnya. */
  ssmt: (
    <>
      <path d="M1.5 5L5.5 8L9 5.5L14.5 3" />
      <path d="M1.5 10L5.5 8L9 10.5L14.5 13" strokeDasharray="2.2 1.6" />
    </>
  ),
  /** Dua deret yang bertemu tepat di satu bar, dan bar itu yang ditandai. */
  psp: (
    <>
      <path d="M1.5 4L8 10.5L14.5 4" />
      <path d="M1.5 12L8 10.5L14.5 12" strokeDasharray="2.2 1.6" />
      <circle cx="8" cy="10.5" r="1.6" fill="currentColor" stroke="none" />
    </>
  ),

  // -------------------------------------------- bacaan, bukan objek pasar
  /** Kipas dari satu titik: sebaran hasil, bukan satu garis ramalan. */
  expectation: (
    <>
      <circle cx="2.5" cy="8" r="1.2" fill="currentColor" stroke="none" />
      <path d="M4 8L14.5 2.5M4 8L14.5 8M4 8L14.5 13.5" />
      <path d="M12 4.2v7.4" strokeDasharray="1.4 1.4" />
    </>
  ),
  /** Dial dengan tiga tanda. */
  vortex: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 2v2" />
      <path d="M8 8l3.5 2" />
      <circle cx="8" cy="8" r="1.1" fill="currentColor" stroke="none" />
    </>
  ),
  checklist: (
    <>
      <path d="M1.5 4.5l1.5 1.5L5.5 3" />
      <path d="M1.5 11.5l1.5 1.5L5.5 10" />
      <path d="M8 4.5h6.5M8 12.5h6.5" />
    </>
  ),

  // ------------------------------------------------------------ role header
  role_zona: (
    <>
      <rect x="1.5" y="4" width="13" height="3.5" />
      <rect x="1.5" y="9" width="13" height="3.5" />
    </>
  ),
  role_struktur: <path d="M1.5 12L5 6.5L8 9.5L11 3L14.5 7.5" />,
  role_likuiditas: (
    <path d="M1.5 4h13M1.5 8h13M1.5 12h13" strokeDasharray="2.6 1.6" />
  ),
  role_celah: (
    <>
      <path d="M1.5 4h13M1.5 12h13" />
      <path d="M1.5 8h13" strokeDasharray="1.6 1.6" />
    </>
  ),
  role_waktu: (
    <>
      <circle cx="8" cy="8" r="6.2" />
      <path d="M8 4.2V8l2.8 1.8" />
    </>
  ),
  role_divergensi: (
    <>
      <path d="M1.5 8L6 8L14.5 2.5" />
      <path d="M6 8L14.5 13.5" strokeDasharray="2.2 1.6" />
    </>
  ),
  role_bacaan: (
    <>
      <rect x="2.5" y="1.5" width="11" height="13" />
      <path d="M5 5h6M5 8h6M5 11h3.5" />
    </>
  ),

  // ------------------------------------------------------------------- UI
  moon: <path d="M13.4 9.6A6 6 0 1 1 6.4 2.6a4.8 4.8 0 0 0 7 7z" />,
  sun: (
    <>
      <circle cx="8" cy="8" r="3.2" />
      <path d="M8 1v1.6M8 13.4V15M1 8h1.6M13.4 8H15M3.1 3.1l1.1 1.1M11.8 11.8l1.1 1.1M12.9 3.1l-1.1 1.1M4.2 11.8l-1.1 1.1" />
    </>
  ),
  /** Setengah matahari setengah bulan: pilihan yang menyerahkannya ke OS. */
  auto: (
    <>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 2a6 6 0 0 0 0 12z" fill="currentColor" stroke="none" />
    </>
  ),
  close: <path d="M4 4l8 8M12 4l-8 8" />,
  chevron: <path d="M6 3.5L10.5 8L6 12.5" />,
  info: (
    <>
      <circle cx="8" cy="8" r="6.2" />
      <path d="M8 7.2v4M8 4.8v.9" />
    </>
  ),
  check: <path d="M2.5 8.5l3.5 3.5L13.5 4" />,
  camera: (
    <>
      <path d="M1.5 5h3l1.2-1.8h4.6L11.5 5h3v8.5h-13z" />
      <circle cx="8" cy="9" r="2.6" />
    </>
  ),
  panel_left: (
    <>
      <rect x="1.5" y="2.5" width="13" height="11" />
      <path d="M6 2.5v11" />
      <path d="M4.3 6.5L2.8 8l1.5 1.5" />
    </>
  ),
  panel_right: (
    <>
      <rect x="1.5" y="2.5" width="13" height="11" />
      <path d="M10 2.5v11" />
      <path d="M11.7 6.5L13.2 8l-1.5 1.5" />
    </>
  ),
  /** Segitiga, bukan lingkaran seru. Lingkaran seru sudah dipakai `info`, dan
   *  bentuk yang berbeda adalah satu satunya channel yang tersisa: hue amber
   *  yang biasanya membawa peringatan cuma berjarak 12 derajat dari accent
   *  emas di app ini, jadi warna tidak bisa membedakan keduanya. */
  alert: (
    <>
      <path d="M8 2L15 13.5H1z" />
      <path d="M8 6.2v3.4M8 11.2v.9" />
    </>
  ),
  book: (
    <>
      <path d="M2 2.5h4.4c.9 0 1.6.7 1.6 1.6v9.4c0-.7-.6-1.3-1.3-1.3H2z" />
      <path d="M14 2.5H9.6c-.9 0-1.6.7-1.6 1.6v9.4c0-.7.6-1.3 1.3-1.3H14z" />
    </>
  ),
} as const;

export type IconName = keyof typeof P;

/** Peta layer id ke glyph-nya. Kunci di sini HARUS habis menutupi registry.
 *
 *  Sebuah layer tanpa entri akan diam saja dan render tanpa icon, yaitu satu
 *  baris yang terlihat sedikit berbeda dari 20 tetangganya dan tidak ada yang
 *  memperhatikan. `LAYER_SWATCH` di toolbox sudah pernah kehilangan layer baru
 *  dengan cara persis itu, jadi `e2e/theme.mjs` membandingkan kunci di sini
 *  lawan registry dan gagal kalau ada yang hilang.
 */
export const LAYER_ICON: Record<string, IconName> = {
  supply_demand: "supply_demand",
  fvg: "fvg",
  order_block: "order_block",
  ifvg: "ifvg",
  breaker: "breaker",
  structure: "structure",
  wyckoff: "wyckoff",
  cisd: "cisd",
  session: "session",
  dfr: "dfr",
  news: "news",
  gaps: "gaps",
  chart_gaps: "chart_gaps",
  pools: "pools",
  liquidity: "liquidity",
  projections: "projections",
  ssmt: "ssmt",
  psp: "psp",
  expectation: "expectation",
  vortex: "vortex",
  checklist: "checklist",
};

/** Peta role ke glyph-nya, dengan kunci berupa string role dari registry. */
export const ROLE_ICON: Record<string, IconName> = {
  Zona: "role_zona",
  "Struktur dan momentum": "role_struktur",
  "Likuiditas dan level": "role_likuiditas",
  "Celah harga": "role_celah",
  Waktu: "role_waktu",
  "Divergensi lintas instrumen": "role_divergensi",
  "Bacaan, bukan objek pasar": "role_bacaan",
};

/** DEKORATIF SECARA DEFAULT, dan itu pilihan aksesibilitas bukan kemalasan.
 *
 *  Tiap icon di app ini duduk di sebelah label teks yang mengatakan hal yang
 *  sama. Memberinya `aria-label` sendiri membuat screen reader membacanya dua
 *  kali, jadi default-nya `aria-hidden`. Yang berdiri sendiri tanpa teks
 *  mengoper `label`.
 */
export function Icon({
  name,
  className = "size-4",
  label,
  style,
}: {
  name: IconName;
  className?: string;
  label?: string;
  /** Hanya untuk memberi glyph warna ink layer-nya. Warna TIDAK datang dari
   *  file ini; ia datang dari `LAYER_SWATCH`, yang membacanya dari `ink.ts`,
   *  yang memegang satu tabel per theme. */
  style?: React.CSSProperties;
}) {
  return (
    <svg
      viewBox="0 0 16 16"
      className={className}
      style={style}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    >
      {P[name]}
    </svg>
  );
}
