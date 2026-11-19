@echo off
setlocal enabledelayedexpansion
title Instalador de Dependencias - Proyecto UAV Hormigas Cortadoras
color 0F

echo =====================================================================
echo  PROYECTO UAV UTEC-PRIA - INSTALACION DE ENTORNO (WINDOWS)
echo =====================================================================
echo.

:: 1. Verificar Python
echo [1/3] Verificando instalacion de Python...
where py >nul 2>nul
if %errorlevel% equ 0 (
    set PY_CMD=py
    goto :PYTHON_OK
)

where python >nul 2>nul
if %errorlevel% equ 0 (
    set PY_CMD=python
    goto :PYTHON_OK
)

echo.
echo [ERROR] No se encontro Python instalado en el sistema.
echo Por favor, descargue e instale Python desde https://www.python.org/
echo Asegurese de marcar la casilla "Add python.exe to PATH" durante la instalacion.
echo.
pause
exit /b 1

:PYTHON_OK
echo [+] Python detectado correctamente:
%PY_CMD% --version
echo.

:: 2. Instalar requerimientos de Python
echo [2/3] Instalando paquetes y librerias necesarias...
%PY_CMD% -m pip install --upgrade pip
%PY_CMD% -m pip install -r "%~dp0requirements.txt"
if %errorlevel% neq 0 (
    echo.
    echo [ADVERTENCIA] Algunos paquetes reportaron problemas. Reintentando instalacion individual...
    %PY_CMD% -m pip install pymavlink pyserial psutil requests reportlab pillow open-gopro
)
echo [+] Librerias de Python instaladas con exito.
echo.

:: 3. Verificar o instalar ExifTool
echo [3/3] Verificando herramienta de metadatos (ExifTool)...
where exiftool >nul 2>nul
if %errorlevel% equ 0 (
    echo [+] ExifTool ya se encuentra instalado en el sistema.
    goto :FINAL
)

if exist "C:\Users\%USERNAME%\AppData\Local\Programs\ExifTool\exiftool.exe" (
    echo [+] ExifTool encontrado en la carpeta de usuario.
    goto :FINAL
)

echo [*] ExifTool no detectado. Intentando instalacion automatica con winget...
where winget >nul 2>nul
if %errorlevel% equ 0 (
    winget install --id OliverBetz.ExifTool --silent --accept-package-agreements --accept-source-agreements
    if %errorlevel% equ 0 (
        echo [+] ExifTool instalado exitosamente.
        goto :FINAL
    )
)

echo.
echo [AVISO] No se pudo instalar ExifTool de manera automatica.
echo Si el etiquetador de fotos no encuentra ExifTool, puede descargarlo gratuitamente
echo desde https://exiftool.org/ y copiar exiftool.exe en su carpeta de Windows.
echo.

:FINAL
echo.
echo =====================================================================
echo  INSTALACION FINALIZADA SATISFACTORIAMENTE
echo =====================================================================
echo Ya puede ejecutar los siguientes programas de trabajo:
echo  - 1_sincronizar_relojes.bat  (Antes de despegar, con cable USB)
echo  - 2_grabar_telemetria.bat    (Durante el vuelo, con antena de 915 MHz)
echo  - 3_vincular_vuelo_dji.bat   (Al finalizar el vuelo, para procesar fotos)
echo =====================================================================
echo.
pause
