#!/usr/bin/env bash
echo "====================================================================="
echo " INICIANDO CENTRO DE CONTROL Y TELEMETRIA UAV (UTEC-PRIA)"
echo " Se abrira automaticamente su navegador en http://localhost:8000"
echo "====================================================================="
echo ""
python3 "$(dirname "$0")/../../app/web_dashboard.py"
