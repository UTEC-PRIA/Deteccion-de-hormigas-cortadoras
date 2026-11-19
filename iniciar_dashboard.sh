#!/usr/bin/env bash
# Iniciar Dashboard Web - Ubuntu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "====================================================================="
echo " INICIANDO CENTRO DE CONTROL Y TELEMETRIA UAV (UTEC-PRIA)"
echo " Se abrira automaticamente su navegador en http://localhost:8000"
echo "====================================================================="

if [ -f "venv/bin/python3" ]; then
    venv/bin/python3 web_dashboard.py
else
    python3 web_dashboard.py
fi
