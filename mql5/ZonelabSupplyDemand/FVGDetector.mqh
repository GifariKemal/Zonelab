//+------------------------------------------------------------------+
//|                                               FVGDetector.mqh    |
//|  Port faithful dari app/detect/imbalance.py::detect_fvg.          |
//|  Fair value gap = 3 bar berurutan yang wick luarnya tak bertemu.  |
//|  Memakai primitif dari SupplyDemandDetector.mqh (ATR, lifecycle).  |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "SupplyDemandDetector.mqh"

// Parameter FVG (ImbalanceParams), default shipped.
// filter_mother dan min_body_ratio DITAMBAHKAN 6 September 2026. Keduanya
// sudah ada di `detect_fvg` sejak lama tapi tidak pernah diport, dan port ini
// cocok hanya karena keduanya mati secara default. Begitu default menyala,
// EA akan menggambar lebih banyak zona daripada engine tanpa satu pun pesan.
struct FVGParams
  {
   int    atr_period;      // 14
   double min_gap_atr;     // 0.0
   double mitigation_pct;  // 0.5
   bool   filter_mother;   // true
   double min_body_ratio;  // 0.3
  };

//+------------------------------------------------------------------+
//| Deteksi FVG. Return jumlah zona yang lolos gate.                  |
//| up gap   : high[first] < low[third] -> DEMAND, box [high[first],  |
//|            low[third]].                                           |
//| down gap : low[first] > high[third] -> SUPPLY, box [high[third],  |
//|            low[first]].                                           |
//+------------------------------------------------------------------+
int DetectFVG(const double &open_[],const double &high[],const double &low[],
              const double &close[],const datetime &time[],const double &atr[],
              int n,const FVGParams &p,SDZone &zones[])
  {
   ArrayResize(zones,0);
   if(n<p.atr_period+3)
      return 0;

   int count=0;
   for(int i=1;i<n-1;i++)
     {
      int first=i-1;
      int third=i+1;

      int direction=0;
      if(high[first]<low[third])
         direction=1;        // up gap (bullish)
      else if(low[first]>high[third])
         direction=-1;       // down gap (bearish)
      if(direction==0)
         continue;

      bool up=(direction==1);

      // Bar tengah yang menelan kedua tetangganya bukan displacement, ia
      // inside bar. Urutan filternya sama dengan Python: mother dulu, lalu
      // body ratio, lalu lantai ukuran.
      if(p.filter_mother
         && high[i]>=high[first] && high[i]>=high[third]
         && low[i]<=low[first]   && low[i]<=low[third])
         continue;

      if(p.min_body_ratio>0.0)
        {
         double rng=high[i]-low[i];
         double body=MathAbs(close[i]-open_[i]);
         if(rng>SD_EPS && body/rng<p.min_body_ratio)
            continue;
        }

      double top,bottom;
      if(up)
        {
         top=low[third];
         bottom=high[first];
        }
      else
        {
         top=low[first];
         bottom=high[third];
        }

      double scale=atr[MathMax(0,first-1)];
      if(scale<=SD_EPS || (top-bottom)<p.min_gap_atr*scale)
         continue;   // terlalu kecil

      double size=(top-bottom)/scale;

      ENUM_SD_SIDE side=up?SD_DEMAND:SD_SUPPLY;
      bool is_demand=(side==SD_DEMAND);
      double proximal=is_demand?top:bottom;
      double distal  =is_demand?bottom:top;

      int born=third;
      int break_idx=-1;
      int state=SDLifecycle(high,low,close,n,top,bottom,distal,is_demand,
                            born+1,p.mitigation_pct,break_idx);

      ArrayResize(zones,count+1);
      zones[count].kind="FVG";
      zones[count].side=side;
      zones[count].top=top;
      zones[count].bottom=bottom;
      zones[count].proximal=proximal;
      zones[count].distal=distal;
      zones[count].departure_atr=size;   // gap size in ATR = gate
      zones[count].profit_margin=0.0;
      zones[count].profit_zone_rr=-1.0;
      zones[count].state=state;
      zones[count].time_from=time[first];
      zones[count].time_to=(break_idx!=-1)?time[break_idx]:time[n-1];
      zones[count].base_from=first;
      zones[count].base_to=first;
      zones[count].leg_out_from=born;
      zones[count].leg_out_to=born;
      count++;
     }
   return count;
  }
//+------------------------------------------------------------------+
