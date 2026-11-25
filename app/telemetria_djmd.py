"""Telemetria que los DJI nuevos (probado: Mini 5 Pro, FC9313) graban en la pista 'djmd' del MP4 (protobuf, un registro por cuadro)."""
import json, math, struct, subprocess

def _var(b, i):
    r = s = 0
    while True:
        c = b[i]; i += 1; r |= (c & 127) << s; s += 7
        if c < 128: return (r - (1 << 64) if r >> 63 else r), i

def _campos(b):
    i, o = 0, {}
    while i < len(b):
        k, i = _var(b, i); f, w = k >> 3, k & 7
        if w == 0: v, i = _var(b, i)
        elif w == 1: v = struct.unpack("<d", b[i:i + 8])[0]; i += 8
        elif w == 5: v = struct.unpack("<f", b[i:i + 4])[0]; i += 4
        elif w == 2:
            n, i = _var(b, i); v = b[i:i + n]; i += n
            if len(v) < n: raise ValueError("pista djmd cortada")
        else: raise ValueError("pista djmd no reconocida")
        o.setdefault(f, []).append(v)
    return o

def _sub(b, *ruta):
    """Submensaje anidado como {campo: valor}; vacio si falta (protobuf omite los ceros)."""
    for f in ruta:
        b = _campos(b).get(f, [b""])[0]
    return {f: v[0] for f, v in _campos(b).items()}

def _pista(ruta):
    q = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=index,codec_tag_string", "-of", "json", ruta], capture_output=True, text=True)
    return next((s["index"] for s in json.loads(q.stdout or "{}").get("streams", []) if s.get("codec_tag_string") == "djmd"), None)

def _extraer(ruta, *lim):
    n = _pista(ruta)
    if n is None: return b""
    return subprocess.run(["ffmpeg", "-v", "error", *lim, "-i", ruta, "-map", f"0:{n}", "-c", "copy", "-f", "data", "-"], capture_output=True).stdout

def modelo(ruta):
    """'FC9313' o '' si el video no tiene esta pista."""
    try:
        b = _extraer(ruta, "-t", "0.1"); p = b.find(b"DJI FC")
        return b[p + 4:p + 10].decode("ascii") if p >= 0 else ""
    except (OSError, ValueError): return ""

def leer(ruta):
    """Un dato por segundo de video, mismo formato que drones.telemetria_video mas msl, actitud y gimbal."""
    b = _extraer(ruta)
    if not b: return []
    r, t0 = [], None
    for c in _campos(b).get(3, []):
        us = _sub(c, 1).get(2)
        if us is None: continue
        if t0 is None: t0 = us
        s = (us - t0) / 1e6
        if r and s - r[-1]["s"] < 0.99: continue
        pos, at, gi = _sub(c, 3, 4, 1), _sub(c, 3, 3), _sub(c, 4, 3)
        la, lo = pos.get(2, 0.0), pos.get(3, 0.0)
        r.append({"s": s, "lat": la, "lon": lo, "alt": _sub(c, 3, 5).get(1, 0) / 1000, "msl": _sub(c, 3, 4).get(2, 0) / 1000, "vel": 0.0,
                  "casa": None, "cam": None, "gps": bool(la or lo) and abs(la) <= 90 and abs(lo) <= 180,
                  "roll": at.get(1, 0) / 10, "pitch": at.get(2, 0) / 10, "yaw": at.get(3, 0) / 10,
                  "g_pitch": gi.get(1, 0) / 10, "g_roll": gi.get(2, 0) / 10, "g_yaw": gi.get(3, 0) / 10})
    for x, y in zip(r, r[1:]):
        if x["gps"] and y["gps"]:
            dn = (y["lat"] - x["lat"]) * 111320; de = (y["lon"] - x["lon"]) * 111320 * math.cos(math.radians(x["lat"]))
            y["vel"] = round(math.hypot(dn, de) / max(y["s"] - x["s"], .1), 2)
    return r
