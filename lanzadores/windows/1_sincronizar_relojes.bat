@echo off
title Sincronizacion Pre-Vuelo - Pixhawk y GoPro
color 0A

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0..\..\app\sincronizar_relojes.py"
) else (
    python "%~dp0..\..\app\sincronizar_relojes.py"
)

pause
