# Drones DJI

Pestaña **Drones DJI** (hardware e importación) y selector **Dron** en *Plan de vuelo*. Los perfiles están en `drones.py` (`PERFILES`).

| Dron | Plan de vuelo | Estado |
|---|---|---|
| F450 + Pixhawk | Carga por radio y relectura | Probado con simulador |
| Mini 5 Pro | KMZ por batería, se vuela con DJI Fly | KMZ generado; **sin probar en el dron** |
| Mini 2 SE | Sólo guía para vuelo manual | DJI no da SDK ni waypoints |

## Importar
Lee la tarjeta sin escribir en ella. Copia fotos intactas, extrae fotogramas y toma la posición de los subtítulos del MP4
(1 por segundo, coordenadas de 4 decimales, unos 11 m; altura y velocidad con más detalle). El rumbo no viene en el video.
`GimbalPitchDegree` de cada fotograma es el del inicio del video. En las fotos originales el gimbal figura 0 aunque estén inclinadas:
no usarlo. Voltaje y satélites quedan en 0 (no disponibles). Vuelos: `datos/vuelos/dji_<modelo>/<nombre>_<fecha>/` con `dron.json`.

## Cambio de batería
- **DJI:** marcar despegue y minutos útiles; *Calcular tramos* reparte el plan con ida, regreso y 30 s de margen, y repite el último punto.
- **Interrupción:** importar el vuelo y *Ver avance*, o indicar el WP. Es una estimación; confirmar a mano.
- **Pixhawk:** en AUTO se guarda el WP en `datos/planes/.progreso.json`. Tras cambiar la batería: *Última misión interrumpida*,
  *Dejar sólo lo pendiente*, cargar y verificar de nuevo. El primer punto debe quedar a 100 m o menos del despegue.

## Mini 5 Pro: pasar el KMZ
1. Crear en DJI Fly una misión cualquiera, copiar su KMZ a la PC y adjuntarlo (aporta el modelo de dron).
2. Descargar el tramo y reemplazar con él ese archivo, conservando el nombre.
   En Android/RC 2: `Android/data/dji.go.v5/files/waypoint/<id>/<id>.kmz`.
3. Abrirla en DJI Fly y revisar altura, puntos y acción final antes de volar.

## Pruebas
`.venv/bin/python tests/probar_drones.py`
