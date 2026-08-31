//+------------------------------------------------------------------+
//|                                          SupplyDemandDetector.mqh|
//|  Port faithful dari backend/app/detect/supply_demand.py dan       |
//|  backend/app/indicators.py. Konvensi index SAMA dengan Python:    |
//|  index 0 = bar tertua, index n-1 = bar terbaru.                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#define SD_EPS 1e-12

// State lifecycle, cocok dengan ZoneState di Python.
#define SD_STATE_FRESH     0
#define SD_STATE_TESTED    1
#define SD_STATE_MITIGATED 2
#define SD_STATE_BROKEN    3

enum ENUM_SD_SIDE { SD_DEMAND = 0, SD_SUPPLY = 1 };

// Parameter detektor, default = nilai yang dikirim (shipped).
struct SDParams
  {
   int    atr_period;           // 14
   double impulse_body_ratio;   // 0.5
   double impulse_atr;          // 1.0
   int    base_max_bars;        // 6
   double base_max_atr;         // 2.5
   double departure_min_atr;    // 2.0
   int    departure_lookahead;  // 20
   int    proximal_basis;       // 0 = wick, 1 = body
   double min_profit_margin;    // 0.0 (off)
   double zone_min_atr;         // 0.05
   double max_base_drift;       // 0.6
   double mitigation_pct;       // 0.5
  };

struct SDZone
  {
   string       kind;          // "DBR" / "RBR" / "RBD" / "DBD"
   ENUM_SD_SIDE side;
   double       top, bottom, proximal, distal;
   double       departure_atr;
   double       profit_margin;
   int          state;
   datetime     time_from;     // epoch bar pertama base
   int          base_from, base_to, leg_out_from, leg_out_to;
  };

//--- true range -------------------------------------------------------------
double SDTrueRange(double h,double l,double pc)
  {
   return MathMax(h-l, MathMax(MathAbs(h-pc), MathAbs(l-pc)));
  }

//--- Wilder ATR (RMA true range). index 0 = tertua. -------------------------
void SDWilderAtr(double &atr[],const double &high[],const double &low[],
                 const double &close[],int n,int period)
  {
   ArrayResize(atr,n);
   if(n==0)
      return;

   double tr[];
   ArrayResize(tr,n);
   tr[0]=high[0]-low[0];
   for(int i=1;i<n;i++)
      tr[i]=SDTrueRange(high[i],low[i],close[i-1]);

   double mean=0.0;
   if(n<=period)
     {
      for(int i=0;i<n;i++) mean+=tr[i];
      mean/=(double)n;
      for(int i=0;i<n;i++) atr[i]=mean;
      return;
     }

   double seed=0.0;
   for(int i=0;i<period;i++) seed+=tr[i];
   seed/=(double)period;
   for(int i=0;i<period;i++) atr[i]=seed;

   double prev=seed;
   for(int i=period;i<n;i++)
     {
      prev=(prev*(period-1)+tr[i])/period;
      atr[i]=prev;
     }
  }

//--- flat ATR pada bar `at`. -1.0 = None (window tidak lengkap). ------------
double SDFlatAtr(const double &high[],const double &low[],const double &close[],
                 int n,int period,int at)
  {
   int lo=at-period+1;
   if(period<=0 || lo<1 || at>=n || at<0)
      return -1.0;
   double sum=0.0;
   for(int j=lo;j<=at;j++)
      sum+=SDTrueRange(high[j],low[j],close[j-1]);
   return sum/(double)period;
  }

//--- Label bar: +1 exciting up, -1 exciting down, 0 base. -------------------
void SDClassify(int &labels[],const double &open[],const double &high[],
                const double &low[],const double &close[],const double &atr[],
                int n,double body_ratio_min,double range_atr_min)
  {
   ArrayResize(labels,n);
   for(int i=0;i<n;i++)
     {
      double rng=MathMax(high[i]-low[i],SD_EPS);
      double body=close[i]-open[i];
      double body_ratio=MathAbs(body)/rng;
      double prior_atr=(i==0)?atr[0]:atr[i-1];
      bool exciting=(body_ratio>=body_ratio_min) && (rng>=range_atr_min*prior_atr);
      if(!exciting)
         labels[i]=0;
      else
         labels[i]=(body>0.0)?1:-1;
     }
  }

