# Vuelos DJI
La navegación por waypoints en DJI está **oculta** (`NAV_DJI = False` en `app/drones.py`) hasta que esté probada.

## Cargar
1. Dron encendido por USB, o copiar MP4/JPG/SRT en `datos/entrada_dji/`.
2. Pestaña **Vuelos DJI** → *Buscar vuelos*: agrupa por hora y marca lo ya cargado.
3. *Cargar vuelos elegidos*. Los videos con el dron quieto en tierra se omiten. La tarjeta no se modifica.

Probado con Mini 2 SE. Para otros modelos se lee el SRT aparte (latitude/longitude/rel_alt), probado sólo con un archivo sintético.

## Mapa
El Mini 2 SE graba en el video la posición con 4 decimales (unos 11 m). `app/trayectoria.py` **estima** el recorrido suave que
respeta esa celda, la distancia al despegue y la velocidad (`estimada.json`). En un recorrido simulado el error medio bajó de 3,5 a 1,8 m;
no hay una referencia de campo completa. *Ver GPS grabado* muestra el dato original, que es el que queda en `telemetria.csv` y en los tags.
Las fotos JPG tienen GPS fino y no se tocan. Sin rumbo en los videos; gimbal del fotograma = el del inicio del video.
