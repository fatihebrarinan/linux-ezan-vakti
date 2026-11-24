"""Günün ayeti, hadisi ve vecizesi (data/ altındaki hazır listelerden)."""

import datetime as dt
import os

from . import ayarlar as A

_onbellek = {}


def _liste(dosya, anahtar):
    yol = os.path.join(A.VERI_DIZINI, dosya)
    try:
        mtime = os.path.getmtime(yol)
    except OSError:
        mtime = None
    if dosya not in _onbellek or _onbellek[dosya][0] != mtime:  # dosya değişince yeniden oku
        veri = A.json_oku(yol, {}) or {}
        _onbellek[dosya] = (mtime, veri.get(anahtar, []), veri.get("kaynak_notu", ""))
    return _onbellek[dosya][1:]


def _gunun(dosya, anahtar, tarih, kayma):
    liste, _ = _liste(dosya, anahtar)
    if not liste:
        return None
    tarih = tarih or dt.date.today()
    # Her gün bir sonraki; üç liste farklı kaymayla dönsün ki aynı konu üst üste gelmesin.
    return liste[(tarih.toordinal() * 37 + kayma) % len(liste)]


def gunun_ayeti(tarih=None):
    return _gunun("ayetler.json", "ayetler", tarih, 0)


def gunun_hadisi(tarih=None):
    return _gunun("hadisler.json", "hadisler", tarih, 11)


def gunun_vecizesi(tarih=None):
    return _gunun("vecizeler.json", "vecizeler", tarih, 23)


def kaynak_notu(dosya, anahtar):
    return _liste(dosya, anahtar)[1]


def bugun_ozeti(tarih=None):
    """Günün içeriği ve dini gün bilgisi; widget'ın ve Wallqueue'nun okuduğu bugun.json'un içeriği."""
    from . import resim, takvim
    tarih = tarih or dt.date.today()
    bugunku = [g["ad"] for g in takvim.o_gun(tarih)]
    h = takvim.hicri(tarih)
    yaklasan = takvim.yaklasan(tarih, 1)
    r = resim.gunun_resmi(tarih=tarih)
    return {
        "tarih": tarih.isoformat(),
        "hicri": takvim.hicri_yaz(tarih),
        "dini_gunler": bugunku,
        "yaklasan_dini_gun": ({"ad": yaklasan[0]["ad"], "tarih": yaklasan[0]["tarih"].isoformat(),
                               "kalan_gun": (yaklasan[0]["tarih"] - tarih).days} if yaklasan else None),
        # Ramazan ayı boyunca ve dini günlerde (kandil, bayram, arefe…) Wallqueue İslami resimleri öne alır
        "islami_tema": bool(bugunku) or bool(h and h[1] == 9),
        "ayet": gunun_ayeti(tarih),
        "hadis": gunun_hadisi(tarih),
        "vecize": gunun_vecizesi(tarih),
        "resim": (r or {}).get("bilgi"),
    }


def bugun_yaz(zorla=False):
    """bugun.json'u gerekiyorsa (gün değişmiş ya da veri dosyaları yenilenmişse) yeniden yazar."""
    eski = A.json_oku(A.BUGUN_DOSYASI, {}) or {}
    veri_zamani = max((os.path.getmtime(os.path.join(A.VERI_DIZINI, f))
                       for f in os.listdir(A.VERI_DIZINI) if f.endswith(".json")), default=0)
    if (not zorla and eski.get("tarih") == dt.date.today().isoformat()
            and eski.get("veri_zamani") == veri_zamani):
        return False
    ozet = bugun_ozeti()
    ozet["veri_zamani"] = veri_zamani
    A.json_yaz(A.BUGUN_DOSYASI, ozet)
    return True


def disa_ac():
    """Resim listesini başka uygulamaların (Wallqueue) bulacağı yere bağlar."""
    os.makedirs(A.DISA_ACIK_DIZIN, exist_ok=True)
    hedef = os.path.join(A.DISA_ACIK_DIZIN, "resimler.json")
    kaynak = os.path.join(A.VERI_DIZINI, "resimler.json")
    if os.path.islink(hedef) and os.readlink(hedef) == kaynak:
        return
    if os.path.lexists(hedef):
        os.remove(hedef)
    os.symlink(kaynak, hedef)
