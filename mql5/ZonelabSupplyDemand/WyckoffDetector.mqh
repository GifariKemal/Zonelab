//+------------------------------------------------------------------+
//|                                            WyckoffDetector.mqh   |
//|  Port setia dari app/wyckoff.py::phases.                          |
//|                                                                   |
//|  INI JUGA DETEKTOR BREAKOUT, dan itu bukan penamaan ulang yang    |
//|  longgar: `sos` adalah close di ATAS trading range high, yaitu    |
//|  range breakout naik yang dikonfirmasi close, dan `sow` yang      |
//|  turun. `spring` dan `upthrust` adalah false breakout di kedua    |
//|  sisi - wick melewati tepi, close balik ke dalam.                 |
//|                                                                   |
//|  RIG PYTHON SUDAH MENGUKURNYA NULL, dan port ini bukan hipotesis  |
//|  baru. docs/wyckoff_outcomes.json: empat fase lawan drift         |
//|  instrumennya sendiri di sembilan instrumen, `sos` n=19.667        |
//|  t=-0,95 dengan 13 dari 36 fold positif, yaitu di bawah           |
//|  kebetulan. Yang port ini jawab pertanyaan LAIN: apakah           |
//|  Strategy Tester dengan real tick dan biaya terminal setuju.      |
//|  Kedua rig itu pernah tidak sepakat di 6 dari 8 sel               |
//|  (docs/mt5_python_parity.json), jadi null di Python pada resolusi  |
//|  bar tidak menyelesaikan apa yang MT5 katakan.                    |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "SupplyDemandDetector.mqh"

enum ENUM_WYK_KIND
  {
   WYK_SPRING = 0,   // wick di bawah TR low, close balik ke dalam
   WYK_UPTHRUST = 1, // wick di atas TR high, close balik ke dalam
   WYK_SOS = 2,      // close di atas TR high  -> breakout naik
   WYK_SOW = 3       // close di bawah TR low  -> breakout turun
  };

struct WykParams
  {
   int lookback;   // 20, sama dengan default WyckoffParams
  };

struct WykPhase
  {
   ENUM_WYK_KIND kind;
   int      at;          // indeks bar event
   double   level;       // tepi TR yang disapu atau ditembus
   double   tr_low;
   double   tr_high;
   int      tr_from;     // bar pertama window range
   datetime time_at;
   long     ticks;       // tick_volume bar event, BUKAN volume transaksi
   double   ticks_median; // median tick_volume window range
  };

//+------------------------------------------------------------------+
//| Median sebuah slice long[]. Dipakai untuk baseline hitungan tick. |
//| Insertion sort atas salinan: window-nya 20 bar, jadi O(n^2) di    |
//| sini lebih murah daripada mengalokasi struktur lain.              |
//+------------------------------------------------------------------+
double WykMedianTicks(const long &vol[],int from,int count)
  {
   if(count<=0)
      return 0.0;
   long tmp[];
   ArrayResize(tmp,count);
   for(int i=0;i<count;i++)
      tmp[i]=vol[from+i];
   for(int i=1;i<count;i++)
     {
      long key=tmp[i];
      int j=i-1;
      while(j>=0 && tmp[j]>key)
        {
         tmp[j+1]=tmp[j];
         j--;
        }
      tmp[j+1]=key;
     }
   if(count%2==1)
      return (double)tmp[count/2];
   return 0.5*((double)tmp[count/2-1]+(double)tmp[count/2]);
  }

