# Sistema de Telemetria y Georreferenciacion UAV (UTEC-PRIA)
### Deteccion de Caminos de Hormigas Cortadoras

Plataforma operativa para el relevamiento aereo con cuadricoptero F450 (Pixhawk 2.4.8 / ArduPilot) y camara GoPro HERO13 Black instalada en la parte inferior orientada hacia el suelo (Nadir).

El sistema permite ver la telemetria en tiempo real a traves de una radio de 915 MHz en una interfaz web local (`http://localhost:8000`), realizar autoescaneo activo de hardware, verificar la grabacion real de la camara, monitorear la bateria LiPo 3S, y al finalizar el vuelo, descargar automaticamente las fotos de la camara e incrustar los metadatos en formato nativo **DJI Mini 2 SE** (EXIF estandar y etiquetas XMP `drone-dji`).

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
4. Presione **[Sincronizar Relojes]** para calibrar la hora interna de la camara (< 0.05 s de diferencia) y registrar fotos previas.
5. Puede probar el disparo con los botones **[Grabar Camara]** y **[Detener Camara]** verificando el indicador en pantalla.
6. Desconecte la GoPro y montela en el soporte inferior del dron mirando hacia abajo (Nadir).

### Paso 2: Durante el Vuelo (Radio de 915 MHz)
1. En la pagina web, haga clic en el boton verde **[Comenzar Grabacion]**.  
   El sistema verifica la telemetria y activa la grabacion de la camara si esta conectada por cable. Si vuela en modo autonomo, encienda la grabacion manualmente antes de despegar.
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

*Nota sobre Videos:* Si en lugar de fotos se grabo video continuo (`.MP4`), el sistema genera automaticamente el archivo de subtitulos de telemetria `.SRT` correspondiente.

---

## 6. Documentacion PDF

El manual operativo completo con diagramas y protocolo de campo impreso se encuentra en la raiz del repositorio:  
**`Manual_Operativo_Telemetria_GoPro_DJI.pdf`**
