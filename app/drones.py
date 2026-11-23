#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perfiles de dron intercambiables, importacion de medios DJI, tramos por bateria, KMZ y reanudacion.
Nunca escribe en la tarjeta del dron ni envia ordenes de vuelo a un DJI."""
import os, re, io, csv, glob, json, math, time, shutil, zipfile, threading, subprocess
from datetime import datetime, timezone, timedelta
import rutas
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

BASE = os.path.dirname(os.path.abspath(__file__))
VUELOS, PLANES = rutas.VUELOS, rutas.PLANES
PROGRESO = os.path.join(PLANES, ".progreso.json")
router = APIRouter()
_DJI = {"alt_min": 5.0, "alt_max": 60.0, "vel_min": 0.5, "vel_ref": 2.0, "vel_max": 8.0, "radio_max": 500.0,
        "tramo_max": 300.0, "wp_max": 200, "min_max": 180.0}
PERFILES = {
    "f450": {"nombre": "F450 + Pixhawk (GoPro)", "carga": "mavlink", "camara": "GoPro", "bateria_min": 6, "vels": [0.4, 0.6, 0.8],
             "nota": "El plan se carga y verifica por radio."},
    "mini2se": {"nombre": "DJI Mini 2 SE", "carga": "manual", "camara": "propia", "bateria_min": 18, "vels": [1, 2, 3, 5], "lim": _DJI,
                "nota": "DJI no ofrece carga de waypoints para este modelo: el plan es guia para vuelo manual."},
    "mini5pro": {"nombre": "DJI Mini 5 Pro", "carga": "kmz", "camara": "propia", "bateria_min": 22, "vels": [1, 2, 3, 5], "lim": _DJI,
                 "nota": "El plan se exporta en KMZ y se vuela con DJI Fly."},
}

def limites(dron, base):
    return {**base, **PERFILES[dron].get("lim", {})}

def dist(a, b):
    r = math.radians
    h = math.sin(r(b[0] - a[0]) / 2) ** 2 + math.cos(r(a[0])) * math.cos(r(b[0])) * math.sin(r(b[1] - a[1]) / 2) ** 2
    return 12742000 * math.asin(math.sqrt(min(1, h)))

# ---------- hardware ----------
def usb_dji():
    r = []
    for d in glob.glob("/sys/bus/usb/devices/*/idVendor"):
        b = os.path.dirname(d)
        lee = lambda n: open(os.path.join(b, n)).read().strip() if os.path.exists(os.path.join(b, n)) else ""
        v, p = lee("idVendor"), lee("idProduct")
        if v == "2ca3": r.append({"tipo": "control" if p == "1020" else "dron", "id": f"{v}:{p}", "nombre": lee("product")})
        elif (v, p) == ("070a", "4026"): r.append({"tipo": "dron (modo almacenamiento)", "id": f"{v}:{p}", "nombre": lee("product")})
    return r

def tarjetas():
    return sorted({os.path.dirname(os.path.dirname(p)) for pat in ("/media/*/*/DCIM/*MEDIA", "/media/*/*/DCIM/DJI*") for p in glob.glob(pat)})

def _tarjeta(t):
    if t not in tarjetas(): raise HTTPException(404, "No se encuentra la tarjeta del dron.")
    return t

def _utc(x, es_video, desfase_h):
    f = datetime.strptime(x["CreateDate" if es_video else "DateTimeOriginal"][:19], "%Y:%m:%d %H:%M:%S")
    return (f if es_video else f - timedelta(hours=desfase_h)).replace(tzinfo=timezone.utc)

def _desfase():
    return datetime.now().astimezone().utcoffset().total_seconds() / 3600

def listar_medios(t):
    fs = [f for e in ("MP4", "JPG", "mp4", "jpg") for f in glob.glob(os.path.join(t, "DCIM", "*", "*." + e))]
    if not fs: return []
    q = subprocess.run(["exiftool", "-api", "largefilesupport=1", "-json", "-n", "-q", "-Model", "-CreateDate", "-DateTimeOriginal",
                        "-Duration", "-GPSLatitude", "-GPSLongitude", *fs], capture_output=True, text=True)
    r = []
    for x in json.loads(q.stdout or "[]"):
        v = x["SourceFile"].lower().endswith(".mp4")
        try: h = _utc(x, v, _desfase())
        except (KeyError, ValueError): continue
        r.append({"archivo": os.path.relpath(x["SourceFile"], t), "tipo": "video" if v else "foto", "utc": h.timestamp(),
                  "dur": x.get("Duration"), "mb": round(os.path.getsize(x["SourceFile"]) / 1e6, 1), "modelo": x.get("Model", "")})
    return sorted(r, key=lambda z: z["utc"])

MODELOS = {"FC7503": "mini2se"}
NUM = r"(-?\d+(?:\.\d+)?)"
SUB = re.compile(r"GPS\s*\(\s*" + NUM + r",\s*" + NUM + r",\s*" + NUM + r"\s*\),\s*D\s*" + NUM + r"m,\s*H\s*" + NUM + r"m,\s*H\.S\s*" + NUM + r"m/s")
CAM = re.compile(r"F/([\d.]+), SS ([\d.]+), ISO (\d+)")

def telemetria_video(ruta):
    """Subtitulos que el dron graba dentro del MP4, uno por segundo. Coordenadas con 4 decimales (unos 11 m)."""
    q = subprocess.run(["exiftool", "-api", "largefilesupport=1", "-ee", "-n", "-q", "-p", "$SampleTime|$Text", ruta], capture_output=True, text=True)
    r = []
    for l in q.stdout.splitlines():
        a, _, txt = l.partition("|"); m = SUB.search(txt)
        if not m: continue
        lon, lat, _, d, h, v = map(float, m.groups())
        try: r.append({"s": float(a), "lat": lat, "lon": lon, "alt": h, "vel": v, "casa": d, "gps": bool(lat or lon),
                        "cam": (lambda c: c and [float(g) for g in c.groups()])(CAM.search(txt))})
        except ValueError: continue
    return r

CAB = ["timestamp_utc", "latitud", "longitud", "altitud_msl", "altitud_relativa", "alabeo_roll", "cabeceo_pitch", "rumbo_yaw",
       "velocidad_ms", "satelites", "voltaje_bateria", "modo_vuelo"]
tarea = {"activa": False, "msg": "", "pct": 0, "vuelo": None, "error": None}

def _fotogramas(ruta, tel, ini, destino, cada):
    import cv2
    q = json.loads(subprocess.run(["exiftool", "-api", "largefilesupport=1", "-json", "-n", "-q", "-Model", "-CameraPitch", "-Comment", ruta], capture_output=True, text=True).stdout)[0]
    sn = re.search(r"SN=(\w+)", str(q.get("Comment", "")))
    fijos = {"Make": "DJI", "Model": q.get("Model", "")}
    if sn: fijos["SerialNumber"] = sn.group(1)
    if q.get("Model") == "FC7503": fijos["FocalLength"] = 4.5
    if q.get("CameraPitch") not in (None, ""): fijos["XMP-drone-dji:GimbalPitchDegree"] = f"{float(q['CameraPitch']):+.2f}"
    cap = cv2.VideoCapture(ruta); fps = cap.get(cv2.CAP_PROP_FPS) or 25; filas, i, prox = [], 0, 0.0
    base = os.path.splitext(os.path.basename(ruta))[0]
    while cap.grab():
        s = i / fps; i += 1
        if s + 1e-6 < prox: continue
        prox += cada
        ok, im = cap.retrieve()
        if not ok: continue
        n = f"{base}_{int(s):05d}s.JPG"; cv2.imwrite(os.path.join(destino, n), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
        p = min(tel, key=lambda q: abs(q["s"] - s), default=None)
        f = (ini + timedelta(seconds=s)).astimezone()
        x = {"SourceFile": n, "DateTimeOriginal": f.strftime("%Y:%m:%d %H:%M:%S"), "SubSecTimeOriginal": f"{f.microsecond // 1000:03d}",
             "OffsetTimeOriginal": f.strftime("%z")[:3] + ":" + f.strftime("%z")[3:], **fijos,
             "ImageDescription": f"Fotograma de {os.path.basename(ruta)} a {s:.2f} s. Posicion del video: 4 decimales (unos 11 m). GimbalPitch: el del inicio del video."}
        if p and p["cam"] and abs(p["s"] - s) <= 1.5:
            x.update(FNumber=p["cam"][0], ExposureTime=1 / p["cam"][1] if p["cam"][1] else 0, ISO=int(p["cam"][2]))
        if p and p["gps"] and abs(p["s"] - s) <= 1.5:
            x.update(GPSLatitude=abs(p["lat"]), GPSLatitudeRef="S" if p["lat"] < 0 else "N", GPSLongitude=abs(p["lon"]),
                     GPSLongitudeRef="W" if p["lon"] < 0 else "E", GPSHPositioningError=8,
                     GPSDateStamp=(ini + timedelta(seconds=s)).strftime("%Y:%m:%d"), GPSTimeStamp=(ini + timedelta(seconds=s)).strftime("%H:%M:%S"))
            x["XMP-drone-dji:RelativeAltitude"] = f"{p['alt']:+.2f}"
        filas.append(x)
    cap.release()
    if not filas: raise RuntimeError(f"{base}: no se pudo leer el video.")
    j = os.path.join(destino, "_tags.json")
    with open(j, "w") as f: json.dump([{**x, "SourceFile": os.path.join(destino, x["SourceFile"])} for x in filas], f)
    q = subprocess.run(["exiftool", "-q", "-m", "-n", "-overwrite_original", "-json=" + j, *[os.path.join(destino, x["SourceFile"]) for x in filas]], capture_output=True, text=True)
    os.remove(j)
    if q.returncode: raise RuntimeError("exiftool: " + q.stderr[:200])
    return len(filas), sum("GPSLatitude" in x for x in filas)

def _importar(t, arch, nombre, cada, copiar):
    carpeta = None
    try:
        med = [m for m in listar_medios(t) if m["archivo"] in set(arch)]
        if not med: raise RuntimeError("Ningun archivo valido.")
        ini = datetime.fromtimestamp(med[0]["utc"])
        carpeta = os.path.join(VUELOS, "dji_" + re.sub(r"\W", "", MODELOS.get(med[0]["modelo"], med[0]["modelo"]) or "otro"), f"{nombre}_{ini:%Y%m%d_%H%M%S}")
        if os.path.exists(os.path.join(carpeta, "telemetria.csv")): raise RuntimeError("Ese vuelo ya fue importado: " + os.path.basename(carpeta))
        fd, vd = os.path.join(carpeta, "fotos"), os.path.join(carpeta, "video")
        os.makedirs(fd, exist_ok=True); os.makedirs(vd, exist_ok=True)
        filas, sin, nf, ng = [], 0, 0, 0
        for k, m in enumerate(med):
            tarea.update(pct=int(100 * k / len(med)), msg=f"{m['archivo']} ({k + 1}/{len(med)})")
            src = os.path.join(t, m["archivo"]); u = datetime.fromtimestamp(m["utc"], timezone.utc)
            if m["tipo"] == "foto":
                dst = os.path.join(fd, os.path.basename(src)); shutil.copy2(src, dst + ".part"); os.replace(dst + ".part", dst)
                q = json.loads(subprocess.run(["exiftool", "-json", "-n", "-GPSLatitude", "-GPSLongitude", "-GPSAltitude", "-RelativeAltitude",
                    "-FlightYawDegree", dst], capture_output=True, text=True).stdout)[0]
                nf += 1
                if q.get("GPSLatitude"):
                    ng += 1; filas.append([u, q["GPSLatitude"], q["GPSLongitude"], float(q.get("GPSAltitude", 0)), float(q.get("RelativeAltitude", 0)), float(q.get("FlightYawDegree", 0)), 0, "FOTO"])
                continue
            tel = telemetria_video(src)
            for p in tel:
                if p["gps"]: filas.append([u + timedelta(seconds=p["s"]), p["lat"], p["lon"], 0, p["alt"], 0, p["vel"], "VIDEO"])
                else: sin += 1
            if cada > 0:
                a, b = _fotogramas(src, tel, u, fd, cada); nf += a; ng += b
            if copiar:
                dst = os.path.join(vd, os.path.basename(src))
                if not (os.path.exists(dst) and os.path.getsize(dst) == os.path.getsize(src)):
                    shutil.copy2(src, dst + ".part"); os.replace(dst + ".part", dst)
        filas.sort(key=lambda f: f[0])
        with open(os.path.join(carpeta, "telemetria.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(CAB)
            for h, la, lo, am, al, yw, v, o in filas:
                w.writerow([h.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3], f"{la:.7f}", f"{lo:.7f}", f"{am:.2f}", f"{al:.2f}", "0.00", "0.00", f"{yw:.2f}", f"{v:.2f}", 0, "0.00", o])
        with open(os.path.join(carpeta, "dron.json"), "w") as f:
            json.dump({"dron": MODELOS.get(med[0]["modelo"], med[0]["modelo"]), "camara": med[0]["modelo"], "archivos": [m["archivo"] for m in med],
                       "precision_video_m": 11}, f, indent=1)
        tarea.update(vuelo=os.path.basename(carpeta), pct=100, msg=f"{len(filas)} posiciones, {nf} imagenes ({ng} con GPS), {sin} segundos de video sin GPS.")
    except Exception as e:
        tarea.update(error=str(e), msg="Error: " + str(e))
    finally: tarea["activa"] = False

# ---------- plan ----------
def _mins(w, vel, casa):
    """Minutos de un tramo completo: despegue, ida, recorrido, esperas y regreso."""
    pts = [casa] + [(x["lat"], x["lon"]) for x in w] + [casa]
    alts = [0] + [x["alt"] for x in w] + [0]
    return (sum(dist(a, b) for a, b in zip(pts, pts[1:])) / max(vel, .1) + sum(abs(b - a) for a, b in zip(alts, alts[1:]))
            + sum(x["espera"] for x in w) + 30) / 60

def tramos(w, vel, casa, minutos):
    out, i = [], 0
    while i < len(w):
        j = i
        while j < len(w) and _mins(w[i:j + 1], vel, casa) <= minutos: j += 1
        if j == i: raise HTTPException(400, f"WP{i + 1} no entra en una bateria con el regreso incluido.")
        if out and j - i == 1 and j < len(w): raise HTTPException(400, f"Con esta bateria no se avanza despues del WP{i + 1}: suba la velocidad o acerque el despegue.")
        out.append((i, j))
        if j >= len(w): break
        i = j - 1                    # se repite el ultimo punto para no dejar huecos
    return out

FIN_DJI = {"RTL": "goHome", "LAND": "autoLand", "LOITER": "noAction"}

def kmz(w, vel, fin, media, info=None):
    info = info or "<wpml:droneInfo><wpml:droneEnumValue>68</wpml:droneEnumValue><wpml:droneSubEnumValue>0</wpml:droneSubEnumValue></wpml:droneInfo>"
    cfg = ("<wpml:missionConfig><wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>"
           f"<wpml:finishAction>{FIN_DJI[fin]}</wpml:finishAction><wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>"
           "<wpml:executeRCLostAction>goBack</wpml:executeRCLostAction>"
           f"<wpml:globalTransitionalSpeed>{vel}</wpml:globalTransitionalSpeed>{info}</wpml:missionConfig>")
    act = lambda n, f, p: f"<wpml:action><wpml:actionId>{n}</wpml:actionId><wpml:actionActuatorFunc>{f}</wpml:actionActuatorFunc><wpml:actionActuatorFuncParam>{p}</wpml:actionActuatorFuncParam></wpml:action>"
    pay = "<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>"
    pl, total = "", sum(dist((a["lat"], a["lon"]), (b["lat"], b["lon"])) for a, b in zip(w, w[1:]))
    for i, x in enumerate(w):
        ac = []
        if i == 0: ac.append(("gimbalRotate", "<wpml:gimbalRotateMode>absoluteAngle</wpml:gimbalRotateMode><wpml:gimbalPitchRotateEnable>1</wpml:gimbalPitchRotateEnable><wpml:gimbalPitchRotateAngle>-90</wpml:gimbalPitchRotateAngle><wpml:gimbalRollRotateEnable>0</wpml:gimbalRollRotateEnable><wpml:gimbalRollRotateAngle>0</wpml:gimbalRollRotateAngle><wpml:gimbalYawRotateEnable>0</wpml:gimbalYawRotateEnable><wpml:gimbalYawRotateAngle>0</wpml:gimbalYawRotateAngle><wpml:gimbalRotateTimeEnable>0</wpml:gimbalRotateTimeEnable><wpml:gimbalRotateTime>0</wpml:gimbalRotateTime>" + pay))
        if x["espera"]: ac.append(("hover", f"<wpml:hoverTime>{x['espera']}</wpml:hoverTime>"))
        if media == "foto": ac.append(("takePhoto", pay))
        if media == "video" and i == 0: ac.append(("startRecord", pay))
        if media == "video" and i == len(w) - 1: ac.append(("stopRecord", pay))
        g = ""
        if ac:
            g = (f"<wpml:actionGroup><wpml:actionGroupId>{i}</wpml:actionGroupId><wpml:actionGroupStartIndex>{i}</wpml:actionGroupStartIndex>"
                 f"<wpml:actionGroupEndIndex>{i}</wpml:actionGroupEndIndex><wpml:actionGroupMode>sequence</wpml:actionGroupMode>"
                 "<wpml:actionTrigger><wpml:actionTriggerType>reachPoint</wpml:actionTriggerType></wpml:actionTrigger>"
                 + "".join(act(n, f, p) for n, (f, p) in enumerate(ac)) + "</wpml:actionGroup>")
        pl += (f"<Placemark><Point><coordinates>{x['lon']:.8f},{x['lat']:.8f}</coordinates></Point><wpml:index>{i}</wpml:index>"
               f"<wpml:executeHeight>{x['alt']}</wpml:executeHeight><wpml:waypointSpeed>{vel}</wpml:waypointSpeed>"
               "<wpml:waypointHeadingParam><wpml:waypointHeadingMode>followWayline</wpml:waypointHeadingMode><wpml:waypointHeadingAngle>0</wpml:waypointHeadingAngle><wpml:waypointHeadingPathMode>followBadArc</wpml:waypointHeadingPathMode></wpml:waypointHeadingParam>"
               "<wpml:waypointTurnParam><wpml:waypointTurnMode>toPointAndStopWithDiscontinuityCurvature</wpml:waypointTurnMode><wpml:waypointTurnDampingDist>0</wpml:waypointTurnDampingDist></wpml:waypointTurnParam>"
               f"<wpml:useStraightLine>1</wpml:useStraightLine>{g}</Placemark>")
    cab = '<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/1.0.2"><Document>'
    ms = int(time.time() * 1000)
    tpl = f"{cab}<wpml:author>hormigas</wpml:author><wpml:createTime>{ms}</wpml:createTime><wpml:updateTime>{ms}</wpml:updateTime>{cfg}</Document></kml>"
    way = (f"{cab}{cfg}<Folder><wpml:templateId>0</wpml:templateId><wpml:executeHeightMode>relativeToStartPoint</wpml:executeHeightMode><wpml:waylineId>0</wpml:waylineId>"
           f"<wpml:distance>{total:.1f}</wpml:distance><wpml:duration>{total / vel:.1f}</wpml:duration><wpml:autoFlightSpeed>{vel}</wpml:autoFlightSpeed>{pl}</Folder></Document></kml>")
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z: z.writestr("wpmz/template.kml", tpl); z.writestr("wpmz/waylines.wpml", way)
    return b.getvalue()

def _casa(d, p):
    c = d.get("casa")
    if not c: return (p["wps"][0]["lat"], p["wps"][0]["lon"])
    try: c = (float(c[0]), float(c[1]))
    except (TypeError, ValueError, IndexError): raise HTTPException(400, "Punto de despegue invalido.")
    if not (abs(c[0]) <= 90 and abs(c[1]) <= 180): raise HTTPException(400, "Punto de despegue invalido.")
    return c

def _preparar(d):
    import plan_vuelo as pv
    p = pv.normalizar(d)
    if not p["wps"]: raise HTTPException(400, "El plan esta vacio.")
    if p["dron"] == "f450": raise HTTPException(400, "Use Cargar y verificar para la Pixhawk.")
    casa = _casa(d, p); e = pv.validar(p, casa)["errores"]
    if e: raise HTTPException(400, " ".join(e))
    try: mn = float(d.get("bateria") or PERFILES[p["dron"]]["bateria_min"])
    except (TypeError, ValueError): raise HTTPException(400, "Minutos de bateria invalidos.")
    if not 3 <= mn <= 30: raise HTTPException(400, "Minutos utiles por bateria: de 3 a 30.")
    return p, casa, tramos(p["wps"], p["vel"], casa, mn)

def _guardia(x):
    if x != "1": raise HTTPException(403, "Solicitud no permitida.")

@router.get("/api/drones")
def api_drones():
    import plan_vuelo as pv
    return {k: {**{a: b for a, b in v.items() if a != "lim"}, "lim": limites(k, pv.LIM)} for k, v in PERFILES.items()}

@router.get("/api/drones/hardware")
def api_hw(): return {"usb": usb_dji(), "tarjetas": tarjetas()}

@router.get("/api/drones/medios")
def api_medios(t: str): return listar_medios(_tarjeta(t))

@router.post("/api/drones/importar")
def api_importar(d: dict, x_hormigas: str = Header("")):
    _guardia(x_hormigas); t = _tarjeta(d.get("tarjeta")); n = str(d.get("nombre", ""))
    if not re.fullmatch(r"[\w-]{1,40}", n): raise HTTPException(400, "Nombre: solo letras, numeros, - y _.")
    try: cada = float(d.get("cada", 2))
    except (TypeError, ValueError): raise HTTPException(400, "Intervalo invalido.")
    if cada != 0 and not 0.5 <= cada <= 60: raise HTTPException(400, "Intervalo: 0 (sin fotogramas) o de 0,5 a 60 s.")
    if not isinstance(d.get("archivos"), list) or not d["archivos"]: raise HTTPException(400, "Elija al menos un archivo.")
    if tarea["activa"]: raise HTTPException(409, "Ya hay una importacion en curso.")
    tarea.update(activa=True, msg="Leyendo...", pct=0, vuelo=None, error=None)
    threading.Thread(target=_importar, args=(t, d["archivos"], n, cada, d.get("copiar") is True), daemon=True).start()
    return {"exito": True}

@router.get("/api/drones/tarea")
def api_tarea(): return tarea

@router.post("/api/drones/tramos")
def api_tramos(d: dict, x_hormigas: str = Header("")):
    _guardia(x_hormigas); p, casa, tr = _preparar(d)
    return [{"desde": a + 1, "hasta": b, "min": round(_mins(p["wps"][a:b], p["vel"], casa), 1)} for a, b in tr]

@router.post("/api/drones/kmz")
def api_kmz(d: dict, x_hormigas: str = Header("")):
    """Un KMZ por bateria. droneInfo se copia de una mision creada en DJI Fly si se adjunta."""
    _guardia(x_hormigas); p, _, tr = _preparar(d)
    if PERFILES[p["dron"]]["carga"] != "kmz": raise HTTPException(400, PERFILES[p["dron"]]["nota"])
    try: n = int(d.get("tramo", 1))
    except (TypeError, ValueError): raise HTTPException(400, "Tramo invalido.")
    if not 1 <= n <= len(tr): raise HTTPException(400, "Tramo inexistente.")
    info = d.get("info")
    if info is not None and not re.fullmatch(r"<wpml:droneInfo>\s*<wpml:droneEnumValue>\d{1,4}</wpml:droneEnumValue>\s*(<wpml:droneSubEnumValue>\d{1,4}</wpml:droneSubEnumValue>\s*)?</wpml:droneInfo>", str(info)):
        raise HTTPException(400, "droneInfo no reconocido en el KMZ de DJI Fly.")
    a, b = tr[n - 1]
    if b - a < 2: raise HTTPException(400, "El tramo tiene un solo punto.")
    media = d.get("media") if d.get("media") in ("foto", "video") else "nada"
    return Response(kmz(p["wps"][a:b], p["vel"], "RTL", media, info), media_type="application/vnd.google-earth.kmz")

# ---------- reanudacion ----------
def guardar_progreso(st, cargado):
    """Se llama periodicamente en vuelo. Guarda el WP hacia el que iba en AUTO, aunque se cierre el programa."""
    s = st.wp_actual
    if not (st.en_grabacion and st.armado and st.modo_vuelo == "AUTO" and cargado["plan"] and isinstance(s, int) and s >= 3): return
    i = min(s - 3, len(cargado["plan"]["wps"]))
    d = {"plan": cargado["plan"], "id": cargado["id"], "hacia": i, "hora": datetime.now().strftime("%d/%m %H:%M:%S"), "lat": st.lat, "lon": st.lon}
    os.makedirs(PLANES, exist_ok=True)
    with open(PROGRESO + ".part", "w", encoding="utf-8") as f: json.dump(d, f)
    os.replace(PROGRESO + ".part", PROGRESO)

def vigilar(st, cargado):
    def bucle():
        while True:
            try: guardar_progreso(st, cargado)
            except Exception as e: print("progreso:", e)
            time.sleep(1)
    threading.Thread(target=bucle, daemon=True).start()

@router.get("/api/drones/progreso")
def api_progreso():
    try:
        with open(PROGRESO, encoding="utf-8") as f: d = json.load(f)
    except (OSError, ValueError): return None
    d["completo"] = d["hacia"] >= len(d["plan"]["wps"])
    return d

@router.post("/api/drones/cobertura")
def api_cobertura(d: dict, x_hormigas: str = Header("")):
    """Ultimo waypoint alcanzado EN ORDEN segun un vuelo ya importado. Es una sugerencia: el usuario confirma."""
    _guardia(x_hormigas)
    import plan_vuelo as pv, visor_vuelos as vv
    p = pv.normalizar(d); tel = vv.leer_telemetria(vv._carpeta(str(d.get("vuelo", ""))))
    r, i = (15.0 if any(q[7] == "VIDEO" for q in tel) else 5.0), 0
    for q in tel:
        if i < len(p["wps"]) and dist((q[1], q[2]), (p["wps"][i]["lat"], p["wps"][i]["lon"])) <= r: i += 1
    return {"alcanzados": i, "total": len(p["wps"]), "radio": r}
