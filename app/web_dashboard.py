#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Dashboard Web de Telemetria en Tiempo Real con Autoescaneo Activo de Hardware,
Verificacion de Grabacion GoPro y Monitor de Bateria LiPo 3S.
"""

import sys
import os
import time
import json
import threading
import subprocess
import webbrowser
import struct
import re
from collections import deque
from datetime import datetime, timezone
import requests
import serial.tools.list_ports
from pymavlink import mavutil
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Importar funciones de vinculacion DJI
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vincular_vuelo_dji import (
    cargar_desde_csv,
    interpolar_telemetria,
    escribir_metadatos_dji,
    escribir_metadatos_dji_batch,
    dividir_video_en_imagenes_dji,
    calcular_inicios_videos,
    hora_local_exif,
    generar_srt_dji,
    obtener_timestamp_imagen
)
from sincronizar_relojes import (
    buscar_ip_gopro,
    buscar_puerto_pixhawk,
    leer_tiempo_gps_pixhawk,
    fijar_hora_gopro,
    consultar_estado_gopro,
    medir_desfase_gopro
)

app = FastAPI(title="UTEC PRIA - UAV Telemetry Dashboard")

import rutas
from visor_vuelos import router as router_visor
app.include_router(router_visor)
import plan_vuelo
from plan_vuelo import PUERTO_LOCK
app.include_router(plan_vuelo.router)
import drones
app.include_router(drones.router)
import control_rc
app.include_router(control_rc.router)
import trayecto
app.include_router(trayecto.router)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")

class EstadoSistema:
    def __init__(self):
        self.en_grabacion = False
        self.tiempo_inicio_vuelo = None
        self.carpeta_mision = None
        self.ruta_csv = None
        self.ruta_tlog = None
        self.conexion_mavlink = None
        self.archivo_csv = None
        self.archivo_tlog = None
        self.hilo_telemetria = None
        
        # Telemetria en vivo
        self.lat = 0.0
        self.lon = 0.0
        self.alt_msl = 0.0
        self.alt_rel = 0.0
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.velocidad = 0.0
        self.satelites = 0
        self.bateria_dron = 0.0
        self.modo_vuelo = "DESCONOCIDO"
        self.total_registros = 0
        self.ultimo_registro_tiempo = 0
        self.puerto_real = None
        self.ultimo_msg_tiempo = 0.0       # ultimo paquete MAVLink del autopiloto
        self.ultima_solicitud_stream = 0.0
        self.sistema_autopiloto = None     # sysid del autopiloto (ignora GCS / otros)
        self.snapshot_medios_tomado = False
        self.ultimos_voltajes = deque(maxlen=20)
        self.procesando = False
        self.armado = False
        self.rc_canales = 0
        self.wp_actual = None

        # Hardware GoPro
        self.gopro_ip = None
        self.gopro_bateria = "--"
        self.gopro_grabando = False
        self.fotos_previas = set()
        self.intervalo_fotos_seg = 1.0
        self.gopro_config = []

        # Proceso post-vuelo
        self.estado_proceso = "LISTO"
        self.mensaje_proceso = ""
        self.progreso_porcentaje = 0

        # Autoescaneo
        self.autoescaneo_resultado = None

estado = EstadoSistema()

MODOS_ARDUPILOT = {
    0: 'STABILIZE', 1: 'ACRO', 2: 'ALT_HOLD', 3: 'AUTO', 4: 'GUIDED',
    5: 'LOITER', 6: 'RTL', 7: 'CIRCLE', 9: 'LAND', 11: 'DRIFT',
    13: 'SPORT', 14: 'FLIP', 15: 'AUTOTUNE', 16: 'POSHOLD', 17: 'BRAKE'
}

def puerto_es_util(p):
    """Descarta puertos Bluetooth y puertos serie fisicos inexistentes (/dev/ttyS* sin hardware en Linux)."""
    if "bluetooth" in (p.description or "").lower():
        return False
    if p.vid == 0x2CA3:      # control o dron DJI: no habla MAVLink
        return False
    if not sys.platform.startswith("win") and (p.hwid or "n/a") == "n/a":
        return False
    return True

def resetear_telemetria_en_vivo():
    """Evita que un vuelo nuevo arranque con la posicion/valores del vuelo anterior."""
    estado.lat = estado.lon = 0.0
    estado.alt_msl = estado.alt_rel = 0.0
    estado.roll = estado.pitch = estado.yaw = estado.velocidad = 0.0
    estado.satelites = 0
    estado.modo_vuelo = "DESCONOCIDO"
    estado.ultimo_msg_tiempo = 0.0
    estado.ultima_solicitud_stream = 0.0
    estado.sistema_autopiloto = None
    estado.ultimo_registro_tiempo = 0
    estado.ultimos_voltajes.clear()
    estado.armado = False
    estado.rc_canales = 0
    estado.wp_actual = None

def solicitar_streams(conn):
    """Pide al autopiloto todos los streams a 4 Hz (se repite periodicamente por si se pierde)."""
    try:
        conn.mav.request_data_stream_send(
            conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1
        )
    except Exception:
        pass

def abrir_conexion_mavlink(puerto):
    if "udp" in puerto.lower() or "tcp" in puerto.lower():
        return mavutil.mavlink_connection(puerto, source_system=254)
    return mavutil.mavlink_connection(puerto, baud=57600, source_system=254)

def registrar_medios_previos(ip):
    """Guarda la lista de archivos que YA estaban en la SD para no descargarlos como 'nuevos'."""
    medios = obtener_lista_medios_gopro(ip)
    if medios is None:
        estado.snapshot_medios_tomado = False
        return 0
    estado.fotos_previas = {(d, n) for d, n, cre, size in medios}
    estado.snapshot_medios_tomado = True
    return len(estado.fotos_previas)

# Calidad maxima de video para la GoPro HERO13 Black (ajustes de la API Open GoPro).
# Cada ajuste lleva sus opciones en orden de preferencia: si la camara rechaza la
# primera (HTTP 403 por combinacion no permitida) se prueba la siguiente.
# El orden importa: Controles Pro habilita bitrate/bits/perfil y la resolucion
# limita los lentes disponibles.
CALIDAD_MAXIMA_GOPRO = [
    (175, [1],     "Controles",            {1: "Pro"}),
    (2,   [100, 1], "Resolucion",          {100: "5.3K (5312x2988)", 1: "4K (3840x2160)"}),
    (3,   [8],     "Cuadros por segundo",  {8: "30 fps"}),
    (121, [4, 0],  "Lente",                {4: "Linear (sin ojo de pez)", 0: "Wide"}),
    (135, [0],     "Estabilizacion",       {0: "Apagada (sin recorte)"}),
    (182, [1],     "Bitrate",              {1: "Alto (~120 Mbps)"}),
    (183, [2],     "Profundidad de color", {2: "10 bits"}),
    (184, [0],     "Perfil de color",      {0: "Estandar (sin LOG)"}),
]

def configurar_gopro_maxima_calidad(ip):
    """
    Pone la GoPro en modo Video con la maxima calidad y comprueba, leyendo el
    estado de la camara, que cada ajuste quedo aplicado.
    Devuelve (todo_ok, reporte) con una fila por ajuste: nombre, valor, ok.
    """
    base = f"http://{ip}:8080/gopro/camera"
    reporte = []
    try:
        requests.get(f"{base}/control/wired_usb?p=1", timeout=2)
        requests.get(f"{base}/presets/set_group?id=1000", timeout=2)
        time.sleep(0.5)
        for ajuste, opciones, nombre, textos in CALIDAD_MAXIMA_GOPRO:
            elegida = None
            for op in opciones:
                try:
                    r = requests.get(f"{base}/setting?setting={ajuste}&option={op}", timeout=3)
                    if r.status_code == 200:
                        elegida = op
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.2)
            reporte.append({"id": ajuste, "nombre": nombre, "opcion": elegida,
                            "valor": textos.get(elegida, "rechazado por la camara"),
                            "ok": elegida == opciones[0]})
            time.sleep(0.3)  # la camara necesita un momento entre ajustes

        # Verificacion final contra el estado real de la camara
        r = requests.get(f"{base}/state", timeout=3)
        actuales = r.json().get("settings", {}) if r.status_code == 200 else {}
        for fila in reporte:
            real = actuales.get(str(fila["id"]))
            if real is not None and real != fila["opcion"]:
                fila["ok"] = False
                fila["valor"] = f"no quedo aplicado (camara en opcion {real})"
    except Exception as e:
        reporte.append({"id": None, "nombre": "Comunicacion", "opcion": None,
                        "valor": f"error: {e}", "ok": False})
    estado.gopro_config = reporte
    return all(f["ok"] for f in reporte), reporte

def resumen_config(reporte):
    if not reporte:
        return "sin configurar"
    fallas = [f"{f['nombre']}: {f['valor']}" for f in reporte if not f["ok"]]
    return "calidad maxima aplicada" if not fallas else "ATENCION " + "; ".join(fallas)

def activar_shutter_gopro(ip, iniciar=True):
    """
    Envia la orden de iniciar/detener grabacion a la GoPro y VERIFICA
    activamente contra el sensor interno de la camara (status 10).
    Antes de iniciar aplica la configuracion de calidad maxima.
    """
    try:
        requests.get(f"http://{ip}:8080/gopro/camera/control/wired_usb?p=1", timeout=2)
        if iniciar:
            configurar_gopro_maxima_calidad(ip)

        endpoint = "start" if iniciar else "stop"
        r = requests.get(f"http://{ip}:8080/gopro/camera/shutter/{endpoint}", timeout=3)
        if r.status_code != 200:
            return False, f"La camara respondio HTTP {r.status_code}"

        # Comprobacion activa del sensor de grabacion
        objetivo = 1 if iniciar else 0
        for _ in range(7):
            time.sleep(0.4)
            r_st = requests.get(f"http://{ip}:8080/gopro/camera/state", timeout=1.5)
            if r_st.status_code == 200:
                st = r_st.json().get("status", {}).get("10")
                if st == objetivo:
                    if iniciar:
                        return True, f"Grabacion confirmada en la camara ({resumen_config(estado.gopro_config)})"
                    return True, "Grabacion detenida correctamente"

        return False, "La orden se envio pero el sensor interno no confirmo el cambio de estado"
    except Exception as e:
        return False, f"Error de comunicacion con la camara: {e}"

def consultar_grabacion_gopro(ip):
    """Consulta si la GoPro esta actualmente grabando (status 10 == 1)."""
    try:
        r = requests.get(f"http://{ip}:8080/gopro/camera/state", timeout=1.5)
        if r.status_code == 200:
            status = r.json().get("status", {})
            return status.get("10") == 1
    except Exception:
        pass
    return False

def obtener_lista_medios_gopro(ip):
    """Lista todos los archivos multimedia en la tarjeta SD de la GoPro."""
    try:
        r = requests.get(f"http://{ip}:8080/gopro/media/list", timeout=3)
        if r.status_code == 200:
            datos = r.json()
            archivos = []
            for medio in datos.get("media", []):
                d = medio.get("d", "")
                for f in medio.get("fs", []):
                    nombre = f.get("n", "")
                    if nombre.lower().endswith(('.thm', '.lrv')):
                        continue
                    archivos.append((d, nombre, int(f.get("cre", 0)), int(f.get("s", 0))))
            return archivos
    except Exception:
        pass
    return None  # error de lectura: distinto de tarjeta vacia

def guardar_mision():
    """Guarda el estado de la mision en disco para poder reintentar aunque se cierre el dashboard."""
    if not estado.carpeta_mision:
        return
    try:
        ruta = os.path.join(estado.carpeta_mision, "mision.json")
        with open(ruta + ".part", "w", encoding="utf-8") as f:
            json.dump({"inicio": estado.tiempo_inicio_vuelo, "intervalo": estado.intervalo_fotos_seg,
                       "snapshot": estado.snapshot_medios_tomado, "previas": sorted(estado.fotos_previas),
                       "proceso": estado.estado_proceso}, f)
        os.replace(ruta + ".part", ruta)
    except Exception as e:
        print(f"[AVISO] No se pudo guardar mision.json: {e}")

def recuperar_mision():
    """Al arrancar, deja lista para reintentar la ultima mision si quedo sin procesar."""
    try:
        carpetas = rutas.carpetas()
        carpetas = [c for c in carpetas if os.path.dirname(c) == rutas.F450]
        if not carpetas:
            return
        carpeta = max(carpetas, key=lambda c: c[-15:])
        with open(os.path.join(carpeta, "mision.json"), encoding="utf-8") as f:
            m = json.load(f)
        if m["proceso"] == "COMPLETADO":
            return
        estado.carpeta_mision = carpeta
        estado.ruta_csv = os.path.join(carpeta, "telemetria.csv")
        estado.tiempo_inicio_vuelo = m["inicio"]
        estado.intervalo_fotos_seg = m["intervalo"]
        estado.snapshot_medios_tomado = m["snapshot"]
        estado.fotos_previas = {tuple(x) for x in m["previas"]}
        estado.estado_proceso = "ERROR"
        estado.mensaje_proceso = f"Mision {os.path.basename(carpeta)} sin procesar. Conecte la GoPro y presione Finalizar y Procesar."
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[AVISO] No se pudo recuperar la ultima mision: {e}")

def bucle_telemetria():
    """Hilo secundario que captura y almacena paquetes MAVLink en vivo."""
    global estado
    errores_seguidos = 0
    while estado.en_grabacion:
        try:
            if not estado.conexion_mavlink:
                time.sleep(0.1)
                continue

            ahora = time.time()
            # Re-solicitar streams cada 10 s mientras no lleguen datos (radio recien conectada,
            # Pixhawk reiniciada o solicitud inicial perdida en el enlace de 915 MHz)
            if ahora - estado.ultimo_msg_tiempo > 3 and ahora - estado.ultima_solicitud_stream > 10:
                solicitar_streams(estado.conexion_mavlink)
                estado.ultima_solicitud_stream = ahora

            msg = estado.conexion_mavlink.recv_msg()
            errores_seguidos = 0
            if msg is None:
                time.sleep(0.01)
                continue

            mtype = msg.get_type()
            if mtype == 'BAD_DATA':
                continue
            # Solo aceptar datos del autopiloto (ignorar heartbeats de GCS como Mission Planner)
            if mtype == 'HEARTBEAT':
                if msg.type == mavutil.mavlink.MAV_TYPE_GCS or msg.autopilot == mavutil.mavlink.MAV_AUTOPILOT_INVALID:
                    continue
                if estado.sistema_autopiloto is None:
                    estado.sistema_autopiloto = msg.get_srcSystem()
            if estado.sistema_autopiloto is not None and msg.get_srcSystem() != estado.sistema_autopiloto:
                continue
            estado.ultimo_msg_tiempo = time.time()

            # Guardar en archivo binario tlog
            if estado.archivo_tlog:
                try:
                    estado.archivo_tlog.write(struct.pack('>Q', int(time.time() * 1e6)) + msg.get_msgbuf())
                except Exception:
                    pass

            control_rc._mensaje(msg)
            if mtype == 'HEARTBEAT':
                cm = getattr(msg, 'custom_mode', 0)
                estado.modo_vuelo = MODOS_ARDUPILOT.get(cm, f"MODO_{cm}")
                estado.armado = bool(msg.base_mode & 128)

            elif mtype == 'RC_CHANNELS':
                estado.rc_canales = msg.chancount

            elif mtype == 'MISSION_CURRENT':
                estado.wp_actual = msg.seq

            elif mtype == 'GLOBAL_POSITION_INT':
                estado.lat = msg.lat / 1e7
                estado.lon = msg.lon / 1e7
                estado.alt_msl = msg.alt / 1000.0
                estado.alt_rel = msg.relative_alt / 1000.0
                vx = msg.vx / 100.0
                vy = msg.vy / 100.0
                estado.velocidad = (vx**2 + vy**2)**0.5

            elif mtype == 'GPS_RAW_INT':
                estado.satelites = getattr(msg, 'satellites_visible', estado.satelites)
                if estado.lat == 0.0 and msg.lat != 0:
                    estado.lat = msg.lat / 1e7
                    estado.lon = msg.lon / 1e7
                    estado.alt_msl = msg.alt / 1000.0

            elif mtype == 'ATTITUDE':
                import math
                estado.roll = math.degrees(msg.roll)
                estado.pitch = math.degrees(msg.pitch)
                yaw = math.degrees(msg.yaw)
                estado.yaw = yaw if yaw >= 0 else (yaw + 360.0)

            elif mtype == 'SYS_STATUS':
                if 0 < msg.voltage_battery < 65535:
                    estado.bateria_dron = msg.voltage_battery / 1000.0
                    estado.ultimos_voltajes.append(estado.bateria_dron)

            elif mtype == 'BATTERY_STATUS':
                if hasattr(msg, 'voltages') and len(msg.voltages) > 0 and msg.voltages[0] != 65535:
                    v_tot = sum([v for v in msg.voltages if v != 65535]) / 1000.0
                    if v_tot > 0:
                        estado.bateria_dron = v_tot

            ahora = time.time()
            # Escribir linea de telemetria en CSV cada 250 ms (4 Hz)
            tiene_posicion = not (estado.lat == 0.0 and estado.lon == 0.0)
            if ahora >= estado.ultimo_registro_tiempo and estado.archivo_csv and tiene_posicion:
                t_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                linea = (
                    f"{t_utc},{estado.lat:.7f},{estado.lon:.7f},{estado.alt_msl:.2f},"
                    f"{estado.alt_rel:.2f},{estado.roll:.2f},{estado.pitch:.2f},"
                    f"{estado.yaw:.2f},{estado.velocidad:.2f},{estado.satelites},"
                    f"{estado.bateria_dron:.2f},{estado.modo_vuelo}\n"
                )
                estado.archivo_csv.write(linea)
                estado.archivo_csv.flush()
                # Programar el proximo registro a +250 ms (evita derivar a ~3.3 Hz)
                estado.ultimo_registro_tiempo = max(estado.ultimo_registro_tiempo + 0.25, ahora - 0.25)
                estado.total_registros += 1

        except Exception as e:
            errores_seguidos += 1
            # Puerto serie caido (cable USB de la radio flojo/desconectado): reintentar abrirlo
            if errores_seguidos >= 20 and estado.en_grabacion and estado.puerto_real:
                print(f"[AVISO] Enlace de telemetria con errores ({e}). Reintentando abrir {estado.puerto_real}...")
                try:
                    estado.conexion_mavlink.close()
                except Exception:
                    pass
                time.sleep(2)
                try:
                    if estado.en_grabacion:
                        # el USB puede volver con otro nombre (ttyUSB1 -> ttyUSB0)
                        if estado.puerto_real.startswith("/dev/") and not os.path.exists(estado.puerto_real):
                            estado.puerto_real = buscar_puerto_pixhawk() or estado.puerto_real
                        estado.conexion_mavlink = abrir_conexion_mavlink(estado.puerto_real)
                        estado.ultima_solicitud_stream = 0.0
                        print("[OK] Puerto de telemetria reabierto.")
                except Exception:
                    pass
                errores_seguidos = 0
            else:
                time.sleep(0.05)


@app.get("/", response_class=HTMLResponse)
async def index():
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Vuelo F450</title>
    <style>
        :root {
            --primary: #0F2942;
            --primary-light: #1A5F7A;
            --accent: #2C7A7B;
            --bg: #F8FAFC;
            --card-bg: #FFFFFF;
            --text: #1E293B;
            --text-muted: #64748B;
            --border: #CBD5E1;
            --success: #15803D;
            --success-bg: #F0FDF4;
            --warning: #B45309;
            --warning-bg: #FFFBEB;
            --danger: #B91C1C;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body { background-color: var(--bg); color: var(--text); padding: 20px; }
        .container { max-width: 1100px; margin: 0 auto; }
        
        header { background: var(--primary); color: white; padding: 20px 28px; border-radius: 8px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; }
        header h1 { font-size: 1.35rem; font-weight: 700; letter-spacing: 0.5px; }
        header p { font-size: 0.85rem; color: #94A3B8; margin-top: 4px; }
        .badge-status { padding: 6px 14px; border-radius: 20px; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; background: #334155; color: #E2E8F0; }
        .badge-recording { background: #DC2626; color: white; animation: pulse 1.5s infinite; }
        
        .badge-cam-rec { background: #DC2626; color: white; font-size: 0.76rem; padding: 4px 10px; border-radius: 12px; font-weight: 700; animation: pulse 1.2s infinite; }
        .badge-cam-idle { background: #E2E8F0; color: #475569; font-size: 0.76rem; padding: 4px 10px; border-radius: 12px; font-weight: 600; }
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }

        /* Banner de Autoescaneo Activo */
        .scan-banner { background: #FFFFFF; border: 2px solid #CBD5E1; border-radius: 8px; padding: 16px 20px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.06); }
        .scan-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
        .scan-title { font-size: 1.05rem; font-weight: 700; color: var(--primary); }
        .scan-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
        @media (max-width: 768px) { .scan-grid { grid-template-columns: 1fr; } }
        .scan-item { background: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 14px; border-radius: 6px; }
        .scan-item-lbl { font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 4px; }
        .scan-item-val { font-size: 0.95rem; font-weight: 700; }
        .scan-item-sub { font-size: 0.78rem; color: var(--text-muted); margin-top: 2px; }
        .scan-btn { padding: 8px 16px; font-size: 0.85rem; border-radius: 6px; font-weight: 600; border: none; cursor: pointer; background: var(--accent); color: white; transition: background 0.2s; }
        .scan-btn:hover { background: #234E52; }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card h2 { font-size: 1.05rem; color: var(--primary); margin-bottom: 14px; border-bottom: 1px solid #E2E8F0; padding-bottom: 8px; }
        
        .status-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #F1F5F9; font-size: 0.9rem; align-items: center; }
        .status-label { color: var(--text-muted); }
        .status-value { font-weight: 600; }
        .val-ok { color: var(--success); }
        .val-warn { color: var(--warning); }
        .val-bad { color: var(--danger); }

        .metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 15px 0; }
        @media (max-width: 600px) { .metrics-grid { grid-template-columns: repeat(2, 1fr); } }
        .metric-box { background: #F1F5F9; padding: 12px; border-radius: 6px; text-align: center; }
        .metric-label { font-size: 0.72rem; text-transform: uppercase; color: var(--text-muted); font-weight: 600; margin-bottom: 4px; }
        .metric-val { font-size: 1.35rem; font-weight: 700; color: var(--primary); }
        .metric-sub { font-size: 0.75rem; color: var(--text-muted); }

        .btn-group { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
        button { flex: 1; min-width: 130px; padding: 11px 16px; border-radius: 6px; border: none; font-size: 0.88rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-light); }
        .btn-success { background: var(--success); color: white; }
        .btn-success:hover { background: #166534; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: #991B1B; }
        .btn-secondary { background: #E2E8F0; color: var(--text); }
        .btn-secondary:hover { background: #CBD5E1; }
        .btn-cam-start { background: #0284C7; color: white; }
        .btn-cam-start:hover { background: #0369A1; }
        .btn-cam-stop { background: #475569; color: white; }
        .btn-cam-stop:hover { background: #334155; }
        button:disabled { opacity: 0.45; cursor: not-allowed; }

        .alert-box { padding: 12px 16px; border-radius: 6px; margin-top: 15px; font-size: 0.88rem; display: none; }
        .alert-success { background: var(--success-bg); color: var(--success); border: 1px solid #BBF7D0; }
        .alert-warning { background: var(--warning-bg); color: var(--warning); border: 1px solid #FDE68A; }
        .progress-bar-container { width: 100%; height: 8px; background: #E2E8F0; border-radius: 4px; overflow: hidden; margin-top: 10px; display: none; }
        .progress-bar { height: 100%; width: 0%; background: var(--accent); transition: width 0.3s; }

        .campo { padding: 6px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.88rem; width: 220px; }
        .pasos { margin: 0 0 14px 20px; font-size: 0.88rem; color: var(--text-muted); line-height: 1.6; }
        .btn-grande { padding: 15px 18px; font-size: 1rem; }
        .cfg-lista { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
        .cfg-item { font-size: 0.78rem; padding: 4px 8px; border-radius: 10px; }
        .cfg-ok { background: var(--success-bg); color: var(--success); }
        .cfg-mal { background: #FEF2F2; color: var(--danger); }
        .avanzado { margin-top: 18px; border-top: 1px solid #E2E8F0; padding-top: 12px; }
        .avanzado summary { cursor: pointer; font-size: 0.88rem; font-weight: 600; color: var(--text-muted); }
        .nota { font-size: 0.8rem; color: var(--text-muted); margin-top: 12px; line-height: 1.5; }
        .console-log { background: #0F172A; color: #38BDF8; font-family: monospace; font-size: 0.78rem; padding: 12px; border-radius: 6px; height: 120px; overflow-y: auto; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Vuelo F450 + GoPro HERO13</h1>
                <p>Deteccion de hormigas cortadoras | UTEC PRIA</p>
            </div>
            <div>
                <span id="badge-estado" class="badge-status">Inactivo</span>
            </div>
        </header>

        <!-- ESTADO DEL EQUIPO -->
        <div class="scan-banner" id="banner-autoescaneo">
            <div class="scan-header">
                <div>
                    <div class="scan-title" id="txt-scan-titulo">Revisando equipo...</div>
                    <div style="font-size: 0.82rem; color: var(--text-muted);" id="txt-scan-sub">Radio 915 MHz, bateria del dron y GoPro por USB</div>
                </div>
                <div>
                    <button class="scan-btn" id="btn-scan" onclick="ejecutarAutoescaneo()">Revisar de nuevo</button>
                </div>
            </div>
            <div class="scan-grid">
                <div class="scan-item">
                    <div class="scan-item-lbl">Radio / Pixhawk</div>
                    <div class="scan-item-val" id="scan-val-radio">Buscando...</div>
                    <div class="scan-item-sub" id="scan-sub-radio">Esperando paquetes MAVLink</div>
                </div>
                <div class="scan-item">
                    <div class="scan-item-lbl">Bateria del dron (LiPo 3S)</div>
                    <div class="scan-item-val" id="scan-val-bat">--</div>
                    <div class="scan-item-sub" id="scan-sub-bat">Sin lectura</div>
                </div>
                <div class="scan-item">
                    <div class="scan-item-lbl">GoPro HERO13</div>
                    <div class="scan-item-val" id="scan-val-gopro">Buscando...</div>
                    <div class="scan-item-sub" id="scan-sub-gopro">Conecte el cable USB</div>
                </div>
            </div>
        </div>

        <!-- VUELO -->
        <div class="card" style="margin-bottom: 20px;">
            <h2>Vuelo</h2>
            <ol class="pasos">
                <li>Conecte la GoPro a la PC por USB y encienda el dron.</li>
                <li>Presione <b>Comenzar vuelo</b>: configura la camara en calidad maxima, sincroniza la hora y empieza a grabar.</li>
                <li>Desconecte el cable y vuele.</li>
                <li>Al aterrizar, conecte el cable y presione <b>Finalizar y procesar</b>.</li>
            </ol>

            <div class="status-row">
                <span class="status-label">Nombre del vuelo:</span>
                <input type="text" id="input-mision" value="Vuelo_Campo_01" class="campo">
            </div>
            <div class="status-row">
                <span class="status-label">Calidad de video:</span>
                <span class="status-value">Maxima: 5.3K, 30 fps, 10 bits, bitrate alto, lente Linear, color Estandar</span>
            </div>
            <div id="cfg-camara" class="cfg-lista"></div>

            <div class="btn-group">
                <button id="btn-iniciar" class="btn-success btn-grande" onclick="iniciarGrabacion()">Comenzar vuelo</button>
                <button id="btn-finalizar" class="btn-danger btn-grande" onclick="finalizarYProcesar()" disabled>Finalizar y procesar</button>
            </div>

            <div class="progress-bar-container" id="bar-container">
                <div class="progress-bar" id="prog-bar"></div>
            </div>
            <div id="msg-proceso" class="alert-box"></div>

            <details class="avanzado">
                <summary>Opciones avanzadas</summary>
                <div class="status-row">
                    <span class="status-label">Puerto de telemetria:</span>
                    <select id="sel-puerto" class="campo">
                        <option value="AUTO">Deteccion automatica</option>
                    </select>
                </div>
                <div class="status-row">
                    <span class="status-label">Fotos a extraer del video:</span>
                    <select id="sel-intervalo" class="campo">
                        <option value="1.0" selected>1 foto por segundo</option>
                        <option value="0.5">2 fotos por segundo</option>
                        <option value="2.0">1 foto cada 2 segundos</option>
                    </select>
                </div>
                <div class="btn-group">
                    <button id="btn-config" class="btn-primary" onclick="configurarCamara()">Aplicar calidad maxima</button>
                    <button id="btn-sync" class="btn-secondary" onclick="sincronizarRelojes()">Sincronizar hora</button>
                    <button id="btn-cam-rec-start" class="btn-cam-start" onclick="iniciarGrabacionCamara()">Grabar camara</button>
                    <button id="btn-cam-rec-stop" class="btn-cam-stop" onclick="detenerGrabacionCamara()">Detener camara</button>
                </div>
                <div id="msg-sync" class="alert-box"></div>
                <p class="nota">Ajustes que la camara no permite cambiar por USB (hagalos una vez en la GoPro, menu Protune):
                nitidez <b>Alta</b>, obturador <b>1/480 o mas rapido</b> con sol (o Auto), ISO maximo <b>800</b>.</p>
            </details>
        </div>

        <!-- TELEMETRIA EN VIVO -->
        <div class="card">
            <h2>Telemetria en vivo</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-label">Altura</div>
                    <div class="metric-val" id="met-alt-rel">0.0 m</div>
                    <div class="metric-sub">Sobre el despegue</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Modo</div>
                    <div class="metric-val" id="met-modo">--</div>
                    <div class="metric-sub" id="met-sats">0 satelites</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Bateria</div>
                    <div class="metric-val" id="met-bat">0.0 V</div>
                    <div class="metric-sub">Alarma: &lt;10.5 V</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Registros</div>
                    <div class="metric-val" id="met-regs">0</div>
                    <div class="metric-sub">telemetria.csv</div>
                </div>
            </div>
            <div class="status-row">
                <span class="status-label">Posicion:</span>
                <span id="met-coords" class="status-value">Lat: 0.000000 | Lon: 0.000000</span>
            </div>
            <div class="status-row">
                <span class="status-label">Rumbo y velocidad:</span>
                <span id="met-rumbo-vel" class="status-value">Rumbo: 0.0° | Vel: 0.0 m/s</span>
            </div>
        </div>

        <div class="console-log" id="consola-log">
            [SISTEMA] Panel iniciado. Revisando equipo...
        </div>
    </div>

    <script>
        let ultimoAutoescaneo = null;

        function logMsg(msg) {
            const el = document.getElementById("consola-log");
            const t = new Date().toTimeString().split(' ')[0];
            el.innerHTML += `<div>[${t}] ${msg}</div>`;
            el.scrollTop = el.scrollHeight;
        }

        function calcularPorcentaje3S(v) {
            if (v <= 0) return 0;
            const pct = Math.round(((v - 10.5) / (12.6 - 10.5)) * 100);
            return Math.max(0, Math.min(100, pct));
        }

        function pintar(id, texto, clase) {
            const el = document.getElementById(id);
            el.innerText = texto;
            if (clase) el.className = "scan-item-val " + clase;
        }

        function mostrarConfig(reporte) {
            const el = document.getElementById("cfg-camara");
            if (!reporte || !reporte.length) { el.innerHTML = ""; return; }
            el.innerHTML = reporte.map(f =>
                `<span class="cfg-item ${f.ok ? 'cfg-ok' : 'cfg-mal'}">${f.ok ? '✓' : '✗'} ${f.nombre}: ${f.valor}</span>`
            ).join("");
            const fallas = reporte.filter(f => !f.ok);
            if (fallas.length) logMsg(`[CAMARA] Ajustes no aplicados: ${fallas.map(f => f.nombre).join(", ")}`);
            else logMsg("[CAMARA] Calidad maxima aplicada y verificada en la camara.");
        }

        async function ejecutarAutoescaneo() {
            const btnScan = document.getElementById("btn-scan");
            btnScan.disabled = true;
            btnScan.innerText = "Revisando...";
            document.getElementById("txt-scan-titulo").innerText = "Revisando equipo...";
            try {
                const r = await fetch("/api/scan_all");
                const d = await r.json();
                ultimoAutoescaneo = d;
                const t = d.telemetria;
                if (t.conectada) {
                    pintar("scan-val-radio", `OK en ${t.puerto}`, (t.avisos || []).length ? "val-warn" : "val-ok");
                    document.getElementById("scan-sub-radio").innerText =
                        [`Modo ${t.modo}`, `${t.satelites} satelites`, ...(t.avisos || [])].join(" | ");
                    (t.avisos || []).forEach(a => logMsg(`[AVISO DRON] ${a}`));
                } else {
                    pintar("scan-val-radio", "Sin senal", "val-bad");
                    document.getElementById("scan-sub-radio").innerText = "Encienda el dron y conecte la radio 915 MHz";
                }
                const tEl = document.getElementById("txt-scan-titulo");
                if (t.conectada && d.gopro.conectada) {
                    tEl.innerText = "Equipo listo"; tEl.style.color = "var(--success)";
                } else {
                    tEl.innerText = t.conectada ? "Falta conectar la GoPro por USB" : "Esperando senal del dron";
                    tEl.style.color = "var(--warning)";
                }
                logMsg(`[REVISION] Radio: ${t.conectada ? 'OK' : 'sin senal'} | GoPro: ${d.gopro.conectada ? 'OK' : 'desconectada'}`);
                actualizarHardware();
            } catch (e) {
                logMsg(`[ERROR] ${e}`);
            } finally {
                btnScan.disabled = false;
                btnScan.innerText = "Revisar de nuevo";
            }
        }

        async function actualizarHardware() {
            try {
                const r = await fetch("/api/status");
                const d = await r.json();

                // GoPro
                if (d.gopro_conectada) {
                    pintar("scan-val-gopro", d.gopro_grabando ? "GRABANDO" : `Conectada (${d.gopro_bateria}%)`, d.gopro_grabando ? "val-bad" : "val-ok");
                    document.getElementById("scan-sub-gopro").innerText = d.gopro_grabando ? `Bateria ${d.gopro_bateria}%` : "Lista por USB";
                } else if (d.gopro_grabando) {
                    pintar("scan-val-gopro", "Grabando sin cable", "val-ok");
                    document.getElementById("scan-sub-gopro").innerText = "Verifique la luz roja de la camara";
                } else {
                    pintar("scan-val-gopro", "Desconectada", "val-warn");
                    document.getElementById("scan-sub-gopro").innerText = "Conecte el cable USB";
                }

                // Radio durante el vuelo
                if (d.en_grabacion) {
                    const sinSenal = d.segundos_sin_telemetria === null || d.segundos_sin_telemetria > 3;
                    pintar("scan-val-radio", sinSenal ? "Sin senal" : "Recibiendo", sinSenal ? "val-bad" : "val-ok");
                }

                // Bateria
                const vBat = d.bateria_dron || 0;
                const pctBat = calcularPorcentaje3S(vBat);
                const claseBat = vBat >= 11.4 ? "val-ok" : (vBat >= 10.5 ? "val-warn" : "val-bad");
                if (vBat > 9.0) {
                    pintar("scan-val-bat", `${vBat.toFixed(2)} V (${pctBat}%)`, claseBat);
                    document.getElementById("scan-sub-bat").innerText = vBat >= 11.4 ? "Carga suficiente" : "Bateria baja";
                } else {
                    pintar("scan-val-bat", "--", "val-warn");
                    document.getElementById("scan-sub-bat").innerText = "Sin lectura";
                }

                // Puertos
                const sel = document.getElementById("sel-puerto");
                if (d.puertos_disponibles && d.puertos_disponibles.length > 0) {
                    const actual = sel.value;
                    sel.innerHTML = '<option value="AUTO">Deteccion automatica</option>';
                    d.puertos_disponibles.forEach(p => { sel.innerHTML += `<option value="${p.dev}">${p.desc}</option>`; });
                    sel.innerHTML += '<option value="udpin:127.0.0.1:14550">Red UDP (Mission Planner)</option>';
                    sel.value = actual;
                }

                // Estado del vuelo
                const badge = document.getElementById("badge-estado");
                const btnIni = document.getElementById("btn-iniciar");
                const btnFin = document.getElementById("btn-finalizar");
                if (d.en_grabacion) {
                    const sinSenal = d.segundos_sin_telemetria === null || d.segundos_sin_telemetria > 3;
                    badge.innerText = sinSenal ? "EN VUELO - SIN SENAL DEL DRON" : "EN VUELO - GRABANDO";
                    badge.className = sinSenal ? "badge-status" : "badge-status badge-recording";
                    badge.style.background = sinSenal ? "var(--danger)" : "";
                    btnIni.disabled = true;
                    btnFin.disabled = false;
                } else {
                    badge.innerText = d.estado_proceso;
                    badge.className = "badge-status";
                    badge.style.background = "";
                    btnIni.disabled = d.procesando;
                    btnFin.disabled = !(d.estado_proceso === "ERROR" && d.carpeta_mision);
                }

                // Metricas
                document.getElementById("met-alt-rel").innerText = `${d.alt_rel.toFixed(1)} m`;
                document.getElementById("met-modo").innerText = d.modo_vuelo;
                document.getElementById("met-sats").innerText = `${d.satelites} satelites`;
                const metBat = document.getElementById("met-bat");
                metBat.innerText = vBat > 9.0 ? `${vBat.toFixed(1)} V (${pctBat}%)` : "0.0 V";
                metBat.style.color = vBat > 9.0 ? `var(--${claseBat === "val-ok" ? "success" : claseBat === "val-warn" ? "warning" : "danger"})` : "var(--primary)";
                document.getElementById("met-regs").innerText = d.total_registros;
                document.getElementById("met-coords").innerText = `Lat: ${d.lat.toFixed(6)} | Lon: ${d.lon.toFixed(6)}`;
                document.getElementById("met-rumbo-vel").innerText = `Rumbo: ${d.yaw.toFixed(1)}° | Vel: ${d.velocidad.toFixed(1)} m/s`;

                // Procesamiento
                const msgProc = document.getElementById("msg-proceso");
                const barCont = document.getElementById("bar-container");
                const bar = document.getElementById("prog-bar");
                if (["DESCARGANDO", "ETIQUETANDO", "PROCESANDO_VIDEO"].includes(d.estado_proceso)) {
                    msgProc.style.display = "block";
                    msgProc.className = "alert-box alert-warning";
                    msgProc.innerText = d.mensaje_proceso;
                    barCont.style.display = "block";
                    bar.style.width = `${d.progreso_porcentaje}%`;
                } else if (d.estado_proceso === "COMPLETADO") {
                    msgProc.style.display = "block";
                    msgProc.className = "alert-box alert-success";
                    msgProc.innerText = d.mensaje_proceso + " ";
                    const b = document.createElement("button");
                    b.className = "btn-secondary"; b.style.marginTop = "8px"; b.innerText = "Abrir carpeta de fotos";
                    b.onclick = () => abrirCarpeta(d.carpeta_mision + "/fotos");
                    msgProc.appendChild(b);
                    barCont.style.display = "none";
                } else if (d.estado_proceso === "ERROR") {
                    msgProc.style.display = "block";
                    msgProc.className = "alert-box alert-warning";
                    msgProc.innerText = d.mensaje_proceso;
                    barCont.style.display = "none";
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function configurarCamara() {
            const btn = document.getElementById("btn-config");
            btn.disabled = true;
            logMsg("[CAMARA] Aplicando calidad maxima...");
            try {
                const d = await (await fetch("/api/gopro/configurar", { method: "POST" })).json();
                if (d.reporte) mostrarConfig(d.reporte);
                else logMsg(`[CAMARA ERROR] ${d.error}`);
            } catch (e) {
                logMsg(`[CAMARA ERROR] ${e}`);
            } finally {
                btn.disabled = false;
            }
        }

        async function sincronizarRelojes() {
            const btn = document.getElementById("btn-sync");
            btn.disabled = true;
            try {
                const d = await (await fetch("/api/sync_clocks", { method: "POST" })).json();
                const el = document.getElementById("msg-sync");
                el.style.display = "block";
                el.className = d.exito ? "alert-box alert-success" : "alert-box alert-warning";
                el.innerText = d.exito
                    ? `Hora sincronizada (${d.hora}). Desfase camara - PC: ${d.desfase === null ? 'no disponible' : d.desfase + ' s'}.`
                    : `Error: ${d.error}`;
                logMsg(d.exito ? "[OK] Hora de la camara sincronizada." : `[ERROR] ${d.error}`);
            } catch (e) {
                logMsg(`[ERROR] ${e}`);
            } finally {
                btn.disabled = false;
                actualizarHardware();
            }
        }

        async function iniciarGrabacionCamara() {
            logMsg("[CAMARA] Configurando calidad maxima e iniciando grabacion...");
            try {
                const d = await (await fetch("/api/gopro/shutter/start", { method: "POST" })).json();
                if (d.reporte) mostrarConfig(d.reporte);
                logMsg(d.exito ? `[CAMARA] ${d.mensaje}` : `[CAMARA ERROR] ${d.error || d.mensaje}`);
                if (!d.exito) alert(`Error en camara: ${d.error || d.mensaje}`);
            } catch (e) {
                logMsg(`[CAMARA ERROR] ${e}`);
            }
            actualizarHardware();
        }

        async function detenerGrabacionCamara() {
            try {
                const d = await (await fetch("/api/gopro/shutter/stop", { method: "POST" })).json();
                logMsg(d.exito ? `[CAMARA] ${d.mensaje}` : `[CAMARA ERROR] ${d.error || d.mensaje}`);
            } catch (e) {
                logMsg(`[CAMARA ERROR] ${e}`);
            }
            actualizarHardware();
        }

        async function iniciarGrabacion() {
            if (ultimoAutoescaneo && !ultimoAutoescaneo.telemetria.conectada) {
                if (!confirm("No llega senal del dron por la radio 915 MHz.\\n\\n¿Comenzar de todos modos?")) return;
            }
            if (ultimoAutoescaneo && !ultimoAutoescaneo.gopro.conectada) {
                if (!confirm("La GoPro no esta conectada por USB: no se podra configurar la calidad ni iniciar la grabacion.\\n\\n¿Comenzar de todos modos?")) return;
            }
            const btn = document.getElementById("btn-iniciar");
            btn.disabled = true;
            const mision = document.getElementById("input-mision").value.trim() || "Vuelo";
            const puerto = document.getElementById("sel-puerto").value;
            const intervalo = parseFloat(document.getElementById("sel-intervalo").value) || 1.0;
            logMsg(`Comenzando vuelo ${mision}: configurando camara y telemetria...`);
            try {
                const d = await (await fetch("/api/flight/start", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mision: mision, puerto: puerto, intervalo: intervalo })
                })).json();
                if (!d.exito) {
                    alert(`Error al comenzar: ${d.error}`);
                    logMsg(`[ERROR] ${d.error}`);
                    return;
                }
                logMsg(`[+] Telemetria en ${d.puerto}.`);
                if (d.hora_sincronizada) logMsg("[+] Hora de la camara sincronizada con la PC.");
                mostrarConfig(d.gopro_config);
                if (d.advertencia) { logMsg(`[AVISO] ${d.advertencia}`); alert(`ATENCION: ${d.advertencia}`); }
                if (d.gopro_iniciada) {
                    logMsg(`[+] ${d.gopro_mensaje}`);
                } else {
                    logMsg(`[AVISO] CAMARA NO CONFIRMADA: ${d.gopro_mensaje}`);
                    alert(`ATENCION: la camara NO esta confirmada como grabando.\\n${d.gopro_mensaje}\\nVerifiquela antes de despegar.`);
                }
            } catch (e) {
                logMsg(`[ERROR] ${e}`);
            } finally {
                actualizarHardware();
            }
        }

        async function finalizarYProcesar() {
            if (!confirm("¿Finalizar el vuelo y descargar y procesar el video de la GoPro?")) return;
            logMsg("Deteniendo telemetria y procesando el video...");
            const d = await (await fetch("/api/flight/stop_and_process", { method: "POST" })).json();
            logMsg(d.mensaje || `[ERROR] ${d.error}`);
            actualizarHardware();
        }

        async function abrirCarpeta(ruta) {
            await fetch(`/api/open_folder?ruta=${encodeURIComponent(ruta)}`);
        }

        setInterval(actualizarHardware, 1000);
        ejecutarAutoescaneo();
    </script>
    <script src="/static/pestanas.js?v=4"></script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/api/scan_all")
def scan_all():
    with PUERTO_LOCK:
        return _scan_all()

def _scan_all():
    """Realiza un autoescaneo activo enviando pruebas reales a la radio y GoPro."""
    global estado
    
    # 1. Probar GoPro
    gp_ip = buscar_ip_gopro()
    gp_ok = False
    gp_batt = "--"
    gp_shutter = False
    gp_grabando = estado.gopro_grabando
    if gp_ip:
        try:
            r = requests.get(f"http://{gp_ip}:8080/gopro/version", timeout=1.2)
            if r.status_code == 200:
                gp_ok = True
                gp_batt = consultar_estado_gopro(gp_ip)
                r_ctrl = requests.get(f"http://{gp_ip}:8080/gopro/camera/control/wired_usb?p=1", timeout=1.5)
                gp_shutter = (r_ctrl.status_code == 200)
                gp_grabando = consultar_grabacion_gopro(gp_ip)
                estado.gopro_ip = gp_ip
                estado.gopro_bateria = gp_batt
                estado.gopro_grabando = gp_grabando
        except Exception:
            pass

    # 2. Probar Radio 915 MHz y MAVLink real
    avisos = set()
    if estado.en_grabacion and estado.conexion_mavlink:
        telem_ok = bool(estado.ultimo_msg_tiempo) and time.time() - estado.ultimo_msg_tiempo < 3
        telem_puerto = "Activo"
        telem_modo = estado.modo_vuelo
        telem_paquetes = estado.total_registros or 10
        telem_voltaje = estado.bateria_dron
        telem_sats = estado.satelites
    else:
        puertos_raw = list(serial.tools.list_ports.comports())
        candidatos = [p.device for p in puertos_raw if puerto_es_util(p)]
        telem_ok = False
        telem_puerto = None
        telem_modo = "DESCONOCIDO"
        telem_paquetes = 0
        voltajes = []
        telem_voltaje = estado.bateria_dron
        telem_sats = estado.satelites

        for port in candidatos:
            try:
                m = mavutil.mavlink_connection(port, baud=57600, source_system=254)
                if not m.wait_heartbeat(timeout=2.5):
                    m.close()
                    continue
                solicitar_streams(m)
                t_ini = time.time()
                while time.time() - t_ini < 3.0:
                    msg = m.recv_match(blocking=True, timeout=0.3)
                    if msg and msg.get_type() != 'BAD_DATA' and msg.get_srcSystem() == m.target_system:
                        telem_paquetes += 1
                        mtype = msg.get_type()
                        if mtype == 'HEARTBEAT':
                            cm = getattr(msg, 'custom_mode', 0)
                            telem_modo = MODOS_ARDUPILOT.get(cm, f"MODO_{cm}")
                        elif mtype == 'SYS_STATUS':
                            if 0 < msg.voltage_battery < 65535:
                                voltajes.append(msg.voltage_battery / 1000.0)
                                telem_voltaje = sum(voltajes) / len(voltajes)
                                estado.bateria_dron = telem_voltaje
                            # Salida de motores deshabilitada = boton de seguridad activo
                            if not msg.onboard_control_sensors_enabled & 32768:
                                avisos.add("Boton de seguridad activo: no armara")
                        elif mtype == 'GPS_RAW_INT':
                            telem_sats = getattr(msg, 'satellites_visible', telem_sats)
                            estado.satelites = telem_sats
                            if msg.fix_type < 3:
                                avisos.add("GPS sin fix 3D")
                        elif mtype == 'RC_CHANNELS':
                            if msg.chancount == 0:
                                avisos.add("Sin senal del control remoto")
                        elif mtype == 'STATUSTEXT' and 'PreArm' in msg.text:
                            avisos.add(msg.text)
                        if telem_paquetes >= 3:
                            telem_ok = True
                            telem_puerto = port
                m.close()
                if telem_ok:
                    break
            except Exception:
                pass

    return {
        "gopro": {
            "conectada": gp_ok,
            "ip": gp_ip,
            "bateria": gp_batt,
            "shutter_listo": gp_shutter,
            "grabando": gp_grabando
        },
        "telemetria": {
            "conectada": telem_ok,
            "puerto": telem_puerto or "--",
            "avisos": sorted(avisos),
            "modo": telem_modo,
            "paquetes": telem_paquetes,
            "bateria_v": telem_voltaje,
            "satelites": telem_sats
        }
    }

@app.post("/api/gopro/shutter/start")
def gopro_shutter_start():
    ip = estado.gopro_ip or buscar_ip_gopro()
    if not ip:
        return {"exito": False, "error": "GoPro no conectada por USB"}
    if not consultar_grabacion_gopro(ip):
        registrar_medios_previos(ip)
    ok, msg = activar_shutter_gopro(ip, iniciar=True)
    estado.gopro_grabando = ok
    return {"exito": ok, "mensaje": msg, "reporte": estado.gopro_config}

@app.post("/api/gopro/shutter/stop")
def gopro_shutter_stop():
    ip = estado.gopro_ip or buscar_ip_gopro()
    if not ip:
        return {"exito": False, "error": "GoPro no conectada por USB"}
    ok, msg = activar_shutter_gopro(ip, iniciar=False)
    if ok:
        estado.gopro_grabando = False
    return {"exito": ok, "mensaje": msg}

@app.get("/api/status")
def get_status():
    global estado
    
    ip_gp = buscar_ip_gopro()
    estado.gopro_ip = ip_gp
    if ip_gp:
        estado.gopro_bateria = consultar_estado_gopro(ip_gp)
        estado.gopro_grabando = consultar_grabacion_gopro(ip_gp)
    else:
        # Camara desconectada del cable USB (modo vuelo en el dron).
        # Mantenemos estado.gopro_grabando = True si ya habia sido iniciada,
        # porque la GoPro continua grabando en la tarjeta SD de forma autonoma con su bateria interna.
        pass

    puertos_raw = list(serial.tools.list_ports.comports())
    puertos = [{"dev": p.device, "desc": f"{p.device} ({p.description})"} for p in puertos_raw if puerto_es_util(p)]
    pix_puerto = buscar_puerto_pixhawk()

    return {
        "en_grabacion": estado.en_grabacion,
        "gopro_conectada": estado.gopro_ip is not None,
        "gopro_ip": estado.gopro_ip,
        "gopro_bateria": estado.gopro_bateria,
        "gopro_grabando": estado.gopro_grabando,
        "pixhawk_puerto": pix_puerto,
        "satelites": estado.satelites,
        "lat": estado.lat,
        "lon": estado.lon,
        "alt_msl": estado.alt_msl,
        "alt_rel": estado.alt_rel,
        "roll": estado.roll,
        "pitch": estado.pitch,
        "yaw": estado.yaw,
        "velocidad": estado.velocidad,
        "bateria_dron": (sum(estado.ultimos_voltajes) / len(estado.ultimos_voltajes)) if estado.ultimos_voltajes else estado.bateria_dron,
        "procesando": estado.procesando,
        "modo_vuelo": estado.modo_vuelo,
        "total_registros": estado.total_registros,
        "segundos_sin_telemetria": (round(time.time() - estado.ultimo_msg_tiempo, 1) if estado.ultimo_msg_tiempo else None),
        "estado_proceso": estado.estado_proceso,
        "mensaje_proceso": estado.mensaje_proceso,
        "progreso_porcentaje": estado.progreso_porcentaje,
        "carpeta_mision": estado.carpeta_mision,
        "puertos_disponibles": puertos
    }

@app.post("/api/sync_clocks")
def sync_clocks():
    global estado
    if estado.en_grabacion or estado.procesando:
        return {"exito": False, "error": "Hay una mision o un procesamiento en curso."}
    gopro_ip = buscar_ip_gopro()
    if not gopro_ip:
        return {"exito": False, "error": "GoPro no encontrada. Verifique la conexion por cable USB."}

    # La telemetria se registra con el reloj de la PC: la camara debe usar esa misma base
    if consultar_grabacion_gopro(gopro_ip):
        return {"exito": False, "error": "La camara esta grabando. Detengala antes de sincronizar."}
    fuente = "Reloj de la Computadora"
    tiempo_ref = datetime.now()
    ok, datos = fijar_hora_gopro(gopro_ip, tiempo_ref)
    if ok:
        if not consultar_grabacion_gopro(gopro_ip):
            registrar_medios_previos(gopro_ip)
        estado.gopro_bateria = consultar_estado_gopro(gopro_ip)
        return {
            "exito": True,
            "fuente": fuente,
            "hora": f"{datos.get('date')} {datos.get('time')}",
            "desfase": medir_desfase_gopro(gopro_ip),
            "bateria": estado.gopro_bateria
        }
    return {"exito": False, "error": "Fallo al escribir la hora en la GoPro"}

@app.post("/api/flight/start")
def start_flight(data: dict):
    if not PUERTO_LOCK.acquire(timeout=20):
        return {"exito": False, "error": "El puerto de la radio esta en uso (plan de vuelo). Reintente."}
    try:
        return _start_flight(data)
    finally:
        PUERTO_LOCK.release()

def _start_flight(data: dict):
    global estado
    if estado.en_grabacion:
        return {"exito": False, "error": "Ya hay una grabacion en curso."}
    if estado.procesando:
        return {"exito": False, "error": "Espere a que termine el procesamiento del vuelo anterior."}

    nombre_mision = re.sub(r"[^\w.-]+", "_", data.get("mision", "Vuelo")).strip("._") or "Vuelo"
    puerto_sel = data.get("puerto", "AUTO")
    estado.intervalo_fotos_seg = float(data.get("intervalo", 1.0))

    if puerto_sel == "AUTO":
        puerto_pix = buscar_puerto_pixhawk()
        puerto_real = puerto_pix if puerto_pix else "udpin:127.0.0.1:14550"
    else:
        puerto_real = puerto_sel

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = os.path.join(rutas.F450, f"{nombre_mision}_{timestamp_str}")
    os.makedirs(carpeta, exist_ok=True)

    ruta_csv = os.path.join(carpeta, "telemetria.csv")
    ruta_tlog = os.path.join(carpeta, "telemetria.tlog")

    try:
        conn = abrir_conexion_mavlink(puerto_real)
    except Exception as e:
        return {"exito": False, "error": f"No se pudo conectar a {puerto_real}: {e}"}

    # Verificar que realmente llegue un HEARTBEAT del autopiloto (hasta 3 s)
    hb = None
    try:
        hb = conn.wait_heartbeat(timeout=3)
    except Exception:
        pass
    solicitar_streams(conn)
    advertencia_enlace = None if hb else (
        f"No se recibio senal del dron en {puerto_real}. La grabacion queda activa y "
        "empezara a registrar cuando llegue telemetria: verifique radio 915 MHz y bateria del dron.")

    resetear_telemetria_en_vivo()
    estado.puerto_real = puerto_real

    estado.conexion_mavlink = conn
    estado.carpeta_mision = carpeta
    estado.ruta_csv = ruta_csv
    estado.ruta_tlog = ruta_tlog
    estado.archivo_csv = open(ruta_csv, "w", encoding="utf-8")
    estado.archivo_csv.write("timestamp_utc,latitud,longitud,altitud_msl,altitud_relativa,alabeo_roll,cabeceo_pitch,rumbo_yaw,velocidad_ms,satelites,voltaje_bateria,modo_vuelo\n")
    estado.archivo_tlog = open(ruta_tlog, "wb")
    
    estado.total_registros = 0
    estado.tiempo_inicio_vuelo = time.time()
    estado.en_grabacion = True
    estado.estado_proceso = "GRABANDO EN VIVO"
    estado.mensaje_proceso = ""
    estado.progreso_porcentaje = 0

    # Iniciar y verificar grabacion GoPro
    gopro_iniciada = False
    gopro_msg = "GoPro no conectada por USB"
    hora_sincronizada = False
    ip_gp = buscar_ip_gopro()
    if ip_gp and consultar_grabacion_gopro(ip_gp):
        # Ya estaba grabando (Grabar Camara): no re-registrar medios, conservar la lista previa
        gopro_iniciada = True
        gopro_msg = f"La camara ya estaba grabando ({resumen_config(estado.gopro_config)})"
        estado.gopro_grabando = True
    elif ip_gp:
        # Misma base de tiempo que la telemetria: la hora de la camara se fija con la de la PC
        try:
            hora_sincronizada, _ = fijar_hora_gopro(ip_gp, datetime.now())
        except Exception:
            hora_sincronizada = False
        # Registrar medios existentes en la camara antes de comenzar el vuelo
        registrar_medios_previos(ip_gp)
        ok, msg = activar_shutter_gopro(ip_gp, iniciar=True)
        gopro_iniciada = ok
        gopro_msg = msg
        estado.gopro_grabando = ok
    elif estado.gopro_grabando:
        gopro_msg = "Camara sin cable: se inicio antes, pero no se puede comprobar que siga grabando"

    estado.hilo_telemetria = threading.Thread(target=bucle_telemetria, daemon=True)
    estado.hilo_telemetria.start()
    guardar_mision()
    guardar_config_camara(carpeta)

    return {
        "exito": True,
        "puerto": puerto_real,
        "carpeta": carpeta,
        "gopro_iniciada": gopro_iniciada,
        "gopro_mensaje": gopro_msg,
        "gopro_config": estado.gopro_config,
        "hora_sincronizada": hora_sincronizada,
        "advertencia": advertencia_enlace
    }

def guardar_config_camara(carpeta):
    """Deja constancia en la carpeta del vuelo de como quedo configurada la camara."""
    try:
        with open(os.path.join(carpeta, "camara.json"), "w", encoding="utf-8") as f:
            json.dump({"modelo": "GoPro HERO13 Black", "ajustes": estado.gopro_config}, f,
                      ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[AVISO] No se pudo guardar camara.json: {e}")

def revisar_calidad_video(ruta):
    """Lee los metadatos que graba la GoPro y avisa si el video no salio en calidad maxima."""
    try:
        res = subprocess.run(["exiftool", "-api", "largefilesupport=1", "-j", "-n",
                              "-GoPro:ColorMode", "-Composite:AvgBitrate", "-Track1:ImageHeight", ruta],
                             capture_output=True, text=True, timeout=60)
        m = json.loads(res.stdout)[0]
    except Exception:
        return []
    avisos = []
    if str(m.get("ColorMode", "")).upper() == "LOG":
        avisos.append("grabado en color LOG (imagen gris y lavada)")
    bitrate = m.get("AvgBitrate") or 0
    if bitrate and bitrate < 60e6:
        avisos.append(f"bitrate bajo ({bitrate / 1e6:.0f} Mbps)")
    if (m.get("ImageHeight") or 9999) < 2160:
        avisos.append(f"resolucion baja ({m.get('ImageHeight')} p)")
    return avisos

@app.post("/api/gopro/configurar")
def gopro_configurar():
    ip = estado.gopro_ip or buscar_ip_gopro()
    if not ip:
        return {"exito": False, "error": "GoPro no conectada por USB"}
    if consultar_grabacion_gopro(ip):
        return {"exito": False, "error": "La camara esta grabando: detengala para cambiar la configuracion"}
    ok, reporte = configurar_gopro_maxima_calidad(ip)
    return {"exito": ok, "reporte": reporte}

def tarea_procesamiento_post_vuelo():
    try:
        procesar_post_vuelo()
    finally:
        estado.procesando = False
        guardar_mision()

def procesar_post_vuelo():
    global estado
    try:
        # 1. Comprobar conexion con GoPro (reintentar unos segundos por si recién conectan el cable USB)
        estado.estado_proceso = "DESCARGANDO"
        estado.mensaje_proceso = "Comprobando conexion con GoPro..."
        estado.progreso_porcentaje = 5

        ip = buscar_ip_gopro()
        if not ip:
            for seg in range(15):
                estado.mensaje_proceso = f"Esperando conexion USB de la GoPro ({15 - seg} s)... Conecte el cable a la PC."
                time.sleep(1.0)
                ip = buscar_ip_gopro()
                if ip:
                    estado.gopro_ip = ip
                    break

        if ip:
            if consultar_grabacion_gopro(ip):
                ok, msg = activar_shutter_gopro(ip, iniciar=False)
                if not ok:
                    raise RuntimeError(f"No se pudo detener la camara: {msg}")
            estado.gopro_grabando = False
            time.sleep(1.5)  # Esperar que la GoPro finalice de escribir el archivo MP4

        if not ip:
            estado.estado_proceso = "ERROR"
            estado.mensaje_proceso = "GoPro no detectada por USB. Conecte el cable USB y vuelva a presionar Finalizar y Procesar."
            return

        estado.mensaje_proceso = "Buscando videos 4K y fotos nuevas en la GoPro..."
        estado.progreso_porcentaje = 10

        medios_actuales = obtener_lista_medios_gopro(ip)
        if medios_actuales is None:
            raise RuntimeError("No se pudo leer la lista de archivos de la GoPro. Reintente.")
        nuevos = []
        # 'cre' de la GoPro es la hora LOCAL de la camara expresada como epoch
        offset_local = datetime.now().astimezone().utcoffset().total_seconds()
        limite_cre = (estado.tiempo_inicio_vuelo or 0) + offset_local - 30 * 60
        for d, n, cre, size in medios_actuales:
            if (d, n) in estado.fotos_previas:
                continue
            if not estado.snapshot_medios_tomado and cre and cre < limite_cre:
                continue  # archivo viejo de la SD (no se registro la lista previa al vuelo)
            nuevos.append((d, n, size))

        carpeta_video = os.path.join(estado.carpeta_mision, "video")
        carpeta_fotos = os.path.join(estado.carpeta_mision, "fotos")
        os.makedirs(carpeta_video, exist_ok=True)
        os.makedirs(carpeta_fotos, exist_ok=True)

        total_descargas = len(nuevos)
        if total_descargas == 0:
            estado.mensaje_proceso = "No se detectaron medios nuevos en la tarjeta SD de la GoPro."
            estado.estado_proceso = "ERROR"
            estado.progreso_porcentaje = 100
            return

        videos_descargados = []
        fotos_directas_descargadas = []
        avisos_video = []

        for idx, (d, n, size) in enumerate(nuevos, 1):
            url_descarga = f"http://{ip}:8080/videos/DCIM/{d}/{n}"
            es_video = n.lower().endswith((".mp4", ".mov"))
            destino = os.path.join(carpeta_video if es_video else carpeta_fotos, n)

            tamanio_mb = size / (1024 * 1024) if size > 0 else 0
            estado.mensaje_proceso = f"Descargando archivo {idx} de {total_descargas} ({n} - {tamanio_mb:.1f} MB)..."
            estado.progreso_porcentaje = int(10 + (idx / total_descargas) * 30)

            ya_descargado = os.path.exists(destino) and size > 0 and os.path.getsize(destino) == size
            if not ya_descargado:
              with requests.get(url_descarga, stream=True, timeout=20) as r:
                r.raise_for_status()
                with open(destino + ".part", 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
              if size > 0 and os.path.getsize(destino + ".part") != size:
                raise RuntimeError(f"Descarga incompleta de {n}. Reintente.")
              os.replace(destino + ".part", destino)

            if es_video:
                videos_descargados.append(destino)
                avisos_video += [f"{n}: {a}" for a in revisar_calidad_video(destino)]
            else:
                fotos_directas_descargadas.append(destino)

        puntos = cargar_desde_csv(estado.ruta_csv)
        if not puntos:
            estado.mensaje_proceso = "Medios descargados, pero no se registraron puntos en telemetria.csv."
            if avisos_video:
                estado.mensaje_proceso += " ATENCION: " + "; ".join(avisos_video)
            estado.estado_proceso = "COMPLETADO"
            estado.progreso_porcentaje = 100
            return

        # 2. Extraccion de fotogramas del video 4K e inyeccion de metadatos DJI Mini 2 SE
        total_fotos_generadas = 0
        avisos_calidad = list(avisos_video)
        if videos_descargados:
            estado.estado_proceso = "PROCESANDO_VIDEO"
            videos_descargados.sort()
            inicios = calcular_inicios_videos(videos_descargados, puntos)
            for v_idx, ruta_vid in enumerate(videos_descargados, 1):
                nombre_vid = os.path.basename(ruta_vid)
                
                def progreso_extraccion(pct, msg):
                    estado.progreso_porcentaje = int(40 + (pct / 100.0) * 50)
                    estado.mensaje_proceso = f"[Video {v_idx}/{len(videos_descargados)}: {nombre_vid}] {msg}"

                fotos_ext = dividir_video_en_imagenes_dji(
                    ruta_video=ruta_vid,
                    puntos=puntos,
                    carpeta_salida=carpeta_fotos,
                    intervalo_segundos=estado.intervalo_fotos_seg,
                    callback_progreso=progreso_extraccion,
                    t_inicio=inicios.get(ruta_vid)
                )
                total_fotos_generadas += getattr(dividir_video_en_imagenes_dji, "ultimas_etiquetadas", len(fotos_ext))
                avisos_calidad += [f"{nombre_vid}: {a}" for a in getattr(dividir_video_en_imagenes_dji, "ultimos_avisos", [])]

        # 3. Si hubo fotos directas JPG, etiquetarlas tambien
        if fotos_directas_descargadas:
            estado.estado_proceso = "ETIQUETANDO"
            estado.mensaje_proceso = "Inyectando metadatos DJI en fotos directas..."
            metadatos_directas = []
            for ruta_f in fotos_directas_descargadas:
                t_foto = obtener_timestamp_imagen(ruta_f)
                telem = interpolar_telemetria(puntos, t_foto)
                if telem:
                    metadatos_directas.append((ruta_f, telem, hora_local_exif(t_foto)))
            etiquetadas = escribir_metadatos_dji_batch(metadatos_directas)
            total_fotos_generadas += etiquetadas

        for d, n, size in nuevos:
            estado.fotos_previas.add((d, n))

        estado.progreso_porcentaje = 100
        estado.estado_proceso = "COMPLETADO"
        estado.mensaje_proceso = (
            f"Exito: {len(videos_descargados)} video(s) y {total_fotos_generadas} fotografias "
            f"etiquetadas con metadatos DJI Mini 2 SE."
        )
        if avisos_calidad:
            estado.mensaje_proceso += " ATENCION: " + "; ".join(avisos_calidad)

    except Exception as e:
        estado.estado_proceso = "ERROR"
        estado.mensaje_proceso = f"Error durante el procesamiento: {e}"

@app.post("/api/flight/stop_and_process")
def stop_flight(background_tasks: BackgroundTasks):
    global estado
    if estado.procesando:
        return {"exito": False, "error": "Ya se esta procesando el vuelo."}
    if not estado.en_grabacion:
        if estado.carpeta_mision and estado.estado_proceso == "ERROR":
            estado.procesando = True
            background_tasks.add_task(tarea_procesamiento_post_vuelo)
            return {"exito": True, "mensaje": "Reintentando descarga USB y etiquetado DJI del ultimo vuelo..."}
        return {"exito": False, "error": "No hay ningun vuelo en grabacion actualmente."}

    estado.en_grabacion = False
    estado.procesando = True
    if estado.hilo_telemetria:
        estado.hilo_telemetria.join(timeout=3)
    
    if estado.archivo_csv:
        estado.archivo_csv.close()
        estado.archivo_csv = None
    if estado.archivo_tlog:
        estado.archivo_tlog.close()
        estado.archivo_tlog = None
    if estado.conexion_mavlink:
        try:
            estado.conexion_mavlink.close()
        except Exception:
            pass
        estado.conexion_mavlink = None

    background_tasks.add_task(tarea_procesamiento_post_vuelo)
    return {"exito": True, "mensaje": "Grabacion detenida. Iniciando descarga USB y etiquetado DJI..."}

@app.get("/api/open_folder")
def open_folder(ruta: str):
    raiz = os.path.realpath(rutas.VUELOS)
    if os.path.isdir(ruta) and os.path.realpath(ruta).startswith(raiz + os.sep):
        if sys.platform.startswith('win'):
            os.startfile(ruta)
        elif sys.platform.startswith('darwin'):
            subprocess.run(["open", ruta])
        else:
            subprocess.run(["xdg-open", ruta])
        return {"exito": True}
    return {"exito": False, "error": "Ruta no encontrada"}

plan_vuelo.conexion.update(abrir=abrir_conexion_mavlink, puerto=buscar_puerto_pixhawk, estado=estado)
drones.vigilar(estado, plan_vuelo.cargado)
plan_vuelo.vigilar_fin(control_rc.R)
control_rc.mantener()

def iniciar_servidor():
    print("=================================================================")
    print("   INICIANDO DASHBOARD WEB UAV UTEC-PRIA")
    print("   Abriendo navegador en: http://localhost:8000")
    print("=================================================================")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:8000")).start()
    rutas.migrar()
    recuperar_mision()
    # Solo esta PC; HORMIGAS_HOST=0.0.0.0 para permitir acceso desde la red
    uvicorn.run(app, host=os.environ.get("HORMIGAS_HOST", "127.0.0.1"), port=8000, log_level="warning")

if __name__ == "__main__":
    iniciar_servidor()
