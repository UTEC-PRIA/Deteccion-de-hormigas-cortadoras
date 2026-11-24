#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vista en vivo del control remoto: canales y funcion de cada llave. SOLO LECTURA:
pide parametros y telemetria, nunca escribe parametros, modos ni canales."""
import threading, time
from fastapi import APIRouter
from pymavlink import mavutil
import plan_vuelo as pv, trayecto

router = APIRouter()
NOMBRES = (["FLTMODE_CH"] + [f"FLTMODE{i}" for i in range(1, 7)] + [f"CH{i}_OPT" for i in range(7, 13)]
           + ["RCMAP_ROLL", "RCMAP_PITCH", "RCMAP_THROTTLE", "RCMAP_YAW", "TUNE", "FS_THR_ENABLE", "FS_THR_VALUE"]
           + [f"RC{i}_{s}" for i in range(1, 5) for s in ("MIN", "MAX", "REVERSED")])
R = {"canales": None, "t": 0.0, "modo": None, "armado": None, "rc_ok": None, "params": {}, "leido": None, "error": None,
     "pos": None, "pos_t": 0.0, "fix": 0, "sats": 0, "hdop": None, "rumbo": None, "alt": None, "vel": None, "volt": None}
_pedido = [0.0]          # ultima consulta de la pagina
_hilo = [None]
_lk = threading.Lock()

def _mensaje(m):
    t = m.get_type()
    if t == "HEARTBEAT": R.update(modo=pv.MODOS.get(m.custom_mode, f"MODO_{m.custom_mode}"), armado=bool(m.base_mode & 128))
    elif t == "RC_CHANNELS": R.update(canales=[getattr(m, f"chan{i}_raw") for i in range(1, m.chancount + 1) if i <= 18], t=time.time())
    elif t == "GLOBAL_POSITION_INT":
        if m.lat or m.lon: R.update(pos=[m.lat / 1e7, m.lon / 1e7], pos_t=time.time(), alt=m.relative_alt / 1000, vel=(m.vx ** 2 + m.vy ** 2) ** 0.5 / 100, rumbo=m.hdg / 100 if m.hdg < 65535 else None); trayecto.muestra(m.lat / 1e7, m.lon / 1e7, m.relative_alt / 1000, R["armado"], _gps())
    elif t == "GPS_RAW_INT": R.update(fix=m.fix_type, sats=m.satellites_visible, hdop=m.eph / 100 if m.eph < 65535 else None)
    elif t == "SYS_STATUS": R["volt"], R["rc_ok"] = m.voltage_battery / 1000, bool(m.onboard_control_sensors_health & pv.ML.MAV_SYS_STATUS_SENSOR_RC_RECEIVER)
    elif t == "PARAM_VALUE" and m.param_id in NOMBRES:
        R["params"][m.param_id] = m.param_value; R["leido"] = time.strftime("%H:%M:%S")

def _gps(): return R["fix"] >= 3 and R["sats"] >= pv.LIM["sats_min"] and R["hdop"] is not None and R["hdop"] <= pv.LIM["hdop_max"]

def _activo(): return (trayecto.G["on"] or time.time() - _pedido[0] < 2.5) and not pv.conexion["estado"].en_grabacion and not pv.PUERTO_LOCK.esperando

def _leer():
    """Usa la radio solo mientras la pestana esta abierta y nadie mas la pide."""
    if not pv.PUERTO_LOCK.acquire(timeout=1): R["error"] = "Radio ocupada por otra funcion."; return
    c = None
    try:
        if not _activo(): return
        c = pv._conectar(todo=False)
        ts, tc = c.target_system, c.target_component
        for s in (pv.ML.MAV_DATA_STREAM_RC_CHANNELS, pv.ML.MAV_DATA_STREAM_EXTENDED_STATUS, pv.ML.MAV_DATA_STREAM_POSITION): c.mav.request_data_stream_send(ts, tc, s, 5, 1)
        R["error"] = None; faltan, k, sig, fin = list(NOMBRES), 0, 0, time.time() + 30
        while _activo():
            if faltan and time.time() > sig and time.time() < fin:
                c.mav.param_request_read_send(ts, tc, faltan[k % len(faltan)].encode(), -1); k += 1; sig = time.time() + 0.12
            m = c.recv_match(blocking=True, timeout=0.1)
            if not m or m.get_srcSystem() != ts or m.get_srcComponent() != tc: continue
            _mensaje(m)
            if m.get_type() == "PARAM_VALUE" and m.param_id in faltan: faltan.remove(m.param_id)
    except Exception as x: R["error"] = str(getattr(x, "detail", x))
    finally:
        if c: c.close()
        pv.PUERTO_LOCK.release()

def _asegurar():
    if pv.conexion["estado"].en_grabacion: return
    with _lk:
        if not (_hilo[0] and _hilo[0].is_alive()) and not pv.PUERTO_LOCK.esperando:
            _hilo[0] = threading.Thread(target=_leer, daemon=True); _hilo[0].start()

def mantener():
    """Mientras se graba un trayecto, sigue leyendo aunque la pagina este oculta."""
    def bucle():
        while True:
            time.sleep(0.7)
            if trayecto.G["on"]: _asegurar()
    threading.Thread(target=bucle, daemon=True).start()

@router.get("/api/control/vivo")
def vivo():
    _pedido[0] = time.time(); st = pv.conexion["estado"]
    _asegurar()
    return {**R, "edad": round(time.time() - R["t"], 1) if R["t"] else None, "grabando": st.en_grabacion,
            "pos_edad": round(time.time() - R["pos_t"], 1) if R["pos_t"] else None,
            "gps_ok": _gps(), "tray": trayecto.resumen()}
