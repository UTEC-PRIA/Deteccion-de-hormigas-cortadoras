# Informe de Avance: Componente Prototipo UAV, Telemetria y Georreferenciacion

**Proyecto:** Deteccion y Monitoreo de Hormigas Cortadoras mediante Vehiculos Aereos No Tripulados  
**Institucion:** Universidad Tecnologica del Uruguay (UTEC) - Programa de Investigacion en Informatica Aplicada (PRIA)  
**Ambito de Aplicacion:** Sistemas Silvopastoriles y Agroforestales

---

## 4. Sintesis del Sistema Desarrollado

### 4.1. Descripcion General y Flujo de Trabajo
El sistema desarrollado constituye una plataforma integral para la adquisicion, registro y georreferenciacion de datos aerofotogrametricos de ultra-alta resolucion orientada a la identificacion de senderos y nidos de hormigas cortadoras (*Acromyrmex* y *Atta*) en parcelas silvopastoriles.

El flujo operativo se estructura en cuatro etapas consecutivas:
1. **Adquisicion Aerea:** Un cuadricoptero F450 equipado con una controladora de vuelo Pixhawk 2.4.8 recorre la superficie de interes a una altitud relativa nominal de 25 metros. La camara optica de alta definicion (GoPro HERO13 Black) captura video continuo en resolucion 4K a 30 cuadros por segundo, orientada perpendicularmente hacia el terreno (posicion Nadir, -90.0°).
2. **Telemetria en Tiempo Real:** Mediante un enlace de radioenlace SiK de 915 MHz, la estacion terrena recibe a 4 Hz las coordenadas geograficas WGS-84, la altitud relativa, la actitud angular (alabeo, cabeceo y rumbo) y el voltaje de la bateria LiPo 3S del vehiculo, almacenandose en registros sincronizados de texto (`telemetria.csv`) y binarios MAVLink (`telemetria.tlog`).
3. **Division y Procesamiento Post-Vuelo:** Al retornar la aeronave, el video 4K es transferido y dividido algoritmicamente en fotogramas fijos a una tasa configurable de 1 fotograma por segundo (obteniendo un solapamiento longitudinal del 90%). Cada cuadro recibe una marca de tiempo temporal interpolada con precision de sub-segundo con respecto al reloj GPS.
4. **Estandarizacion e Inyeccion de Metadatos:** Los fotogramas individuales son procesados mediante una rutina automatica por lotes que inyecta etiquetas EXIF estandar y metadatos XMP en formato nativo **DJI Mini 2 SE** (`XMP-drone-dji`). Esto garantiza compatibilidad directa, sin configuracion adicional, con plataformas de fotogrametria (WebODM, Pix4D, Agisoft Metashape) y sistemas de informacion geografica (QGIS, plataforma AntTrack).

### 4.2. Diagrama en Bloques del Sistema

