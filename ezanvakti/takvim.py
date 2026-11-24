"""Dini günler ve hicrî tarih (Diyanet'in yayımladığı listelere göre)."""

import bisect
import datetime as dt
import os

from . import ayarlar as A

HICRI_AYLAR = ["Muharrem", "Safer", "Rebîülevvel", "Rebîülâhir", "Cemâziyelevvel", "Cemâziyelâhir",
               "Recep", "Şaban", "Ramazan", "Şevval", "Zilkade", "Zilhicce"]
MILADI_AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
                "Eylül", "Ekim", "Kasım", "Aralık"]
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
KANDILLER = {"Regaib Kandili", "Miraç Kandili", "Berat Kandili", "Mevlid Kandili", "Kadir Gecesi"}
ONEMLI = ("Ramazan Başlangıcı", "Ramazan Bayramı (1. gün)", "Kurban Bayramı (1. gün)")

_veri = None


def _yukle():
    global _veri
    if _veri is None:
        ham = A.json_oku(os.path.join(A.VERI_DIZINI, "dini_gunler.json"), {}) or {}
        gunler = []
        for g in ham.get("gunler", []):
            gunler.append({**g, "tarih": dt.date.fromisoformat(g["tarih"])})
        baslar = [(dt.date.fromisoformat(b["tarih"]), b["yil"], b["ay"]) for b in ham.get("hicri_ay_baslari", [])]
        _veri = {"gunler": gunler, "baslar": baslar, "kaynak": ham.get("kaynak", "")}
    return _veri


def kaynak():
    return _yukle()["kaynak"]


def hicri(tarih):
    """(yıl, ay, gün) ya da veri kapsamı dışındaysa None."""
    baslar = _yukle()["baslar"]
    if not baslar:
        return None
    i = bisect.bisect_right([b[0] for b in baslar], tarih) - 1
    if i < 0:
        return None
    t0, yil, ay = baslar[i]
    gun = (tarih - t0).days + 1
    if gun > 30 or (i == len(baslar) - 1 and gun > 29):
        return None
    return yil, ay, gun


def hicri_yaz(tarih):
    h = hicri(tarih)
    return f"{h[2]} {HICRI_AYLAR[h[1] - 1]} {h[0]}" if h else ""


def miladi_yaz(tarih, gun_adi=True):
    s = f"{tarih.day} {MILADI_AYLAR[tarih.month - 1]} {tarih.year}"
    return f"{s} {GUNLER[tarih.weekday()]}" if gun_adi else s


def dini_gunler(yil=None):
    g = _yukle()["gunler"]
    return [x for x in g if yil is None or x["tarih"].year == yil]


def yillar():
    return sorted({x["tarih"].year for x in _yukle()["gunler"]})


def o_gun(tarih):
    return [x for x in _yukle()["gunler"] if x["tarih"] == tarih]


def yaklasan(bugun=None, adet=1, yalniz=None):
    bugun = bugun or dt.date.today()
    sonuc = [x for x in _yukle()["gunler"] if x["tarih"] >= bugun and (yalniz is None or x["ad"] in yalniz)]
    return sonuc[:adet]


def kandil_mi(ad):
    return ad in KANDILLER
