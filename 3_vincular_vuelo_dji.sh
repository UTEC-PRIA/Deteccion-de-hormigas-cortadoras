#!/usr/bin/env bash
# Vinculador a Formato DJI Mini 2 SE - Ubuntu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "venv/bin/python3" ]; then
    venv/bin/python3 vincular_vuelo_dji.py
else
    python3 vincular_vuelo_dji.py
fi

read -p "Presione ENTER para continuar..."
