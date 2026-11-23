"""Tramos por bateria, KMZ y reanudacion sin hardware: .venv/bin/python tests/probar_drones.py"""
import sys, os, io, zipfile, tempfile, types, xml.dom.minidom as X
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(P, "app"))
import drones as d, plan_vuelo as pv, trayectoria, math
from fastapi import HTTPException
assert list(d.api_drones()) == ["f450"]
try: pv.normalizar({"vel": 1, "fin": "RTL", "wps": [], "dron": "mini5pro"}); assert False
except HTTPException: pass
d.NAV_DJI = True
W = [{"lat": -32.309 + .0001 * (i // 2), "lon": -53.807 + .002 * ((i + 1) // 2 % 2), "alt": 8, "espera": 2} for i in range(40)]
p = {"nombre": "t", "vel": 2, "fin": "RTL", "wps": W, "dron": "mini5pro", "casa": [-32.3092, -53.8071], "bateria": 15}
def falla(f, n):
    try: f()
    except HTTPException as e: assert e.status_code == n, e.detail; return
    assert False, "debia fallar"
t = d.api_tramos(p, "1"); print(t)
assert t[0]["desde"] == 1 and t[-1]["hasta"] == 40 and all(a["hasta"] == b["desde"] for a, b in zip(t, t[1:])) and all(x["min"] <= 15 for x in t) and len(t) > 1
z = zipfile.ZipFile(io.BytesIO(d.api_kmz({**p, "tramo": 2, "media": "foto"}, "1").body)); assert z.namelist() == ["wpmz/template.kml", "wpmz/waylines.wpml"]
x = X.parseString(z.read("wpmz/waylines.wpml")); X.parseString(z.read("wpmz/template.kml"))
assert len(x.getElementsByTagName("Placemark")) == t[1]["hasta"] - t[1]["desde"] + 1 and "goHome" in x.toxml()
falla(lambda: d.api_kmz({**p, "dron": "mini2se"}, "1"), 400); falla(lambda: d.api_kmz({**p, "info": "<a/>"}, "1"), 400)
falla(lambda: d.api_tramos({**p, "bateria": 3}, "1"), 400); falla(lambda: d.api_tramos({**p, "casa": ["x"]}, "1"), 400); falla(lambda: d.api_tramos(p, ""), 403)
falla(lambda: pv.cargar({**p, "confirmo": True}, "1"), 400); falla(lambda: pv.normalizar({**p, "dron": "otro"}), 400)
assert pv.validar(pv.normalizar({**p, "dron": "f450"}))["errores"]      # limites de f450 intactos
d.PLANES = tempfile.mkdtemp(); d.PROGRESO = d.PLANES + "/p.json"; assert d.api_progreso() is None
st = types.SimpleNamespace(wp_actual=7, en_grabacion=True, armado=True, modo_vuelo="AUTO", lat=1, lon=2); c = {"plan": pv.normalizar(p), "id": "a"}
d.guardar_progreso(st, c); st.modo_vuelo = "RTL"; st.wp_actual = 30; d.guardar_progreso(st, c); r = d.api_progreso()
assert r["hacia"] == 4 and not r["completo"]; st.modo_vuelo = "AUTO"; st.wp_actual = 43; d.guardar_progreso(st, c); assert d.api_progreso()["completo"]
# recorrido conocido -> redondeado a 4 decimales -> estimado
la, lo, ky, kx = -32.31, -53.807, 110574, 111320 * math.cos(math.radians(32.31))
R = [(min(i, 60) * 1.0, max(0, i - 60) * 1.0) for i in range(121)]
T = [{"s": i, "lat": round(la + y / ky, 4), "lon": round(lo + x / kx, 4), "casa": round(math.hypot(x, y), 2), "vel": 1.0} for i, (x, y) in enumerate(R)]
E = trayectoria.estimar(T); err = lambda P: sum(d.dist(p, (la + y / ky, lo + x / kx)) for p, (x, y) in zip(P, R)) / len(R)
a, b = err([(p["lat"], p["lon"]) for p in T]), err(E); print(f"error medio grabado {a:.1f} m, estimado {b:.1f} m"); assert b < a
import tempfile as tf
f = tf.mktemp(suffix=".SRT"); open(f, "w").write("1\n00:00:00,000 --> 00:00:00,033\n[latitude: -32.3] [longitude: -53.8] [rel_alt: 5.1 abs_alt: 200]\n\n2\n00:00:01,001 --> 00:00:01,034\n[latitude: -32.30001] [longitude: -53.8] [rel_alt: 5.2 abs_alt: 200]\n")
q = d.telemetria_srt(f); assert len(q) == 2 and q[1]["alt"] == 5.2 and q[1]["vel"] > 1; assert not d.en_tierra(q)
print("OK")