```
+-------------------------------------------------------------------------+
|                       SEGMENTO AEREO (AERONAVE)                         |
|                                                                         |
|  [Bateria LiPo 3S] ---> [Modulo Sensor Potencia] ---> [Pixhawk 2.4.8]  |
|                                                              |          |
|  [Brujula / GNSS u-blox M8N] --------------------------------+          |
|                                                              |          |
|  [Radio SiK 915 MHz Aire] <======================+           |          |
|                                                  |           |          |
|  [GoPro HERO13 Black]                            |           |          |
|  - Video 4K 30 FPS Nadir (-90°)                  |           |          |
|  - Estabilizacion HyperSmooth                    |           |          |
|  - Almacenamiento en microSD                     |           |          |
+--------------------------------------------------|-----------|----------+
                                                   |           |
                              Enlace 915 MHz (4Hz) |           | Enlace USB
                              MAVLink Telemetria   |           | (Pre/Post Vuelo)
                                                   v           v
+-------------------------------------------------------------------------+
|                    ESTACION TERRENA DE CONTROL (PC)                     |
|                                                                         |
|  [Dashboard Local FastAPI / Web] <--- [Radio SiK 915 MHz Tierra USB]    |
|  - Autoescaneo activo de hardware previo al despegue                    |
|  - Monitoreo en vivo de bateria 3S, altitud, satelites y enlace         |
|  - Registro simultaneo en telemetria.csv y telemetria.tlog              |
+-------------------------------------------------------------------------+
                                                   |
                                                   v Procesamiento Post-Vuelo
+-------------------------------------------------------------------------+
|                  MOTOR DE PROCESAMIENTO Y GEORREFERENCIACION            |
|                                                                         |
|  1. Descarga automatica de video 4K (MP4)                               |
|  2. Descomposicion en fotogramas a 1 FPS (OpenCV)                       |
|  3. Interpolacion temporal sub-segundo con telemetria.csv               |
|  4. Inyeccion batch de metadatos EXIF / XMP drone-dji (ExifTool)        |
|  5. Generacion de subtitulos de telemetria SRT                          |
+-------------------------------------------------------------------------+
                                                   |
                                                   v Salida Estandarizada
+-------------------------------------------------------------------------+
|                     PLATAFORMAS RECEPTORAS Y ANALISIS                   |
|                                                                         |
|  - Ortomosaicos y Modelos Digitales de Elevacion (WebODM / Pix4D)       |
|  - Plataforma AntTrack / Modelos de Deteccion de Hormigueros            |
|  - Analisis Espacial y Georreferenciado en QGIS / ArcGIS                |
+-------------------------------------------------------------------------+
```

---

## 5. Avances por Componente

### 5.2. Prototipo UAV

#### 5.2.1. Configuracion del Prototipo y Componentes Integrados
La plataforma aerea se construyo sobre una estructura de cuadricoptero clase F450 con una distancia entre ejes diagonales de 450 mm. La seleccion de componentes responde a criterios de robustez mecanica, disponibilidad de repuestos y estabilidad aerodinamica:
* **Controladora de Vuelo:** Pixhawk 2.4.8 con firmware ArduCopter. Incorpora sensores inerciales triaxiales redundantes, barometro de precision y microprocesador STM32F427.
* **Sistema de Navegacion GNSS:** Modulo Radiolink SE100 con receptor u-blox M8N y brujula digital integrada, montado sobre un mastil vertical de 14 cm para aislar el magnetometro de los campos electromagneticos generados por las lineas de alimentacion de potencia.
* **Sistema de Propulsion:** Cuatro motores *brushless* de 920 KV acoplados a helices autoajustables de 9.4 x 5.0 pulgadas, controlados por variadores electronicos de velocidad (ESC) de 30 A.
* **Modulo de Potencia y Bateria:** Bateria de polimero de litio (LiPo) de 3 celdas (3S, 11.1 V nominal, capacidad 4200-5200 mAh). El sensado se realiza mediante un modulo de potencia analogo conectado a las entradas ADC de la controladora (Pin 13 para tension y Pin 14 para corriente).
* **Enlace de Datos:** Modems de telemetria por radio SiK / 3DR Radio a 915 MHz (potencia de 500 mW), operando a 57600 baudios, comunicando la aeronave con la terminal terrena.

#### 5.2.2. Sensor Optico y Sistema de Estabilizacion
Para la obtencion de imagenes con suficiente resolucion en tierra (GSD inferior a 1.0 cm/pixel a 25 m de altura) se selecciono una camara GoPro HERO13 Black:
* **Soporte Mecanico Nadir:** Se diseno y fabrico en impresion 3D un soporte rigido especifico adosado a la base inferior de la placa del F450, asegurando una orientacion fija hacia el cenit del suelo (-90.0° de cabeceo).
* **Estabilizacion sin Gimbal Fisico:** Con el proposito de maximizar la autonomia de vuelo y reducir el peso util y la complejidad de fallos mecanicos, se prescindio de un cardan motorizado (gimbal). En su lugar, se aprovecha el algoritmo de estabilizacion electronica de horizonte y reduccion de vibraciones integrado en el sensor de la camara (*HyperSmooth* con bloqueo de horizonte).
* **Modo de Captura Estandarizado:** Se establecio por programa la configuracion predeterminada en resolucion 4K UHD (3840 x 2160 pixeles) a 30 fotogramas por segundo, con relacion de aspecto 16:9 y perfil de color optimizado para contraste de vegetacion.

