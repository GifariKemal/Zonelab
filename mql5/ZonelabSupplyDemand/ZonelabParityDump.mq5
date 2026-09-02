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
#include "CISDDetector.mqh"
#include "StructureDetector.mqh"
#include "NYClock.mqh"
#include "PoolsDetector.mqh"
#include "LiquidityDetector.mqh"
#include "ProjectionsDetector.mqh"
#include "GapsDetector.mqh"

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
//--- cisd ---
input int    InpMinRun             = 2;
input int    InpInterruptTolerance = 0;
//--- structure ---
input int    InpSwingN             = 50;
input int    InpInternalN          = 5;
//--- pools ---
input string InpSessions           = "asia,london,ny_am,london_close";
//--- liquidity ---
input string InpPeriods            = "day,week,friday,monday";
input string InpBoundary           = "cycle";
//--- gaps ---
input int    InpGapKeep            = 5;
input int    InpHorizonEvery       = 200;   // sampel as_of tiap N bar

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
//| BENTUK KEDUA. Sebuah CISD bukan box: ia satu bar, satu arah dan
//| satu level horizontal, jadi ia tidak muat di SDZone dan komparator
//| zona tidak bisa membandingkannya sama sekali. Menuliskannya sebagai
//| SDZone dengan top == bottom akan membuatnya LOLOS pemeriksaan
//| geometri secara hampa, yang lebih buruk daripada tidak diperiksa.
//+------------------------------------------------------------------+
int WriteEvents(string filename,const SDCisd &events[],int count)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"index","time","direction","level","run_start","run_end","run_length");
   for(int i=0;i<count;i++)
      FileWrite(h,
                IntegerToString(events[i].index),
                IntegerToString((long)events[i].time),
                IntegerToString(events[i].direction),
                DoubleToString(events[i].level,DUMP_DIGITS),
                IntegerToString(events[i].run_start),
                IntegerToString(events[i].run_end),
                IntegerToString(events[i].run_length));
   FileClose(h);
   return count;
  }


//+------------------------------------------------------------------+
//| Break dan sweep, DUA SKALA dalam satu file dengan kolom `scale`.
//| `overlay` di Python menjalankan swing dan internal berdampingan,
//| dan gerbang order block memakai skala internal-nya sendiri lewat
//| ImbalanceParams.structure_n - jadi memisahkannya jadi dua file akan
//| menyembunyikan bahwa keduanya berasal dari satu loop yang sama.
//+------------------------------------------------------------------+
int WriteBreaks(string filename,const SDBreak &a[],int na,string scale_a,
                const SDBreak &b[],int nb,string scale_b)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"scale","index","time","kind","direction","level",
             "swing_index","bias_before");
   for(int i=0;i<na;i++)
      FileWrite(h,scale_a,IntegerToString(a[i].index),
                IntegerToString((long)a[i].time),a[i].kind,
                IntegerToString(a[i].direction),
                DoubleToString(a[i].level,DUMP_DIGITS),
                IntegerToString(a[i].swing_index),
                IntegerToString(a[i].bias_before));
   for(int i=0;i<nb;i++)
      FileWrite(h,scale_b,IntegerToString(b[i].index),
                IntegerToString((long)b[i].time),b[i].kind,
                IntegerToString(b[i].direction),
                DoubleToString(b[i].level,DUMP_DIGITS),
                IntegerToString(b[i].swing_index),
                IntegerToString(b[i].bias_before));
   FileClose(h);
   return na+nb;
  }


