"""Ezan Vakti uygulaması: Bugün · Bu Hafta · Dini Günler · Ayarlar."""

import datetime as dt
import html
import os
import shutil
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango  # noqa: E402

from . import __version__  # noqa: E402
from . import ayarlar as A  # noqa: E402
from . import cinnamon, icerik, resim, takvim  # noqa: E402
from . import vakitler as V  # noqa: E402

UYGULAMA_KIMLIGI = "io.github.ezanvakti.EzanVakti"
ICERIK_GENISLIGI = 760

CSS = b"""
.kart { background-color: alpha(@theme_fg_color, 0.045); border-radius: 12px; padding: 18px; }
.kart-baslik { font-weight: bold; font-size: 0.8em; letter-spacing: 1px; opacity: 0.65; }
.konum { font-size: 1.5em; font-weight: bold; }
.soluk { opacity: 0.65; }
.sayac { font-size: 2.8em; font-weight: bold; color: @theme_selected_bg_color; }
.vakit-kutu { border-radius: 10px; padding: 10px 4px; background-color: alpha(@theme_fg_color, 0.04); }
.vakit-kutu.simdiki { background-color: alpha(@theme_selected_bg_color, 0.28); }
.vakit-kutu .saat { font-size: 1.35em; font-weight: bold; }
.vakit-kutu.siradaki .saat, .vakit-kutu.siradaki .ad { color: @theme_selected_bg_color; }
.arapca { font-family: "Noto Naskh Arabic", "Amiri", serif; font-size: 1.55em; }
.vurgulu { color: @theme_selected_bg_color; font-weight: bold; }
.tablo-baslik { font-weight: bold; opacity: 0.65; }
.satir-bugun { background-color: alpha(@theme_selected_bg_color, 0.22); border-radius: 8px; }
.gecmis { opacity: 0.45; }
.geri-sayim-kart { border-radius: 12px; padding: 14px; background-color: alpha(@theme_selected_bg_color, 0.14); }
.buyuk-sayi { font-size: 2em; font-weight: bold; }
.ayar-bolum { font-weight: bold; font-size: 1.1em; }
"""


def etiket(metin="", sinif=None, xalign=0, sar=True, secilebilir=False, markup=False):
    e = Gtk.Label(xalign=xalign)
    if markup:
        e.set_markup(metin)
    else:
        e.set_text(metin)
    if sar:
        e.set_line_wrap(True)
        e.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        e.set_max_width_chars(40)  # doğal genişliği sınırla; ayrılan alan kadar genişler
    e.set_selectable(secilebilir)
    for s in ([sinif] if isinstance(sinif, str) else sinif or []):
        e.get_style_context().add_class(s)
    return e


def kart(baslik=None):
    kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    kutu.get_style_context().add_class("kart")
    if baslik:
        kutu.pack_start(etiket(baslik.upper(), "kart-baslik"), False, False, 0)
    return kutu


def kaydirmali(icerik_kutusu):
    sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
    ortala = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=20, margin_bottom=28)
    icerik_kutusu.set_size_request(ICERIK_GENISLIGI, -1)
    ortala.pack_start(icerik_kutusu, False, False, 0)
    sw.add(ortala)
    return sw


def rgba(metin):
    r = Gdk.RGBA()
    r.parse(metin or "white")
    return r


def wallqueue_yolu():
    """Wallqueue kuruluysa komutunun yolu, değilse None."""
    yol = shutil.which("wallqueue") or os.path.expanduser("~/.local/bin/wallqueue")
    return yol if os.path.exists(yol) else None


def kalan_gun_yaz(gun):
    return "bugün" if gun == 0 else "yarın" if gun == 1 else f"{gun} gün sonra"


# ======================= Bugün =======================

