@echo off
title Centro de Control y Telemetria UAV - UTEC PRIA
color 0F
echo =====================================================================
echo  INICIANDO CENTRO DE CONTROL Y TELEMETRIA UAV (UTEC-PRIA)
echo  Se abrira automaticamente su navegador en http://localhost:8000
echo =====================================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0web_dashboard.py"
) else (
    python "%~dp0web_dashboard.py"
)

pause
