@echo off
cd /d "%~dp0..\.."
title Subir Cambios a GitHub - Proyecto UTEC PRIA
color 0B
echo =====================================================================
echo  SUBIENDO ARCHIVOS AL REPOSITORIO GITHUB
echo  https://github.com/UTEC-PRIA/Deteccion-de-hormigas-cortadoras
echo =====================================================================
echo.
git push origin main
if %errorlevel% equ 0 (
    echo.
    echo [+] Cambios subidos exitosamente a GitHub.
) else (
    echo.
    echo [AVISO] Si se solicita inicio de sesion, complete la autenticacion en el navegador.
)
echo.
pause