class BugunSayfasi(Gtk.Box):
    def __init__(self, pencere):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.pencere = pencere
        self.kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(kaydirmali(self.kutu), True, True, 0)

        # Üst kart: konum, tarih, geri sayım, vakitler
        ust = kart()
        satir = Gtk.Box(spacing=8)
        self.lbl_konum = etiket("", "konum", sar=False)
        degistir = Gtk.Button(label="Konumu değiştir", relief=Gtk.ReliefStyle.NONE, valign=Gtk.Align.CENTER)
        degistir.connect("clicked", lambda *_: pencere.konum_sec())
        satir.pack_start(self.lbl_konum, True, True, 0)
        satir.pack_end(degistir, False, False, 0)
        ust.pack_start(satir, False, False, 0)
        self.lbl_tarih = etiket("", "soluk")
        ust.pack_start(self.lbl_tarih, False, False, 0)
        self.lbl_dini = etiket("", "vurgulu")
        ust.pack_start(self.lbl_dini, False, False, 0)

        self.lbl_sayac = etiket("--:--:--", "sayac", xalign=0.5)
        self.lbl_sayac_alt = etiket("", "soluk", xalign=0.5)
        ust.pack_start(self.lbl_sayac, False, False, 6)
        ust.pack_start(self.lbl_sayac_alt, False, False, 0)

        vakit_satiri = Gtk.Box(spacing=8, homogeneous=True, margin_top=8)
        self.vakit_kutulari = {}
        for v in V.VAKITLER:
            k = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            k.get_style_context().add_class("vakit-kutu")
            ad = etiket(v.ad, "ad", xalign=0.5, sar=False)
            saat = etiket("--:--", "saat", xalign=0.5, sar=False)
            k.pack_start(ad, False, False, 0)
            k.pack_start(saat, False, False, 0)
            vakit_satiri.pack_start(k, True, True, 0)
            self.vakit_kutulari[v.id] = (k, saat)
        ust.pack_start(vakit_satiri, False, False, 0)
        self.kutu.pack_start(ust, False, False, 0)

        # Günün içerikleri
        self.kart_ayet = kart("Günün Ayeti")
        self.kart_hadis = kart("Günün Hadisi")
        self.kart_vecize = kart("Günün Vecizesi")
        self.kart_resim = kart("Günün Resmi")
        for k in (self.kart_ayet, self.kart_hadis, self.kart_vecize, self.kart_resim):
            self.kutu.pack_start(k, False, False, 0)
        self.icerik_gunu = None
        self.resim_anahtari = None

    # -- yardımcılar --
    @staticmethod
    def _temizle(k):
        for c in k.get_children()[1:]:
            k.remove(c)
            c.destroy()

    def _kaynak(self, k, metin):
        k.pack_start(etiket(metin, "soluk", secilebilir=True), False, False, 0)

    def yenile(self):
        """Konum, vakit verisi veya gün değişince her şeyi baştan çizer."""
        self.icerik_gunu = None
        self.resim_anahtari = None
        self.tik()

    def tik(self):
        simdi = dt.datetime.now()
        bugun = simdi.date()
        k = A.konum()
        self.lbl_konum.set_text(A.konum_adi(k))
        d = V.Durum(self.pencere.gunler, simdi)

        hicri = d.bugun.hicri if d.bugun else takvim.hicri_yaz(bugun)
        self.lbl_tarih.set_text(f"{takvim.miladi_yaz(bugun)}" + (f"  ·  {hicri}" if hicri else ""))

        bugunku = takvim.o_gun(bugun)
        if bugunku:
            self.lbl_dini.set_text("Bugün: " + ", ".join(g["ad"] for g in bugunku))
        else:
            y = takvim.yaklasan(bugun, 1)
            self.lbl_dini.set_text(
                f"Sıradaki: {y[0]['ad']} — {kalan_gun_yaz((y[0]['tarih'] - bugun).days)}" if y else "")
        self.lbl_dini.set_visible(bool(self.lbl_dini.get_text()))

        if not k:
            self.lbl_sayac.set_text("--:--:--")
            self.lbl_sayac_alt.set_text("Başlamak için konum seçin")
        elif not d.bugun:
            self.lbl_sayac.set_text("--:--:--")
            self.lbl_sayac_alt.set_text("Vakitler indiriliyor…" if self.pencere.indiriliyor
                                        else "Vakitler alınamadı; internet bağlantısını kontrol edin.")
        elif d.siradaki:
            self.lbl_sayac.set_text(V.sure_yaz(d.kalan))
            self.lbl_sayac_alt.set_text(f"{d.siradaki[0].yonelme} kalan")
        for v in V.VAKITLER:
            kutu, saat = self.vakit_kutulari[v.id]
            saat.set_text(d.bugun.saatler[v.id] if d.bugun else "--:--")
            ctx = kutu.get_style_context()
            for sinif, kosul in (("simdiki", d.bugun and v.id == d.simdiki),
                                 ("siradaki", d.siradaki and v.id == d.siradaki[0].id)):
                (ctx.add_class if kosul else ctx.remove_class)(sinif)

        if self.icerik_gunu != bugun:
            self.icerik_gunu = bugun
            self._icerikleri_ciz(bugun)

    def _icerikleri_ciz(self, bugun):
        # Ayet
        k = self.kart_ayet
        self._temizle(k)
        a = icerik.gunun_ayeti(bugun)
        if a:
            k.pack_start(etiket(a["arapca"], "arapca", xalign=1, secilebilir=True), False, False, 0)
            k.pack_start(etiket(a["meal"], secilebilir=True), False, False, 0)
            self._kaynak(k, a["ref"])
            k.set_tooltip_text(icerik.kaynak_notu("ayetler.json", "ayetler") + (f"\n{a['not']}" if a.get("not") else ""))
        else:
            k.pack_start(etiket("Ayet listesi bulunamadı.", "soluk"), False, False, 0)

        # Hadis
        k = self.kart_hadis
        self._temizle(k)
        h = icerik.gunun_hadisi(bugun)
        if h:
            k.pack_start(etiket(h["arapca"], "arapca", xalign=1, secilebilir=True), False, False, 0)
            k.pack_start(etiket(h["turkce"], secilebilir=True), False, False, 0)
            kaynak = f"Risale-i Nur › {h['cite_as']}"
            if h.get("turkce_kaynak") == "yayinci":
                kaynak += "\nTürkçesi: yayıncının tercümesi"
            if h.get("yayinci_kaynak"):
                kaynak += "\nYayıncının kaynak notu: " + h["yayinci_kaynak"]
            self._kaynak(k, kaynak)
            k.set_tooltip_text(icerik.kaynak_notu("hadisler.json", "hadisler"))
        else:
            k.pack_start(etiket("Hadis listesi henüz hazır değil.", "soluk"), False, False, 0)

        # Vecize
        k = self.kart_vecize
        self._temizle(k)
        v = icerik.gunun_vecizesi(bugun)
        if v:
            e = etiket(v["metin"], secilebilir=True)
            e.get_style_context().add_class("vecize")
            k.pack_start(e, False, False, 0)
            self._kaynak(k, v["cite_as"])
            if v.get("lugat"):
                ex = Gtk.Expander(label="Lügat")
                ex.add(etiket("\n".join(f"<b>{html.escape(l['kelime'])}</b>: {html.escape(l['anlam'])}"
                                        for l in v["lugat"]), markup=True, secilebilir=True))
                k.pack_start(ex, False, False, 0)
        else:
            k.pack_start(etiket("Vecize listesi henüz hazır değil.", "soluk"), False, False, 0)

        self._resmi_ciz(bugun)
        self.kutu.show_all()

    def _resmi_ciz(self, bugun):
        k = self.kart_resim
        ayar = self.pencere.ayar
        r = resim.gunun_resmi(ayar, bugun)
        k.set_visible(r is not None)
        if r is None:
            return
        self._temizle(k)
        if r.get("hata"):
            k.pack_start(etiket(r["hata"], "soluk"), False, False, 0)
            k.show_all()
            return
        resim_kutusu = Gtk.Image()
        k.pack_start(resim_kutusu, False, False, 0)
        bilgi = r["bilgi"]
        if bilgi:
            k.pack_start(etiket(bilgi.get("aciklama", ""), "vecize"), False, False, 0)
            atif = (f"<a href=\"{html.escape(bilgi['sayfa_url'])}\">{html.escape(bilgi.get('yazar') or 'Bilinmiyor')}</a>"
                    f" · <a href=\"{html.escape(bilgi.get('lisans_url') or bilgi['sayfa_url'])}\">"
                    f"{html.escape(bilgi.get('lisans', ''))}</a> · Wikimedia Commons")
            k.pack_start(etiket(atif, "soluk", markup=True), False, False, 0)
        elif r["yol"]:
            k.pack_start(etiket(os.path.basename(r["yol"]), "soluk"), False, False, 0)

        dugmeler = Gtk.Box(spacing=8)
        if wallqueue_yolu():  # duvar kâğıdını Wallqueue yönetiyor: resmi ona teslim et
            eylemler = [(Gtk.Button(label="Şimdi duvar kâğıdı yap"), True),
                        (Gtk.Button(label="Wallqueue sırasına ekle"), False)]
        else:
            eylemler = [(Gtk.Button(label="Duvar kâğıdı yap"), None)]
        ac = Gtk.Button(label="Büyük aç")
        for d, _ in eylemler:
            dugmeler.pack_start(d, False, False, 0)
            d.set_sensitive(False)
        dugmeler.pack_start(ac, False, False, 0)
        k.pack_start(dugmeler, False, False, 0)
        ac.set_sensitive(False)

        def goster(yol, hata=None):
            if hata or not yol:
                resim_kutusu.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
                if hata:
                    k.pack_start(etiket(f"Resim indirilemedi: {hata}", "soluk"), False, False, 0)
                    k.show_all()
                return False
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(yol, ICERIK_GENISLIGI - 36, 520, True)
                resim_kutusu.set_from_pixbuf(pb)
            except GLib.Error:
                resim_kutusu.set_from_icon_name("image-missing", Gtk.IconSize.DIALOG)
                return False
            ac.set_sensitive(True)
            for d, simdi in eylemler:
                d.set_sensitive(True)
                d.connect("clicked", lambda dg, s=simdi: self._duvar_kagidi(yol, bilgi, dg, s))
            ac.connect("clicked", lambda *_: Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(yol), None))
            return False

        if r["yol"]:
            goster(r["yol"])
        else:
            resim_kutusu.set_from_icon_name("image-loading", Gtk.IconSize.DIALOG)

            def indir():
                try:
                    GLib.idle_add(goster, resim.indir(bilgi))
                except Exception as e:  # noqa: BLE001
                    GLib.idle_add(goster, None, e)
            threading.Thread(target=indir, daemon=True).start()
        k.show_all()

    def _duvar_kagidi(self, yol, bilgi, dugme, simdi):
        """simdi None: Wallqueue yok, doğrudan duvar kâğıdı. True/False: Wallqueue'ya şimdi göster / sıraya ekle."""
        dugme.set_sensitive(False)
        if simdi is None:
            resim.duvar_kagidi_yap(yol)
            dugme.set_label("Duvar kâğıdı yapıldı ✓")
            return
        komut = [wallqueue_yolu(), "add", yol]
        if bilgi:
            komut += ["--title", bilgi.get("aciklama", ""),
                      "--credit", " · ".join(x for x in (bilgi.get("yazar"), bilgi.get("lisans")) if x),
                      "--page-url", bilgi.get("sayfa_url", "")]
        if simdi:
            komut.append("--now")

        def is_():
            p = subprocess.run(komut, capture_output=True, text=True)
            GLib.idle_add(bitti, p.returncode, (p.stderr or p.stdout).strip())

        def bitti(kod, cikti):
            if kod == 0:
                dugme.set_label("Duvar kâğıdı yapıldı ✓" if simdi else "Sıraya eklendi ✓")
            else:
                dugme.set_label("Olmadı")
                dugme.set_tooltip_text(cikti or "Wallqueue hata verdi")
                dugme.set_sensitive(True)
            return False
        threading.Thread(target=is_, daemon=True).start()


