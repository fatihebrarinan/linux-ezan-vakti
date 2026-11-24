"""Konum seçici: Diyanet'in ülke / şehir / ilçe listesinden seçim."""

import threading

from gi.repository import GLib, Gtk

from . import ayarlar as A
from .vakitler import api_get

TURKIYE_ID = "2"
_TR_SIRA = "AÂBCÇDEFGĞHIİÎJKLMNOÖPRSŞTUÛÜVYZ"


def _sira(metin):
    return [_TR_SIRA.find(c) if c in _TR_SIRA else 100 + ord(c) for c in metin.upper()]


class KonumSecici(Gtk.Dialog):
    def __init__(self, ebeveyn=None):
        super().__init__(title="Konum Seç", transient_for=ebeveyn, modal=True)
        self.set_default_size(440, -1)
        self.set_icon_name("find-location")
        self.add_button("İptal", Gtk.ResponseType.CANCEL)
        self.kaydet = self.add_button("Kaydet", Gtk.ResponseType.OK)
        self.kaydet.get_style_context().add_class("suggested-action")
        self.kaydet.set_sensitive(False)
        self.eski = A.konum() or {}

        grid = Gtk.Grid(row_spacing=10, column_spacing=12, border_width=16)
        self.get_content_area().add(grid)
        baslik = Gtk.Label(xalign=0)
        baslik.set_markup("<b>Namaz vakitleri için konumunuzu seçin</b>\n"
                          "<small>Vakitler Diyanet İşleri Başkanlığı verisidir.</small>")
        grid.attach(baslik, 0, 0, 2, 1)
        self.ulke = self._combo(grid, "Ülke", 1)
        self.sehir = self._combo(grid, "Şehir / Eyalet", 2)
        self.ilce = self._combo(grid, "İlçe", 3)
        self.durum = Gtk.Label(xalign=0)
        self.durum.get_style_context().add_class("dim-label")
        grid.attach(self.durum, 0, 4, 2, 1)

        self.ulke.connect("changed", self._ulke_degisti)
        self.sehir.connect("changed", self._sehir_degisti)
        self.ilce.connect("changed", lambda *_: self.kaydet.set_sensitive(self.ilce.get_active_id() is not None))
        self._yukle("/ulkeler", self.ulke, "UlkeAdi", "UlkeID", self.eski.get("ulkeId", TURKIYE_ID))
        self.show_all()

    def _combo(self, grid, etiket, satir):
        grid.attach(Gtk.Label(label=etiket, xalign=0), 0, satir, 1, 1)
        c = Gtk.ComboBoxText(hexpand=True)
        grid.attach(c, 1, satir, 1, 1)
        return c

    def _yukle(self, yol, combo, ad_k, id_k, secili=None):
        combo.remove_all()
        combo.set_sensitive(False)
        self.kaydet.set_sensitive(False)
        self.durum.set_text("Yükleniyor…")

        def bitti(veri, hata):
            if hata is not None:
                self.durum.set_text(f"Liste alınamadı: {hata}")
                return False
            self.durum.set_text("")
            for o in sorted(veri, key=lambda x: _sira(x[ad_k])):
                combo.append(o[id_k], A.baslik_harfi(o[ad_k]))
            combo.set_sensitive(True)
            if not (secili and combo.set_active_id(secili)) and len(veri) == 1:
                combo.set_active(0)
            return False

        def is_():
            try:
                GLib.idle_add(bitti, api_get(yol, 20), None)
            except Exception as e:  # noqa: BLE001
                GLib.idle_add(bitti, None, e)

        threading.Thread(target=is_, daemon=True).start()

    def _ulke_degisti(self, c):
        self.sehir.remove_all()
        self.ilce.remove_all()
        if c.get_active_id():
            self._yukle(f"/sehirler/{c.get_active_id()}", self.sehir, "SehirAdi", "SehirID", self.eski.get("sehirId"))

    def _sehir_degisti(self, c):
        self.ilce.remove_all()
        if c.get_active_id():
            self._yukle(f"/ilceler/{c.get_active_id()}", self.ilce, "IlceAdi", "IlceID", self.eski.get("ilceId"))

    def sec(self):
        """Diyaloğu çalıştırır; kaydedildiyse yeni konumu döndürür."""
        yanit = self.run()
        k = None
        if yanit == Gtk.ResponseType.OK and self.ilce.get_active_id():
            k = {
                "ulkeId": self.ulke.get_active_id(), "ulke": self.ulke.get_active_text(),
                "sehirId": self.sehir.get_active_id(), "sehir": self.sehir.get_active_text(),
                "ilceId": self.ilce.get_active_id(), "ilce": self.ilce.get_active_text(),
            }
            A.konum_kaydet(k)
        self.destroy()
        return k


def calistir():
    k = KonumSecici().sec()
    if k:
        from . import vakitler as V
        try:
            V.guncelle(zorla=True)
        except Exception as e:  # noqa: BLE001
            print(f"Vakitler indirilemedi: {e}")
    return 0
