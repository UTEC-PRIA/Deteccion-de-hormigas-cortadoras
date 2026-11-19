#!/usr/bin/env bash
# =====================================================================
#  PROYECTO UAV UTEC-PRIA - INSTALACION DE ENTORNO (UBUNTU / DEBIAN)
# =====================================================================

set -e

echo "====================================================================="
echo " PROYECTO UAV UTEC-PRIA - INSTALACION DE ENTORNO (UBUNTU)"
echo "====================================================================="
echo ""

# 1. Actualizar repositorios e instalar paquetes del sistema
echo "[1/4] Instalando dependencias del sistema operativo (apt)..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip python3-venv libimage-exiftool-perl git

# Permisos para el puerto serie USB (telemetria 915 MHz / Pixhawk)
echo "[2/4] Configurando permisos de usuario para puertos serie USB..."
sudo usermod -a -G dialout "$USER" || true

# 2. Crear y activar entorno virtual
echo "[3/4] Configurando entorno virtual de Python (venv)..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[+] Entorno virtual creado en ./venv"
else
    echo "[+] Entorno virtual existente detectado."
fi

# 3. Instalar requerimientos
echo "[4/4] Instalando librerias de Python en el entorno virtual..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Asignar permisos de ejecucion a los scripts .sh
chmod +x *.sh 2>/dev/null || true
if [ -d "scripts" ]; then
    chmod +x scripts/*.sh 2>/dev/null || true
fi

echo ""
echo "====================================================================="
echo " INSTALACION FINALIZADA SATISFACTORIAMENTE"
echo "====================================================================="
echo "Para operar el sistema en Ubuntu puede ejecutar:"
echo " - ./1_sincronizar_relojes.sh (Pre-vuelo por cable USB)"
echo " - ./2_grabar_telemetria.sh   (Durante el vuelo con radio 915 MHz)"
echo " - ./3_vincular_vuelo_dji.sh  (Post-vuelo para generar fotos DJI)"
echo ""
echo "Nota: Si es la primera vez que se agrega su usuario al grupo 'dialout',"
echo "puede requerirse cerrar sesion y volver a entrar para acceder al puerto serie."
echo "====================================================================="
