//+------------------------------------------------------------------+
//|                                           StructureDetector.mqh  |
//|  Port faithful dari backend/app/detect/structure.py, bagian       |
//|  `swings` dan `walk_breaks`. Konvensi index sama: 0 = bar tertua. |
//|                                                                   |
//|  INI BUKAN BOX. Sebuah swing adalah TITIK, sebuah break adalah    |
//|  EVENT plus satu level horizontal. Keduanya dibandingkan lewat    |
//|  CSV event, bukan lewat komparator zona.                          |
//|                                                                   |
//|  KENAPA INI YANG PERTAMA DARI TUJUH SISANYA. Bukan karena ia      |
//|  paling berguna, tapi karena ia menutup cacat di detektor yang    |
//|  SUDAH diport: OrderBlockDetector.mqh tidak punya satu baris kode |
//|  swing pun, jadi `require_structure_break` - satu-satunya gerbang  |
//|  ICT yang sebenarnya di order block - tidak bisa diekspresikan di |
//|  MQL5 sama sekali. Order block yang parity-nya terbukti selama ini |
//|  hanya jalur default-nya.                                          |
//|                                                                   |
//|  ARAHNYA SUDAH DIUKUR NULL. app/layers.py H6 dan H9, keduanya.    |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

struct SDSwing
  {
   int    index;        // bar tempat pivot berada
   double price;
   bool   is_high;
   int    confirmed_at; // index + right, bar saat ia jadi diketahui
  };

struct SDBreak
  {
   int      index;       // bar yang menembus
   datetime time;
   string   kind;        // "BOS" / "CHoCH" / "SWEEP"
   int      direction;   // +1 ke atas, -1 ke bawah
   double   level;       // harga swing yang ditembus
   int      swing_index;
   int      bias_before;
  };

