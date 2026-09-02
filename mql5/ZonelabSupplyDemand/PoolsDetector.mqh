//+------------------------------------------------------------------+
//|                                               PoolsDetector.mqh  |
//|  Port faithful dari backend/app/pools.py::liquidity_pools.        |
//|  Konvensi index sama: 0 = bar tertua.                             |
//|                                                                   |
//|  INI LEVEL, BUKAN BOX. Satu sesi menghasilkan dua pool: BSL di    |
//|  high-nya, SSL di low-nya. Masing-masing satu harga plus jendela  |
//|  waktu, jadi ia dibandingkan lewat CSV level, bukan lewat         |
//|  komparator zona.                                                  |
//|                                                                   |
//|  TIDAK ADA KLAIM ARAH. Pool yang belum diambil adalah KANDIDAT    |
//|  target, bukan ramalan bahwa harga akan sampai. app/layers.py     |
//|  mencatatnya MEASURED NULL: kontrol jitter per-event +0,15pp,     |
//|  walk-forward 4 dari 8, sign test p = 1,00. Kontrol shuffled yang |
//|  dulu memberi +2,90pp terbukti cacat, karena mengacak memutus     |
//|  pasangan antara jarak sebuah level dan volatilitas bar-nya, dan  |
//|  di dalam pita jarak yang disamakan selisihnya -0,68pp.           |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "NYClock.mqh"

//: Jendela sesi dalam JAM DINDING New York, sebagai (open, close, hari).
//: Field ketiga adalah jumlah hari kalender dari tanggal open ke tanggal
//: close; `asia` menyeberang tengah malam. Angka-angka ini bukan parameter di
//: Python dan tidak dijadikan parameter di sini, supaya keduanya tidak bisa
//: berbeda pendapat tentang kapan sebuah sesi mulai.
#define SD_SESSION_COUNT 4

struct SDSessionDef
  {
   string name;
   int    open_hour;
   int    close_hour;
   int    close_days;
  };

void SDSessionDefs(SDSessionDef &out[])
  {
   ArrayResize(out,SD_SESSION_COUNT);
   out[0].name="asia";         out[0].open_hour=19; out[0].close_hour=0;  out[0].close_days=1;
   out[1].name="london";       out[1].open_hour=2;  out[1].close_hour=5;  out[1].close_days=0;
   out[2].name="ny_am";        out[2].open_hour=7;  out[2].close_hour=10; out[2].close_days=0;
   out[3].name="london_close"; out[3].open_hour=10; out[3].close_hour=12; out[3].close_days=0;
  }

struct SDPool
  {
   string   session;
   string   side;        // "BSL" di high, "SSL" di low
   double   price;
   datetime window_from;
   datetime window_to;
   datetime first_bar;
   datetime last_bar;
   int      bars;
   bool     covered;
   int      gap_at_open;  // detik jendela tanpa bar di awal
   int      gap_at_close; // dan di akhir
   datetime knowable_at;
   datetime taken_at;    // 0 = belum diambil
  };

//+------------------------------------------------------------------+
//| Index bar pertama yang open-nya >= t. Bisa mengembalikan n.        |
//| Deret waktu naik, jadi binary search.                              |
//+------------------------------------------------------------------+
int SDLowerBound(const datetime &time_[],int n,datetime t)
  {
   int lo=0,hi=n;
   while(lo<hi)
     {
      int mid=(lo+hi)/2;
      if(time_[mid]<t)
         lo=mid+1;
      else
         hi=mid;
     }
   return lo;
  }

//+------------------------------------------------------------------+
//| Interval bar feed, diambil sebagai gap MODAL antara dua bar.       |
//|                                                                    |
//| BUKAN yang terkecil, dan alasannya diukur. Pada 500 bar emas 15m   |
//| Yahoo gap-nya 900 detik 493 kali, 4500 empat kali di jeda sesi,    |
//| dan 899 TEPAT SEKALI. Minimum mengambil satu ketidakrapian satu    |
//| detik itu sebagai interval feed, sehingga jendela Asia lima jam    |
//| yang penuh terukur 20 x 899 = 17.980 lawan 18.000 dan SETIAP pool  |
//| di chart kembali sebagai partial. Flag itu ada untuk mengatakan    |
//| "high ini bukan high sesinya"; menyalakannya pada sesi yang lengkap|
//| mengatakan kebalikan dari kebenaran tentang semua ray sekaligus.   |
//+------------------------------------------------------------------+
int SDStep(const datetime &time_[],int n)
  {
   if(n<2)
      return 0;
   // Gap dikumpulkan lalu dicari yang paling sering. n kecil di sini
   // (ribuan), jadi hitung frekuensi dengan satu lintasan bersarang atas
   // nilai unik alih-alih membangun map.
   int gaps[];
   ArrayResize(gaps,n-1);
   for(int i=1;i<n;i++)
      gaps[i-1]=(int)(time_[i]-time_[i-1]);
   ArraySort(gaps);

   int best=gaps[0],best_run=0;
   int cur=gaps[0],run=0;
   for(int i=0;i<n-1;i++)
     {
      if(gaps[i]==cur)
         run++;
      else
        {
         if(run>best_run) { best_run=run; best=cur; }
         cur=gaps[i];
         run=1;
        }
     }
   if(run>best_run)
      best=cur;
   return best;
  }

