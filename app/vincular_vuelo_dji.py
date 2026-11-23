#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Modulo 3: Vinculador de Telemetria a Formato Nativo DJI Mini 2 SE (Post-Vuelo)
Configuracion: GoPro HERO13 Black orientada hacia abajo (Nadir -90.0° con estabilizacion HyperSmooth propia).
Compatible con Windows y Ubuntu.
"""

import sys
import os
import time
import argparse
import subprocess
import shutil
import csv
from datetime import datetime, timezone, timedelta
import bisect
import re
import cv2
from pymavlink import mavutil

def obtener_ruta_exiftool():
    en_path = shutil.which("exiftool")
    if en_path:
        return en_path
    rutas_win = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\ExifTool\exiftool.exe"),
        r"C:\Program Files\ExifTool\exiftool.exe",
        r"C:\Program Files (x86)\ExifTool\exiftool.exe",
        os.path.join(os.path.dirname(__file__), "tools", "exiftool.exe")
    ]
    for r in rutas_win:
        if os.path.exists(r):
            return r
    return "exiftool"

EXIFTOOL_CMD = obtener_ruta_exiftool()
GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
LEAP_SECONDS = 18

class PuntoTelemetria:
    def __init__(self, timestamp_utc, lat, lon, alt_msl, rel_alt, roll=0.0, pitch=0.0, yaw=0.0, vx=0.0, vy=0.0, vz=0.0):
        self.timestamp = timestamp_utc  # float epoch seconds UTC
        self.lat = lat
        self.lon = lon
        self.alt_msl = alt_msl
        self.rel_alt = rel_alt
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.vx = vx
        self.vy = vy
        self.vz = vz

def gps_a_utc_epoch(semana_gps, ms_semana):
    t = GPS_EPOCH + timedelta(weeks=semana_gps, milliseconds=ms_semana) - timedelta(seconds=LEAP_SECONDS)
    return t.timestamp()

def cargar_desde_csv(ruta_csv):
    print(f"[*] Leyendo archivo CSV de telemetria: {ruta_csv}...")
    puntos = []
    with open(ruta_csv, "r", encoding="utf-8") as f:
        lector = csv.DictReader(f)
        for fila in lector:
            try:
                t_str = fila['timestamp_utc'].strip()
                dt = datetime.strptime(t_str, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
                
                lat = float(fila['latitud'])
                lon = float(fila['longitud'])
                alt_msl = float(fila['altitud_msl'])
                alt_rel = float(fila['altitud_relativa'])
                roll = float(fila.get('alabeo_roll', 0.0))
                pitch = float(fila.get('cabeceo_pitch', 0.0))
                yaw = float(fila.get('rumbo_yaw', 0.0))
                vel = float(fila.get('velocidad_ms', 0.0))
                if lat == 0.0 and lon == 0.0:
                    continue  # fila registrada antes de tener posicion GPS
                
                pt = PuntoTelemetria(
                    timestamp_utc=ts, lat=lat, lon=lon, alt_msl=alt_msl,
                    rel_alt=alt_rel, roll=roll, pitch=pitch, yaw=yaw, vx=vel
                )
                puntos.append(pt)
            except Exception:
                continue
    print(f"[+] Total de puntos de telemetria cargados: {len(puntos)}")
    return puntos

def cargar_desde_bin_o_tlog(ruta_log):
    print(f"[*] Analizando registro binario de vuelo: {ruta_log}...")
    try:
        mlog = mavutil.mavlink_connection(ruta_log)
    except Exception as e:
        print(f"[ERROR] No se pudo abrir el archivo de log: {e}")
        return []

    puntos = []
    home_alt = None
    c_roll, c_pitch, c_yaw = 0.0, 0.0, 0.0
    c_vx, c_vy, c_vz = 0.0, 0.0, 0.0
    c_rel_alt = 0.0
    offset_timeus_utc = None

    while True:
        msg = mlog.recv_msg()
        if msg is None:
            break
        mtype = msg.get_type()

        # DataFlash .BIN
        if mtype == 'ATT':
            c_roll = getattr(msg, 'Roll', 0.0)
            c_pitch = getattr(msg, 'Pitch', 0.0)
            c_yaw = getattr(msg, 'Yaw', 0.0)
        elif mtype in ('POS', 'XKF1'):
            if hasattr(msg, 'RelAlt'): c_rel_alt = getattr(msg, 'RelAlt', 0.0)
            if hasattr(msg, 'VN'):
                c_vx = getattr(msg, 'VN', 0.0)
                c_vy = getattr(msg, 'VE', 0.0)
                c_vz = getattr(msg, 'VD', 0.0)
        elif mtype == 'GPS':
            status = getattr(msg, 'Status', 0)
            if status >= 3:
                gwk = getattr(msg, 'GWk', 0)
                gms = getattr(msg, 'GMS', 0)
                time_us = getattr(msg, 'TimeUS', 0)
                lat = getattr(msg, 'Lat', 0.0)
                lon = getattr(msg, 'Lng', 0.0)
                alt = getattr(msg, 'Alt', 0.0)
                if gwk > 0 and gms > 0:
                    utc_ts = gps_a_utc_epoch(gwk, gms)
                    if time_us > 0 and offset_timeus_utc is None:
                        offset_timeus_utc = utc_ts - (time_us / 1e6)
                elif offset_timeus_utc is not None and time_us > 0:
                    utc_ts = offset_timeus_utc + (time_us / 1e6)
                else:
                    continue

                if home_alt is None: home_alt = alt
                rel_alt = c_rel_alt if c_rel_alt != 0.0 else (alt - home_alt)
                puntos.append(PuntoTelemetria(utc_ts, lat, lon, alt, rel_alt, c_roll, c_pitch, c_yaw, c_vx, c_vy, c_vz))

        # Telemetry .tlog
        elif mtype == 'GLOBAL_POSITION_INT':
            lat = msg.lat / 1e7
            lon = msg.lon / 1e7
            alt = msg.alt / 1000.0
            rel_alt = msg.relative_alt / 1000.0
            vx = msg.vx / 100.0
            vy = msg.vy / 100.0
            vz = msg.vz / 100.0
            utc_ts = getattr(msg, '_timestamp', 0)
            if utc_ts > 0 and lat != 0.0:
                puntos.append(PuntoTelemetria(utc_ts, lat, lon, alt, rel_alt, c_roll, c_pitch, c_yaw, vx, vy, vz))
        elif mtype == 'ATTITUDE':
            import math
            c_roll = math.degrees(msg.roll)
            c_pitch = math.degrees(msg.pitch)
            c_yaw = math.degrees(msg.yaw)

    print(f"[+] Total de puntos de GPS extraidos: {len(puntos)}")
    return puntos

def interpolar_telemetria(puntos, target_time):
    if not puntos:
        return None

    if isinstance(target_time, datetime):
        if target_time.tzinfo is None:
            target_ts = target_time.replace(tzinfo=timezone.utc).timestamp()
        else:
            target_ts = target_time.timestamp()
    elif isinstance(target_time, (int, float)):
        target_ts = float(target_time)
    else:
        return None

    tiempos = [p.timestamp for p in puntos]
    idx = bisect.bisect_left(tiempos, target_ts)
    if idx == 0: return puntos[0]
    if idx >= len(puntos): return puntos[-1]

    p0 = puntos[idx - 1]
    p1 = puntos[idx]
    dt_sec = p1.timestamp - p0.timestamp
    if dt_sec <= 0: return p0

    f = max(0.0, min(1.0, (target_ts - p0.timestamp) / dt_sec))
    return PuntoTelemetria(
        timestamp_utc=target_ts,
        lat=p0.lat + f * (p1.lat - p0.lat),
        lon=p0.lon + f * (p1.lon - p0.lon),
        alt_msl=p0.alt_msl + f * (p1.alt_msl - p0.alt_msl),
        rel_alt=p0.rel_alt + f * (p1.rel_alt - p0.rel_alt),
        roll=p0.roll + f * (p1.roll - p0.roll),
        pitch=p0.pitch + f * (p1.pitch - p0.pitch),
        yaw=(p0.yaw + f * (((p1.yaw - p0.yaw + 180.0) % 360.0) - 180.0)) % 360.0,
        vx=p0.vx + f * (p1.vx - p0.vx),
        vy=p0.vy + f * (p1.vy - p0.vy),
        vz=p0.vz + f * (p1.vz - p0.vz)
    )

def obtener_timestamp_imagen(ruta_img):
    cmd = [
        EXIFTOOL_CMD,
        "-s3",
        "-d", "%Y:%m:%d %H:%M:%S",
        "-DateTimeOriginal",
        "-SubSecTimeOriginal",
        ruta_img
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    lineas = res.stdout.strip().splitlines()
    if lineas and lineas[0]:
        try:
            dt_str = lineas[0].strip()
            subsec = 0.0
            if len(lineas) > 1 and lineas[1].strip().isdigit():
                subsec = float("0." + lineas[1].strip())
            dt = datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
            offset = -time.timezone if time.localtime().tm_isdst == 0 else -time.altzone
            local_tz = timezone(timedelta(seconds=offset))
            dt = dt.replace(tzinfo=local_tz)
            return dt.timestamp() + subsec
        except Exception:
            pass
    return os.path.getmtime(ruta_img)

def escribir_metadatos_dji(ruta_img, telem):
    """
    Inyecta metadatos EXIF y XMP en formato nativo DJI Mini 2 SE.
    La GoPro HERO13 cuenta con estabilizacion de horizonte propia (HyperSmooth):
    - GimbalRollDegree = 0.0 (Horizonte estabilizado por la camara)
    - GimbalPitchDegree = -90.0 (Alineada perpendicular hacia el suelo - Nadir)
    - GimbalYawDegree = Rumbo del dron
    - La actitud fisica del dron se registra en FlightRollDegree, FlightPitchDegree y FlightYawDegree.
    """
    lat_ref = "N" if telem.lat >= 0 else "S"
    lon_ref = "E" if telem.lon >= 0 else "W"

    cmd = [
        EXIFTOOL_CMD,
        "-overwrite_original",
        "-Make=DJI",
        "-Model=Mini 2 SE",
        f"-GPSLatitude={abs(telem.lat)}",
        f"-GPSLatitudeRef={lat_ref}",
        f"-GPSLongitude={abs(telem.lon)}",
        f"-GPSLongitudeRef={lon_ref}",
        f"-GPSAltitude={telem.alt_msl:.2f}",
        "-GPSAltitudeRef=0",
        "-GPSMapDatum=WGS-84",
        f"-XMP-drone-dji:AbsoluteAltitude={telem.alt_msl:+.2f}",
        f"-XMP-drone-dji:RelativeAltitude={telem.rel_alt:+.2f}",
        f"-XMP-drone-dji:FlightRollDegree={telem.roll:.1f}",
        f"-XMP-drone-dji:FlightPitchDegree={telem.pitch:.1f}",
        f"-XMP-drone-dji:FlightYawDegree={telem.yaw:.1f}",
        "-XMP-drone-dji:GimbalRollDegree=0.0",
        "-XMP-drone-dji:GimbalPitchDegree=-90.0",
        f"-XMP-drone-dji:GimbalYawDegree={telem.yaw:.1f}",
        f"-XMP-drone-dji:FlightXSpeed={telem.vx:.1f}",
        f"-XMP-drone-dji:FlightYSpeed={telem.vy:.1f}",
        f"-XMP-drone-dji:FlightZSpeed={telem.vz:.1f}",
        "-XMP-drone-dji:CamReverse=0",
        "-XMP-drone-dji:GimbalReverse=0",
        ruta_img
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0

def escribir_metadatos_dji_batch(metadatos_lista):
    """
    Escribe metadatos EXIF y XMP en formato nativo DJI Mini 2 SE en lote (batch)
    usando un archivo CSV temporal y una unica llamada a ExifTool (-csv=...).
    Es significativamente mas rapido para cientos o miles de fotografias.
    """
    if not metadatos_lista:
        return 0

    directorio_base = os.path.dirname(metadatos_lista[0][0])
    ruta_csv_temp = os.path.join(directorio_base, "_batch_dji_metadata.csv")

    encabezados = [
        "SourceFile", "Make", "Model",
        "GPSLatitude", "GPSLatitudeRef",
        "GPSLongitude", "GPSLongitudeRef",
        "GPSAltitude", "GPSAltitudeRef", "GPSMapDatum",
        "XMP-drone-dji:AbsoluteAltitude", "XMP-drone-dji:RelativeAltitude",
        "XMP-drone-dji:FlightRollDegree", "XMP-drone-dji:FlightPitchDegree", "XMP-drone-dji:FlightYawDegree",
        "XMP-drone-dji:GimbalRollDegree", "XMP-drone-dji:GimbalPitchDegree", "XMP-drone-dji:GimbalYawDegree",
        "XMP-drone-dji:FlightXSpeed", "XMP-drone-dji:FlightYSpeed", "XMP-drone-dji:FlightZSpeed",
        "XMP-drone-dji:CamReverse", "XMP-drone-dji:GimbalReverse",
        "DateTimeOriginal", "CreateDate"
    ]

    filas = []
    for item in metadatos_lista:
        ruta_img = os.path.abspath(item[0])
        telem = item[1]
        dt_str = item[2] if len(item) > 2 and item[2] else None
        if not dt_str:
            dt_str = hora_local_exif(telem.timestamp)

        lat_ref = "N" if telem.lat >= 0 else "S"
        lon_ref = "E" if telem.lon >= 0 else "W"

        filas.append([
            ruta_img, "DJI", "Mini 2 SE",
            f"{abs(telem.lat):.7f}", lat_ref,
            f"{abs(telem.lon):.7f}", lon_ref,
            f"{telem.alt_msl:.2f}", 0, "WGS-84",
            f"{telem.alt_msl:+.2f}", f"{telem.rel_alt:+.2f}",
            f"{telem.roll:.1f}", f"{telem.pitch:.1f}", f"{telem.yaw:.1f}",
            "0.0", "-90.0", f"{telem.yaw:.1f}",
            f"{telem.vx:.1f}", f"{telem.vy:.1f}", f"{telem.vz:.1f}",
            0, 0,
            dt_str, dt_str
        ])

    try:
        with open(ruta_csv_temp, "w", newline="", encoding="utf-8") as f:
            escritor = csv.writer(f)
            escritor.writerow(encabezados)
            escritor.writerows(filas)

        cmd = [
            EXIFTOOL_CMD,
            "-overwrite_original",
            f"-csv={ruta_csv_temp}",
            directorio_base
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(ruta_csv_temp):
            try: os.remove(ruta_csv_temp)
            except Exception: pass
        return len(filas) if res.returncode == 0 else 0
    except Exception as e:
        print(f"[ERROR] Fallo en escritura batch de ExifTool: {e}")
        if os.path.exists(ruta_csv_temp):
            try: os.remove(ruta_csv_temp)
            except Exception: pass
        return 0

def obtener_inicio_video(ruta_video, puntos):
    """
    Devuelve el instante (epoch UTC) de inicio del video.
    La GoPro guarda CreateDate del MP4 en hora LOCAL de la camara (no en UTC como dice
    el estandar QuickTime). Se prueban ambas interpretaciones y se elige la que cae
    dentro del rango temporal de la telemetria. Si ninguna coincide se emite un aviso,
    porque todas las fotos quedarian con la posicion del extremo del registro.
    """
    cmd = [EXIFTOOL_CMD, "-api", "largefilesupport=1", "-s3", "-d", "%Y:%m:%d %H:%M:%S", "-CreateDate", ruta_video]  # videos > 4 GB
    res = subprocess.run(cmd, capture_output=True, text=True)
    candidatos = []
    try:
        dt = datetime.strptime(res.stdout.strip(), "%Y:%m:%d %H:%M:%S")
        if dt.year > 1970:
            candidatos.append(("hora local", dt.astimezone().timestamp()))
            candidatos.append(("UTC", dt.replace(tzinfo=timezone.utc).timestamp()))
    except Exception:
        pass
    candidatos.append(("fecha de modificacion del archivo", os.path.getmtime(ruta_video)))

    if puntos:
        t_min, t_max = puntos[0].timestamp, puntos[-1].timestamp
        dur = duracion_video(ruta_video)
        # Vale si el video se superpone con la telemetria (la camara puede empezar antes)
        for nombre, t in candidatos:
            if t <= t_max and t + dur >= t_min:
                print(f"[*] Inicio del video tomado de CreateDate ({nombre}).")
                return t
        print("[AVISO] El inicio del video NO coincide con el rango de la telemetria "
              f"({datetime.fromtimestamp(t_min, tz=timezone.utc)} a {datetime.fromtimestamp(t_max, tz=timezone.utc)} UTC). "
              "Las coordenadas de las fotos no seran correctas. Verifique la sincronizacion de relojes.")
    return candidatos[0][1]

def hora_local_exif(t_epoch):
    """Fecha/hora EXIF en hora LOCAL (convencion de camaras DJI/GoPro y de obtener_timestamp_imagen)."""
    return datetime.fromtimestamp(t_epoch).strftime("%Y:%m:%d %H:%M:%S")

def duracion_video(ruta_video):
    cap = cv2.VideoCapture(ruta_video)
    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        if n > 0:
            return n / fps
    finally:
        cap.release()
    res = subprocess.run([EXIFTOOL_CMD, "-api", "largefilesupport=1", "-s3", "-Duration#", ruta_video], capture_output=True, text=True)
    try:
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def calcular_inicios_videos(rutas_videos, puntos):
    """
    La GoPro divide las grabaciones largas en capitulos (GX010123, GX020123, GX030123...).
    Los capitulos son continuos: el inicio del capitulo N es el inicio del N-1 mas su duracion.
    Devuelve {ruta: t_inicio_epoch_utc}.
    """
    patron = re.compile(r"^G[HXLP]?[A-Z]?(\d{2})(\d{4})\.(MP4|MOV)$", re.IGNORECASE)
    grupos, inicios = {}, {}
    for ruta in rutas_videos:
        m = patron.match(os.path.basename(ruta))
        if m:
            grupos.setdefault(m.group(2), []).append((int(m.group(1)), ruta))
        else:
            inicios[ruta] = obtener_inicio_video(ruta, puntos)
    for capitulos in grupos.values():
        capitulos.sort()
        t = obtener_inicio_video(capitulos[0][1], puntos)
        for _, ruta in capitulos:
            inicios[ruta] = t
            t += duracion_video(ruta)
    return inicios

def dividir_video_en_imagenes_dji(ruta_video, puntos, carpeta_salida, intervalo_segundos=1.0, offset=0.0, callback_progreso=None, t_inicio=None):
    """
    Extrae fotogramas de un video 4K a intervalos regulares (por defecto 1 FPS),
    calcula la marca de tiempo exacta de cada fotograma, interpola los datos de
    telemetria MAVLink e incrusta metadatos nativos DJI Mini 2 SE en formato EXIF/XMP.
    Tambien genera el archivo de subtitulos .SRT correspondiente.
    """
    if not os.path.exists(ruta_video):
        raise FileNotFoundError(f"No se encuentra el archivo de video: {ruta_video}")

    os.makedirs(carpeta_salida, exist_ok=True)
    nombre_base = os.path.splitext(os.path.basename(ruta_video))[0]

    # 1. Obtener timestamp inicial de inicio de grabacion del video (UTC)
    if t_inicio is None:
        t_inicio = obtener_inicio_video(ruta_video, puntos)
    t_inicio += offset

    # 2. Abrir video con OpenCV
    cap = cv2.VideoCapture(ruta_video)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video con OpenCV: {ruta_video}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duracion_sec = total_frames / fps if total_frames > 0 else 0
    paso_frames = max(1, int(round(fps * intervalo_segundos)))
    total_estimadas = max(1, total_frames // paso_frames) if total_frames > 0 else 1

    print(f"[*] Analizando video: {os.path.basename(ruta_video)}")
    print(f"    Resolucion: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {fps:.2f} FPS")
    print(f"    Duracion: {duracion_sec:.2f} s ({total_frames} cuadros)")
    print(f"    Intervalo de extraccion: {intervalo_segundos:.2f} s (~{total_estimadas} fotos)")

    metadatos_batch = []
    fotos_guardadas = []
    frame_idx = 0
    num_foto = 1
    fuera_de_rango = 0
    en_hueco = 0
    tiempos = [p.timestamp for p in puntos]

    # Lectura secuencial: el salto con CAP_PROP_POS_FRAMES es impreciso en H.264/H.265
    # de GoPro (cae en keyframes) y desalinearia la imagen con su marca de tiempo.
    actual = 0
    while True:
        ok = True
        while actual < frame_idx and ok:
            ok = cap.grab()
            actual += 1
        if not ok:
            break
        ret, frame = cap.read()
        actual += 1
        if not ret:
            break

        segundo_offset = frame_idx / fps
        t_frame = t_inicio + segundo_offset

        nombre_foto = f"{nombre_base}_{num_foto:04d}.JPG"
        ruta_foto = os.path.join(carpeta_salida, nombre_foto)

        # Guardar en alta calidad (95%)
        cv2.imwrite(ruta_foto, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        fotos_guardadas.append(ruta_foto)

        if not tiempos or t_frame < tiempos[0] - 2 or t_frame > tiempos[-1] + 2:
            fuera_de_rango += 1  # sin telemetria para este instante: no se inventa posicion
        else:
            i = bisect.bisect_left(tiempos, t_frame)
            vecinos = tiempos[max(0, i - 1):i + 1]
            if len(vecinos) == 2 and vecinos[1] - vecinos[0] > 2.0:
                en_hueco += 1  # posicion interpolada sobre un corte de radio > 2 s
            telem = interpolar_telemetria(puntos, t_frame)
            if telem:
                metadatos_batch.append((ruta_foto, telem, hora_local_exif(t_frame)))

        if callback_progreso and total_estimadas > 0:
            pct = min(90, int((num_foto / total_estimadas) * 80) + 10)
            callback_progreso(pct, f"Extrayendo fotograma {num_foto}/{total_estimadas} ({nombre_foto})...")

        num_foto += 1
        frame_idx += paso_frames
        if total_frames > 0 and frame_idx >= total_frames:
            break

    cap.release()

    # 3. Escribir metadatos nativos DJI Mini 2 SE en todas las fotos extraidas
    print(f"[*] Incrustando metadatos nativos DJI Mini 2 SE en {len(metadatos_batch)} fotografias...")
    if callback_progreso:
        callback_progreso(92, f"Incrustando metadatos DJI Mini 2 SE en {len(metadatos_batch)} fotos...")

    etiquetadas = escribir_metadatos_dji_batch(metadatos_batch)

    # 4. Generar subtitulos SRT para el video
    generar_srt_dji(ruta_video, puntos, t_inicio=t_inicio)

    avisos = []
    if fuera_de_rango:
        avisos.append(f"{fuera_de_rango} fotos sin GPS (fuera del rango de la telemetria)")
    if en_hueco:
        avisos.append(f"{en_hueco} fotos con posicion interpolada sobre cortes de radio > 2 s")
    for a in avisos:
        print(f"[AVISO] {a}")
    if etiquetadas < len(metadatos_batch):
        avisos.append(f"exiftool fallo: {len(metadatos_batch)} fotos sin etiquetar")
    dividir_video_en_imagenes_dji.ultimos_avisos = avisos
    dividir_video_en_imagenes_dji.ultimas_etiquetadas = etiquetadas

    if callback_progreso:
        callback_progreso(100, f"Completado: {len(fotos_guardadas)} fotos generadas, {etiquetadas} etiquetadas.")

    print(f"[+] Extraccion completada con exito: {len(fotos_guardadas)} fotos generadas.")
    print(f"[+] Fotos etiquetadas con telemetria DJI: {etiquetadas}")
    return fotos_guardadas

def generar_srt_dji(ruta_video, puntos, t_inicio=None):
    """Genera subtitulos de telemetria .SRT para video en formato DJI."""
    base, _ = os.path.splitext(ruta_video)
    ruta_srt = base + ".SRT"
    
    if t_inicio is None:
        t_inicio = obtener_inicio_video(ruta_video, puntos)
    cmd = [EXIFTOOL_CMD, "-api", "largefilesupport=1", "-s3", "-Duration#", ruta_video]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        duracion_seg = int(float(res.stdout.strip()))
    except Exception:
        duracion_seg = 60

    print(f"[*] Generando subtitulos DJI SRT para el video ({duracion_seg} seg)...")
    with open(ruta_srt, "w", encoding="utf-8") as f:
        for s in range(duracion_seg):
            telem = interpolar_telemetria(puntos, t_inicio + s)
            if not telem: continue
            
            ts_ini = f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
            ts_fin = f"{(s + 1) // 3600:02d}:{((s + 1) % 3600) // 60:02d}:{(s + 1) % 60:02d}"
            
            bloque = (
                f"{s + 1}\n"
                f"{ts_ini},000 --> {ts_fin},000\n"
                f"[latitude: {telem.lat:.6f}] [longitude: {telem.lon:.6f}] "
                f"[rel_alt: {telem.rel_alt:.3f} abs_alt: {telem.alt_msl:.3f}] "
                f"[flight_yaw: {telem.yaw:.1f}] [iso: 100] [shutter: 1/240]\n\n"
            )
            f.write(bloque)
    print(f"[+] Archivo de subtitulos generado: {ruta_srt}")
    return ruta_srt

def main():
    print("=================================================================")
    print("   VINCULADOR DE TELEMETRIA A FORMATO NATIVO DJI MINI 2 SE")
    print("   Configuracion: GoPro HERO13 Nadir (-90.0° hacia abajo)")
    print("   Proyecto UAV Hormigas Cortadoras - UTEC PRIA")
    print("=================================================================")

    parser = argparse.ArgumentParser(description="Etiquetador de fotos/videos a formato DJI Mini 2 SE")
    parser.add_argument("--log", help="Ruta al archivo .CSV, .BIN o .tlog de telemetria")
    parser.add_argument("--media", help="Carpeta con fotos o archivo de video MP4")
    parser.add_argument("--interval", type=float, default=1.0, help="Intervalo en segundos para extraer fotos de video (default: 1.0s = 1 FPS)")
    parser.add_argument("--output", help="Carpeta de destino para las fotos extraidas")
    parser.add_argument("--only-srt", action="store_true", help="Solo generar archivo .SRT para video sin extraer fotos")
    parser.add_argument("--offset", type=float, default=0.0, help="Ajuste manual de segundos si es necesario")
    args = parser.parse_args()

    log_path = args.log
    media_path = args.media

    if not log_path:
        log_path = input("\n[?] Arrastre aqui el archivo de telemetria (.CSV, .BIN o .tlog) y presione ENTER: ").strip().strip('"').strip("'")
    if not media_path:
        media_path = input("[?] Arrastre aqui la carpeta con las fotos (o el archivo .MP4) y presione ENTER: ").strip().strip('"').strip("'")

    if not os.path.exists(log_path):
        print(f"[ERROR] No se encuentra el archivo de log: {log_path}")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    if not os.path.exists(media_path):
        print(f"[ERROR] No se encuentra la ruta de fotos/video: {media_path}")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    ext = os.path.splitext(log_path)[1].lower()
    if ext == '.csv':
        puntos = cargar_desde_csv(log_path)
    else:
        puntos = cargar_desde_bin_o_tlog(log_path)

    if not puntos:
        print("[ERROR] No se pudieron extraer datos de posicion GPS del archivo indicado.")
        if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
        return 1

    # Caso 1: Archivo de video MP4 / MOV
    if os.path.isfile(media_path) and media_path.lower().endswith((".mp4", ".mov")):
        if args.only_srt:
            generar_srt_dji(media_path, puntos)
        else:
            carpeta_out = args.output
            if not carpeta_out:
                dir_video = os.path.dirname(media_path) or "."
                carpeta_out = os.path.join(dir_video, "fotos")
            dividir_video_en_imagenes_dji(
                ruta_video=media_path,
                puntos=puntos,
                carpeta_salida=carpeta_out,
                intervalo_segundos=args.interval,
                offset=args.offset
            )
        print("\n[+] Proceso completado exitosamente.")
        if sys.stdin.isatty(): input("\nPresione ENTER para finalizar...")
        return 0

    # Caso 2: Carpeta con fotos JPG / DNG
    if os.path.isdir(media_path):
        archivos = [f for f in os.listdir(media_path) if f.lower().endswith((".jpg", ".jpeg", ".dng"))]
        archivos.sort()

        if not archivos:
            print("[ERROR] No se encontraron fotografias JPG/DNG en la carpeta indicada.")
            if sys.stdin.isatty(): input("\nPresione ENTER para salir...")
            return 1

        print(f"\n[*] Procesando {len(archivos)} fotografias...")
        metadatos_batch = []
        for i, nombre in enumerate(archivos, 1):
            ruta_foto = os.path.join(media_path, nombre)
            t_foto = obtener_timestamp_imagen(ruta_foto) + args.offset
            telem = interpolar_telemetria(puntos, t_foto)

            if telem:
                dt_str = hora_local_exif(t_foto)
                metadatos_batch.append((ruta_foto, telem, dt_str))
                print(f"  [{i}/{len(archivos)}] {nombre} -> Lat: {telem.lat:.6f}, Lon: {telem.lon:.6f}, AltRel: {telem.rel_alt:.1f}m [DJI OK]")
            else:
                print(f"  [{i}/{len(archivos)}] {nombre} -> Fuera de rango de tiempo del registro.")

        exitos = escribir_metadatos_dji_batch(metadatos_batch)

        print("\n=================================================================")
        print(f"   RESUMEN: {exitos} de {len(archivos)} fotografias etiquetadas.")
        print("   Formato: NATIVO DJI MINI 2 SE (EXIF + XMP drone-dji)")
        print("   Compatible directamente con: WebODM, Pix4D, Agisoft, QGIS, DJI Terra")
        print("=================================================================")

    if sys.stdin.isatty():
        input("\nPresione ENTER para finalizar...")
    return 0

if __name__ == "__main__":
    sys.exit(main())
