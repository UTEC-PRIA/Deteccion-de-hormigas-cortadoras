@echo off
chcp 65001 > nul
echo =================================================================
echo   CONFIGURACION DE BATERIA LIPO 3S EN PIXHAWK 2.4.8
echo   UTEC PRIA - Deteccion de Hormigas Cortadoras
echo =================================================================
echo.
py configurar_bateria_3s.py %1
echo.
pause