//--- Kompres label jadi run (label, start, end inklusif). Return jumlah run. -
int SDRuns(const int &labels[],int n,int &r_label[],int &r_start[],int &r_end[])
  {
   ArrayResize(r_label,0);
   ArrayResize(r_start,0);
   ArrayResize(r_end,0);
   if(n==0)
      return 0;

   int count=0;
   int start=0;
   for(int i=1;i<n;i++)
     {
      if(labels[i]!=labels[start])
        {
         ArrayResize(r_label,count+1);
         ArrayResize(r_start,count+1);
         ArrayResize(r_end,count+1);
         r_label[count]=labels[start];
         r_start[count]=start;
         r_end[count]=i-1;
         count++;
         start=i;
        }
     }
   ArrayResize(r_label,count+1);
   ArrayResize(r_start,count+1);
   ArrayResize(r_end,count+1);
   r_label[count]=labels[start];
   r_start[count]=start;
   r_end[count]=n-1;
   count++;
   return count;
  }

//--- Replay lifecycle dari bar `start`. Mengembalikan state. -----------------
int SDLifecycle(const double &high[],const double &low[],const double &close[],
                int n,double top,double bottom,double distal,bool is_demand,
                int start,double mitigation_pct)
  {
   double height=MathMax(top-bottom,SD_EPS);
   double penetration=0.0;
   int touches=0;
   int break_index=-1;
   bool was_inside=false;

   for(int i=start;i<n;i++)
     {
      if(is_demand ? (close[i]<distal) : (close[i]>distal))
        {
         break_index=i;
         break;
        }
      bool inside=(low[i]<=top) && (high[i]>=bottom);
      if(inside)
        {
         if(!was_inside)
            touches++;
         double depth=is_demand ? (top-low[i]) : (high[i]-bottom);
         penetration=MathMax(penetration,MathMin(1.0,depth/height));
        }
      was_inside=inside;
     }

   if(break_index!=-1)
      return SD_STATE_BROKEN;
   if(penetration>=mitigation_pct)
      return SD_STATE_MITIGATED;
   if(touches>0)
      return SD_STATE_TESTED;
   return SD_STATE_FRESH;
  }

