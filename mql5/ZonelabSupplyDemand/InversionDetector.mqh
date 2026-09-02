//+------------------------------------------------------------------+
//|                                            InversionDetector.mqh |
//|  Port faithful dari app/detect/inversion.py.                      |
//|  IFVG = fair value gap yang harganya sudah CLOSE menembusnya,      |
//|  dibaca dari sisi sebaliknya. BRK = versi order block-nya.         |
//|                                                                   |
//|  TIDAK ADA GEOMETRI BARU DI SINI, dan itu maksudnya. Rectangle,    |
//|  skala ATR, lantai gap dan ambang impulse semuanya datang dari     |
//|  detektor induk. Modul ini menyumbang satu keputusan, yaitu        |
//|  lifecycle box terbalik dimulai di `break_index + 1`, dan satu     |
//|  field, `inverted_at`. Ambang gap kedua untuk inversi akan membuat |
//|  dua populasinya menyimpang, jadi parameternya dipakai bersama.    |
//|                                                                   |
//|  JANGAN DIBACA SEBAGAI KLAIM ARAH. docs/CALIBRATION.md H8 mengukur |
//|  ketiga klaim arah inversi lawan kontrol yang hanya tahu gerakan   |
//|  20 bar terakhir, dan ketiganya SIGNIFIKAN NEGATIF: supply_demand  |
//|  -0,179 (t=-2,40), fvg -0,165 (t=-2,23), order_block -0,274        |
//|  (t=-4,22). Sebuah box IFVG menyatakan "pita ini berganti peran di |
//|  bar ini". Itu fakta tentang gambarnya, bukan tentang arah harga.  |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "SupplyDemandDetector.mqh"
#include "OrderBlockDetector.mqh"
#include "FVGDetector.mqh"

//+------------------------------------------------------------------+
//| Index bar dengan stempel waktu `t`, atau -1. Deret waktu naik,    |
//| jadi binary search. Padanan `index_of` di inversion.py, yang di   |
//| sana sebuah dict dan di sini tidak perlu jadi satu.               |
//+------------------------------------------------------------------+
int SDIndexOfTime(const datetime &time[],int n,datetime t)
  {
   int lo=0,hi=n-1;
   while(lo<=hi)
     {
      int mid=(lo+hi)/2;
      if(time[mid]==t)
         return mid;
      if(time[mid]<t)
         lo=mid+1;
      else
         hi=mid-1;
     }
   return -1;
  }

//+------------------------------------------------------------------+
//| Setiap box induk yang PECAH, dimasuki lagi dari sisi sebaliknya.  |
//|                                                                   |
//| `born` adalah bar tempat box jadi diketahui, jadi lifecycle-nya   |
//| mulai di `broke + 1`. Mulai di bar yang memecahkan berarti lilin  |
//| yang membunuh box lama dihitung sebagai test pertama box baru,    |
//| aturan dan alasan yang sama dengan bar ketiga detektor gap.       |
//|                                                                   |
//| TEPI KIRI adalah bar inversinya, BUKAN origin induk. Diukur       |
//| sebelum koreksi itu di Python: 9 dari 9 breaker pada satu deret   |
//| 500 bar dimulai sebelum mereka terbalik. Sebuah box tidak boleh   |
//| mengaku sudah ada sebelum peristiwa yang menciptakannya. `origin` |
//| tetap bar induk, jadi `base_from` dan id-nya masih menunjuk lilin |
//| asal rectangle-nya.                                               |
//+------------------------------------------------------------------+
int DetectInversion(string kind,const SDZone &parents[],int parent_count,
                    const double &high[],const double &low[],const double &close[],
                    const datetime &time[],int n,double mitigation_pct,
                    SDZone &zones[])
  {
   ArrayResize(zones,0);
   int count=0;
   for(int i=0;i<parent_count;i++)
     {
      if(parents[i].state!=SD_STATE_BROKEN)
         continue;

      int broke=SDIndexOfTime(time,n,parents[i].time_to);
      if(broke<0)
         continue;   // tidak mungkin untuk induk BROKEN, dijaga bukan diasumsikan

      double top=parents[i].top;
      double bottom=parents[i].bottom;
      if(top-bottom<=SD_EPS)
         continue;

      // Rectangle yang sama, dimasuki dari sisi lain. Aturan proximal dan
      // distal diturunkan dari SISI, jadi pembalikannya dinyatakan dengan
      // mengoper sisi yang lain, bukan dengan menghitung tepi di sini.
      ENUM_SD_SIDE side=(parents[i].side==SD_DEMAND)?SD_SUPPLY:SD_DEMAND;
      bool is_demand=(side==SD_DEMAND);
      double proximal=is_demand?top:bottom;
      double distal  =is_demand?bottom:top;

      int break_idx=-1;
      int state=SDLifecycle(high,low,close,n,top,bottom,distal,is_demand,
                            broke+1,mitigation_pct,break_idx);

      ArrayResize(zones,count+1);
      zones[count].kind=kind;
      zones[count].side=side;
      zones[count].top=top;
      zones[count].bottom=bottom;
      zones[count].proximal=proximal;
      zones[count].distal=distal;
      // Displacement INDUK, dibawa dan bukan dihitung ulang: ia menggambarkan
      // box, dan box-nya milik induk.
      zones[count].departure_atr=parents[i].departure_atr;
      zones[count].profit_margin=0.0;
      zones[count].profit_zone_rr=-1.0;
      zones[count].state=state;
      zones[count].time_from=time[broke];         // tepi kiri = inversinya
      zones[count].time_to=(break_idx!=-1)?time[break_idx]:time[n-1];
      zones[count].base_from=parents[i].base_from;  // origin induk, untuk id
      zones[count].base_to=parents[i].base_to;
      zones[count].leg_out_from=broke;
      zones[count].leg_out_to=broke;
      count++;
     }
   return count;
  }

//+------------------------------------------------------------------+
//| IFVG: fair value gap yang harganya sudah close menembusnya.       |
//+------------------------------------------------------------------+
int DetectIFVG(const double &open_[],const double &high[],const double &low[],
               const double &close[],const datetime &time[],const double &atr[],
               int n,const FVGParams &p,SDZone &zones[])
  {
   SDZone parents[];
   int parent_count=DetectFVG(open_,high,low,close,time,atr,n,p,parents);
   return DetectInversion("IFVG",parents,parent_count,high,low,close,time,n,
                          p.mitigation_pct,zones);
  }

//+------------------------------------------------------------------+
//| Breaker: order block yang harganya sudah close menembusnya.       |
//+------------------------------------------------------------------+
int DetectBreaker(const double &open_[],const double &high[],const double &low[],
                  const double &close[],const datetime &time[],const double &atr[],
                  int n,const OBParams &p,SDZone &zones[])
  {
   SDZone parents[];
   int parent_count=DetectOrderBlock(open_,high,low,close,time,atr,n,p,parents);
   return DetectInversion("BRK",parents,parent_count,high,low,close,time,n,
                          p.mitigation_pct,zones);
  }
//+------------------------------------------------------------------+
