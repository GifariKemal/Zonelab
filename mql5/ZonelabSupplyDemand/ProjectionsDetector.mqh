//+------------------------------------------------------------------+
//|                                        ProjectionsDetector.mqh   |
//|  Port faithful dari backend/app/projections.py::projection.       |
//|                                                                   |
//|  Kelipatan dari tinggi sebuah range, diproyeksikan dari tepi yang |
//|  harga tinggalkan. Range-nya datang dari `SDLiquidityPools`, bukan |
//|  dipotong ulang di sini, supaya jendela yang diukur proyeksi       |
//|  identik byte-per-byte dengan jendela yang menggambar ray pool.    |
//|  Dua objek yang berbeda pendapat tentang di mana London berada     |
//|  lebih buruk daripada salah satunya salah.                         |
//|                                                                   |
//|  `direction` adalah DESKRIPSI kaki yang diukur, bukan ramalan      |
//|  tentang kaki berikutnya. +1 saat harga keluar ke atas, -1 ke      |
//|  bawah, dan ia memilih tepi mana yang jadi origin.                 |
//|                                                                   |
//|  ENAM LEVEL DEFAULT ADALAH TRANSKRIPSI, BUKAN KUTIPAN. Angka       |
//|  0, -0,5, -1,0, -1,5, 2,0 dan 2,5 disalin dari chart pemiliknya    |
//|  sendiri, dan tidak ada hit rate yang pernah diukur untuknya di    |
//|  sini maupun di sumber mana pun yang bisa ditunjuk project ini.    |
//|                                                                   |
//|  app/layers.py mencatat MEASURED NULL: +0,46pp lawan kontrol       |
//|  jitter per-event, 6,5 kali di bawah ambang praregistrasi,         |
//|  walk-forward 6 dari 8, p = 0,29.                                  |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "PoolsDetector.mqh"

//: Enam label yang ditranskripsi dari chart pemiliknya. Bukan parameter di
//: dump ini, supaya kedua sisi tidak bisa berbeda pendapat tentang level mana
//: yang sedang dibandingkan.
#define SD_PROJ_LEVELS 6

void SDProjectionLevels(double &out[])
  {
   ArrayResize(out,SD_PROJ_LEVELS);
   out[0]=0.0; out[1]=-0.5; out[2]=-1.0; out[3]=-1.5; out[4]=2.0; out[5]=2.5;
  }

struct SDProjection
  {
   string   session;
   datetime window_from;
   datetime window_to;
   int      direction;
   double   multiple;
   double   price;
   double   origin;
   double   height;
   int      bars;
   datetime knowable_at;
   datetime taken_at;   // 0 = belum diambil
  };

//+------------------------------------------------------------------+
//| Proyeksi untuk SETIAP session range, kedua arah, enam level.       |
//|                                                                    |
//| UI Python hanya menggambar range TERBARU, dan itu keputusan        |
//| tampilan bukan doktrin: enam level kali dua arah kali dua sesi     |
//| adalah 24 garis. Dump ini menghitung semuanya, karena yang diuji   |
//| di sini aritmetikanya di seluruh deret dan bukan keputusan berapa  |
//| banyak yang layak digambar.                                        |
//+------------------------------------------------------------------+
int SDProjections(const double &high[],const double &low[],const datetime &time_[],
                  int n,const string &sessions[],SDProjection &out[])
  {
   ArrayResize(out,0);
   int count=0;
   if(n==0)
      return 0;

   SDPool pools[];
   int npool=SDLiquidityPools(high,low,time_,n,sessions,pools);

   double mults[];
   SDProjectionLevels(mults);

   // Pool datang berpasangan BSL lalu SSL untuk satu jendela, dalam urutan
   // yang sama dengan Python menghasilkannya, jadi pasangannya dibaca dua-dua
   // alih-alih dicocokkan lewat map.
   for(int i=0;i+1<npool;i+=2)
     {
      if(pools[i].window_from!=pools[i+1].window_from ||
         pools[i].session!=pools[i+1].session)
         continue;   // dijaga, bukan diasumsikan
      double hi=pools[i].price;      // BSL, high sesi
      double lo=pools[i+1].price;    // SSL, low sesi
      if(hi<lo)
         continue;

      double height=hi-lo;
      int lo_idx=SDLowerBound(time_,n,pools[i].window_to);
      if(lo_idx>=n)
         continue;

      for(int s=0;s<2;s++)
        {
         int direction=(s==0)?1:-1;
         double origin=(direction<0)?lo:hi;
         for(int m=0;m<SD_PROJ_LEVELS;m++)
           {
            double price=origin-direction*mults[m]*height;
            // Kelipatan di atau di bawah 0 berada di SISI PERJALANAN dari
            // origin, jadi ia di bawah saat perjalanan turun dan di atas saat
            // naik; kelipatan positif ada di sisi seberangnya. Diputuskan dari
            // TANDANYA dan bukan dengan membandingkan harga, supaya range yang
            // datar - semua level di origin - tetap menanyakan pertanyaan yang
            // benar.
            bool above=(direction<0)?(mults[m]>0):(mults[m]<=0);
            ArrayResize(out,count+1);
            out[count].session    =pools[i].session;
            out[count].window_from=pools[i].window_from;
            out[count].window_to  =pools[i].window_to;
            out[count].direction  =direction;
            out[count].multiple   =mults[m];
            out[count].price      =price;
            out[count].origin     =origin;
            out[count].height     =height;
            out[count].bars       =pools[i].bars;
            out[count].knowable_at=pools[i].knowable_at;
            out[count].taken_at   =SDTakenAt(high,low,time_,lo_idx,n,price,above);
            count++;
           }
        }
     }
   return count;
  }
//+------------------------------------------------------------------+
