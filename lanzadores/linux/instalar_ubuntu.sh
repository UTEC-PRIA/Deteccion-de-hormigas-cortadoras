#!/usr/bin/env bash
set -e
echo "====================================================================="
echo " PROYECTO UAV UTEC-PRIA - INSTALACION DE ENTORNO (UBUNTU/DEBIAN)"
echo "====================================================================="
echo ""
echo "[1/3] Actualizando repositorios e instalando paquetes del sistema..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv libimage-exiftool-perl

echo "[2/3] Instalando dependencias de Python..."
python3 -m pip install -r "$(dirname "$0")/../../requirements.txt" || python3 -m pip install pymavlink pyserial psutil requests reportlab pillow open-gopro fastapi uvicorn

echo "[3/3] Configurando permisos de usuario para puertos serie..."
sudo usermod -a -G dialout "$USER"

echo ""
echo "[EXITO] Instalacion completada con exito."
echo "Si es la primera vez que agrega el grupo dialout, reinicie la sesion de Ubuntu."
