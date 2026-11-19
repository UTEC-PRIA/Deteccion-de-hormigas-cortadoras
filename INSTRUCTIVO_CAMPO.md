# Manual Operativo de Telemetria, Sincronizacion y Georreferenciacion en Formato DJI Mini 2 SE

**Proyecto UAV UTEC-PRIA**: Deteccion de caminos de hormigas cortadoras  
**Plataforma**: Cuadricoptero F450 (Pixhawk 2.4.8 con ArduPilot) + GoPro HERO13 Black  
**Compatibilidad**: Windows 10/11 y Ubuntu Linux (sin necesidad de conocimientos de programacion)

---

## 1. Descripcion General del Sistema

Este conjunto de herramientas permite operar en campo recolectando telemetria en tiempo real a traves del kit de radio de 915 MHz, sincronizar previamente el reloj interno de la camara GoPro HERO13 Black con la hora atomica del GPS de la Pixhawk por cable USB, y al finalizar la jornada, transformar todas las fotos o videos para que queden con el formato nativo de un dron **DJI Mini 2 SE** (metadatos estandar EXIF y etiquetas propietarias XMP `drone-dji`).

Esto permite procesar el relevamiento en herramientas profesionales como **WebODM, Pix4D, Agisoft Metashape, QGIS, ArcGIS o DJI Terra** sin necesidad de calibraciones manuales complejas.

---

## 2. Instalacion Inicial (Solo se realiza una vez)

### En Windows
1. Conecte la computadora a Internet.
2. Haga doble clic sobre el archivo:
   `instalar_windows.bat`
3. El instalador verificara Python, instalara automaticamente las librerias necesarias e instalara la herramienta de metadatos `ExifTool`.

### En Ubuntu / Debian
1. Abra una terminal en la carpeta del proyecto.
2. Ejecute el siguiente comando:
   ```bash
   chmod +x *.sh
   ./instalar_ubuntu.sh
   ```
3. El instalador configurara las librerias del sistema (`libimage-exiftool-perl`, `python3-venv`) y anadira los permisos necesarios para el puerto serie (`dialout`).

---

## 3. Protocolo de Operacion en Campo (3 Pasos Sencillos)

### Paso 1: Pre-Vuelo (Sincronizacion de Relojes por Cable USB)
*Momento: Antes de despegar, en el taller, mesa de trabajo o vehiculo.*

1. Encienda la GoPro HERO13 Black. En su pantalla tactil, deslice hacia abajo y vaya a:
   `Preferencias` -> `Conexiones` -> `Conexion USB` -> Seleccione **GoPro Connect**.
2. Conecte la GoPro a la computadora mediante cable USB-C.
3. Conecte la controladora Pixhawk a la computadora mediante cable USB (o encienda el dron para enlace de radio).
4. Ejecute el sincronizador:
   - En Windows: Doble clic en `1_sincronizar_relojes.bat`
   - En Ubuntu: Doble clic o terminal `./1_sincronizar_relojes.sh`
5. La pantalla informara el nivel de bateria de la camara y confirmara la calibracion del reloj con precision de milisegundos.
6. Desconecte el cable USB de la camara y montela orientada perpendicularmente hacia el suelo (vista Nadir) en el dron.

---

### Paso 2: Durante el Vuelo (Grabacion de Telemetria en Vivo con Radio 915 MHz)
*Momento: En el lote o campo mientras el dron esta en el aire.*

> **ADVERTENCIA OBLIGATORIA:** Enrosque siempre las antenas a las radios antes de conectarlas a la energia o a la computadora. Transmitir sin antena dana irreversiblemente el amplificador de radiofrecuencia.

1. Conecte la antena receptora de 915 MHz al puerto USB de la computadora.
2. Ejecute el grabador:
   - En Windows: Doble clic en `2_grabar_telemetria.bat`
   - En Ubuntu: Doble clic o terminal `./2_grabar_telemetria.sh`
