//+------------------------------------------------------------------+
//|                                                        ZonelabOB.mq5 |
//|  EA backtest order block di MT5 Strategy Tester.                  |
//|  Entry: limit di proximal (demand long, supply short), stop di     |
//|  distal - buffer, target zona lawan terdekat (profit_zone).       |
//|  Satu order per block (idempoten). Tanpa dedupe (OB tidak dedupe). |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"
#property strict

#include "OrderBlockDetector.mqh"
#include <Trade/Trade.mqh>

//--- parameter detektor (default = shipped) ---
input int    InpAtrPeriod        = 14;
input double InpDisplacementAtr  = 1.5;
input int    InpDisplacementBars = 5;
input double InpMitigationPct    = 0.5;
//--- parameter trade ---
input double InpStopBufferAtr    = 0.25;
input int    InpStopAtrMode      = 0;    // 0 = ATR bar sebelum base zona, 1 = ATR bar terakhir
input int    InpTargetMode       = 0;    // 0 = profit_zone, 1 = fixed R
input double InpRewardR          = 2.0;
input double InpRiskPercent      = 1.0;
input int    InpBars             = 3000;   // fixed window: OB terlalu padat untuk window tumbuh
input int    InpMagic            = 20260901;

CTrade trade;

string g_ordered[];
int    g_ordered_count = 0;

int g_detect_calls = 0;
int g_zones_total = 0;
int g_zones_fresh = 0;
int g_orders_placed = 0;
int g_orders_failed = 0;
int g_orders_skipped_price = 0;
int g_orders_skipped_notarget = 0;

bool AlreadyOrdered(string id)
  {
   for(int i=0;i<g_ordered_count;i++)
      if(g_ordered[i]==id)
         return true;
   return false;
  }

void MarkOrdered(string id)
  {
   ArrayResize(g_ordered,g_ordered_count+1);
   g_ordered[g_ordered_count]=id;
   g_ordered_count++;
  }

int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(10);
   trade.SetAsyncMode(false);
   long fm=SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK)!=0)
      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fm & SYMBOL_FILLING_IOC)!=0)
      trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      trade.SetTypeFilling(ORDER_FILLING_RETURN);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Print("=== ZONELABOB SUMMARY ===");
   Print("detect calls: ",g_detect_calls);
   Print("zones total: ",g_zones_total);
   Print("zones fresh: ",g_zones_fresh);
   Print("orders placed: ",g_orders_placed);
   Print("orders failed: ",g_orders_failed);
   Print("skipped price: ",g_orders_skipped_price);
   Print("skipped no-target: ",g_orders_skipped_notarget);
  }

void OnTick()
  {
   static datetime lastBar=0;
   datetime cur=iTime(_Symbol,_Period,0);
   if(cur==lastBar)
      return;
   lastBar=cur;
   DetectAndTrade();
  }