//+------------------------------------------------------------------+
//| Deteksi fase Wyckoff. Return jumlah fase.                         |
//|                                                                   |
//| URUTAN PEMERIKSAANNYA MENGIKAT dan disalin apa adanya dari        |
//| app/wyckoff.py: sweep yang ditolak diperiksa LEBIH DULU, karena   |
//| close yang balik ke dalam range bukan break atas range itu.       |
//| Membalik urutannya akan mengklasifikasikan setiap spring sebagai  |
//| sow dan setiap upthrust sebagai sos.                              |
//|                                                                   |
//| Dan sebuah bar membawa PALING BANYAK satu fase, sama seperti di   |
//| Python: `continue` sesudah sweep, bukan pemeriksaan lanjutan.     |
//+------------------------------------------------------------------+
int DetectWyckoff(const double &open_[],const double &high[],const double &low[],
                  const double &close[],const datetime &time[],const long &vol[],
                  int n,const WykParams &p,WykPhase &out[])
  {
   ArrayResize(out,0);
   if(p.lookback<1 || n<=p.lookback)
      return 0;

   int count=0;
   for(int i=p.lookback;i<n;i++)
     {
      // Window = `lookback` bar yang BERAKHIR SEBELUM bar i, jadi bar event
      // sendiri tidak pernah masuk range yang ia diuji terhadapnya. Itu yang
      // membuatnya no-lookahead.
      double tr_high=high[i-p.lookback];
      double tr_low =low[i-p.lookback];
      for(int j=i-p.lookback+1;j<i;j++)
        {
         if(high[j]>tr_high) tr_high=high[j];
         if(low[j]<tr_low)   tr_low=low[j];
        }

      double o=open_[i], h=high[i], l=low[i], c=close[i];
      // KEDUANYA DIINISIALISASI, dan compiler yang benar soal ini: ia tidak
      // bisa membuktikan bahwa `found` menjamin keduanya terisi. Invarian yang
      // bergantung pada pembacaan alur adalah invarian yang bisa pecah tanpa
      // suara saat cabang kelima ditambahkan, dan warning 60 justru yang
      // memperingatkannya.
      ENUM_WYK_KIND kind=WYK_SPRING;
      double level=0.0;
      bool found=false;

      // Sweep plus rejection. Bar-nya wajib DATANG dari sisi dekat, yaitu
      // open di dalam range: itu operasionalisasi "purge" yang sama dengan
      // app/psp.py, dan tanpa syarat itu sebuah bar yang membuka jauh di luar
      // range lalu ditutup di dalamnya akan terhitung sebagai spring.
      if(o>=tr_low && l<tr_low && c>tr_low)
        {
         kind=WYK_SPRING;
         level=tr_low;
         found=true;
        }
      else if(o<=tr_high && h>tr_high && c<tr_high)
        {
         kind=WYK_UPTHRUST;
         level=tr_high;
         found=true;
        }
      else if(c>tr_high)
        {
         kind=WYK_SOS;
         level=tr_high;
         found=true;
        }
      else if(c<tr_low)
        {
         kind=WYK_SOW;
         level=tr_low;
         found=true;
        }

      if(!found)
         continue;

      ArrayResize(out,count+1);
      out[count].kind=kind;
      out[count].at=i;
      out[count].level=level;
      out[count].tr_low=tr_low;
      out[count].tr_high=tr_high;
      out[count].tr_from=i-p.lookback;
      out[count].time_at=time[i];
      // HITUNGAN TICK, DIBERI NAMA HITUNGAN TICK. Kedua deskripsi metode
      // breakout menuntut "konfirmasi volume" sebagai bukti partisipasi
      // institusi, dan volume itu TIDAK ADA di feed ini: `real_volume`
      // terukur NOL di kedelapan instrumen yang broker ini layani (XAUUSD,
      // XAGUSD, EURUSD, GBPUSD, USDJPY, US30, USOIL, BTCUSD). Yang ada
      // hitungan tick, yaitu seberapa sering feed broker memperbarui, dan itu
      // besaran yang berbeda serta berbeda antar broker.
      //
      // Ia tetap dibawa supaya arm filternya bisa diukur, tapi namanya tidak
      // boleh berbohong tentang apa yang ia hitung.
      out[count].ticks=vol[i];
      out[count].ticks_median=WykMedianTicks(vol,i-p.lookback,p.lookback);
      count++;
     }
   return count;
  }
//+------------------------------------------------------------------+
