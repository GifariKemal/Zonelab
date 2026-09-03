//+------------------------------------------------------------------+
//|                                                   ZonelabWYK.mq5 |
//|  EA backtest BREAKOUT di MT5 Strategy Tester, lewat fase Wyckoff. |
//|                                                                   |
//|  KENAPA EA INI ADA MESKIPUN RIG PYTHON SUDAH BILANG NULL.         |
//|  docs/wyckoff_outcomes.json mengukur keempat fase lawan drift     |
//|  instrumennya sendiri di sembilan instrumen: `sos` n=19.667        |
//|  t=-0,95 dengan 13 dari 36 fold positif, di bawah kebetulan.      |
//|  Itu menjawab "apakah fase mendahului move arah di atas drift".   |
//|                                                                   |
//|  Yang EA ini jawab pertanyaan LAIN: apakah Strategy Tester dengan |
//|  real tick, spread terminal dan komisi sungguhan setuju. Kedua    |
//|  rig itu pernah TIDAK sepakat di 6 dari 8 sel                     |
//|  (docs/mt5_python_parity.json), jadi null di Python pada resolusi  |
//|  bar tidak menyelesaikan apa yang MT5 katakan. Dan rig Python     |
//|  tidak menguji EKSEKUSI sama sekali: ia mengukur move ke depan,   |
//|  bukan entry-stop-target dengan biaya.                            |
//|                                                                   |
//|  EMPAT ARM, dan keempatnya diminta eksplisit. Dua varian eksekusi  |
//|  yang metode breakout kenal, satu filter yang kedua deskripsinya   |
//|  tuntut, dan satu arm untuk mekanisme institusional yang           |
//|  framing ICT klaim:                                               |
//|                                                                   |
//|    0 AGRESIF   masuk market di bar sesudah close menembus tepi.    |
//|                "Memasuki pasar detik itu juga saat harga melewati |
//|                level penentu."                                    |
//|    1 RETEST    limit di level yang ditembus, kedaluwarsa N bar.    |
//|                "Menunggu harga berbalik menguji kembali level."    |
//|    2 TICK      arm 0 plus syarat hitungan tick bar break di atas   |
//|                kelipatan median window-nya.                        |
//|    3 FADE      spring dibeli, upthrust dijual: melawan false       |
//|                breakout-nya, bukan mengikuti break-nya.            |
//|                                                                   |
//|  ARM 2 TIDAK MENGUKUR VOLUME, dan namanya sengaja tidak bilang     |
//|  volume. `real_volume` terukur NOL di kedelapan instrumen yang     |
//|  broker ini layani, jadi volume transaksi tidak ada di sumber ini. |
//|  Yang tersisa hitungan tick: seberapa sering feed broker           |
//|  memperbarui. Ia besaran berbeda dan berbeda antar broker.         |
//|                                                                   |
//|  Dan satu angka yang harus dibaca sebelum arm 1 dan 2 diharapkan   |
//|  menolong: keduanya sudah diukur di literatur dan keduanya         |
//|  MEMPERBURUK. Bulkowski, 8.765 pattern: 97 persen tipe pattern     |
//|  breakout naik perform LEBIH BAIK TANPA retest, dan volume tinggi  |
//|  di bar break membuat failure TRIPLE.                              |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"
#property strict

#include "WyckoffDetector.mqh"
#include <Trade/Trade.mqh>

//--- parameter detektor (default = shipped WyckoffParams) ---
input int    InpLookback     = 20;
//--- arm ---
input int    InpArm          = 0;     // 0 agresif, 1 retest, 2 tick, 3 fade
input double InpTickMult     = 1.5;   // arm 2: ticks >= mult * median window
input int    InpRetestBars   = 10;    // arm 1: umur limit, dalam bar
//--- parameter trade ---
input int    InpAtrPeriod    = 14;
input double InpStopBufferAtr = 0.25;
input double InpRewardR      = 2.0;
input double InpRiskPercent  = 1.0;
input int    InpBars         = 3000;  // fixed window, sama dengan EA lain
input int    InpMagic        = 20260903;

