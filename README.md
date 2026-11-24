# Ezan Vakti

Linux Mint Cinnamon için Diyanet namaz vakitleri: bir masaüstü uygulaması, bildirim servisi, masaüstü
widget'ları ve panel göstergesi. Arayüz Türkçedir.

- Günün vakitleri ve sıradaki vakte saniye saniye geri sayım
- Vakit girince bildirim; isteğe bağlı vakitten önce hatırlatma, kısa uyarı sesi ya da ezan
- Kandiller, bayramlar, Ramazan başlangıcı (Diyanet'in 2025–2035 listesi) ve hicrî takvim
- Günün ayeti, hadisi, vecizesi ve İslami resmi
- Birden fazla masaüstü widget'ı; her biri istenen bölümleri gösterir ve metne göre kendini boyutlandırır
- Alt panelde "Öğle 12:41" göstergesi; vakte 15 dakika kala rengi değişir
- İsteğe bağlı [Wallqueue](https://github.com/fatihebrarinan/background-images) entegrasyonu

## Gereksinimler

- Cinnamon masaüstü (Linux Mint 22.3 / Cinnamon 6.6 üzerinde denendi)
- `python3`, `python3-gi`, GTK 3, libnotify (`gir1.2-notify-0.7`); Linux Mint'te hazır gelir
- Ezan sesi için `gst-play-1.0` (GStreamer) ya da `paplay`
- Vakitleri indirmek için internet; 30 günlük vakit saklandığı için sonrasında çevrimdışı da çalışır

API anahtarı gerekmez.

## Kurulum

```bash
git clone https://github.com/fatihebrarinan/linux-ezan-vakti.git
cd linux-ezan-vakti
./install.sh
```

Kurulum şunları yapar:

- `ezan-vakti` komutunu `~/.local/bin/` altına bağlar.
- Menüye "Ezan Vakti" girişini ekler.
- Bildirim servisini oturum açılışına ekler ve hemen başlatır.
- Masaüstüne bir widget, panele de göstergeyi ekler.
- İlk kurulumda konum seçiciyi açar.

Kurulum, proje klasörüne sembolik bağlarla yapılır. Klasörü taşırsanız `./install.sh`'i yeniden çalıştırın.

Kaldırmak için `./uninstall.sh` çalıştırın. Ayarlar (`~/.config/ezan-vakti`) ve önbellek (`~/.cache/ezan-vakti`) silinmez.

## Kullanım

Uygulama menüdeki **Ezan Vakti** girişinden açılır ve beş sayfadan oluşur:

| Sayfa | İçerik |
| --- | --- |
| **Bugün** | Vakitler, geri sayım, günün ayeti, hadisi, vecizesi ve resmi |
| **Bu Hafta** | 7 günlük vakit tablosu ve o haftanın dini günleri |
| **Dini Günler** | Ramazan ve bayramlara kalan gün, yıl yıl dini günler listesi |
| **Ayarlar** | Konum, bildirimler, widget'lar, panel göstergesi, günün resmi |
| **Hakkında** | Sürüm, kaynaklar ve lisanslar, servisin durumu |

Bir widget'a ya da panel göstergesine sağ tıklayıp **Yapılandır…** seçerseniz uygulamanın Ayarlar sayfası
açılır; widget'tan açıldığında o widget'ın ayarı açık gelir. **Hakkında…** ise Hakkında sayfasını açar.

**Widget'lar:** Ayarlar sayfasından istediğiniz kadar widget ekleyebilirsiniz. Hazır türler: namaz vakitleri,
günün ayeti, günün hadisi, günün vecizesi ya da üçü birlikte. Her widget'ın bölümleri ayrı ayrı açılıp kapanır:

- konum ve tarih
- hicrî tarih
- sıradaki dini gün
- geri sayım
- namaz vakitleri
- ayet
- hadis
- vecize

Genişlik 0 iken widget metnin uzunluğuna göre kendini boyutlandırır.

### Komut satırı

```bash
ezan-vakti                     # uygulamayı açar
ezan-vakti --sayfa dini        # bir sayfada açar: bugun | hafta | dini | ayarlar | hakkinda
ezan-vakti durum               # bugünün vakitlerini yazdırır
ezan-vakti konum               # konum seçici
ezan-vakti guncelle --zorla    # vakitleri yeniden indirir
ezan-vakti sustur              # çalan ezanı durdurur
ezan-vakti servis              # bildirim servisi (oturum açılınca kendiliğinden başlar)
```

## Nasıl çalışır

Veriyle ilgili bütün işleri Python tarafı yapar:

- Vakitleri indirir.
- Bildirim gönderir.
- Her gün `~/.cache/ezan-vakti/bugun.json` dosyasına günün özetini yazar: içerik, dini gün, hicrî tarih.

Cinnamon widget'ı ve panel göstergesi bu dosyaları yalnızca okur ve değişince kendini yeniler. Ayarlar
`~/.config/ezan-vakti/ayarlar.json` dosyasındadır; varsayılanların tek kaynağı `data/varsayilan-ayarlar.json`'dır.

| Yol | İçerik |
| --- | --- |
| `ezanvakti/` | Python paketi: uygulama (GTK 3), servis, vakit, takvim, içerik ve resim modülleri |
| `bin/ezan-vakti` | Komut |
| `ezan-vakti@fatih/` | Cinnamon masaüstü widget'ı |
| `ezan-vakti-panel@fatih/` | Cinnamon panel göstergesi |
| `xlet-ortak/ortak.js` | Widget ile panelin ortak kodu (ikisine de sembolik bağla girer) |
| `data/` | Hazır veriler: ayetler, hadisler, vecizeler, resim listesi, dini günler, varsayılan ayarlar |
| `tools/` | `data/` altındaki dosyaları yeniden üreten betikler |

Widget ve panel hataları `~/.xsession-errors` dosyasına, servis kayıtları `~/.cache/ezan-vakti/servis.log`
dosyasına düşer. Koddaki bir değişikliğin geçerli olması için:

- **Uygulamada:** uygulamayı kapatıp yeniden açın.
- **Serviste:** `pkill -f "bin/ezan-vakti servis$"; ezan-vakti servis &` ile yeniden başlatın.
- **Widget ve panelde:** Cinnamon'u yeniden başlatın (`Alt+F2`, `r`).

## Wallqueue ile birlikte

[Wallqueue](https://github.com/fatihebrarinan/background-images) kuruluysa duvar kâğıdını o yönetir. İki uygulama
birbirinin kodunu kullanmaz; yalnızca dosyalar üzerinden konuşur:

| Dosya | Yazan | Okuyan |
| --- | --- | --- |
| `~/.local/share/ezan-vakti/resimler.json` | Ezan Vakti | Wallqueue'nun "İslami resimler (Ezan Vakti)" kaynağı |
| `~/.cache/ezan-vakti/bugun.json` | Ezan Vakti servisi | Widget'lar; Wallqueue (`islami_tema`: Ramazan'da ve dini günlerde İslami resimleri öne alır) |

Bugün sayfasındaki günün resmi, Wallqueue varsa `wallqueue add` komutuyla ona verilir. Wallqueue yoksa resim
doğrudan duvar kâğıdı yapılır.

## Veri kaynakları

| Veri | Kaynak |
| --- | --- |
| Namaz vakitleri | T.C. Diyanet İşleri Başkanlığı; resmî olmayan `ezanvakti.emushaf.net` API'si üzerinden |
| Dini günler ve hicrî takvim | Diyanet'in yıllık [Dini Günler Listesi](https://vakithesaplama.diyanet.gov.tr/dini_gunler.php); `tools/dini_gunler_indir.py` ile üretilir |
| Ayetler (100) | Arapça metin [Tanzil Projesi](https://tanzil.net) (Medine Mushafı); meal Türkiye Diyanet Vakfı (Tanzil üzerinden); `tools/ayetleri_olustur.py` ile üretilir |
| Hadisler (61) ve vecizeler (100) | Risale-i Nur Külliyatı |
| Resimler (100) | [Wikimedia Commons](https://commons.wikimedia.org) |

Hadis ve vecize metinleri kaynaktan harfi harfine alınmış ve kaynak adresleriyle doğrulanmıştır. Hadislerin
yanındaki kaynak notları yayıncınındır; sıhhat değerlendirmesi yapılmamıştır. Hadisler, Risale-i Nur'da geçenler
arasından tek başına anlaşılabilenlerdir.

Ayet mealinde iki dizgi hatası düzeltilmiş ve ilgili girdide belirtilmiştir.

## Lisans

Kod [MIT Lisansı](LICENSE) ile yayımlanmıştır: herkes kullanabilir, değiştirebilir ve dağıtabilir.

`data/` klasöründeki içerik bu lisansın kapsamında değildir; her biri kendi kaynağının şartlarına tabidir.

| İçerik | Şart |
| --- | --- |
| Arapça Kur'an metni | Tanzil şartları: metin değiştirilmeden kullanılır ve Tanzil'e atıf yapılır |
| Diyanet Vakfı meali | Ticari olmayan kullanım |
| Risale-i Nur metinleri | Kaynakları belirtilerek kullanılır |
| Resimler | Depoda yalnızca adresleri ve künyeleri vardır. Resimlerin kendisi her birinin yazarına aittir ve Commons'taki lisansıyla (CC BY, CC BY-SA, CC0 ya da kamu malı) kullanılır; uygulama yazarı ve lisansı resmin altında gösterir |
| Namaz vakitleri ve dini günler | Diyanet İşleri Başkanlığı'nın verisidir |

Bu içerikleri başka bir yerde, özellikle ticari amaçla kullanacaksanız ilgili kaynağın şartlarına bakın.
