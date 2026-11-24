#!/usr/bin/env python3
"""Seçilmiş ayet referanslarından data/ayetler.json üretir.

Kullanım: ayetleri_olustur.py <secim.json> <quran-uthmani.txt> <tr.vakfi.txt>
Metinler Tanzil'den (tanzil.net): Arapça "Uthmani" metin ve Türkiye Diyanet Vakfı meali (txt-2 biçimi: sure|ayet|metin).
"""
import json
import os
import sys

SURELER = """Fâtiha|Bakara|Âl-i İmrân|Nisâ|Mâide|En'âm|A'râf|Enfâl|Tevbe|Yûnus|Hûd|Yûsuf|Ra'd|İbrâhîm|Hicr|Nahl|İsrâ|Kehf|Meryem|Tâhâ|Enbiyâ|Hac|Mü'minûn|Nûr|Furkān|Şuarâ|Neml|Kasas|Ankebût|Rûm|Lokmân|Secde|Ahzâb|Sebe'|Fâtır|Yâsîn|Sâffât|Sâd|Zümer|Mü'min|Fussilet|Şûrâ|Zuhruf|Duhân|Câsiye|Ahkāf|Muhammed|Fetih|Hucurât|Kāf|Zâriyât|Tûr|Necm|Kamer|Rahmân|Vâkıa|Hadîd|Mücâdele|Haşr|Mümtehine|Saf|Cuma|Münâfikūn|Teğâbün|Talâk|Tahrîm|Mülk|Kalem|Hâkka|Meâric|Nûh|Cin|Müzzemmil|Müddessir|Kıyâme|İnsân|Mürselât|Nebe'|Nâziât|Abese|Tekvîr|İnfitâr|Mutaffifîn|İnşikāk|Bürûc|Târık|A'lâ|Ğāşiye|Fecr|Beled|Şems|Leyl|Duhâ|İnşirâh|Tîn|Alak|Kadr|Beyyine|Zilzâl|Âdiyât|Kāria|Tekâsür|Asr|Hümeze|Fîl|Kureyş|Mâûn|Kevser|Kâfirûn|Nasr|Tebbet|İhlâs|Felak|Nâs""".split("|")
assert len(SURELER) == 114

# Tanzil'deki Diyanet Vakfı mealinde bulunan bariz dizgi hataları (metne dokunmadan yalnızca boşluk/işaret).
DUZELTMELER = {
    (15, 9): ("Kur an'ı", "Kur'an'ı"),
    (25, 63): ("Rahman'ın(has)", "Rahman'ın (has)"),
}
ARAPCA_RAKAM = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def oku(yol):
    d = {}
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            p = satir.rstrip("\n").split("|", 2)
            if len(p) == 3 and p[0].isdigit():
                d[(int(p[0]), int(p[1]))] = p[2]
    return d


def main(secim_yolu, arapca_yolu, meal_yolu):
    secim = json.load(open(secim_yolu, encoding="utf-8"))["ayetler"]
    arapca, meal = oku(arapca_yolu), oku(meal_yolu)
    cikti = []
    for s in secim:
        sure, bas, son = s["sure_no"], s["ayet"], s.get("bitis") or s["ayet"]
        ar, tr, notlar = [], [], []
        for a in range(bas, son + 1):
            # Tanzil şartı: Arapça metin değiştirilmeden kullanılır (işaretler dahil)
            ar.append(arapca[(sure, a)] + (f" ﴿{str(a).translate(ARAPCA_RAKAM)}﴾" if son > bas else ""))
            m = meal[(sure, a)]
            if (sure, a) in DUZELTMELER:
                eski, yeni = DUZELTMELER[(sure, a)]
                assert eski in m, (sure, a)
                m = m.replace(eski, yeni)
                notlar.append(f"Mealdeki \"{eski}\" dizgi hatası \"{yeni}\" olarak düzeltildi.")
            tr.append(m)
        ad = SURELER[sure - 1]
        cikti.append({
            "sure_no": sure, "sure": ad, "ayet": bas, "bitis": son,
            "ref": f"{ad} Sûresi, {sure}:{bas}" + (f"-{son}" if son > bas else ""),
            "arapca": " ".join(ar), "meal": " ".join(tr), "konu": s.get("konu", ""),
            **({"not": " ".join(notlar)} if notlar else {}),
        })
    hedef = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "ayetler.json")
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump({
            "kaynak_notu": "Arapça metin: Tanzil Projesi (tanzil.net), Medine Mushafı. "
                           "Meal: Türkiye Diyanet Vakfı meali (Tanzil üzerinden; ticari olmayan kullanım).",
            "ayetler": cikti,
        }, f, ensure_ascii=False, indent=1)
    print(f"{len(cikti)} ayet → {os.path.normpath(hedef)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