CTrade trade;

string g_ordered[];
int    g_ordered_count = 0;

int g_detect_calls = 0;
int g_phases_total = 0;
int g_phases_armed = 0;
int g_orders_placed = 0;
int g_orders_failed = 0;
int g_skipped_tick = 0;
int g_skipped_price = 0;
int g_skipped_risk = 0;
int g_kind_count[4];

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
   if(InpArm<0 || InpArm>3)
     {
      Print("InpArm harus 0..3, dapat ",InpArm);
      return INIT_PARAMETERS_INCORRECT;
     }
   ArrayInitialize(g_kind_count,0);
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
   // COUNTER DICETAK, dan `tools/mt5_backtest.py` membaca DELTA agent log-nya.
   // Sebuah run yang menempatkan nol order dan sebuah run yang detektornya
   // mati terlihat sama di report Strategy Tester; hanya baris ini yang
   // membedakan keduanya.
   Print("=== ZONELABWYK SUMMARY ===");
   Print("arm: ",InpArm);
   Print("detect calls: ",g_detect_calls);
   Print("phases total: ",g_phases_total);
   Print("phases spring: ",g_kind_count[WYK_SPRING]);
   Print("phases upthrust: ",g_kind_count[WYK_UPTHRUST]);
   Print("phases sos: ",g_kind_count[WYK_SOS]);
   Print("phases sow: ",g_kind_count[WYK_SOW]);
   Print("phases armed: ",g_phases_armed);
   Print("orders placed: ",g_orders_placed);
   Print("orders failed: ",g_orders_failed);
   Print("skipped tick: ",g_skipped_tick);
   Print("skipped price: ",g_skipped_price);
   Print("skipped risk: ",g_skipped_risk);
  }