//+------------------------------------------------------------------+
//| Pivot fraktal, masing-masing distempel bar ia jadi diketahui.     |
//|                                                                   |
//| `left` adalah seberapa banyak sejarah yang harus didominasi pivot,|
//| `right` adalah seberapa lama harus MENUNGGU sebelum boleh tahu.   |
//| Keduanya dipisah karena pekerjaannya berbeda; menggabungkannya    |
//| jadi satu angka menyembunyikan yang kedua.                        |
//|                                                                   |
//| Seri diputus dengan menuntut maksimum KETAT di kiri dan tidak-    |
//| melebihi di kanan. Puncak datar kalau tidak akan mencatat pivot   |
//| di setiap bar dataran itu.                                        |
//|                                                                   |
//| Urutan keluarannya (confirmed_at, index) dan untuk satu bar yang  |
//| sama HIGH mendahului LOW, sama dengan sort stabil Python di sana. |
//| Karena confirmed_at = index + right, satu nilai confirmed_at cuma |
//| bisa berasal dari satu index, jadi urutannya sudah naik apa adanya|
//| dan tidak butuh sort sama sekali.                                 |
//+------------------------------------------------------------------+
int SDSwings(const double &high[],const double &low[],int n,int left,int right,
             SDSwing &out[])
  {
   ArrayResize(out,0);
   int count=0;
   for(int i=left;i<n-right;i++)
     {
      double lmax=high[i-left];
      double lmin=low[i-left];
      for(int j=i-left+1;j<i;j++)
        {
         if(high[j]>lmax) lmax=high[j];
         if(low[j]<lmin)  lmin=low[j];
        }
      double rmax=high[i+1];
      double rmin=low[i+1];
      for(int j=i+2;j<=i+right;j++)
        {
         if(high[j]>rmax) rmax=high[j];
         if(low[j]<rmin)  rmin=low[j];
        }

      if(high[i]>lmax && high[i]>=rmax)
        {
         ArrayResize(out,count+1);
         out[count].index       =i;
         out[count].price       =high[i];
         out[count].is_high     =true;
         out[count].confirmed_at=i+right;
         count++;
        }
      if(low[i]<lmin && low[i]<=rmin)
        {
         ArrayResize(out,count+1);
         out[count].index       =i;
         out[count].price       =low[i];
         out[count].is_high     =false;
         out[count].confirmed_at=i+right;
         count++;
        }
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Satu lintasan maju, memancarkan break tiap kali sebuah CLOSE      |
//| melewati sebuah swing. Tanpa lookahead apa pun: di bar `i` ia     |
//| hanya boleh melihat swing yang sudah terkonfirmasi di `i`, dan ia |
//| hanya menguji CLOSE bar `i`.                                      |
//|                                                                   |
//| SWEEP lawan BREAK. Wick yang menembus lalu close kembali ke dalam |
//| adalah SWEEP, likuiditas diambil, dan menyebutnya break akan      |
//| menggabungkan dua peristiwa berlawanan jadi satu nama. Sweep      |
//| DIPANCARKAN, tidak dilewati diam-diam.                            |
//|                                                                   |
//| Sebuah level hanya boleh menyapu SEKALI (`swept`), dan kuncinya   |
//| index swing-nya sendiri bukan harganya: dua swing bisa duduk di   |
//| harga yang sama dan itu dua level, dan membersihkannya saat break |
//| akan mengarmkan ulang level yang break itu sudah pakai.           |
//|                                                                   |
//| Atas dievaluasi sebelum bawah, jadi outside bar yang close        |
//| melewati KEDUA level memancarkan dua-duanya dan berakhir bearish. |
//| Tidak ada sumber yang membahas kasus itu; urutannya pilihan yang  |
//| dinyatakan, dan kedua event disimpan alih-alih satu ditelan.      |
//+------------------------------------------------------------------+
int SDWalkBreaks(const double &high[],const double &low[],const double &close[],
                 const datetime &time_[],int n,const SDSwing &found[],int swing_count,
                 bool resweep,SDBreak &out[])
  {
   ArrayResize(out,0);
   int count=0;

   int live_high=-1;   // index ke found[], -1 = tidak ada
   int live_low=-1;
   int bias=0;

   bool swept[];
   ArrayResize(swept,n);
   ArrayInitialize(swept,false);

   for(int i=0;i<n;i++)
     {
      // Swing yang terkonfirmasi TEPAT di bar ini, urut seperti dihasilkan.
      for(int s=0;s<swing_count;s++)
        {
         if(found[s].confirmed_at!=i)
            continue;
         if(found[s].is_high)
            live_high=s;
         else
            live_low=s;
        }

      if(live_high>=0)
        {
         if(close[i]>found[live_high].price)
           {
            ArrayResize(out,count+1);
            out[count].index      =i;
            out[count].time       =time_[i];
            out[count].kind       =(bias>=0)?"BOS":"CHoCH";
            out[count].direction  =1;
            out[count].level      =found[live_high].price;
            out[count].swing_index=found[live_high].index;
            out[count].bias_before=bias;
            count++;
            bias=1;
            live_high=-1;
           }
         else if(high[i]>found[live_high].price)
           {
            int si=found[live_high].index;
            if(resweep || !swept[si])
              {
               ArrayResize(out,count+1);
               out[count].index      =i;
               out[count].time       =time_[i];
               out[count].kind       ="SWEEP";
               out[count].direction  =1;
               out[count].level      =found[live_high].price;
               out[count].swing_index=si;
               out[count].bias_before=bias;
               count++;
               swept[si]=true;
              }
            // Level tetap terarm untuk BREAK, dan harganya tidak berubah.
            // Menaikkannya ke wick sweep akan mengubah setiap break di
            // hilirnya, dan doktrin diam soal mana yang benar.
           }
        }

      if(live_low>=0)
        {
         if(close[i]<found[live_low].price)
           {
            ArrayResize(out,count+1);
            out[count].index      =i;
            out[count].time       =time_[i];
            out[count].kind       =(bias<=0)?"BOS":"CHoCH";
            out[count].direction  =-1;
            out[count].level      =found[live_low].price;
            out[count].swing_index=found[live_low].index;
            out[count].bias_before=bias;
            count++;
            bias=-1;
            live_low=-1;
           }
         else if(low[i]<found[live_low].price)
           {
            int si=found[live_low].index;
            if(resweep || !swept[si])
              {
               ArrayResize(out,count+1);
               out[count].index      =i;
               out[count].time       =time_[i];
               out[count].kind       ="SWEEP";
               out[count].direction  =-1;
               out[count].level      =found[live_low].price;
               out[count].swing_index=si;
               out[count].bias_before=bias;
               count++;
               swept[si]=true;
              }
           }
        }
     }
   return count;
  }

//+------------------------------------------------------------------+
//| `breaks` di Python: swings lalu walk, dengan guard panjang deret. |
//+------------------------------------------------------------------+
int SDBreaks(const double &high[],const double &low[],const double &close[],
             const datetime &time_[],int n,int left,int right,
             SDBreak &out[],SDSwing &found[])
  {
   ArrayResize(out,0);
   ArrayResize(found,0);
   if(n<left+right+2)
      return 0;
   int swing_count=SDSwings(high,low,n,left,right,found);
   return SDWalkBreaks(high,low,close,time_,n,found,swing_count,false,out);
  }
//+------------------------------------------------------------------+
