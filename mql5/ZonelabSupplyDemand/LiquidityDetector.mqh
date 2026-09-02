//+------------------------------------------------------------------+
//|                                           LiquidityDetector.mqh  |
//|  Port faithful dari backend/app/liquidity.py::previous_period_    |
//|  levels. PDH, PDL, PWH, PWL, plus varian Jumat dan Senin.         |
//|                                                                   |
//|  INI LEVEL, sama bentuknya dengan pools, jadi ia memakai          |
//|  komparator level yang sama.                                       |
//|                                                                   |
//|  `boundary` MENENTUKAN SEGALANYA dan ikut dilaporkan di tiap      |
//|  level. `cycle` menjalankan hari 18:00 ke 18:00 New York dan      |
//|  pekan Minggu 18:00 ke Minggu 18:00; `midnight` menjalankan       |
//|  keduanya dari 00:00. Keduanya memberi ANGKA BERBEDA pada deret   |
//|  yang sama, dan default-nya keputusan supaya cocok dengan grid    |
//|  yang engine ini sudah gambar, bukan kutipan dari sumber.         |
//|                                                                   |
//|  SUDAH DIUKUR, DAN NEGATIF. app/layers.py: jangkauan dalam 96 bar |
//|  lawan placebo di offset yang sama, PDH/PDL n=4152 -1,59pp        |
//|  [-3,28, +0,10] walk-forward 3 dari 8; PWH/PWL n=747 -0,94pp,     |
//|  walk-forward 3 dari 8. Negatif di keempat instrumen. Level yang  |
//|  belum diambil adalah harga yang belum ditembus, bukan ramalan.   |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "NYClock.mqh"
#include "PoolsDetector.mqh"   // SDLowerBound, SDStep, SDTakenAt, SDPool

//: Nama per periode, (high, low). Dieja dan bukan diturunkan, karena ini nama
//: pemiliknya sendiri dan PDH bukan "day high". Setiap nama muat di kolom
//: label kanvas selebar 46 px, yang di Python dijaga sebuah test yang membaca
//: LABEL_GUTTER dari TypeScript.
struct SDPeriodDef
  {
   string name;        // "day" / "week" / "friday" / "monday"
   string high_name;
   string low_name;
   int    weekday_only; // -1 = tiap hari, selain itu 0=Minggu .. 5=Jumat
   bool   is_week;
  };

void SDPeriodDefs(SDPeriodDef &out[])
  {
   ArrayResize(out,4);
   out[0].name="day";    out[0].high_name="PDH";   out[0].low_name="PDL";
   out[0].weekday_only=-1; out[0].is_week=false;
   out[1].name="week";   out[1].high_name="PWH";   out[1].low_name="PWL";
   out[1].weekday_only=1;  out[1].is_week=true;    // Senin
   out[2].name="friday"; out[2].high_name="FRI H"; out[2].low_name="FRI L";
   out[2].weekday_only=5;  out[2].is_week=false;
   out[3].name="monday"; out[3].high_name="MON H"; out[3].low_name="MON L";
   out[3].weekday_only=1;  out[3].is_week=false;
  }

//+------------------------------------------------------------------+
//| [open, close) siklus hari yang DILABELI tanggal itu.               |
//|                                                                    |
//| Di `cycle` itu 18:00 petang sebelumnya sampai 18:00 tanggal ini,   |
//| pelabelan yang dipakai `quarters.py`: 18:00 Senin membuka Selasa.  |
//+------------------------------------------------------------------+
void SDDayWindow(string boundary,int year,int mon,int day,
                 datetime &start,datetime &close)
  {
   MqlDateTime d;
   ZeroMemory(d);
   d.year=year; d.mon=mon; d.day=day;
   datetime naive=StructToTime(d);
   MqlDateTime prev,next;
   TimeToStruct(naive-86400,prev);
   TimeToStruct(naive+86400,next);

   if(boundary=="cycle")
     {
      start=SDNyWall(prev.year,prev.mon,prev.day,18,0);
      close=SDNyWall(year,mon,day,18,0);
      return;
     }
   start=SDNyWall(year,mon,day,0,0);
   close=SDNyWall(next.year,next.mon,next.day,0,0);
  }

//+------------------------------------------------------------------+
//| [open, close) siklus pekan yang Senin-nya tanggal itu.             |
//|                                                                    |
//| Tujuh hari penuh, dibangun DARI jendela hari supaya kedua batasnya |
//| tidak bisa melenceng satu sama lain: pekan membuka di tempat       |
//| Senin-nya membuka dan menutup di tempat Senin berikutnya membuka.  |
//+------------------------------------------------------------------+
void SDWeekWindow(string boundary,int year,int mon,int day,
                  datetime &start,datetime &close)
  {
   datetime a,b;
   SDDayWindow(boundary,year,mon,day,a,b);
   start=a;
   MqlDateTime d;
   ZeroMemory(d);
   d.year=year; d.mon=mon; d.day=day;
   MqlDateTime nx;
   TimeToStruct(StructToTime(d)+7*86400,nx);
   datetime c,e;
   SDDayWindow(boundary,nx.year,nx.mon,nx.day,c,e);
   close=c;
  }