# ======================= Bu Hafta =======================

class HaftaSayfasi(Gtk.Box):
    def __init__(self, pencere):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.pencere = pencere
        self.kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(kaydirmali(self.kutu), True, True, 0)
        self.kart = kart("Bu hafta")
        self.kutu.pack_start(self.kart, False, False, 0)
        self.grid = Gtk.Grid(column_spacing=6, row_spacing=2)
        self.kart.pack_start(self.grid, False, False, 0)
        self.kutu.pack_start(etiket("Vakitler Diyanet İşleri Başkanlığı verisidir.", "soluk"), False, False, 0)
        self.cizilen = None

    def yenile(self):
        self.cizilen = None
        self.tik()

    def tik(self):
        bugun = dt.date.today()
        if self.cizilen == bugun:
            return
        self.cizilen = bugun
        for c in self.grid.get_children():
            self.grid.remove(c)
        basliklar = ["Gün", "Hicrî"] + [v.ad for v in V.VAKITLER]
        for i, b in enumerate(basliklar):
            self.grid.attach(etiket(b, "tablo-baslik", xalign=0 if i < 2 else 0.5, sar=False), i, 0, 1, 1)
        for satir in range(7):
            t = bugun + dt.timedelta(days=satir)
            g = self.pencere.gunler.get(t)
            arka = Gtk.Box()
            if satir == 0:
                arka.get_style_context().add_class("satir-bugun")
            self.grid.attach(arka, 0, satir + 1, len(basliklar), 1)

            ad = "Bugün" if satir == 0 else "Yarın" if satir == 1 else takvim.GUNLER[t.weekday()]
            gun_kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin=8)
            gun_kutu.pack_start(etiket(f"<b>{ad}</b>", markup=True, sar=False), False, False, 0)
            gun_kutu.pack_start(etiket(takvim.miladi_yaz(t, gun_adi=False), "soluk", sar=False), False, False, 0)
            for dg in takvim.o_gun(t):
                gun_kutu.pack_start(etiket(dg["ad"], "vurgulu"), False, False, 0)
            self.grid.attach(gun_kutu, 0, satir + 1, 1, 1)

            hicri = g.hicri if g else takvim.hicri_yaz(t)
            self.grid.attach(etiket(hicri, "soluk", sar=True, xalign=0), 1, satir + 1, 1, 1)
            for i, v in enumerate(V.VAKITLER):
                e = etiket(g.saatler[v.id] if g else "—", xalign=0.5, sar=False)
                e.set_hexpand(True)
                self.grid.attach(e, i + 2, satir + 1, 1, 1)
        self.grid.show_all()


