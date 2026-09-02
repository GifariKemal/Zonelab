//+------------------------------------------------------------------+
//|                                                      NYClock.mqh |
//|  Jam dinding New York untuk MQL5, port dari backend/app/clock.py. |
//|                                                                   |
//|  KENAPA INI ADA, dan kenapa ia file sendiri. Empat layer ICT yang |
//|  tersisa - pools, liquidity, projections, gaps - semuanya         |
//|  menyatakan batasnya dalam WAKTU LOKAL New York, bukan dalam      |
//|  offset tetap dari UTC. New York berjalan UTC-5 di musim dingin   |
//|  dan UTC-4 di musim panas. Implementasi yang menanamkan salah     |
//|  satunya benar persis untuk separuh tahun dan diam-diam meleset   |
//|  satu jam untuk separuhnya lagi, dan tidak ada apa pun di chart   |
//|  yang mengatakan separuh mana yang sedang dilihat: level-levelnya |
//|  cuma duduk satu jam bergeser.                                    |
//|                                                                   |
//|  Waktu server broker BUKAN jawabannya. Exness biasanya UTC+2 atau |
//|  UTC+3 dengan tanggal transisi EU, yang berbeda dari US selama    |
//|  dua sampai tiga minggu tiap tahun. Selama minggu-minggu itu      |
//|  offset server ke New York berubah satu jam.                       |
//|                                                                   |
//|  Aturan US sejak 2007: DST mulai Minggu KEDUA Maret 02:00 waktu   |
//|  standar (07:00 UTC), berakhir Minggu PERTAMA November 02:00      |
//|  waktu daylight (06:00 UTC). History MT5 di mesin ini mulai 2016, |
//|  jadi aturan tunggal itu menutup seluruh rentangnya.               |
//|                                                                   |
//|  PEP 495, dan ini tidak boleh disederhanakan. Waktu dinding di    |
//|  dalam transisi bisa TIDAK ADA (spring forward) atau GANDA (fall  |
//|  back). Python memakai fold=0. Itu penting di sini dan bukan      |
//|  kasus teoretis: `app/pools.py` mendefinisikan sesi London mulai  |
//|  pukul 02:00 New York, tepat di lubangnya, dan docstring-nya      |
//|  menamainya "THE 02:00 HOLE" - pada hari spring-forward killzone  |
//|  London jadi dua jam nyata, bukan tiga. Fungsi di bawah           |
//|  mereproduksi fold=0, bukan menghindarinya.                       |
//|                                                                   |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)"
#property version   "1.00"

#define NY_EST (-5*3600)
#define NY_EDT (-4*3600)

//+------------------------------------------------------------------+
//| Epoch UTC dari hari kerja ke-`nth` bernomor `weekday` di sebuah    |
//| bulan, pada jam UTC tertentu. `weekday` 0 = Minggu, sesuai         |
//| MqlDateTime.day_of_week.                                           |
//+------------------------------------------------------------------+
datetime SDNthWeekdayUtc(int year,int month,int weekday,int nth,int utc_hour)
  {
   MqlDateTime t;
   ZeroMemory(t);
   t.year=year; t.mon=month; t.day=1;
   datetime first=StructToTime(t);
   MqlDateTime f;
   TimeToStruct(first,f);
   int shift=(weekday-f.day_of_week+7)%7;

   MqlDateTime r;
   ZeroMemory(r);
   r.year=year; r.mon=month; r.day=1+shift+(nth-1)*7; r.hour=utc_hour;
   return StructToTime(r);
  }

//+------------------------------------------------------------------+
//| Apakah instant UTC ini jatuh di dalam DST New York.                |
//+------------------------------------------------------------------+
bool SDNyIsDst(datetime utc)
  {
   MqlDateTime t;
   TimeToStruct(utc,t);
   datetime start=SDNthWeekdayUtc(t.year,3,0,2,7);   // Minggu ke-2 Maret, 07:00 UTC
   datetime stop =SDNthWeekdayUtc(t.year,11,0,1,6);  // Minggu ke-1 Nov, 06:00 UTC
   return (utc>=start && utc<stop);
  }

//+------------------------------------------------------------------+
//| Epoch UTC dari sebuah tanggal dan jam DINDING New York.            |
//|                                                                    |
//| Dua kandidat dicoba, lalu dipilih dengan aturan fold=0 Python:      |
//|   keduanya DST      -> daylight                                     |
//|   keduanya standar  -> standard                                     |
//|   hanya EST di DST  -> waktu itu TIDAK ADA (lubang spring forward), |
//|                        fold=0 memberi offset SEBELUM transisi       |
//|   hanya EDT di DST  -> waktu itu GANDA (fall back), fold=0 memberi  |
//|                        kemunculan PERTAMA, yaitu daylight           |
//+------------------------------------------------------------------+
datetime SDNyWall(int year,int month,int day,int hour,int minute)
  {
   MqlDateTime t;
   ZeroMemory(t);
   t.year=year; t.mon=month; t.day=day; t.hour=hour; t.min=minute;
   datetime naive=StructToTime(t);

   datetime utc_est=naive-NY_EST;   // -(-5h) = +5h
   datetime utc_edt=naive-NY_EDT;   // -(-4h) = +4h
   bool est_dst=SDNyIsDst(utc_est);
   bool edt_dst=SDNyIsDst(utc_edt);

   if(est_dst && edt_dst)
      return utc_edt;
   if(!est_dst && !edt_dst)
      return utc_est;
   if(est_dst && !edt_dst)
      return utc_est;   // lubang spring forward, fold=0
   return utc_edt;      // ambiguitas fall back, fold=0
  }

//+------------------------------------------------------------------+
//| Waktu dinding New York pada sebuah instant UTC.                    |
//+------------------------------------------------------------------+
void SDToNy(datetime utc,MqlDateTime &out)
  {
   TimeToStruct(utc+(SDNyIsDst(utc)?NY_EDT:NY_EST),out);
  }

//+------------------------------------------------------------------+
//| Jam `hour`:00 New York pada tanggal KALENDER New York dari         |
//| `epoch`, digeser `days` hari kalender.                             |
//|                                                                    |
//| Bukan `epoch + days*86400`: melewati transisi, satu hari kalender  |
//| adalah 23 atau 25 jam, jadi menambah detik menggeser jam dinding   |
//| dan grid-nya ikut melorot.                                         |
//+------------------------------------------------------------------+
datetime SDAtNyHour(datetime epoch,int hour,int days)
  {
   MqlDateTime t;
   SDToNy(epoch,t);
   MqlDateTime d;
   ZeroMemory(d);
   d.year=t.year; d.mon=t.mon; d.day=t.day;
   // Aritmetika TANGGAL dilakukan di ruang naif, tempat sehari selalu 86400,
   // lalu hasilnya dikonversi lewat SDNyWall yang tahu offsetnya.
   MqlDateTime shifted;
   TimeToStruct(StructToTime(d)+days*86400,shifted);
   return SDNyWall(shifted.year,shifted.mon,shifted.day,hour,0);
  }
//+------------------------------------------------------------------+
