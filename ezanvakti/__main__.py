"""Komut satırı: ezan-vakti [uygulama|servis|guncelle|sustur|konum|durum]"""

import sys

import gi

gi.require_version("Gtk", "3.0")

KULLANIM = """Kullanım: ezan-vakti [komut]
  (boş)       Uygulamayı açar
  servis      Bildirim servisini çalıştırır
  guncelle    Vakitleri gerekiyorsa indirir (--zorla ile her durumda)
  sustur      Çalan ezanı durdurur
  konum       Konum seçiciyi açar
  durum       Bugünün vakitlerini yazdırır
  bugun       Günün özetini (bugun.json) yeniler
  --sayfa S   Uygulamayı açar: bugun | hafta | dini | ayarlar | hakkinda (ayarlar için: --widget KİMLİK)"""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    komut = argv[0] if argv else "uygulama"
    if komut in ("uygulama", "--sayfa"):
        from .uygulama import main as m
        return m(argv[1:] if komut == "uygulama" else argv)
    if komut == "servis":
        from .servis import main as m
        return m()
    if komut == "guncelle":
        from . import vakitler as V
        try:
            n = V.guncelle(zorla="--zorla" in argv)
        except Exception as e:  # noqa: BLE001
            print(f"Vakitler indirilemedi: {e}", file=sys.stderr)
            return 1
        print(f"{n} günlük vakit indirildi." if n else "Vakitler güncel.")
        return 0
    if komut == "bugun":
        from . import icerik
        icerik.bugun_yaz(zorla="--zorla" in argv)
        icerik.disa_ac()
        return 0
    if komut == "sustur":
        from .servis import ses_sustur
        return 0 if ses_sustur() else 1
    if komut == "konum":
        from .konum_secici import calistir
        return calistir()
    if komut == "durum":
        from . import ayarlar as A, takvim, vakitler as V
        k = A.konum()
        if not k:
            print("Konum seçilmedi. `ezan-vakti konum` ile seçin.")
            return 1
        d = V.Durum(V.gunleri_oku(k["ilceId"]))
        if not d.bugun:
            print("Bugünün vakitleri yok. `ezan-vakti guncelle` deneyin.")
            return 1
        print(f"{A.konum_adi(k)} — {d.bugun.miladi} — {d.bugun.hicri}")
        for v in V.VAKITLER:
            isaret = "▶" if v.id == d.simdiki else " "
            print(f" {isaret} {v.ad:<7} {d.bugun.saatler[v.id]}")
        if d.siradaki:
            print(f"{d.siradaki[0].yonelme} kalan: {V.sure_yaz(d.kalan)}")
        for g in takvim.yaklasan(adet=1):
            print(f"Sıradaki dini gün: {g['ad']} — {takvim.miladi_yaz(g['tarih'])}")
        return 0
    print(KULLANIM)
    return 0 if komut in ("-h", "--help", "yardim") else 2


if __name__ == "__main__":
    sys.exit(main())
