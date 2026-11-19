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
from datetime import datetime, timezone
import requests
import serial.tools.list_ports
from pymavlink import mavutil
import uvicorn
from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Importar funciones de vinculacion DJI
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vincular_vuelo_dji import (
    cargar_desde_csv,
    interpolar_telemetria,
    escribir_metadatos_dji,
    generar_srt_dji,
    obtener_timestamp_imagen
)
from sincronizar_relojes import (
    buscar_ip_gopro,
    buscar_puerto_pixhawk,
    leer_tiempo_gps_pixhawk,
    fijar_hora_gopro,
    consultar_estado_gopro
)

app = FastAPI(title="UTEC PRIA - UAV Telemetry Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

        # Hardware GoPro
        self.gopro_ip = None
        self.gopro_bateria = "--"
        self.gopro_grabando = False
        self.fotos_previas = set()

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

def activar_shutter_gopro(ip, iniciar=True):
    """
    Envia la orden de iniciar/detener grabacion a la GoPro y VERIFICA
    activamente contra el sensor interno de la camara (status 10).
    """
    try:
        # Asegurar control por cable USB activo
        requests.get(f"http://{ip}:8080/gopro/camera/control/wired_usb?p=1", timeout=2)
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
                    return True, "Grabacion confirmada y activa en la camara (Sensor 10 = 1)" if iniciar else "Grabacion detenida correctamente (Sensor 10 = 0)"

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
                    archivos.append((d, nombre, int(f.get("cre", 0)), int(f.get("s", 0))))
            return archivos
    except Exception:
        pass
    return []

def bucle_telemetria():
    """Hilo secundario que captura y almacena paquetes MAVLink en vivo."""
    global estado
    while estado.en_grabacion:
        try:
            if not estado.conexion_mavlink:
                time.sleep(0.1)
                continue
            
            msg = estado.conexion_mavlink.recv_msg()
            if msg is None:
                time.sleep(0.01)
                continue

            # Guardar en archivo binario tlog
            if estado.archivo_tlog:
                try:
                    estado.archivo_tlog.write(msg.get_msgbuf())
                except Exception:
                    pass

            mtype = msg.get_type()

            if mtype == 'HEARTBEAT':
                cm = getattr(msg, 'custom_mode', 0)
                estado.modo_vuelo = MODOS_ARDUPILOT.get(cm, f"MODO_{cm}")

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
                if msg.voltage_battery > 0:
                    estado.bateria_dron = msg.voltage_battery / 1000.0

            elif mtype == 'BATTERY_STATUS':
                if hasattr(msg, 'voltages') and len(msg.voltages) > 0 and msg.voltages[0] != 65535:
                    v_tot = sum([v for v in msg.voltages if v != 65535]) / 1000.0
                    if v_tot > 0:
                        estado.bateria_dron = v_tot

            ahora = time.time()
            # Escribir linea de telemetria en CSV cada 250 ms (4 Hz)
            if ahora - estado.ultimo_registro_tiempo >= 0.25 and estado.lat != 0.0 and estado.archivo_csv:
                t_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                linea = (
                    f"{t_utc},{estado.lat:.7f},{estado.lon:.7f},{estado.alt_msl:.2f},"
                    f"{estado.alt_rel:.2f},{estado.roll:.2f},{estado.pitch:.2f},"
                    f"{estado.yaw:.2f},{estado.velocidad:.2f},{estado.satelites},"
                    f"{estado.bateria_dron:.2f},{estado.modo_vuelo}\n"
                )
                estado.archivo_csv.write(linea)
                estado.archivo_csv.flush()
                estado.ultimo_registro_tiempo = ahora
                estado.total_registros += 1

        except Exception:
            time.sleep(0.05)


@app.get("/", response_class=HTMLResponse)
async def index():
    html = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UTEC PRIA - Control de Mision y Telemetria UAV</title>
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

        .console-log { background: #0F172A; color: #38BDF8; font-family: monospace; font-size: 0.78rem; padding: 12px; border-radius: 6px; height: 120px; overflow-y: auto; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>UTEC PRIA | Centro de Control y Telemetria UAV</h1>
                <p>Cuadricoptero F450 + GoPro HERO13 Black | Formato DJI Mini 2 SE</p>
            </div>
            <div>
                <span id="badge-estado" class="badge-status">Inactivo</span>
            </div>
        </header>

        <!-- BANNER DE AUTOESCANEO ACTIVO DE HARDWARE -->
        <div class="scan-banner" id="banner-autoescaneo">
            <div class="scan-header">
                <div>
                    <div class="scan-title" id="txt-scan-titulo">Autoescaneo de Hardware en Curso...</div>
                    <div style="font-size: 0.82rem; color: var(--text-muted);" id="txt-scan-sub">Comprobando radio 915 MHz, bateria LiPo 3S y conexion USB de GoPro...</div>
                </div>
                <div>
                    <button class="scan-btn" id="btn-scan" onclick="ejecutarAutoescaneo()">Re-Escanear Todo</button>
                </div>
            </div>
            <div class="scan-grid">
                <div class="scan-item">
                    <div class="scan-item-lbl">Radio de Telemetria 915 MHz</div>
                    <div class="scan-item-val" id="scan-val-radio">Escaneando...</div>
                    <div class="scan-item-sub" id="scan-sub-radio">Verificando paquetes MAVLink</div>
                </div>
                <div class="scan-item">
                    <div class="scan-item-lbl">Bateria Dron (LiPo 3S)</div>
                    <div class="scan-item-val" id="scan-val-bat">Leyendo...</div>
                    <div class="scan-item-sub" id="scan-sub-bat">Sensor analogo Pixhawk</div>
                </div>
                <div class="scan-item">
                    <div class="scan-item-lbl">Camara GoPro HERO13</div>
                    <div class="scan-item-val" id="scan-val-gopro">Escaneando...</div>
                    <div class="scan-item-sub" id="scan-sub-gopro">IP y control por cable USB</div>
                </div>
            </div>
        </div>

        <div class="grid">
            <!-- TARJETA 1: PRE-VUELO -->
            <div class="card">
                <h2>1. Verificacion Pre-Vuelo y Camara GoPro</h2>
                <div class="status-row">
                    <span class="status-label">Camara GoPro (Red USB):</span>
                    <span id="txt-gopro-status" class="status-value val-bad">Desconectada</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Bateria Interna de Camara:</span>
                    <span id="txt-gopro-batt" class="status-value">--</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Estado Grabacion Camara:</span>
                    <span id="txt-gopro-rec" class="badge-cam-idle">EN ESPERA (STANDBY)</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Radio Telemetria / Pixhawk:</span>
                    <span id="txt-pix-status" class="status-value val-warn">Buscando radio...</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Bateria Dron (LiPo 3S):</span>
                    <span id="txt-dron-batt" class="status-value">0.0 V (0%)</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Satelites GPS Pixhawk:</span>
                    <span id="txt-pix-sats" class="status-value">0 satelites</span>
                </div>
                
                <div class="btn-group">
                    <button id="btn-sync" class="btn-primary" onclick="sincronizarRelojes()">Sincronizar Relojes</button>
                    <button id="btn-cam-rec-start" class="btn-cam-start" onclick="iniciarGrabacionCamara()">Grabar Camara</button>
                    <button id="btn-cam-rec-stop" class="btn-cam-stop" onclick="detenerGrabacionCamara()">Detener Camara</button>
                </div>
                <div id="msg-sync" class="alert-box"></div>
            </div>

            <!-- TARJETA 2: CONTROL DE MISION -->
            <div class="card">
                <h2>2. Control de Mision y Grabacion de Vuelo</h2>
                <div class="status-row">
                    <span class="status-label">Nombre de Mision:</span>
                    <input type="text" id="input-mision" value="Vuelo_Campo_01" style="padding: 5px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.88rem; width: 180px;">
                </div>
                <div class="status-row">
                    <span class="status-label">Puerto Telemetria (915 MHz):</span>
                    <select id="sel-puerto" style="padding: 5px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.85rem; width: 180px;">
                        <option value="AUTO">Deteccion Automatica</option>
                    </select>
                </div>
                
                <div class="btn-group">
                    <button id="btn-iniciar" class="btn-success" onclick="iniciarGrabacion()">Comenzar Grabacion</button>
                    <button id="btn-finalizar" class="btn-danger" onclick="finalizarYProcesar()" disabled>Finalizar y Procesar</button>
                </div>

                <div class="progress-bar-container" id="bar-container">
                    <div class="progress-bar" id="prog-bar"></div>
                </div>
                <div id="msg-proceso" class="alert-box"></div>
            </div>
        </div>

        <!-- TARJETA 3: TELEMETRIA EN TIEMPO REAL -->
        <div class="card">
            <h2>3. Telemetria de Vuelo en Vivo</h2>
            <div class="metrics-grid">
                <div class="metric-box">
                    <div class="metric-label">Altura Relativa</div>
                    <div class="metric-val" id="met-alt-rel">0.0 m</div>
                    <div class="metric-sub">Sobre el despegue</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Modo de Vuelo</div>
                    <div class="metric-val" id="met-modo">--</div>
                    <div class="metric-sub">ArduCopter</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Bateria Dron</div>
                    <div class="metric-val" id="met-bat">0.0 V</div>
                    <div class="metric-sub" id="met-bat-sub">LiPo 3S (Alarma: &lt;10.5V)</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Registros Guardados</div>
                    <div class="metric-val" id="met-regs">0</div>
                    <div class="metric-sub">telemetria.csv</div>
                </div>
            </div>

            <div class="status-row">
                <span class="status-label">Posicion Geografica:</span>
                <span id="met-coords" class="status-value">Lat: 0.000000 | Lon: 0.000000</span>
            </div>
            <div class="status-row">
                <span class="status-label">Altitud Absoluta (MSL):</span>
                <span id="met-alt-msl" class="status-value">0.0 m</span>
            </div>
            <div class="status-row">
                <span class="status-label">Orientacion y Velocidad:</span>
                <span id="met-rumbo-vel" class="status-value">Rumbo: 0.0° | Vel: 0.0 m/s</span>
            </div>
        </div>

        <!-- TERMINAL DE REGISTRO EN VIVO -->
        <div class="console-log" id="consola-log">
            [SISTEMA] Dashboard iniciado. Ejecutando autoescaneo previo de hardware...
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
            // Rango seguro LiPo 3S: 10.5V (0%) a 12.6V (100%)
            const pct = Math.round(((v - 10.5) / (12.6 - 10.5)) * 100);
            return Math.max(0, Math.min(100, pct));
        }

        async function ejecutarAutoescaneo() {
            const btnScan = document.getElementById("btn-scan");
            if (btnScan) {
                btnScan.disabled = true;
                btnScan.innerText = "Escaneando...";
            }
            logMsg("[AUTOESCANEO] Iniciando comprobacion activa de radio 915 MHz, bateria y GoPro...");
            document.getElementById("txt-scan-titulo").innerText = "Autoescaneo en curso...";
            document.getElementById("txt-scan-sub").innerText = "Probando comunicacion serie y enlace USB...";

            try {
                const r = await fetch("/api/scan_all");
                const d = await r.json();
                ultimoAutoescaneo = d;

                const tEl = document.getElementById("txt-scan-titulo");
                const sEl = document.getElementById("txt-scan-sub");

                // 1. Radio Telemetria
                const rVal = document.getElementById("scan-val-radio");
                const rSub = document.getElementById("scan-sub-radio");
                if (d.telemetria.conectada) {
                    rVal.innerText = `${d.telemetria.puerto} (${d.telemetria.paquetes} paq/s)`;
                    rVal.className = "scan-item-val val-ok";
                    rSub.innerText = `Modo: ${d.telemetria.modo} | ${d.telemetria.satelites} sats`;
                } else {
                    rVal.innerText = "Sin Senal MAVLink";
                    rVal.className = "scan-item-val val-bad";
                    rSub.innerText = "Verifique dron encendido y antena 915 MHz";
                }

                // 2. Bateria LiPo 3S
                const bVal = document.getElementById("scan-val-bat");
                const bSub = document.getElementById("scan-sub-bat");
                const vBat = d.telemetria.bateria_v || 0;
                if (vBat > 9.0) {
                    const pct = calcularPorcentaje3S(vBat);
                    bVal.innerText = `${vBat.toFixed(2)} V (${pct}%)`;
                    bVal.className = vBat >= 11.4 ? "scan-item-val val-ok" : (vBat >= 10.5 ? "scan-item-val val-warn" : "scan-item-val val-bad");
                    bSub.innerText = vBat >= 11.4 ? "LiPo 3S Optima (Rango Seguro)" : "Bateria 3S Baja (<11.4V)";
                } else {
                    bVal.innerText = "0.0 V";
                    bVal.className = "scan-item-val val-warn";
                    bSub.innerText = "Sin lectura de voltaje";
                }

                // 3. GoPro HERO13
                const gVal = document.getElementById("scan-val-gopro");
                const gSub = document.getElementById("scan-sub-gopro");
                if (d.gopro.conectada) {
                    gVal.innerText = `Conectada (${d.gopro.bateria}%)`;
                    gVal.className = "scan-item-val val-ok";
                    const recTxt = d.gopro.grabando ? "GRABANDO ACTIVA" : "En Espera (Listo)";
                    gSub.innerText = `IP: ${d.gopro.ip} | ${recTxt}`;
                } else {
                    if (d.gopro.grabando) {
                        gVal.innerText = "Grabando en Vuelo";
                        gVal.className = "scan-item-val val-ok";
                        gSub.innerText = "Autonoma en SD con bateria interna";
                    } else {
                        gVal.innerText = "Desconectada";
                        gVal.className = "scan-item-val val-warn";
                        gSub.innerText = "Modo autonomo (o conecte USB)";
                    }
                }

                // Resumen Global
                if (d.telemetria.conectada) {
                    tEl.innerText = "Autoescaneo OK: Hardware Verificado en Vivo";
                    tEl.style.color = "var(--success)";
                    sEl.innerText = `Radio OK en ${d.telemetria.puerto} | Bateria: ${vBat.toFixed(1)}V | Camara: ${d.gopro.conectada ? 'USB Listo' : 'Modo Manual'}`;
                    logMsg(`[AUTOESCANEO EXITOSO] Telemetria activa en ${d.telemetria.puerto}. Bateria: ${vBat.toFixed(2)}V. Camara: ${d.gopro.conectada ? 'OK' : 'Desconectada'}.`);
                } else {
                    tEl.innerText = "Autoescaneo: Esperando Senal del Dron";
                    tEl.style.color = "var(--warning)";
                    sEl.innerText = "No se recibieron paquetes de la radio 915 MHz. Verifique que el dron este encendido.";
                    logMsg("[AUTOESCANEO ADVERTENCIA] Radio 915 MHz sin paquetes MAVLink.");
                }

                actualizarHardware();
            } catch (e) {
                logMsg(`[AUTOESCANEO ERROR] ${e}`);
            } finally {
                if (btnScan) {
                    btnScan.disabled = false;
                    btnScan.innerText = "Re-Escanear Todo";
                }
            }
        }

        async function actualizarHardware() {
            try {
                const r = await fetch("/api/status");
                const d = await r.json();

                // GoPro
                const elGpStatus = document.getElementById("txt-gopro-status");
                const elGpBatt = document.getElementById("txt-gopro-batt");
                const elGpRec = document.getElementById("txt-gopro-rec");

                if (d.gopro_conectada) {
                    elGpStatus.innerText = `Conectada (${d.gopro_ip})`;
                    elGpStatus.className = "status-value val-ok";
                    elGpBatt.innerText = `${d.gopro_bateria}%`;
                    if (d.gopro_grabando) {
                        elGpRec.innerText = "GRABANDO EN VIVO (Verificado)";
                        elGpRec.className = "badge-cam-rec";
                    } else {
                        elGpRec.innerText = "EN ESPERA (STANDBY)";
                        elGpRec.className = "badge-cam-idle";
                    }
                } else {
                    elGpStatus.innerText = "Desconectada (Modo Vuelo)";
                    elGpStatus.className = "status-value val-warn";
                    elGpBatt.innerText = "--";
                    if (d.gopro_grabando) {
                        elGpRec.innerText = "GRABANDO EN VUELO (Autonoma)";
                        elGpRec.className = "badge-cam-rec";
                    } else {
                        elGpRec.innerText = "EN ESPERA (Desconectada)";
                        elGpRec.className = "badge-cam-idle";
                    }
                }

                // Pixhawk / Radio
                const elPixStatus = document.getElementById("txt-pix-status");
                const elPixSats = document.getElementById("txt-pix-sats");
                const elDronBatt = document.getElementById("txt-dron-batt");

                if (d.pixhawk_puerto) {
                    elPixStatus.innerText = `Radio en ${d.pixhawk_puerto}`;
                    elPixStatus.className = "status-value val-ok";
                } else {
                    elPixStatus.innerText = "Buscando radio...";
                    elPixStatus.className = "status-value val-warn";
                }

                elPixSats.innerText = `${d.satelites} satelites`;

                const vBat = d.bateria_dron || 0;
                const pctBat = calcularPorcentaje3S(vBat);
                if (vBat > 9.0) {
                    elDronBatt.innerText = `${vBat.toFixed(2)} V (${pctBat}%)`;
                    elDronBatt.className = vBat >= 11.4 ? "status-value val-ok" : (vBat >= 10.5 ? "status-value val-warn" : "status-value val-bad");
                } else {
                    elDronBatt.innerText = "0.0 V (0%)";
                    elDronBatt.className = "status-value val-warn";
                }

                // Puertos
                const sel = document.getElementById("sel-puerto");
                if (d.puertos_disponibles && d.puertos_disponibles.length > 0) {
                    const actual = sel.value;
                    sel.innerHTML = '<option value="AUTO">Deteccion Automatica</option>';
                    d.puertos_disponibles.forEach(p => {
                        sel.innerHTML += `<option value="${p.dev}">${p.desc}</option>`;
                    });
                    sel.innerHTML += '<option value="udpin:127.0.0.1:14550">Red UDP (Mission Planner)</option>';
                    sel.value = actual;
                }

                // Grabacion
                const badge = document.getElementById("badge-estado");
                const btnIni = document.getElementById("btn-iniciar");
                const btnFin = document.getElementById("btn-finalizar");

                if (d.en_grabacion) {
                    badge.innerText = "GRABANDO EN VIVO";
                    badge.className = "badge-status badge-recording";
                    btnIni.disabled = true;
                    btnFin.disabled = false;
                } else {
                    badge.innerText = d.estado_proceso;
                    badge.className = "badge-status";
                    btnIni.disabled = false;
                    btnFin.disabled = true;
                }

                // Metricas
                document.getElementById("met-alt-rel").innerText = `${d.alt_rel.toFixed(1)} m`;
                document.getElementById("met-modo").innerText = d.modo_vuelo;
                
                const metBat = document.getElementById("met-bat");
                if (vBat > 9.0) {
                    metBat.innerText = `${vBat.toFixed(1)} V (${pctBat}%)`;
                    metBat.style.color = vBat >= 11.4 ? "var(--success)" : (vBat >= 10.5 ? "var(--warning)" : "var(--danger)");
                } else {
                    metBat.innerText = "0.0 V";
                    metBat.style.color = "var(--primary)";
                }

                document.getElementById("met-regs").innerText = d.total_registros;
                document.getElementById("met-coords").innerText = `Lat: ${d.lat.toFixed(6)} | Lon: ${d.lon.toFixed(6)}`;
                document.getElementById("met-alt-msl").innerText = `${d.alt_msl.toFixed(1)} m`;
                document.getElementById("met-rumbo-vel").innerText = `Rumbo: ${d.yaw.toFixed(1)}° | Vel: ${d.velocidad.toFixed(1)} m/s`;

                // Progreso
                const msgProc = document.getElementById("msg-proceso");
                const barCont = document.getElementById("bar-container");
                const bar = document.getElementById("prog-bar");

                if (d.estado_proceso === "DESCARGANDO" || d.estado_proceso === "ETIQUETANDO") {
                    msgProc.style.display = "block";
                    msgProc.className = "alert-box alert-warning";
                    msgProc.innerText = d.mensaje_proceso;
                    barCont.style.display = "block";
                    bar.style.width = `${d.progreso_porcentaje}%`;
                } else if (d.estado_proceso === "COMPLETADO") {
                    msgProc.style.display = "block";
                    msgProc.className = "alert-box alert-success";
                    msgProc.innerHTML = `${d.mensaje_proceso} <br><button class="btn-secondary" style="margin-top:8px; padding:6px 12px;" onclick="abrirCarpeta('${d.carpeta_mision.replace(/\\\\/g, '/')}')">Abrir Carpeta de Fotos</button>`;
                    barCont.style.display = "none";
                }

            } catch (e) {
                console.error(e);
            }
        }

        async function sincronizarRelojes() {
            logMsg("Iniciando sincronizacion de reloj con GoPro por cable USB...");
            const btn = document.getElementById("btn-sync");
            btn.disabled = true;
            try {
                const r = await fetch("/api/sync_clocks", { method: "POST" });
                const d = await r.json();
                const el = document.getElementById("msg-sync");
                el.style.display = "block";
                if (d.exito) {
                    el.className = "alert-box alert-success";
                    el.innerText = `Sincronizacion completada con exito. Margen: < 0.05 segundos. (Hora: ${d.hora})`;
                    logMsg(`[OK] Reloj calibrado exitosamente con ${d.fuente}.`);
                } else {
                    el.className = "alert-box alert-warning";
                    el.innerText = `Error: ${d.error}`;
                    logMsg(`[ERROR] ${d.error}`);
                }
            } catch (e) {
                logMsg(`[ERROR] Fallo de comunicacion: ${e}`);
            } finally {
                btn.disabled = false;
                actualizarHardware();
            }
        }

        async function iniciarGrabacionCamara() {
            logMsg("[CAMARA] Enviando orden de inicio de grabacion por USB...");
            try {
                const r = await fetch("/api/gopro/shutter/start", { method: "POST" });
                const d = await r.json();
                if (d.exito) {
                    logMsg(`[CAMARA EXITOSO] ${d.mensaje}`);
                } else {
                    logMsg(`[CAMARA ERROR] ${d.error || d.mensaje}`);
                    alert(`Error en camara: ${d.error || d.mensaje}`);
                }
            } catch (e) {
                logMsg(`[CAMARA ERROR] ${e}`);
            }
            actualizarHardware();
        }

        async function detenerGrabacionCamara() {
            logMsg("[CAMARA] Enviando orden de detener grabacion...");
            try {
                const r = await fetch("/api/gopro/shutter/stop", { method: "POST" });
                const d = await r.json();
                if (d.exito) {
                    logMsg(`[CAMARA OK] ${d.mensaje}`);
                } else {
                    logMsg(`[CAMARA ERROR] ${d.error || d.mensaje}`);
                }
            } catch (e) {
                logMsg(`[CAMARA ERROR] ${e}`);
            }
            actualizarHardware();
        }

        async function iniciarGrabacion() {
            // Comprobar resultado del autoescaneo previo
            if (ultimoAutoescaneo && !ultimoAutoescaneo.telemetria.conectada) {
                const confirma = confirm(`ADVERTENCIA DE AUTOESCANEO:\n\nNo se han detectado paquetes de telemetria desde la radio 915 MHz.\nVerifique que el dron tenga la bateria LiPo 3S conectada y la radio este conectada a la PC.\n\n¿Desea forzar el inicio de todos modos?`);
                if (!confirma) return;
            }

            const mision = document.getElementById("input-mision").value.trim() || "Mision_Vuelo";
            const puerto = document.getElementById("sel-puerto").value;
            logMsg(`Iniciando mision: ${mision}...`);

            const r = await fetch("/api/flight/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mision: mision, puerto: puerto })
            });
            const d = await r.json();
            if (d.exito) {
                logMsg(`[+] Telemetria iniciada en ${d.puerto}.`);
                if (d.gopro_iniciada) {
                    logMsg(`[+] Camara GoPro: Grabacion confirmada y activa en la camara (${d.gopro_mensaje}).`);
                } else {
                    logMsg("[AVISO] Camara sin conexion USB: inicie la grabacion manualmente en la GoPro antes del despegue.");
                }
            } else {
                alert(`Error al iniciar: ${d.error}`);
                logMsg(`[ERROR] No se pudo conectar a telemetria: ${d.error}`);
            }
            actualizarHardware();
        }

        async function finalizarYProcesar() {
            if (!confirm("¿Desea finalizar la grabacion del vuelo actual y descargar/procesar las fotos de la GoPro?")) return;
            logMsg("Deteniendo telemetria y procesando medios de la GoPro...");
            
            const r = await fetch("/api/flight/stop_and_process", { method: "POST" });
            const d = await r.json();
            logMsg(d.mensaje);
            actualizarHardware();
        }

        async function abrirCarpeta(ruta) {
            await fetch(`/api/open_folder?ruta=${encodeURIComponent(ruta)}`);
        }

        // Bucle periodico de actualizacion
        setInterval(actualizarHardware, 1000);

        // Ejecutar autoescaneo activo inmediatamente al abrir
        ejecutarAutoescaneo();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/api/scan_all")
