#!/usr/bin/env bash
# Ezan Vakti'yi kullanıcı dizinine kurar: uygulama, bildirim servisi, masaüstü widget'ı, panel göstergesi.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"
BIN="$HOME/.local/bin/ezan-vakti"

link() {  # link <kaynak> <hedef>: hedef yoksa ya da zaten bağlantıysa bağla
    mkdir -p "$(dirname "$2")"
    if [ -L "$2" ] || [ ! -e "$2" ]; then ln -sfn "$1" "$2"
    else echo "Uyarı: $2 zaten var ve bağlantı değil; dokunulmadı." >&2; fi
}

# 1) Komut ve Cinnamon parçaları (sembolik bağ: koddaki değişiklikler doğrudan geçerli)
link "$ROOT/bin/ezan-vakti" "$BIN"
link "$ROOT/ezan-vakti@fatih" "$DATA/cinnamon/desklets/ezan-vakti@fatih"
link "$ROOT/ezan-vakti-panel@fatih" "$DATA/cinnamon/applets/ezan-vakti-panel@fatih"

# 2) Simge
ICONS="$DATA/icons/hicolor"
mkdir -p "$ICONS/scalable/apps" "$ICONS/256x256/apps"
cp "$ROOT/ezan-vakti@fatih/icon.svg" "$ICONS/scalable/apps/ezan-vakti.svg"
python3 -c "
import gi; gi.require_version('GdkPixbuf','2.0'); from gi.repository import GdkPixbuf
GdkPixbuf.Pixbuf.new_from_file_at_size('$ROOT/ezan-vakti@fatih/icon.svg',256,256).savev('$ICONS/256x256/apps/ezan-vakti.png','png',[],[])"
gtk-update-icon-cache -q -t "$ICONS" 2>/dev/null || true

# 3) Menü girişi
mkdir -p "$DATA/applications"
cat > "$DATA/applications/ezan-vakti.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Ezan Vakti
Comment=Namaz vakitleri, dini günler, günün ayeti, hadisi ve vecizesi
Exec=$BIN
Icon=ezan-vakti
Terminal=false
Categories=Utility;
Keywords=namaz;ezan;vakit;imsakiye;ramazan;kandil;
StartupWMClass=ezan-vakti
DESKTOP
update-desktop-database -q "$DATA/applications" 2>/dev/null || true

# 4) Bildirim servisi: oturum açılınca başlasın, şimdi de başlat
mkdir -p "$CONF/autostart"
cat > "$CONF/autostart/ezan-vakti-servis.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Ezan Vakti servisi
Comment=Namaz vakti bildirimleri
Exec=$BIN servis
Icon=ezan-vakti
NoDisplay=true
X-GNOME-Autostart-enabled=true
DESKTOP
# (servis zaten çalışıyorsa yeni kopya kilidi alamaz ve hemen çıkar)
mkdir -p "${XDG_CACHE_HOME:-$HOME/.cache}/ezan-vakti"
setsid "$BIN" servis >>"${XDG_CACHE_HOME:-$HOME/.cache}/ezan-vakti/servis.log" 2>&1 < /dev/null &

# 5) Masaüstü widget'ı ve panel göstergesi
python3 - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from ezanvakti import cinnamon, icerik
if not cinnamon.widget_ekli():
    cinnamon.widget_ekle()
cinnamon.panel_ekle()
icerik.bugun_yaz(zorla=True)   # widget'ların okuduğu günün özeti
icerik.disa_ac()               # resim listesi → ~/.local/share/ezan-vakti/ (Wallqueue okur)
PY

echo "Ezan Vakti kuruldu. Menüden 'Ezan Vakti'yi açabilirsiniz."
if [ ! -f "$CONF/ezan-vakti/konum.json" ]; then "$BIN" konum >/dev/null 2>&1 & fi
