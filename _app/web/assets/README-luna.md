# Luna maskot pozları

Tur (tanıtım), açılış ve durum kartı Luna'nın pozlarını buradan okur. Dosyalar
yoksa uygulama otomatik olarak mevcut `echo-mascot.webp` görseline düşer, yani
eksik dosya hata vermez — sadece o poz mevcut maskotla gösterilir.

## Eklemen gereken dosyalar

`_app/web/assets/` içine, **şeffaf arka planlı** (PNG veya WEBP), dikey/portre
Luna görselleri olarak koy:

| Dosya adı          | Poz / kullanım                                  |
|--------------------|-------------------------------------------------|
| `luna-wave.webp`   | El sallayan karşılama (turun ilk adımı)         |
| `luna-point.webp`  | Ekranı gösteren/anlatan poz (çoğu adım)         |
| `luna-run.webp`    | Hareketli/aksiyon poz (indir, izle, geçmiş)     |
| `luna-thumb.webp`  | Başparmak yukarı / onay (turun son adımı)       |

## Chibi durum görselleri

Koyu lacivert kenarlara sahip kare vignette'ler durum kartlarına ve boş
ekranlara doğrudan karışacak şekilde hazırlanmıştır:

| Dosya adı                    | Kullanım                                      |
|------------------------------|-----------------------------------------------|
| `luna-chibi-work.webp`       | İndirme, dönüştürme ve otomatik çözüm         |
| `luna-chibi-celebrate.webp`  | Hazır/tamamlandı durumu ve yardım ekranı      |
| `luna-chibi-discover.webp`   | Arama, tarama, boş kütüphane ve boş kuyruk    |

Bu üç görsel, mevcut Luna poz sayfası kimlik referansı ve uygulamanın
cyan–violet aurora arayüzü kullanılarak yerleşik imagegen akışıyla üretildi.
Ortak istem özeti: aynı uzun indigo saç, mor göz, hilal toka ve siyah/lacivert
siber arşivci kıyafetini koru; premium chibi anime oyun arayüzü illüstrasyonu;
koyu gece mavisi vignette; metin, logo, filigran ve ikinci karakter olmasın.

Not: `.webp` bekleniyor. Elinde `.png` varsa ya `.webp`'ye çevir ya da
`app.js` içindeki `TOUR_POSES` uzantısını `.png` yap.

## Önemli
- Arka plan **şeffaf** olmalı. Yapıştırdığın sprite sheet'lerdeki magenta/yeşil
  arka plan CSS ile saydamlaşmaz; önce arka planı silinmiş PNG dışa aktar.
- Kenarlardaki beyaz halka/çerçeve varsa temizlenmeli, yoksa koyu panelde
  belli olur.
- Kare değil, dikey (portre) kırpım daha iyi durur (ör. 900×1200 civarı).

Bu dosyaları ekleyip commit'lediğinde tur, açılış ekranı ve durum kartı
otomatik olarak gerçek pozları kullanır.
