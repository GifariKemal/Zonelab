//+------------------------------------------------------------------+
//|                                                GapsDetector.mqh  |
//|  Port faithful dari backend/app/gaps.py: `opening_gaps` dan       |
//|  `event_horizons`. NDOG dan NWOG, plus level di antaranya.        |
//|                                                                   |
//|  SATU-SATUNYA OBJEK DI SURVEI INI YANG TIDAK BEKU SAAT LAHIR.     |
//|  Sebuah gap beku: kedua harganya tetap begitu kedua bar-nya ada.  |
//|  Sebuah EVENT HORIZON tidak: ia rata-rata antara dua gap yang     |
//|  bertetangga MENURUT HARGA, jadi gap baru yang menyisip di antara |
//|  dua gap lama menggeser level yang sudah tergambar tanpa satu     |
//|  harga pun berubah. Itu sebabnya `event_horizons` di Python punya |
//|  parameter `as_of`, dan sebabnya port ini menuliskannya sebagai   |
//|  fungsi dari bar, bukan sebagai daftar tunggal.                    |
//|                                                                   |
//|  APAKAH INSTRUMEN INI PERNAH TUTUP. Ditanyakan sekali tentang     |
//|  DERETNYA, bukan sekali per batas. Deret yang diperdagangkan 24/7 |
//|  tidak punya interval tanpa perdagangan, jadi ia tidak punya      |
//|  opening gap - tapi kedua lookup akan dengan senang hati          |
//|  menemukan bar sebelum 17:00 dan bar di 18:00 lalu melaporkan     |
//|  jaraknya. Lebih buruk dari sekadar angka salah: pada bar per jam |
//|  yang rapi uji ketepatannya LOLOS, jadi pita karangan itu terkirim|
//|  dengan flag `approximate=false`. Diukur 19 Agustus 2026 di       |
//|  binance BTCUSDT 1h: 29 pita semacam itu, semuanya berflag exact. |
//|                                                                   |
//|  SUDAH DIUKUR, DAN NEGATIF. app/layers.py: respect di sentuhan CE |
//|  pertama keluar -0,58 ATR, t = -2,54, walk-forward 2 dari 8.      |
//|  Harga MENERUSKAN lewat level itu.                                 |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "NYClock.mqh"
#include "PoolsDetector.mqh"   // SDLowerBound

#define SD_GAP_KEEP_DEFAULT 5

struct SDGap
  {
   string   kind;        // "NDOG" / "NWOG"
   double   top;
   double   bottom;
   datetime close_time;  // bar yang CLOSE-nya memberi satu tepi
   datetime open_time;   // bar yang OPEN-nya memberi tepi lainnya
   bool     approximate;
  };

struct SDHorizon
  {
   double   price;
   datetime lower_open_time;
   datetime upper_open_time;
   datetime as_of;
  };

//+------------------------------------------------------------------+
//| Gap yang open 18:00-nya `open_at`, atau found=false kalau salah   |
//| satu bar-nya tidak ada.                                            |
//|                                                                    |
//| Kedua bar dibatasi ke SESINYA SENDIRI, dan itu yang membuat hari  |
//| libur mengembalikan nol alih-alih menjangkau mundur atau maju ke  |
//| harga milik hari lain.                                             |
//+------------------------------------------------------------------+
bool SDGapAt(const double &open_[],const double &close_[],const datetime &time_[],
             int n,datetime open_at,string kind,SDGap &out)
  {
   // Sesi penutup sebuah NDOG berakhir 17:00 hari yang sama; sebuah NWOG
   // berakhir 17:00 hari Jumat, dua hari sebelum pembukaan Minggu.
   int close_off=(kind=="NDOG")?0:-2;
   datetime close_at =SDAtNyHour(open_at,17,close_off);
   datetime close_from=SDAtNyHour(open_at,18,close_off-1);
   datetime open_to  =SDAtNyHour(open_at,17,1);

   int i_close=SDLowerBound(time_,n,close_at)-1;   // bar terakhir yang open sebelum 17:00
   if(i_close<0 || time_[i_close]<close_from)
      return false;
   int i_open=SDLowerBound(time_,n,open_at);       // bar pertama yang open di atau setelah 18:00
   if(i_open>=n || time_[i_open]>=open_to)
      return false;

   // Ketepatan harus DIBUKTIKAN, bukan diasumsikan. Lebar bar penutup dibaca
   // dari pendahulunya - bar SESUDAHNYA adalah bar 18:00, karena tidak ada bar
   // yang berdagang antara 17:00 dan 18:00, jadi step-nya tidak bisa diukur ke
   // depan. Lubang di feed sebelum bar penutup membuat step yang tersimpul
   // terlalu lebar dan gap-nya melaporkan approximate, yang adalah arah yang
   // aman untuk salah di sini.
   int step=(i_close>0)?(int)(time_[i_close]-time_[i_close-1]):0;
   bool exact=(step>0 && time_[i_close]+step==close_at && time_[i_open]==open_at);

   double last=close_[i_close];
   double first=open_[i_open];
   out.kind       =kind;
   out.top        =MathMax(last,first);
   out.bottom     =MathMin(last,first);
   out.close_time =time_[i_close];
   out.open_time  =time_[i_open];
   out.approximate=!exact;
   return true;
  }

