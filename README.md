# Sistema de Telemetria y Georreferenciacion UAV (UTEC-PRIA)
### Deteccion de Caminos de Hormigas Cortadoras

Plataforma operativa para el relevamiento aereo con cuadricoptero F450 (Pixhawk 2.4.8 / ArduPilot) y camara GoPro HERO13 Black instalada en la parte inferior orientada hacia el suelo (Nadir).

El sistema permite ver la telemetria en tiempo real a traves de una radio de 915 MHz en una interfaz web local (`http://localhost:8000`), sincronizar previamente los relojes por cable USB, y al finalizar el vuelo, descargar automaticamente las fotos de la camara e incrustar los metadatos en formato nativo **DJI Mini 2 SE** (EXIF estandar y etiquetas XMP `drone-dji`).

Las fotografias resultantes son compatibles de forma directa con software de fotogrametria y GIS como **WebODM, Pix4D, Agisoft Metashape, QGIS y ArcGIS**.

---

## 1. Instalacion Rapida (Solo la primera vez)

### En Windows
Haga doble clic en el archivo:
```text
instalar_windows.bat
```
Instala automaticamente las dependencias de Python y la herramienta de metadatos ExifTool.

### En Ubuntu / Debian
Abra una terminal en la carpeta del proyecto y ejecute:
```bash
chmod +x *.sh
./instalar_ubuntu.sh
```
Instala las dependencias del sistema operativo (`libimage-exiftool-perl`, `python3-venv`) y configura los permisos del puerto serie (`dialout`).

---

## 2. Puesta en Marcha (Un Clic)

* **En Windows:** Doble clic en `iniciar_dashboard.bat`
* **En Ubuntu:** Ejecutar en terminal `./iniciar_dashboard.sh`

El programa abrira automaticamente su navegador en:  
**`http://localhost:8000`**

---

## 3. Flujo de Trabajo en Campo (3 Pasos)

### Paso 1: Pre-Vuelo (Conectar equipos por cable USB)
1. Encienda la GoPro HERO13. En la pantalla tactil: *Preferencias* -> *Conexiones* -> *Conexion USB* -> Verifique que este en **GoPro Connect**.
2. Conecte la GoPro y la Pixhawk por cable USB a la computadora.
3. En la pagina web (`http://localhost:8000`), haga clic en **[Sincronizar Relojes]**.  
   El sistema calibra la hora interna de la camara con la hora atomica del GPS de la Pixhawk (diferencia menor a 0.05 segundos) y registra las fotos previas.
4. Desconecte la GoPro y montela debajo del dron mirando hacia abajo.

### Paso 2: Durante el Vuelo (Radio de 915 MHz)
1. Conecte la antena USB de 915 MHz a la computadora.
2. En la pagina web, haga clic en el boton verde **[Comenzar Grabacion]**.  
   Vera en vivo: altura relativa sobre el suelo, modo de vuelo, voltaje de bateria, satelites GPS y rumbo.
3. Inicie el disparo en la GoPro y realice el vuelo del dron.

### Paso 3: Al Aterrizar (Descarga y Procesamiento)
1. Conecte la GoPro por cable USB a la computadora.
2. En la pagina web, haga clic en el boton rojo **[Finalizar y Procesar]**.  
   El sistema de forma automatica:
   * Cierra el registro de vuelo (`telemetria.csv`).
   * Descarga a la computadora solo las fotos nuevas tomadas en el vuelo (en `vuelos/NOMBRE_MISION/fotos/`).
   * Escribe las coordenadas GPS y la altura relativa en formato DJI Mini 2 SE en cada foto.
3. Al finalizar, presione el boton **[Abrir Carpeta de Fotos]** para ver los resultados listos para fotogrametria.

---

## 4. Estructura de Metadatos Inyectados (DJI Mini 2 SE)

| Etiqueta | Ejemplo | Descripcion |
| :--- | :--- | :--- |
| **Make** | `DJI` | Fabricante reconocido para perfiles de software. |
| **Model** | `Mini 2 SE` | Modelo de camara / aeronave. |
| **GPSLatitude** | `34 deg 34' 55.6" S` | Latitud WGS-84 precisa al instante de captura. |
| **GPSLongitude** | `58 deg 25' 17.7" W` | Longitud WGS-84 precisa al instante de captura. |
| **GPSAltitude** | `68.50 m Above Sea Level` | Altura sobre el nivel del mar (MSL). |
| **RelativeAltitude** | `+25.30` | Altura real sobre el suelo (permite escalar el tamano del pixel). |
| **AbsoluteAltitude** | `+68.50` | Altura geodesica de vuelo. |
| **GimbalPitchDegree**| `-90.0` | Camara apuntando perpendicularmente hacia el suelo (Nadir). |
| **GimbalRollDegree** | `0.0` | Horizonte estabilizado por la propia GoPro. |
| **FlightYawDegree** | `145.8` | Rumbo de avance de la aeronave. |

*Nota sobre Videos:* Si en lugar de fotos se grabo video continuo (`.MP4`), el sistema genera automaticamente el archivo de subtitulos de telemetria `.SRT` correspondiente.

---

## 5. Documentacion PDF

El manual operativo completo con diagramas y protocolo de campo impreso se encuentra en la raiz del repositorio:  
**`Manual_Operativo_Telemetria_GoPro_DJI.pdf`**