# ======================= Dini Günler =======================

class DiniGunlerSayfasi(Gtk.Box):
    def __init__(self, pencere):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.pencere = pencere
        self.kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(kaydirmali(self.kutu), True, True, 0)

        self.ozet = Gtk.Box(spacing=12, homogeneous=True)
        self.kutu.pack_start(self.ozet, False, False, 0)

        self.liste_kart = kart()
        ust = Gtk.Box(spacing=8)
        ust.pack_start(etiket("DİNİ GÜNLER", "kart-baslik", sar=False), True, True, 0)
        self.yil = Gtk.ComboBoxText()
        for y in takvim.yillar():
            self.yil.append(str(y), str(y))
        self.yil.connect("changed", lambda *_: self._listeyi_ciz())
        ust.pack_end(self.yil, False, False, 0)
        self.liste_kart.pack_start(ust, False, False, 0)
        self.grid = Gtk.Grid(column_spacing=16, row_spacing=6)
        self.liste_kart.pack_start(self.grid, False, False, 0)
        self.kutu.pack_start(self.liste_kart, False, False, 0)
        self.kutu.pack_start(etiket(
            "Kandiller, belirtilen günün akşamı (o geceye bağlanan akşam) idrak edilir. "
            f"Kaynak: {takvim.kaynak() or 'Diyanet İşleri Başkanlığı'}.", "soluk"), False, False, 0)
        self.cizilen = None

    def yenile(self):
        self.cizilen = None
        self.tik()

    def tik(self):
        bugun = dt.date.today()
        if self.cizilen == bugun:
            return
        self.cizilen = bugun
        for c in self.ozet.get_children():
            self.ozet.remove(c)
        for ad, etiket_adi in (("Ramazan Başlangıcı", "Ramazan"), ("Ramazan Bayramı (1. gün)", "Ramazan Bayramı"),
                               ("Kurban Bayramı (1. gün)", "Kurban Bayramı")):
            y = takvim.yaklasan(bugun, 1, yalniz={ad})
            k = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            k.get_style_context().add_class("geri-sayim-kart")
            k.pack_start(etiket(etiket_adi, "tablo-baslik", xalign=0.5), False, False, 0)
            if y:
                gun = (y[0]["tarih"] - bugun).days
                k.pack_start(etiket("Bugün" if gun == 0 else f"{gun} gün", "buyuk-sayi", xalign=0.5), False, False, 0)
                k.pack_start(etiket(takvim.miladi_yaz(y[0]["tarih"]), "soluk", xalign=0.5), False, False, 0)
            else:
                k.pack_start(etiket("—", "buyuk-sayi", xalign=0.5), False, False, 0)
            self.ozet.pack_start(k, True, True, 0)
        self.ozet.show_all()
        if not self.yil.set_active_id(str(bugun.year)) and takvim.yillar():
            self.yil.set_active(0)
        self._listeyi_ciz()

    def _listeyi_ciz(self):
        for c in self.grid.get_children():
            self.grid.remove(c)
        yil = self.yil.get_active_id()
        if not yil:
            self.grid.attach(etiket("Dini günler listesi bulunamadı.", "soluk"), 0, 0, 1, 1)
            self.grid.show_all()
            return
        bugun = dt.date.today()
        siradaki = next((g for g in takvim.dini_gunler() if g["tarih"] >= bugun), None)
        for i, b in enumerate(["Tarih", "Gün", "Hicrî", "Dini gün", ""]):
            self.grid.attach(etiket(b, "tablo-baslik", sar=False), i, 0, 1, 1)
        for satir, g in enumerate(takvim.dini_gunler(int(yil)), start=1):
            t = g["tarih"]
            h = g["hicri"]
            hucreler = [
                takvim.miladi_yaz(t, gun_adi=False), takvim.GUNLER[t.weekday()],
                f"{h[2]} {takvim.HICRI_AYLAR[h[1] - 1]} {h[0]}", g["ad"],
                "" if t < bugun else kalan_gun_yaz((t - bugun).days),
            ]
            for i, metin in enumerate(hucreler):
                e = etiket(metin, sar=False)
                if t < bugun:
                    e.get_style_context().add_class("gecmis")
                elif g is siradaki or (siradaki and t == siradaki["tarih"]):
                    e.get_style_context().add_class("vurgulu")
                self.grid.attach(e, i, satir, 1, 1)
        self.grid.show_all()


# ======================= Ayarlar =======================

