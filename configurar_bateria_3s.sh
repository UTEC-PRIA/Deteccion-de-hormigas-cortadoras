#!/usr/bin/env bash
echo "================================================================="
echo "  CONFIGURACION DE BATERIA LIPO 3S EN PIXHAWK 2.4.8"
echo "  UTEC PRIA - Deteccion de Hormigas Cortadoras"
echo "================================================================="
echo ""
python3 configurar_bateria_3s.py "$1"
echo ""
read -p "Presione ENTER para continuar..."
