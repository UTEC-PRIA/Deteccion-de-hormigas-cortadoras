"""Convierte un log .BIN de la Pixhawk (ArduCopter) en telemetria.csv, con hora GPS y 10 posiciones por segundo.
Uso: python app/log_pixhawk.py LOG.BIN SALIDA.csv"""
import csv, math, sys
from datetime import datetime, timezone
from pymavlink import mavutil
from vincular_vuelo_dji import gps_a_utc_epoch

MODOS = {0: "STABILIZE", 2: "ALT_HOLD", 3: "AUTO", 5: "LOITER", 6: "RTL", 9: "LAND"}
CAB = ["timestamp_utc", "latitud", "longitud", "altitud_msl", "altitud_relativa", "alabeo_roll", "cabeceo_pitch", "rumbo_yaw",
       "velocidad_ms", "satelites", "voltaje_bateria", "modo_vuelo"]

def leer(ruta):
    m = mavutil.mavlink_connection(ruta); off = None; s = dict(r=0, p=0, y=0, v=0, sat=0, vel=0, m="DESCONOCIDO"); filas = []
    while True:
        x = m.recv_match(type=["GPS", "POS", "ATT", "BAT", "MODE"])
        if x is None: break
        k = x.get_type()
        if k == "GPS":
            if x.Status >= 3 and x.GWk > 2000:
                if off is None: off = gps_a_utc_epoch(x.GWk, x.GMS) - x.TimeUS / 1e6
                s.update(sat=x.NSats, vel=x.Spd)
        elif k == "ATT": s.update(r=x.Roll, p=x.Pitch, y=x.Yaw % 360)
        elif k == "BAT": s["v"] = x.Volt
        elif k == "MODE": s["m"] = MODOS.get(x.Mode, str(x.Mode))
        elif (x.Lat or x.Lng): filas.append((x.TimeUS / 1e6, x.Lat, x.Lng, x.Alt, x.RelHomeAlt, s["r"], s["p"], s["y"], s["vel"], s["sat"], s["v"], s["m"]))
    if off is None: raise RuntimeError("El log no tiene hora GPS.")
    return [(t + off, *f) for t, *f in filas]

def escribir(ruta_bin, ruta_csv):
    f = leer(ruta_bin)
    with open(ruta_csv, "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h); w.writerow(CAB)
        for t, la, lo, am, al, r, p, y, v, n, b, m in f:
            w.writerow([datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], f"{la:.7f}", f"{lo:.7f}", f"{am:.2f}", f"{al:.2f}",
                        f"{r:.2f}", f"{p:.2f}", f"{y:.2f}", f"{v:.2f}", n, f"{b:.2f}", m])
    return len(f)

if __name__ == "__main__": print(escribir(sys.argv[1], sys.argv[2]), "posiciones")
