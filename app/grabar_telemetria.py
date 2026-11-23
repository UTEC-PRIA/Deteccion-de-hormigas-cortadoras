#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Modulo 2: Grabador de Telemetria en Tiempo Real (Kit SiK 915 MHz / MAVLink)
Compatible con Windows y Ubuntu.
"""

import sys
import os
import time
import argparse
from datetime import datetime, timezone
import serial.tools.list_ports
from pymavlink import mavutil

MODOS_ARDUPILOT = {
    0: 'STABILIZE', 1: 'ACRO', 2: 'ALT_HOLD', 3: 'AUTO', 4: 'GUIDED',
    5: 'LOITER', 6: 'RTL', 7: 'CIRCLE', 9: 'LAND', 11: 'DRIFT',
    13: 'SPORT', 14: 'FLIP', 15: 'AUTOTUNE', 16: 'POSHOLD', 17: 'BRAKE'
}

def listar_puertos_disponibles():
    """Retorna una lista de puertos serie disponibles en el sistema."""
    puertos = [p for p in serial.tools.list_ports.comports() if p.vid != 0x2CA3]
    res = []
    for p in puertos:
        desc = p.description or ""
        hwid = p.hwid or ""
        res.append((p.device, f"{p.device} ({desc})"))
    # Agregar puertos tipicos de Linux si existen
    for dev in ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]:
        if os.path.exists(dev) and not any(p.device == dev for p in serial.tools.list_ports.comports()) and not any(r[0] == dev for r in res):
            res.append((dev, dev))
    return res

def seleccionar_puerto_interactivo():
    """Permite seleccionar el puerto COM de forma interactiva y simple."""
    print("\n--- SELECCION DE PUERTO DE TELEMETRIA ---")
    puertos = listar_puertos_disponibles()
    
    opciones = []
    for dev, desc in puertos:
        # Excluir puertos de Bluetooth de Windows que suelen no ser telemetria
        if "bluetooth" not in desc.lower():
            opciones.append((dev, desc))

    print("Puertos detectados en el sistema:")
    for idx, (dev, desc) in enumerate(opciones, 1):
        print(f"  [{idx}] {desc}")
    print(f"  [U] Entrada de red UDP (127.0.0.1:14550) - Util si Mission Planner esta abierto")
    
    if not opciones:
        print("  [!] No se encontraron puertos serie directos.")
        print("      Verifique que la antena receptora de 915 MHz este conectada por USB.")
        manual = input("\nIngrese manualmente el puerto (ejemplo COM5 o /dev/ttyUSB0) o 'U' para UDP: ").strip()
        if manual.upper() == 'U':
            return "udpin:127.0.0.1:14550"
        return manual

    eleccion = input("\nSeleccione el numero de puerto (o presione ENTER para la opcion 1): ").strip()
    if not eleccion:
        return opciones[0][0]
    if eleccion.upper() == 'U':
        return "udpin:127.0.0.1:14550"
    try:
        idx_sel = int(eleccion) - 1
        if 0 <= idx_sel < len(opciones):
            return opciones[idx_sel][0]
    except Exception:
        pass
    return eleccion

def main():
    print("=================================================================")
    print("   GRABADOR DE TELEMETRIA EN VIVO (KIT 915 MHz / MAVLINK)")
    print("   Proyecto UAV Hormigas Cortadoras - UTEC PRIA")
    print("=================================================================")

    parser = argparse.ArgumentParser(description="Grabador de telemetria en tiempo real para UAV")
    parser.add_argument("--port", help="Puerto serie (ej. COM5, /dev/ttyUSB0) o direccion UDP (ej. udpin:127.0.0.1:14550)")
    parser.add_argument("--baud", type=int, default=57600, help="Velocidad en baudios (57600 para radios de 915 MHz)")
    parser.add_argument("--outdir", default="registros_vuelo", help="Carpeta donde se guardaran los registros")
    args = parser.parse_args()

    puerto = args.port
    if not puerto:
        puerto = seleccionar_puerto_interactivo()

    baud = args.baud
    # Si es UDP el baudrate no aplica
    es_udp = "udp" in puerto.lower()

    # Crear carpeta de registro con fecha y hora
    timestamp_inicio = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta_mision = os.path.join(args.outdir, f"vuelo_{timestamp_inicio}")
    os.makedirs(carpeta_mision, exist_ok=True)

    ruta_csv = os.path.join(carpeta_mision, "telemetria.csv")
    ruta_tlog = os.path.join(carpeta_mision, "telemetria.tlog")

    print(f"\n[*] Conectando a telemetria en: {puerto} " + (f"a {baud} baudios" if not es_udp else ""))
    print(f"[*] Carpeta de almacenamiento : {carpeta_mision}")

    try:
        if es_udp:
            conexion = mavutil.mavlink_connection(puerto)
        else:
            conexion = mavutil.mavlink_connection(puerto, baud=baud)
    except Exception as e:
        print(f"\n[ERROR] No se pudo abrir la conexion: {e}")
        print("Si Mission Planner ya esta usando este puerto, ciérrelo o utilice la opcion UDP.")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    print("[*] Esperando senal del dron (Heartbeat)...")
    hb = conexion.wait_heartbeat(timeout=30)
    if not hb:
        print("[!] No se recibio respuesta del dron en 30 segundos.")
        print("Verifique que el dron este encendido y la antena de 915 MHz tenga el LED verde fijo.")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    print(f"[+] CONEXION ESTABLECIDA con Sistema {conexion.target_system} (Autopilot: {hb.autopilot})")

    # Solicitar flujos de telemetria necesarios
    try:
        conexion.mav.request_data_stream_send(
            conexion.target_system,
            conexion.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            4, 1
        )
    except Exception:
        pass

    # Archivo binario TLOG para Mission Planner
    f_tlog = open(ruta_tlog, "wb")
    
    # Archivo tabular CSV para post-procesamiento directo
    f_csv = open(ruta_csv, "w", encoding="utf-8")
    f_csv.write("timestamp_utc,latitud,longitud,altitud_msl,altitud_relativa,alabeo_roll,cabeceo_pitch,rumbo_yaw,velocidad_ms,satelites,voltaje_bateria,modo_vuelo\n")

    # Variables de estado actual
    lat = 0.0
    lon = 0.0
    alt_msl = 0.0
    alt_rel = 0.0
    roll = 0.0
    pitch = 0.0
    yaw = 0.0
    speed = 0.0
    sats = 0
    voltage = 0.0
    flight_mode = "DESCONOCIDO"

    total_muestras = 0
    ultimo_escrito = 0
    ultimo_refresco_pantalla = 0

    print("\n" + "=" * 65)
    print("   GRABACION DE TELEMETRIA EN CURSO")
    print("   Presione Ctrl + C en cualquier momento para detener y guardar.")
    print("=" * 65)

    try:
        while True:
            msg = conexion.recv_msg()
            if msg is None:
                time.sleep(0.01)
                continue

            # Guardar paquete crudo en tlog
            try:
                f_tlog.write(msg.get_msgbuf())
            except Exception:
                pass

            mtype = msg.get_type()

            if mtype == 'HEARTBEAT':
                custom_mode = getattr(msg, 'custom_mode', 0)
                flight_mode = MODOS_ARDUPILOT.get(custom_mode, f"MODO_{custom_mode}")

            elif mtype == 'GLOBAL_POSITION_INT':
                lat = msg.lat / 1e7
                lon = msg.lon / 1e7
                alt_msl = msg.alt / 1000.0
                alt_rel = msg.relative_alt / 1000.0
                vx = msg.vx / 100.0
                vy = msg.vy / 100.0
                speed = (vx**2 + vy**2)**0.5

            elif mtype == 'GPS_RAW_INT':
                sats = getattr(msg, 'satellites_visible', sats)
                if lat == 0.0:
                    lat = msg.lat / 1e7
                    lon = msg.lon / 1e7
                    alt_msl = msg.alt / 1000.0

            elif mtype == 'ATTITUDE':
                import math
                roll = math.degrees(msg.roll)
                pitch = math.degrees(msg.pitch)
                yaw = math.degrees(msg.yaw)
                if yaw < 0:
                    yaw += 360.0

            elif mtype == 'SYS_STATUS':
                voltage = msg.voltage_battery / 1000.0

            # Guardar en CSV cada 250 ms (4 Hz)
            ahora = time.time()
            if ahora - ultimo_escrito >= 0.25 and lat != 0.0:
                t_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                linea = f"{t_utc},{lat:.7f},{lon:.7f},{alt_msl:.2f},{alt_rel:.2f},{roll:.2f},{pitch:.2f},{yaw:.2f},{speed:.2f},{sats},{voltage:.2f},{flight_mode}\n"
                f_csv.write(linea)
                f_csv.flush()
                ultimo_escrito = ahora
                total_muestras += 1

            # Actualizar estado en pantalla cada 1 segundo
            if ahora - ultimo_refresco_pantalla >= 1.0:
                sys.stdout.write(
                    f"\r[ESTADO] Modo: {flight_mode:<9} | Sats: {sats:<2} | AltRel: {alt_rel:>5.1f}m | "
                    f"Bat: {voltage:>4.1f}V | Lat: {lat:>10.6f} | Lon: {lon:>10.6f} | Regs: {total_muestras:<5}"
                )
                sys.stdout.flush()
                ultimo_refresco_pantalla = ahora

    except KeyboardInterrupt:
        print("\n\n[*] Deteniendo grabacion a solicitud del operador...")
    finally:
        f_csv.close()
        f_tlog.close()
        conexion.close()

    print("=================================================================")
    print("   GRABACION COMPLETADA Y GUARDADA")
    print("=================================================================")
    print(f"  Total de registros capturados : {total_muestras}")
    print(f"  Archivo de datos CSV          : {ruta_csv}")
    print(f"  Archivo de registro TLOG      : {ruta_tlog}")
    print("\nAmbos archivos quedan listos para vincularse con las fotos de la GoPro.")
    print("=================================================================")
    if sys.stdin.isatty():
        input("\nPresione ENTER para finalizar...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