#### 5.2.3. Pruebas Realizadas y Resultados Obtenidos
1. **Calibracion de Telemetria de Bateria:** Se efectuo la calibracion precisa de los divisores resistivos de la Pixhawk mediante comparacion con multimetro patron de banco, configurando `BATT_VOLT_MULT = 10.1` y estableciendo alarmas de seguridad (`BATT_LOW_VOLT = 10.5 V` y `BATT_CRT_VOLT = 10.2 V`). La lectura en vivo en el panel coincide con un margen de error menor a ±0.05 V.
2. **Pruebas de Autoescaneo y Conectividad en Tierra:** El sistema de autoescaneo en tiempo real valida la tasa de paquetes MAVLink (promedio de 170 a 180 paquetes por segundo en canal 915 MHz), el estado del receptor GNSS y el enlace por cable USB de la camara antes de cada salida a campo.
3. **Verificacion Activa de Grabacion:** El software confirma el inicio efectivo de la captura consultando el registro interno de estado del sensor de codificacion (`status 10 = 1`), eliminando incertidumbres operativas.
4. **Desconexion Dinamica en Vuelo:** Se verifico experimentalmente que al iniciar la grabacion en tierra y desacoplar el cable USB para el despegue, la camara mantiene la grabacion continua sobre su tarjeta microSD sin interrupcion gracias a su bateria interna Enduro, registrandose el evento en el panel como `GRABANDO EN VUELO (Autonoma)`.
5. **Calidad de Georreferenciacion:** En ensayos de extraccion a 1 FPS, el proceso de sincronizacion temporal con `telemetria.csv` logro una consistencia temporal promedio inferior a 40 milisegundos entre la exposicion del cuadro y la posicion calculada por el GNSS.

#### 5.2.4. Ajustes Pendientes
* Instalacion de patas de aterrizaje de mayor despeje vertical para otorgar mayor margen de proteccion al lente de la camara durante tomas de contacto en terrenos con pasturas altas o rugosas.
* Evaluacion de filtros opticos de densidad neutra (ND4/ND8) para optimizar la velocidad de obturacion y eliminar el efecto gelatina (*rolling shutter*) en dias de alta insolacion.

---

### 5.5. Integracion del Sistema

#### 5.5.1. Dashboard Web Unificado de Mision
Se implemento una estacion de control basada en arquitectura web ligera (FastAPI en backend, JavaScript asincrono en frontend) accesible localmente en `http://localhost:8000`:
* **Modulo de Autoescaneo:** Comprobacion en un clic de los tres subsistemas vitales (radio, bateria de vuelo y camara).
* **Modulo de Sincronizacion Horaria:** Sincroniza el reloj interno de la GoPro mediante comandos REST contra el reloj de la computadora o la hora UTC del GNSS Pixhawk, reduciendo la deriva a menos de 50 milisegundos.
* **Control de Mision:** Inicio coordinado de la captura de telemetria a 4 Hz y orden de activacion de la camara.

#### 5.5.2. Algoritmo de Post-Procesamiento y Georreferenciacion DJI Mini 2 SE
Al culminar el vuelo y reconectar la camara por cable USB a la computadora:
1. El sistema transfiere automaticamente el archivo de video `.MP4` a la carpeta estructurada `datos/vuelos/f450_gopro/NOMBRE_MISION/video/`.
2. Mediante la libreria OpenCV, un proceso descompone el video extrayendo fotogramas a una cadencia de 1 imagen por segundo, guardandolos en `datos/vuelos/f450_gopro/NOMBRE_MISION/fotos/`.
3. Por cada fotograma, se calcula su tiempo absoluto $T_k = T_{inicio} + (k / fps)$ y se realiza una interpolacion lineal exacta entre los dos puntos de telemetria mas proximos en `telemetria.csv`.
4. Mediante una ejecucion optimizada por lotes de ExifTool (`-csv=`), se incrustan en las cabeceras de cada archivo JPG las etiquetas estandar de un dron **DJI Mini 2 SE**:
   * Coordenadas geograficas `GPSLatitude`, `GPSLongitude`, `GPSAltitude` (WGS-84).
   * Etiquetas XMP especificas: `XMP-drone-dji:RelativeAltitude` (altura sobre el punto de despegue), `XMP-drone-dji:GimbalPitchDegree = -90.0` (posicion Nadir), `XMP-drone-dji:GimbalRollDegree = 0.0` (horizonte nivelado electronicamente) y `XMP-drone-dji:FlightYawDegree` (rumbo de avance).
