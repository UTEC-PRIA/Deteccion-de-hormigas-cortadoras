#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Graba el recorrido de un vuelo MANUAL y lo convierte en waypoints. Solo lectura: no envia nada al dron."""
import os, json, math, time, threading
from fastapi import APIRouter, Header, HTTPException
import plan_vuelo as pv, rutas

router = APIRouter()
DIR = os.path.join(os.path.dirname(rutas.PLANES), "trayectos")
MAX_WP, ALT_AIRE, PASO = 40, 2.0, 0.5      # puntos maximos, altura desde la que cuenta, metros entre muestras
G = {"on": False, "pts": [], "inicio": None, "archivo": None, "descartadas": 0}
_l = threading.Lock()

def muestra(lat, lon, alt, armado, gps_ok):
    """La llama el lector de telemetria con cada posicion."""
    if not G["on"] or not armado or alt < ALT_AIRE: return
    if not gps_ok: G["descartadas"] += 1; return
    with _l:
        p = G["pts"]
        if p and math.hypot(pv.dist(p[-1], (lat, lon)), alt - p[-1][2]) < PASO: return
        if len(p) >= 5000: return
        p.append((lat, lon, round(alt, 2)))
        try:
            with open(G["archivo"], "a", encoding="utf-8") as f: f.write(f"{time.time():.1f},{lat:.7f},{lon:.7f},{alt:.2f}\n")
        except OSError: pass

def _dp(q, tol):
    """Douglas-Peucker en 3D; q en metros. Devuelve indices conservados."""
    ok, pila = {0, len(q) - 1}, [(0, len(q) - 1)]
    while pila:
        a, b = pila.pop(); md, mi = 0, None
        A, B = q[a], q[b]; v = [B[i] - A[i] for i in range(3)]; L = sum(x * x for x in v)
        for i in range(a + 1, b):
            w = [q[i][k] - A[k] for k in range(3)]; t = max(0, min(1, sum(x * y for x, y in zip(w, v)) / L)) if L else 0
            d = math.sqrt(sum((w[k] - t * v[k]) ** 2 for k in range(3)))
            if d > md: md, mi = d, i
        if md > tol: ok.add(mi); pila += [(a, mi), (mi, b)]
    return sorted(ok)

def simplificar(pts):
    """Recorrido -> waypoints: conserva curvas, al menos 2 m entre puntos, altura dentro de los limites y tramos cortos."""
    if len(pts) < 2: return {"wps": [], "ajustadas": 0, "tol": 0}
    la, lo = pts[0][:2]; kx = 111320 * math.cos(math.radians(la))
    q = [((p[1] - lo) * kx, (p[0] - la) * 111320, p[2]) for p in pts]
    tol = 1.0
    while True:
        s = _dp(q, tol); f = [s[0]]
        for i in s[1:]:
            if math.dist(q[i], q[f[-1]]) >= 2: f.append(i)
        if len(f) > 1 and f[-1] != s[-1]: f[-1] = s[-1]      # terminar donde termino el vuelo
        if len(f) <= MAX_WP: break
        tol *= 1.3
    L, aj, w = pv.LIM, 0, []
    for i in f:
        h = min(L["alt_max"], max(L["alt_min"], pts[i][2])); aj += abs(h - pts[i][2]) > 0.05
        w.append({"lat": pts[i][0], "lon": pts[i][1], "alt": round(h * 2) / 2, "espera": 0})
    return {"wps": w, "ajustadas": aj, "tol": round(tol, 1)}

def resumen():
    p = G["pts"]
    return {"on": G["on"], "n": len(p), "seg": round(time.time() - G["inicio"]) if G["on"] else None, "descartadas": G["descartadas"]}

@router.post("/api/trayecto/iniciar")
def iniciar(x_hormigas: str = Header("")):
    pv._guardia(x_hormigas); os.makedirs(DIR, exist_ok=True)
    with _l: G.update(pts=[], inicio=time.time(), descartadas=0, archivo=os.path.join(DIR, time.strftime("trayecto_%Y%m%d_%H%M%S.csv")), on=True)
    return {"exito": True}

@router.post("/api/trayecto/parar")
def parar(x_hormigas: str = Header("")):
    pv._guardia(x_hormigas); G["on"] = False
    return resumen()

@router.get("/api/trayecto/puntos")
def puntos():
    with _l: p = list(G["pts"])
    return {**simplificar(p), "crudo": [x[:2] for x in p], "metros": round(sum(pv.dist(a, b) for a, b in zip(p, p[1:])))}
