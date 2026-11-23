#!/bin/bash
# ============================================================
# Mission Planner Finisher — Configura fuentes y lanza MP
# Ejecutar DESPUÉS de que install_mission_planner.sh haya copiado los archivos
# ============================================================
set -e
WINEPREFIX="$HOME/.wine-mp"
MP_EXE="$WINEPREFIX/drive_c/Program Files (x86)/Mission Planner/MissionPlanner.exe"
ICON_PATH="$HOME/.local/share/icons/mission-planner.png"
DESKTOP_FILE="$HOME/.local/share/applications/mission-planner.desktop"

export WINEPREFIX
export WINEARCH=win64

echo "=== Configurando fuentes para Mission Planner ==="
# Install fonts without interactive EULA
echo "ubuntu" | sudo -S DEBIAN_FRONTEND=noninteractive apt-get install -y fonts-liberation libgdiplus 2>/dev/null || true

# Install corefonts via winetricks
Xvfb :99 -screen 0 1024x768x24 &
sleep 2
DISPLAY=:99 winetricks -q corefonts 2>/dev/null || true
kill %1 2>/dev/null || true

echo "=== Creando acceso directo ==="
mkdir -p "$(dirname "$ICON_PATH")" "$(dirname "$DESKTOP_FILE")"
wget -q -O "$ICON_PATH" \
    "https://play-lh.googleusercontent.com/Fzz2Mm6jeclcPtG9mckXt2GbM_Ihnd8SkmKH16Kowuku3ALkImMv52rp4ypbsJCuB54=w240-h480-rw" 2>/dev/null || true

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Mission Planner
Comment=Ground Control Station for ArduPilot drones
Exec=env WINEPREFIX=$WINEPREFIX DISPLAY=\${DISPLAY:-:0} wine "$MP_EXE"
Icon=$ICON_PATH
Type=Application
Categories=Utility;Science;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"

echo ""
echo "=== Lanzando Mission Planner ==="
echo "Conectar en Mission Planner: tcp:localhost:5760"
echo ""
DISPLAY=${DISPLAY:-:0} wine "$MP_EXE" &
echo "Mission Planner lanzado (PID: $!)"
