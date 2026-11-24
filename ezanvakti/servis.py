"""Arka plan servisi: vakit bildirimleri, ses, vakit verisinin ve günün resminin güncellenmesi.

Oturum açılınca otomatik başlar (~/.config/autostart/ezan-vakti-servis.desktop).
Tek kopya çalışır; ikinci kopya hemen çıkar.
"""

import datetime as dt
import fcntl
import os
import signal
import subprocess
import sys
import threading

import gi

gi.require_version("Notify", "0.7")
from gi.repository import GLib, Notify  # noqa: E402

from . import ayarlar as A  # noqa: E402
from . import icerik, resim, takvim  # noqa: E402
from . import vakitler as V  # noqa: E402

TIK_SN = 10
YENIDEN_DENE = dt.timedelta(minutes=10)
GEC_KALMA_SINIRI = dt.timedelta(seconds=90)
UYKU_ESIGI = dt.timedelta(minutes=5)
DURUM_DOSYASI = os.path.join(A.ONBELLEK_DIZINI, "servis-durum.json")


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


# ---------- Ses ----------

def ses_cal(dosya):
    """Sesi çalar, pid'ini kaydeder. Dönüş: Popen."""
    ses_sustur()
    if not dosya or not os.path.exists(dosya):
        dosya = A.VARSAYILAN_SES
    if GLib.find_program_in_path("gst-play-1.0"):
        komut = ["gst-play-1.0", "--no-interactive", "-q", dosya]
    else:
        komut = ["paplay", dosya]
    p = subprocess.Popen(komut, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.makedirs(A.ONBELLEK_DIZINI, exist_ok=True)
    with open(A.SES_PID_DOSYASI, "w") as f:
        f.write(str(p.pid))
    return p


def ses_sustur():
    try:
        with open(A.SES_PID_DOSYASI) as f:
            pid = int(f.read().strip())
        os.remove(A.SES_PID_DOSYASI)
        # Yalnızca gerçekten bizim çalıcımızsa öldür
        with open(f"/proc/{pid}/comm") as f:
            if f.read().strip() in ("gst-play-1.0", "paplay"):
                os.kill(pid, signal.SIGTERM)
                return True
    except (OSError, ValueError):
        pass
    return False


# ---------- Bildirim ----------

class Bildirici:
    def __init__(self):
        Notify.init("Ezan Vakti")
        self._acik = []   # eylem sinyalleri için referans tut

    def gonder(self, baslik, govde, kalici=False, sustur_dugmesi=False):
        n = Notify.Notification.new(baslik, govde, A.SIMGE)
        n.set_app_name("Ezan Vakti")
        if kalici:
            n.set_urgency(Notify.Urgency.CRITICAL)
        else:
            n.set_timeout(10000)
        if sustur_dugmesi:
            n.add_action("sustur", "Ezanı durdur", lambda *_: ses_sustur())
        n.connect("closed", lambda x: self._acik.remove(x) if x in self._acik else None)
        self._acik.append(n)
        try:
            n.show()
        except GLib.Error as e:
            log("bildirim gönderilemedi:", e.message)


def vakit_basligi(v, ayar):
    if ayar["bildirim"]["baslik"] == "namaz" and v.namaz:
        return f"Namaz vakti — {v.namaz}"
    return f"{v.ad} vakti girdi"


# ---------- Servis ----------

class Servis:
    def __init__(self):
        self.bildirici = Bildirici()
        self.ayar = A.yukle()
        self.ayar_mtime = None
        self.gunler, self.gunler_kaynagi = {}, None
        self.son_tik = dt.datetime.now()
        self.sonraki_indirme = dt.datetime.min
        self.indiriliyor = False
        self.durum = A.json_oku(DURUM_DOSYASI, {}) or {}

    def _durum_kaydet(self):
        A.json_yaz(DURUM_DOSYASI, self.durum)

    def _ayarlari_tazele(self):
        try:
            m = os.path.getmtime(A.AYARLAR_DOSYASI)
        except OSError:
            m = None
        if m != self.ayar_mtime:
            self.ayar_mtime = m
            self.ayar = A.yukle()

    def _vakitleri_tazele(self, simdi):
        k = A.konum()
        if not k:
            self.gunler = {}
            return
        yol = V.onbellek_yolu(k["ilceId"])
        try:
            anahtar = (yol, os.path.getmtime(yol))
        except OSError:
            anahtar = (yol, None)
        if anahtar != self.gunler_kaynagi:
            self.gunler_kaynagi = anahtar
            self.gunler = V.gunleri_oku(k["ilceId"])
        if (not self.indiriliyor and simdi >= self.sonraki_indirme
                and V.guncelleme_gerekli(k["ilceId"], simdi.date())):
            self._arka_planda(self._indir)

    def _arka_planda(self, is_):
        def calistir():
            try:
                is_()
            except Exception as e:  # noqa: BLE001
                log("hata:", e)
        threading.Thread(target=calistir, daemon=True).start()

    def _indir(self):
        self.indiriliyor = True
        try:
            n = V.guncelle()
            log(f"vakitler güncellendi ({n} gün)")
        except Exception as e:  # noqa: BLE001
            log("vakitler indirilemedi:", e)
            self.sonraki_indirme = dt.datetime.now() + YENIDEN_DENE
        finally:
            self.indiriliyor = False

    def _gunluk_isler(self, simdi):
        bugun = simdi.date().isoformat()
        # Widget'ların ve Wallqueue'nun okuduğu günün özeti (gün ya da veri değişince yenilenir)
        icerik.bugun_yaz()
        # Günün resmini önceden indir (duvar kâğıdını artık Wallqueue yönetiyor)
        if self.durum.get("resim_gunu") != bugun:
            def resim_hazirla():
                resim.hazirla(self.ayar)
                self.durum["resim_gunu"] = bugun
                self._durum_kaydet()
            self.durum["resim_gunu"] = bugun  # aynı gün tekrar denemesin
            self._arka_planda(resim_hazirla)
        # Dini gün hatırlatması (sabah 8'den sonra, günde bir kez)
        if (self.ayar["bildirim"]["dini_gun"] and simdi.hour >= 8
                and self.durum.get("dini_gun_bildirimi") != bugun):
            self.durum["dini_gun_bildirimi"] = bugun
            self._durum_kaydet()
            for g in takvim.o_gun(simdi.date()):
                ek = "Kandiliniz mübarek olsun. Kandil bu akşam idrak edilir." if takvim.kandil_mi(g["ad"]) else \
                     "Bayramınız mübarek olsun." if "Bayramı (" in g["ad"] else ""
                self.bildirici.gonder(f"Bugün {g['ad']}", ek or takvim.hicri_yaz(simdi.date()))

    def tik(self):
        simdi = dt.datetime.now()
        try:
            self._ayarlari_tazele()
            self._vakitleri_tazele(simdi)
            self._uyarilar(simdi)
            self._gunluk_isler(simdi)
        except Exception as e:  # noqa: BLE001
            log("tik hatası:", e)
        self.son_tik = simdi
        return GLib.SOURCE_CONTINUE

    def _uyarilar(self, simdi):
        onceki = self.son_tik
        if simdi - onceki > UYKU_ESIGI:
            return  # uykudan dönüş: kaçırılmış eski uyarıları art arda gösterme
        bugun = self.gunler.get(simdi.date())
        if not bugun:
            return

        def gecti(an):
            return onceki < an <= simdi and simdi - an < GEC_KALMA_SINIRI

        b = self.ayar["bildirim"]
        once = dt.timedelta(minutes=int(b["once_dk"] or 0))
        k = A.konum()
        yer = A.konum_adi(k)
        for v in V.VAKITLER:
            an = bugun.an(v.id)
            saat = bugun.saatler[v.id]
            if once and gecti(an - once):
                dk = int(b["once_dk"])
                if v.id == "gunes":
                    if b["gunes"]:
                        self.bildirici.gonder(f"Güneşin doğmasına {dk} dakika kaldı",
                                              f"Sabah namazının vakti {saat}'de çıkıyor.")
                else:
                    self.bildirici.gonder(f"{v.ad} vaktine {dk} dakika kaldı", f"{v.ad} vakti: {saat}")
            if gecti(an):
                self.vakit_girdi(v, saat, yer)

    def vakit_girdi(self, v, saat, yer):
        b = self.ayar["bildirim"]
        if v.id == "gunes":
            if b["gunes"]:
                self.bildirici.gonder("Güneş doğdu", "Sabah namazının vakti çıktı.")
            return
        ezan = b["tur"] == "ezan" and (v.id != "imsak" or b["imsakta_ezan"])
        if b["acik"]:
            self.bildirici.gonder(vakit_basligi(v, self.ayar), f"{saat} · {yer}",
                                  kalici=b["ekranda_kal"], sustur_dugmesi=ezan)
        if ezan:
            ses_cal(b["ezan_dosyasi"])
        elif b["tur"] == "kisa_ses":
            ses_cal(A.VARSAYILAN_SES)

    def calistir(self):
        log("Ezan Vakti servisi başladı")
        try:
            icerik.disa_ac()
        except OSError as e:
            log("resim listesi yayımlanamadı:", e)
        self.tik()
        GLib.timeout_add_seconds(TIK_SN, self.tik)
        dongu = GLib.MainLoop()
        for s in (signal.SIGINT, signal.SIGTERM):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, s, lambda *_: (dongu.quit(), False)[1])
        dongu.run()


KILIT_DOSYASI = os.path.join(A.ONBELLEK_DIZINI, "servis.lock")


def calisiyor_mu():
    """Servis kilidi başka bir süreçte mi?"""
    try:
        with open(KILIT_DOSYASI, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
            return False
    except OSError:
        return True


def main():
    os.makedirs(A.ONBELLEK_DIZINI, exist_ok=True)
    kilit = open(KILIT_DOSYASI, "a")
    try:
        fcntl.flock(kilit, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("Ezan Vakti servisi zaten çalışıyor.", file=sys.stderr)
        return 0
    Servis().calistir()
    return 0
