"""Dosya yolları ve ortak ayarlar (~/.config/ezan-vakti/ayarlar.json).

Uygulama ayarları yazar; servis, masaüstü widget'ı ve panel göstergesi bu dosyayı izler.
"""

import copy
import json
import os
import tempfile

from gi.repository import GLib

PROJE_DIZINI = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI_DIZINI = os.path.join(PROJE_DIZINI, "data")
AYAR_DIZINI = os.path.join(GLib.get_user_config_dir(), "ezan-vakti")
ONBELLEK_DIZINI = os.path.join(GLib.get_user_cache_dir(), "ezan-vakti")
AYARLAR_DOSYASI = os.path.join(AYAR_DIZINI, "ayarlar.json")
KONUM_DOSYASI = os.path.join(AYAR_DIZINI, "konum.json")
SES_PID_DOSYASI = os.path.join(ONBELLEK_DIZINI, "ses.pid")
BUGUN_DOSYASI = os.path.join(ONBELLEK_DIZINI, "bugun.json")
SIMGE = os.path.join(PROJE_DIZINI, "ezan-vakti@fatih", "icon.png")
CLI = os.path.join(PROJE_DIZINI, "bin", "ezan-vakti")
VARSAYILAN_SES = "/usr/share/sounds/freedesktop/stereo/complete.oga"
# Wallqueue gibi başka uygulamaların okuyabilmesi için resim listesinin yayımlandığı yer
DISA_ACIK_DIZIN = os.path.join(GLib.get_user_data_dir(), "ezan-vakti")

# Varsayılanların tek kaynağı: data/varsayilan-ayarlar.json (widget ve panel de aynı dosyayı okur).
#  bildirim.tur: sessiz | kisa_ses | ezan      bildirim.baslik: girdi | namaz
#  panel.gosterim: saat | kalan | ikisi        resim.kaynak: wikimedia | klasor | kapali
#  widget_varsayilan: her widget'ın başlangıç ayarı; widgetlar["<cinnamon kimliği>"]: o widget'a özel farklar
with open(os.path.join(VERI_DIZINI, "varsayilan-ayarlar.json"), encoding="utf-8") as _f:
    VARSAYILAN = json.load(_f)

WIDGET_BOLUMLERI = [
    ("baslik", "Konum ve tarih"), ("hicri", "Hicrî tarih"), ("dini_gun", "Sıradaki dini gün"),
    ("sayac", "Geri sayım"), ("vakitler", "Namaz vakitleri"),
    ("ayet", "Günün ayeti"), ("hadis", "Günün hadisi"), ("vecize", "Günün vecizesi"),
]
WIDGET_HAZIR = {
    "vakitler": ("Namaz vakitleri", {"baslik", "hicri", "dini_gun", "sayac", "vakitler"}),
    "ayet": ("Günün ayeti", {"ayet"}),
    "hadis": ("Günün hadisi", {"hadis"}),
    "vecize": ("Günün vecizesi", {"vecize"}),
    "icerik": ("Ayet, hadis ve vecize", {"ayet", "hadis", "vecize"}),
}


def _birlestir(taban, ust):
    sonuc = copy.deepcopy(taban)
    for k, v in (ust or {}).items():
        if isinstance(v, dict) and isinstance(sonuc.get(k), dict):
            sonuc[k] = _birlestir(sonuc[k], v)
        else:
            sonuc[k] = v
    return sonuc


def json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def json_yaz(yol, veri):
    dizin = os.path.dirname(yol)
    os.makedirs(dizin, exist_ok=True)
    # Her yazım kendi geçici dosyasını kullanır (iş parçacıkları çakışmasın)
    fd, gecici = tempfile.mkstemp(dir=dizin, prefix=".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=2)
        os.replace(gecici, yol)
    except BaseException:
        if os.path.exists(gecici):
            os.remove(gecici)
        raise


def _eski_ayarlari_tasi(ham):
    """Sürüm 2.0'daki tek "widget" bölümünü yeni yapıya çevirir. Değişiklik yaptıysa True."""
    eski = ham.pop("widget", None)
    degisti = eski is not None
    if eski:
        ortak = ham.setdefault("widget_ortak", {})
        for k in ("opaklik", "yazi_rengi", "vurgu_rengi"):
            if k in eski:
                ortak.setdefault(k, eski[k])
        ilk = ham.setdefault("widgetlar", {}).setdefault("0", {})
        for k in ("boyut",):
            if k in eski:
                ilk.setdefault(k, eski[k])
        if "hicri" in eski:
            ilk.setdefault("bolumler", {})["hicri"] = eski["hicri"]
    if "resim" in ham and "duvar_kagidi" in ham["resim"]:
        ham["resim"].pop("duvar_kagidi")  # duvar kâğıdını artık Wallqueue yönetiyor
        degisti = True
    return degisti


def yukle():
    ham = json_oku(AYARLAR_DOSYASI, {}) or {}
    if _eski_ayarlari_tasi(ham):
        json_yaz(AYARLAR_DOSYASI, ham)
    return _birlestir(VARSAYILAN, ham)


def widget_ayari(ayarlar, kimlik):
    """Bir widget'ın tam ayarı: varsayılan + o widget'a özel farklar."""
    return _birlestir(ayarlar["widget_varsayilan"], ayarlar["widgetlar"].get(str(kimlik), {}))


def widget_hazir_ayar(tur):
    """Hazır türden (vakitler, ayet, …) yeni bir widget ayarı."""
    _, acik = WIDGET_HAZIR[tur]
    return {"bolumler": {k: k in acik for k, _ in WIDGET_BOLUMLERI}}


def kaydet(ayarlar):
    json_yaz(AYARLAR_DOSYASI, ayarlar)


def konum():
    k = json_oku(KONUM_DOSYASI)
    return k if k and k.get("ilceId") else None


def konum_kaydet(k):
    json_yaz(KONUM_DOSYASI, k)


def baslik_harfi(s):
    """'İSTANBUL / ARNAVUTKÖY' → 'İstanbul / Arnavutköy' (Türkçe büyük/küçük harf kurallarıyla)."""
    s = (s or "").replace("I", "ı").replace("İ", "i").lower()
    out, bas = [], True
    for ch in s:
        if bas and ch.isalpha():
            ch = "İ" if ch == "i" else ("I" if ch == "ı" else ch.upper())
            bas = False
        elif not ch.isalpha():
            bas = ch in " /-("
        out.append(ch)
    return "".join(out)


def konum_adi(k):
    if not k:
        return "Konum seçilmedi"
    sehir, ilce = k.get("sehir") or "", k.get("ilce") or ""
    ad = f"{sehir} / {ilce}" if ilce and ilce != sehir else (sehir or ilce)
    return baslik_harfi(ad)
