"""Puente hacia AnTrack. No envia nada: prepara archivos.
  python app/antrack.py paquete VUELO|todos [SALIDA] ZIP con las imagenes originales y las coordenadas del dron (uso actual)
  python app/antrack.py imagenes VUELO              lista de imagenes con GPS para el servidor de IA (imagenes.csv)
  python app/antrack.py exportar VUELO [SALIDA]     detecciones.json -> ZIP con pares .json + .png (formato A, para mas adelante)
detecciones.json (en la carpeta del vuelo): [{"imagen": "X.JPG", "clase": "hormiguero", "confianza": 0.87, "x": 10, "y": 20, "ancho": 30, "alto": 40}]
x, y = CENTRO del recuadro en pixeles de la imagen original. Se aceptan los nombres class, confidence, width, height.
Guia: docs/guias/ANTRACK.md"""
import csv, io, json, math, os, re, subprocess, sys, unicodedata, zipfile
from datetime import datetime
from functools import lru_cache
from PIL import Image, ImageDraw
import rutas

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, "datos", "salida_antrack")
MAX_PNG, MAX_ZIP, MAX_ARCH = 10_000_000, 90_000_000, 2000
TIPOS = {"colony", "colonia", "hormiguero", "nido", "nest", "anthill", "trail", "camino", "sendero", "rastro", "path", "caminito", "leaf_cut", "leafcut",
         "leaf_cutting", "corte", "corte_de_hoja", "corte_hoja", "hoja_cortada", "hojas_cortadas", "defoliacion", "defoliation"}

def tipo(t):
    t = unicodedata.normalize("NFD", str(t or "")).encode("ascii", "ignore").decode().lower().strip()
    t = re.sub(r"[\s-]+", "_", t)
    return t if t in TIPOS else None

def carpeta_vuelo(v):
    c = os.path.abspath(v) if os.path.isdir(v) else next((c for c in rutas.carpetas() if os.path.basename(c) == v), None)
    if not c: raise SystemExit(f"No existe el vuelo: {v}")
    return c

@lru_cache(None)
def fps(ruta):
    q = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", ruta], capture_output=True, text=True)
    m = re.match(r"(\d+)/(\d+)", q.stdout.strip())
    if not m or not int(m[2]): raise ValueError("no se puede leer el video " + os.path.basename(ruta))
    return int(m[1]) / int(m[2])

def cuadro(carpeta, imagen):
    """(video, numero de cuadro) segun como extrae cada importador. Una foto suelta devuelve (imagen, 0)."""
    base = os.path.splitext(imagen)[0]
    for rx, f450 in ((r"(.+)_(\d{5})s$", False), (r"(.+)_(\d{4})$", True)):
        m = re.match(rx, base)
        if not m: continue
        v = next((m[1] + e for e in (".MP4", ".mp4", ".MOV") if os.path.exists(os.path.join(carpeta, "video", m[1] + e))), None)
        if not v: continue
        f = fps(os.path.join(carpeta, "video", v))
        if not f450: return v, math.ceil(int(m[2]) * f - 1e-4)          # drones._fotogramas
        try:
            with open(os.path.join(carpeta, "mision.json"), encoding="utf-8") as h: paso = float(json.load(h).get("intervalo") or 1)
        except (OSError, ValueError): paso = 1.0
        return v, (int(m[2]) - 1) * max(1, round(f * paso))             # dividir_video_en_imagenes_dji
    if re.match(r".+_(\d{5})s$", base): raise ValueError("falta el video de la imagen")
    return imagen, 0

def datos_imagenes(carpeta, nombres=None):
    d = os.path.join(carpeta, "fotos"); nombres = sorted(nombres or [n for n in os.listdir(d) if n.lower().endswith((".jpg", ".jpeg"))])
    r = {}
    for i in range(0, len(nombres), 500):
        fs = [os.path.join(d, n) for n in nombres[i:i + 500]]
        q = subprocess.run(["exiftool", "-json", "-n", "-q", "-DateTimeOriginal", "-GPSLatitude", "-GPSLongitude", "-RelativeAltitude", "-AbsoluteAltitude",
                            "-FlightYawDegree", "-GimbalPitchDegree", "-GimbalYawDegree", "-ImageWidth", "-ImageHeight", "-Model", *fs], capture_output=True, text=True)
        for x in json.loads(q.stdout or "[]"): r[os.path.basename(x["SourceFile"])] = x
    return r

