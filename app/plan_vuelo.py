#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan de vuelo por waypoints: valida, carga en la Pixhawk y verifica releyendo.
Reglas: nunca arma el dron, solo carga con el dron DESARMADO y no cambia parametros."""
import os, re, json, math, time, hashlib, threading
from fastapi import APIRouter, Header, HTTPException
from pymavlink import mavutil
import drones, rutas

BASE = os.path.dirname(os.path.abspath(__file__))
PLANES = rutas.PLANES
class _Puerto:
    """Un solo usuario del puerto serie a la vez. 'esperando' avisa a la vista del control que debe ceder la radio."""
    def __init__(self): self._l, self._g, self.esperando = threading.Lock(), threading.Lock(), 0
    def acquire(self, blocking=True, timeout=-1):
        with self._g: self.esperando += 1
        try: return self._l.acquire(blocking, timeout)
        finally:
            with self._g: self.esperando -= 1
    def release(self): self._l.release()
    def __enter__(self): self.acquire(); return self
    def __exit__(self, *_): self.release()
PUERTO_LOCK = _Puerto()
router = APIRouter()
ML = mavutil.mavlink
LIM = {"alt_min": 3.0, "alt_max": 8.0, "vel_min": 0.3, "vel_ref": 0.4, "vel_max": 0.8, "wpnav_max": 100.0, "radio_max": 200.0, "tramo_max": 100.0,
       "wp_max": 50, "min_max": 6.0, "sats_min": 10, "hdop_max": 1.5}
FINES = {"RTL": ML.MAV_CMD_NAV_RETURN_TO_LAUNCH, "LAND": ML.MAV_CMD_NAV_LAND, "LOITER": ML.MAV_CMD_NAV_LOITER_UNLIM}
MODOS = {0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO", 4: "GUIDED", 5: "LOITER", 6: "RTL", 7: "CIRCLE",
         9: "LAND", 16: "POSHOLD", 17: "BRAKE"}
PARAMS = ["FLTMODE1", "FLTMODE2", "FLTMODE3", "FLTMODE4", "FLTMODE5", "FLTMODE6", "FS_THR_ENABLE", "FS_GCS_ENABLE",
          "CH7_OPT", "CH8_OPT", "RTL_ALT", "FENCE_ENABLE", "BATT_FS_LOW_ACT", "BATT_LOW_VOLT", "WPNAV_SPEED", "RTL_SPEED"]
conexion = {"abrir": None, "puerto": None, "estado": None}   # las completa web_dashboard
cargado = {"id": None, "plan": None, "hora": None}

def dist(a, b):
    r = math.radians
    h = math.sin(r(b[0] - a[0]) / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(r(b[1] - a[1]) / 2) ** 2
    return 12742000 * math.asin(math.sqrt(min(1, h)))

def normalizar(d):
    try:
        wps = [{"lat": float(w["lat"]), "lon": float(w["lon"]), "alt": float(w["alt"]),
                "espera": float(w.get("espera", 0))} for w in d["wps"]]
        p = {"nombre": str(d.get("nombre", "Plan")), "vel": float(d["vel"]), "fin": d["fin"], "wps": wps, "dron": str(d.get("dron") or "f450"), "despegue": d.get("despegue") is True}
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Plan con datos invalidos")
    if p["dron"] not in drones.PERFILES or not drones.visible(p["dron"]): raise HTTPException(400, "Tipo de dron desconocido")
    nums = [p["vel"]] + [w[k] for w in wps for k in w]
    if not all(math.isfinite(x) for x in nums):
        raise HTTPException(400, "Plan con numeros invalidos")
    return p

def _id(p):
    return hashlib.sha256(json.dumps({k: p[k] for k in ("vel", "fin", "wps")}, sort_keys=True).encode()).hexdigest()[:8]

def validar(p, home=None):
    e, w, L = [], p["wps"], drones.limites(p.get("dron", "f450"), LIM)
    if not 2 <= len(w) <= L["wp_max"]: e.append(f"Debe haber entre 2 y {L['wp_max']} waypoints.")
    if not L["vel_min"] <= p["vel"] <= L["vel_max"]: e.append(f"Velocidad fuera de {L['vel_min']} a {L['vel_max']} m/s.")
    if p["fin"] not in FINES: e.append("Accion final invalida.")
    for i, x in enumerate(w, 1):
        if not L["alt_min"] <= x["alt"] <= L["alt_max"]: e.append(f"WP{i}: altura fuera de {L['alt_min']:.0f} a {L['alt_max']:.0f} m.")
        if not (-90 <= x["lat"] <= 90 and -180 <= x["lon"] <= 180) or (x["lat"] == 0 and x["lon"] == 0): e.append(f"WP{i}: coordenadas invalidas.")
        if not 0 <= x["espera"] <= 60: e.append(f"WP{i}: espera fuera de 0 a 60 s.")
    pts = ([home] if home else []) + [(x["lat"], x["lon"]) for x in w]
    total = 0.0
    for i in range(1, len(pts)):
        d = dist(pts[i - 1], pts[i]); total += d
        if d > L["tramo_max"]: e.append(f"Tramo {i} de {d:.0f} m: maximo {L['tramo_max']:.0f} m.")
    ref = home or (pts[0] if pts else None)
    if ref:
        for i, x in enumerate(w, 1):
            if dist(ref, (x["lat"], x["lon"])) > L["radio_max"]: e.append(f"WP{i}: a mas de {L['radio_max']:.0f} m del despegue.")
        if p["fin"] == "RTL" and pts: total += dist(pts[-1], ref)
    alts = [0.0] + [x["alt"] for x in w] + ([0.0] if p["fin"] != "LOITER" else [])
    vert = sum(abs(b - a) for a, b in zip(alts, alts[1:]))
    minutos = (total / max(p["vel"], 0.1) + vert + sum(x["espera"] for x in w) + 20) / 60
    if minutos > L["min_max"]: e.append(f"Duracion estimada {minutos:.1f} min: maximo {L['min_max']:.0f} min.")
    return {"errores": e, "distancia": round(total), "minutos": round(minutos, 1)}

def items(p, home):
    c = [(ML.MAV_CMD_NAV_WAYPOINT, 0, 0, 0, home[0], home[1], home[2], ML.MAV_FRAME_GLOBAL),
         (ML.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, p["wps"][0]["alt"], ML.MAV_FRAME_GLOBAL_RELATIVE_ALT),
         (ML.MAV_CMD_DO_CHANGE_SPEED, 1, p["vel"], -1, 0, 0, 0, ML.MAV_FRAME_GLOBAL_RELATIVE_ALT)]
    for x in p["wps"]:
        c.append((ML.MAV_CMD_NAV_WAYPOINT, x["espera"], 0, 0, x["lat"], x["lon"], x["alt"], ML.MAV_FRAME_GLOBAL_RELATIVE_ALT))
    u = p["wps"][-1]
    c.append((FINES[p["fin"]], 0, 0, 0, *((0, 0, 0) if p["fin"] == "RTL" else (u["lat"], u["lon"], 0 if p["fin"] == "LAND" else u["alt"])), ML.MAV_FRAME_GLOBAL_RELATIVE_ALT))
    return c

def _leer(c, s, params=False):
    """Estado actual del autopiloto: exige datos frescos."""
    L, textos, pr, fin, sig, k = {}, set(), {}, time.time() + s, 0, 0
    faltan = list(PARAMS) if params else []
    while time.time() < fin:
        if faltan and time.time() > sig:
            c.mav.param_request_read_send(c.target_system, c.target_component, faltan[k % len(faltan)].encode(), -1)
            k += 1; sig = time.time() + 0.25
        m = c.recv_match(blocking=True, timeout=0.2)
        if not m or m.get_srcSystem() != c.target_system: continue
        t = m.get_type(); L[t] = m
        if t == "STATUSTEXT" and "PreArm" in m.text: textos.add(m.text)
        if t == "PARAM_VALUE":
            pr[m.param_id] = m.param_value
            if m.param_id in faltan: faltan.remove(m.param_id)
        if params and not faltan and {"HEARTBEAT", "GPS_RAW_INT", "RC_CHANNELS", "GLOBAL_POSITION_INT", "SYS_STATUS"} <= set(L) and time.time() > fin - s + 3: break
    return L, textos, pr

def _chequeo(L):
    e = []
    for t in ("HEARTBEAT", "GPS_RAW_INT", "GLOBAL_POSITION_INT", "RC_CHANNELS"):
        if t not in L: e.append(f"No llego {t}.")
    if e: return e
    if L["HEARTBEAT"].type != ML.MAV_TYPE_QUADROTOR or L["HEARTBEAT"].autopilot != ML.MAV_AUTOPILOT_ARDUPILOTMEGA: e.append("No es un cuadricoptero ArduPilot.")
    if L["HEARTBEAT"].base_mode & 128: e.append("El dron esta ARMADO: solo se carga desarmado.")
    g = L["GPS_RAW_INT"]
    if g.fix_type < 3 or g.satellites_visible < LIM["sats_min"] or g.eph > LIM["hdop_max"] * 100: e.append(f"GPS insuficiente (fix {g.fix_type}, {g.satellites_visible} sats, HDOP {g.eph/100:.2f}).")
    if L["RC_CHANNELS"].chancount == 0: e.append("Sin senal del control remoto.")
    return e

def _velocidades(pr):
    """El firmware puede ignorar un cambio de velocidad muy bajo y RTL no lo usa: se exige tope en los parametros."""
    e, t = [], LIM["wpnav_max"]
    if "WPNAV_SPEED" not in pr: e.append("No se pudo leer WPNAV_SPEED.")
    elif pr["WPNAV_SPEED"] > t: e.append(f"WPNAV_SPEED = {pr['WPNAV_SPEED']:.0f} cm/s: bajelo a {t:.0f} o menos en Mission Planner.")
    if pr.get("RTL_SPEED", 0) > t: e.append(f"RTL_SPEED = {pr['RTL_SPEED']:.0f} cm/s: bajelo a {t:.0f} o menos.")
    return e

def _conectar(todo=True):
    st = conexion["estado"]
    if st.en_grabacion: raise HTTPException(409, "Hay una mision grabando: usa el puerto de la radio.")
    puerto = conexion["puerto"]()
    if not puerto: raise HTTPException(409, "Radio 915 MHz no conectada.")
    c = conexion["abrir"](puerto)
    h, fin = None, time.time() + 6
    while time.time() < fin:
        m = c.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if m and m.autopilot == ML.MAV_AUTOPILOT_ARDUPILOTMEGA:
            h = m; c.target_system, c.target_component = m.get_srcSystem(), m.get_srcComponent(); break
    if not h:
        c.close(); raise HTTPException(409, "Sin senal del dron.")
    if todo: c.mav.request_data_stream_send(c.target_system, c.target_component, 0, 4, 1)
    return c

def _esperar(c, tipos, s):
    fin = time.time() + s
    while time.time() < fin:
        m = c.recv_match(type=tipos, blocking=True, timeout=0.3)
        if m and m.get_srcSystem() == c.target_system: return m
    return None

def _subir(c, its):
    ts, tc = c.target_system, c.target_component
    c.mav.mission_count_send(ts, tc, len(its))
    quieto, fin = 0, time.time() + 60
    while time.time() < fin:
        m = _esperar(c, ["MISSION_REQUEST", "MISSION_REQUEST_INT", "MISSION_ACK"], 2)
        if m is None:
            quieto += 1
            if quieto > 4: raise RuntimeError("El dron dejo de responder durante la carga.")
            if quieto == 1: c.mav.mission_count_send(ts, tc, len(its))
            continue
        quieto = 0
        if m.get_type() == "MISSION_ACK":
            if m.type != ML.MAV_MISSION_ACCEPTED: raise RuntimeError(f"Mision rechazada por la Pixhawk (codigo {m.type}).")
            return
        if not 0 <= m.seq < len(its): raise RuntimeError("Pedido de item inesperado.")
        cmd, a, b, d, lat, lon, alt, fr = its[m.seq]
        c.mav.mission_item_int_send(ts, tc, m.seq, fr, cmd, 0, 1, a, b, d, 0, round(lat * 1e7), round(lon * 1e7), alt)
    raise RuntimeError("Tiempo agotado al cargar la mision.")

def _verificar(c, its):
    ts, tc = c.target_system, c.target_component
    n = None
    for _ in range(4):
        c.mav.mission_request_list_send(ts, tc)
        n = _esperar(c, ["MISSION_COUNT"], 2)
        if n: break
    if not n or n.count != len(its): raise RuntimeError("La Pixhawk no devolvio la misma cantidad de items.")
    for i in range(1, len(its)):            # el item 0 (home) lo administra la Pixhawk
        m = None
        for _ in range(5):
            c.mav.mission_request_int_send(ts, tc, i)
            fin = time.time() + 1.5
            while time.time() < fin:
                x = _esperar(c, ["MISSION_ITEM_INT", "MISSION_ITEM"], 0.5)
                if x and x.seq == i: m = x; break
            if m: break
        if not m: raise RuntimeError(f"No se pudo releer el item {i}.")
        cmd, a, b, d, lat, lon, alt, fr = its[i]
        esc = 1e7 if m.get_type() == "MISSION_ITEM_INT" else 1.0
        ok = m.command == cmd
        if cmd in (ML.MAV_CMD_NAV_WAYPOINT, ML.MAV_CMD_NAV_LAND, ML.MAV_CMD_NAV_LOITER_UNLIM):
            ok = ok and dist((m.x / esc, m.y / esc), (lat, lon)) < 1.0
        if cmd in (ML.MAV_CMD_NAV_WAYPOINT, ML.MAV_CMD_NAV_TAKEOFF, ML.MAV_CMD_NAV_LOITER_UNLIM):
            ok = ok and abs(m.z - alt) < 0.1 and m.frame in (3, 6)
        if cmd == ML.MAV_CMD_NAV_WAYPOINT: ok = ok and abs(m.param1 - a) < 1.0
        if cmd == ML.MAV_CMD_DO_CHANGE_SPEED: ok = ok and abs(m.param2 - b) < 0.1
        if not ok: raise RuntimeError(f"El item {i} releido no coincide con el plan.")
    c.mav.mission_ack_send(ts, tc, ML.MAV_MISSION_ACCEPTED)

def _guardia(x):
    if x != "1": raise HTTPException(403, "Solicitud no permitida.")     # impide ordenes desde otras paginas web

@router.get("/api/plan/limites")
def limites(): return LIM

@router.post("/api/plan/validar")
def api_validar(d: dict): return validar(normalizar(d))

@router.get("/api/plan/lista")
def lista():
    return sorted(f[:-5] for f in os.listdir(PLANES) if f.endswith(".json")) if os.path.isdir(PLANES) else []

def _ruta(n):
    if not re.fullmatch(r"[\w-]{1,60}", n): raise HTTPException(400, "Nombre: solo letras, numeros, - y _.")
    return os.path.join(PLANES, n + ".json")

@router.get("/api/plan/abrir/{n}")
def abrir(n: str):
    if not os.path.exists(_ruta(n)): raise HTTPException(404)
    with open(_ruta(n), encoding="utf-8") as f: return json.load(f)

@router.post("/api/plan/guardar")
def guardar(d: dict, x_hormigas: str = Header("")):
    _guardia(x_hormigas); p = normalizar(d); r = _ruta(p["nombre"]); os.makedirs(PLANES, exist_ok=True)
    with open(r, "w", encoding="utf-8") as f: json.dump(p, f, indent=1)
    return {"exito": True}

@router.post("/api/plan/estado")
def estado_dron(x_hormigas: str = Header("")):
    """Prevuelo de solo lectura: GPS, RC, modos del control y failsafes."""
    _guardia(x_hormigas)
    if not PUERTO_LOCK.acquire(timeout=8): raise HTTPException(409, "Puerto ocupado.")
    try:
        c = _conectar()
        try: L, tx, pr = _leer(c, 12, True)
        finally: c.close()
    finally: PUERTO_LOCK.release()
    av = sorted(tx)
    modos = [MODOS.get(int(pr[f"FLTMODE{i}"]), str(int(pr[f"FLTMODE{i}"]))) for i in range(1, 7) if f"FLTMODE{i}" in pr]
    if len(modos) == 6:
        if "AUTO" not in modos and 16 not in (pr.get("CH7_OPT"), pr.get("CH8_OPT")): av.append("AUTO no esta en la llave de modos: se inicia desde el dashboard.")
        if not {"LOITER", "ALT_HOLD", "STABILIZE"} & set(modos): av.append("No hay modo manual en la llave.")
    else: av.append("No se pudieron leer todos los modos.")
    if pr.get("FS_THR_ENABLE") != 1: av.append("Failsafe de control: no esta en 'RTL siempre' (o no se leyo).")
    if pr.get("FS_GCS_ENABLE") == 0: av.append("Si se pierde la radio 915, el dron SIGUE la mision.")
    if pr.get("RTL_ALT", 0) > LIM["alt_max"] * 100: av.append(f"RTL_ALT = {pr['RTL_ALT']/100:.0f} m: el regreso sube por encima del maximo de {LIM['alt_max']:.0f} m.")
    if pr.get("FENCE_ENABLE") == 0: av.append("Geocerca desactivada.")
    if pr.get("WPNAV_SPEED", 0) > 41: av.append(f"WPNAV_SPEED = {pr['WPNAV_SPEED']:.0f} cm/s: si pausa y vuelve a AUTO, vuela a esa velocidad y no a la del plan (medido en SITL). Recomendado: 40.")
    faltan = [p for p in PARAMS if p not in pr and p not in ("RTL_SPEED", "CH7_OPT", "CH8_OPT")]   # no existe en firmware antiguo
    if faltan: av.append("Parametros sin leer: " + ", ".join(faltan))
    g, s = L.get("GPS_RAW_INT"), L.get("SYS_STATUS")
    if s and not s.onboard_control_sensors_enabled & 32768: av.append("Boton de seguridad activo (no arma).")
    pos = L.get("GLOBAL_POSITION_INT")
    return {"errores": _chequeo(L) + _velocidades(pr), "avisos": av, "modos": modos, "rtl_alt": pr["RTL_ALT"] / 100 if "RTL_ALT" in pr else None,
            "sats": g.satellites_visible if g else None, "voltaje": s.voltage_battery / 1000 if s else None,
            "pos": [pos.lat / 1e7, pos.lon / 1e7] if pos else None}

@router.post("/api/plan/cargar")
def cargar(d: dict, x_hormigas: str = Header("")):
    _guardia(x_hormigas); p = normalizar(d)
    if p["dron"] != "f450": raise HTTPException(400, "Este plan es para un DJI: no se carga en la Pixhawk.")
    if d.get("confirmo") is not True: raise HTTPException(400, "Falta confirmar obstaculos y zona despejada.")
    if not PUERTO_LOCK.acquire(timeout=8): raise HTTPException(409, "Puerto ocupado.")
    try:
        c = _conectar()
        try:
            L, _, pr = _leer(c, 12, True)
            e = _chequeo(L) + _velocidades(pr)
            if pr.get("RTL_ALT", 1e9) > LIM["alt_max"] * 100: e.append(f"RTL_ALT no se leyo o supera {LIM['alt_max']:.0f} m: no se carga.")
            if not e:
                g = L["GLOBAL_POSITION_INT"]; home = (g.lat / 1e7, g.lon / 1e7, g.alt / 1000)
                if p["despegue"] and p["wps"]: p["wps"][0].update(lat=home[0], lon=home[1])    # punto 1 = posicion del dron
                e = validar(p, home[:2])["errores"]
            if e: return {"exito": False, "errores": e}
            its = items(p, home); cargado["id"] = None; _subir(c, its); _verificar(c, its)
            hb = _esperar(c, ["HEARTBEAT"], 3)
            if not hb or hb.base_mode & 128: return {"exito": False, "errores": ["El dron se armo o dejo de responder durante la carga. No usar."]}
        except RuntimeError as x: return {"exito": False, "errores": [f"{x} La mision en el dron NO es confiable: vuelva a cargarla."]}
        finally: c.close()
    finally: PUERTO_LOCK.release()
    cargado.update(id=_id(p), plan=p, hora=time.strftime("%H:%M:%S"))
    return {"exito": True, "items": len(its), "id": cargado["id"], "wps": p["wps"], "home": home[:2]}

@router.get("/api/plan/vivo")
def vivo():
    st = conexion["estado"]
    return {"cargado": cargado["id"], "hora": cargado["hora"], "grabando": st.en_grabacion, "armado": st.armado, "modo": st.modo_vuelo,
            "lat": st.lat, "lon": st.lon, "alt": st.alt_rel, "wp": st.wp_actual,
            "edad": round(time.time() - st.ultimo_msg_tiempo, 1) if st.ultimo_msg_tiempo else None}

@router.post("/api/plan/modo")
def modo(d: dict, x_hormigas: str = Header("")):
    """Cambia de modo en vuelo. AUTO exige mision verificada y dron ya en vuelo en LOITER."""
    _guardia(x_hormigas); st, m = conexion["estado"], d.get("modo")
    n = {"AUTO": 3, "LOITER": 5, "RTL": 6, "LAND": 9}.get(m)
    if n is None: raise HTTPException(400, "Modo invalido.")
    if not st.en_grabacion or not st.conexion_mavlink: raise HTTPException(409, "Primero Comenzar Grabacion en la pestana Control.")
    if m == "AUTO":
        f = []
        if not cargado["id"]: f.append("no hay mision cargada y verificada en esta sesion")
        elif _id(normalizar(d)) != cargado["id"]: f.append("el plan en pantalla no es el que esta cargado en el dron")
        elif dist((st.lat, st.lon), (cargado["plan"]["wps"][0]["lat"], cargado["plan"]["wps"][0]["lon"])) > LIM["tramo_max"]: f.append("dron lejos del primer waypoint")
        if not st.ultimo_msg_tiempo or time.time() - st.ultimo_msg_tiempo > 2: f.append("telemetria sin datos recientes")
        if not st.armado: f.append("el dron no esta armado")
        if st.modo_vuelo != "LOITER": f.append("el dron debe estar en LOITER")
        if st.alt_rel < 3: f.append("altura menor a 3 m")
        if st.satelites < LIM["sats_min"]: f.append("pocos satelites")
        if not st.rc_canales: f.append("sin senal del control remoto")
        if d.get("confirmo") is not True: f.append("falta confirmacion")
        if f: return {"exito": False, "error": "AUTO bloqueado: " + "; ".join(f)}
    c = st.conexion_mavlink
    for _ in range(3):
        c.mav.set_mode_send(st.sistema_autopiloto or c.target_system, 1, n)
        fin = time.time() + 1.6
        while time.time() < fin:
            if st.modo_vuelo == m: return {"exito": True}
            time.sleep(0.1)
        if m == "AUTO": break      # AUTO no se reintenta: el piloto pudo haber retomado el mando
    return {"exito": False, "error": f"{m} sin confirmar. Modo actual: {st.modo_vuelo}. USE EL CONTROL."}
