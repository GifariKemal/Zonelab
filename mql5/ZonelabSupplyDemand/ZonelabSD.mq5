//+------------------------------------------------------------------+
//|                                                       ZonelabSD.mq5|
//|  EA backtest drawing supply/demand di MT5 Strategy Tester.        |
//|  Entry: limit di proximal (demand long, supply short), stop di     |
//|  distal - buffer, target 2R. Satu order per zona (idempoten).     |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"
#property strict

#include "SupplyDemandDetector.mqh"
#include <Trade/Trade.mqh>

//--- parameter detektor (default = shipped) ---
input int    InpAtrPeriod        = 14;
input double InpImpulseBodyRatio = 0.5;
input double InpImpulseAtr       = 1.0;
input int    InpBaseMaxBars      = 6;
input double InpBaseMaxAtr       = 2.5;
input double InpDepartureMinAtr  = 2.0;
input int    InpDepartureLook    = 20;
input int    InpProximalBasis    = 0;     // 0 = wick, 1 = body
input double InpMinProfitMargin  = 0.0;
input double InpZoneMinAtr       = 0.05;
input double InpMaxBaseDrift     = 0.6;
input double InpMitigationPct    = 0.5;
//--- parameter trade ---
input double InpStopBufferAtr    = 0.25;
input double InpRewardR          = 2.0;
input double InpRiskPercent      = 1.0;
input int    InpBars             = 3000;
input int    InpMagic            = 20260831;

CTrade trade;

// Zone yang sudah di-order, supaya idempoten (satu order per zona).
string g_ordered[];
int    g_ordered_count = 0;

bool AlreadyOrdered(string id)
  {
   for(int i = 0; i < g_ordered_count; i++)
      if(g_ordered[i] == id)
         return true;
   return false;
  }

void MarkOrdered(string id)
  {
   ArrayResize(g_ordered, g_ordered_count + 1);
   g_ordered[g_ordered_count] = id;
   g_ordered_count++;
  }

int OnInit()
  {
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(10);
   trade.SetAsyncMode(false);
   // Pilih filling mode yang didukung simbol (Exness XAUUSD = FOK/IOC).
   long fm = SymbolInfoInteger(_Symbol, SYMBOL_FILLING_MODE);
   if((fm & SYMBOL_FILLING_FOK) != 0)
      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fm & SYMBOL_FILLING_IOC) != 0)
      trade.SetTypeFilling(ORDER_FILLING_IOC);
   else
      trade.SetTypeFilling(ORDER_FILLING_RETURN);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) {}

void OnTick()
  {
   static datetime lastBar = 0;
   datetime cur = iTime(_Symbol, _Period, 0);
   if(cur == lastBar)
      return;
   lastBar = cur;
   DetectAndTrade();
  }

void DetectAndTrade()
  {
   int total = Bars(_Symbol, _Period);
   int n = MathMin(InpBars, total - 1);   // bar tertutup saja (skip forming shift 0)
   if(n < InpAtrPeriod + 3)
      return;

   // as_series true => index 0 = bar tertua (konvensi Python). start_pos=1
   // skip bar forming shift 0, jadi window = shift 1..n (n bar tertutup).
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, _Period, 1, n, rates);
   if(copied < n)
      return;

   double open_[], high_[], low_[], close_[];
   datetime time_[];
   ArrayResize(open_, n);
   ArrayResize(high_, n);
   ArrayResize(low_, n);
   ArrayResize(close_, n);
   ArrayResize(time_, n);
   for(int i = 0; i < n; i++)
     {
      open_[i]  = rates[i].open;
      high_[i]  = rates[i].high;
      low_[i]   = rates[i].low;
      close_[i] = rates[i].close;
      time_[i]  = rates[i].time;
     }

   double atr[];
   SDWilderAtr(atr, high_, low_, close_, n, InpAtrPeriod);

   SDParams p;
   p.atr_period          = InpAtrPeriod;
   p.impulse_body_ratio  = InpImpulseBodyRatio;
   p.impulse_atr         = InpImpulseAtr;
   p.base_max_bars       = InpBaseMaxBars;
   p.base_max_atr        = InpBaseMaxAtr;
   p.departure_min_atr   = InpDepartureMinAtr;
   p.departure_lookahead = InpDepartureLook;
   p.proximal_basis      = InpProximalBasis;
   p.min_profit_margin   = InpMinProfitMargin;
   p.zone_min_atr        = InpZoneMinAtr;
   p.max_base_drift      = InpMaxBaseDrift;
   p.mitigation_pct      = InpMitigationPct;

   SDZone zones[];
   int zcount = SDDetect(open_, high_, low_, close_, time_, atr, n, p, zones);

   for(int i = 0; i < zcount; i++)
     {
      if(zones[i].state != SD_STATE_FRESH)
         continue;
      // Hanya zona yang leg-out-nya sudah selesai (confirmed).
      if(zones[i].leg_out_to >= n - 1)
         continue;

      string id = zones[i].kind + "-" + IntegerToString((long)zones[i].time_from);
      if(AlreadyOrdered(id))
         continue;

      bool is_demand = (zones[i].side == SD_DEMAND);
      double way    = is_demand ? 1.0 : -1.0;
      double entry  = zones[i].proximal;
      double atr_base = atr[MathMax(0, zones[i].base_from - 1)];
      double buffer = InpStopBufferAtr * atr_base;
      double stop   = zones[i].distal - way * buffer;
      double risk   = MathAbs(entry - stop);
      if(risk <= SD_EPS)
         continue;
      double target = entry + way * InpRewardR * risk;

      double lots = RiskLots(risk);

      bool ok;
      if(is_demand)
         ok = trade.BuyLimit(lots, entry, _Symbol, stop, target,
                             ORDER_TIME_GTC, 0, id);
      else
         ok = trade.SellLimit(lots, entry, _Symbol, stop, target,
                              ORDER_TIME_GTC, 0, id);

      if(!ok)
         Print("order gagal zona ", id, ": ", trade.ResultRetcode());
      MarkOrdered(id);
     }
  }

double RiskLots(double riskDistance)
  {
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0)
      return 0.01;

   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney = equity * InpRiskPercent / 100.0;
   double lossPerLot = riskDistance / tickSize * tickValue;
   if(lossPerLot <= 0)
      return 0.01;

   double lots = riskMoney / lossPerLot;
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxv = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(step > 0)
      lots = MathFloor(lots / step) * step;
   lots = MathMax(minv, MathMin(maxv, lots));
   return NormalizeDouble(lots, 2);
  }
//+------------------------------------------------------------------+
