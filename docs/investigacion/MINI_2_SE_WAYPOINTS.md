# Waypoints en el DJI Mini 2 SE (revisado el 23/11/2026)

**Conclusión:** sin vía oficial ni caso documentado de waypoints en este modelo. Hay una vía experimental plausible en Android.
Equipo: cámara FC7503, control RC-N1 (`wm231_rc`).

## Oficial: no
- DJI: "MSDK will not support DJI MINI 2 SE", y también que es "essentially the same as the DJI MINI 2 in terms of functionality":
  https://github.com/dji-sdk/Mobile-SDK-Android-V5/issues/395
- No compatible: Maven/MavenRoute (https://www.mavenpilot.com/), Litchi (https://www.litchiutilities.com/docs/waypoint.php),
  Map Pilot Pro (https://support.dronesmadeeasy.com/hc/en-us/articles/205704366-Supported-Hardware).

## Pistas
| Proyecto | Qué aporta | Límite |
|---|---|---|
| https://github.com/CJ-Polilla/enable-dji-mini-4k-in-msdk-4 | El SDK 4.18 trata al **Mini 4K** (tipo 107) como Mini 2 (WM161) | Sólo muestra cámara y modelo; no documenta virtual stick. No sabemos si el 2 SE informa 107 |
| https://github.com/karolis1115/mini2secamera | **Mini 2 SE** con SDK 4.17: detecta el dron, video irregular, avisos de brújula | "Unknown aircraft"; sin vuelo |
| https://github.com/m4xw/rosettadrone_mini2 | Engaño con Frida y waypoints por virtual stick en **Mini 2** | Sin el 2 SE; advierte posible daño del gimbal |
| https://github.com/RosettaDrone/rosettadrone | MAVLink y misiones por virtual stick | Requiere modelo aceptado por el SDK |
| https://github.com/sworrl/GlassFalcon | Control DUML sin SDK | Sólo Mavic 2 |
| https://github.com/zbycu19101019/G29DroneControl | Diagnóstico SDK 4.18 con Mini 2 SE | "SDK rechazado"; sin control de vuelo |
| https://github.com/maeger/DJI-Mini-2-SE-Hack | Dice correr firmware de Mini 2 | **Repositorio vacío**; no flashear |

Según Litchi Utilities el Mini 4K es en esencia un Mini 2 SE con otra cámara; por eso la primera pista es la más fuerte.

## Plan de prueba (cada paso decide el siguiente)
1. App Android propia con SDK 4.18 y clave de desarrollador. **Sólo lectura:** anotar el tipo numérico que informa el dron.
2. Si es 107, probar el parche tal cual; si no, adaptar el número. Verificar que aparezcan modelo y telemetría.
3. Virtual stick **sin hélices**, y con el simulador del SDK si está disponible.
4. En campo abierto, GPS bueno, 5 m de altura: un desplazamiento corto, con la palanca lista para retomar el mando.
5. Recién entonces, waypoints por virtual stick conectados a este planificador.

Riesgos: sin soporte ni garantía; requiere enlace continuo; no detecta obstáculos; puede perderse el dron.
No se quitan límites de altura ni zonas. Apps "mod" de terceros: no usarlas.
No se usa `Volver a casa` como único respaldo: verificarlo antes.

## Alternativa inmediata
Vuelo manual con el plan como guía, importación y cálculo de lo pendiente: [DRONES_DJI.md](../guias/DRONES_DJI.md).