3. El programa listara los puertos detectados. Presione ENTER para aceptar la opcion sugerida (ej. `COM5` o `/dev/ttyUSB0`).
4. En cuanto el dron se encienda, vera la telemetria actualizandose cada segundo:
   `Modo: LOITER | Sats: 14 | AltRel: 25.3m | Bat: 11.6V | Lat: -34.582104 | Lon: -58.421590`
5. Inicie la grabacion de video o fotos a intervalos en la GoPro y realice el vuelo planificado.
6. Al aterrizar, presione las teclas `Ctrl + C` en la ventana de la computadora para detener y guardar la grabacion.
7. Los datos quedaran archivados en la carpeta `registros_vuelo/vuelo_FECHA_HORA/`:
   - `telemetria.csv`: Archivo en formato tabla con 4 lecturas de posicion por segundo.
   - `telemetria.tlog`: Archivo binario compatible con Mission Planner para reproducir el vuelo.

---

### Paso 3: Post-Vuelo (Vinculacion y Generacion de Formato DJI Mini 2 SE)
*Momento: Al finalizar los vuelos del dia.*

1. Extraiga la tarjeta microSD de la GoPro y copie las fotos a su computadora (ejemplo: `C:\Vuelos\Mision_01`).
2. Ejecute el vinculador:
   - En Windows: Doble clic en `3_vincular_vuelo_dji.bat`
   - En Ubuntu: Doble clic o terminal `./3_vincular_vuelo_dji.sh`
3. El programa solicitara dos datos simples:
   - **Archivo de telemetria**: Arrastre a la ventana el archivo `telemetria.csv` obtenido en el Paso 2 (o el archivo `.BIN` descargado de la Pixhawk) y presione ENTER.
   - **Carpeta de fotos**: Arrastre la carpeta con las fotos de la GoPro y presione ENTER.
4. El sistema realizara la interpolacion temporal exacta e inyectara los metadatos en cada imagen.
5. Al finalizar, cada imagen contendra latitud, longitud, altitud sobre el mar y altitud relativa sobre el suelo en formato nativo DJI Mini 2 SE.

*Nota para Videos:* Si en lugar de fotos grabo un archivo de video (`.MP4`), arrastre el archivo de video. El sistema generara el archivo de subtitulos de telemetria `.SRT` correspondiente.

---

## 4. Estructura de Datos Incrustados en Cada Fotografia

| Etiqueta | Ejemplo | Descripcion y Utilidad |
| :--- | :--- | :--- |
| **Make** | `DJI` | Identificador de fabricante reconocido por software de fotogrametria. |
| **Model** | `Mini 2 SE` | Modelo de dron / camara. Permite asociar parametros focales conocidos. |
| **GPSLatitude** | `34 deg 34' 55.6" S` | Latitud WGS-84 en el instante de captura. |
| **GPSLongitude** | `58 deg 25' 17.7" W` | Longitud WGS-84 en el instante de captura. |
| **GPSAltitude** | `68.50 m Above Sea Level` | Altura ortometrica sobre el nivel del mar (MSL). |
| **RelativeAltitude** | `+25.30` | Altura relativa sobre el suelo/despegue. Clave para calcular el tamano real del pixel en tierra. |
| **AbsoluteAltitude** | `+68.50` | Altura geodesica absoluta. |
| **GimbalPitchDegree**| `-90.0` | Orientacion de camara perpendicular hacia abajo (Nadir). |
| **FlightYawDegree** | `145.8` | Rumbo de la aeronave respecto al norte. |
| **FlightRollDegree**| `1.2` | Inclinacion lateral del dron al momento del disparo. |
| **FlightPitchDegree**| `-0.5` | Inclinacion longitudinal del dron al momento del disparo. |

---

## 5. Documentacion en Formato PDF

Se incluye en la raiz del repositorio el documento:  
**`Manual_Operativo_Telemetria_GoPro_DJI.pdf`**  
Contiene la version formal con diagramas de flujo, tablas comparativas y protocolo impreso de campo listo para llevar al terreno.
