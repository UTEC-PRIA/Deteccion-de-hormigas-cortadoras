# Drone Mission Control Dashboard 🚁📸

Un framework web integral y automatizado para la gestión de misiones de drones (ej. quadcopters F450 con Pixhawk 2.4.8) con integración **100% inalámbrica** para cámaras GoPro (probado con HERO9 y superior).

Este software está diseñado específicamente para que operadores sin experiencia técnica avanzada puedan configurar sus vuelos, conectar hardware, visualizar telemetría en tiempo real y, sobre todo, generar de forma automática un **dataset georreferenciado** (fotos sincronizadas con latitud y longitud GPS) sin la necesidad de conectar cables o realizar copias manuales.

---

## 🎯 ¿Qué hace esta aplicación?

El problema clásico en misiones de fotogrametría o recolección de datos con drones custom (Pixhawk + GoPro) es la tediosa sincronización de los datos de vuelo y las imágenes capturadas. Esta aplicación unifica todo el proceso en una interfaz web tipo "Asistente" (Wizard) paso a paso:

1. **Configura la cámara** a distancia.
2. **Obtiene datos en vivo** del drone (telemetría MAVLink).
3. **Inicia y monitorea el vuelo**.
4. **Detecta el aterrizaje de forma autónoma**.
5. **Se conecta de nuevo a la GoPro, descarga los medios y cruza el tiempo de las fotos con los registros del GPS** para entregarte un archivo `.csv` final listo para análisis.

## 🛠️ Requisitos de Hardware

- **Drone**: Controlador de vuelo compatible con MAVLink (ej. Pixhawk 2.4.8 con firmware ArduPilot/PX4).
- **Telemetría**: Radios SiK (un módulo en el drone, el otro conectado por USB a la computadora base).
- **Cámara**: GoPro HERO 9, 10, 11 o 12. *(Nota: La GoPro debe contar con batería y una tarjeta SD instalada)*.
- **Computadora Base**: Laptop preferentemente con Ubuntu/Linux, con Bluetooth y WiFi funcionales.

---

## ⚙️ Instalación Fácil (One-Click)

Hemos incluido un script de instalación automatizado para preparar tu entorno en sistemas basados en Ubuntu/Debian. Este script instala Python, crea entornos virtuales, instala dependencias y crea un acceso directo en tu escritorio.

Abre una terminal en la carpeta del proyecto y ejecuta:

```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

Al finalizar, verás un icono de una "hormiga" en tu escritorio llamado `DroneMissionControl.desktop`. Al hacer doble clic en él, el servidor se iniciará automáticamente y se abrirá tu navegador por defecto mostrando la aplicación.

Si prefieres ejecutarlo de forma manual desde la terminal:
```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```
Y luego visita en tu navegador: `http://localhost:8000`

---

## 🗺️ Guía de Uso Paso a Paso (El Asistente)

La interfaz gráfica consta de 5 pasos principales que te guiarán de principio a fin.

### Paso 1: Configuración de la Misión
Aquí decides qué datos quieres recolectar.
- **Nombre de la Misión**: Para identificar los archivos y carpetas generados.
- **Modo de Captura**: Puedes elegir "Foto" (tomar fotografías periódicamente, por ejemplo cada 2 segundos) o "Video" (grabación continua).
*Una vez presiones Confirmar Misión, la app guardará los parámetros para aplicarlos más adelante.*

### Paso 2: Conexión con la GoPro (Totalmente Inalámbrico)
Olvídate de los cables. La aplicación se encarga de la conexión de la siguiente manera:
1. Asegúrate de encender tu GoPro. Ve a **Preferencias > Conexiones Inalámbricas** y selecciona "Conectar Dispositivo" o ponla en modo emparejamiento.
2. En la interfaz web, haz clic en **"Conectar Inalámbrico"**.
3. **¿Qué sucede internamente?** El sistema buscará tu cámara usando Bluetooth (BLE). Una vez vinculada, a través de Bluetooth le ordenará a la cámara encender su propia red WiFi (Access Point). Finalmente, usando el administrador de redes del sistema (`nmcli`), conectará tu laptop al WiFi de la GoPro de manera casi instantánea y robusta.
4. Tras conectar exitosamente, verás un check verde indicando que la cámara está lista.