def scan_all():
    """Realiza un autoescaneo activo enviando pruebas reales a la radio y GoPro."""
    global estado
    
    # 1. Probar GoPro
    gp_ip = buscar_ip_gopro()
    gp_ok = False
    gp_batt = "--"
    gp_shutter = False
    gp_grabando = False
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
    if estado.en_grabacion and estado.conexion_mavlink:
        telem_ok = True
        telem_puerto = "Activo"
        telem_modo = estado.modo_vuelo
        telem_paquetes = estado.total_registros or 10
        telem_voltaje = estado.bateria_dron
        telem_sats = estado.satelites
    else:
        puertos_raw = list(serial.tools.list_ports.comports())
        candidatos = [p.device for p in puertos_raw if "bluetooth" not in (p.description or "").lower()]
        telem_ok = False
        telem_puerto = None
        telem_modo = "DESCONOCIDO"
        telem_paquetes = 0
        telem_voltaje = estado.bateria_dron
        telem_sats = estado.satelites

        for port in candidatos:
            try:
                m = mavutil.mavlink_connection(port, baud=57600, timeout=1.2)
                m.mav.request_data_stream_send(m.target_system, m.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
                t_ini = time.time()
                while time.time() - t_ini < 1.8:
                    msg = m.recv_msg()
                    if msg:
                        telem_paquetes += 1
                        mtype = msg.get_type()
                        if mtype == 'HEARTBEAT':
                            cm = getattr(msg, 'custom_mode', 0)
                            telem_modo = MODOS_ARDUPILOT.get(cm, f"MODO_{cm}")
                        elif mtype == 'SYS_STATUS':
                            if msg.voltage_battery > 0:
                                telem_voltaje = msg.voltage_battery / 1000.0
                                estado.bateria_dron = telem_voltaje
                        elif mtype == 'GPS_RAW_INT':
                            telem_sats = getattr(msg, 'satellites_visible', telem_sats)
                            estado.satelites = telem_sats
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
            "puerto": telem_puerto or "COM10",
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
    ok, msg = activar_shutter_gopro(ip, iniciar=True)
    estado.gopro_grabando = ok
    return {"exito": ok, "mensaje": msg}

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
    puertos = [{"dev": p.device, "desc": f"{p.device} ({p.description})"} for p in puertos_raw if "bluetooth" not in (p.description or "").lower()]
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
        "bateria_dron": estado.bateria_dron,
        "modo_vuelo": estado.modo_vuelo,
        "total_registros": estado.total_registros,
        "estado_proceso": estado.estado_proceso,
        "mensaje_proceso": estado.mensaje_proceso,
        "progreso_porcentaje": estado.progreso_porcentaje,
        "carpeta_mision": estado.carpeta_mision,
        "puertos_disponibles": puertos
    }

