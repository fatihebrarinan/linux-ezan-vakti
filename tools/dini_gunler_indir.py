#!/usr/bin/env python3
"""Diyanet'in yıllık dini günler listelerini indirip data/dini_gunler.json üretir.

Kaynak: https://vakithesaplama.diyanet.gov.tr (Önemli Günler › Dini Günler Listesi)
Listeler her hicrî ayın 1. gününü de içerdiği için hicrî takvim dönüşümü de buradan çıkar.
"""
import html
import json
import os
import re
import sys
import time
import urllib.request

BASE = "https://vakithesaplama.diyanet.gov.tr/"
SAYFALAR = {
    2025: "dinigunler.php?yil=2025",
    2026: "dinigunler.php?yil=2026",
    2027: "icerik.php?icerik=154",
    **{2028 + i: f"icerik.php?icerik={185 + i}" for i in range(8)},  # 2028–2035
}
MILADI = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN", "TEMMUZ",
          "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
ADLAR = {
    "ÜÇ AYLARIN BAŞLANGICI": "Üç Ayların Başlangıcı",
    "REGAİB KANDİLİ": "Regaib Kandili",
    "MİRAC KANDİLİ": "Miraç Kandili",
    "BERAT KANDİLİ": "Berat Kandili",
    "RAMAZAN BAŞLANGICI": "Ramazan Başlangıcı",
    "KADİR GECESİ": "Kadir Gecesi",
    "HİCRİ YILBAŞI": "Hicrî Yılbaşı",
    "AŞURE GÜNÜ": "Aşure Günü",
    "MEVLİD KANDİLİ": "Mevlid Kandili",
}


def norm(s):
    return re.sub(r"\s+", " ", s.replace("İ", "İ")).strip().upper()


def hicri_ay(ad):
    """Ay adını 1–12'ye çevirir; sayfalardaki yazım farklılıklarına (R.EVVEL, R.VVEL, REBİÜLEVVEL…) dayanıklı."""
    a = norm(ad).replace(" ", "")
    oneki = [("MUH", 1), ("SAF", 2), ("REC", 7), ("ŞAB", 8), ("RAM", 9), ("ŞEV", 10), ("ZİLK", 11), ("ZİLH", 12)]
    for on, no in oneki:
        if a.startswith(on):
            return no
    if a[:1] in ("R", "C"):
        ilk = 3 if a[0] == "R" else 5
        if "AH" in a:
            return ilk + 1
        if "EV" in a or "VVEL" in a:
            return ilk
    raise ValueError(f"bilinmeyen hicrî ay: {ad}")


def gun_adi(ham, hay, hgun):
    h = norm(ham)
    if h.startswith("."):
        return None
    if h in ADLAR:
        return ADLAR[h]
    m = re.match(r"(RAMAZAN|KURBAN) BAYRAMI \((\d)\. GÜN\)", h)
    if m:
        return f"{m.group(1).title()} Bayramı ({m.group(2)}. gün)"
    if h == "AREFE":
        return "Ramazan Bayramı Arefesi" if hay == 9 else "Kurban Bayramı Arefesi"
    return ham.strip().title()


def indir(yol):
    onbellek = os.environ.get("DG_ONBELLEK")  # isteğe bağlı: indirilen sayfaları sakla
    if onbellek:
        yolu = os.path.join(onbellek, re.sub(r"\W", "_", yol) + ".html")
        if os.path.exists(yolu):
            with open(yolu, encoding="utf-8") as f:
                return f.read()
    for deneme in range(6):
        try:
            req = urllib.request.Request(BASE + yol, headers={"User-Agent": "Mozilla/5.0 (EzanVakti)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                metin = r.read().decode("utf-8", "replace")
            if onbellek:
                os.makedirs(onbellek, exist_ok=True)
                with open(yolu, "w", encoding="utf-8") as f:
                    f.write(metin)
            return metin
        except OSError as e:
            print(f"  {yol}: {e}, tekrar…", file=sys.stderr)
            time.sleep(10 * (deneme + 1))
    raise SystemExit(f"{yol} indirilemedi")


def ayikla(sayfa, yil):
    tablo = re.search(r"<table.*?</table>", sayfa, flags=re.S)
    if not tablo:
        raise SystemExit(f"{yil}: tablo bulunamadı")
    satirlar = []
    for tr in re.findall(r"<tr.*?</tr>", tablo.group(0), flags=re.S):
        h = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip()
             for c in re.findall(r"<t[dh].*?</t[dh]>", tr, flags=re.S)]
        if len(h) < 7 or not h[0].isdigit():
            continue
        hgun, hay, hyil = int(h[0]), hicri_ay(h[1]), int(h[2])
        ay_ad, myil = [x.strip() for x in h[4].split("-")]
        may = MILADI.index(norm(ay_ad)) + 1
        tarih = f"{int(myil):04d}-{may:02d}-{int(h[3]):02d}"
        satirlar.append({"tarih": tarih, "hicri": [hyil, hay, hgun], "ad": gun_adi(h[6], hay, hgun)})
    return satirlar


def main():
    hedef = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "dini_gunler.json")
    gunler, baslar = {}, {}
    for yil, yol in SAYFALAR.items():
        print(f"{yil}…", file=sys.stderr)
        for s in ayikla(indir(yol), yil):
            if s["hicri"][2] == 1:
                baslar[s["tarih"]] = s["hicri"][:2]
            if s["ad"]:
                gunler[(s["tarih"], s["ad"])] = s
        time.sleep(8)  # site sık isteklerde bağlantıyı kesiyor
    cikti = {
        "kaynak": "T.C. Diyanet İşleri Başkanlığı, vakithesaplama.diyanet.gov.tr — Dini Günler Listesi",
        "gunler": sorted(gunler.values(), key=lambda s: s["tarih"]),
        "hicri_ay_baslari": [{"tarih": t, "yil": v[0], "ay": v[1]} for t, v in sorted(baslar.items())],
    }
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump(cikti, f, ensure_ascii=False, indent=1)
    print(f"{len(cikti['gunler'])} dini gün, {len(cikti['hicri_ay_baslari'])} hicrî ay başı → {os.path.normpath(hedef)}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
