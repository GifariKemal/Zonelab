//+------------------------------------------------------------------+
//|                                          QuarterlyDetector.mqh   |
//|  Port faithful dari backend/app/quarters.py (degree `day`) dan     |
//|  backend/app/quarterly.py: grid kuarter, DFR, profil AMDX/XAMD,    |
//|  dan manipulation_done.                                            |
//|                                                                    |
//|  KENAPA INI DIPORT, DAN KENAPA SEKARANG. Empat klausa checklist     |
//|  berdiri di atas kedua objek ini - `manipulation_quarter`,          |
//|  `manipulation_seen`, `manipulation_after_accumulation` dan         |
//|  `dfr_side` - dan `dfr_side` satu-satunya dari tujuh belas yang     |
//|  melewati ambang Bonferroni 3,267. Tapi keduanya family Quarterly   |
//|  Theory, dan sensus port di `tools/mqh_parity.py` sampai            |
//|  2 September 2026 HANYA menutup family ICT. Jadi presisi keduanya   |
//|  lawan MQL5 bukan terukur-dan-lolos maupun terukur-dan-gagal:       |
//|  belum pernah ditanyakan. Klausa yang paling berhak dapat           |
//|  pengukuran adalah klausa yang satu-satunya memisahkan.             |
//|                                                                    |
//|  DEGREE `day` SAJA, dan itu bukan pemotongan sembarang:             |
//|  `app/conditions.py:at_bar` default `degree="day"` dan keempat      |
//|  klausa itu membaca state yang dihasilkannya. Degree lain adalah    |
//|  populasi lain dan tidak ada klausa yang membacanya.                |
//|                                                                    |
//|  ATURAN PERTIGA MASIH SINGLE-SOURCED. `app/quarterly.py` mencatat   |
//|  statusnya: satu fetch yang merangkum, dikuatkan hanya oleh situs   |
//|  penulisnya sendiri, satu suara dua kali. Yang diukur di sini       |
//|  KESETARAAN dua implementasi, bukan kebenaran aturannya.            |
//|                                                                    |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)               |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "NYClock.mqh"
#include "PoolsDetector.mqh"      // SDLowerBound
#include "StructureDetector.mqh"  // SDBreaks, SDBreak

struct SDQuarter
  {
   string   label;   // "Q1".."Q4"
   datetime start;   // inklusif
   datetime end;     // eksklusif
  };

struct SDDfr
  {
   datetime cycle_start;
   datetime start;   // sepertiga pertama Q1 sudah dibuang
   datetime end;     // = Q1.end
   double   high;
   double   low;
  };

struct SDProfileRead
  {
   datetime cycle_start;
   string   name;           // "AMDX" / "XAMD"
   string   manipulation;   // "Q2" / "Q3"
   datetime knowable_at;    // = Q1.end
   double   q1_high;
   double   q1_low;
   double   prev_q4_high;
   double   prev_q4_low;
  };

struct SDManipulation
  {
   datetime cycle_start;
   string   profile;
   datetime quarter_start;  // kuarter manipulasi
   datetime quarter_end;
   datetime swept_start;    // kuarter yang ekstremnya diambil, selalu yang sebelumnya
   datetime swept_end;
   double   level;          // ekstrem kuarter itu - KEPUTUSANNYA
   double   swing_level;    // swing confirmed tempat event SWEEP menyala
   int      direction;      // +1 wick ke atas, -1 ke bawah
   datetime sweep_time;
  };

//+------------------------------------------------------------------+
//| Batas 18:00 New York di atau sebelum `epoch`.                     |
//+------------------------------------------------------------------+
datetime SDDayCycleStart(datetime epoch)
  {
   datetime start=SDAtNyHour(epoch,18,0);
   return (start<=epoch) ? start : SDAtNyHour(epoch,18,-1);
  }

