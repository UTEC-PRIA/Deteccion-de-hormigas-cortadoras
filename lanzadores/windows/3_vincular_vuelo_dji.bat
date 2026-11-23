@echo off
title Vinculador a Formato DJI Mini 2 SE
color 0B

where py >nul 2>nul
if %errorlevel% equ 0 (
    py "%~dp0..\..\app\vincular_vuelo_dji.py"
) else (
    python "%~dp0..\..\app\vincular_vuelo_dji.py"
)

pause
