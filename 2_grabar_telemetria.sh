#!/usr/bin/env bash
# Grabador de Telemetria en Vivo - Ubuntu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "venv/bin/python3" ]; then
    venv/bin/python3 grabar_telemetria.py
else
    python3 grabar_telemetria.py
fi

read -p "Presione ENTER para continuar..."
