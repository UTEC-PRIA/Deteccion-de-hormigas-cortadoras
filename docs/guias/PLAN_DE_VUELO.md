# Plan de vuelo por waypoints

Pestaña **Plan de vuelo** del dashboard. Diseña, valida, carga y verifica misiones en la Pixhawk.

> **Estado:** probado con un dron simulado (`tests/simular_plan.py`), en ArduCopter SITL 4.0.7 y en Firefox.
> **Aún no probado con la aeronave real.** Haga las pruebas de la sección 5 antes de usarlo.

## 1. Herramientas
| Herramienta | Uso |
|---|---|
| Puntos | Clic agrega un waypoint; clic en la línea inserta; arrastrar mueve |
| Mover mapa / Medir | Navegar sin agregar / medir distancias |
| Zona y Grilla | Marca un polígono y genera pasadas paralelas (separación y ángulo) |
| Deshacer, Rehacer, Invertir, Vaciar | Edición del recorrido |
| Punto en el dron / Por coordenadas | Agrega la posición actual del dron o grados decimales |
| Altura y espera por punto | Editables en la tabla; "Aplicar a todos" iguala alturas |
| Guardar, Exportar, Importar | Planes en `datos/planes/`, JSON o `.waypoints` (QGC WPL 110, Mission Planner) |

La grilla rechaza las zonas en las que una pasada saldría del polígono (cóncavas): divídalas.
El círculo rojo es una referencia de 45 m alrededor del WP1; el límite real se mide desde el dron al cargar.

## 2. Velocidad
Por defecto **0,4 m/s**: percentil 10 de la velocidad neta en tramos de 10 s con avance (> 0,3 m/s) del vuelo de
campo 02 (23/11/2026). Opciones: 0,4, 0,6 y 0,8 m/s.

RTL no usa la velocidad del plan y algunos firmware antiguos pueden ignorar valores muy bajos. Por eso la carga
se **bloquea** si `WPNAV_SPEED` (o `RTL_SPEED`, si existe) supera 100 cm/s. El programa no cambia parámetros:
ajústelos en Mission Planner.

## 3. Límites
Altura 3-8 m; 2-50 puntos; tramos ≤ 100 m; radio ≤ 45 m del despegue (geocerca a 50 m); ≤ 6 min estimados; espera ≤ 60 s.
A 0,4 m/s, 6 min equivalen a unos 120 m de recorrido. **No detecta obstáculos ni relieve.**

## 4. Uso
1. Diseñar y guardar.
2. Dron encendido y **desarmado**: *Revisar dron* (solo lectura).
3. Confirmar obstáculos y *Cargar y verificar*: sube la misión y relee cada item.
4. Armar y despegar **con el control**; LOITER a más de 3 m.
5. *Iniciar misión* (AUTO): comienza también la grabación si no estaba activa. La GoPro sólo se inicia con el cable USB. Se bloquea sin RC, con menos de 10 satélites, telemetría vieja, plan distinto al cargado
   o dron a más de 100 m del WP1.

El dashboard **nunca arma**. Cambiar la llave de modos del control interrumpe AUTO; si ya está en el modo deseado,
muévala a otro y vuelva. LAND desciende donde esté: para frenar use primero LOITER. Los botones dependen de la radio.

## 5. Pruebas previas obligatorias
1. **Sin hélices:** Revisar dron, cargar, y comprobar en pantalla cada modo de la llave.
2. **Vuelo manual:** 1-2 min en LOITER sin deriva ni círculos; aterrizar.
3. **Primer AUTO:** 2-3 puntos separados 15-20 m, 8-10 m de altura, final LOITER; retomar el mando a mitad de camino.

## 6. Riesgos a revisar
- `RTL_ALT` leído: 15 m. Debe superar los obstáculos (también lo usan los failsafes).
- `FS_GCS_ENABLE = 0`: sin radio, el dron **sigue** la misión. `FENCE_ENABLE = 0`: sin geocerca.
- Voltaje ruidoso (10,94-12,27 V en el vuelo 02): una lectura falsa puede disparar RTL.
- Altura: 2,3 m de diferencia entre inicio y fin del vuelo 02.

## Despegue sincronizado
Con "Punto 1 = posición inicial del dron", *Revisar dron* coloca el punto D en el GPS del dron y *Cargar y verificar* lo actualiza con la
posición del momento. Si mueve el dron después de cargar, cargue de nuevo. El despegue sigue siendo manual.

## Pruebas en ArduCopter simulado (SITL), 23/11/2026
`tests/sitl_f450.py` carga el plan, despega en LOITER, vuela AUTO, pausa, reanuda, hace RTL y aterriza. No usa el dron.

| Firmware | WPNAV_SPEED | Resultado | Velocidad antes / después de pausar (plan 0,4) |
|---|---|---|---|
| 4.0.7 | 40 | Completa; aterrizó a 0,2 m | 0,35 / 0,34 m/s (máx. 0,50) |
| 4.0.7 | 100 | Completa; aterrizó a 0,2 m | 0,35 / **0,95** m/s |
| 4.7.3 | 40 | **Carga rechazada**: ese firmware no es compatible con esta versión | - |

**Poner `WPNAV_SPEED = 40`:** al volver a AUTO el autopiloto usa ese valor en lugar de la velocidad del plan.
SITL no reproduce viento, sensores, batería ni la radio reales: falta la prueba con la aeronave.
