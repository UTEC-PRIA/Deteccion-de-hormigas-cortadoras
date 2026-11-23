# -*- coding: utf-8 -*-
"""Ubicacion unica de los datos: datos/vuelos/<dron>/<vuelo>/ y datos/planes/."""
import os, glob, re, shutil
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS = os.path.join(RAIZ, "datos")
VUELOS, PLANES = os.path.join(DATOS, "vuelos"), os.path.join(DATOS, "planes")
F450 = os.path.join(VUELOS, "f450_gopro")

def carpetas():
    return sorted((os.path.dirname(p) for p in glob.glob(os.path.join(VUELOS, "*", "*", "telemetria.csv"))),
                  key=lambda c: c[-15:], reverse=True)

def buscar(nombre):
    if not re.fullmatch(r"[\w.-]+", nombre) or nombre.startswith("."): return None
    return next((c for c in carpetas() if os.path.basename(c) == nombre), None)

def migrar():
    """Vuelos guardados por una version anterior en <raiz>/vuelos. Nunca reemplaza un vuelo existente."""
    for c in glob.glob(os.path.join(RAIZ, "vuelos", "*", "")):
        d = os.path.join(F450, os.path.basename(c.rstrip("/\\")))
        if not os.path.exists(d): os.makedirs(F450, exist_ok=True); shutil.move(c.rstrip("/\\"), d)
