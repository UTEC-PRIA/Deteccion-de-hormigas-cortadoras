# Cambios

## Noviembre de 2026
### Nuevo
- Pestañas en el dashboard: Control, Vuelos y mapa, Imágenes y tags, Plan de vuelo.
- `visor_vuelos.py`: trayectoria, reproducción e imagen al hacer clic en el recorrido; galería con tags.
- `plan_vuelo.py`: waypoints con validación, carga y relectura. Ver `docs/PLAN_DE_VUELO.md`.
- `mision.json` por vuelo: permite reintentar el procesamiento tras cerrar el dashboard.
- `ejecutar.sh`: instala dependencias si faltan y abre el dashboard en Linux.
- `tests/simular_plan.py`: prueba del plan de vuelo sin hardware.

### Corregido
- Videos de más de 4 GB: todas las fotos quedaban sin GPS (exiftool sin `largefilesupport`).
- Hora de 1970 al sincronizar: `GPS_RAW_INT.time_usec` es tiempo desde el encendido en esta Pixhawk.
- La cámara se sincroniza con el reloj de la PC, la misma base que la telemetría; se informa el desfase medido.
- Se informaban como etiquetadas fotos sin GPS.
- Error de lectura de la SD tratado como tarjeta vacía; descargas cortadas dadas por buenas.
- Estado "grabando" mostrado sin poder comprobarlo con la cámara sin cable.
- Autoescaneo: exige HEARTBEAT y avisa por RC, GPS, botón de seguridad y PreArm.
- Alturas negativas mal escritas en XMP (`+-0.50`).
- Acciones duplicadas o simultáneas durante el procesamiento.

### Seguridad
- El servidor escucha solo en `127.0.0.1` (`HORMIGAS_HOST=0.0.0.0` lo cambia); se eliminó CORS abierto.
