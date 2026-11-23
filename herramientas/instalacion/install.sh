#!/bin/bash
set -e

echo "==============================================="
echo "🐜 Instalador del Dashboard Drone PRIA"
echo "==============================================="

echo "Este script requiere permisos sudo para instalar dependencias de apt."
sudo apt-get update
sudo apt-get install -y python3-pip mono-complete network-manager msitools wine winetricks xvfb libgdiplus fonts-liberation cabextract

echo "[2/4] Instalando dependencias de Python..."
pip3 install -r "$(dirname "${BASH_SOURCE[0]}")/../../requirements.txt"

echo "[3/4] Creando acceso directo en el Escritorio..."
DESKTOP_DIR=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
if [ ! -d "$DESKTOP_DIR" ]; then
    mkdir -p "$DESKTOP_DIR"
fi

SHORTCUT="$DESKTOP_DIR/DroneMissionControl.desktop"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ICON_PATH="$PROJECT_DIR/app/static/ant_icon.png"

cat <<EOF > "$SHORTCUT"
[Desktop Entry]
Version=1.0
Name=Drone Mission Control
Comment=Lanza el servidor de telemetria y GoPro, y abre el navegador
Exec=bash -c "cd '$PROJECT_DIR' && ./ejecutar.sh"
Icon=$ICON_PATH
Terminal=true
Type=Application
Categories=Utility;
EOF

chmod +x "$SHORTCUT"
# En Ubuntu, los accesos directos deben ser confiables para poder ejecutarse.
gio set "$SHORTCUT" metadata::trusted true || true

echo "==============================================="
echo "✅ Instalación completada."
echo "==============================================="

echo "[4/4] Ejecutando verificador de salud..."
python3 "$PROJECT_DIR/herramientas/instalacion/check_install.py"
