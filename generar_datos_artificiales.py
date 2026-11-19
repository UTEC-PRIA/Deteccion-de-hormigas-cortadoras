#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Generador de Datos Sinteticos / Artificiales para Pruebas y Simulacion
Crea misiones sinteticas con telemetria MAVLink 4 Hz, video 4K simulado,
fotogramas extraidos y metadatos nativos DJI Mini 2 SE (EXIF + XMP).
"""

import os
import sys
import math
import csv
from datetime import datetime, timezone, timedelta
import numpy as np
import cv2

# Importar funciones del proyecto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vincular_vuelo_dji import (
    PuntoTelemetria,
    escribir_metadatos_dji_batch,
    generar_srt_dji,
    obtener_ruta_exiftool
)

def generar_mision_sintetica(carpeta_destino="datos_artificiales/mision_simulada_4k", duracion_seg=60, fps_video=30):
    """
    Genera un conjunto completo de datos artificiales de vuelo:
    1. telemetria.csv (registro continuo a 4 Hz con dinamica de vuelo y bateria 3S).
    2. video_simulado_4k.mp4 (video 4K a 30 FPS con patrulla aerea sobre caminos de hormigas).
    3. fotos/ (fotogramas extraidos a 1 FPS con metadatos nativos DJI Mini 2 SE).
    4. video_simulado_4k.SRT (subtitulos de telemetria segundo a segundo).
    """
    os.makedirs(carpeta_destino, exist_ok=True)
    carpeta_fotos = os.path.join(carpeta_destino, "fotos")
    os.makedirs(carpeta_fotos, exist_ok=True)

    t_base = datetime.now(timezone.utc).replace(microsecond=0)
    lat_origen = -34.895420
    lon_origen = -56.162350
    alt_msl_origen = 45.0
    alt_rel_objetivo = 25.0

    print("=================================================================")
    print("   GENERADOR DE DATOS ARTIFICIALES / SINTETICOS UAV UTEC-PRIA")
    print(f"   Destino: {carpeta_destino}")
    print(f"   Duracion: {duracion_seg} segundos | Video: 4K 30 FPS")
    print("=================================================================")

    # 1. Generar telemetria a 4 Hz (250 ms)
    puntos_telem = []
    ruta_csv = os.path.join(carpeta_destino, "telemetria.csv")

    with open(ruta_csv, "w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow([
            "timestamp_utc", "latitud", "longitud", "altitud_msl", "altitud_relativa",
            "alabeo_roll", "cabeceo_pitch", "rumbo_yaw", "velocidad_ms", "satelites",
            "voltaje_bateria", "modo_vuelo"
        ])

        total_pasos = duracion_seg * 4
        for paso in range(total_pasos):
            t_actual = t_base + timedelta(seconds=paso * 0.25)
            s = paso * 0.25

            # Trayectoria de escaneo lineal con curvas suaves
            desp_x = 3.5 * s
            desp_y = 6.0 * math.sin(s / 6.0)

            lat = lat_origen + (desp_y / 111320.0)
            lon = lon_origen + (desp_x / (111320.0 * math.cos(math.radians(lat_origen))))

            # Altura suavemente estabilizada en 25m
            rel_alt = min(alt_rel_objetivo, (s / 5.0) * alt_rel_objetivo) if s < 5.0 else alt_rel_objetivo + 0.3 * math.sin(s / 3.0)
            alt_msl = alt_msl_origen + rel_alt

            # Actitud del dron
            roll = 1.2 * math.cos(s / 2.0)
            pitch = -1.5 + 0.5 * math.sin(s / 2.5)
            yaw = (math.degrees(math.atan2(6.0 * math.cos(s / 6.0) / 6.0, 3.5))) % 360.0

            # Bateria LiPo 3S descargando lentamente
            voltaje = max(11.4, 12.5 - (s / duracion_seg) * 0.6)
            satelites = 14
            modo = "AUTO" if s >= 5.0 else "LOITER"

            linea_csv = [
                t_actual.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                f"{lat:.7f}", f"{lon:.7f}", f"{alt_msl:.2f}", f"{rel_alt:.2f}",
                f"{roll:.2f}", f"{pitch:.2f}", f"{yaw:.2f}", "3.50",
                str(satelites), f"{voltaje:.2f}", modo
            ]
            writer.writerow(linea_csv)

            pt = PuntoTelemetria(
                timestamp_utc=t_actual.timestamp(),
                lat=lat, lon=lon, alt_msl=alt_msl, rel_alt=rel_alt,
                roll=roll, pitch=pitch, yaw=yaw, vx=3.5, vy=0.0, vz=0.0
            )
            puntos_telem.append(pt)

    print(f"[+] Archivo CSV generado: {ruta_csv} ({len(puntos_telem)} registros a 4 Hz)")

    # 2. Generar Video 4K Simulado (3840x2160 @ 30 FPS)
    ruta_video = os.path.join(carpeta_destino, "video_simulado_4k.mp4")
    ancho, alto = 3840, 2160
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vw = cv2.VideoWriter(ruta_video, fourcc, float(fps_video), (ancho, alto))

    print(f"[*] Renderizando video sintetico 4K (3840x2160 @ {fps_video} FPS) duracion {duracion_seg}s...")
    
    # Crear textura base de suelo sintetico
    np.random.seed(42)
    pasto_base = np.full((alto, ancho, 3), (35, 75, 45), dtype=np.uint8)
    ruido = np.random.randint(-12, 12, (alto, ancho, 3), dtype=np.int16)
    suelo = np.clip(pasto_base.astype(np.int16) + ruido, 0, 255).astype(np.uint8)

    # Dibujar camino de hormigas cortadoras (suelo desnudo / sendero marron claro)
    puntos_camino = []
    for x in range(0, ancho, 80):
        y = int(alto * 0.52 + 180 * math.sin(x / 400.0))
        puntos_camino.append((x, y))
    
    for i in range(len(puntos_camino) - 1):
        cv2.line(suelo, puntos_camino[i], puntos_camino[i+1], (45, 90, 130), 28)

    # Dibujar monticulo de hormiguero principal
    centro_nido = (int(ancho * 0.65), int(alto * 0.50))
    cv2.circle(suelo, centro_nido, 95, (50, 85, 115), -1)
    cv2.circle(suelo, centro_nido, 40, (30, 50, 70), -1)

    # Escribir frames de video
    total_frames = duracion_seg * fps_video
    metadatos_fotos_batch = []
    fotos_guardadas = []

    # Extraer 1 foto por segundo
    intervalo_seg = 1.0
    paso_frames = int(round(fps_video * intervalo_seg))

    foto_contador = 1
    for f_idx in range(total_frames):
        s = f_idx / fps_video
        frame = suelo.copy()

        # Telemetria en pantalla (simulando overlay de camara de inspeccion)
        t_frame = t_base + timedelta(seconds=s)
        dt_str = t_frame.strftime("%Y-%m-%d %H:%M:%S")

        # Guardar fotograma a 1 FPS para el dataset de fotogrametria
        if f_idx % paso_frames == 0:
            nombre_foto = f"GX01_{foto_contador:04d}.JPG"
            ruta_foto = os.path.join(carpeta_fotos, nombre_foto)
            cv2.imwrite(ruta_foto, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
            fotos_guardadas.append(ruta_foto)

            # Buscar punto de telemetria
            idx_pt = min(len(puntos_telem) - 1, int(s * 4))
            pt_actual = puntos_telem[idx_pt]
            metadatos_fotos_batch.append((ruta_foto, pt_actual, dt_str))
            foto_contador += 1

        vw.write(frame)

    vw.release()
    print(f"[+] Video 4K sintetico generado: {ruta_video}")

    # 3. Inyectar metadatos DJI Mini 2 SE en las fotos extraidas
    print(f"[*] Inyectando metadatos nativos DJI Mini 2 SE en {len(metadatos_fotos_batch)} fotos...")
    etiquetadas = escribir_metadatos_dji_batch(metadatos_fotos_batch)
    print(f"[+] {etiquetadas} fotos etiquetadas con metadatos nativos DJI Mini 2 SE.")

    # 4. Generar subtitulos SRT
    generar_srt_dji(ruta_video, puntos_telem)

    print("\n=================================================================")
    print("   GENERACION DE DATOS ARTIFICIALES COMPLETADA EXITOSAMENTE")
    print(f"   Fotos DJI listas para WebODM/Pix4D en: {carpeta_fotos}")
    print("=================================================================\n")
    return carpeta_destino

if __name__ == "__main__":
    dur = 20
    if len(sys.argv) > 1:
        try: dur = int(sys.argv[1])
        except Exception: pass
    generar_mision_sintetica(duracion_seg=dur)