COLS = ["id", "vuelo", "dron", "imagen", "video", "cuadro", "fecha", "hora", "latitud", "longitud", "altura_relativa", "altura_msl", "rumbo_dron", "gimbal_pitch", "gimbal_yaw", "ancho", "alto"]
EXIF = ["GPSLatitude", "GPSLongitude", "RelativeAltitude", "AbsoluteAltitude", "FlightYawDegree", "GimbalPitchDegree", "GimbalYawDegree", "ImageWidth", "ImageHeight"]

def _num(v):
    try: v = float(v)
    except (TypeError, ValueError): return None
    return int(v) if v.is_integer() and abs(v) > 999 else v

def filas(carpeta):
    vuelo, dron, r = os.path.basename(carpeta), os.path.basename(os.path.dirname(carpeta)), []
    for nom, x in sorted(datos_imagenes(carpeta).items()):
        try: v, c = cuadro(carpeta, nom)
        except ValueError: v, c = None, None
        f, _, t = str(x.get("DateTimeOriginal", "")).partition(" ")
        e = [_num(x.get(k)) for k in EXIF]
        if dron == "dji_mini2se": e[3] = None                     # su video no graba altura sobre el mar
        r.append(dict(zip(COLS, [f"{vuelo}__{os.path.splitext(nom)[0]}", vuelo, dron, nom, v, c, f.replace(":", "-"), t[:8], *e])))
    return r

def _csv(h, fs):
    w = csv.DictWriter(h, COLS); w.writeheader(); w.writerows({k: "" if v is None else v for k, v in f.items()} for f in fs)

def imagenes(carpeta):
    fs = filas(carpeta); dest = os.path.join(carpeta, "imagenes.csv")
    with open(dest, "w", newline="", encoding="utf-8") as h: _csv(h, fs)
    return dest, len(fs)

LEEME = """Imagenes del vuelo a resolucion original, sin recomprimir, una carpeta 'imagenes' y sus datos en imagenes.csv / imagenes.json.
latitud, longitud: posicion del DRON (WGS84, grados decimales), no la del objeto que se ve en la imagen.
fecha y hora: hora de Uruguay (UTC-3). altura_relativa: metros sobre el despegue, NO sobre el suelo (puede ser negativa).
altura_msl: metros sobre el mar; vacia si el dron no la graba. rumbo_dron, gimbal_*: grados.
Precision: Mini 2 SE redondea la posicion a 4 decimales (unos 11 m). Los demas, GPS sin RTK (metros, sin medir).
F450: gimbal_pitch -90 es el montaje (camara fija hacia abajo), no una medicion. Las imagenes pueden venir rotadas segun la GoPro.
Cada ZIP se abre solo: su imagenes.csv describe las imagenes que contiene. Las imagenes sin GPS no se incluyen.
"""
MAX_PAQ = 2_000_000_000

def paquete(carpeta, salida=SALIDA, tope=MAX_PAQ):
    vuelo = os.path.basename(carpeta); fs = filas(carpeta); con = [f for f in fs if f["latitud"] is not None and f["longitud"] is not None and (f["latitud"] or f["longitud"])]
    partes, peso = [], 0
    for f in con:
        n = os.path.getsize(os.path.join(carpeta, "fotos", f["imagen"]))
        if not partes or peso + n > tope: partes.append([]); peso = 0
        partes[-1].append(f); peso += n
    os.makedirs(salida, exist_ok=True); zips = []
    for v in os.listdir(salida):
        if re.fullmatch(re.escape(vuelo) + r"_imagenes_\d{2}de\d{2}\.zip", v): os.remove(os.path.join(salida, v))
    for i, p in enumerate(partes, 1):
        z = os.path.join(salida, f"{vuelo}_imagenes_{i:02d}de{len(partes):02d}.zip")
        with zipfile.ZipFile(z + ".part", "w", zipfile.ZIP_STORED) as h:
            b = io.StringIO(newline=""); _csv(b, p); h.writestr("imagenes.csv", b.getvalue())
            h.writestr("imagenes.json", json.dumps(p, ensure_ascii=False, indent=1)); h.writestr("LEEME.txt", LEEME)
            for f in p: h.write(os.path.join(carpeta, "fotos", f["imagen"]), "imagenes/" + f["imagen"])
        os.replace(z + ".part", z); zips.append(z)
    return zips, len(con), len(fs) - len(con)

