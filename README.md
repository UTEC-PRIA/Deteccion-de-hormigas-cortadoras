# Drone Mission Control Dashboard 🚁

Framework web automatizado para la gestión de misiones de drones (ej. F450 con Pixhawk 2.4.8) e integración inalámbrica con cámaras GoPro (HERO9+). 

Este software está diseñado para que operadores no técnicos puedan configurar misiones, visualizar telemetría en tiempo real y generar un dataset georreferenciado (fotos sincronizadas con datos GPS) de forma totalmente automática y sin cables.

## 🚀 Arquitectura Inalámbrica (Nuevo)
La GoPro ahora se conecta de manera **100% inalámbrica**, eliminando la necesidad de cables USB en campo:
1. **Conexión Inicial (BLE + WiFi)**: Se escanea y empareja la GoPro vía Bluetooth de bajo consumo (BLE), lo que enciende el punto de acceso WiFi de la cámara automáticamente para la configuración de captura.
2. **Reconexión Post-Vuelo (WiFi Directo)**: Tras el aterrizaje, el sistema se reconecta automáticamente al WiFi de la GoPro (usando las credenciales guardadas previamente) para realizar la descarga de las imágenes y la sincronización con la telemetría.

## ⚙️ Requisitos y Dependencias
* Python 3.8+
* Módulo de telemetría SiK conectado por USB (`/dev/ttyUSB0`) para lectura de MAVLink
* Interfaz de red WiFi gestionada mediante `nmcli` (NetworkManager) en Linux
* Dependencias de Python: `pymavlink`, `open-gopro`, `fastapi`, `websockets`, `Pillow`, `aiofiles`, `uvicorn`

```bash
pip install -r requirements.txt
```

## 🛠️ Estructura del Proyecto
* `main.py`: Servidor FastAPI con WebSockets para telemetría en vivo.
* `mission_manager.py`: Máquina de estados que orquesta el ciclo de la misión (IDLE → PRE_FLIGHT → IN_FLIGHT → LANDING → SYNCING).
* `gopro_manager.py`: Control completo de la cámara mediante el SDK *Open GoPro*, configurando captura y descarga de medios de manera inalámbrica.
* `telemetry_manager.py`: Integración MAVLink para extraer posición GPS, actitud y modos de vuelo, además de simulación de vuelos.
* `sync_engine.py`: Motor de sincronización que extrapola los timestamps de la telemetría MAVLink y los metadatos EXIF de la GoPro para generar el dataset CSV.

## 🗺️ Uso del Asistente (Wizard)
El panel web (`http://localhost:8000`) cuenta con un flujo de 5 pasos:
1. **Misión**: Definir modo de captura (Foto Timelapse / Video).
2. **GoPro (Inalámbrico)**: Conectar mediante BLE + WiFi y armar la captura.
3. **Telemetría**: Conectar el radio SiK a la estación base.
4. **Vuelo**: Dashboard en tiempo real (Mapa Leaflet, altitud, satélites, estado de batería). Detecta automáticamente el aterrizaje.
5. **Resultados**: Reconexión WiFi, descarga automática de fotos y exportación del CSV final.

## 🧪 Modo Simulación
Incluye un modo "Demo Simulación" (botón superior derecho) que genera telemetría sintética de vuelo y archivos simulados para probar todo el flujo sin necesidad de tener el drone encendido.
