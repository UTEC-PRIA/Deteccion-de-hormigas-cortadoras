# Roadmap y Especificacion de Siguientes Pasos: Navegacion Autonoma por Waypoints

**Proyecto:** Relevamiento Aereo de Hormigas Cortadoras con UAV  
**Institucion:** UTEC - PRIA (Universidad Tecnologica del Uruguay)  
**Aeronave:** Cuadricoptero F450 con Pixhawk 2.4.8 (ArduCopter) y Camara GoPro HERO13 Nadir (-90°)  
**Estado:** Planificado (Futura Fase de Implementacion)

---

## 1. Vision General del Sistema de Navegacion Autonoma

Actualmente, el sistema ejecuta el autoescaneo activo de hardware, monitoreo de bateria LiPo 3S, sincronizacion de reloj con la GoPro HERO13 por USB, telemetria en vivo a 4 Hz via radio SiK 915 MHz, grabacion de video 4K a 30 FPS, division automatica en fotogramas a 1 FPS e incrustacion de metadatos nativos **DJI Mini 2 SE** para WebODM y software fotogrametrico.

El siguiente hito del proyecto consiste en dotar al cuadricoptero de **capacidad de navegacion autonoma por grilla de waypoints (Mision Fotogrametrica Automatizada)**, donde la aeronave despegue, recorra las lineas de escaneo sobre el monte o pastura con solapamiento longitudinal y lateral constante, y regrese al punto de partida (RTL) de manera completamente desatendida.

---

## 2. Arquitectura de la Solucion Planificada

```
+-------------------------------------------------------------+
|                ESTACION DE TIERRA (GCS / PC)                |
|  1. Definicion de poligono de busqueda de hormigueros       |
|  2. Calculo automatico de grilla de waypoints (GSD / Solape)|
|  3. Envio de mision via MAVLink (MISSION_ITEM_INT)          |
+------------------------------+------------------------------+
                               | Radio SiK 915 MHz
                               v
+-------------------------------------------------------------+
|              CONTROLADORA DE VUELO (PIXHAWK 2.4.8)          |
|  1. Modo AUTO: Despegue automatico (NAV_TAKEOFF a 25m)      |
|  2. Navegacion por grilla: Control PID de posicion y rumbo  |
|  3. Geofencing perimetral y proteccion de bateria LiPo 3S   |
|  4. Retorno y Aterrizaje Automatico (RTL / LAND)            |
+------------------------------+------------------------------+
                               | Disparo / Grabacion Continua
                               v
+-------------------------------------------------------------+
|                 CARGA UTIL (GOPRO HERO13)                   |
|  1. Video 4K 30 FPS HyperSmooth Nadir (-90.0°)              |
|  2. Post-procesamiento automatico con telemetria del log    |
+-------------------------------------------------------------+
```

---

## 3. Componentes a Desarrollar

### 3.1. Generador de Grillas de Vuelo Fotogrametrico
* **Entrada:** Poligono KML/GeoJSON con la zona de estudio (coordenadas WGS-84).
* **Parametros:**
  * Altura de vuelo relativa ($h$): Típicamente 20 a 30 metros (optimo para detectar caminos de hormigas de 5 a 15 cm de ancho).
  * Solapamiento frontal: 80% a 90% (obtenido dividiendo el video 4K a 1 o 2 fotos/segundo).
  * Solapamiento lateral: 70% a 80% (distancia entre pasadas paralelas).
  * GSD resultante (Ground Sample Distance): Estimado en ~0.6 a 0.8 cm/pixel con sensor 4K a 25m de altura.
* **Salida:** Lista de waypoints con comando `MAV_CMD_NAV_WAYPOINT`.

### 3.2. Protocolo de Carga de Misiones MAVLink
* Implementacion mediante `pymavlink`:
  * `MISSION_COUNT`: Notifica a la Pixhawk la cantidad total de puntos.
  * `MISSION_REQUEST_INT`: Recepcion de solicitud punto por punto desde la Pixhawk.
  * `MISSION_ITEM_INT`: Envio de latitud, longitud, altitud y tiempo de permanencia (`acceptance_radius = 1.5m`).
  * `MISSION_ACK`: Confirmacion de recepcion integra en la memoria EEPROM de la controladora.

### 3.3. Sincronizacion de Eventos de Mision
* **Inicio de Grabacion en Primer Waypoint:** La grabacion de video 4K 30 FPS se activa al alcanzar el primer waypoint de la grilla de escaneo para ahorrar bateria y almacenamiento.
* **Fin de Escaneo y Retorno:** Al alcanzar el ultimo waypoint, el sistema conmuta automaticamente al modo `RTL` (Return to Launch), retornando al punto de despegue y descendiendo en modo `LAND`.

### 3.4. Parametros y Protecciones de Seguridad (Fail-Safe) en ArduCopter
* **FS_BATT_ENABLE = 2 (RTL):** Si la bateria LiPo 3S desciende por debajo de 10.5 V (3.5 V/celda), la Pixhawk aborta la mision y regresa automaticamente a la base.
* **FS_GCS_ENABLE = 1 (RTL):** Si se pierde el enlace de telemetria de 915 MHz por mas de 5 segundos, la aeronave evalua regreso o continuacion de mision segun configuracion de seguridad.
* **FENCE_ENABLE = 1:** Geocerca perimetral para impedir que el dron abandone el campo asignado bajo cualquier circunstancia.

---

## 4. Plan de Pruebas Escalonado para la Fase Futura

1. **Simulacion en Software (SITL):** Validar la generacion de la grilla y recepcion de comandos en ArduCopter SITL con Mission Planner / QGroundControl antes de cualquier vuelo de campo.
2. **Prueba de Banco (Motores Desarmados):** Enviar mision a la Pixhawk real por la radio de 915 MHz, verificar cambios de modo (`STABILIZE` -> `AUTO` -> `RTL`) en el dashboard.
3. **Vuelo Manual con Conmutacion a AUTO:** Despegue manual a 15m, activacion del switch de modo AUTO en la emisora RC para recorrer 3 waypoints simples, y recuperacion manual con switch en LOITER o STABILIZE.
4. **Mision Fotogrametrica Completa:** Ejecucion de grilla de 1 hectarea en campo con captura de video 4K e integracion post-vuelo con el vinculador DJI Mini 2 SE.
