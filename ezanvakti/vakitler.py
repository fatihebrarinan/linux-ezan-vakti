"""Diyanet namaz vakitleri: indirme, önbellek ve "şu an hangi vakit" hesapları."""

import datetime as dt
import json
import os
import urllib.request

from . import ayarlar as A

API = "https://ezanvakti.emushaf.net"
YENILEME_ESIGI_GUN = 7


class Vakit:
    def __init__(self, id, ad, yonelme, api, namaz):
        self.id, self.ad, self.yonelme, self.api, self.namaz = id, ad, yonelme, api, namaz


VAKITLER = [
    Vakit("imsak", "İmsak", "İmsak'a", "Imsak", "Sabah"),
    Vakit("gunes", "Güneş", "Güneş'e", "Gunes", None),
    Vakit("ogle", "Öğle", "Öğle'ye", "Ogle", "Öğle"),
    Vakit("ikindi", "İkindi", "İkindi'ye", "Ikindi", "İkindi"),
    Vakit("aksam", "Akşam", "Akşam'a", "Aksam", "Akşam"),
    Vakit("yatsi", "Yatsı", "Yatsı'ya", "Yatsi", "Yatsı"),
]
VAKIT = {v.id: v for v in VAKITLER}


def api_get(yol, zaman_asimi=30):
    req = urllib.request.Request(API + yol, headers={"User-Agent": "ezan-vakti-desktop"})
    with urllib.request.urlopen(req, timeout=zaman_asimi) as r:
        return json.loads(r.read().decode("utf-8"))


def onbellek_yolu(ilce_id):
    return os.path.join(A.ONBELLEK_DIZINI, f"vakitler-{ilce_id}.json")


class Gun:
    def __init__(self, ham):
        g, a, y = (int(x) for x in ham["MiladiTarihKisa"].split("."))
        self.tarih = dt.date(y, a, g)
        self.miladi = ham.get("MiladiTarihUzun", "")
        self.hicri = ham.get("HicriTarihUzun", "")
        self.saatler = {v.id: ham[v.api] for v in VAKITLER}

    def an(self, vakit_id):
        s, d = (int(x) for x in self.saatler[vakit_id].split(":"))
        return dt.datetime.combine(self.tarih, dt.time(s, d))


def gunleri_oku(ilce_id):
    ham = A.json_oku(onbellek_yolu(ilce_id), [])
    gunler = {}
    for h in ham if isinstance(ham, list) else []:
        try:
            g = Gun(h)
            gunler[g.tarih] = g
        except (KeyError, ValueError):
            pass
    return gunler


def indir(ilce_id):
    veri = api_get(f"/vakitler/{ilce_id}")
    if not isinstance(veri, list) or not veri:
        raise ValueError("boş yanıt")
    Gun(veri[0])  # biçim denetimi
    A.json_yaz(onbellek_yolu(ilce_id), veri)
    return len(veri)


def guncelleme_gerekli(ilce_id, bugun=None):
    bugun = bugun or dt.date.today()
    gunler = gunleri_oku(ilce_id)
    if bugun not in gunler:
        return True
    kalan = sum(1 for t in gunler if t >= bugun)
    return kalan < YENILEME_ESIGI_GUN


def guncelle(zorla=False):
    """Gerekirse vakitleri indirir. Dönüş: indirilen gün sayısı veya 0."""
    k = A.konum()
    if not k:
        return 0
    if zorla or guncelleme_gerekli(k["ilceId"]):
        return indir(k["ilceId"])
    return 0


class Durum:
    """Belirli bir anda bugünün vakitleri, şu anki ve sıradaki vakit."""

    def __init__(self, gunler, simdi=None):
        self.simdi = simdi or dt.datetime.now()
        bugun = self.simdi.date()
        self.bugun = gunler.get(bugun)
        self.yarin = gunler.get(bugun + dt.timedelta(days=1))
        self.simdiki = "yatsi"
        self.siradaki = None      # (Vakit, datetime)
        if not self.bugun:
            return
        for v in VAKITLER:
            an = self.bugun.an(v.id)
            if an <= self.simdi:
                self.simdiki = v.id
            elif self.siradaki is None:
                self.siradaki = (v, an)
        if self.siradaki is None and self.yarin:
            self.siradaki = (VAKITLER[0], self.yarin.an("imsak"))

    @property
    def kalan(self):
        return self.siradaki[1] - self.simdi if self.siradaki else None


def sure_yaz(td, saniye=True):
    s = max(0, int(td.total_seconds()))
    if saniye:
        return f"{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d}"
    return f"{s // 3600}:{s // 60 % 60:02d}"
