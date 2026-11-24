"""Günün İslami resmi: Wikimedia Commons listesinden ya da kullanıcının klasöründen."""

import datetime as dt
import glob
import hashlib
import os
import shutil
import subprocess
import urllib.request

from gi.repository import GLib

from . import ayarlar as A

RESIM_ONBELLEK = os.path.join(A.ONBELLEK_DIZINI, "resimler")
DUVAR_DIZINI = os.path.join(GLib.get_user_data_dir(), "ezan-vakti")
UZANTILAR = (".jpg", ".jpeg", ".png", ".webp")
USER_AGENT = "EzanVaktiDesktop/1.0 (personal open-source desktop app)"
SAKLANACAK = 10

_liste = (None, [])


def wikimedia_listesi():
    global _liste
    yol = os.path.join(A.VERI_DIZINI, "resimler.json")
    try:
        mtime = os.path.getmtime(yol)
    except OSError:
        mtime = None
    if _liste[0] != mtime or mtime is None:
        veri = A.json_oku(yol, {}) or {}
        _liste = (mtime, veri.get("resimler", []))
    return _liste[1]


def _sira(tarih, n):
    return (tarih.toordinal() * 31 + 7) % n


def gunun_resmi(ayarlar=None, tarih=None):
    """{'yol': yerel dosya ya da None, 'bilgi': Wikimedia girdisi ya da None} veya kapalıysa None."""
    ayarlar = ayarlar or A.yukle()
    tarih = tarih or dt.date.today()
    r = ayarlar["resim"]
    if r["kaynak"] == "kapali":
        return None
    if r["kaynak"] == "klasor":
        klasor = os.path.expanduser(r.get("klasor") or "")
        dosyalar = sorted(f for f in glob.glob(os.path.join(klasor, "**", "*"), recursive=True)
                          if f.lower().endswith(UZANTILAR)) if klasor else []
        if not dosyalar:
            return {"yol": None, "bilgi": None, "hata": "Klasörde resim bulunamadı."}
        return {"yol": dosyalar[_sira(tarih, len(dosyalar))], "bilgi": None}
    liste = wikimedia_listesi()
    if not liste:
        return {"yol": None, "bilgi": None, "hata": "Resim listesi yok."}
    bilgi = liste[_sira(tarih, len(liste))]
    yol = _onbellek_yolu(bilgi)
    return {"yol": yol if os.path.exists(yol) else None, "bilgi": bilgi}


def _onbellek_yolu(bilgi):
    ad = hashlib.sha1(bilgi["dosya"].encode()).hexdigest()[:16]
    uzanti = os.path.splitext(bilgi["thumb_url"])[1].lower() or ".jpg"
    return os.path.join(RESIM_ONBELLEK, ad + uzanti)


def indir(bilgi):
    """Resmi önbelleğe indirir (bloklayan çağrı; iş parçacığında çalıştırın)."""
    yol = _onbellek_yolu(bilgi)
    if os.path.exists(yol):
        return yol
    os.makedirs(RESIM_ONBELLEK, exist_ok=True)
    req = urllib.request.Request(bilgi["thumb_url"], headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        veri = r.read()
    gecici = yol + ".tmp"
    with open(gecici, "wb") as f:
        f.write(veri)
    os.replace(gecici, yol)
    _temizle()
    return yol


def _temizle():
    dosyalar = sorted(glob.glob(os.path.join(RESIM_ONBELLEK, "*")), key=os.path.getmtime, reverse=True)
    for f in dosyalar[SAKLANACAK:]:
        try:
            os.remove(f)
        except OSError:
            pass


def hazirla(ayarlar=None, tarih=None):
    """Günün resmini yerelde hazır eder ve yolunu döndürür (gerekirse indirir)."""
    r = gunun_resmi(ayarlar, tarih)
    if not r:
        return None
    if r["yol"] is None and r["bilgi"]:
        r["yol"] = indir(r["bilgi"])
    return r["yol"]


def duvar_kagidi_yap(yol):
    """Resmi kalıcı bir yere kopyalayıp Cinnamon masaüstü arka planı yapar."""
    os.makedirs(DUVAR_DIZINI, exist_ok=True)
    uzanti = os.path.splitext(yol)[1].lower() or ".jpg"
    hedef = os.path.join(DUVAR_DIZINI, f"duvar-kagidi-{dt.date.today().isoformat()}{uzanti}")
    if os.path.abspath(yol) != hedef:
        shutil.copyfile(yol, hedef)
    for eski in glob.glob(os.path.join(DUVAR_DIZINI, "duvar-kagidi-*")):
        if eski != hedef:
            os.remove(eski)
    uri = GLib.filename_to_uri(hedef, None)
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-uri", uri], check=False)
    subprocess.run(["gsettings", "set", "org.cinnamon.desktop.background", "picture-options", "zoom"], check=False)
    return hedef
