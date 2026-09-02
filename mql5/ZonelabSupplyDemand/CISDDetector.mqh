//+------------------------------------------------------------------+
//|                                                CISDDetector.mqh  |
//|  Port faithful dari backend/app/cisd.py.                          |
//|  CISD = sebuah close melewati OPEN dari run berlawanan terakhir.  |
//|  Konvensi index sama: 0 = bar tertua.                             |
//|                                                                   |
//|  INI BUKAN BOX. Ia EVENT plus satu level horizontal, jadi ia      |
//|  tidak muat di SDZone dan tidak dibandingkan oleh komparator zona. |
//|  Pembandingnya `tools/mqh_parity.py` lewat CSV event terpisah.    |
//|                                                                   |
//|  ARAHNYA SUDAH DIUKUR DAN NULL. app/layers.py: delta -0,0195 ATR, |
//|  t = -0,53, dan spread instrumen 13 kali lipat edge yang negatif   |
//|  itu. Port ini ada untuk membuktikan presisi, bukan untuk trade.   |
//|  Zonelab sendiri tidak punya jalur order dari CISD: satu-satunya   |
//|  pemakaian di app/poi.py:128 adalah MENGHITUNG berapa level jatuh  |
//|  di dalam pita sebuah zona.                                       |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

struct CISDParamsMQ
  {
   int min_run;             // 2
   int interrupt_tolerance; // 0
  };

//+------------------------------------------------------------------+
//| Satu delivery run: deretan lilin yang close-nya searah.           |
//+------------------------------------------------------------------+
struct SDRun
  {
   int    start;        // index lilin pertama; open-nya yang jadi level
   int    end;          // index lilin conforming TERAKHIR, inklusif
   int    direction;    // +1 up-close, -1 down-close
   double open_price;
   int    confirmed_at; // bar saat ujung run jadi diketahui
   int    length;       // hanya lilin conforming, interupsi tidak dihitung
  };

//+------------------------------------------------------------------+
//| Satu event CISD.                                                  |
//+------------------------------------------------------------------+
struct SDCisd
  {
   int      index;      // bar yang menembus, dan bar ia diketahui
   datetime time;
   int      direction;  // +1 close di atas open run turun, -1 sebaliknya
   double   level;      // open lilin PERTAMA run itu
   int      run_start;
   int      run_end;
   int      run_length;
  };

//+------------------------------------------------------------------+
//| +1 up-close, -1 down-close, 0 tidak keduanya.                     |
//|                                                                   |
//| `close == open` TIDAK men-deliver apa pun, jadi ia non-conforming |
//| dan bukan diam-diam dihitung sebagai kelanjutan. Itu yang membuat |
//| deret datar menghasilkan nol run alih-alih run yang tak bisa      |
//| dijadikan anchor oleh siapa pun.                                  |
//+------------------------------------------------------------------+
int SDDelivery(double open_price,double close_price)
  {
   if(close_price>open_price)
      return 1;
   if(close_price<open_price)
      return -1;
   return 0;
  }

//+------------------------------------------------------------------+
//| Delivery run yang tidak tumpang tindih, masing-masing distempel   |
//| kapan ujungnya diketahui. Satu lintasan maju.                     |
//|                                                                   |
//| Run yang MASIH BERJALAN di lilin terakhir TIDAK dikembalikan.     |
//| Ujungnya belum diketahui, jadi ia tidak bisa jadi anchor apa pun, |
//| dan mengeluarkannya berarti menaruh objek belum terkonfirmasi di  |
//| daftar yang sama dengan yang sudah.                               |
//+------------------------------------------------------------------+
int SDDeliveryRuns(const double &open_[],const double &close_[],int n,
                   int interrupt_tolerance,SDRun &runs[])
  {
   ArrayResize(runs,0);
   int count=0;
   int i=0;
   while(i<n)
     {
      int direction=SDDelivery(open_[i],close_[i]);
      if(direction==0)
        {
         i++;
         continue;
        }

      int start=i;
      int end=i;
      int length=1;
      int opposing=0;
      int confirmed_at=-1;
      for(int j=i+1;j<n;j++)
        {
         if(SDDelivery(open_[j],close_[j])==direction)
           {
            end=j;
            length++;
            opposing=0;
           }
         else
           {
            opposing++;
            if(opposing>interrupt_tolerance)
              {
               confirmed_at=j;
               break;
              }
           }
        }

      if(confirmed_at>=0)
        {
         ArrayResize(runs,count+1);
         runs[count].start       =start;
         runs[count].end         =end;
         runs[count].direction   =direction;
         runs[count].open_price  =open_[start];
         runs[count].confirmed_at=confirmed_at;
         runs[count].length      =length;
         count++;
        }
      // Lanjut dari end+1, jadi run tidak pernah tumpang tindih.
      i=end+1;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| Jalan sekali lewat bar, memancarkan CISD tiap kali sebuah close   |
//| melewati level. Run terkonfirmasi TERBARU di tiap sisi dipegang   |
//| hidup, sebuah level hanya bisa diambil sekali, dan bar `i` tidak  |
//| melihat apa pun yang belum diketahui di `i`.                      |
//|                                                                   |
//| Daftar run yang dikembalikan TIDAK difilter: `min_run` menentukan |
//| run mana yang boleh mengarmkan level, bukan run mana yang ada.    |
//+------------------------------------------------------------------+
int SDCisds(const double &open_[],const double &close_[],const datetime &time_[],
            int n,const CISDParamsMQ &p,SDCisd &out[],SDRun &runs[])
  {
   ArrayResize(out,0);
   int run_count=SDDeliveryRuns(open_,close_,n,p.interrupt_tolerance,runs);

   int live_down=-1;   // index ke runs[], -1 = tidak ada
   int live_up=-1;
   int count=0;

   for(int i=0;i<n;i++)
     {
      // Arm level dari run yang terkonfirmasi TEPAT di bar ini.
      for(int r=0;r<run_count;r++)
        {
         if(runs[r].confirmed_at!=i || runs[r].length<p.min_run)
            continue;
         if(runs[r].direction<0)
            live_down=r;
         else
            live_up=r;
        }

      // Close-nya, tidak pernah wick-nya. Up dievaluasi sebelum down supaya
      // sebuah bar yang menembus KEDUA level hidup memancarkan dua-duanya
      // alih-alih yang satu menelan yang lain diam-diam - pilihan yang sama
      // yang `walk_breaks` nyatakan untuk outside bar, dan tidak ada sumber
      // yang membahas kasus ini.
      if(live_down>=0 && close_[i]>runs[live_down].open_price)
        {
         ArrayResize(out,count+1);
         out[count].index     =i;
         out[count].time      =time_[i];
         out[count].direction =1;
         out[count].level     =runs[live_down].open_price;
         out[count].run_start =runs[live_down].start;
         out[count].run_end   =runs[live_down].end;
         out[count].run_length=runs[live_down].length;
         count++;
         live_down=-1;
        }
      if(live_up>=0 && close_[i]<runs[live_up].open_price)
        {
         ArrayResize(out,count+1);
         out[count].index     =i;
         out[count].time      =time_[i];
         out[count].direction =-1;
         out[count].level     =runs[live_up].open_price;
         out[count].run_start =runs[live_up].start;
         out[count].run_end   =runs[live_up].end;
         out[count].run_length=runs[live_up].length;
         count++;
         live_up=-1;
        }
     }
   return count;
  }
//+------------------------------------------------------------------+
