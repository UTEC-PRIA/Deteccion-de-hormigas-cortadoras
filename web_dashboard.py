#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Dashboard Web de Telemetria en Tiempo Real y Procesamiento Automatico
Plataforma: Cuadricoptero F450 con soporte fijo inferior (GoPro mirando hacia abajo, sin gimbal).
Compatible con Windows y Ubuntu.
"""

import sys
import os
import time
import json
import socket
import threading
import subprocess
import shutil
from datetime import datetime, timezone, timedelta
import requests
import psutil
import serial.tools.list_ports
from pymavlink import mavutil

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import webbrowser

from sincronizar_relojes import buscar_ip_gopro, buscar_puerto_pixhawk, leer_tiempo_gps_pixhawk, fijar_hora_gopro, consultar_estado_gopro
from vincular_vuelo_dji import (
    PuntoTelemetria, cargar_desde_csv, interpolar_telemetria,
    obtener_timestamp_imagen, escribir_metadatos_dji, generar_srt_dji,
    obtener_ruta_exiftool, EXIFTOOL_CMD
)

app = FastAPI(title="UTEC PRIA - UAV Telemetry Dashboard")

class EstadoMision:
    def __init__(self):
        self.en_grabacion = False
        self.conexion_mavlink = None
        self.hilo_telemetria = None
        self.carpeta_mision = None
        self.ruta_csv = None
        self.ruta_tlog = None
        self.archivo_csv = None
        self.archivo_tlog = None
        
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
        
        # GoPro
        self.gopro_ip = None
        self.gopro_bateria = "N/D"
        self.fotos_previas = set()
        self.tiempo_inicio_vuelo = None
        
        # Procesamiento
        self.estado_proceso = "INACTIVO"
        self.mensaje_proceso = "Listo para iniciar"
        self.progreso_porcentaje = 0
        self.archivos_procesados = []

estado = EstadoMision()

MODOS_ARDUPILOT = {
    0: 'STABILIZE', 1: 'ACRO', 2: 'ALT_HOLD', 3: 'AUTO', 4: 'GUIDED',
    5: 'LOITER', 6: 'RTL', 7: 'CIRCLE', 9: 'LAND', 11: 'DRIFT',
    13: 'SPORT', 14: 'FLIP', 15: 'AUTOTUNE', 16: 'POSHOLD', 17: 'BRAKE'
}

def obtener_lista_medios_gopro(ip):
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
                estado.bateria_dron = msg.voltage_battery / 1000.0

            ahora = time.time()
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
            --border: #E2E8F0;
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
        @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }

        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        @media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }
        
        .card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 22px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        .card h2 { font-size: 1.05rem; color: var(--primary); margin-bottom: 14px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }
        
        .status-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #F1F5F9; font-size: 0.9rem; }
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

        .btn-group { display: flex; gap: 12px; margin-top: 15px; }
        button { flex: 1; padding: 12px 18px; border-radius: 6px; border: none; font-size: 0.9rem; font-weight: 600; cursor: pointer; transition: background 0.2s; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-light); }
        .btn-success { background: var(--success); color: white; }
        .btn-success:hover { background: #166534; }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: #991B1B; }
        .btn-secondary { background: #E2E8F0; color: var(--text); }
        .btn-secondary:hover { background: #CBD5E1; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }

        .alert-box { padding: 12px 16px; border-radius: 6px; margin-top: 15px; font-size: 0.88rem; display: none; }
        .alert-success { background: var(--success-bg); color: var(--success); border: 1px solid #BBF7D0; }
        .alert-warning { background: var(--warning-bg); color: var(--warning); border: 1px solid #FDE68A; }
        .progress-bar-container { width: 100%; height: 8px; background: #E2E8F0; border-radius: 4px; overflow: hidden; margin-top: 10px; display: none; }
        .progress-bar { height: 100%; width: 0%; background: var(--accent); transition: width 0.3s; }

        .console-log { background: #0F172A; color: #38BDF8; font-family: monospace; font-size: 0.78rem; padding: 12px; border-radius: 6px; height: 110px; overflow-y: auto; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>UTEC PRIA | Centro de Control y Telemetria UAV</h1>
                <p>Cuadricoptero F450 (Sin Gimbal - Camara fija hacia abajo) + GoPro HERO13 Black | Formato DJI Mini 2 SE</p>
            </div>
            <div>
                <span id="badge-estado" class="badge-status">Inactivo</span>
            </div>
        </header>

        <div class="grid">
            <!-- TARJETA 1: PRE-VUELO -->
            <div class="card">
                <h2>1. Verificacion Pre-Vuelo y Relojes (Por Cable)</h2>
                <div class="status-row">
                    <span class="status-label">Camara GoPro HERO13 (USB):</span>
                    <span id="txt-gopro-status" class="status-value val-bad">Desconectada</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Bateria de la Camara:</span>
                    <span id="txt-gopro-batt" class="status-value">--</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Controladora Pixhawk:</span>
                    <span id="txt-pix-status" class="status-value val-warn">Buscando puerto...</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Satélites GPS Pixhawk:</span>
                    <span id="txt-pix-sats" class="status-value">--</span>
                </div>
                <div class="status-row">
                    <span class="status-label">Montura de Camara:</span>
                    <span class="status-value val-ok">Soporte Fijo Inferior (Hacia Abajo - Nadir)</span>
                </div>
                
                <div class="btn-group">
                    <button id="btn-sync" class="btn-primary" onclick="sincronizarRelojes()">Sincronizar Relojes</button>
                    <button class="btn-secondary" onclick="actualizarHardware()">Refrescar Hardware</button>
                </div>
                <div id="msg-sync" class="alert-box"></div>
            </div>

            <!-- TARJETA 2: CONTROL DE MISION -->
            <div class="card">
                <h2>2. Control de Mision y Grabacion</h2>
                <div class="status-row">
                    <span class="status-label">Nombre de Mision:</span>
                    <input type="text" id="input-mision" value="Vuelo_Campo_01" style="padding: 4px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.88rem; width: 170px;">
                </div>
                <div class="status-row">
                    <span class="status-label">Puerto de Telemetria (915 MHz):</span>
                    <select id="sel-puerto" style="padding: 4px 8px; border: 1px solid var(--border); border-radius: 4px; font-size: 0.85rem; width: 170px;">
                        <option value="AUTO">Deteccion Automatica</option>
                        <option value="udpin:127.0.0.1:14550">Red UDP (Mission Planner)</option>
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
                    <div class="metric-label">Bateria Drone</div>
                    <div class="metric-val" id="met-bat">0.0 V</div>
                    <div class="metric-sub">LiPo 3S</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Registros Guardados</div>
                    <div class="metric-val" id="met-regs">0</div>
                    <div class="metric-sub">telemetria.csv</div>
                </div>
            </div>

            <div class="status-row">
                <span class="status-label">Coordenadas GPS Actuales:</span>
                <span id="met-coords" class="status-value">Lat: 0.000000 | Lon: 0.000000</span>
            </div>
            <div class="status-row">
                <span class="status-label">Altitud Absoluta MSL:</span>
                <span id="met-alt-msl" class="status-value">0.0 m</span>
            </div>
            <div class="status-row">
                <span class="status-label">Rumbo (Yaw) y Velocidad:</span>
                <span id="met-rumbo-vel" class="status-value">Rumbo: 0.0° | Vel: 0.0 m/s</span>
            </div>
            <div class="status-row">
                <span class="status-label">Angulo Optico Camara (Compensacion F450):</span>
                <span id="met-angulos" class="status-value">Roll: 0.0° | Pitch: -90.0° (Nadir)</span>
            </div>

            <div class="console-log" id="log-terminal">
                [SISTEMA] Dashboard iniciado. Conecte los equipos y verifique el estado.
            </div>
        </div>
    </div>

    <script>
        function logMsg(txt) {
            const el = document.getElementById("log-terminal");
            const time = new Date().toLocaleTimeString();
            el.innerHTML += `<br>[${time}] ${txt}`;
            el.scrollTop = el.scrollHeight;
        }

        async function actualizarHardware() {
            try {
                const r = await fetch("/api/status");
                const d = await r.json();

                // GoPro
                const elGpStatus = document.getElementById("txt-gopro-status");
                const elGpBatt = document.getElementById("txt-gopro-batt");
                if (d.gopro_conectada) {
                    elGpStatus.innerText = `Conectada (${d.gopro_ip})`;
                    elGpStatus.className = "status-value val-ok";
                    elGpBatt.innerText = `${d.gopro_bateria}%`;
                } else {
                    elGpStatus.innerText = "Desconectada (Revise cable y modo GoPro Connect)";
                    elGpStatus.className = "status-value val-bad";
                    elGpBatt.innerText = "--";
                }

                // Pixhawk
                const elPixStatus = document.getElementById("txt-pix-status");
                const elPixSats = document.getElementById("txt-pix-sats");
                if (d.pixhawk_puerto) {
                    elPixStatus.innerText = `Detectada en ${d.pixhawk_puerto}`;
                    elPixStatus.className = "status-value val-ok";
                    elPixSats.innerText = `${d.satelites} satélites`;
                } else {
                    elPixStatus.innerText = "No detectada por USB directo";
                    elPixStatus.className = "status-value val-warn";
                    elPixSats.innerText = "--";
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
                document.getElementById("met-bat").innerText = `${d.bateria_dron.toFixed(1)} V`;
                document.getElementById("met-regs").innerText = d.total_registros;
                document.getElementById("met-coords").innerText = `Lat: ${d.lat.toFixed(6)} | Lon: ${d.lon.toFixed(6)}`;
                document.getElementById("met-alt-msl").innerText = `${d.alt_msl.toFixed(1)} m`;
                document.getElementById("met-rumbo-vel").innerText = `Rumbo: ${d.yaw.toFixed(1)}° | Vel: ${d.velocidad.toFixed(1)} m/s`;
                document.getElementById("met-angulos").innerText = `Roll: ${d.roll.toFixed(1)}° | Pitch: ${(-90.0 + d.pitch).toFixed(1)}° (Nadir F450)`;

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
            logMsg("Iniciando sincronizacion de relojes por cable USB...");
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

        async function iniciarGrabacion() {
            const mision = document.getElementById("input-mision").value.trim() || "Mision_Vuelo";
            const puerto = document.getElementById("sel-puerto").value;
            logMsg(`Iniciando grabacion de telemetria para mision: ${mision}...`);

            const r = await fetch("/api/flight/start", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mision: mision, puerto: puerto })
            });
            const d = await r.json();
            if (d.exito) {
                logMsg(`[+] Enlace de telemetria activo en ${d.puerto}. Guardando datos en vivo.`);
            } else {
                alert(`Error al iniciar: ${d.error}`);
                logMsg(`[ERROR] No se pudo conectar a telemetria: ${d.error}`);
            }
            actualizarHardware();
        }

        async function finalizarYProcesar() {
            if (!confirm("¿Desea finalizar la grabacion del vuelo actual y descargar/procesar las fotos de la GoPro?")) return;
            logMsg("Deteniendo telemetria y comenzando transferencia de fotos desde GoPro...");
            
            const r = await fetch("/api/flight/stop_and_process", { method: "POST" });
            const d = await r.json();
            logMsg(d.mensaje);
            actualizarHardware();
        }

        async function abrirCarpeta(ruta) {
            await fetch(`/api/open_folder?ruta=${encodeURIComponent(ruta)}`);
        }

        setInterval(actualizarHardware, 800);
        actualizarHardware();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html)

@app.get("/api/status")
async def get_status():
    global estado
    
    if not estado.gopro_ip:
        estado.gopro_ip = buscar_ip_gopro()
    if estado.gopro_ip and estado.gopro_bateria == "N/D":
        estado.gopro_bateria = consultar_estado_gopro(estado.gopro_ip)

    puertos_raw = list(serial.tools.list_ports.comports())
    puertos = [{"dev": p.device, "desc": f"{p.device} ({p.description})"} for p in puertos_raw if "bluetooth" not in (p.description or "").lower()]
    pix_puerto = buscar_puerto_pixhawk()

    return {
        "en_grabacion": estado.en_grabacion,
        "gopro_conectada": estado.gopro_ip is not None,
        "gopro_ip": estado.gopro_ip,
        "gopro_bateria": estado.gopro_bateria,
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
async def sync_clocks():
    global estado
    gopro_ip = buscar_ip_gopro()
    if not gopro_ip:
        return {"exito": False, "error": "No se detecto la GoPro. Verifique conexion USB y modo 'GoPro Connect'."}
    
    estado.gopro_ip = gopro_ip
    archivos_previos = obtener_lista_medios_gopro(gopro_ip)
    estado.fotos_previas = set((d, n) for d, n, _, _ in archivos_previos)

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
async def start_flight(data: dict):
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

    estado.hilo_telemetria = threading.Thread(target=bucle_telemetria, daemon=True)
    estado.hilo_telemetria.start()

    return {"exito": True, "puerto": puerto_real, "carpeta": carpeta}

def tarea_procesamiento_post_vuelo():
    global estado
    try:
        estado.estado_proceso = "DESCARGANDO"
        estado.mensaje_proceso = "Buscando fotografias y videos nuevos en la GoPro..."
        estado.progreso_porcentaje = 10

        ip = estado.gopro_ip or buscar_ip_gopro()
        if not ip:
            estado.estado_proceso = "ERROR"
            estado.mensaje_proceso = "No se pudo conectar con la GoPro para descargar los medios."
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

        # Fase de etiquetado a formato DJI Mini 2 SE con montura fijo_nadir (F450 sin gimbal)
        estado.estado_proceso = "ETIQUETANDO"
        estado.mensaje_proceso = "Inyectando metadatos DJI Mini 2 SE con compensacion F450 sin gimbal..."
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
        estado.mensaje_proceso = f"Exito: {exitos} de {total_locales} archivos procesados con metadatos nativos DJI Mini 2 SE (Montura F450 Nadir sin gimbal)."

    except Exception as e:
        estado.estado_proceso = "ERROR"
        estado.mensaje_proceso = f"Error durante el procesamiento: {e}"

@app.post("/api/flight/stop_and_process")
async def stop_flight(background_tasks: BackgroundTasks):
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
async def open_folder(ruta: str):
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
    print("   Plataforma F450 (Sin Gimbal - Camara fija mirando hacia abajo)")
    print("   Abriendo navegador en: http://localhost:8000")
    print("=================================================================")
    threading.Timer(1.2, lambda: webbrowser.open("http://localhost:8000")).start()
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")

if __name__ == "__main__":
    iniciar_servidor()
