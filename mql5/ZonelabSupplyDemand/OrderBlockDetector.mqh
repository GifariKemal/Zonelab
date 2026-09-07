//+------------------------------------------------------------------+
//|                                          OrderBlockDetector.mqh  |
//|  Port faithful dari app/detect/imbalance.py::detect_order_block.  |
//|  Order block = lilin berlawanan TERAKHIR sebelum gerakan impulsif. |
//|  Memakai primitif dari SupplyDemandDetector.mqh (ATR, lifecycle).  |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "SupplyDemandDetector.mqh"

// Cermin `imbalance.MIN_OB_BOX_RANGE`. Acuannya rentang lilin dan BUKAN ATR:
// ATR adalah rata rata berjalan yang disemai dari bar pertama, jadi ia berbeda
// antar jendela dan membuat geometri kotak bergantung berapa bar yang dimuat.
#define SD_MIN_OB_BOX_RANGE 0.15

// Parameter order block (ImbalanceParams), default shipped.
struct OBParams
  {
   int    atr_period;        // 14
   double displacement_atr;  // 1.5
   int    displacement_bars; // 5
   double mitigation_pct;    // 0.5
  };

//+------------------------------------------------------------------+
//| Deteksi order block. Return jumlah zona yang lolos gate.          |
//| Box = whole range lilin block (top=high[i], bottom=low[i]).       |
//| side: lilin bearish sebelum gerakan naik = DEMAND (bullish block);|
//|       lilin bullish sebelum gerakan turun = SUPPLY.               |
//+------------------------------------------------------------------+
int DetectOrderBlock(const double &open_[],const double &high[],const double &low[],
                     const double &close[],const datetime &time[],const double &atr[],
                     int n,const OBParams &p,SDZone &zones[])
  {
   ArrayResize(zones,0);
   if(n<p.atr_period+p.displacement_bars+2)
      return 0;

   int count=0;
   for(int i=1;i<n-p.displacement_bars-1;i++)
     {
      double scale=atr[MathMax(0,i-1)];
      if(scale<=SD_EPS)
         continue;

      // IMPULS DIUKUR KE CLOSE EKSTREM, BUKAN KE WICK EKSTREM. Port ini
      // memakai high/low sampai 6 September 2026, empat hari setelah
      // `detect_order_block` pindah ke close - 30,6 persen block lolos di sini
      // lewat sumbu yang tidak pernah ada close-nya. `ea_parity_ob` melaporkan
      // 1.504 dari 1.504 mismatch dan tidak ada yang membacanya.
      bool bearish=(close[i]<open_[i]);
      double move;
      ENUM_SD_SIDE side;
      if(bearish)
        {
         double m=close[i+1];
         for(int j=i+2;j<=i+p.displacement_bars;j++)
            if(close[j]>m) m=close[j];
         move=(m-close[i])/scale;
         side=SD_DEMAND;
        }
      else if(close[i]>open_[i])
        {
         double m=close[i+1];
         for(int j=i+2;j<=i+p.displacement_bars;j++)
            if(close[j]<m) m=close[j];
         move=(close[i]-m)/scale;
         side=SD_SUPPLY;
        }
      else
        {
         continue;   // doji, bukan block
        }

      if(move<p.displacement_atr)
         continue;   // gerakan lemah

      // "Terakhir": lilin berikutnya wajib close berlawanan arah.
      int nxt=i+1;
      bool turned=bearish ? (close[nxt]>open_[nxt]) : (close[nxt]<open_[nxt]);
      if(!turned)
         continue;   // bukan yang terakhir

      int born=i+p.displacement_bars;
      // KOTAKNYA BADAN LILIN, DIMEKARKAN KE LANTAI 0,15 RENTANG, LALU DIGESER
      // KEMBALI KE DALAM LILINNYA. Sama dengan `imbalance.py`; port ini memakai
      // rentang penuh sampai 6 September 2026. Stop duduk di luar distal, jadi
      // rentang penuh menyerahkan risk per unit ke panjang sumbu - besaran yang
      // tak berhubungan dengan sinyalnya. Diukur di docs/QA-OB-GATE.md: PF
      // 0,984 ke 1,320 bersama impuls-dari-close di atas.
      double top=MathMax(open_[i],close[i]);
      double bottom=MathMin(open_[i],close[i]);
      double floor_h=(high[i]-low[i])*SD_MIN_OB_BOX_RANGE;
      double short_h=floor_h-(top-bottom);
      if(short_h>0.0)
        {
         top+=short_h/2.0;
         bottom-=short_h/2.0;
         if(top>high[i])
           {
            bottom-=top-high[i];
            top=high[i];
           }
         else if(bottom<low[i])
           {
            top+=low[i]-bottom;
            bottom=low[i];
           }
        }
      if(top-bottom<=SD_EPS)
         continue;
      bool is_demand=(side==SD_DEMAND);
      double proximal=is_demand?top:bottom;
      double distal  =is_demand?bottom:top;

      int break_idx=-1;
      int state=SDLifecycle(high,low,close,n,top,bottom,distal,is_demand,
                            born+1,p.mitigation_pct,break_idx);

      ArrayResize(zones,count+1);
      zones[count].kind="OB";
      zones[count].side=side;
      zones[count].top=top;
      zones[count].bottom=bottom;
      zones[count].proximal=proximal;
      zones[count].distal=distal;
      zones[count].departure_atr=move;      // displacement = gate
      zones[count].profit_margin=0.0;
      zones[count].profit_zone_rr=-1.0;     // diisi SDMarkProfitZones
      zones[count].state=state;
      zones[count].time_from=time[i];
      zones[count].time_to=(break_idx!=-1)?time[break_idx]:time[n-1];
      zones[count].base_from=i;
      zones[count].base_to=i;
      zones[count].leg_out_from=born;
      zones[count].leg_out_to=born;
      count++;
     }
   return count;
  }
//+------------------------------------------------------------------+
