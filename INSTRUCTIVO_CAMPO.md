# Manual Operativo de Telemetria, Sincronizacion y Georreferenciacion en Formato DJI Mini 2 SE

**Proyecto UAV UTEC-PRIA**: Deteccion de caminos de hormigas cortadoras  
**Plataforma**: Cuadricoptero F450 (Pixhawk 2.4.8 con ArduPilot) + GoPro HERO13 Black  
**Compatibilidad**: Windows 10/11 y Ubuntu Linux (sin necesidad de conocimientos de programacion)

---

## 1. Descripcion General del Sistema

El sistema cuenta ahora con un **Dashboard Web Local (`http://localhost:8000`)** que unifica todo el flujo de trabajo en una sola pantalla amigable e intuitiva:

1. **Pre-Vuelo (Cables conectados a la PC):** Detecta la GoPro HERO13 Black y la Pixhawk por cable USB. Un boton permite sincronizar los relojes al milisegundo antes de salir a volar.
2. **Durante el Vuelo (Radio 915 MHz conectada a la PC):** Al pulsar *Comenzar Grabacion*, recolecta la telemetria en tiempo real por la antena de 915 MHz, mostrando en vivo: modo de vuelo, altura sobre el suelo, satelites, rumbo y voltaje de bateria.
3. **Al Aterrizar:** Al conectar la camara por USB y pulsar *Finalizar y Procesar*, el sistema:
   - Descarga automaticamente por cable USB todas las fotos o videos tomados durante el vuelo a la memoria de la computadora.
   - Inyecta de forma automatica los metadatos de un **DJI Mini 2 SE** (EXIF WGS-84 + XMP `drone-dji:RelativeAltitude`, etc.).
   - Ofrece un boton para abrir directamente la carpeta con las fotos etiquetadas listas para fotogrametria (WebODM, Pix4D, Agisoft Metashape, QGIS).

---

## 2. Puesta en Marcha (Un Clic)

### En Windows
Haga doble clic en el archivo:  
**`iniciar_dashboard.bat`**  
*(Se abrira automaticamente su navegador web en `http://localhost:8000`)*.

### En Ubuntu
Ejecute en la terminal:  
```bash
./iniciar_dashboard.sh
```
*(Se abrira automaticamente su navegador web en `http://localhost:8000`)*.

---

## 3. Guia de Uso del Dashboard Web

### 3.1. Antes de Volar (Pre-Vuelo)
1. Encienda la GoPro HERO13 Black. En su pantalla tactil vaya a:  
   *Preferencias* -> *Conexiones* -> *Conexion USB* -> Verifique que este seleccionado **GoPro Connect**.
2. Conecte la GoPro y la Pixhawk por cable USB a la computadora.
3. En el dashboard web (`http://localhost:8000`), vera el estado de ambos dispositivos.
4. Haga clic en el boton azul **[Sincronizar Relojes]**.  
   El sistema ajustara la hora exacta del reloj interno de la camara y registrara la lista de fotos previas para saber exactamente cuales seran las fotos nuevas del vuelo.
5. Desconecte la GoPro y montela perpendicular al suelo (Nadir) en el dron.

### 3.2. Durante el Vuelo
1. Enrosque la antena al receptor USB de 915 MHz y conectelo a la computadora.
2. En la pagina web, escriba el nombre de la mision (ej. `Vuelo_Lote_1`).
3. **Inicio y Desconexion de la GoPro:**
   * La GoPro HERO13 cuenta con bateria interna propia (Enduro).
   * Puede presionar **[Grabar Camara]** desde el dashboard para confirmar el encendido por software antes de desconectarla, o presionar el boton superior del obturador fisico de la GoPro una vez montada.
   * **Al desconectar el cable USB, la camara continuara grabando de forma ininterrumpida y autonoma en su tarjeta SD interna.** El dashboard mantendra el indicador visual `GRABANDO EN VUELO (Autonoma)`.
4. Haga clic en **[Comenzar Grabacion]** en el dashboard.
5. Vera el indicador cambiar a rojo: `GRABANDO EN VIVO` y vera los numeros de altura, satelites y bateria 3S actualizandose segundo a segundo.
6. Realice el vuelo del dron sobre el lote de estudio.

### 3.3. Al Aterrizar (Descarga y Procesamiento Automatico)
1. Conecte nuevamente el cable USB-C de la GoPro a la computadora.
2. En la pagina web, haga clic en el boton rojo **[Finalizar y Procesar]**.
3. El sistema de forma automatica:
   - Cerrara los registros de vuelo (`telemetria.csv` y `telemetria.tlog`).
   - Se comunicara con la GoPro por cable USB a alta velocidad y descargara a la PC solo las fotos y videos capturados durante este vuelo (en `vuelos/NOMBRE_MISION/fotos/`).
   - Inyectara los metadatos exactos de un dron DJI Mini 2 SE en cada foto.
4. Al terminar la barra de progreso, aparecera el mensaje de confirmacion y un boton para **[Abrir Carpeta de Fotos]**.

---

## 4. Estructura de Metadatos Inyectados (DJI Mini 2 SE)

| Etiqueta | Ejemplo | Descripcion |
| :--- | :--- | :--- |
| **Make** | `DJI` | Fabricante reconocido para perfiles de software. |
| **Model** | `Mini 2 SE` | Modelo de dron y camara. |
| **GPSLatitude** | `34 deg 34' 55.6" S` | Latitud WGS-84 precisa al milisegundo. |
| **GPSLongitude** | `58 deg 25' 17.7" W` | Longitud WGS-84 precisa al milisegundo. |
| **GPSAltitude** | `68.50 m Above Sea Level` | Altura ortometrica sobre el nivel del mar. |
| **RelativeAltitude** | `+25.30` | Altura sobre el suelo / despegue (escala metrica del pixel). |
| **AbsoluteAltitude** | `+68.50` | Altura geodesica de referencia. |
| **GimbalPitchDegree**| `-90.0` | Inclinacion de camara perpendicular hacia abajo (Nadir). |
| **FlightYawDegree** | `145.8` | Rumbo de la aeronave respecto al norte. |

---

## 5. Documento PDF Formal

En la raiz del repositorio se encuentra el documento impreso:  
**`Manual_Operativo_Telemetria_GoPro_DJI.pdf`**  
Contiene la version formal con tablas tecnicas y lista de chequeo de campo.
