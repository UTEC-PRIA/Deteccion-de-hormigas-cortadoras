"""Vuela el plan en el ArduCopter real simulado (SITL). No usa el dron ni la radio.
Uso: .venv/bin/python -u tests/sitl_f450.py RUTA_ARDUCOPTER copter.parm [WPNAV_SPEED en cm/s]
Binarios oficiales: https://firmware.ardupilot.org/Copter/ (carpeta SITL_x86_64_linux_gnu)."""
import os, sys, time, subprocess, tempfile, threading, traceback

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(P, "app"))
BIN, PARM = map(os.path.abspath, sys.argv[1:3])
WPNAV = int(sys.argv[3]) if len(sys.argv) > 3 else 40
D = tempfile.mkdtemp()
os.chdir(D)
import rutas
rutas.PLANES, rutas.F450 = D + "/planes", D + "/vuelos"
HOME = (-32.3085, -53.8072)
with open(D + "/x.parm", "w") as f:
    f.write(f"WPNAV_SPEED {WPNAV}\nRTL_SPEED 100\nRTL_ALT 1500\nFS_THR_ENABLE 1\n")
sitl = subprocess.Popen([BIN, "--model", "quad", "--speedup", "1", "--home", f"{HOME[0]},{HOME[1]},200,0",
                         "--defaults", PARM + "," + D + "/x.parm", "-w"],
                        stdout=open(D + "/sitl.log", "w"), stderr=subprocess.STDOUT)
from pymavlink import mavutil

gas, rc = [1000], None


def piloto():
    """Segundo enlace: hace de control remoto."""
    global rc
    c = mavutil.mavlink_connection("tcp:127.0.0.1:5762", source_system=255)
    c.wait_heartbeat()
    rc = c
    while True:
        c.mav.rc_channels_override_send(c.target_system, 1, 1500, 1500, gas[0], 1500, 1800, 1000, 1000, 1000)
        c.mav.heartbeat_send(6, 8, 0, 0, 0)
        while c.recv_match(blocking=False):
            pass
        time.sleep(0.1)


def hasta(f, s, que):
    t = time.time()
    while time.time() - t < s:
        if f():
            return
        time.sleep(0.2)
    raise AssertionError(f"{que}: modo {st.modo_vuelo} alt {st.alt_rel} item {st.wp_actual} armado {st.armado}")


codigo = 1
try:
    time.sleep(4)
    import web_dashboard as w, plan_vuelo as pv, drones
    st = w.estado
    U = "tcp:127.0.0.1:5760"
    w.buscar_ip_gopro = lambda: None
    pv.conexion["puerto"] = lambda: U
    def enlace():
        # SITL no abre el puerto del control hasta que alguien usa el primero
        threading.Thread(target=piloto, daemon=True).start()
    k = 1 / 110574
    q = k / 0.845
    W = [{"lat": HOME[0] + 0.0001, "lon": HOME[1], "alt": 8}, {"lat": HOME[0] + 12 * k, "lon": HOME[1], "alt": 8},
         {"lat": HOME[0] + 12 * k, "lon": HOME[1] + 10 * q, "alt": 9, "espera": 2}, {"lat": HOME[0], "lon": HOME[1] + 10 * q, "alt": 8}]
    p = {"nombre": "s", "vel": 0.4, "fin": "RTL", "wps": W, "despegue": True, "confirmo": True}
    c0 = mavutil.mavlink_connection(U); c0.wait_heartbeat(timeout=20)
    enlace()
    t = time.time()
    while time.time() - t < 45:          # GPS y EKF
        c0.recv_match(blocking=True, timeout=0.2)
    c0.close()
    time.sleep(1)
    print("estado:", {x: y for x, y in pv.estado_dron("1").items() if x in ("errores", "sats", "rtl_alt", "pos")})
    r = pv.cargar(p, "1")
    print("carga:", {x: y for x, y in r.items() if x != "wps"})
    assert r["exito"]
    assert pv.dist((r["wps"][0]["lat"], r["wps"][0]["lon"]), HOME) < 3
    p["wps"] = r["wps"]
    print("grabacion:", w.start_flight({"mision": "s", "puerto": U}).get("exito"))
    hasta(lambda: st.satelites >= 10 and st.ultimo_msg_tiempo, 30, "telemetria")
    rc.mav.set_mode_send(rc.target_system, 1, 5)
    hasta(lambda: st.modo_vuelo == "LOITER", 15, "LOITER")
    time.sleep(2)
    for _ in range(10):
        rc.mav.command_long_send(rc.target_system, 1, 400, 0, 1, 0, 0, 0, 0, 0, 0)
        time.sleep(2)
        if st.armado:
            break
    assert st.armado, "no armo"
    gas[0] = 1750
    hasta(lambda: st.alt_rel > 5, 40, "despegue manual")
    gas[0] = 1500
    time.sleep(4)
    r = pv.modo({**p, "modo": "AUTO"}, "1")
    print("AUTO:", r)
    assert r["exito"]
    vis, v1, v2, pausa, t0 = [False] * 4, [], [], False, time.time()
    while time.time() - t0 < 420 and st.modo_vuelo == "AUTO":
        for i, x in enumerate(p["wps"]):
            if pv.dist((st.lat, st.lon), (x["lat"], x["lon"])) < 2.5 and (i == 0 or vis[i - 1]):
                vis[i] = True
        if (st.wp_actual or 0) >= 7:
            break
        if (st.wp_actual or 0) >= 4:
            (v2 if pausa else v1).append(st.velocidad)
        if not pausa and len(v1) > 60:
            it = st.wp_actual
            assert pv.modo({"modo": "LOITER"}, "1")["exito"]
            time.sleep(4)
            r = pv.modo({**p, "modo": "AUTO"}, "1")
            print("pausa y reanuda:", r, "item", it, "->", st.wp_actual)
            assert r["exito"]
            pausa = True
        time.sleep(0.2)
    med = lambda v: round(sorted(v)[len(v) // 2], 2) if v else None
    print(f"velocidad plan 0.4 | antes de pausar mediana {med(v1)} max {max(v1 or [0]):.2f} | despues mediana {med(v2)} max {max(v2 or [0]):.2f} | WPNAV {WPNAV / 100}")
    print("puntos alcanzados", vis, "segundos", round(time.time() - t0), "progreso", (drones.api_progreso() or {}).get("hacia"))
    assert all(vis)
    hasta(lambda: not st.armado, 240, "RTL y desarme")
    d = pv.dist((st.lat, st.lon), HOME)
    print(f"aterrizo a {d:.1f} m del despegue")
    assert d < 2
    print("SITL OK")
    codigo = 0
except BaseException:
    traceback.print_exc()
    print(open(D + "/sitl.log").read()[-500:])
finally:
    sitl.kill()
    os._exit(codigo)