//+------------------------------------------------------------------+
//| Lima tepi cycle hari yang memuat `epoch`, plus awal cycle depan.   |
//|                                                                    |
//| Q1 18:00-00:00, Q2 00:00-06:00, Q3 06:00-12:00, Q4 12:00-18:00.    |
//| Tepi tengahnya dihitung dari TANGGAL HARI BERIKUTNYA, sama seperti  |
//| Python, karena cycle yang dibuka 18:00 Senin adalah cycle SELASA -  |
//| pelabelan yang dipakai seluruh modul quarter.                      |
//|                                                                    |
//| DIHITUNG LEWAT JAM DINDING, BUKAN LEWAT PENAMBAHAN DETIK. Hari DST  |
//| punya kuarter lima atau tujuh jam di dalamnya, dan grid yang        |
//| dibangun dengan span/4 akan meleset satu jam dua kali setahun.      |
//+------------------------------------------------------------------+
void SDDayCycleEdges(datetime epoch,datetime &edges[])
  {
   ArrayResize(edges,5);
   datetime start=SDDayCycleStart(epoch);
   edges[0]=start;
   MqlDateTime t;
   SDToNy(start,t);
   // Tanggal kalender New York milik hari BERIKUTNYA.
   MqlDateTime d;
   ZeroMemory(d);
   d.year=t.year; d.mon=t.mon; d.day=t.day;
   MqlDateTime nx;
   TimeToStruct(StructToTime(d)+86400,nx);
   int hours[4]={0,6,12,18};
   for(int i=0;i<4;i++)
      edges[i+1]=SDNyWall(nx.year,nx.mon,nx.day,hours[i],0);
  }

