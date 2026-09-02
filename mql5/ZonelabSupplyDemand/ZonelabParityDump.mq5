//+------------------------------------------------------------------+
//|                                          ZonelabParityDump.mq5   |
//|  Menjalankan KETIGA detektor MQL5 di dalam terminal, lalu menulis |
//|  bar dan zonanya ke CSV supaya Python bisa membandingkannya.      |
//|                                                                   |
//|  KENAPA INI ADA. Sampai 1 September 2026 tiga gate parity di      |
//|  backend/tools/ea_parity*.py membandingkan detektor numpy dengan  |
//|  PORT REFERENSI PYTHON di file yang sama, dan tidak pernah        |
//|  menyentuh satu baris pun MQL5. Ketiganya mencetak PARITY OK dan  |
//|  README menyebutnya "port faithful, parity-proven" - padahal yang |
//|  dibuktikan cuma Python cocok dengan Python. Kalau .mqh bergeser  |
//|  dari port referensinya, tidak ada yang merah.                    |
//|                                                                   |
//|  EA ini menutup lubang itu: bar yang dipakai IKUT ditulis, jadi   |
//|  Python tidak menebak window-nya. Selisih apa pun setelah itu     |
//|  murni logika detektor.                                           |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#include "SupplyDemandDetector.mqh"
#include "OrderBlockDetector.mqh"
#include "FVGDetector.mqh"
#include "InversionDetector.mqh"

input int    InpBars               = 3000;
//--- supply/demand (SDParams, default shipped) ---
input int    InpAtrPeriod          = 14;
input double InpImpulseBodyRatio   = 0.5;
input double InpImpulseAtr         = 1.0;
input int    InpBaseMaxBars        = 6;
input double InpBaseMaxAtr         = 2.5;
input double InpDepartureMinAtr    = 2.0;
input int    InpDepartureLookahead = 20;
input int    InpProximalBasis      = 0;
input double InpMinProfitMargin    = 0.0;
input double InpZoneMinAtr         = 0.05;
input double InpMaxBaseDrift       = 0.6;
input double InpMitigationPct      = 0.5;
input double InpMergeOverlapPct    = 0.6;
//--- order block ---
input double InpDisplacementAtr    = 1.5;
input int    InpDisplacementBars   = 5;
//--- fvg ---
input double InpMinGapAtr          = 0.1;

// Cukup untuk harga broker mana pun: emas 2 desimal, kripto 2, forex 5.
// Sepuluh desimal menulis nilai double-nya persis, bukan pembulatan.
#define DUMP_DIGITS 10

