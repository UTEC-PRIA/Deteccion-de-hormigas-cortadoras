#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Datos Sinteticos y Ejemplos de Salida para Documentacion
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
"""

import os
import sys
import math
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(base_dir, "ejemplos_salida", "vuelo_mision_campo_01")
    fotos_dir = os.path.join(out_dir, "fotos")
    os.makedirs(fotos_dir, exist_ok=True)

    print("Generando datos sinteticos de ejemplo...")

    # 1. telemetria.csv
    csv_path = os.path.join(out_dir, "telemetria.csv")
    t_base = datetime(2026, 11, 20, 10, 30, 0, tzinfo=timezone.utc)

    lat_base = -33.381250
    lon_base = -56.529800
    alt_rel_base = 25.0
    alt_msl_base = 78.5

    rows = [
        "timestamp_utc,latitud,longitud,altitud_msl,altitud_relativa,alabeo_roll,cabeceo_pitch,rumbo_yaw,velocidad_ms,satelites,voltaje_bateria,modo_vuelo"
    ]

    sys.path.insert(0, base_dir)
    from vincular_vuelo_dji import escribir_metadatos_dji, interpolar_telemetria, generar_srt_dji, PuntoTelemetria

    puntos_telem = []

    for i in range(120):  # 30 segundos a 4 Hz
        dt = t_base + timedelta(seconds=i * 0.25)
        t_str = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        lat = lat_base + (i * 0.000015)
        lon = lon_base + math.sin(i * 0.05) * 0.000008
        alt_rel = alt_rel_base + math.sin(i * 0.1) * 0.3
        alt_msl = alt_msl_base + (alt_rel - alt_rel_base)
        roll = math.sin(i * 0.2) * 1.5
        pitch = -1.2 + math.cos(i * 0.15) * 0.8
        yaw = 45.0 + math.sin(i * 0.05) * 2.0
        vel = 3.5 + math.sin(i * 0.1) * 0.3
        sats = 15
        bat = 12.45 - (i * 0.005)
        modo = "AUTO"
        
        line = f"{t_str},{lat:.7f},{lon:.7f},{alt_msl:.2f},{alt_rel:.2f},{roll:.2f},{pitch:.2f},{yaw:.2f},{vel:.2f},{sats},{bat:.2f},{modo}"
        rows.append(line)
        puntos_telem.append(PuntoTelemetria(dt.timestamp(), lat, lon, alt_msl, alt_rel, roll, pitch, yaw, bat))

    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print(f" [OK] Archivo CSV generado: {csv_path}")

    # 2. Fotos sinteticas con metadatos DJI
    for idx in range(1, 5):
        t_foto = t_base + timedelta(seconds=idx * 6)
        img = Image.new("RGB", (1920, 1080), color=(50 + idx * 12, 110 + idx * 8, 45 + idx * 5))
        draw = ImageDraw.Draw(img)
        draw.rectangle([80, 80, 1840, 1000], outline=(170, 190, 90), width=4)
        draw.line([150, 200, 1750, 850], fill=(120, 75, 35), width=10)
        draw.text((100, 100), f"UTEC-PRIA Deteccion Aerea F450 - Foto {idx:02d}", fill=(255, 255, 255))
        draw.text((100, 130), f"Hora UTC: {t_foto.isoformat()}", fill=(255, 255, 255))
        
        img_name = f"GX01{idx:04d}.JPG"
        img_path = os.path.join(fotos_dir, img_name)
        img.save(img_path, "JPEG", quality=95)
        
        telem = interpolar_telemetria(puntos_telem, t_foto)
        if telem:
            escribir_metadatos_dji(img_path, telem)
            print(f" [OK] Foto con metadatos nativos DJI Mini 2 SE inyectados: {img_name}")

    # 3. Subtitulos SRT
    dummy_video = os.path.join(out_dir, "video_vuelo_mision_01.MP4")
    with open(dummy_video, "wb") as f:
        f.write(b"video_dummy_stream")
    generar_srt_dji(dummy_video, puntos_telem)
    if os.path.exists(dummy_video):
        os.remove(dummy_video)
    print(" [OK] Subtitulos de telemetria SRT generados correctamente.")
    print("\n[COMPLETADO] Carpeta de ejemplos generada con exito.")

if __name__ == "__main__":
    main()