//+------------------------------------------------------------------+
//| JAM, DIBANDINGKAN SEBAGAI EPOCH. Empat layer ICT yang tersisa
//| menyatakan batasnya dalam waktu lokal New York, jadi sebuah jam
//| yang meleset satu jam menggeser setiap level di keempatnya tanpa
//| satu pun pesan. Yang ditulis di sini bukan tanggal terformat tapi
//| DETIK EPOCH, supaya perbandingannya integer lawan integer dan
//| tidak ada ruang untuk dua string yang terlihat sama.
//|
//| Probe-nya sengaja memuat kedua hari transisi tiap tahun beserta
//| hari sebelum dan sesudahnya, plus jam 02:00 yang di hari spring
//| forward TIDAK ADA - `app/pools.py` memulai sesi London tepat di
//| lubang itu.
//+------------------------------------------------------------------+
int WriteClock(string filename)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"year","month","day","hour","epoch","is_dst");

   int hours[]={0,2,5,6,7,10,12,17,18,19,23};
   int rows=0;
   for(int y=2016;y<=2027;y++)
     {
      // Hari transisi dan tetangganya, dihitung bukan diketik.
      datetime spring=SDNthWeekdayUtc(y,3,0,2,7);
      datetime autumn=SDNthWeekdayUtc(y,11,0,1,6);
      MqlDateTime sp,au;
      TimeToStruct(spring,sp);
      TimeToStruct(autumn,au);

      int days[6];
      int mons[6];
      for(int k=0;k<3;k++)
        {
         MqlDateTime d1,d2;
         TimeToStruct(spring+(k-1)*86400,d1);
         TimeToStruct(autumn+(k-1)*86400,d2);
         mons[k]=d1.mon;   days[k]=d1.day;
         mons[k+3]=d2.mon; days[k+3]=d2.day;
        }

      for(int k=0;k<6;k++)
         for(int hi=0;hi<ArraySize(hours);hi++)
           {
            datetime e=SDNyWall(y,mons[k],days[k],hours[hi],0);
            FileWrite(h,IntegerToString(y),IntegerToString(mons[k]),
                      IntegerToString(days[k]),IntegerToString(hours[hi]),
                      IntegerToString((long)e),
                      SDNyIsDst(e)?"1":"0");
            rows++;
           }
      // Satu tanggal biasa di tiap kuartal, supaya bukan cuma tepi yang diuji.
      int plain_mon[]={1,5,8,12};
      for(int k=0;k<4;k++)
         for(int hi=0;hi<ArraySize(hours);hi++)
           {
            datetime e=SDNyWall(y,plain_mon[k],15,hours[hi],0);
            FileWrite(h,IntegerToString(y),IntegerToString(plain_mon[k]),"15",
                      IntegerToString(hours[hi]),IntegerToString((long)e),
                      SDNyIsDst(e)?"1":"0");
            rows++;
           }
     }
   FileClose(h);
   return rows;
  }


//+------------------------------------------------------------------+
//| BENTUK KEEMPAT: level. Sebuah pool adalah SATU HARGA plus jendela
//| waktu, bukan kotak dan bukan event. `covered` dan `taken_at` ikut
//| karena keduanya yang membedakan pool yang berdiri dari pool yang
//| sudah diambil, dan itu satu-satunya hal yang pembaca chart pakai.
//+------------------------------------------------------------------+
int WriteLevels(string filename,const SDPool &pools[],int count)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"session","side","price","window_from","window_to",
             "first_bar","last_bar","bars","covered","gap_at_open",
             "gap_at_close","knowable_at","taken_at");
   for(int i=0;i<count;i++)
      FileWrite(h,pools[i].session,pools[i].side,
                DoubleToString(pools[i].price,DUMP_DIGITS),
                IntegerToString((long)pools[i].window_from),
                IntegerToString((long)pools[i].window_to),
                IntegerToString((long)pools[i].first_bar),
                IntegerToString((long)pools[i].last_bar),
                IntegerToString(pools[i].bars),
                pools[i].covered?"1":"0",
                IntegerToString(pools[i].gap_at_open),
                IntegerToString(pools[i].gap_at_close),
                IntegerToString((long)pools[i].knowable_at),
                IntegerToString((long)pools[i].taken_at));
   FileClose(h);
   return count;
  }


//+------------------------------------------------------------------+
//| BENTUK KELIMA: proyeksi. Satu harga plus kelipatan yang
//| menghasilkannya, plus range asalnya. `multiple`, `origin` dan
//| `height` ikut ditulis karena harga saja tidak bisa membedakan dua
//| sisi yang setuju pada satu angka lewat aritmetika yang berbeda.
//+------------------------------------------------------------------+
int WriteProjections(string filename,const SDProjection &rows[],int count)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE)
     {
      Print("PARITYDUMP gagal membuka ",filename," err=",GetLastError());
      return -1;
     }
   FileWrite(h,"session","window_from","window_to","direction","multiple",
             "price","origin","height","bars","knowable_at","taken_at");
   for(int i=0;i<count;i++)
      FileWrite(h,rows[i].session,
                IntegerToString((long)rows[i].window_from),
                IntegerToString((long)rows[i].window_to),
                IntegerToString(rows[i].direction),
                DoubleToString(rows[i].multiple,4),
                DoubleToString(rows[i].price,DUMP_DIGITS),
                DoubleToString(rows[i].origin,DUMP_DIGITS),
                DoubleToString(rows[i].height,DUMP_DIGITS),
                IntegerToString(rows[i].bars),
                IntegerToString((long)rows[i].knowable_at),
                IntegerToString((long)rows[i].taken_at));
   FileClose(h);
   return count;
  }


