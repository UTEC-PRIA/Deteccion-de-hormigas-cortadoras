"""Tramos por bateria, KMZ y reanudacion sin hardware: .venv/bin/python tests/probar_drones.py"""
import sys, os, io, zipfile, tempfile, types, xml.dom.minidom as X
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(P, "app"))
import drones as d, plan_vuelo as pv
from fastapi import HTTPException
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
print("OK")
