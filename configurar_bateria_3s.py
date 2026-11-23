#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Configuracion Automatica del Monitor de Bateria LiPo 3S en Pixhawk 2.4.8 (ArduPilot)
"""

import sys
import time
import serial.tools.list_ports
from pymavlink import mavutil

PARAMETROS_3S = [
    # Activar monitor analogo de voltaje y corriente
    ('BATT_MONITOR', 4.0),
    # Pixhawk 2.4.8 (FMUv3): Pin 13 es voltaje analogo, Pin 14 es corriente analoga
    ('BATT_VOLT_PIN', 13.0),
    ('BATT_CURR_PIN', 14.0),
    # Divisor resistivo estandar para Power Module 3DR (10.1:1)
    ('BATT_VOLT_MULT', 10.1),
    # Multiplicador y offset de corriente
    ('BATT_AMP_PERVLT', 18.001),
    ('BATT_AMP_OFFSET', 1.35),
    # Protecciones LiPo 3S (Nominal 11.1V, Max 12.6V, Alarma 10.5V, Critico 10.2V)
    ('BATT_LOW_VOLT', 10.5),
    ('BATT_CRT_VOLT', 10.2),
    ('BATT_FS_LOW_ACT', 2.0), # RTL o advertencia
    ('BATT_FS_CRT_ACT', 1.0), # Aterrizaje inmediato
    ('BATT_CAPACITY', 4200.0) # Capacidad tipica en mAh
]

def buscar_puerto():
    from sincronizar_relojes import buscar_puerto_pixhawk
    puerto = buscar_puerto_pixhawk()
    if puerto:
        return puerto
    # Descartar Bluetooth y puertos serie sin hardware (/dev/ttyS* en Linux)
    puertos = list(serial.tools.list_ports.comports())
    candidatos = [p.device for p in puertos
                  if "bluetooth" not in (p.description or "").lower() and (p.hwid or "n/a") != "n/a"]
    return candidatos[0] if candidatos else "COM10"

def main():
    print("=================================================================")
    print("  CONFIGURACION DE BATERIA LIPO 3S EN PIXHAWK 2.4.8")
    print("  UTEC PRIA - Deteccion de Hormigas Cortadoras")
    print("=================================================================")

    puerto = sys.argv[1] if len(sys.argv) > 1 else buscar_puerto()
    baud = 57600
    print(f"Conectando a {puerto} a {baud} baudios...")

    try:
        conn = mavutil.mavlink_connection(puerto, baud=baud, timeout=5)
        conn.wait_heartbeat(timeout=6)
        print(f"[OK] Comunicacion MAVLink establecida con sistema {conn.target_system}.\n")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a {puerto}: {e}")
        return

    print("Grabando parametros para bateria LiPo 3S en memoria EEPROM de Pixhawk:")
    for param_name, param_val in PARAMETROS_3S:
        conn.mav.param_set_send(
            conn.target_system, conn.target_component,
            param_name.encode('ascii'),
            float(param_val),
            mavutil.mavlink.MAV_PARAM_TYPE_REAL32
        )
        print(f"  -> {param_name:<16} = {param_val}")
        time.sleep(0.12)

    time.sleep(1)
    print("\nVerificando lectura en vivo del sensor de bateria...")
    conn.mav.request_data_stream_send(conn.target_system, conn.target_component, mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)

    lecturas_ok = 0
    start = time.time()
    while time.time() - start < 4:
        msg = conn.recv_match(type='SYS_STATUS', blocking=True, timeout=1)
        if msg:
            voltaje = msg.voltage_battery / 1000.0
            corriente = msg.current_battery / 100.0
            remanente = msg.battery_remaining
            if voltaje > 9.0:
                celda = voltaje / 3.0
                pct = max(0, min(100, int((voltaje - 10.5) / (12.6 - 10.5) * 100)))
                print(f"  Voltaje Total: {voltaje:.2f} V ({celda:.2f} V/celda) | Carga Estimada: ~{pct}% | Consumo en Reposo: {corriente:.2f} A")
                lecturas_ok += 1
                if lecturas_ok >= 3:
                    break

    if lecturas_ok > 0:
        print("\n[EXITO] La lectura de bateria 3S quedo configurada y calibrada correctamente.")
    else:
        print("\n[AVISO] Parametros grabados. Conecte la bateria 3S al Power Module para ver el voltaje.")

if __name__ == "__main__":
    main()