//+------------------------------------------------------------------+
//| Setiap NDOG dan NWOG yang bar-nya bisa dukung, urut waktu.        |
//|                                                                    |
//| Sebuah gap muncul di sini hanya setelah KEDUA harganya ada di     |
//| data, jadi deret yang terpotong sebelum bar 18:00 tidak           |
//| menghasilkan gap untuk batas itu: aturan anti-lookahead jatuh dari|
//| definisinya, bukan ditegakkan di atasnya. Gap selebar nol tetap   |
//| gap dan tetap dikembalikan, karena "tidak ada gap hari ini" adalah|
//| fakta tentang pasar, dan membuangnya akan diam-diam mengubah      |
//| pasangan Event Horizon.                                            |
//+------------------------------------------------------------------+
int SDOpeningGaps(const double &open_[],const double &close_[],const datetime &time_[],
                  int n,SDGap &out[],bool &traded_through)
  {
   ArrayResize(out,0);
   traded_through=false;
   if(n==0)
      return 0;

   // Deret yang tidak pernah tutup tidak punya opening gap. Diperiksa lewat
   // lubang di grid bar-nya sendiri, dan HANYA di tempat bar-nya bisa melihat
   // lubang itu: jendela tutup harian selebar satu jam, jadi pada bar satu jam
   // atau kurang ketiadaannya adalah bukti, dan pada yang lebih kasar ia bukan
   // apa-apa. Grid 4 jam yang berjalan 06:00, 10:00, 14:00, 18:00 mulus baik
   // pasarnya tutup di 17:00 maupun tidak.
   if(n>2)
     {
      int smallest=(int)(time_[1]-time_[0]);
      for(int i=2;i<n;i++)
        {
         int g=(int)(time_[i]-time_[i-1]);
         if(g<smallest) smallest=g;
        }
      bool seamless=true;
      for(int i=1;i<n;i++)
         if((int)(time_[i]-time_[i-1])>smallest) { seamless=false; break; }
      if(smallest>0 && smallest<=3600 && seamless)
        {
         traded_through=true;
         return 0;
        }
     }

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
   datetime day=StructToTime(dz);

   while(day<=last_day)
     {
      MqlDateTime d;
      TimeToStruct(day,d);
      // Python memakai weekday() dengan Senin=0; MQL5 day_of_week Minggu=0.
      // Senin sampai Kamis -> NDOG, Minggu -> NWOG.
      string kind="";
      if(d.day_of_week>=1 && d.day_of_week<=4)
         kind="NDOG";
      else if(d.day_of_week==0)
         kind="NWOG";

      if(kind!="")
        {
         SDGap g;
         if(SDGapAt(open_,close_,time_,n,SDNyWall(d.year,d.mon,d.day,18,0),kind,g))
           {
            ArrayResize(out,count+1);
            out[count]=g;
            count++;
           }
        }
      day+=86400;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| N-1 level di antara N gap yang dipertahankan, urut harga.         |
//|                                                                    |
//| `as_of` ADALAH SELURUH MAKSUD tanda tangan ini: berikan waktu     |
//| sebuah bar dan yang keluar adalah himpunan level SEBAGAIMANA IA   |
//| BERDIRI di bar itu, satu-satunya cara jujur mengukur apa pun      |
//| terhadap objek yang bergerak setelah lahir.                        |
//|                                                                    |
//| `keep` mempertahankan gap terbaru menurut `open_time` dan membuang|
//| sisanya, dan mengubahnya mengubah level MANA yang ada, bukan cuma |
//| berapa banyak. 0 berarti simpan semua.                             |
//+------------------------------------------------------------------+
int SDEventHorizons(const SDGap &gaps[],int ngap,int keep,datetime as_of,
                    SDHorizon &out[])
  {
   ArrayResize(out,0);

   // Hidup pada `as_of`. 0 berarti "sekarang", yang adalah pertanyaan chart
   // dan bukan pertanyaan sebuah pengukuran.
   int live[];
   int nlive=0;
   for(int i=0;i<ngap;i++)
     {
      if(as_of!=0 && gaps[i].open_time>as_of)
         continue;
      ArrayResize(live,nlive+1);
      live[nlive++]=i;
     }
   if(nlive<2)
      return 0;

   // Urutkan menurut open_time lalu ambil `keep` terbaru. Insertion sort:
   // jumlahnya puluhan, dan stabilitasnya penting supaya dua gap dengan
   // open_time sama mempertahankan urutan kemunculannya seperti di Python.
   for(int i=1;i<nlive;i++)
     {
      int key=live[i];
      int j=i-1;
      while(j>=0 && gaps[live[j]].open_time>gaps[key].open_time)
        {
         live[j+1]=live[j];
         j--;
        }
      live[j+1]=key;
     }
   int start=0;
   if(keep>0 && nlive>keep)
      start=nlive-keep;

   int kept[];
   int nkept=0;
   for(int i=start;i<nlive;i++)
     {
      ArrayResize(kept,nkept+1);
      kept[nkept++]=live[i];
     }
   if(nkept<2)
      return 0;

   // Lalu urutkan menurut CE, titik tengah pita.
   for(int i=1;i<nkept;i++)
     {
      int key=kept[i];
      double kce=(gaps[key].top+gaps[key].bottom)/2.0;
      int j=i-1;
      while(j>=0 && (gaps[kept[j]].top+gaps[kept[j]].bottom)/2.0>kce)
        {
         kept[j+1]=kept[j];
         j--;
        }
      kept[j+1]=key;
     }

   int count=0;
   for(int i=0;i+1<nkept;i++)
     {
      int lower=kept[i],upper=kept[i+1];
      ArrayResize(out,count+1);
      out[count].price          =(gaps[lower].top+gaps[upper].bottom)/2.0;
      out[count].lower_open_time=gaps[lower].open_time;
      out[count].upper_open_time=gaps[upper].open_time;
      out[count].as_of          =as_of;
      count++;
     }
   return count;
  }
//+------------------------------------------------------------------+