//+------------------------------------------------------------------+
//| Open time bar PERTAMA yang menembus `price`, atau 0 kalau bertahan.|
//|                                                                    |
//| Tembus KETAT: high yang sama persis menyentuh level tanpa           |
//| mengambilnya, dan itu penting karena bar sesi itu sendiri yang     |
//| mencetak high tersebut.                                             |
//+------------------------------------------------------------------+
datetime SDTakenAt(const double &high[],const double &low[],const datetime &time_[],
                   int from_index,int n,double price,bool above)
  {
   for(int i=from_index;i<n;i++)
     {
      if(above ? (high[i]>price) : (low[i]<price))
         return time_[i];
     }
   return 0;
  }

//+------------------------------------------------------------------+
//| High dan low tiap sesi bernama, plus apakah harga sudah menembus.  |
//|                                                                    |
//| Sebuah sesi tidak menghasilkan pool sampai ia TUTUP, dan buktinya  |
//| terbaca dari datanya sendiri: harus ada bar yang open-nya di atau  |
//| setelah jendela ditutup, dan bar itulah `knowable_at`.             |
//+------------------------------------------------------------------+
int SDLiquidityPools(const double &high[],const double &low[],const datetime &time_[],
                     int n,const string &wanted[],SDPool &out[])
  {
   ArrayResize(out,0);
   if(n==0)
      return 0;

   SDSessionDef defs[];
   SDSessionDefs(defs);
   int step=SDStep(time_,n);
   int count=0;

   MqlDateTime first_ny,last_ny;
   SDToNy(time_[0],first_ny);
   SDToNy(time_[n-1],last_ny);
   // Tanggal kalender New York, dibandingkan sebagai tanggal dan bukan sebagai
   // epoch, sama seperti Python membandingkan objek `date`.
   MqlDateTime dz;
   ZeroMemory(dz);
   dz.year=last_ny.year; dz.mon=last_ny.mon; dz.day=last_ny.day;
   datetime last_day=StructToTime(dz);

   for(int w=0;w<ArraySize(wanted);w++)
     {
      int si=-1;
      for(int k=0;k<SD_SESSION_COUNT;k++)
         if(defs[k].name==wanted[w]) { si=k; break; }
      if(si<0)
         continue;   // nama tak dikenal dilaporkan, bukan error, sama dengan Python

      ZeroMemory(dz);
      dz.year=first_ny.year; dz.mon=first_ny.mon; dz.day=first_ny.day;
      datetime day=StructToTime(dz);

      while(day<=last_day)
        {
         MqlDateTime d,sh;
         TimeToStruct(day,d);
         TimeToStruct(day+defs[si].close_days*86400,sh);
         datetime start=SDNyWall(d.year,d.mon,d.day,defs[si].open_hour,0);
         datetime close=SDNyWall(sh.year,sh.mon,sh.day,defs[si].close_hour,0);
         day+=86400;

         int lo=SDLowerBound(time_,n,start);
         int hi=SDLowerBound(time_,n,close);
         if(hi<=lo || hi>=n)
            continue;   // tidak ada bar di dalam, atau tidak ada bar sesudahnya

         double hh=high[lo],ll=low[lo];
         for(int i=lo+1;i<hi;i++)
           {
            if(high[i]>hh) hh=high[i];
            if(low[i]<ll)  ll=low[i];
           }
         bool covered=(time_[lo]-start<step) && (time_[hi-1]+step>=close);

         for(int s=0;s<2;s++)
           {
            bool above=(s==0);
            ArrayResize(out,count+1);
            out[count].session    =defs[si].name;
            out[count].side       =above?"BSL":"SSL";
            out[count].price      =above?hh:ll;
            out[count].window_from=start;
            out[count].window_to  =close;
            out[count].first_bar  =time_[lo];
            out[count].last_bar   =time_[hi-1];
            out[count].bars       =hi-lo;
            out[count].covered    =covered;
            // Ditulis juga di sini walau `pools.py` tidak memakainya, supaya
            // satu bentuk CSV melayani pools DAN period level dan komparatornya
            // memeriksa field yang memang dimiliki tiap sisi.
            out[count].gap_at_open =(int)MathMax(0,time_[lo]-start);
            out[count].gap_at_close=(int)MathMax(0,close-time_[hi-1]-step);
            out[count].knowable_at=time_[hi];
            out[count].taken_at   =SDTakenAt(high,low,time_,hi,n,
                                             above?hh:ll,above);
            count++;
           }
        }
     }
   return count;
  }
//+------------------------------------------------------------------+