void OnTick()
  {
   // NEW-BAR GUARD. Tanpa ini deteksinya berjalan tiap tick dan biayanya
   // O(tick x InpBars x lookback), yang pada real tick XAUUSD adalah puluhan
   // juta iterasi per hari perdagangan.
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
   if(n<=InpLookback+InpAtrPeriod+2)
      return;

   double open_[],high_[],low_[],close_[];
   datetime time_[];
   long vol_[];
   ArrayResize(open_,n);
   ArrayResize(high_,n);
   ArrayResize(low_,n);
   ArrayResize(close_,n);
   ArrayResize(time_,n);
   ArrayResize(vol_,n);
   for(int i=0;i<n;i++)
     {
      int shift=n-i;
      open_[i] =iOpen(_Symbol,_Period,shift);
      high_[i] =iHigh(_Symbol,_Period,shift);
      low_[i]  =iLow(_Symbol,_Period,shift);
      close_[i]=iClose(_Symbol,_Period,shift);
      time_[i] =iTime(_Symbol,_Period,shift);
      vol_[i]  =iVolume(_Symbol,_Period,shift);
     }

   double atr[];
   SDWilderAtr(atr,high_,low_,close_,n,InpAtrPeriod);

   WykParams p;
   p.lookback=InpLookback;

   WykPhase ph[];
   int pcount=DetectWyckoff(open_,high_,low_,close_,time_,vol_,n,p,ph);
   g_phases_total+=pcount;

   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   for(int i=0;i<pcount;i++)
     {
      g_kind_count[ph[i].kind]++;

      // HANYA FASE DI BAR TERAKHIR YANG SELESAI. Fase lama sudah lewat, dan
      // memasang order untuknya sekarang akan memakai harga hari ini pada
      // keputusan minggu lalu - bentuk lookahead yang paling mudah masuk.
      if(ph[i].at!=n-1)
         continue;

      bool is_break=(ph[i].kind==WYK_SOS || ph[i].kind==WYK_SOW);
      bool is_fade =(ph[i].kind==WYK_SPRING || ph[i].kind==WYK_UPTHRUST);
      if(InpArm==3)
        {
         if(!is_fade)
            continue;
        }
      else
        {
         if(!is_break)
            continue;
        }

      // Arah. Untuk arm break: sos beli, sow jual. Untuk arm fade: spring
      // dibeli (sweep di bawah yang ditolak), upthrust dijual.
      bool go_long = (InpArm==3)
                     ? (ph[i].kind==WYK_SPRING)
                     : (ph[i].kind==WYK_SOS);
      double way=go_long?1.0:-1.0;

      string id="WYK"+IntegerToString(InpArm)+"-"
                +IntegerToString((int)ph[i].kind)+"-"
                +IntegerToString((long)ph[i].time_at);
      if(AlreadyOrdered(id))
         continue;

      // Arm 2: syarat hitungan tick. Median window-nya nol berarti feed tidak
      // melaporkan tick di sana, dan sebuah syarat atas nol akan lolos selalu -
      // jadi barnya dilewati, bukan diloloskan.
      if(InpArm==2)
        {
         if(ph[i].ticks_median<=0.0
            || (double)ph[i].ticks < InpTickMult*ph[i].ticks_median)
           {
            g_skipped_tick++;
            MarkOrdered(id);
            continue;
           }
        }

      g_phases_armed++;

      double atr_stop=atr[n-1];
      double buffer=InpStopBufferAtr*atr_stop;

      double entry,stop;
      if(InpArm==1)
        {
         // RETEST: limit tepat di level yang ditembus. Stop di sisi jauhnya,
         // karena kalau level itu tidak menahan maka premis retest-nya salah.
         entry=ph[i].level;
         stop=ph[i].level-way*buffer;
        }
      else if(InpArm==3)
        {
         // FADE: masuk market, stop di luar ekstrem sweep-nya. Ekstremnya
         // adalah low bar untuk spring dan high bar untuk upthrust, yaitu
         // titik terjauh yang sudah dicapai penyapuan itu.
         entry=go_long?ask:bid;
         double swept=go_long?low_[ph[i].at]:high_[ph[i].at];
         stop=swept-way*buffer;
        }
      else
        {
         // AGRESIF dan TICK: masuk market di bar sesudah break-nya.
         entry=go_long?ask:bid;
         stop=ph[i].level-way*buffer;
        }

      double risk=MathAbs(entry-stop);
      if(risk<=SD_EPS)
        {
         g_skipped_risk++;
         MarkOrdered(id);
         continue;
        }
      double target=entry+way*InpRewardR*risk;
      double lots=RiskLots(risk);

      bool ok;
      if(InpArm==1)
        {
         // Guard harga yang sama dengan EA zona: buy limit wajib di bawah ask,
         // sell limit di atas bid. Sebuah limit di sisi salah akan diisi
         // terminal sebagai market dan mengubah arm ini jadi arm 0 tanpa
         // suara.
         if(go_long && entry>=ask)
           {
            g_skipped_price++;
            MarkOrdered(id);
            continue;
           }
         if(!go_long && entry<=bid)
           {
            g_skipped_price++;
            MarkOrdered(id);
            continue;
           }
         datetime expiry=time_[n-1]+(datetime)(InpRetestBars*PeriodSeconds(_Period));
         if(go_long)
            ok=trade.BuyLimit(lots,entry,_Symbol,stop,target,
                              ORDER_TIME_SPECIFIED,expiry,id);
         else
            ok=trade.SellLimit(lots,entry,_Symbol,stop,target,
                               ORDER_TIME_SPECIFIED,expiry,id);
        }
      else
        {
         if(go_long)
            ok=trade.Buy(lots,_Symbol,0.0,stop,target,id);
         else
            ok=trade.Sell(lots,_Symbol,0.0,stop,target,id);
        }

      if(ok)
         g_orders_placed++;
      else
        {
         g_orders_failed++;
         Print("order gagal fase ",id,": ",trade.ResultRetcode());
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