//+------------------------------------------------------------------+
//| High dan low tiap periode yang SUDAH SELESAI, plus apakah harga   |
//| sudah menembusnya.                                                 |
//|                                                                    |
//| Sebuah periode tidak menghasilkan apa pun kalau jendelanya tidak   |
//| memuat bar, dan tidak menghasilkan apa pun sampai ada bar di atau  |
//| setelah ujung jendelanya yang membuktikan periode itu tutup.       |
//| Periode yang feed-nya cuma menutup sebagian TETAP menghasilkan     |
//| levelnya - membuangnya akan menyembunyikan bar yang memang ada -   |
//| dengan `gap_at_open` dan `gap_at_close` menyebut dalam detik       |
//| berapa banyak jendela yang tidak berisi bar.                       |
//|                                                                    |
//| Mulai SEPEKAN LEBIH AWAL, supaya periode yang feed-nya buka di     |
//| tengahnya tetap diukur dan dilaporkan sebagai partial, alih-alih   |
//| lenyap karena Senin-nya jatuh sebelum bar pertama.                 |
//+------------------------------------------------------------------+
int SDPeriodLevels(const double &high[],const double &low[],const datetime &time_[],
                   int n,const string &wanted[],string boundary,SDPool &out[])
  {
   ArrayResize(out,0);
   if(n==0)
      return 0;

   SDPeriodDef defs[];
   SDPeriodDefs(defs);
   int step=SDStep(time_,n);
   int count=0;

   MqlDateTime f,l;
   SDToNy(time_[0],f);
   SDToNy(time_[n-1],l);
   MqlDateTime dz;
   ZeroMemory(dz);
   dz.year=l.year; dz.mon=l.mon; dz.day=l.day;
   datetime last_day=StructToTime(dz);
   ZeroMemory(dz);
   dz.year=f.year; dz.mon=f.mon; dz.day=f.day;
   datetime day=StructToTime(dz)-7*86400;

   while(day<=last_day)
     {
      MqlDateTime d;
      TimeToStruct(day,d);
      for(int w=0;w<ArraySize(wanted);w++)
        {
         int pi=-1;
         for(int k=0;k<4;k++)
            if(defs[k].name==wanted[w]) { pi=k; break; }
         if(pi<0)
            continue;
         if(defs[pi].weekday_only>=0 && d.day_of_week!=defs[pi].weekday_only)
            continue;

         datetime start,close;
         if(defs[pi].is_week)
            SDWeekWindow(boundary,d.year,d.mon,d.day,start,close);
         else
            SDDayWindow(boundary,d.year,d.mon,d.day,start,close);

         int lo=SDLowerBound(time_,n,start);
         int hi=SDLowerBound(time_,n,close);
         if(hi<=lo || hi>=n)
            continue;

         double hh=high[lo],ll=low[lo];
         for(int i=lo+1;i<hi;i++)
           {
            if(high[i]>hh) hh=high[i];
            if(low[i]<ll)  ll=low[i];
           }

         for(int s=0;s<2;s++)
           {
            bool above=(s==0);
            ArrayResize(out,count+1);
            // `session` memuat nama periode dan `side` nama levelnya, supaya
            // satu struct SDPool melayani pools DAN period level tanpa dua
            // bentuk CSV yang harus dijaga sinkron.
            out[count].session    =defs[pi].name;
            out[count].side       =above?defs[pi].high_name:defs[pi].low_name;
            out[count].price      =above?hh:ll;
            out[count].window_from=start;
            out[count].window_to  =close;
            out[count].first_bar  =time_[lo];
            out[count].last_bar   =time_[hi-1];
            out[count].bars       =hi-lo;
            // `covered` dihitung dengan rumus yang SAMA dengan pools, dan
            // kedua gap ditulis apa adanya. Memakai ulang satu boolean untuk
            // membawa gap_at_open akan membuang gap_at_close tanpa suara, dan
            // field yang tidak dibandingkan adalah field yang bisa salah tanpa
            // ketahuan.
            out[count].covered     =(time_[lo]-start<step) && (time_[hi-1]+step>=close);
            out[count].gap_at_open =(int)MathMax(0,time_[lo]-start);
            out[count].gap_at_close=(int)MathMax(0,close-time_[hi-1]-step);
            out[count].knowable_at=time_[hi];
            out[count].taken_at   =SDTakenAt(high,low,time_,hi,n,
                                             above?hh:ll,above);
            count++;
           }
        }
      day+=86400;
     }
   return count;
  }
//+------------------------------------------------------------------+