5. Se genera de forma suplementaria un archivo de subtitulos de telemetria `.SRT` asociado al video completo.

Esta integracion hace que el lote de fotografias resulte indistinguible para herramientas de fotogrametria respecto a un relevamiento capturado por un dron comercial DJI, permitiendo procesar ortomosaicos a escala metrica precisa en WebODM de manera directa.

---

## 6. Cumplimiento del Plan de Trabajo

| Actividad Prevista | Estado | Grado de Cumplimiento | Evidencia Técnica |
| :--- | :---: | :---: | :--- |
| Ensamble y puesta a punto de plataforma aerea F450 | Completado | 100% | Prototipo operativo con Pixhawk 2.4.8 y GNSS M8N. |
| Integracion de carga util optica en posicion Nadir | Completado | 100% | Soporte 3D rigido a -90.0° con GoPro HERO13 y estabilizacion HyperSmooth. |
| Monitoreo y telemetria en tiempo real por radiofrecuencia | Completado | 100% | Enlace SiK 915 MHz a 4 Hz con guardado dual (`.csv` y `.tlog`). |
| Calibracion de estado de bateria y alarmas de seguridad | Completado | 100% | Sensor analogo LiPo 3S calibrado en EEPROM Pixhawk. |
| Sistema de adquisicion y sincronizacion de imagenes | Completado | 100% | Dashboard local web con autoescaneo y control de obturador. |
| Georreferenciacion e integracion con software fotogrametrico | Completado | 100% | Generacion automatica de fotos 4K con etiquetas DJI Mini 2 SE para WebODM/AntTrack. |

---

## 7. Desvios, Dificultades y Medidas Adoptadas

1. **Limitacion de Carga Util para Gimbal Motorizado de 3 Ejes:**
   * *Dificultad:* El peso de un cardan mecanico comercial de 3 ejes acoplado a la GoPro superaba el limite de peso util del chasis F450, reduciendo drasticamente la autonomia de vuelo a niveles no operativos (< 7 minutos).
   * *Medida Adoptada:* Se prescindio del gimbal mecanico y se diseno un anclaje rigido Nadir cenital (-90.0°), delegando la compensacion angular de alabeo y cabeceo a la tecnologia electronica integrada *HyperSmooth* con bloqueo de horizonte propio de la camara. En los metadatos se fija la actitud de camara a nivel y se registra la actitud angular real del dron en los campos de vuelo de la aeronave.
2. **Gestion del Cableado USB en Vuelo:**
   * *Dificultad:* El protocolo Open GoPro requiere enlace fisico para la transferencia de alta velocidad, pero la aeronave debe volar sin ataduras fisicas.
   * *Medida Adoptada:* Se implemento una rutina de desacople en dos fases: en tierra se utiliza conexion USB para sincronizacion horaria, comprobacion del sensor y disparo; al retirar el cable para volar, el software detecta la ausencia del adaptador en 10 ms (sin bloquear la interfaz) y asume el modo autonomo en microSD. Al aterrizar, la reconexion permite la descarga inmediata y automatica.
3. **Incompatibilidad de Metadatos en Software Fotogrametrico Abierto:**
   * *Dificultad:* Las imagenes con metadatos EXIF genericos carecian de parametros de calibracion de altura relativa respecto al suelo (`RelativeAltitude`), provocando errores de escala metrica en la generacion de ortomosaicos y nubes de puntos densas en WebODM.
   * *Medida Adoptada:* Se diseno un modulo de emulacion de metadatos nativos **DJI Mini 2 SE** (`Make=DJI`, `Model=Mini 2 SE` y espacio de nombres `XMP-drone-dji`), permitiendo que WebODM reconozca perfiles de camara pre-calibrados y dimensione la escena con exactitud centimetrica.

