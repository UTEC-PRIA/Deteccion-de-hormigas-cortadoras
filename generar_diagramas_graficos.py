#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Diagramas Graficos de Alta Resolucion para el Informe Tecnico UAV
Proyecto UTEC-PRIA - Deteccion de Hormigas Cortadoras
"""

import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np

os.makedirs("docs/imagenes", exist_ok=True)

# -----------------------------------------------------------------------------
# 1. DIAGRAMA DE ARQUITECTURA GENERAL DEL SISTEMA
# -----------------------------------------------------------------------------
def generar_diagrama_arquitectura():
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=200)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Titulo
    ax.text(50, 96, "ARQUITECTURA INTEGRAL DEL SISTEMA AEROFOTOGRAMETRICO UAV", 
            fontsize=13, fontweight='bold', ha='center', color='#0F2942', fontfamily='sans-serif')
    ax.text(50, 92.5, "Plataforma Cuadricoptero F450 + GoPro HERO13 Nadir (-90°) + Telemetria 915 MHz + Formato DJI Mini 2 SE",
            fontsize=8.5, ha='center', color='#1A5F7A', fontfamily='sans-serif')

    # Caja 1: Segmento Aereo
    rect_aereo = patches.FancyBboxPatch((4, 48), 38, 40, boxstyle="round,pad=1.2", 
                                        ec="#0F2942", fc="#F8FAFC", lw=1.5)
    ax.add_patch(rect_aereo)
    ax.text(23, 85, "SEGMENTO AEREO (AERONAVE)", fontsize=10, fontweight='bold', ha='center', color='#0F2942')
    
    subcajas_aereo = [
        ("Chasis F450 + 4 Motores 920KV (ESC 30A)", 78),
        ("Controladora Pixhawk 2.4.8 (ArduCopter 4.x)", 71),
        ("GNSS Radiolink SE100 (u-blox M8N en mastil 14cm)", 64),
        ("Bateria LiPo 3S (Sensor analogico Pin 13 y 14)", 57),
        ("GoPro HERO13 Black (Nadir -90°, HyperSmooth)", 50)
    ]
    for txt, y in subcajas_aereo:
        r = patches.FancyBboxPatch((6, y-1.5), 34, 5, boxstyle="round,pad=0.5", ec="#CBD5E1", fc="#FFFFFF", lw=1)
        ax.add_patch(r)
        ax.text(23, y+0.7, txt, fontsize=7.2, ha='center', color='#1E293B')

    # Enlaces
    # Radio 915 MHz
    ax.annotate("", xy=(58, 70), xytext=(43, 70),
                arrowprops=dict(arrowstyle="<->", color="#DC2626", lw=2, mutation_scale=15))
    ax.text(50.5, 74, "Radio SiK 915 MHz\n(500 mW, 4 Hz, MAVLink)", fontsize=7.2, ha='center', color='#DC2626', fontweight='bold')

    # Cable USB
    ax.annotate("", xy=(58, 54), xytext=(43, 54),
                arrowprops=dict(arrowstyle="<->", color="#0284C7", lw=2, linestyle="dashed", mutation_scale=15))
    ax.text(50.5, 50, "Cable USB-C Open GoPro\n(Pre/Post-Vuelo en Tierra)", fontsize=7.2, ha='center', color='#0284C7', fontweight='bold')

    # Caja 2: Estacion Terrena
    rect_tierra = patches.FancyBboxPatch((58, 48), 38, 40, boxstyle="round,pad=1.2", 
                                         ec="#1A5F7A", fc="#F8FAFC", lw=1.5)
    ax.add_patch(rect_tierra)
    ax.text(77, 85, "ESTACION TERRENA DE CONTROL", fontsize=10, fontweight='bold', ha='center', color='#1A5F7A')

    subcajas_tierra = [
        ("Dongle USB Receptor SiK 915 MHz (COM10)", 78),
        ("Dashboard Local FastAPI (http://localhost:8000)", 71),
        ("Modulo Autoescaneo de Hardware en Vivo", 64),
        ("Sincronizacion Horaria GPS (<0.05 s)", 57),
        ("Almacenamiento: telemetria.csv y .tlog", 50)
    ]
    for txt, y in subcajas_tierra:
        r = patches.FancyBboxPatch((60, y-1.5), 34, 5, boxstyle="round,pad=0.5", ec="#CBD5E1", fc="#FFFFFF", lw=1)
        ax.add_patch(r)
        ax.text(77, y+0.7, txt, fontsize=7.2, ha='center', color='#1E293B')

    # Flecha hacia abajo: Procesamiento
    ax.annotate("", xy=(50, 40), xytext=(50, 46),
                arrowprops=dict(arrowstyle="->", color="#0F2942", lw=2.5, mutation_scale=18))
    ax.text(50, 42.5, "Al aterrizar: Clic en [Finalizar y Procesar]", fontsize=8, ha='center', color='#0F2942', fontweight='bold')

    # Caja 3: Motor de Georreferenciacion
    rect_proc = patches.FancyBboxPatch((15, 14), 70, 24, boxstyle="round,pad=1.2", 
                                       ec="#2C7A7B", fc="#F0FDF4", lw=1.5)
    ax.add_patch(rect_proc)
    ax.text(50, 34, "MOTOR DE PROCESAMIENTO Y GEORREFERENCIACION (vincular_vuelo_dji.py)", 
            fontsize=9.5, fontweight='bold', ha='center', color="#15803D")

    pasos_proc = [
        ("1. Descarga MP4 4K", 23, 27),
        ("2. Division a 1 FPS (OpenCV)", 41, 27),
        ("3. Interpolacion GPS WGS-84", 59, 27),
        ("4. Inyeccion Batch DJI Mini 2 SE", 77, 27),
    ]
    for tit, cx, cy in pasos_proc:
        r = patches.FancyBboxPatch((cx-8, cy-3), 16, 6, boxstyle="round,pad=0.4", ec="#86EFAC", fc="#FFFFFF", lw=1)
        ax.add_patch(r)
        ax.text(cx, cy, tit, fontsize=6.8, ha='center', color='#166534', fontweight='bold')

    ax.text(50, 18, "Salida Estandarizada: vuelos/MISION/fotos/ (Fotogramas 4K JPG con XMP-drone-dji) + video.SRT", 
            fontsize=7.8, ha='center', color='#1E293B', style='italic')

    # Destinos finales
    destinos = [
        ("WebODM / Pix4D\n(Ortomosaicos a Escala)", 25, 4),
        ("Plataforma AntTrack\n(Deteccion IA de Hormigueros)", 50, 4),
        ("QGIS / ArcGIS\n(Mapeo SIG Silvopastoril)", 75, 4)
    ]
    for tit, cx, cy in destinos:
        ax.annotate("", xy=(cx, cy+4), xytext=(cx, 12),
                    arrowprops=dict(arrowstyle="->", color="#15803D", lw=1.5, mutation_scale=12))
        r = patches.FancyBboxPatch((cx-11, cy-3), 22, 6, boxstyle="round,pad=0.4", ec="#CBD5E1", fc="#F8FAFC", lw=1)
        ax.add_patch(r)
        ax.text(cx, cy+0.5, tit, fontsize=7, ha='center', color='#0F2942', fontweight='bold')

    plt.tight_layout()
    out_path = "docs/imagenes/diagrama_arquitectura_sistema.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"[+] Generado: {out_path}")

# -----------------------------------------------------------------------------
# 2. DIAGRAMA DE CICLO OPERATIVO Y ESTADOS EN VUELO
# -----------------------------------------------------------------------------
def generar_diagrama_ciclo_operativo():
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=200)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis('off')

    ax.text(50, 56, "CICLO OPERATIVO EN TRES FASES (OPERATOR-PROOF)", 
            fontsize=12, fontweight='bold', ha='center', color='#0F2942')

    fases = [
        ("FASE 1: PRE-VUELO EN TIERRA", 18, "#0284C7", [
            "Conectar USB GoPro + Receptor 915 MHz",
            "Autoescaneo activo de hardware (OK)",
            "Sincronizar Relojes (< 0.05 s)",
            "Configurar Video 4K 30 FPS",
            "Clic en [Comenzar Grabacion] (Status 10 = 1)"
        ]),
        ("FASE 2: VUELO AUTONOMO EN SD", 50, "#DC2626", [
            "DESCONECTAR CABLE USB de GoPro",
            "Grabacion continua autonoma en microSD",
            "Dashboard: GRABANDO EN VUELO",
            "Vuelo libre sobre parcela silvopastoril",
            "Telemetria MAVLink 915 MHz a 4 Hz en vivo"
        ]),
        ("FASE 3: POST-VUELO Y EXTRACCION", 82, "#15803D", [
            "Aterrizaje y RECONEXION USB-C",
            "Clic en [Finalizar y Procesar]",
            "Descarga automatica de video 4K (MP4)",
            "Division en cuadros a 1 FPS (OpenCV)",
            "Inyeccion batch metadatos DJI Mini 2 SE"
        ])
    ]

    for tit, cx, color_header, bullets in fases:
        # Caja principal
        rect = patches.FancyBboxPatch((cx-14.5, 6), 29, 44, boxstyle="round,pad=1.0",
                                     ec=color_header, fc="#F8FAFC", lw=1.8)
        ax.add_patch(rect)
        
        # Cabecera
        head = patches.FancyBboxPatch((cx-14.5, 43), 29, 7, boxstyle="round,pad=0.5",
                                      ec=color_header, fc=color_header, lw=1)
        ax.add_patch(head)
        ax.text(cx, 46.5, tit, fontsize=7.8, fontweight='bold', ha='center', color='white')

        # Bullets
        y = 37
        for b in bullets:
            ax.plot(cx-12.5, y+0.5, marker='o', markersize=3.5, color=color_header)
            ax.text(cx-11, y, b, fontsize=6.8, ha='left', va='center', color='#1E293B')
            y -= 6.5

    # Flechas conectoras entre fases
    ax.annotate("", xy=(34.5, 28), xytext=(32.5, 28),
                arrowprops=dict(arrowstyle="->", color="#0F2942", lw=2.5, mutation_scale=15))
    ax.annotate("", xy=(66.5, 28), xytext=(64.5, 28),
                arrowprops=dict(arrowstyle="->", color="#0F2942", lw=2.5, mutation_scale=15))

    plt.tight_layout()
    out_path = "docs/imagenes/diagrama_flujo_estados.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"[+] Generado: {out_path}")

# -----------------------------------------------------------------------------
# 3. CURVA DE DESCARGA Y CALIBRACION DE BATERIA LIPO 3S
# -----------------------------------------------------------------------------
def generar_curva_bateria():
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)

    # Curva tipica de descarga de bateria LiPo 3S bajo carga (4-5A de crucero)
    tiempo = np.linspace(0, 16, 200) # minutos
    # Modelo exponencial suave de descarga LiPo
    voltaje = 12.6 - 0.45 * (1 - np.exp(-tiempo / 1.5)) - 1.1 * (tiempo / 16)**1.2 - 0.8 * (np.maximum(0, tiempo - 13) / 3)**2

    ax.plot(tiempo, voltaje, color='#0F2942', lw=2.5, label='Curva de Tension LiPo 3S bajo carga')

    # Lineas de referencia y zonas de seguridad
    ax.axhspan(11.4, 12.6, color='#DCFCE7', alpha=0.6, label='Rango Optimo Operativo (100% - 40%)')
    ax.axhspan(10.5, 11.4, color='#FEF9C3', alpha=0.6, label='Zona de Advertencia / Retorno Recomendado')
    ax.axhspan(9.5, 10.5, color='#FEE2E2', alpha=0.6, label='Zona Critica / Fail-Safe Obligatorio')

    ax.axhline(10.5, color='#D97706', linestyle='--', lw=1.5)
    ax.text(0.5, 10.55, 'BATT_LOW_VOLT = 10.5 V (Alarma de Bateria Baja en Panel Web)', fontsize=7.5, color='#B45309', fontweight='bold')

    ax.axhline(10.2, color='#DC2626', linestyle='--', lw=1.5)
    ax.text(0.5, 10.25, 'BATT_CRT_VOLT = 10.2 V (Voltaje Critico - RTL Inmediato Pixhawk)', fontsize=7.5, color='#B91C1C', fontweight='bold')

    ax.set_title("CURVA DE DESCARGA Y UMBRALES DE SEGURIDAD LIPO 3S (PIXHAWK 2.4.8)", fontsize=10.5, fontweight='bold', color='#0F2942', pad=10)
    ax.set_xlabel("Tiempo Estimado de Vuelo (Minutos)", fontsize=8.5, color='#1E293B')
    ax.set_ylabel("Tension Total del Pack (Voltios)", fontsize=8.5, color='#1E293B')
    ax.set_xlim(0, 16)
    ax.set_ylim(9.8, 12.8)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(loc='lower left', fontsize=7.5, framealpha=0.9)

    plt.tight_layout()
    out_path = "docs/imagenes/curva_calibracion_bateria_3s.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"[+] Generado: {out_path}")

# -----------------------------------------------------------------------------
# 4. DIAGRAMA DE GRILLA FOTOGRAMETRICA Y WAYPOINTS (FASE FUTURA)
# -----------------------------------------------------------------------------
def generar_diagrama_grilla_waypoints():
    fig, ax = plt.subplots(figsize=(8, 5.0), dpi=200)

    # Parcela de pastura / silvopastoril
    parcela = patches.Polygon([[10, 10], [90, 15], [85, 85], [15, 80]], closed=True, 
                              ec='#15803D', fc='#F0FDF4', lw=2, linestyle='--', label='Poligono de Relevamiento (Parcela)')
    ax.add_patch(parcela)

    # Waypoints de grilla fotogrametrica (zigzag)
    lineas_x = [25, 40, 55, 70]
    puntos_mision = [
        (10, 5, "HOME / Despegue"),
        (25, 25, "WP 1 (NAV_TAKEOFF + Inicio Video 4K)"),
        (25, 75, "WP 2"),
        (40, 75, "WP 3"),
        (40, 25, "WP 4"),
        (55, 25, "WP 5"),
        (55, 75, "WP 6"),
        (70, 75, "WP 7"),
        (70, 25, "WP 8 (Fin de Escaneo -> RTL)"),
        (10, 5, "LAND (Aterrizaje en Base)")
    ]

    xs = [p[0] for p in puntos_mision]
    ys = [p[1] for p in puntos_mision]

    # Linea de vuelo
    ax.plot(xs, ys, color='#0284C7', lw=2, linestyle='-', marker='o', markersize=5, mfc='#0F2942', label='Trayectoria de Mision MAVLink (AUTO)')

    # Anotaciones de puntos clave
    ax.text(10, 2, "HOME / Despegue", fontsize=7.5, fontweight='bold', color='#15803D', ha='center')
    ax.text(25, 20, "WP 1: Inicio Video 4K 30fps", fontsize=7, color='#0284C7', ha='center')
    ax.text(70, 20, "WP 8: Fin Escaneo -> RTL", fontsize=7, color='#DC2626', ha='center')

    # Solapamientos
    ax.annotate("", xy=(25, 50), xytext=(40, 50),
                arrowprops=dict(arrowstyle="<->", color="#D97706", lw=1.5))
    ax.text(32.5, 52, "Solape Lateral: 75%\n(Espaciado pasadas)", fontsize=6.8, ha='center', color='#B45309')

    ax.annotate("", xy=(55, 45), xytext=(55, 60),
                arrowprops=dict(arrowstyle="<->", color="#D97706", lw=1.5))
    ax.text(58, 52.5, "Solape Frontal: 90%\n(1 foto / seg)", fontsize=6.8, ha='left', color='#B45309')

    # Hormigueros sinteticos simulados en la parcela
    hormigueros = [(32, 60), (48, 38), (62, 70), (45, 68)]
    for hx, hy in hormigueros:
        c = patches.Circle((hx, hy), 2.5, color='#92400E', alpha=0.7)
        ax.add_patch(c)
        ax.plot([hx-3, hx+4], [hy-2, hy+3], color='#B45309', lw=1.2, linestyle=':')
    ax.text(32, 63, "Nido / Hormiguero", fontsize=6.5, color='#92400E', ha='center')

    ax.set_title("ESPECIFICACION DE GRILLA DE NAVEGACION AUTONOMA POR WAYPOINTS (ARDUCOPTER)", fontsize=9.5, fontweight='bold', color='#0F2942', pad=10)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 95)
    ax.axis('off')
    ax.legend(loc='upper right', fontsize=7.5)

    plt.tight_layout()
    out_path = "docs/imagenes/diagrama_grilla_waypoints_futuro.png"
    plt.savefig(out_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"[+] Generado: {out_path}")

if __name__ == "__main__":
    generar_diagrama_arquitectura()
    generar_diagrama_ciclo_operativo()
    generar_curva_bateria()
    generar_diagrama_grilla_waypoints()
    print("[+] Todos los diagramas fueron generados exitosamente.")