//+------------------------------------------------------------------+
int WriteZones(string filename,const SDZone &zones[],int count)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"kind","side","top","bottom","proximal","distal",
             "departure_atr","state","time_from","time_to","base_from");
   for(int i=0;i<count;i++)
      FileWrite(h,
                zones[i].kind,
                (zones[i].side==SD_DEMAND)?"demand":"supply",
                DoubleToString(zones[i].top,DUMP_DIGITS),
                DoubleToString(zones[i].bottom,DUMP_DIGITS),
                DoubleToString(zones[i].proximal,DUMP_DIGITS),
                DoubleToString(zones[i].distal,DUMP_DIGITS),
                DoubleToString(zones[i].departure_atr,DUMP_DIGITS),
                IntegerToString(zones[i].state),
                IntegerToString((long)zones[i].time_from),
                IntegerToString((long)zones[i].time_to),
                IntegerToString(zones[i].base_from));
   FileClose(h);
   return count;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   int total=Bars(_Symbol,_Period);
   int n=MathMin(InpBars,total-1);
   if(n<InpAtrPeriod+InpDisplacementBars+3)
     {
      Print("PARITYDUMP bar tidak cukup: ",n);
      return INIT_FAILED;
     }

   double open_[],high_[],low_[],close_[];
   datetime time_[];
   ArrayResize(open_,n); ArrayResize(high_,n);
   ArrayResize(low_,n);  ArrayResize(close_,n);
   ArrayResize(time_,n);
   // Konvensi index sama dengan Python: 0 = tertua, n-1 = bar TERAKHIR YANG
   // SUDAH TUTUP. shift 0 adalah bar yang masih terbentuk dan tidak diambil.
   for(int i=0;i<n;i++)
     {
      int shift=n-i;
      open_[i] =iOpen(_Symbol,_Period,shift);
      high_[i] =iHigh(_Symbol,_Period,shift);
      low_[i]  =iLow(_Symbol,_Period,shift);
      close_[i]=iClose(_Symbol,_Period,shift);
      time_[i] =iTime(_Symbol,_Period,shift);
     }

   int hb=FileOpen("zonelab_parity_bars.csv",
                   FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(hb==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal menulis bar, err=",GetLastError());
      return INIT_FAILED;
     }
   FileWrite(hb,"time","open","high","low","close");
   for(int i=0;i<n;i++)
      FileWrite(hb,
                IntegerToString((long)time_[i]),
                DoubleToString(open_[i],DUMP_DIGITS),
                DoubleToString(high_[i],DUMP_DIGITS),
                DoubleToString(low_[i],DUMP_DIGITS),
                DoubleToString(close_[i],DUMP_DIGITS));
   FileClose(hb);

   double atr[];
   SDWilderAtr(atr,high_,low_,close_,n,InpAtrPeriod);

   SDParams sp;
   sp.atr_period=InpAtrPeriod;
   sp.impulse_body_ratio=InpImpulseBodyRatio;
   sp.impulse_atr=InpImpulseAtr;
   sp.base_max_bars=InpBaseMaxBars;
   sp.base_max_atr=InpBaseMaxAtr;
   sp.departure_min_atr=InpDepartureMinAtr;
   sp.departure_lookahead=InpDepartureLookahead;
   sp.proximal_basis=InpProximalBasis;
   sp.min_profit_margin=InpMinProfitMargin;
   sp.zone_min_atr=InpZoneMinAtr;
   sp.max_base_drift=InpMaxBaseDrift;
   sp.mitigation_pct=InpMitigationPct;

   OBParams op;
   op.atr_period=InpAtrPeriod;
   op.displacement_atr=InpDisplacementAtr;
   op.displacement_bars=InpDisplacementBars;
   op.mitigation_pct=InpMitigationPct;

   FVGParams fp;
   fp.atr_period=InpAtrPeriod;
   fp.min_gap_atr=InpMinGapAtr;
   fp.mitigation_pct=InpMitigationPct;

   SDZone sd[],ob[],fvg[],ifvg[],brk[];
   int nsd =SDDetect(open_,high_,low_,close_,time_,atr,n,sp,sd);
   int nob =DetectOrderBlock(open_,high_,low_,close_,time_,atr,n,op,ob);
   int nfvg=DetectFVG(open_,high_,low_,close_,time_,atr,n,fp,fvg);
   // Kedua inversi memanggil detektor induknya sendiri, sama seperti
   // `_invert` di Python memanggil `detect_fvg` dan `detect_order_block`.
   // Menyodorkan array induk yang sudah ada di atas akan lebih murah dan akan
   // menjadi jalur kedua yang bisa menyimpang dari jalur yang di-ship.
   int nifvg=DetectIFVG(open_,high_,low_,close_,time_,atr,n,fp,ifvg);
   int nbrk =DetectBreaker(open_,high_,low_,close_,time_,atr,n,op,brk);

   WriteZones("zonelab_parity_sd.csv",sd,nsd);
   // Dedupe dibuang dari perbandingan detektor supaya selisih yang muncul
   // adalah selisih detektor. Tapi SDDedupe DIPAKAI di ZonelabSD.mq5 dan
   // sampai sekarang tidak ada satu pun gate yang menyentuhnya, karena
   // tools/ea_parity.py memasang merge_overlap_pct=1.0 yang menonaktifkannya.
   // Jadi dump kedua, dengan ambang yang benar-benar dikirim.
   int nsd_dedup=SDDedupe(sd,nsd,InpMergeOverlapPct);
   WriteZones("zonelab_parity_sd_dedup.csv",sd,nsd_dedup);
   WriteZones("zonelab_parity_ob.csv",ob,nob);
   WriteZones("zonelab_parity_fvg.csv",fvg,nfvg);
   WriteZones("zonelab_parity_ifvg.csv",ifvg,nifvg);
   WriteZones("zonelab_parity_brk.csv",brk,nbrk);

   PrintFormat("PARITYDUMP symbol=%s period=%d bars=%d sd=%d sd_dedup=%d ob=%d fvg=%d ifvg=%d brk=%d",
               _Symbol,(int)_Period,n,nsd,nsd_dedup,nob,nfvg,nifvg,nbrk);
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   // Kerjanya selesai di OnInit. Tick pertama menghentikan pass supaya
   // tester tidak menjalankan delapan bulan bar untuk sebuah dump.
   ExpertRemove();
  }
//+------------------------------------------------------------------+