---

## 8. Proxima Etapa: Navegacion Autonoma por Waypoints

Como continuacion del desarrollo del prototipo UAV, se establecen las siguientes lineas de trabajo:
1. **Planificacion de Misiones Fotogrametricas Automatizadas:** Integracion en la estacion de control de una herramienta interactiva para el trazo de poligonos sobre parcelas silvopastoriles y generacion automatica de grillas de vuelo en zig-zag con calculo de solapamiento frontal (80-90%) y lateral (70-80%) en funcion de la resolucion espacial objetivo (GSD ~0.7 cm/pixel a 25 m de altura).
2. **Envio de Misiones por Protocolo MAVLink:** Implementacion del protocolo de mision `MISSION_ITEM_INT` mediante enlace de 915 MHz para transferir la secuencia de waypoints a la memoria no volatil de la Pixhawk 2.4.8.
3. **Automatizacion de Eventos de Carga Util:** Sincronizacion del inicio de grabacion de video 4K 30 FPS al alcanzar el primer waypoint de la grilla de prospeccion, y activacion automatica de la maniobra de retorno a base (`RTL`) y aterrizaje asistido (`LAND`) al finalizar la cobertura del area.
4. **Configuracion de Politicas de Retorno Seguro (Fail-Safe):** Parametrizacion estricta en ArduCopter para retorno automatico inmediato ante caida de tension de la bateria LiPo 3S por debajo de 10.5 V (`FS_BATT_ENABLE = 2`) o ante perdida sostenida del enlace de telemetria por mas de 5 segundos (`FS_GCS_ENABLE = 1`).

---

## 9. Anexos Tecnicos

### Anexo A: Estructura de Metadatos Inyectados por Fotograma (Formato DJI Mini 2 SE)

| Etiqueta EXIF / XMP | Valor Tipico de Ejemplo | Proposito en Fotogrametria / GIS |
| :--- | :--- | :--- |
| `Make` | `DJI` | Identificador de fabricante para carga de perfiles opticos. |
| `Model` | `Mini 2 SE` | Modelo emulado para reconocimiento directo en WebODM y Pix4D. |
| `GPSLatitude` | `34.895420 S` | Latitud WGS-84 interpolada al instante de la captura. |
| `GPSLongitude` | `56.162350 W` | Longitud WGS-84 interpolada al instante de la captura. |
| `GPSAltitude` | `70.00 m` | Altitud sobre el nivel medio del mar (MSL). |
| `XMP-drone-dji:AbsoluteAltitude` | `+70.00` | Altitud geodesica de referencia. |
| `XMP-drone-dji:RelativeAltitude` | `+25.00` | Altura relativa sobre el terreno (escala metrica del pixel). |
| `XMP-drone-dji:GimbalPitchDegree`| `-90.0` | Orientacion Nadir de la camara (vertical hacia el suelo). |
| `XMP-drone-dji:GimbalRollDegree` | `0.0` | Horizonte estabilizado por HyperSmooth. |
| `XMP-drone-dji:FlightYawDegree` | `145.8` | Rumbo de desplazamiento del vehiculo. |
| `DateTimeOriginal` | `2026:11:19 17:30:00` | Marca temporal sincronizada con precision de sub-segundo. |

### Anexo B: Registro de Archivos y Repositorio de Codigo
* **Repositorio Central:** `https://github.com/UTEC-PRIA/Deteccion-de-hormigas-cortadoras`
* **Modulo de Vinculacion y Georreferenciacion:** `vincular_vuelo_dji.py`
* **Estacion Terrena y Servidor Local:** `web_dashboard.py`
* **Script de Calibracion de Bateria LiPo 3S:** `configurar_bateria_3s.py`
* **Generador de Datos Sinteticos para Pruebas:** `generar_datos_artificiales.py`
