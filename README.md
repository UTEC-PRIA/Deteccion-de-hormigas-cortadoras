# Sistema de Telemetria y Georreferenciacion UAV (UTEC-PRIA)
### Deteccion de Caminos de Hormigas Cortadoras

Plataforma operativa para el relevamiento aereo con cuadricoptero F450 (Pixhawk 2.4.8 / ArduPilot) y camara GoPro HERO13 Black instalada en la parte inferior orientada hacia el suelo (Nadir).

El sistema permite ver la telemetria en tiempo real a traves de una radio de 915 MHz en una interfaz web local (`http://localhost:8000`), realizar autoescaneo activo de hardware, verificar la grabacion real de la camara, monitorear la bateria LiPo 3S, y al finalizar el vuelo, descargar automaticamente las fotos de la camara e incrustar los metadatos en formato nativo **DJI Mini 2 SE** (EXIF estandar y etiquetas XMP `drone-dji`).

Las fotografias resultantes son compatibles de forma directa con software de fotogrametria y GIS como **WebODM, Pix4D, Agisoft Metashape, QGIS y ArcGIS**.

## Novedades

El dashboard tiene cuatro pestañas: **Control**, **Vuelos y mapa**, **Imágenes y tags** y **Plan de vuelo**.
Detalle en [CHANGELOG.md](CHANGELOG.md). Plan de vuelo: [docs/PLAN_DE_VUELO.md](docs/PLAN_DE_VUELO.md) (aún sin probar con la aeronave real).

Los metadatos imitan el formato DJI Mini 2 SE por compatibilidad fotogramétrica: las imágenes son de la GoPro.

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
* **En Ubuntu:** Ejecutar en terminal `./ejecutar.sh` (crea el entorno la primera vez) o `./iniciar_dashboard.sh`

El programa abrira automaticamente su navegador en:  
**`http://localhost:8000`**

---

## 3. Funciones Clave Incorporadas

1. **Autoescaneo Activo de Hardware**:  
   Al abrir la aplicacion o presionar *Re-Escanear Todo*, el sistema verifica en vivo:
   * Comunicacion MAVLink con la radio de 915 MHz y paquetes recibidos por segundo.
   * Lectura y porcentaje de la bateria LiPo 3S conectada al dron.
   * Enlace por cable USB con la GoPro HERO13, nivel de bateria y estado de obturador.

2. **Verificacion Real de Grabacion de la Camara**:  
   El inicio y detencion del obturador no solo envia la orden a la camara, sino que consulta directamente el sensor interno de codificacion (`status 10`) de la GoPro HERO13 para asegurar que la camara esta grabando efectivamente antes del despegue.

3. **Monitor y Calibracion de Bateria LiPo 3S**:  
   Configurado para leer el divisor analogo de la Pixhawk 2.4.8 (Pin 13 de voltaje, Pin 14 de corriente) con protecciones configuradas:
   * Rango optimo: 11.4 V - 12.6 V (100% - 40%).
   * Alarma de bateria baja: 10.5 V (3.5 V por celda).
   * Nivel critico: 10.2 V (3.4 V por celda).
   * Se incluye el script `configurar_bateria_3s.bat` / `.sh` para re-aplicar esta configuracion en la EEPROM de la controladora con un solo clic.

---

## 4. Flujo de Trabajo en Campo (3 Pasos)

### Paso 1: Pre-Vuelo (Conectar equipos por cable USB)
1. Encienda la GoPro HERO13. En la pantalla tactil: *Preferencias* -> *Conexiones* -> *Conexion USB* -> Verifique que este en **GoPro Connect**.
2. Conecte la GoPro por cable USB a la computadora y la antena receptora de 915 MHz en otro puerto USB.
3. En la pagina web (`http://localhost:8000`), el sistema realizara el **Autoescaneo** mostrando el estado de la radio, bateria 3S y camara.
4. Presione **[Sincronizar Relojes]** para igualar la hora de la camara a la de la PC; el panel muestra el desfase medido y registra los archivos previos.
5. Puede iniciar el disparo con el boton **[Grabar Camara]** verificando el indicador en pantalla antes de desconectar el cable, o presionar el obturador fisico superior de la camara una vez montada en el dron.
6. **Desconexion para vuelo:** Al desconectar el cable USB, la GoPro HERO13 cuenta con bateria interna propia y continuara grabando ininterrumpidamente en su tarjeta SD. Sin cable el dashboard **no puede comprobarlo**: verifique la luz roja de la camara.
7. Monte la GoPro en el soporte inferior del dron orientada perpendicularmente hacia el suelo (Nadir).

### Paso 2: Durante el Vuelo (Radio de 915 MHz)
1. En la pagina web, haga clic en el boton verde **[Comenzar Grabacion]**.  
   El sistema confirma la telemetria MAVLink activa a traves de la radio de 915 MHz.
2. Vera en vivo: altura relativa sobre el suelo, modo de vuelo, voltaje y porcentaje de bateria 3S, satelites GPS y rumbo.

### Paso 3: Al Aterrizar (Descarga y Procesamiento)
1. Conecte la GoPro por cable USB a la computadora.
2. En la pagina web, haga clic en el boton rojo **[Finalizar y Procesar]**.  
   El sistema de forma automatica:
   * Cierra el registro de vuelo (`telemetria.csv`).
   * Descarga a la computadora solo las fotos nuevas tomadas en el vuelo (en `vuelos/NOMBRE_MISION/fotos/`).
   * Escribe las coordenadas GPS y la altura relativa en formato DJI Mini 2 SE en cada foto.
