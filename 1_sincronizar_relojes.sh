#!/usr/bin/env bash
# Sincronizacion Pre-Vuelo - Ubuntu
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ -f "venv/bin/python3" ]; then
    venv/bin/python3 sincronizar_relojes.py
else
    python3 sincronizar_relojes.py
fi

read -p "Presione ENTER para continuar..."