//+------------------------------------------------------------------+
//| BENTUK KEENAM: gap, yang beku, DAN event horizon, yang tidak.
//|
//| Gap ditulis sekali. Event horizon ditulis SEKALI PER as_of, karena
//| ia rata-rata antara dua gap yang bertetangga menurut harga: gap
//| baru yang menyisip di antara dua gap lama menggeser level yang
//| sudah tergambar tanpa satu harga pun berubah. Membandingkannya
//| sebagai satu daftar akan menanyakan "apakah nilainya sama" pada
//| objek yang jawabannya bergantung KAPAN ditanya.
//+------------------------------------------------------------------+
int WriteGaps(string filename,const SDGap &gaps[],int count)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE) return -1;
   FileWrite(h,"kind","top","bottom","close_time","open_time","approximate");
   for(int i=0;i<count;i++)
      FileWrite(h,gaps[i].kind,
                DoubleToString(gaps[i].top,DUMP_DIGITS),
                DoubleToString(gaps[i].bottom,DUMP_DIGITS),
                IntegerToString((long)gaps[i].close_time),
                IntegerToString((long)gaps[i].open_time),
                gaps[i].approximate?"1":"0");
   FileClose(h);
   return count;
  }

int WriteHorizons(string filename,const SDGap &gaps[],int ngap,
                  const datetime &time_[],int n,int keep,int every)
  {
   int h=FileOpen(filename,FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON,",");
   if(h==INVALID_HANDLE) return -1;
   FileWrite(h,"as_of","price","lower_open_time","upper_open_time");
   int rows=0;
   if(every<1) every=1;
   for(int b=0;b<n;b+=every)
     {
      SDHorizon hz[];
      int nh=SDEventHorizons(gaps,ngap,keep,time_[b],hz);
      for(int i=0;i<nh;i++)
        {
         FileWrite(h,IntegerToString((long)hz[i].as_of),
                   DoubleToString(hz[i].price,DUMP_DIGITS),
                   IntegerToString((long)hz[i].lower_open_time),
                   IntegerToString((long)hz[i].upper_open_time));
         rows++;
        }
     }
   FileClose(h);
   return rows;
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

   CISDParamsMQ cp;
   cp.min_run            =InpMinRun;
   cp.interrupt_tolerance=InpInterruptTolerance;
   SDCisd cisd[];
   SDRun  runs[];
   int ncisd=SDCisds(open_,close_,time_,n,cp,cisd,runs);
   WriteEvents("zonelab_parity_cisd.csv",cisd,ncisd);

   SDBreak brk_swing[],brk_internal[];
   SDSwing sw_swing[],sw_internal[];
   int nbs=SDBreaks(high_,low_,close_,time_,n,InpSwingN,InpSwingN,
                    brk_swing,sw_swing);
   int nbi=SDBreaks(high_,low_,close_,time_,n,InpInternalN,InpInternalN,
                    brk_internal,sw_internal);
   int nclock=WriteClock("zonelab_parity_clock.csv");

   string sessions[];
   int nsess=StringSplit(InpSessions,',',sessions);
   SDPool pools[];
   int npool=SDLiquidityPools(high_,low_,time_,n,sessions,pools);
   WriteLevels("zonelab_parity_pools.csv",pools,npool);

   string periods[];
   int nper=StringSplit(InpPeriods,',',periods);
   SDPool levels[];
   int nlvl=SDPeriodLevels(high_,low_,time_,n,periods,InpBoundary,levels);
   WriteLevels("zonelab_parity_liquidity.csv",levels,nlvl);

   SDProjection projs[];
   int nproj=SDProjections(high_,low_,time_,n,sessions,projs);
   WriteProjections("zonelab_parity_projections.csv",projs,nproj);

   SDGap gaps[];
   bool traded_through=false;
   int ngap=SDOpeningGaps(open_,close_,time_,n,gaps,traded_through);
   WriteGaps("zonelab_parity_gaps.csv",gaps,ngap);
   int nhz=WriteHorizons("zonelab_parity_horizons.csv",gaps,ngap,time_,n,
                         InpGapKeep,InpHorizonEvery);
   WriteBreaks("zonelab_parity_structure.csv",
               brk_swing,nbs,"swing",brk_internal,nbi,"internal");

   PrintFormat("PARITYDUMP symbol=%s period=%d bars=%d sd=%d sd_dedup=%d ob=%d fvg=%d ifvg=%d brk=%d cisd=%d struct=%d+%d clock=%d pools=%d liq=%d proj=%d gaps=%d hz=%d",
               _Symbol,(int)_Period,n,nsd,nsd_dedup,nob,nfvg,nifvg,nbrk,ncisd,nbs,nbi,nclock,npool,nlvl,nproj,ngap,nhz);
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
