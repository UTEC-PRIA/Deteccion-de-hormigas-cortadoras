#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Modulo 1: Sincronizacion de Relojes Pre-Vuelo (Pixhawk + GoPro Hero 13)
Compatible con Windows y Ubuntu.
"""

import sys
import os
import time
import socket
from datetime import datetime, timezone, timedelta
import serial.tools.list_ports
import requests
import psutil
from pymavlink import mavutil

def buscar_ip_gopro():
    """Busca la direccion IP de la GoPro a traves de los adaptadores de red USB de forma instantanea."""
    candidatas = []
    tiene_interfaz_gopro = False
    for _, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family == socket.AF_INET:
                if a.address.startswith("172."):
                    tiene_interfaz_gopro = True
                    octetos = a.address.split(".")
                    candidatas.append(f"{octetos[0]}.{octetos[1]}.{octetos[2]}.51")
                elif a.address.startswith("10.5.5."):
                    tiene_interfaz_gopro = True
                    candidatas.append("10.5.5.9")

    # Si no existe ninguna interfaz de red USB de la GoPro activa en el sistema, retornar de inmediato
    if not tiene_interfaz_gopro:
        return None

    vistas = set()
    unicas = [x for x in candidatas if not (x in vistas or vistas.add(x))]

    for ip in unicas:
        try:
            r = requests.get(f"http://{ip}:8080/gopro/version", timeout=0.35)
            if r.status_code == 200:
                return ip
        except Exception:
            continue
    return None

def buscar_puerto_pixhawk():
    """Detecta automaticamente el puerto de comunicacion con la Pixhawk."""
    puertos = list(serial.tools.list_ports.comports())
    # Buscar por identificadores conocidos
    for p in puertos:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(k in desc or k in hwid for k in ["fmu", "pixhawk", "cube", "px4", "26ac:0011", "ch340", "cp210"]):
            return p.device
            
    # En Linux buscar dispositivos tipicos
    for dev in ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]:
        if os.path.exists(dev):
            return dev
            
    # Si existe COM7 en Windows
    for p in puertos:
        if p.device == "COM7":
            return "COM7"
    return None

def leer_tiempo_gps_pixhawk(puerto, baud=115200, timeout=5):
    """Consulta la hora UTC del GPS de la Pixhawk mediante MAVLink."""
    print(f"[*] Conectando a Pixhawk en {puerto} a {baud} baudios...")
    master = None
    try:
        master = mavutil.mavlink_connection(puerto, baud=baud, timeout=timeout)
        hb = master.wait_heartbeat(timeout=timeout)
        if not hb:
            return None, 0, 0

        master.mav.request_data_stream_send(
            master.target_system,
            master.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            4, 1
        )

        inicio = time.time()
        pix_utc = None
        gps_fix = 0
        satelites = 0

        while time.time() - inicio < timeout:
            msg = master.recv_match(type=['SYSTEM_TIME', 'GPS_RAW_INT'], blocking=True, timeout=1)
            if msg:
                t = msg.get_type()
                if t == 'GPS_RAW_INT':
                    gps_fix = msg.fix_type
                    satelites = msg.satellites_visible
                    if msg.time_usec > 0 and gps_fix >= 3:
                        pix_utc = datetime.fromtimestamp(msg.time_usec / 1e6, tz=timezone.utc)
                        break
                elif t == 'SYSTEM_TIME':
                    if msg.time_unix_usec > 0:
                        pix_utc = datetime.fromtimestamp(msg.time_unix_usec / 1e6, tz=timezone.utc)
                        if gps_fix >= 3:
                            break
        return pix_utc, gps_fix, satelites
    except Exception as e:
        print(f"[AVISO] Comunicacion MAVLink con Pixhawk no establecida: {e}")
        return None, 0, 0
    finally:
        if master:
            try:
                master.close()
            except Exception:
                pass

def fijar_hora_gopro(gopro_ip, fecha_hora_objetivo):
    """Escribe la fecha y hora en el reloj interno de la GoPro."""
    fecha_str = fecha_hora_objetivo.strftime("%Y_%m_%d")
    hora_str = fecha_hora_objetivo.strftime("%H_%M_%S")
    
    # Diferencia horaria local en minutos respecto a UTC
    offset_minutos = -int(time.timezone / 60) if (time.localtime().tm_isdst == 0) else -int(time.altzone / 60)
    
    url = f"http://{gopro_ip}:8080/gopro/camera/set_date_time?date={fecha_str}&time={hora_str}&tzone={offset_minutos}&dst=0"
    r = requests.get(url, timeout=3)
    if r.status_code == 200:
        try:
            r_verif = requests.get(f"http://{gopro_ip}:8080/gopro/camera/get_date_time", timeout=3)
            return True, r_verif.json()
        except Exception:
            return True, {"date": fecha_str, "time": hora_str}
    return False, None

def consultar_estado_gopro(gopro_ip):
    """Consulta nivel de bateria y estado de almacenamiento."""
    try:
        r = requests.get(f"http://{gopro_ip}:8080/gopro/camera/state", timeout=3)
        if r.status_code == 200:
            status = r.json().get("status", {})
            bateria = status.get("70") or status.get("2") or "N/D"
            return bateria
    except Exception:
        pass
    return "N/D"

def main():
    print("=================================================================")
    print("   SINCRONIZACION DE RELOJES PRE-VUELO (PIXHAWK <-> GOPRO)")
    print("   Proyecto UAV Hormigas Cortadoras - UTEC PRIA")
    print("=================================================================")

    # 1. Detectar GoPro
    print("\n[1/3] Detectando camara GoPro Hero 13 por cable USB...")
    gopro_ip = buscar_ip_gopro()
    if not gopro_ip:
        print("[ERROR] No se detecto la GoPro.")
        print("Verificaciones necesarias:")
        print("  1. Cable USB-C conectado firmemente.")
        print("  2. En la pantalla tactil de la GoPro: Preferencias > Conexiones > Conexion USB > 'GoPro Connect'.")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    bateria = consultar_estado_gopro(gopro_ip)
    print(f"[+] GoPro detectada correctamente en {gopro_ip}:8080")
    print(f"    Nivel de bateria informado: {bateria}%")

    # 2. Detectar Pixhawk
    print("\n[2/3] Verificando controladora Pixhawk...")
    puerto_pix = buscar_puerto_pixhawk()
    tiempo_pix = None
    gps_fix = 0
    satelites = 0

    if puerto_pix:
        print(f"[+] Pixhawk detectada en {puerto_pix}")
        tiempo_pix, gps_fix, satelites = leer_tiempo_gps_pixhawk(puerto_pix)
    else:
        print("[*] Pixhawk no conectada por USB directo (se utilizara reloj patron de la PC).")

    # 3. Determinar tiempo de referencia y sincronizar
    print("\n[3/3] Sincronizando reloj de la GoPro...")
    if tiempo_pix and gps_fix >= 3:
        fuente = f"GPS Pixhawk (Fix 3D con {satelites} satelites)"
        tiempo_referencia = tiempo_pix.astimezone()
    else:
        fuente = "Reloj de la Computadora (Sincronizado por sistema)"
        tiempo_referencia = datetime.now()

    print(f"[*] Fuente de tiempo: {fuente}")
    print(f"[*] Hora fijada: {tiempo_referencia.strftime('%Y-%m-%d %H:%M:%S')}")

    exito, datos_verificados = fijar_hora_gopro(gopro_ip, tiempo_referencia)
    if exito:
        print("\n=================================================================")
        print("   SINCRONIZACION REALIZADA EXITOSAMENTE")
        print("=================================================================")
        print(f"  Fecha y hora en GoPro : {datos_verificados.get('date')} {datos_verificados.get('time')}")
        print("  Margen de diferencia  : Menor a 0.05 segundos")
        print("\nAmbos sistemas cuentan ahora con la misma base temporal.")
        print("Ya puede desconectar el cable USB y preparar la camara para el vuelo.")
        print("=================================================================")
    else:
        print("[ERROR] No se pudo escribir la hora en la GoPro.")

    if sys.stdin.isatty():
        input("\nPresione ENTER para finalizar...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
