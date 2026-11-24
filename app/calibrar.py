#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibracion guiada (brujula, giroscopos, nivel, acelerometro, voltaje). Solo con el dron DESARMADO.
Guarda los valores anteriores en datos/respaldos_parametros antes de cambiar nada."""
import os, math, time, threading
from fastapi import APIRouter, Header, HTTPException
import plan_vuelo as pv, rutas

router = APIRouter(); ML = pv.ML
E = {"activo": False, "tipo": None, "fase": "", "texto": "", "pct": 0, "ok": None, "pos": None, "error_mg": None}
_orden, _lk = {"v": None}, threading.Lock()
POS = {1: "NIVELADO, sobre las patas", 2: "sobre el lado IZQUIERDO", 3: "sobre el lado DERECHO", 4: "con la nariz ABAJO", 5: "con la nariz ARRIBA", 6: "BOCA ABAJO"}
OFS = [f"COMPASS_{p}{n}_{e}" for n in ("", "2") for p in ("OFS", "DIA", "ODI") for e in "XYZ"]
PREVIOS = {"brujula": OFS, "voltaje": ["BATT_VOLT_MULT"], "nivel": ["AHRS_TRIM_X", "AHRS_TRIM_Y"], "giros": [f"INS_GYROFFS_{e}" for e in "XYZ"],
           "acelerometro": [f"INS_ACC{p}_{e}" for p in ("OFFS", "SCAL") for e in "XYZ"]}

def _param(c, n, s=4):
    fin = time.time() + s
    while time.time() < fin:
        c.mav.param_request_read_send(c.target_system, c.target_component, n.encode(), -1)
        t = time.time() + 0.8
        while time.time() < t:
            m = c.recv_match(type="PARAM_VALUE", blocking=True, timeout=0.3)
            if m and m.param_id == n: return m.param_value, m.param_type
    return None, None

def _desarmado(c):
    fin = time.time() + 5
    while time.time() < fin:
        m = c.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
        if m and m.get_srcSystem() == c.target_system and m.get_srcComponent() == c.target_component:
            if m.base_mode & 128: raise RuntimeError("El dron esta ARMADO: no se calibra.")
            return
    raise RuntimeError("Sin senal del dron.")

def _cmd(c, n, *p, s=8):
    c.mav.command_long_send(c.target_system, c.target_component, n, 0, *(list(p) + [0] * (7 - len(p))))
    fin = time.time() + s
    while time.time() < fin:
        m = c.recv_match(type="COMMAND_ACK", blocking=True, timeout=0.5)
        if m and m.command == n: return m.result == 0
    return None

def _respaldo(c, tipo):
    d = os.path.join(rutas.DATOS, "respaldos_parametros"); os.makedirs(d, exist_ok=True); v = {}
    for n in PREVIOS[tipo]:
        x, _ = _param(c, n, 3)
        if x is not None: v[n] = x
    if not v: raise RuntimeError("No se pudieron respaldar los valores actuales: no se calibra.")
    with open(os.path.join(d, f"calibracion_{tipo}_antes_{time.strftime('%Y%m%d_%H%M%S')}.param"), "w", encoding="utf-8") as f:
        f.writelines(f"{k},{x:.9g}\n" for k, x in v.items())

def _tomar():
    o, _orden["v"] = _orden["v"], None
    return o

def _brujula(c, d):
    mask = 1 if not d.get("ambas") else 3
    c.mav.request_data_stream_send(c.target_system, c.target_component, ML.MAV_DATA_STREAM_EXTRA3, 4, 1)
    if not _cmd(c, ML.MAV_CMD_DO_START_MAG_CAL, mask, 0, 0, 0, 0): raise RuntimeError("El dron no acepto iniciar la brujula.")
    E.update(fase="girar", texto="Levantalo y giralo DESPACIO en todos los sentidos: plano, de cada lado, nariz arriba, nariz abajo y boca abajo.")
    pc, rep, fin, hecho = {}, {}, time.time() + 180, False
    try:
        while time.time() < fin:
            o = _tomar()
            if o == "cancelar": raise RuntimeError("Cancelado. No se cambio nada.")
            m = c.recv_match(type=["MAG_CAL_PROGRESS", "MAG_CAL_REPORT", "HEARTBEAT"], blocking=True, timeout=0.3)
            if not m: continue
            t = m.get_type()
            if t == "HEARTBEAT":
                if m.get_srcSystem() == c.target_system and m.base_mode & 128: raise RuntimeError("El dron se ARMO: calibracion cancelada.")
            elif t == "MAG_CAL_PROGRESS":
                if mask >> m.compass_id & 1: pc[m.compass_id] = m.completion_pct; E["pct"] = min(pc.values())
            elif mask >> m.compass_id & 1 and m.cal_status >= 4:
                if m.cal_status > 4: raise RuntimeError("La calibracion fallo. Alejate de metal y repeti, girando mas despacio.")
                rep[m.compass_id] = m.fitness
                if len(rep) == bin(mask).count("1"): break
        else: raise RuntimeError("Tiempo agotado (3 min).")
        E.update(fase="confirmar", pct=100, error_mg=round(max(rep.values()), 1), texto=f"Lista. Error {max(rep.values()):.1f} (menos de 16 es bueno). ¿Guardar?")
        fin = time.time() + 120
        while time.time() < fin:
            o = _tomar()
            if o == "cancelar": raise RuntimeError("Descartada. No se cambio nada.")
            if o == "aceptar":
                _desarmado(c)
                if not _cmd(c, ML.MAV_CMD_DO_ACCEPT_MAG_CAL, mask): raise RuntimeError("El dron no confirmo el guardado.")
                hecho = True; return "Brujula guardada. REINICIA el dron (desconecta la bateria) antes de armar."
            c.recv_match(blocking=True, timeout=0.2)
        raise RuntimeError("No se confirmo: descartada.")
    finally:
        if not hecho: c.mav.command_long_send(c.target_system, c.target_component, ML.MAV_CMD_DO_CANCEL_MAG_CAL, 0, mask, 0, 0, 0, 0, 0, 0)

def _giros(c, d):
    E.update(fase="quieto", texto="No toques el dron (hasta 30 s)...")
    if not _cmd(c, ML.MAV_CMD_PREFLIGHT_CALIBRATION, 1, s=40): raise RuntimeError("No se calibraron: deja el dron quieto y repeti.")
    return "Giroscopos calibrados."

def _nivel(c, d):
    E.update(fase="quieto", texto="Dron en piso nivelado, quieto (hasta 30 s)...")
    if not _cmd(c, ML.MAV_CMD_PREFLIGHT_CALIBRATION, 0, 0, 0, 0, 2, s=40): raise RuntimeError("No se pudo: piso inclinado o dron en movimiento.")
    return "Nivel guardado."

def _acelerometro(c, d):
    E.update(fase="quieto", texto="Deja el dron quieto...")
    # la confirmacion puede llegar junto con el primer pedido de posicion
    c.mav.command_long_send(c.target_system, c.target_component, ML.MAV_CMD_PREFLIGHT_CALIBRATION, 0, 0, 0, 0, 0, 1, 0, 0)
    fin, hecha = time.time() + 45, 0
    while time.time() < fin:
        o = _tomar()
        if o == "cancelar": raise RuntimeError("Cancelado: REINICIA el dron para salir de la calibracion.")
        if o == "siguiente" and E["pos"]:
            hecha = E["pos"]; E.update(fase="quieto", texto="Midiendo, no lo muevas...")
            c.mav.command_long_send(c.target_system, c.target_component, ML.MAV_CMD_ACCELCAL_VEHICLE_POS, 0, hecha, 0, 0, 0, 0, 0, 0); fin = time.time() + 120
        m = c.recv_match(type=["COMMAND_LONG", "COMMAND_ACK", "HEARTBEAT"], blocking=True, timeout=0.2)
        if not m or m.get_srcSystem() != c.target_system: continue
        t = m.get_type()
        if t == "HEARTBEAT" and m.base_mode & 128: raise RuntimeError("El dron se ARMO: REINICIALO.")
        if t == "COMMAND_ACK" and m.command == ML.MAV_CMD_PREFLIGHT_CALIBRATION and m.result != 0: raise RuntimeError("El dron no acepto: dejalo quieto y repeti.")
        if t == "COMMAND_LONG" and m.command == ML.MAV_CMD_ACCELCAL_VEHICLE_POS:
            p = int(m.param1)
            if p == 16777215: return "Acelerometro guardado. REINICIA el dron."
            if p == 16777216: raise RuntimeError("Fallo: repeti con posiciones mas firmes y quietas.")
            if p in POS and p > hecha:
                if E["pos"] != p: fin = time.time() + 120
                E.update(pos=p, pct=round((p - 1) / 6 * 100), fase="posicion", texto=f"Pone el dron {POS[p]} y apreta Siguiente.")
    raise RuntimeError("Tiempo agotado: REINICIA el dron.")

def _voltaje(c, d):
    real = float(d["voltios"]); v = []; fin = time.time() + 8
    if not (math.isfinite(real) and 9 <= real <= 13): raise RuntimeError("Voltaje fuera de 9 a 13 V (bateria 3S).")
    c.mav.request_data_stream_send(c.target_system, c.target_component, ML.MAV_DATA_STREAM_EXTENDED_STATUS, 5, 1)
    E.update(fase="quieto", texto="Promediando la lectura del dron (8 s)...")
    while time.time() < fin:
        m = c.recv_match(type="SYS_STATUS", blocking=True, timeout=0.5)
        if m: v.append(m.voltage_battery / 1000)
    if len(v) < 8: raise RuntimeError("Pocas lecturas de voltaje.")
    med = sum(v) / len(v); viejo, tp = _param(c, "BATT_VOLT_MULT")
    if not viejo: raise RuntimeError("No se leyo BATT_VOLT_MULT.")
    nuevo = viejo * real / med
    if not 0.8 < nuevo / viejo < 1.25: raise RuntimeError(f"Diferencia muy grande (dron {med:.2f} V): revisa la medicion.")
    _desarmado(c); c.mav.param_set_send(c.target_system, c.target_component, b"BATT_VOLT_MULT", nuevo, tp); time.sleep(0.6)
    leido, _ = _param(c, "BATT_VOLT_MULT")
    if leido is None or abs(leido - nuevo) > 0.01: raise RuntimeError("No se confirmo el cambio.")
    return f"Voltaje: el dron leia {med:.2f} V, real {real:.2f} V. Corregido."

PASOS = {"brujula": _brujula, "giros": _giros, "nivel": _nivel, "acelerometro": _acelerometro, "voltaje": _voltaje}

def _correr(tipo, d):
    c, tomado = None, False
    try:
        tomado = pv.PUERTO_LOCK.acquire(timeout=15)
        if not tomado: raise RuntimeError("Radio ocupada.")
        c = pv._conectar(todo=False); _desarmado(c); E["texto"] = "Respaldando valores..."; _respaldo(c, tipo)
        E.update(ok=True, fase="fin", pct=100, texto=PASOS[tipo](c, d))
    except Exception as x: E.update(ok=False, fase="fin", texto=str(getattr(x, "detail", x)))
    finally:
        if c: c.close()
        if tomado: pv.PUERTO_LOCK.release()
        E.update(activo=False, pos=None); print("CALIBRACION:", tipo, E["ok"], E["texto"], flush=True)

@router.get("/api/calibrar/estado")
def estado(): return E

@router.post("/api/calibrar/iniciar")
def iniciar(d: dict, x_hormigas: str = Header("")):
    pv._guardia(x_hormigas)
    if d.get("tipo") not in PASOS: raise HTTPException(400, "Calibracion desconocida.")
    if d.get("sin_helices") is not True: raise HTTPException(400, "Confirma que el dron esta sin helices.")
    if d["tipo"] == "voltaje":
        try: float(d["voltios"])
        except (KeyError, TypeError, ValueError): raise HTTPException(400, "Escribi el voltaje medido.")
    if pv.conexion["estado"].en_grabacion: raise HTTPException(409, "Hay una grabacion activa.")
    with _lk:
        if E["activo"]: raise HTTPException(409, "Ya hay una calibracion en curso.")
        _orden["v"] = None; E.update(activo=True, tipo=d["tipo"], fase="inicio", texto="Conectando...", pct=0, ok=None, pos=None, error_mg=None)
    threading.Thread(target=_correr, args=(d["tipo"], d), daemon=True).start()
    return {"exito": True}

@router.post("/api/calibrar/orden")
def orden(d: dict, x_hormigas: str = Header("")):
    pv._guardia(x_hormigas)
    if d.get("orden") not in ("cancelar", "aceptar", "siguiente"): raise HTTPException(400, "Orden invalida.")
    _orden["v"] = d["orden"]; return {"exito": True}