class AyarlarSayfasi(Gtk.Box):
    def __init__(self, pencere):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.pencere = pencere
        self.ayar = pencere.ayar
        self._kayit = 0
        self.bolumler = {}
        self.kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.kaydirma = kaydirmali(self.kutu)
        self.pack_start(self.kaydirma, True, True, 0)

        # Konum
        b = self._bolum("Konum")
        self.lbl_konum = etiket(A.konum_adi(A.konum()), sar=False)
        dg = Gtk.Button(label="Değiştir…")
        dg.connect("clicked", lambda *_: pencere.konum_sec())
        self._satir(b, "Şu anki konum", self.lbl_konum, dg)

        # Bildirimler
        b = self._bolum("Bildirimler")
        self._anahtar(b, "Vakit girince bildirim göster", ("bildirim", "acik"))
        self._secim(b, "Bildirim başlığı", ("bildirim", "baslik"),
                    [("girdi", "“Öğle vakti girdi”"), ("namaz", "“Namaz vakti — Öğle”")])
        self._anahtar(b, "Bildirim kapatılana kadar ekranda kalsın", ("bildirim", "ekranda_kal"))
        self._sayi(b, "Vakitten önce hatırlat (dakika, 0 = kapalı)", ("bildirim", "once_dk"), 0, 120, 5)
        self._anahtar(b, "Güneş doğuşu için uyar (sabah namazının çıkışı)", ("bildirim", "gunes"))
        self._anahtar(b, "Dini günlerde sabah hatırlat (kandil, bayram…)", ("bildirim", "dini_gun"))
        tur = self._secim(b, "Ses", ("bildirim", "tur"),
                          [("sessiz", "Sessiz (yalnızca bildirim)"), ("kisa_ses", "Kısa bir uyarı sesi"),
                           ("ezan", "Ezan sesi")])
        ezan_dosya = Gtk.FileChooserButton(title="Ezan sesi seçin", action=Gtk.FileChooserAction.OPEN)
        filtre = Gtk.FileFilter()
        filtre.set_name("Ses dosyaları")
        filtre.add_mime_type("audio/*")
        ezan_dosya.add_filter(filtre)
        if self.ayar["bildirim"]["ezan_dosyasi"]:
            ezan_dosya.set_filename(self.ayar["bildirim"]["ezan_dosyasi"])
        ezan_dosya.connect("file-set", lambda w: self._degistir(("bildirim", "ezan_dosyasi"), w.get_filename() or ""))
        ezan_satiri = self._satir(b, "Ezan ses dosyası", ezan_dosya)
        imsak_satiri = self._anahtar(b, "İmsak vaktinde de ezan çal", ("bildirim", "imsakta_ezan"))

        def ezan_gorunurlugu(*_):
            ezan = tur.get_active_id() == "ezan"
            ezan_satiri.set_sensitive(ezan)
            imsak_satiri.set_sensitive(ezan)
        tur.connect("changed", ezan_gorunurlugu)
        ezan_gorunurlugu()

        dene = Gtk.Box(spacing=8)
        for metin, is_ in (("Bildirimi dene", self._bildirim_dene), ("Sesi dene", self._ses_dene),
                           ("Sesi durdur", lambda *_: self._sustur())):
            d = Gtk.Button(label=metin)
            d.connect("clicked", is_)
            dene.pack_start(d, False, False, 0)
        b.pack_start(dene, False, False, 0)
        self.lbl_servis = etiket("", "soluk")
        b.pack_start(self.lbl_servis, False, False, 0)

        # Masaüstü widget'ları
        b = self._bolum("Masaüstü widget'ları", "widget")
        b.pack_start(etiket("Birden fazla widget ekleyebilir, her birinde hangi bölümlerin görüneceğini seçebilirsiniz. "
                            "Genişlik 0 iken widget metnin uzunluğuna göre kendini boyutlandırır. "
                            "Widget'a sağ tıklayıp “Yapılandır…” deyince bu sayfa o widget açık olarak gelir.",
                            "soluk"), False, False, 0)
        self._sayi(b, "Arka plan opaklığı (%)", ("widget_ortak", "opaklik"), 0, 100, 5)
        self._renk(b, "Yazı rengi", ("widget_ortak", "yazi_rengi"))
        self._renk(b, "Vurgu rengi (geri sayım, sıradaki vakit)", ("widget_ortak", "vurgu_rengi"))
        self.widget_kutusu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=6)
        b.pack_start(self.widget_kutusu, False, False, 0)
        self.yeni_tur = Gtk.ComboBoxText()
        for tur, (ad, _) in A.WIDGET_HAZIR.items():
            self.yeni_tur.append(tur, ad)
        self.yeni_tur.set_active_id("vakitler")
        ekle = Gtk.Button(label="Widget ekle")
        ekle.connect("clicked", self._widget_ekle)
        self._satir(b, "Yeni widget", self.yeni_tur, ekle)
        self.acik_widget = None
        self._cizilen_widgetlar = None

        # Panel
        b = self._bolum("Panel göstergesi", "panel")
        self.panel_dugme = Gtk.Button()
        self.panel_dugme.connect("clicked", self._panel_ac_kapa)
        self._satir(b, "Alt panelde göster", self.panel_dugme)
        self._secim(b, "Gösterim", ("panel", "gosterim"),
                    [("saat", "Öğle 12:41"), ("kalan", "Öğle'ye 1:23"), ("ikisi", "Öğle 12:41 · 1:23")])
        self._sayi(b, "Vakte kaç dakika kala renk değişsin", ("panel", "uyari_dk"), 0, 120, 5)
        self._renk(b, "Uyarı rengi", ("panel", "uyari_rengi"))

        # Günün resmi
        b = self._bolum("Günün resmi", "resim")
        kaynak = self._secim(b, "Kaynak", ("resim", "kaynak"),
                             [("wikimedia", "Wikimedia Commons (seçilmiş liste)"), ("klasor", "Kendi klasörüm"),
                              ("kapali", "Kapalı")])
        klasor = Gtk.FileChooserButton(title="Resim klasörü seçin", action=Gtk.FileChooserAction.SELECT_FOLDER)
        if self.ayar["resim"]["klasor"]:
            klasor.set_filename(self.ayar["resim"]["klasor"])
        klasor.connect("file-set", lambda w: self._degistir(("resim", "klasor"), w.get_filename() or ""))
        klasor_satiri = self._satir(b, "Resim klasörü", klasor)
        kaynak.connect("changed", lambda c: klasor_satiri.set_sensitive(c.get_active_id() == "klasor"))
        klasor_satiri.set_sensitive(kaynak.get_active_id() == "klasor")
        self.lbl_wallqueue = etiket("", "soluk")
        b.pack_start(self.lbl_wallqueue, False, False, 0)
        self.durumu_guncelle()

    def yenile(self):
        self.durumu_guncelle()

    def tik(self):
        self._tik_sayaci = getattr(self, "_tik_sayaci", 0) + 1
        if self._tik_sayaci % 3 == 0:
            self._widgetlari_ciz()

    # -- satır yardımcıları --
    def _bolum(self, baslik, ad=None):
        k = kart()
        k.pack_start(etiket(baslik, "ayar-bolum"), False, False, 0)
        self.kutu.pack_start(k, False, False, 0)
        if ad:
            self.bolumler[ad] = k
        return k

    def _satir(self, bolum, metin, *widgetlar):
        s = Gtk.Box(spacing=12)
        s.pack_start(etiket(metin, xalign=0), True, True, 0)
        for w in widgetlar:
            w.set_valign(Gtk.Align.CENTER)
            s.pack_start(w, False, False, 0)
        bolum.pack_start(s, False, False, 0)
        return s

    def _al(self, yol):
        if yol[0] == "widgetlar":  # widget'a özel değer yoksa varsayılanı göster
            d = A.widget_ayari(self.ayar, yol[1])
            yol = yol[2:]
        else:
            d = self.ayar
        for k in yol:
            d = d[k]
        return d

    def _degistir(self, yol, deger):
        d = self.ayar
        for k in yol[:-1]:
            d = d.setdefault(k, {})
        d[yol[-1]] = deger
        if self._kayit:
            GLib.source_remove(self._kayit)
        self._kayit = GLib.timeout_add(300, self._kaydet)

    def _kaydet(self):
        self._kayit = 0
        A.kaydet(self.ayar)
        self.pencere.ayarlar_degisti()
        return False

    def _anahtar(self, b, metin, yol):
        sw = Gtk.Switch(active=bool(self._al(yol)))
        sw.connect("notify::active", lambda w, _p: self._degistir(yol, w.get_active()))
        return self._satir(b, metin, sw)

    def _sayi(self, b, metin, yol, en_az, en_cok, adim):
        sp = Gtk.SpinButton.new_with_range(en_az, en_cok, adim)
        sp.set_value(self._al(yol))
        sp.connect("value-changed", lambda w: self._degistir(yol, int(w.get_value())))
        return self._satir(b, metin, sp)

    def _secim(self, b, metin, yol, secenekler):
        c = Gtk.ComboBoxText()
        for k, ad in secenekler:
            c.append(k, ad)
        c.set_active_id(self._al(yol))
        c.connect("changed", lambda w: self._degistir(yol, w.get_active_id()))
        self._satir(b, metin, c)
        return c

    def _renk(self, b, metin, yol):
        cb = Gtk.ColorButton.new_with_rgba(rgba(self._al(yol)))
        cb.connect("color-set", lambda w: self._degistir(yol, w.get_rgba().to_string()))
        return self._satir(b, metin, cb)

    # -- eylemler --
    def durumu_guncelle(self):
        self.lbl_konum.set_text(A.konum_adi(A.konum()))
        self.panel_dugme.set_label("Kaldır" if cinnamon.panel_ekli() else "Panele ekle")
        self._widgetlari_ciz()
        self.lbl_wallqueue.set_text(
            "Duvar kâğıdını Wallqueue yönetiyor. İslami resimler Wallqueue'da “İslami resimler (Ezan Vakti)” "
            "kaynağıyla sıraya girer; Ramazan'da ve dini günlerde öne alınır." if wallqueue_yolu() else
            "Wallqueue kurulu değil; günün resmini Bugün sayfasından elle duvar kâğıdı yapabilirsiniz.")
        from .servis import calisiyor_mu
        calisiyor = calisiyor_mu()
        self.lbl_servis.set_text("Bildirim servisi çalışıyor." if calisiyor else
                                 "Bildirim servisi çalışmıyor! Oturumu kapatıp açın ya da `ezan-vakti servis` çalıştırın.")

    def _widgetlari_ciz(self, zorla=False):
        liste = cinnamon.widget_listesi()
        if not zorla and liste == self._cizilen_widgetlar:
            return
        self._cizilen_widgetlar = liste
        for c in self.widget_kutusu.get_children():
            self.widget_kutusu.remove(c)
            c.destroy()
        if not liste:
            self.widget_kutusu.pack_start(etiket("Masaüstünde Ezan Vakti widget'ı yok.", "soluk"), False, False, 0)
        for sira, kimlik in enumerate(liste, start=1):
            w = A.widget_ayari(self.ayar, kimlik)
            acik = [ad for k, ad in A.WIDGET_BOLUMLERI if w["bolumler"].get(k)]
            ex = Gtk.Expander(label=f"Widget {sira} — " + (", ".join(acik) if acik else "boş"))
            ex.set_expanded(kimlik == self.acik_widget)
            ic = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=18, margin_top=6)
            for k, ad in A.WIDGET_BOLUMLERI:
                self._anahtar(ic, ad, ("widgetlar", kimlik, "bolumler", k))
            self._anahtar(ic, "Ayet ve hadiste Arapça metni göster", ("widgetlar", kimlik, "arapca"))
            self._sayi(ic, "Boyut (%)", ("widgetlar", kimlik, "boyut"), 60, 250, 5)
            self._sayi(ic, "Genişlik (px; 0 = metne göre otomatik)", ("widgetlar", kimlik, "genislik"), 0, 800, 10)
            kaldir = Gtk.Button(label="Bu widget'ı kaldır", halign=Gtk.Align.START)
            kaldir.get_style_context().add_class("destructive-action")
            kaldir.connect("clicked", lambda _b, k=kimlik: self._widget_kaldir(k))
            ic.pack_start(kaldir, False, False, 0)
            ex.add(ic)
            self.widget_kutusu.pack_start(ex, False, False, 0)
        self.widget_kutusu.show_all()

    def _widget_ekle(self, *_):
        tur = self.yeni_tur.get_active_id() or "vakitler"
        kimlik = cinnamon.widget_ekle()
        self.ayar.setdefault("widgetlar", {})[kimlik] = A.widget_hazir_ayar(tur)
        A.kaydet(self.ayar)
        self.acik_widget = kimlik
        GLib.timeout_add(500, lambda: (self._widgetlari_ciz(zorla=True), False)[1])

    def _widget_kaldir(self, kimlik):
        cinnamon.widget_kaldir(kimlik)
        self.ayar.get("widgetlar", {}).pop(kimlik, None)
        A.kaydet(self.ayar)
        GLib.timeout_add(500, lambda: (self._widgetlari_ciz(zorla=True), False)[1])

    def goster(self, bolum=None, widget=None):
        """Ayarlar sayfasında bir bölüme (ya da belirli bir widget'ın ayarına) kaydırır."""
        if widget is not None:
            self.acik_widget = str(widget)
            self._widgetlari_ciz(zorla=True)
            bolum = "widget"
        hedef = self.bolumler.get(bolum)
        if not hedef:
            return

        deneme = [0]

        def kaydir():
            # Pencere yeni açıldıysa düzen henüz hesaplanmamış olabilir: hazır olana kadar tekrar dene
            deneme[0] += 1
            konum = hedef.translate_coordinates(self.kutu, 0, 0)  # (x, y) ya da başarısızsa None
            y = konum[-1] if konum else 0
            adj = self.kaydirma.get_vadjustment()
            if y > 0 and adj.get_upper() > adj.get_page_size():
                adj.set_value(min(max(0, y - 8), adj.get_upper() - adj.get_page_size()))
                return False
            return deneme[0] < 30
        GLib.timeout_add(100, kaydir)

    def _panel_ac_kapa(self, *_):
        (cinnamon.panel_kaldir if cinnamon.panel_ekli() else cinnamon.panel_ekle)()
        GLib.timeout_add(500, lambda: (self.durumu_guncelle(), False)[1])

    def _bildirim_dene(self, *_):
        from .servis import Bildirici, vakit_basligi
        if not hasattr(self, "_bildirici"):
            self._bildirici = Bildirici()
        self._bildirici.gonder(vakit_basligi(V.VAKIT["ogle"], self.ayar), "Bu bir deneme bildirimidir.",
                               kalici=self.ayar["bildirim"]["ekranda_kal"],
                               sustur_dugmesi=self.ayar["bildirim"]["tur"] == "ezan")

    def _ses_dene(self, *_):
        from .servis import ses_cal
        b = self.ayar["bildirim"]
        if b["tur"] == "sessiz":
            return
        ses_cal(b["ezan_dosyasi"] if b["tur"] == "ezan" else A.VARSAYILAN_SES)

    def _sustur(self):
        from .servis import ses_sustur
        ses_sustur()