### Paso 3: Enlace de Telemetría MAVLink
Para este paso, tu módulo receptor de radio SiK ya debe estar conectado a un puerto USB de tu PC y el drone debe estar encendido (la radio del drone parpadeará en verde fijo al emparejarse con el de la PC).
- **Puerto Serie**: Elige el puerto correspondiente a tu radio (usualmente `/dev/ttyUSB0`).
- **Baudrate**: Generalmente es `57600`.
- Haz clic en **Conectar Telemetría**.
- Una vez conectado, se activará el router en segundo plano. Esto permite que el sistema monitoree la telemetría para sus automatizaciones y, al mismo tiempo, deje libre un puerto UDP (por ejemplo, el 14550) en tu PC. Gracias a esto, ¡puedes abrir *Mission Planner* o *QGroundControl* simultáneamente si deseas control manual extra!

### Paso 4: Vuelo y Dashboard en Vivo
Este es tu panel de control durante el vuelo real.
- Aquí verás el **estado completo del dron**: un mapa satelital con la posición actual en vivo, indicadores de altitud, cantidad de satélites GPS fijados, porcentaje de batería de la Pixhawk, y modo de vuelo (ej. LOITER, AUTO, RTL).
- **Captura Automática**: Cuando armas el drone y despegas, el sistema lo detecta e inicia la captura en la GoPro automáticamente.
- **Aterrizaje**: El sistema se da cuenta autónomamente cuándo el drone ha aterrizado e inmediatamente **detiene** la grabación/captura en la GoPro.

### Paso 5: Sincronización y Descarga (Post-Vuelo)
Al aterrizar el drone, el sistema pasa a la fase de recolección de datos:
1. **Reconexión Automática**: El sistema se vuelve a conectar vía WiFi a la GoPro usando las credenciales memorizadas en el Paso 2.
2. **Descarga**: Copia automáticamente las fotos o videos capturados durante ese vuelo específico desde la cámara a tu PC.
3. **Sincronización de Logs**: Compara los registros de los sensores MAVLink (latitud, longitud, altitud) guardados y correlaciona el tiempo (Timestamp) de cada fotografía con la posición GPS exacta que el drone tenía en ese mismo milisegundo.
4. **Archivo Final**: Te genera un archivo `.csv` (Data Set final) y la carpeta con las imágenes, listo para usar con tu software de IA o fotogrametría (como WebODM).

---

## 🧪 Modo Simulación (Ideal para Pruebas)

Si quieres aprender a usar la herramienta sin necesidad de encender un dron o conectar una cámara, ¡utiliza el modo demo!
En la esquina superior derecha del panel web verás un interruptor llamado **"Modo Simulación"**.
- Al activarlo, puedes navegar libremente por todos los pasos.
- Emula la conexión a una GoPro (sin Bluetooth ni WiFi reales).
- Genera datos sintéticos de MAVLink para simular un despegue, vuelo en círculo y aterrizaje en el mapa de forma automática.
- Genera imágenes locales "falsas" para que veas cómo funciona el proceso de descarga y la construcción final del `.csv`.

---

## 🛠️ Para Desarrolladores

Si deseas contribuir al código, entender a fondo la máquina de estados o adaptar este sistema para tu empresa/proyecto universitario, te recomendamos encarecidamente revisar la documentación extendida:

> **[📝 Ver Guía Completa para Desarrolladores (DEVELOPER_GUIDE.md)](DEVELOPER_GUIDE.md)**
*(Incluye arquitectura de módulos, explicación del enrutamiento MAVLink con retransmisión local UDP, y la implementación de la API OpenGoPro).*

### Estructura de Módulos Core:
* `main.py`: Punto de entrada, Servidor FastAPI + WebSockets para el Frontend.
* `mission_manager.py`: Cerebro principal. Implementa una máquina de estados finitos que reacciona a los eventos del drone y controla la GoPro.
* `gopro_manager.py`: Lógica de conexión Bluetooth/WiFi mediante `open_gopro` y el sistema operativo. Control avanzado de captura.
* `telemetry_manager.py` / `mavproxy_router.py`: Manejan la recepción de paquetes binarios MAVLink y su retransmisión por redes UDP.
* `sync_engine.py`: Encargado de la extrapolación matemática (Interpolación lineal del tiempo) para sincronizar metadatos EXIF con coordenadas espaciales.