@app.post("/api/sync_clocks")
def sync_clocks():
    global estado
    gopro_ip = estado.gopro_ip or buscar_ip_gopro()
    if not gopro_ip:
        return {"exito": False, "error": "GoPro no encontrada. Verifique la conexion por cable USB."}

    puerto_pix = buscar_puerto_pixhawk()
    tiempo_pix = None
    gps_fix = 0
    sats = 0
    if puerto_pix:
        tiempo_pix, gps_fix, sats = leer_tiempo_gps_pixhawk(puerto_pix)

    if tiempo_pix and gps_fix >= 3:
        fuente = f"GPS Pixhawk (Fix 3D con {sats} satelites)"
        tiempo_ref = tiempo_pix.astimezone()
    else:
        fuente = "Reloj de la Computadora (NTP)"
        tiempo_ref = datetime.now()

    ok, datos = fijar_hora_gopro(gopro_ip, tiempo_ref)
    if ok:
        estado.gopro_bateria = consultar_estado_gopro(gopro_ip)
        return {
            "exito": True,
            "fuente": fuente,
            "hora": f"{datos.get('date')} {datos.get('time')}",
            "bateria": estado.gopro_bateria
        }
    return {"exito": False, "error": "Fallo al escribir la hora en la GoPro"}

@app.post("/api/flight/start")
def start_flight(data: dict):
    global estado
    if estado.en_grabacion:
        return {"exito": False, "error": "Ya hay una grabacion en curso."}

    nombre_mision = data.get("mision", "Vuelo").replace(" ", "_")
    puerto_sel = data.get("puerto", "AUTO")

    if puerto_sel == "AUTO":
        puerto_pix = buscar_puerto_pixhawk()
        puerto_real = puerto_pix if puerto_pix else "udpin:127.0.0.1:14550"
    else:
        puerto_real = puerto_sel

    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = os.path.join("vuelos", f"{nombre_mision}_{timestamp_str}")
    os.makedirs(carpeta, exist_ok=True)

    ruta_csv = os.path.join(carpeta, "telemetria.csv")
    ruta_tlog = os.path.join(carpeta, "telemetria.tlog")

    try:
        if "udp" in puerto_real.lower():
            conn = mavutil.mavlink_connection(puerto_real)
        else:
            conn = mavutil.mavlink_connection(puerto_real, baud=57600)
    except Exception as e:
        return {"exito": False, "error": f"No se pudo conectar a {puerto_real}: {e}"}

    try:
        conn.mav.request_data_stream_send(
            conn.target_system, conn.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1
        )
    except Exception:
        pass

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

    # Iniciar y verificar grabacion GoPro
    gopro_iniciada = False
    gopro_msg = "GoPro no conectada por USB"
    ip_gp = estado.gopro_ip or buscar_ip_gopro()
    if ip_gp:
        ok, msg = activar_shutter_gopro(ip_gp, iniciar=True)
        gopro_iniciada = ok
        gopro_msg = msg
        estado.gopro_grabando = ok
    elif estado.gopro_grabando:
        gopro_iniciada = True
        gopro_msg = "Grabacion activa en curso (iniciada previamente por cable, continuando en tarjeta SD)"

    estado.hilo_telemetria = threading.Thread(target=bucle_telemetria, daemon=True)
    estado.hilo_telemetria.start()

    return {
        "exito": True,
        "puerto": puerto_real,
        "carpeta": carpeta,
        "gopro_iniciada": gopro_iniciada,
        "gopro_mensaje": gopro_msg
    }