# ======================= Hakkında =======================

class HakkindaSayfasi(Gtk.Box):
    def __init__(self, pencere):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.pencere = pencere
        self.kutu = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.pack_start(kaydirmali(self.kutu), True, True, 0)

        ust = kart()
        satir = Gtk.Box(spacing=16)
        try:
            satir.pack_start(Gtk.Image.new_from_pixbuf(
                GdkPixbuf.Pixbuf.new_from_file_at_size(A.SIMGE, 64, 64)), False, False, 0)
        except GLib.Error:
            pass
        satir.pack_start(etiket(
            f"<span size='x-large' weight='bold'>Ezan Vakti {__version__}</span>\n"
            "Linux Mint Cinnamon için namaz vakitleri, dini günler ve günün içeriği: "
            "uygulama, bildirim servisi, masaüstü widget'ları ve panel göstergesi.", markup=True), True, True, 0)
        ust.pack_start(satir, False, False, 0)
        self.kutu.pack_start(ust, False, False, 0)

        self.icerik = kart("İçerik")
        self.kutu.pack_start(self.icerik, False, False, 0)

        k = kart("Kaynaklar ve lisanslar")
        for metin in (
            "<b>Namaz vakitleri:</b> T.C. Diyanet İşleri Başkanlığı; resmî olmayan "
            "<a href='https://ezanvakti.emushaf.net'>ezanvakti.emushaf.net</a> API'si üzerinden.",
            "<b>Dini günler ve hicrî takvim:</b> Diyanet'in yıllık "
            "<a href='https://vakithesaplama.diyanet.gov.tr/dini_gunler.php'>Dini Günler Listesi</a>.",
            "<b>Ayetler:</b> Arapça metin <a href='https://tanzil.net'>Tanzil Projesi</a> (Medine Mushafı); "
            "meal Türkiye Diyanet Vakfı (Tanzil üzerinden, ticari olmayan kullanım şartıyla).",
            "<b>Hadisler ve vecizeler:</b> Risale-i Nur Külliyatı; metinler kaynak adresleriyle, harfi harfine. "
            "Hadislerin kaynak notları yayıncınındır; sıhhat değerlendirmesi yapılmamıştır.",
            "<b>Resimler:</b> <a href='https://commons.wikimedia.org'>Wikimedia Commons</a>; "
            "her resmin yazarı ve lisansı Bugün sayfasında gösterilir.",
        ):
            k.pack_start(etiket(metin, markup=True), False, False, 0)
        self.kutu.pack_start(k, False, False, 0)

        self.durum = kart("Durum")
        self.kutu.pack_start(self.durum, False, False, 0)

        k = kart("Dosyalar")
        for ad, yol in (("Ayarlar", A.AYAR_DIZINI), ("Önbellek ve servis kaydı", A.ONBELLEK_DIZINI),
                        ("Program", A.PROJE_DIZINI)):
            ac = Gtk.Button(label="Aç")
            ac.connect("clicked", lambda _b, y=yol: Gio.AppInfo.launch_default_for_uri(GLib.filename_to_uri(y), None))
            s = Gtk.Box(spacing=12)
            s.pack_start(etiket(f"<b>{ad}</b>\n<small>{html.escape(yol)}</small>", markup=True, secilebilir=True),
                         True, True, 0)
            ac.set_valign(Gtk.Align.CENTER)
            s.pack_start(ac, False, False, 0)
            k.pack_start(s, False, False, 0)
        self.kutu.pack_start(k, False, False, 0)

    def _doldur(self, k, satirlar):
        for c in k.get_children()[1:]:
            k.remove(c)
            c.destroy()
        for metin in satirlar:
            k.pack_start(etiket(metin, markup=True), False, False, 0)
        k.show_all()

    def yenile(self):
        from .servis import calisiyor_mu
        sayilar = [(len(icerik._liste(d, a)[0]), ad) for d, a, ad in (
            ("ayetler.json", "ayetler", "ayet"), ("hadisler.json", "hadisler", "hadis"),
            ("vecizeler.json", "vecizeler", "vecize"))]
        yillar = takvim.yillar()
        self._doldur(self.icerik, [
            " · ".join(f"<b>{n}</b> {ad}" for n, ad in sayilar) + f" · <b>{len(resim.wikimedia_listesi())}</b> resim",
            f"Dini günler: {yillar[0]}–{yillar[-1]}" if yillar else "Dini günler listesi yok.",
            "Her gün listeden sıradaki içerik seçilir; uygulama ve widget'lar aynı içeriği gösterir.",
        ])
        evet = lambda x: "✓" if x else "✗"  # noqa: E731
        self._doldur(self.durum, [
            f"{evet(calisiyor_mu())} Bildirim servisi " + ("çalışıyor" if calisiyor_mu() else "çalışmıyor"),
            f"Konum: {html.escape(A.konum_adi(A.konum()))}",
            f"Masaüstü widget'ı: {len(cinnamon.widget_listesi())} · Panel göstergesi: "
            + ("ekli" if cinnamon.panel_ekli() else "yok"),
            f"{evet(wallqueue_yolu())} Wallqueue " + ("kurulu; duvar kâğıdını o yönetiyor"
                                                      if wallqueue_yolu() else "kurulu değil"),
        ])

    def tik(self):
        pass


