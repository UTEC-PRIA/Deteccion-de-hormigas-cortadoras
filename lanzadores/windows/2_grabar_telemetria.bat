@echo off
title Grabador de Telemetria en Vivo (915 MHz)
color 0E

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0..\..\app\grabar_telemetria.py"
) else (
    python "%~dp0..\..\app\grabar_telemetria.py"
)

pause