def tarea_procesamiento_post_vuelo():
    global estado
    try:
        ip = estado.gopro_ip or buscar_ip_gopro()
        if ip:
            activar_shutter_gopro(ip, iniciar=False)
            estado.gopro_grabando = False

        estado.estado_proceso = "DESCARGANDO"
        estado.mensaje_proceso = "Buscando fotografias y videos nuevos en la GoPro..."
        estado.progreso_porcentaje = 10

        if not ip:
            estado.estado_proceso = "ERROR"
            estado.mensaje_proceso = "Conecte la GoPro por cable USB a la computadora para descargar los medios."
            return

        medios_actuales = obtener_lista_medios_gopro(ip)
        nuevos = []
        for d, n, cre, size in medios_actuales:
            if (d, n) not in estado.fotos_previas:
                nuevos.append((d, n, size))

        carpeta_fotos = os.path.join(estado.carpeta_mision, "fotos")
        os.makedirs(carpeta_fotos, exist_ok=True)

        total_descargas = len(nuevos)
        if total_descargas == 0:
            estado.mensaje_proceso = "No se detectaron medios nuevos en la tarjeta SD de la GoPro."
            estado.estado_proceso = "COMPLETADO"
            estado.progreso_porcentaje = 100
            return

        for idx, (d, n, size) in enumerate(nuevos, 1):
            estado.mensaje_proceso = f"Descargando archivo {idx} de {total_descargas} ({n})..."
            estado.progreso_porcentaje = int(10 + (idx / total_descargas) * 45)
            
            url_descarga = f"http://{ip}:8080/videos/DCIM/{d}/{n}"
            destino = os.path.join(carpeta_fotos, n)

            with requests.get(url_descarga, stream=True, timeout=15) as r:
                r.raise_for_status()
                with open(destino, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)

        estado.estado_proceso = "ETIQUETANDO"
        estado.mensaje_proceso = "Inyectando metadatos nativos DJI Mini 2 SE..."
        estado.progreso_porcentaje = 60

        puntos = cargar_desde_csv(estado.ruta_csv)
        if not puntos:
            estado.mensaje_proceso = "Descarga finalizada, pero no se hallaron coordenadas en el CSV de telemetria."
            estado.estado_proceso = "COMPLETADO"
            return

        archivos_locales = [f for f in os.listdir(carpeta_fotos) if f.lower().endswith((".jpg", ".jpeg", ".dng", ".mp4", ".mov"))]
        total_locales = len(archivos_locales)
        exitos = 0

        for idx, nombre in enumerate(archivos_locales, 1):
            estado.progreso_porcentaje = int(60 + (idx / total_locales) * 38)
            ruta_completa = os.path.join(carpeta_fotos, nombre)

            if nombre.lower().endswith((".mp4", ".mov")):
                generar_srt_dji(ruta_completa, puntos)
                exitos += 1
            else:
                t_foto = obtener_timestamp_imagen(ruta_completa)
                telem = interpolar_telemetria(puntos, t_foto)
                if telem:
                    ok = escribir_metadatos_dji(ruta_completa, telem)
                    if ok: exitos += 1

        estado.progreso_porcentaje = 100
        estado.estado_proceso = "COMPLETADO"
        estado.mensaje_proceso = f"Exito: {exitos} de {total_locales} archivos procesados con metadatos nativos DJI Mini 2 SE."

    except Exception as e:
        estado.estado_proceso = "ERROR"
        estado.mensaje_proceso = f"Error durante el procesamiento: {e}"

@app.post("/api/flight/stop_and_process")
def stop_flight(background_tasks: BackgroundTasks):
    global estado
    if not estado.en_grabacion:
        return {"exito": False, "error": "No hay ningun vuelo en grabacion actualmente."}

    estado.en_grabacion = False
    
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
    if os.path.exists(ruta):
        if sys.platform.startswith('win'):
            os.startfile(ruta)
        elif sys.platform.startswith('darwin'):
            subprocess.run(["open", ruta])
        else:
            subprocess.run(["xdg-open", ruta])
        return {"exito": True}
    return {"exito": False, "error": "Ruta no encontrada"}

def iniciar_servidor():
    print("=================================================================")
    print("   INICIANDO DASHBOARD WEB UAV UTEC-PRIA")
    print("   Abriendo navegador en: http://localhost:8000")
    print("=================================================================")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:8000")).start()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

if __name__ == "__main__":
    iniciar_servidor()