//--- Deteksi zona supply/demand. Return jumlah zona yang lolos gate. ---------
int SDDetect(const double &open[],const double &high[],const double &low[],
             const double &close[],const datetime &time[],const double &atr[],
             int n,const SDParams &p,SDZone &zones[])
  {
   ArrayResize(zones,0);
   if(n<p.atr_period+3)
      return 0;

   int labels[];
   SDClassify(labels,open,high,low,close,atr,n,
              p.impulse_body_ratio,p.impulse_atr);

   int r_label[],r_start[],r_end[];
   int run_count=SDRuns(labels,n,r_label,r_start,r_end);

   int count=0;
   for(int k=0;k<run_count-2;k++)
     {
      int leg_in_lab =r_label[k];
      int base_lab   =r_label[k+1];
      int leg_out_lab=r_label[k+2];
      if(leg_in_lab==0 || base_lab!=0 || leg_out_lab==0)
         continue;

      // Formasi: leg_in dir, leg_out dir -> (kind, side).
      string kind;
      ENUM_SD_SIDE side;
      if(leg_in_lab==-1 && leg_out_lab==1)     { kind="DBR"; side=SD_DEMAND;  }
      else if(leg_in_lab==1 && leg_out_lab==1) { kind="RBR"; side=SD_DEMAND;  }
      else if(leg_in_lab==1 && leg_out_lab==-1){ kind="RBD"; side=SD_SUPPLY;  }
      else                                     { kind="DBD"; side=SD_SUPPLY;  }

      int base_to  =r_end[k+1];
      int base_from=MathMax(r_start[k+1], base_to-p.base_max_bars+1);

      double atr_base=atr[MathMax(0,base_from-1)];
      if(atr_base<=SD_EPS)
         continue;

      double wick_hi=high[base_from];
      double wick_lo=low[base_from];
      for(int i=base_from+1;i<=base_to;i++)
        {
         if(high[i]>wick_hi) wick_hi=high[i];
         if(low[i]<wick_lo)  wick_lo=low[i];
        }

      double body_hi,body_lo;
      if(p.proximal_basis==1)
        {
         body_hi=MathMax(open[base_from],close[base_from]);
         body_lo=MathMin(open[base_from],close[base_from]);
         for(int i=base_from+1;i<=base_to;i++)
           {
            double bh=MathMax(open[i],close[i]);
            double bl=MathMin(open[i],close[i]);
            if(bh>body_hi) body_hi=bh;
            if(bl<body_lo) body_lo=bl;
           }
        }
      else
        {
         body_hi=wick_hi;
         body_lo=wick_lo;
        }

      double top,bottom;
      if(side==SD_DEMAND) { top=body_hi; bottom=wick_lo; }
      else                { top=wick_hi; bottom=body_lo; }

      double floor_scale=SDFlatAtr(high,low,close,n,p.atr_period,base_from);
      double floor=(floor_scale>=0.0)?(p.zone_min_atr*floor_scale):0.0;
      double height=top-bottom;
      if(height<floor)
        {
         if(side==SD_DEMAND) top=bottom+floor;
         else                bottom=top-floor;
         height=top-bottom;
        }
      if(height<=SD_EPS)
         continue;

      if(height>p.base_max_atr*atr_base)
         continue;

      bool is_demand=(side==SD_DEMAND);
      double proximal=is_demand?top:bottom;
      double distal  =is_demand?bottom:top;

      double drift=MathAbs(close[base_to]-open[base_from])/height;
      if(drift>p.max_base_drift)
         continue;

      int leg_out_from=r_start[k+2];
      int leg_out_to  =r_end[k+2];

      int first_touch=-1;
      for(int j=leg_out_to+1;j<n;j++)
        {
         if(low[j]<=top && high[j]>=bottom) { first_touch=j; break; }
        }
      int look_to=MathMin(n, leg_out_from+p.departure_lookahead);
      if(first_touch!=-1)
         look_to=MathMax(leg_out_from+1, MathMin(look_to,first_touch));

      double excursion=0.0;
      if(is_demand)
        {
         double m=high[leg_out_from];
         for(int j=leg_out_from;j<look_to;j++)
            if(high[j]>m) m=high[j];
         excursion=m-proximal;
        }
      else
        {
         double m=low[leg_out_from];
         for(int j=leg_out_from;j<look_to;j++)
            if(low[j]<m) m=low[j];
         excursion=proximal-m;
        }
      double departure_atr=MathMax(0.0,excursion)/atr_base;
      double profit_margin=MathMax(0.0,excursion)/height;

      if(departure_atr<p.departure_min_atr)
         continue;
      if(profit_margin<p.min_profit_margin)
         continue;

      int state=SDLifecycle(high,low,close,n,top,bottom,distal,is_demand,
                            leg_out_to+1,p.mitigation_pct);

      ArrayResize(zones,count+1);
      zones[count].kind=kind;
      zones[count].side=side;
      zones[count].top=top;
      zones[count].bottom=bottom;
      zones[count].proximal=proximal;
      zones[count].distal=distal;
      zones[count].departure_atr=departure_atr;
      zones[count].profit_margin=profit_margin;
      zones[count].state=state;
      zones[count].time_from=time[base_from];
      zones[count].base_from=base_from;
      zones[count].base_to=base_to;
      zones[count].leg_out_from=leg_out_from;
      zones[count].leg_out_to=leg_out_to;
      count++;
     }
   return count;
  }
//+------------------------------------------------------------------+