void DetectAndTrade()
  {
   g_detect_calls++;

   int total=Bars(_Symbol,_Period);
   int n=MathMin(InpBars,total-1);
   if(n<InpAtrPeriod+InpDisplacementBars+2)
      return;

   double open_[],high_[],low_[],close_[];
   datetime time_[];
   ArrayResize(open_,n);
   ArrayResize(high_,n);
   ArrayResize(low_,n);
   ArrayResize(close_,n);
   ArrayResize(time_,n);
   for(int i=0;i<n;i++)
     {
      int shift=n-i;
      open_[i]  =iOpen(_Symbol,_Period,shift);
      high_[i]  =iHigh(_Symbol,_Period,shift);
      low_[i]   =iLow(_Symbol,_Period,shift);
      close_[i] =iClose(_Symbol,_Period,shift);
      time_[i]  =iTime(_Symbol,_Period,shift);
     }

   double atr[];
   SDWilderAtr(atr,high_,low_,close_,n,InpAtrPeriod);

   OBParams p;
   p.atr_period        =InpAtrPeriod;
   p.displacement_atr  =InpDisplacementAtr;
   p.displacement_bars =InpDisplacementBars;
   p.mitigation_pct    =InpMitigationPct;

   SDZone zones[];
   int zcount=DetectOrderBlock(open_,high_,low_,close_,time_,atr,n,p,zones);
   SDMarkProfitZones(zones,zcount,time_[n-1]);
   g_zones_total+=zcount;

   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   for(int i=0;i<zcount;i++)
     {
      if(zones[i].state!=SD_STATE_FRESH)
         continue;
      if(zones[i].leg_out_to>=n-1)
         continue;

      g_zones_fresh++;

      string id=zones[i].kind+"-"+IntegerToString((long)zones[i].time_from);
      if(AlreadyOrdered(id))
         continue;

      bool is_demand=(zones[i].side==SD_DEMAND);
      double way=is_demand?1.0:-1.0;
      double entry=zones[i].proximal;
      // DUA BACAAN ATR YANG BERBEDA, dan sampai 1 September 2026 kedua sisi
      // memakai yang berbeda tanpa ada yang memutuskan mana yang benar:
      // Zonelab memakai `atr[-1]` untuk SETIAP zona (`app/main.py:991`), EA ini
      // memakai ATR bar sebelum base zona. Rumus stop-nya identik, inputnya
      // tidak, jadi harga stop, risk, dan lot berbeda hampir di tiap zona.
      // Saklarnya ada supaya pertanyaannya bisa diukur, bukan diperdebatkan.
      double atr_base=atr[MathMax(0,zones[i].base_from-1)];
      double atr_stop=(InpStopAtrMode==1)?atr[n-1]:atr_base;
      double buffer=InpStopBufferAtr*atr_stop;
      double stop=zones[i].distal-way*buffer;
      double risk=MathAbs(entry-stop);
      if(risk<=SD_EPS)
         continue;

      // Target: profit_zone (zona lawan terdekat) atau fixed R.
      double target;
      if(InpTargetMode==1)
        {
         target=entry+way*InpRewardR*risk;
        }
      else
        {
         if(zones[i].profit_zone_rr<=0.0)
           {
            g_orders_skipped_notarget++;
            MarkOrdered(id);
            continue;
           }
         target=entry+way*zones[i].profit_zone_rr*(zones[i].top-zones[i].bottom);
        }

      // Guard: buy limit di bawah ask, sell limit di atas bid.
      if(is_demand && entry>=ask)
        {
         g_orders_skipped_price++;
         MarkOrdered(id);
         continue;
        }
      if(!is_demand && entry<=bid)
        {
         g_orders_skipped_price++;
         MarkOrdered(id);
         continue;
        }

      double lots=RiskLots(risk);

      bool ok;
      if(is_demand)
         ok=trade.BuyLimit(lots,entry,_Symbol,stop,target,ORDER_TIME_GTC,0,id);
      else
         ok=trade.SellLimit(lots,entry,_Symbol,stop,target,ORDER_TIME_GTC,0,id);

      if(ok)
         g_orders_placed++;
      else
        {
         g_orders_failed++;
         Print("order gagal block ",id,": ",trade.ResultRetcode());
        }
      MarkOrdered(id);
     }
  }

double RiskLots(double riskDistance)
  {
   double tickValue=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double tickSize =SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(tickSize<=0 || tickValue<=0)
      return 0.01;

   double equity=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=equity*InpRiskPercent/100.0;
   double lossPerLot=riskDistance/tickSize*tickValue;
   if(lossPerLot<=0)
      return 0.01;

   double lots=riskMoney/lossPerLot;
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double minv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double maxv=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0)
      lots=MathFloor(lots/step)*step;
   lots=MathMax(minv,MathMin(maxv,lots));
   return NormalizeDouble(lots,2);
  }
//+------------------------------------------------------------------+
