#!/bin/bash
# ============================================================
# Mission Planner Installer for Ubuntu via Wine
# Compatible con Ubuntu 22.04 LTS
# ============================================================
set -e

WINEPREFIX="$HOME/.wine-mp"
DESKTOP_FILE="$HOME/.local/share/applications/mission-planner.desktop"
ICON_PATH="$HOME/.local/share/icons/mission-planner.png"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export WINEPREFIX
export WINEARCH=win64

echo "============================================"
echo "  Mission Planner Installer"
echo "  Este proceso puede tomar 20-30 minutos"
echo "============================================"

echo ""
echo "🧹 Limpiando instalación previa si existe..."
rm -rf "$WINEPREFIX"
rm -f "$DESKTOP_FILE"
rm -f "$ICON_PATH"

echo ""
echo "📦 Instalando dependencias del sistema (wine, winbind, winetricks)..."
sudo apt-get update -qq
sudo apt-get install -y wine winbind winetricks xvfb

echo ""
echo "🔄 Actualizando winetricks a la última versión..."
sudo wget -q -O /usr/bin/winetricks https://raw.githubusercontent.com/Winetricks/winetricks/master/src/winetricks
sudo chmod +x /usr/bin/winetricks

echo ""
echo "🌱 Creando nuevo prefijo de Wine 64 bits..."
wineboot -u 2>/dev/null || true

echo ""
echo "📥 Descargando e instalando Wine Mono 4.6.2..."
MONO_FILE="/tmp/wine-mono-4.6.2.msi"
if [ ! -f "$MONO_FILE" ]; then
    wget -q --show-progress -O "$MONO_FILE" https://dl.winehq.org/wine/wine-mono/4.6.2/wine-mono-4.6.2.msi
fi
wine msiexec /i "$MONO_FILE" /quiet 2>/dev/null || echo "⚠️  Problema instalando Wine Mono (puede continuar)."

echo ""
echo "⚙️  Instalando .NET 4.6.1 (requerido por Mission Planner, esto tarda...)..."
WINEDLLOVERRIDES="mscoree,mshtml=" winetricks -q dotnet461 2>/dev/null || echo "⚠️  Problema instalando dotnet461, continuando..."

echo ""
echo "📥 Descargando Mission Planner..."
MP_FILE="/tmp/MissionPlanner-latest.msi"
if [ ! -f "$MP_FILE" ]; then
    wget -q --show-progress -O "$MP_FILE" https://firmware.ardupilot.org/Tools/MissionPlanner/MissionPlanner-latest.msi
fi

echo ""
echo "📦 Instalando Mission Planner (esto puede tardar)..."
wine msiexec /i "$MP_FILE" /quiet /norestart 2>/dev/null || \
wine msiexec /i "$MP_FILE" 2>/dev/null || \
echo "⚠️  Intento de instalación interactiva fallido, verifica manualmente."

echo ""
echo "🖼️  Creando ícono y acceso directo..."
mkdir -p "$(dirname "$ICON_PATH")"
mkdir -p "$(dirname "$DESKTOP_FILE")"
wget -q -O "$ICON_PATH" \
    "https://play-lh.googleusercontent.com/Fzz2Mm6jeclcPtG9mckXt2GbM_Ihnd8SkmKH16Kowuku3ALkImMv52rp4ypbsJCuB54=w240-h480-rw" \
    2>/dev/null || true

# Buscar el ejecutable de Mission Planner
MP_EXE=$(find "$WINEPREFIX" -name "MissionPlanner.exe" 2>/dev/null | head -1)
if [ -z "$MP_EXE" ]; then
    MP_EXE="$WINEPREFIX/drive_c/Program Files (x86)/Mission Planner/MissionPlanner.exe"
fi

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Mission Planner
Comment=Ground Control Station for ArduPilot/PX4 drones
Exec=env WINEPREFIX=$WINEPREFIX wine "$MP_EXE"
Icon=$ICON_PATH
Type=Application
Categories=Utility;Science;
StartupNotify=true
EOF
chmod +x "$DESKTOP_FILE"

echo ""
echo "============================================"
echo "✅ Instalación completa."
echo ""
echo "Ejecutar Mission Planner con:"
echo "  WINEPREFIX=$WINEPREFIX wine \"$MP_EXE\""
echo ""
echo "O desde el menú de aplicaciones del sistema."
echo "============================================"
