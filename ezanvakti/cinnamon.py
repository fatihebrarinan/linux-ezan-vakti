"""Cinnamon'a masaüstü widget'ı (desklet) ve panel göstergesi (applet) ekleme/kaldırma."""

import ast
import subprocess

DESKLET = "ezan-vakti@fatih"
APPLET = "ezan-vakti-panel@fatih"


def _al(anahtar):
    cikti = subprocess.run(["gsettings", "get", "org.cinnamon", anahtar],
                           capture_output=True, text=True).stdout.strip()
    if cikti.startswith("@as"):
        return []
    if cikti.startswith("uint32") or cikti.startswith("int32"):
        cikti = cikti.split()[-1]
    try:
        return ast.literal_eval(cikti)
    except (ValueError, SyntaxError):
        return [] if anahtar.startswith("enabled") else 0


def _yaz(anahtar, deger):
    if isinstance(deger, list):
        deger = str(deger) if deger else "@as []"
    subprocess.run(["gsettings", "set", "org.cinnamon", anahtar, str(deger)], check=True)


def widget_listesi():
    """Masaüstündeki Ezan Vakti widget'larının Cinnamon kimlikleri (metin olarak)."""
    return [d.split(":")[1] for d in _al("enabled-desklets") if d.split(":")[0] == DESKLET]


def widget_ekli():
    return bool(widget_listesi())


def panel_ekli():
    return any(len(a.split(":")) > 3 and a.split(":")[3] == APPLET for a in _al("enabled-applets"))


def _ekran_genisligi():
    """Ana ekranın genişliği (bulunamazsa 1920)."""
    try:
        import gi
        gi.require_version("Gdk", "3.0")
        from gi.repository import Gdk
        ekran = Gdk.Display.get_default()
        monitor = ekran.get_primary_monitor() or ekran.get_monitor(0)
        return monitor.get_geometry().width
    except Exception:  # noqa: BLE001
        return 1920


def widget_ekle(x=None, y=60):
    """Masaüstüne yeni bir widget ekler ve Cinnamon kimliğini döndürür."""
    liste, kimlik = _al("enabled-desklets"), int(_al("next-desklet-id"))
    if x is None:  # ilk widget sağ üste, sonrakiler sola doğru sıralansın
        x = max(40, _ekran_genisligi() - 300 - 300 * len(widget_listesi()))
    liste.append(f"{DESKLET}:{kimlik}:{x}:{y}")
    _yaz("enabled-desklets", liste)
    _yaz("next-desklet-id", kimlik + 1)
    return str(kimlik)


def widget_kaldir(kimlik=None):
    """Bir widget'ı (kimlik verilmezse hepsini) kaldırır."""
    _yaz("enabled-desklets", [d for d in _al("enabled-desklets")
                              if not (d.split(":")[0] == DESKLET and (kimlik is None or d.split(":")[1] == str(kimlik)))])


def panel_ekle():
    """Göstergeyi ana panelin sağına, saatin hemen soluna ekler."""
    if panel_ekli():
        return
    liste, kimlik = _al("enabled-applets"), int(_al("next-applet-id"))
    parcalar = [a.split(":") for a in liste]
    saat = next((p for p in parcalar if len(p) > 3 and p[3] == "calendar@cinnamon.org"), None)
    if saat:
        panel, bolge, sira = saat[0], saat[1], int(saat[2])
        for p in parcalar:
            if p[0] == panel and p[1] == bolge and int(p[2]) >= sira:
                p[2] = str(int(p[2]) + 1)
    else:
        panel, bolge = "panel1", "right"
        sira = 1 + max([int(p[2]) for p in parcalar if p[0] == panel and p[1] == bolge] or [0])
    parcalar.append([panel, bolge, str(sira), APPLET, str(kimlik)])
    _yaz("enabled-applets", [":".join(p) for p in parcalar])
    _yaz("next-applet-id", kimlik + 1)


def panel_kaldir():
    _yaz("enabled-applets", [a for a in _al("enabled-applets")
                             if not (len(a.split(":")) > 3 and a.split(":")[3] == APPLET)])