3. Al finalizar, presione el boton **[Abrir Carpeta de Fotos]** para ver los resultados listos para fotogrametria.

---

## 5. Estructura de Metadatos Inyectados (DJI Mini 2 SE)

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

*Captura de Video 4K 30 FPS y Division Automatica de Fotogramas:*
La camara se configura siempre de manera automatica en **Modo Video 4K a 30 FPS** con estabilizacion electronica HyperSmooth integrada. Al aterrizar y conectar el cable USB, el sistema:
1. Descarga el video `.MP4` completo a `vuelos/NOMBRE_MISION/video/`.
2. Divide el video en imagenes fijas de alta definicion (4K, 3840x2160) al intervalo seleccionado (1 foto/s = 90% solape, 2 fotos/s o 0.5 fotos/s).
3. Calcula la marca de tiempo sub-segundo exacta de cada fotograma ($T_k = T_{inicio} + \frac{k}{fps}$).
4. Interpola la posicion GPS precisa del UAV desde `telemetria.csv`.
5. Inyecta por lotes los metadatos nativos **DJI Mini 2 SE** en cada imagen generada dentro de `vuelos/NOMBRE_MISION/fotos/`.
6. Genera el archivo de subtitulos de telemetria `.SRT` asociado al video.

---

## 6. Capturas de Pantalla y Datos de Ejemplo

### Interfaz del Dashboard Web
* **Vista General con Autoescaneo OK:** [docs/imagenes/dashboard_autoescaneo_ok.png](docs/imagenes/dashboard_autoescaneo_ok.png)
* **Estado de Grabacion en Vivo Verificado:** [docs/imagenes/dashboard_grabando_en_vivo.png](docs/imagenes/dashboard_grabando_en_vivo.png)
* **Estado en Espera (Standby):** [docs/imagenes/dashboard_en_espera.png](docs/imagenes/dashboard_en_espera.png)

### Ejemplos de Salida y Generador de Datos Artificiales
En la carpeta [ejemplos_salida/vuelo_mision_campo_01/](ejemplos_salida/vuelo_mision_campo_01/) y [datos_artificiales/mision_simulada_4k/](datos_artificiales/mision_simulada_4k/) se incluyen conjuntos de datos sinteticos para pruebas inmediatas:
* `telemetria.csv`: Archivo de telemetria a 4 Hz con coordenadas, altura, actitud y voltaje de bateria 3S.
* `video_vuelo_mision_01.MP4`: Video 4K a 30 FPS de patrulla aerea.
* `video_vuelo_mision_01.SRT`: Archivo de subtitulos de telemetria por segundo en formato DJI.
* `fotos/`: Fotografias aereas 4K extraidas del video con metadatos reales nativos de **DJI Mini 2 SE** inyectados (verificables mediante ExifTool o software fotogrametrico WebODM).
* `generar_datos_artificiales.py`: Script para regenerar misiones sinteticas completas con cualquier duracion (`py generar_datos_artificiales.py [segundos]`).

---

## 7. Instrucciones y Prompts para Otras IAs

Para generar nuevos diagramas de arquitectura (Mermaid, PlantUML) o ilustraciones renderizadas en 3D del cuadricoptero F450 y la estacion de tierra con cualquier modelo de IA (Claude, ChatGPT, Midjourney, DALL-E), consulte la guia detallada:  
**[GUIA_PROMPTS_DIAGRAMAS_IA.md](GUIA_PROMPTS_DIAGRAMAS_IA.md)**

---

## 8. Documentacion PDF

El manual operativo completo con diagramas y protocolo de campo impreso se encuentra en la raiz del repositorio:  
**`Manual_Operativo_Telemetria_GoPro_DJI.pdf`**

---

## 9. Siguientes Pasos: Sistema de Navegacion Autonoma por Waypoints

> El diseño, la grilla y la carga de waypoints ya existen en la pestaña Plan de vuelo. Lo que sigue es la hoja de ruta original.

Como siguiente fase de desarrollo para el proyecto de deteccion aerea de hormigas cortadoras con el cuadricoptero F450, se planifica la implementacion de navegacion autonoma por grilla de escaneo:

1. **Planificador de Mision Fotogrametrica (GCS / Dashboard):**
   * Definicion en mapa interactivo de poligonos de inspeccion sobre pasturas y montes.
   * Calculo automatico de pasadas paralelas y waypoints segun GSD deseado (~0.7 cm/pixel a 25m de altura) y solapamiento del 80%-90%.
2. **Carga y Ejecucion de Misiones MAVLink en Pixhawk:**
   * Envio de waypoints (`MISSION_ITEM_INT`) a traves del enlace de telemetria de 915 MHz.
   * Conmutacion al modo de vuelo `AUTO` para despegue, barrido de grilla y retorno.
3. **Sincronizacion de Eventos de Carga Util:**
   * Inicio automatico de grabacion de video 4K 30 FPS al alcanzar el primer waypoint de relevamiento.
   * Finalizacion de grabacion y activacion automatica de `RTL` (Return to Launch) con aterrizaje asistido (`LAND`) al culminar el escaneo.
4. **Protecciones Fail-Safe Avanzadas:**
   * Retorno automatico inmediato (`FS_BATT_ENABLE = 2`) si la bateria LiPo 3S desciende de 10.5 V (3.5 V/celda).
   * Geocerca perimetral de contencion (`FENCE_ENABLE = 1`).

Para consultar la especificacion tecnica y arquitectura completa de esta futura fase, revise el documento:  
**[docs/ROADMAP_NAVEGACION_WAYPOINTS_AUTONOMA.md](docs/ROADMAP_NAVEGACION_WAYPOINTS_AUTONOMA.md)**
