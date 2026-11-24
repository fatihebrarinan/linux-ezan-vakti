#!/usr/bin/env bash
# Ezan Vakti'yi kaldırır (ayarlar ~/.config/ezan-vakti ve önbellek ~/.cache/ezan-vakti silinmez).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
CONF="${XDG_CONFIG_HOME:-$HOME/.config}"

python3 - "$ROOT" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
from ezanvakti import cinnamon
cinnamon.widget_kaldir()
cinnamon.panel_kaldir()
PY
pkill -f "bin/ezan-vakti servis$" || true
rm -f "$HOME/.local/bin/ezan-vakti" \
      "$DATA/cinnamon/desklets/ezan-vakti@fatih" "$DATA/cinnamon/applets/ezan-vakti-panel@fatih" \
      "$DATA/applications/ezan-vakti.desktop" "$CONF/autostart/ezan-vakti-servis.desktop" \
      "$DATA/icons/hicolor/scalable/apps/ezan-vakti.svg" "$DATA/icons/hicolor/256x256/apps/ezan-vakti.png" \
      "$DATA/ezan-vakti/resimler.json"
echo "Kaldırıldı. (Ayarlar: ~/.config/ezan-vakti, önbellek: ~/.cache/ezan-vakti)"
