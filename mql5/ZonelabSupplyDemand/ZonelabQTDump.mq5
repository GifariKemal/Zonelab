//+------------------------------------------------------------------+
//|                                                   ZonelabQTDump.mq5|
//|  Membuang rantai kuarter QT pada grid waktu tetap, untuk parity.   |
//|                                                                    |
//|  KENAPA INI ADA. `tests/test_mql5_contract.py` mengikat KONSTANTA  |
//|  di QTClock.mqh ke sisi Python dengan membaca teksnya, dan itu     |
//|  tidak menyentuh ARITMETIKANYA. Tempat kedua sisi paling mungkin   |
//|  menyimpang diam-diam adalah DST: MQL5 memakai `SDNyIsDst` yang    |
//|  ditulis tangan, Python memakai `zoneinfo`. Selisih satu jam di    |
//|  akhir Maret akan menggeser SETIAP kuarter di sekitarnya, dan      |
//|  tidak ada yang gagal - kedua venue tetap mengeluarkan angka.      |
//|                                                                    |
//|  `docs/mt5_python_parity.json` sudah mencatat bentuk kegagalan     |
//|  yang sama: 6 dari 8 sel tidak sepakat, dan itu baru ketahuan      |
//|  setelah ada yang membandingkan.                                   |
//|                                                                    |
//|  Kerjanya selesai di OnInit lalu pass dihentikan, sama dengan      |
//|  ZonelabParityDump.                                                |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"
#property strict

#include "QTClock.mqh"

// Grid yang dibuang: dari `InpFrom` selama `InpDays` hari kalender, tiap
// `InpStepMinutes` menit. Default menutupi satu tahun penuh termasuk KEDUA
// transisi DST New York, yang adalah seluruh alasan file ini ada.
input string InpFrom        = "2026.01.01";  // tanggal mulai, waktu UTC
input int    InpDays        = 365;
input int    InpStepMinutes = 30;
input string InpOut         = "zonelab_qt_clock.csv";

int OnInit()
  {
   datetime from = StringToTime(InpFrom);
   if(from == 0)
     {
      Print("BLOCKER: InpFrom tidak terbaca: ", InpFrom);
      return INIT_FAILED;
     }

   int handle = FileOpen(InpOut, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ",");
   if(handle == INVALID_HANDLE)
     {
      Print("BLOCKER: tidak bisa menulis ", InpOut, " err=", GetLastError());
      return INIT_FAILED;
     }

   FileWrite(handle, "utc", "weekly", "daily", "q90", "highprob");
   long step = (long)InpStepMinutes * 60;
   long span = (long)InpDays * 86400;
   int rows = 0;
   for(long offset = 0; offset < span; offset += step)
     {
      datetime at = (datetime)((long)from + offset);
      FileWrite(handle,
                (long)at,
                QTWeeklyQuarter(at),
                QTDailyQuarter(at),
                QTQuarter90(at),
                QTHighProbChain(at) ? 1 : 0);
      rows++;
     }
   FileClose(handle);
   Print("QT clock dump: ", rows, " baris ke ", InpOut);

   // INIT_SUCCEEDED, LALU `ExpertRemove` DI TICK PERTAMA. Pola ini disalin
   // dari `ZonelabParityDump.mq5` dan bukan dipilih sendiri: `INIT_FAILED`
   // membatalkan pass sebelum tester menulis report, dan
   // `tools/mt5_backtest.py` MENUNGGU report itu muncul sampai timeout-nya
   // habis - tiga puluh menit menunggu file yang tidak akan pernah ada.
   return INIT_SUCCEEDED;
  }

void OnTick()
  {
   // Kerjanya selesai di OnInit. Tick pertama menghentikan pass supaya tester
   // tidak menjalankan delapan bulan bar untuk sebuah dump jam.
   ExpertRemove();
  }
//+------------------------------------------------------------------+
