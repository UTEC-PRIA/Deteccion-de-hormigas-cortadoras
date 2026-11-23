#!/usr/bin/env bash
# Ejecuta el Dashboard UAV UTEC-PRIA (http://localhost:8000).
# La primera vez crea el entorno virtual .venv e instala requirements.txt.
set -e
cd "$(dirname "$(readlink -f "$0")")"

if ! command -v exiftool >/dev/null 2>&1; then
    echo "[ERROR] Falta exiftool. Ejecute una sola vez:"
    echo "  sudo apt install -y python3-venv python3-pip libimage-exiftool-perl && sudo usermod -aG dialout \$USER"
    exit 1
fi

if [ ! -x .venv/bin/python ] || ! .venv/bin/python -m pip --version >/dev/null 2>&1; then
    echo "[*] Creando entorno virtual .venv (solo la primera vez)..."
    rm -rf .venv
    python3 -m venv .venv
fi

# Reinstalar dependencias solo si requirements.txt cambio
if [ ! -f .venv/.req_ok ] || ! cmp -s requirements.txt .venv/.req_ok; then
    echo "[*] Instalando dependencias de Python..."
    .venv/bin/python -m pip install --upgrade pip -q
    .venv/bin/python -m pip install -r requirements.txt
    cp requirements.txt .venv/.req_ok
fi

if ! id -nG | grep -qw dialout && getent group dialout | grep -qw "$USER"; then
    # El usuario ya pertenece a dialout pero la sesion actual aun no lo tiene: activarlo sin reiniciar
    exec sg dialout -c "$(printf '%q ' "$(readlink -f "$0")" "$@")"
elif ! id -nG | grep -qw dialout; then
    echo "[AVISO] Su usuario no esta en el grupo 'dialout': no podra leer la radio 915 MHz / Pixhawk."
    echo "        Ejecute: sudo usermod -aG dialout \$USER  y reinicie la sesion."
fi

exec .venv/bin/python app/web_dashboard.py "$@"
