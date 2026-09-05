//+------------------------------------------------------------------+
//|                                                          QTClock.mqh|
//|  Rantai kuarter Quarterly Theory: mingguan, harian, 90 menit.      |
//|  Aritmetika jam murni, tanpa satu bar pun, jadi tidak bisa         |
//|  melihat ke depan secara konstruksi.                               |
//|  Copyright 2026 PT Surya Inovasi Prioritas (SURIOTA)              |
//+------------------------------------------------------------------+
#ifndef __QT_CLOCK_MQH__
#define __QT_CLOCK_MQH__

#include "NYClock.mqh"

// KENAPA HEADER INI ADA, DAN KENAPA BUKAN DI QuarterlyDetector.mqh.
// `QuarterlyDetector.mqh` punya kuarter derajat HARI - empat sesi enam jam -
// dan tidak punya derajat minggu maupun 90 menit. Rantai yang dinotasikan
// W-D-90m butuh ketiganya. Ditaruh terpisah supaya detektor yang sudah punya
// angka parity-nya di `docs/mt5_python_parity.json` tidak ikut berubah.
//
// PEMETAAN NAMA. Di sisi Python repo ini, derajat `day` menghasilkan empat
// sesi dan derajat `session` menghasilkan empat kuarter 90 menit di dalam
// sesi. Jadi "daily quarter" sumbernya = derajat `day`, dan "90m quarter"
// sumbernya = derajat `session`. Batasnya sama, namanya berbeda.

// Batas sesi dalam MENIT sejak tengah malam New York. Asia membungkus
// tengah malam, jadi ia diperiksa sebagai dua potongan dan bukan satu.
#define QT_ASIA_START    1170   // 19:30
#define QT_LONDON_START    90   // 01:30
#define QT_NYAM_START     450   // 07:30
#define QT_NYPM_START     810   // 13:30

//+------------------------------------------------------------------+
//| Kuarter mingguan: Senin=1 .. Kamis=4. Jumat, Sabtu, Minggu = 0.    |
//|                                                                    |
//| Nol berarti TIDAK ADA kuarter, bukan kuarter bernomor nol. Jumat   |
//| punya profilnya sendiri di metode ini (cleanup, kembali ke TWO),   |
//| jadi ia bukan Q5 dan bukan Q1 minggu berikutnya.                  |
//+------------------------------------------------------------------+
int QTWeeklyQuarter(datetime utc)
  {
   MqlDateTime ny;
   SDToNy(utc,ny);
   // MqlDateTime.day_of_week: 0=Minggu, 1=Senin .. 6=Sabtu.
   if(ny.day_of_week>=1 && ny.day_of_week<=4)
      return ny.day_of_week;
   return 0;
  }

//+------------------------------------------------------------------+
//| Menit sejak tengah malam New York.                                 |
//+------------------------------------------------------------------+
int QTNyMinutes(datetime utc)
  {
   MqlDateTime ny;
   SDToNy(utc,ny);
   return ny.hour*60+ny.min;
  }

//+------------------------------------------------------------------+
//| Kuarter harian: 1 Asia, 2 London, 3 NY AM, 4 NY PM.                |
//| Selalu mengembalikan 1..4 - setiap instant ada di sebuah sesi.     |
//+------------------------------------------------------------------+
int QTDailyQuarter(datetime utc)
  {
   int m=QTNyMinutes(utc);
   if(m>=QT_ASIA_START || m<QT_LONDON_START) return 1;
   if(m<QT_NYAM_START)                       return 2;
   if(m<QT_NYPM_START)                       return 3;
   return 4;
  }

//+------------------------------------------------------------------+
//| Menit yang sudah berjalan di dalam sesi yang memuat `utc`.         |
//|                                                                    |
//| Asia membungkus tengah malam: 19:30 sampai 23:59 adalah menit 0    |
//| sampai 269, dan 00:00 sampai 01:29 melanjutkannya di 270 sampai    |
//| 359. Tanpa cabang itu, tiap pagi Asia akan mulai ulang dari Q1 dan |
//| kuarter 90 menitnya bergeser satu sesi penuh.                      |
//+------------------------------------------------------------------+
int QTMinutesIntoSession(datetime utc)
  {
   int m=QTNyMinutes(utc);
   if(m>=QT_ASIA_START)   return m-QT_ASIA_START;
   if(m<QT_LONDON_START)  return m+(1440-QT_ASIA_START);
   if(m<QT_NYAM_START)    return m-QT_LONDON_START;
   if(m<QT_NYPM_START)    return m-QT_NYAM_START;
   return m-QT_NYPM_START;
  }

//+------------------------------------------------------------------+
//| Kuarter 90 menit di dalam sesi: 1..4.                              |
//+------------------------------------------------------------------+
int QTQuarter90(datetime utc)
  {
   int into=QTMinutesIntoSession(utc);
   int q=into/90+1;
   return (q>4)?4:q;
  }

//+------------------------------------------------------------------+
//| Apakah rantai (mingguan, harian, 90m) ada di sepuluh yang ia tulis.|
//|                                                                    |
//| Sepuluh dari enam puluh empat, jadi True adalah peristiwa satu     |
//| dari enam menurut aritmetika sebelum satu perilaku pasar pun       |
//| terlibat. Kutip angka itu setiap kali fungsi ini dikutip.          |
//|                                                                    |
//| False pada Jumat sampai Minggu, karena rantainya tidak lengkap.    |
//| Sisi Python menjawab "tidak diketahui" di sana; sini menjawab      |
//| "tidak", sama dengan implementasi referensinya. Selisih itu        |
//| DINYATAKAN dan bukan diperbaiki, karena EA harus memutuskan.       |
//+------------------------------------------------------------------+
bool QTHighProbChain(datetime utc)
  {
   int w=QTWeeklyQuarter(utc);
   if(w==0)
      return false;
   int d=QTDailyQuarter(utc);
   int q=QTQuarter90(utc);
   int code=w*100+d*10+q;
   return (code==111 || code==114 || code==141 || code==144 ||
           code==222 || code==333 ||
           code==411 || code==414 || code==441 || code==444);
  }

//+------------------------------------------------------------------+
//| Apakah `digit` diizinkan oleh sebuah filter berbentuk angka.       |
//|                                                                    |
//| NOL berarti SEMUA diizinkan, jadi lengan kontrol benar benar tidak |
//| difilter. 13 berarti kuarter 1 dan 3. Kuarter selalu 1..4, jadi    |
//| digit nol tidak pernah muncul dan tidak ada yang ambigu.           |
//|                                                                    |
//| ANGKA DAN BUKAN STRING, dan itu bukan selera. `.set` MT5 menyimpan |
//| input sebagai teks dan MENGABAIKAN key yang tidak ia kenal tanpa   |
//| satu pesan pun; sebuah string kosong dan sebuah bool Python        |
//| (`False`, dengan F besar) adalah dua cara diam untuk menjalankan   |
//| lengan yang berbeda dari yang tercatat.                            |
//+------------------------------------------------------------------+
bool QTDigitAllowed(int allowed,int digit)
  {
   if(allowed==0)
      return true;
   int rest=allowed;
   while(rest>0)
     {
      if(rest%10==digit)
         return true;
      rest/=10;
     }
   return false;
  }

#endif // __QT_CLOCK_MQH__