# ======================= Pencere =======================

class Pencere(Gtk.ApplicationWindow):
    def __init__(self, uygulama):
        super().__init__(application=uygulama, title="Ezan Vakti")
        self.set_default_size(880, 780)
        self.ayar = A.yukle()
        self.gunler = {}
        self.indiriliyor = False
        self._gunleri_oku()

        hb = Gtk.HeaderBar(show_close_button=True)
        self.set_titlebar(hb)
        self.yigin = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        hb.set_custom_title(Gtk.StackSwitcher(stack=self.yigin))

        self.sayfalar = {
            "bugun": (BugunSayfasi(self), "Bugün"),
            "hafta": (HaftaSayfasi(self), "Bu Hafta"),
            "dini": (DiniGunlerSayfasi(self), "Dini Günler"),
            "ayarlar": (AyarlarSayfasi(self), "Ayarlar"),
            "hakkinda": (HakkindaSayfasi(self), "Hakkında"),
        }
        for ad, (sayfa, baslik) in self.sayfalar.items():
            self.yigin.add_titled(sayfa, ad, baslik)
        self.add(self.yigin)
        self.yigin.connect("notify::visible-child", lambda *_: self.tik())

        self._izleyiciler = []
        for dizin in (A.AYAR_DIZINI, A.ONBELLEK_DIZINI):
            os.makedirs(dizin, exist_ok=True)
            m = Gio.File.new_for_path(dizin).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
            m.connect("changed", self._dosya_degisti)
            self._izleyiciler.append(m)
        self._yenile_zamanlayici = 0

        self.show_all()
        for s, _ in self.sayfalar.values():
            s.yenile()
        GLib.timeout_add_seconds(1, self.tik)
        self.vakitleri_indir()

    def _gunleri_oku(self):
        k = A.konum()
        self.gunler = V.gunleri_oku(k["ilceId"]) if k else {}

    def tik(self):
        sayfa = self.yigin.get_visible_child()
        if sayfa is not None:
            sayfa.tik()
        return True

    def _dosya_degisti(self, _m, dosya, diger, _olay):
        adlar = {f.get_basename() for f in (dosya, diger) if f}
        if not adlar & {"konum.json"} and not any(a.startswith("vakitler-") and a.endswith(".json") for a in adlar):
            return
        if self._yenile_zamanlayici:
            GLib.source_remove(self._yenile_zamanlayici)
        self._yenile_zamanlayici = GLib.timeout_add(400, self._her_seyi_yenile)

    def _her_seyi_yenile(self):
        self._yenile_zamanlayici = 0
        self._gunleri_oku()
        for s, _ in self.sayfalar.values():
            s.yenile()
        self.sayfalar["ayarlar"][0].durumu_guncelle()
        return False

    def vakitleri_indir(self, zorla=False):
        if self.indiriliyor or not A.konum():
            return
        self.indiriliyor = True

        def is_():
            try:
                V.guncelle(zorla=zorla)
            except Exception as e:  # noqa: BLE001
                print("Vakitler indirilemedi:", e, file=sys.stderr)
            GLib.idle_add(bitti)

        def bitti():
            self.indiriliyor = False
            self._her_seyi_yenile()
            return False
        threading.Thread(target=is_, daemon=True).start()

    def konum_sec(self):
        from .konum_secici import KonumSecici
        if KonumSecici(self).sec():
            self._gunleri_oku()
            self.vakitleri_indir(zorla=True)
            self._her_seyi_yenile()

    def ayarlar_degisti(self):
        # Resim kaynağı değişmiş olabilir
        self.sayfalar["bugun"][0].resim_anahtari = None
        self.sayfalar["bugun"][0].icerik_gunu = None

    def sayfa_ac(self, ad, widget=None, bolum=None):
        if ad in self.sayfalar:
            self.yigin.set_visible_child_name(ad)
            self.sayfalar[ad][0].yenile()
        if ad == "ayarlar" and (widget is not None or bolum):
            self.sayfalar["ayarlar"][0].goster(bolum=bolum, widget=widget)


class Uygulama(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=UYGULAMA_KIMLIGI, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.pencere = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        saglayici = Gtk.CssProvider()
        saglayici.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), saglayici,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Gtk.Window.set_default_icon_from_file(A.SIMGE) if os.path.exists(A.SIMGE) else None

    def do_command_line(self, komut_satiri):
        argv = komut_satiri.get_arguments()[1:]
        if self.pencere is None:
            self.pencere = Pencere(self)
        def secenek(ad):
            return argv[argv.index(ad) + 1] if ad in argv and argv.index(ad) + 1 < len(argv) else None
        if secenek("--sayfa"):
            self.pencere.sayfa_ac(secenek("--sayfa"), widget=secenek("--widget"), bolum=secenek("--bolum"))
        self.pencere.present()
        return 0


def main(argv=None):
    GLib.set_prgname("ezan-vakti")
    GLib.set_application_name("Ezan Vakti")
    return Uygulama().run(["ezan-vakti"] + list(argv or []))