def validar(r):
    """Reglas de AnTrack. Devuelve el motivo de rechazo o None."""
    if not r["unique_id"] or len(r["unique_id"]) > 100: return "unique_id vacio o mayor a 100 caracteres"
    if not r["original_filename"] or len(r["original_filename"]) > 255: return "original_filename vacio o largo"
    try: t = datetime.strptime(r["file_date"] + r["file_time"], "%Y-%m-%d%H:%M:%S")
    except ValueError: return "fecha u hora invalida"
    if t > datetime.now() or t.year < 2000: return "fecha del futuro o anterior a 2000"
    if type(r["detection_frame"]) is not int or r["detection_frame"] < 0: return "cuadro invalido"
    if not tipo(r["detection_class"]): return "tipo no aceptado por AnTrack"
    if not 0 <= r["confidence_level"] <= 1: return "confianza fuera de 0 a 1"
    lo, la, al = r["geometry"]["coordinates"]
    if not all(map(math.isfinite, (lo, la, al))) or abs(la) > 90 or abs(lo) > 180 or (la == 0 and lo == 0): return "coordenadas invalidas"

def png(ruta, d):
    """Cuadro completo a resolucion original con el recuadro. Si pasa de 10 MB, recorte alrededor de la deteccion SIN reducir pixeles."""
    with Image.open(ruta) as o: im = o.convert("RGB")
    W, H = im.size; x, y, a, b = d["x"], d["y"], d["ancho"], d["alto"]
    if not (a > 0 and b > 0 and 0 <= x <= W and 0 <= y <= H): raise ValueError("recuadro fuera de la imagen")
    g = max(3, W // 800)
    ImageDraw.Draw(im).rectangle([max(0, x - a / 2), max(0, y - b / 2), min(W - 1, x + a / 2), min(H - 1, y + b / 2)], outline=(255, 0, 0), width=g)
    k = 1.0
    while True:
        w, h = int(W * k), int(H * k)
        if k < 1 and (w < min(W, a + 4 * g) or h < min(H, b + 4 * g)): raise ValueError("el recuadro no entra en un PNG de 10 MB sin reducir resolucion")
        x0, y0 = int(min(max(0, x - w / 2), W - w)), int(min(max(0, y - h / 2), H - h))
        s = io.BytesIO(); (im if k == 1 else im.crop((x0, y0, x0 + w, y0 + h))).save(s, "PNG", compress_level=6)
        if s.tell() <= MAX_PNG: return s.getvalue(), k < 1
        k = min(k * .95, k * math.sqrt(MAX_PNG / s.tell()) * .97)

def _leer(carpeta):
    with open(os.path.join(carpeta, "detecciones.json"), encoding="utf-8") as h: l = json.load(h)
    if not isinstance(l, list): raise SystemExit("detecciones.json debe ser una lista.")
    r = []
    for i, d in enumerate(l, 1):
        try: r.append({"n": i, "imagen": os.path.basename(str(d["imagen"])), "clase": d.get("clase", d.get("class")), "confianza": float(d.get("confianza", d.get("confidence"))),
                       "x": float(d["x"]), "y": float(d["y"]), "ancho": float(d.get("ancho", d.get("width"))), "alto": float(d.get("alto", d.get("height")))})
        except (KeyError, TypeError, ValueError, AttributeError): r.append({"n": i, "imagen": str(d.get("imagen", "")) if isinstance(d, dict) else "", "error": "faltan campos o no son numeros"})
    return r

def exportar(carpeta, salida=SALIDA):
    dets = _leer(carpeta); vuelo = os.path.basename(carpeta); os.makedirs(salida, exist_ok=True)
    ex = [n for n in {d["imagen"] for d in dets} if n and os.path.exists(os.path.join(carpeta, "fotos", n))]
    meta = datos_imagenes(carpeta, ex) if ex else {}
    dron = re.sub(r"\W", "", os.path.basename(os.path.dirname(carpeta))); veces, inf, zips, z, peso = {}, [], [], None, 0
    for viejo in os.listdir(salida):
        if re.fullmatch(re.escape(vuelo) + r"_\d{2}\.zip", viejo): os.remove(os.path.join(salida, viejo))
    try:
        for d in sorted(dets, key=lambda q: (q["imagen"], q.get("x", 0), q.get("y", 0))):
            uid, nota = "", ""
            try:
                if d.get("error"): raise ValueError(d["error"])
                m = meta.get(d["imagen"])
                if not m: raise ValueError("no existe la imagen")
                if m.get("GPSLatitude") is None or m.get("RelativeAltitude") is None: raise ValueError("imagen sin GPS o sin altura")
                v, c = cuadro(carpeta, d["imagen"]); f, _, t = str(m.get("DateTimeOriginal", "")).partition(" ")
                f, t = f.replace(":", "-"), t[:8]; b = os.path.splitext(d["imagen"])[0] if v == d["imagen"] else os.path.splitext(v)[0]
                uid = re.sub(r"[^\w-]", "", f"{dron}_{b}_{f.replace('-', '')}_{t.replace(':', '')}_f{c}")
                veces[uid] = veces.get(uid, 0) + 1
                if veces[uid] > 1: uid += f"_d{veces[uid]}"
                r = {"unique_id": uid, "original_filename": v, "file_date": f, "file_time": t, "detection_frame": c, "detection_class": tipo(d["clase"]) or str(d["clase"]),
                     "confidence_level": d["confianza"], "geometry": {"type": "Point", "coordinates": [round(float(m["GPSLongitude"]), 8), round(float(m["GPSLatitude"]), 8), round(float(m["RelativeAltitude"]), 2)]}}
                e = validar(r)
                if e: raise ValueError(e)
                img, rec = png(os.path.join(carpeta, "fotos", d["imagen"]), d); nota = "recorte a resolucion original" if rec else "cuadro completo"
                j = json.dumps(r, ensure_ascii=False, indent=2).encode(); n = len(img) + len(j) + 1000
                if z is None or peso + n > MAX_ZIP or len(z.namelist()) + 2 > MAX_ARCH:
                    if z: z.close()
                    zips.append(os.path.join(salida, f"{vuelo}_{len(zips) + 1:02d}.zip")); z, peso = zipfile.ZipFile(zips[-1], "w", zipfile.ZIP_STORED), 0
                z.writestr(uid + ".json", j); z.writestr(uid + ".png", img); peso += n
                inf.append([d["n"], d["imagen"], uid, "ACEPTADA", nota])
            except (ValueError, OSError) as e: inf.append([d["n"], d["imagen"], uid, "RECHAZADA", str(e)])
    finally:
        if z: z.close()
    with open(os.path.join(salida, vuelo + "_informe.csv"), "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h); w.writerow(["deteccion", "imagen", "unique_id", "resultado", "detalle"]); w.writerows(sorted(inf))
    return zips, inf

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("imagenes", "exportar", "paquete"): raise SystemExit(__doc__)
    if sys.argv[1] == "paquete":
        for c in (rutas.carpetas() if sys.argv[2] == "todos" else [carpeta_vuelo(sys.argv[2])]):
            if os.path.isdir(os.path.join(c, "fotos")): z, n, s = paquete(c, *sys.argv[3:4]); print(os.path.basename(c), f"{n} imagenes, {s} sin GPS, {len(z)} ZIP", flush=True)
        raise SystemExit
    c = carpeta_vuelo(sys.argv[2])
    if sys.argv[1] == "imagenes": print(*imagenes(c), "imagenes")
    else:
        zs, inf = exportar(c, *sys.argv[3:4]); print(*zs, sep="\n"); print(sum(i[3] == "ACEPTADA" for i in inf), "aceptadas,", sum(i[3] != "ACEPTADA" for i in inf), "rechazadas")
