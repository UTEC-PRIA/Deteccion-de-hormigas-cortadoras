# Plan de vuelo por waypoints

Pestaña **Plan de vuelo** del dashboard. Diseña, valida, carga y verifica misiones en la Pixhawk.

> **Estado:** probado con un dron simulado (`tests/simular_plan.py`) y en Firefox.
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
| Guardar, Exportar, Importar | Planes en `planes/`, JSON o `.waypoints` (QGC WPL 110, Mission Planner) |

La grilla rechaza las zonas en las que una pasada saldría del polígono (cóncavas): divídalas.
El círculo rojo es una referencia de 200 m alrededor del WP1; el límite real se mide desde el dron al cargar.

## 2. Velocidad
Por defecto **0,4 m/s**: percentil 10 de la velocidad neta en tramos de 10 s con avance (> 0,3 m/s) del vuelo de
campo 02 (23/11/2026). Opciones: 0,4, 0,6 y 0,8 m/s.

RTL no usa la velocidad del plan y algunos firmware antiguos pueden ignorar valores muy bajos. Por eso la carga
se **bloquea** si `WPNAV_SPEED` (o `RTL_SPEED`, si existe) supera 100 cm/s. El programa no cambia parámetros:
ajústelos en Mission Planner.

## 3. Límites
Altura 5-30 m; 2-50 puntos; tramos ≤ 100 m; radio ≤ 200 m del despegue; ≤ 6 min estimados; espera ≤ 60 s.
A 0,4 m/s, 6 min equivalen a unos 120 m de recorrido. **No detecta obstáculos ni relieve.**

## 4. Uso
1. Diseñar y guardar.
2. Dron encendido y **desarmado**: *Revisar dron* (solo lectura).
3. Confirmar obstáculos y *Cargar y verificar*: sube la misión y relee cada item.
4. *Comenzar Grabación*; armar y despegar **con el control**; LOITER a más de 3 m.
5. *Iniciar misión* (AUTO). Se bloquea sin RC, con menos de 10 satélites, telemetría vieja, plan distinto al cargado
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