//+------------------------------------------------------------------+
//| Setiap kuarter degree `day` yang menimpa [from, to], urut waktu.   |
//|                                                                    |
//| Waktu yang tidak dimiliki kuarter mana pun tidak menghasilkan apa  |
//| pun, sama dengan Python: tidak ada Q5 sintetis.                    |
//+------------------------------------------------------------------+
int SDQuartersDay(datetime from,datetime to,SDQuarter &out[])
  {
   ArrayResize(out,0);
   int count=0;
   string labels[4]={"Q1","Q2","Q3","Q4"};
   datetime edges[];
   SDDayCycleEdges(from,edges);
   datetime cursor=edges[0];
   // Batas iterasi: satu cycle hari itu 24 jam, jadi jumlah cycle di jendela
   // mana pun terhingga. 4000 melewati sepuluh tahun dengan margin, dan ia ada
   // supaya sebuah bug jam tidak jadi loop tanpa akhir di dalam terminal.
   for(int guard=0;guard<4000;guard++)
     {
      SDDayCycleEdges(cursor,edges);
      for(int i=0;i<4;i++)
        {
         if(edges[i]<=to && edges[i+1]>from)
           {
            ArrayResize(out,count+1);
            out[count].label=labels[i];
            out[count].start=edges[i];
            out[count].end  =edges[i+1];
            count++;
           }
        }
      if(edges[4]>to)
         break;
      cursor=edges[4];
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Keempat kuarter cycle yang dibuka `cycle_start`, urut Q1..Q4.      |
//+------------------------------------------------------------------+
bool SDCycleQuarters(datetime cycle_start,SDQuarter &out[])
  {
   datetime edges[];
   SDDayCycleEdges(cycle_start,edges);
   if(edges[0]!=cycle_start)
      return false;   // bukan batas Q1, dan itu kesalahan pemanggil
   ArrayResize(out,4);
   string labels[4]={"Q1","Q2","Q3","Q4"};
   for(int i=0;i<4;i++)
     {
      out[i].label=labels[i];
      out[i].start=edges[i];
      out[i].end  =edges[i+1];
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Apakah kuarter itu SUDAH selesai, dibuktikan dari bar-nya sendiri. |
//|                                                                    |
//| Sebuah bar yang open-nya di atau setelah ujungnya adalah buktinya:  |
//| ia tidak bisa ada sebelum bar terakhir kuarter itu close. Menahan   |
//| jawaban satu bar lagi saat feed berhenti tepat di batasnya adalah   |
//| arah yang konservatif, dan konservatif satu-satunya arah yang aman  |
//| untuk uji knowability.                                             |
//+------------------------------------------------------------------+
bool SDQuarterClosed(const datetime &time_[],int n,datetime quarter_end)
  {
   return (n>0 && time_[n-1]>=quarter_end);
  }

//+------------------------------------------------------------------+
//| Ekstrem bar yang open-nya di [start, end). false kalau kosong.     |
//+------------------------------------------------------------------+
bool SDWindowExtremes(const double &high[],const double &low[],
                      const datetime &time_[],int n,
                      datetime start,datetime end,double &hi,double &lo)
  {
   int a=SDLowerBound(time_,n,start);
   int b=SDLowerBound(time_,n,end);
   if(b<=a)
      return false;
   hi=high[a]; lo=low[a];
   for(int i=a+1;i<b;i++)
     {
      if(high[i]>hi) hi=high[i];
      if(low[i]<lo)  lo=low[i];
     }
   return true;
  }

//+------------------------------------------------------------------+
//| DFR Bucko untuk satu cycle: buang sepertiga PERTAMA Q1, ambil sisa.|
//|                                                                    |
//| false saat Q1 belum terbukti tutup, saat jendela dua-pertiga yang  |
//| disimpan tidak memuat satu bar pun, DAN saat jendela itu mulai     |
//| sebelum bar pertama - yang ketiga itu penjaga REPAINT dan bukan    |
//| kerapian: `SDQuarterClosed` membuktikan Q1 berakhir, tidak ada yang|
//| membuktikan ia MULAI di dalam data, jadi pita yang dua-pertiganya  |
//| mulai sebelum bar pertama dihitung dari pecahan yang kebetulan ada |
//| dan ia BERGERAK saat jendelanya diperlebar ke belakang. Diukur di  |
//| Python pada 20.000 bar emas 1 jam: tiga pita berubah high, low dan |
//| setiap proyeksi di atasnya.                                        |
//+------------------------------------------------------------------+
bool SDDefiningRange(const double &high[],const double &low[],
                     const datetime &time_[],int n,datetime cycle_start,
                     SDDfr &out)
  {
   SDQuarter cycle[];
   if(!SDCycleQuarters(cycle_start,cycle))
      return false;
   datetime q1s=cycle[0].start,q1e=cycle[0].end;
   if(!SDQuarterClosed(time_,n,q1e))
      return false;

   datetime kept_from=q1s+(datetime)((q1e-q1s)/3);
   if(n==0 || time_[0]>kept_from)
      return false;

   double hi,lo;
   if(!SDWindowExtremes(high,low,time_,n,kept_from,q1e,hi,lo))
      return false;

   out.cycle_start=q1s;
   out.start      =kept_from;
   out.end        =q1e;
   out.high       =hi;
   out.low        =lo;
   return true;
  }

//+------------------------------------------------------------------+
//| AMDX atau XAMD, dibaca dari Q1 SETELAH Q1 tutup.                   |
//|                                                                    |
//| Q1 termuat di dalam range Q4 cycle sebelumnya -> AMDX, kuarter     |
//| manipulasinya Q2. Q1 keluar dari range itu -> XAMD, Q3.            |
//|                                                                    |
//| TIDAK ADA YANG MENGKLAIM INI BISA DIRAMAL SEBELUM Q1 TUTUP, dan    |
//| kode ini juga tidak: minta profil cycle yang Q1-nya masih terbentuk|
//| dan yang keluar false. Bukan dugaan, bukan label sementara, bukan  |
//| jawaban cycle sebelumnya yang dibawa maju.                         |
//+------------------------------------------------------------------+
bool SDProfileAt(const double &high[],const double &low[],
                 const datetime &time_[],int n,datetime cycle_start,
                 SDProfileRead &out)
  {
   SDQuarter cycle[];
   if(!SDCycleQuarters(cycle_start,cycle))
      return false;
   if(!SDQuarterClosed(time_,n,cycle[0].end))
      return false;

   // Q4 cycle SEBELUMNYA: cycle sebelumnya dibuka satu hari lebih awal, dan
   // Q4-nya kuarter terakhirnya. Dihitung lewat jam dinding lagi, bukan lewat
   // pengurangan 86400 dari Q1.start.
   datetime prev_start=SDAtNyHour(cycle_start,18,-1);
   SDQuarter prev[];
   if(!SDCycleQuarters(prev_start,prev))
      return false;

   double q4h,q4l,q1h,q1l;
   if(!SDWindowExtremes(high,low,time_,n,prev[3].start,prev[3].end,q4h,q4l))
      return false;
   if(!SDWindowExtremes(high,low,time_,n,cycle[0].start,cycle[0].end,q1h,q1l))
      return false;

   bool inside=(q1h<=q4h && q1l>=q4l);
   out.cycle_start =cycle_start;
   out.name        =inside?"AMDX":"XAMD";
   out.manipulation=inside?"Q2":"Q3";
   out.knowable_at =cycle[0].end;
   out.q1_high     =q1h;
   out.q1_low      =q1l;
   out.prev_q4_high=q4h;
   out.prev_q4_low =q4l;
   return true;
  }

//+------------------------------------------------------------------+
//| Kedua paruh, atau tidak ada: kuarter manipulasi DAN sweep di dalamnya.
//|
//| Sweep pertama yang memenuhi syarat yang dilaporkan, karena pertanyaan
//| yang dijawab "manipulation sudah?" dan yang pertama sudah menyelesaikannya.
//|
//| `n_fractal` adalah lebar fraktal yang diserahkan ke `SDBreaks`. Ia
//| KNOB dan bukan angka dari sumber mana pun; Python default 2 dan angka
//| itu disalin apa adanya supaya kedua sisi membandingkan hal yang sama.
//+------------------------------------------------------------------+
bool SDManipulationDone(const double &high[],const double &low[],
                        const double &close[],const datetime &time_[],int n,
                        datetime cycle_start,int n_fractal,
                        SDManipulation &out)
  {
   SDProfileRead shape;
   if(!SDProfileAt(high,low,time_,n,cycle_start,shape))
      return false;

   SDQuarter cycle[];
   if(!SDCycleQuarters(cycle_start,cycle))
      return false;

   // Kuarter manipulasi, dan kuarter yang ekstremnya diambil: selalu yang
   // TEPAT SEBELUMNYA. Q1 di bawah AMDX, Q2 di bawah XAMD.
   int mi=(shape.manipulation=="Q2")?1:2;
   int si=mi-1;
   SDQuarter window=cycle[mi];
   SDQuarter swept =cycle[si];

   double shi,slo;
   if(!SDWindowExtremes(high,low,time_,n,swept.start,swept.end,shi,slo))
      return false;

   SDBreak events[];
   SDSwing found[];
   int ne=SDBreaks(high,low,close,time_,n,n_fractal,n_fractal,events,found);
   for(int i=0;i<ne;i++)
     {
      if(events[i].kind!="SWEEP")
         continue;
      if(!(window.start<=events[i].time && events[i].time<window.end))
         continue;
      int bar=events[i].index;
      bool took=(events[i].direction==1) ? (high[bar]>shi) : (low[bar]<slo);
      if(!took)
         continue;
      out.cycle_start  =cycle_start;
      out.profile      =shape.name;
      out.quarter_start=window.start;
      out.quarter_end  =window.end;
      out.swept_start  =swept.start;
      out.swept_end    =swept.end;
      out.level        =(events[i].direction==1)?shi:slo;
      out.swing_level  =events[i].level;
      out.direction    =events[i].direction;
      out.sweep_time   =events[i].time;
      return true;
     }
   return false;
  }
//+------------------------------------------------------------------+
