#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
Generador del Documento PDF Completo:
INFORME TECNICO Y MANUAL OPERATIVO INTEGRAL
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8.5)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Encabezado (desde la pagina 2)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 34, "UTEC - PRIA | Prototipo UAV de Deteccion de Hormigas Cortadoras")
            self.drawRightString(letter[0] - 54, letter[1] - 34, "Informe Tecnico y Operativo")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 40, letter[0] - 54, letter[1] - 40)
            
        # Pie de pagina
        texto_pie = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 34, texto_pie)
        self.drawString(54, 34, "Cuadricoptero F450 + GoPro HERO13 Nadir (-90°) + Telemetria 915 MHz + Formato DJI Mini 2 SE")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 44, letter[0] - 54, 44)
        self.restoreState()

def generar_pdf(ruta_pdf):
    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    # Paleta de colores sobria y corporativa
    c_primario = colors.HexColor("#0F2942")     # Azul marino institucional
    c_secundario = colors.HexColor("#1A5F7A")   # Azul petroleo
    c_acento = colors.HexColor("#2C7A7B")       # Turquesa oscuro
    c_texto = colors.HexColor("#1E293B")        # Gris carbon
    c_fondo_tabla = colors.HexColor("#F8FAFC")  # Gris claro
    c_borde = colors.HexColor("#CBD5E1")        # Borde sutil
    c_verde = colors.HexColor("#15803D")        # Verde bosque
    c_verde_fondo = colors.HexColor("#F0FDF4")  # Fondo verde tenue
    c_alerta_fondo = colors.HexColor("#FFFBEB") # Fondo amarillo tenue

    # Tipografias y Estilos
    t_portada = ParagraphStyle(
        'TituloPortada', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=18, leading=22, textColor=c_primario, spaceAfter=6
    )
    sub_portada = ParagraphStyle(
        'SubPortada', parent=styles['Normal'],
        fontName='Helvetica', fontSize=10, leading=14, textColor=c_secundario, spaceAfter=14
    )
    h1 = ParagraphStyle(
        'H1', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=c_primario,
        spaceBefore=14, spaceAfter=6, keepWithNext=True
    )
    h2 = ParagraphStyle(
        'H2', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=c_secundario,
        spaceBefore=8, spaceAfter=4, keepWithNext=True
    )
    p = ParagraphStyle(
        'Cuerpo', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12, textColor=c_texto, spaceAfter=4
    )
    p_bold = ParagraphStyle('CuerpoB', parent=p, fontName='Helvetica-Bold')
    p_code = ParagraphStyle(
        'Codigo', parent=styles['Normal'],
        fontName='Courier', fontSize=7.5, leading=10, textColor=colors.HexColor("#0F172A")
    )
    p_callout = ParagraphStyle(
        'Callout', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, leading=11, textColor=c_verde
    )

    story = []

    # =========================================================================
    # PORTADA E IDENTIFICACION
    # =========================================================================
    story.append(Paragraph("UNIVERSIDAD TECNOLOGICA DEL URUGUAY (UTEC)", ParagraphStyle('Inst', fontName='Helvetica-Bold', fontSize=9.5, textColor=c_acento, leading=12)))
    story.append(Paragraph("PROGRAMA DE INVESTIGACION EN INFORMATICA APLICADA (PRIA)", ParagraphStyle('Prog', fontName='Helvetica', fontSize=8, textColor=colors.HexColor("#64748B"), leading=10)))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primario, spaceBefore=0, spaceAfter=8))
    
    story.append(Paragraph("INFORME TECNICO Y MANUAL OPERATIVO INTEGRAL", t_portada))
    story.append(Paragraph("Plataforma Aerofotogrametrica UAV para Deteccion de Hormigas Cortadoras:<br/>Cuadricoptero F450 + GoPro HERO13 Nadir (-90°) + Telemetria 915 MHz y Formato Nativo DJI Mini 2 SE", sub_portada))

    meta_tabla = [
        [Paragraph("<b>Proyecto:</b>", p), Paragraph("Deteccion y mapeo aereo de caminos y nidos de hormigas cortadoras (*Acromyrmex* y *Atta*).", p)],
        [Paragraph("<b>Plataforma Aerea:</b>", p), Paragraph("Cuadricoptero F450 | Controladora Pixhawk 2.4.8 (ArduCopter) | GNSS u-blox M8N.", p)],
        [Paragraph("<b>Sensor Optico:</b>", p), Paragraph("GoPro HERO13 Black fija en soporte Nadir (-90.0°) con estabilizacion HyperSmooth.", p)],
        [Paragraph("<b>Enlace de Telemetria:</b>", p), Paragraph("Radio SiK 915 MHz 500 mW | Enlace MAVLink serie a 57600 baudios (COM10).", p)],
        [Paragraph("<b>Estacion de Control:</b>", p), Paragraph("Dashboard Web local (http://localhost:8000) con autoescaneo activo y descarga USB.", p)],
        [Paragraph("<b>Formato de Salida:</b>", p), Paragraph("Fotogramas 4K con metadatos nativos <b>DJI Mini 2 SE</b> (EXIF + XMP drone-dji) para WebODM.", p)],
    ]
    t_m = Table(meta_tabla, colWidths=[120, 384])
    t_m.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_m)
    story.append(Spacer(1, 8))

    # =========================================================================
    # RESUMEN EJECUTIVO
    # =========================================================================
    story.append(Paragraph("1. Resumen Ejecutivo de Desarrollos e Implementaciones", h1))
    story.append(Paragraph(
        "El presente informe consolida la totalidad de los desarrollos tecnicos, integraciones de hardware y herramientas de software "
        "desarrolladas para el prototipo UAV de relevamiento aerofotogrametrico silvopastoril:",
        p
    ))
    resumen_items = [
        ("Configuracion de Hardware F450:", "Ensamble integral de cuadricoptero con Pixhawk 2.4.8, receptor GNSS M8N elevado en mastil de 14 cm, y radioenlace de 915 MHz (500 mW) con recepcion en tierra en COM10."),
        ("Calibracion de Bateria LiPo 3S:", "Configuracion de divisor de tension resistivo en entradas ADC de la Pixhawk (Pines 13 y 14) con multiplicador 10.1, sensado continuo a 4 Hz y alarmas de seguridad parametrizadas."),
        ("Soporte Optico Nadir sin Gimbal:", "Anclaje rigido cenital a -90.0° impreso en 3D para GoPro HERO13 Black, prescindiendo de cardan mecanico para maximizar la autonomia y empleando la estabilizacion electronica interna HyperSmooth."),
        ("Estacion Terrena (Dashboard Web):", "Servidor local en FastAPI y panel HTML5/JS (http://localhost:8000) con autoescaneo activo de hardware previo, monitoreo en tiempo real y registro simultaneo en CSV y tlog."),
        ("Captura de Video 4K a 30 FPS:", "Configuracion automatica de la camara a 4K 30 FPS con confirmacion activa mediante consulta de registro de estado del sensor de codificacion (status 10 = 1)."),
        ("Desacople Dinamico en Vuelo:", "Mecanismo de operacion en dos fases: configuracion inicial por cable USB y desacople fisico para el vuelo, donde la camara continua grabando de forma autonoma en su tarjeta microSD."),
        ("Motor de Georreferenciacion DJI:", "Modulo que descompone el video 4K en fotogramas a 1 FPS con OpenCV, calcula tiempos sub-segundo exactos, interpola la telemetria MAVLink e incrusta metadatos nativos DJI Mini 2 SE en lote."),
        ("Roadmap de Navegacion Autonoma:", "Especificacion tecnica y plan de pruebas para la ejecucion futura de grillas fotogrametricas automatizadas mediante protocolo MAVLink MISSION_ITEM_INT.")
    ]
    t_res = []
    for tit, desc in resumen_items:
        t_res.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_res_table = Table(t_res, colWidths=[150, 354])
    t_res_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_res_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # SINTESIS DEL SISTEMA Y DIAGRAMA
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Sintesis del Sistema y Arquitectura en Bloques", h1))
    story.append(Paragraph(
        "El sistema resuelve de extremo a extremo la captura de informacion aerea, desde el vuelo de la aeronave hasta la generacion de un conjunto de imagenes listo para la deteccion de senderos de hormigas cortadoras en la plataforma AntTrack o el procesamiento ortomosaico en WebODM:",
        p
    ))

    # Tabla diagrama arquitectonico
    diag_bloques = [
        [Paragraph("<b>Nivel / Subsistema</b>", p_bold), Paragraph("<b>Componentes y Procesos Involucrados</b>", p_bold), Paragraph("<b>Salida / Funcion</b>", p_bold)],
        [
            Paragraph("<b>1. Segmento Aereo (F450)</b>", p),
            Paragraph("Pixhawk 2.4.8 (ArduCopter), LiPo 3S con Power Module, GNSS M8N, GoPro HERO13 Nadir (-90°) y Radio 915 MHz.", p),
            Paragraph("Captura continua de video 4K 30 FPS y transmision de telemetria a 4 Hz.", p)
        ],
        [
            Paragraph("<b>2. Enlaces de Comunicacion</b>", p),
            Paragraph("Inalambrico: Radio SiK 915 MHz (MAVLink serie a 57600 bps).<br/>Fisico: Cable USB-C Open GoPro (pre y post-vuelo).", p),
            Paragraph("Transmision de paquetes de estado y descarga rapida de archivos a la PC.", p)
        ],
        [
            Paragraph("<b>3. Estacion Terrena (GCS)</b>", p),
            Paragraph("Dashboard web local (http://localhost:8000) bajo FastAPI.<br/>Autoescaneo de radio, bateria y camara.", p),
            Paragraph("Supervision del vuelo y guardado de telemetria.csv y telemetria.tlog.", p)
        ],
        [
            Paragraph("<b>4. Motor de Georreferenciacion</b>", p),
            Paragraph("Script vincular_vuelo_dji.py con OpenCV y ExifTool batch.<br/>Extraccion de frames a 1 FPS e interpolacion temporal.", p),
            Paragraph("Inyeccion masiva de etiquetas nativas DJI Mini 2 SE en cada fotograma.", p)
        ],
        [
            Paragraph("<b>5. Destino de Datos</b>", p),
            Paragraph("Carpeta estructurada vuelos/NOMBRE_MISION/fotos/<br/>Subtitulos de telemetria video.SRT", p),
            Paragraph("Alimentacion directa a WebODM, Pix4D, QGIS y clasificador IA AntTrack.", p)
        ],
    ]
    t_diag = Table(diag_bloques, colWidths=[120, 244, 140])
    t_diag.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_diag)
    story.append(Spacer(1, 8))

    # =========================================================================
    # HARDWARE Y ESPECIFICACIONES TECNICAS
    # =========================================================================
    story.append(Paragraph("3. Prototipo UAV: Especificaciones y Calibracion", h1))
    
    spec_tabla = [
        [Paragraph("<b>Componente</b>", p_bold), Paragraph("<b>Especificacion Tecnica</b>", p_bold), Paragraph("<b>Detalle Operativo en el Proyecto</b>", p_bold)],
        [Paragraph("Chasis / Frame", p), Paragraph("F450 (4 brazos, 450 mm entre ejes diagonales)", p), Paragraph("Estructura compacta con tren rigido de despegue.", p)],
        [Paragraph("Autopiloto", p), Paragraph("Pixhawk 2.4.8 (STM32F427 / ArduCopter 4.x)", p), Paragraph("Control de actitud, orientacion y navegacion MAVLink.", p)],
        [Paragraph("GNSS / Brujula", p), Paragraph("Radiolink SE100 (u-blox M8N de 72 canales)", p), Paragraph("Montado en mastil de 14 cm para evitar ruidos magneticos.", p)],
        [Paragraph("Radio Telemetria", p), Paragraph("SiK / 3DR Radio 915 MHz (500 mW, 57600 baud)", p), Paragraph("Transmite telemetria en vivo a 4 Hz hacia la laptop (COM10).", p)],
        [Paragraph("Bateria de Vuelo", p), Paragraph("LiPo 3S (11.1 V nominal, 12.6 V carga max)", p), Paragraph("Monitoreo analogico calibrado en Pin 13 y Pin 14 de Pixhawk.", p)],
        [Paragraph("Camara Optica", p), Paragraph("GoPro HERO13 Black (Sensor 27 MP, Video 4K)", p), Paragraph("Modo 4K 30 FPS en soporte rigido Nadir cenital (-90.0°).", p)],
        [Paragraph("Estabilizacion", p), Paragraph("HyperSmooth integrado con bloqueo de horizonte", p), Paragraph("Estabilizacion electronica interna sin necesidad de gimbal.", p)],
    ]
    t_spec = Table(spec_tabla, colWidths=[95, 205, 204])
    t_spec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_spec)
    story.append(Spacer(1, 6))

    # Parametros EEPROM Bateria
    story.append(Paragraph("3.1. Calibracion de Bateria LiPo 3S en EEPROM Pixhawk", h2))
    story.append(Paragraph(
        "Se configuro y guardo en la memoria no volatil de la controladora la lectura exacta del divisor resistivo de tension y corriente:",
        p
    ))
    bat_params = [
        [Paragraph("<b>Parametro ArduCopter</b>", p_bold), Paragraph("<b>Valor Fijado</b>", p_bold), Paragraph("<b>Significado Tecnico y Funcion de Seguridad</b>", p_bold)],
        [Paragraph("BATT_MONITOR", p_code), Paragraph("4.0", p_code), Paragraph("Habilita sensado analogico de tension y corriente simultaneo.", p)],
        [Paragraph("BATT_VOLT_PIN", p_code), Paragraph("13.0", p_code), Paragraph("Pin ADC fisico 13 de la Pixhawk para la lectura de voltaje.", p)],
        [Paragraph("BATT_CURR_PIN", p_code), Paragraph("14.0", p_code), Paragraph("Pin ADC fisico 14 de la Pixhawk para la lectura de amperaje.", p)],
        [Paragraph("BATT_VOLT_MULT", p_code), Paragraph("10.1", p_code), Paragraph("Multiplicador calibrado del divisor resistivo (lectura real 11.8V).", p)],
        [Paragraph("BATT_LOW_VOLT", p_code), Paragraph("10.5 V", p_code), Paragraph("Alarma de bateria baja (3.5 V por celda). Alerta en panel web.", p)],
        [Paragraph("BATT_CRT_VOLT", p_code), Paragraph("10.2 V", p_code), Paragraph("Voltaje critico (3.4 V por celda). Dispara accion fail-safe de retorno.", p)],
    ]
    t_bat = Table(bat_params, colWidths=[110, 80, 314])
    t_bat.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_bat)
    story.append(Spacer(1, 8))

    # =========================================================================
    # ESTACION TERRENA Y DASHBOARD WEB
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Estacion Terrena: Dashboard Web y Autoescaneo Activo", h1))
    story.append(Paragraph(
        "Se implemento un servidor web local (FastAPI en Python y JavaScript asincrono) accesible en <b>http://localhost:8000</b>. "
        "Permite operar el sistema en campo mediante una interfaz amigable sin necesidad de comandos de consola:",
        p
    ))

    # Insertar imagenes si existen
    img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "imagenes")
    img_scan = os.path.join(img_dir, "dashboard_autoescaneo_ok.png")
    img_rec = os.path.join(img_dir, "dashboard_grabando_en_vivo.png")

    if os.path.exists(img_scan):
        story.append(Paragraph("<b>Figura 1:</b> Panel del Dashboard con Autoescaneo Activo de Hardware Verificado.", h2))
        story.append(Image(img_scan, width=440, height=275))
        story.append(Spacer(1, 6))

    if os.path.exists(img_rec):
        story.append(Paragraph("<b>Figura 2:</b> Estado de Grabacion en Vivo y Telemetria a 4 Hz Recibida por Radio 915 MHz.", h2))
        story.append(Image(img_rec, width=440, height=275))
        story.append(Spacer(1, 8))

    # =========================================================================
    # MOTOR DE GEORREFERENCIACION Y METADATOS DJI
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Motor de Post-Procesamiento y Georreferenciacion DJI Mini 2 SE", h1))
    story.append(Paragraph(
        "Para lograr compatibilidad directa con WebODM, Pix4D y SIG sin necesidad de configuraciones manuales de camara, "
        "el software inyecta en cada fotograma extraido las etiquetas exactas que genera un dron comercial <b>DJI Mini 2 SE</b>:",
        p
    ))

    meta_dji_tabla = [
        [Paragraph("<b>Etiqueta EXIF / XMP</b>", p_bold), Paragraph("<b>Valor Inyectado</b>", p_bold), Paragraph("<b>Proposito y Funcion Fotogrametrica</b>", p_bold)],
        [Paragraph("Make", p_code), Paragraph("DJI", p_code), Paragraph("Identificador de fabricante reconocido automaticamente por WebODM.", p)],
        [Paragraph("Model", p_code), Paragraph("Mini 2 SE", p_code), Paragraph("Modelo de camara emulado para cargar perfiles de distorsion optica.", p)],
        [Paragraph("GPSLatitude", p_code), Paragraph("-34.895420 S", p_code), Paragraph("Latitud geodesica WGS-84 precisa al instante de la captura.", p)],
        [Paragraph("GPSLongitude", p_code), Paragraph("-56.162350 W", p_code), Paragraph("Longitud geodesica WGS-84 precisa al instante de la captura.", p)],
        [Paragraph("GPSAltitude", p_code), Paragraph("70.00 m MSL", p_code), Paragraph("Altitud ortometrica absoluta sobre el nivel medio del mar.", p)],
        [Paragraph("XMP-drone-dji:RelativeAltitude", p_code), Paragraph("+25.00 m", p_code), Paragraph("Altura relativa sobre el terreno. <b>Escala el tamano del pixel (GSD).</b>", p)],
        [Paragraph("XMP-drone-dji:GimbalPitchDegree", p_code), Paragraph("-90.0°", p_code), Paragraph("Inclinacion fija vertical cenital (posicion Nadir perpendicular).", p)],
        [Paragraph("XMP-drone-dji:GimbalRollDegree", p_code), Paragraph("0.0°", p_code), Paragraph("Horizonte nivelado por la tecnologia interna HyperSmooth de GoPro.", p)],
        [Paragraph("XMP-drone-dji:FlightYawDegree", p_code), Paragraph("145.8°", p_code), Paragraph("Rumbo real de la aeronave respecto al norte geografico.", p)],
        [Paragraph("XMP-drone-dji:FlightRollDegree", p_code), Paragraph("1.2°", p_code), Paragraph("Actitud fisica real de alabeo del cuadricoptero F450 en vuelo.", p)],
        [Paragraph("XMP-drone-dji:FlightPitchDegree", p_code), Paragraph("-1.5°", p_code), Paragraph("Actitud fisica real de cabeceo del cuadricoptero F450 en vuelo.", p)],
        [Paragraph("DateTimeOriginal", p_code), Paragraph("2026:11:19 17:30:00", p_code), Paragraph("Marca de tiempo UTC sincronizada con precision de sub-segundo.", p)],
    ]
    t_dji = Table(meta_dji_tabla, colWidths=[140, 110, 254])
    t_dji.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_dji)
    story.append(Spacer(1, 8))

    # =========================================================================
    # PROTOCOLO OPERATIVO DE CAMPO
    # =========================================================================
    story.append(Paragraph("6. Protocolo Operativo de Campo (Paso a Paso)", h1))
    
    pasos_campo = [
        [Paragraph("<b>Fase Operativa</b>", p_bold), Paragraph("<b>Acciones del Operador y Comportamiento del Sistema</b>", p_bold)],
        [
            Paragraph("<b>Paso 1: Pre-Vuelo (USB conectado)</b>", p),
            Paragraph(
                "1. Conectar receptor USB 915 MHz y cable USB-C de la GoPro a la laptop.<br/>"
                "2. Encender dron (bateria LiPo 3S conectada) y encender GoPro (modo GoPro Connect).<br/>"
                "3. Abrir http://localhost:8000. El autoescaneo verifica radio, bateria y camara en verde.<br/>"
                "4. Pulsar <b>[Sincronizar Relojes]</b> para calibrar hora camara-GPS (<0.05 s).<br/>"
                "5. Escribir nombre de mision y seleccionar frecuencia (1 foto/s = 90% solape).<br/>"
                "6. Pulsar <b>[Comenzar Grabacion]</b>: la camara se configura a 4K 30 FPS, inicia la grabacion confirmada por sensor (status 10=1) e inicia el registro a 4 Hz.",
                p
            )
        ],
        [
            Paragraph("<b>Paso 2: Vuelo (Autonomia en SD)</b>", p),
            Paragraph(
                "1. <b>Desconectar el cable USB de la GoPro con total tranquilidad:</b> la camara sigue grabando en su tarjeta microSD con su bateria interna Enduro.<br/>"
                "2. El panel web mantiene el estado en rojo: <b>GRABANDO EN VUELO (Autonoma en SD)</b>.<br/>"
                "3. Volar el dron sobre la parcela silvopastoril. Durante el vuelo, la radio 915 MHz transmite en vivo altura, posicion, orientacion y bateria 3S hacia la laptop.",
                p
            )
        ],
        [
            Paragraph("<b>Paso 3: Post-Vuelo (Descarga y Proceso)</b>", p),
            Paragraph(
                "1. Al aterrizar, volver a conectar el cable USB-C de la GoPro a la computadora.<br/>"
                "2. Pulsar <b>[Finalizar y Procesar]</b>: el sistema detiene la grabacion, descarga el video 4K original a vuelos/MISION/video/, divide los cuadros a 1 FPS con OpenCV, interpola la posicion GPS de cada cuadro e inyecta metadatos DJI Mini 2 SE en vuelos/MISION/fotos/.<br/>"
                "3. Al finalizar, pulsar <b>[Abrir Carpeta de Fotos (DJI)]</b> para cargar directamente en WebODM.",
                p
            )
        ],
    ]
    t_pasos = Table(pasos_campo, colWidths=[130, 374])
    t_pasos.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_pasos)
    story.append(Spacer(1, 8))

    # =========================================================================
    # DIFICULTADES Y MEDIDAS ADOPTADAS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("7. Dificultades Tecnicas y Medidas Adoptadas", h1))
    
    desvios = [
        ("Peso util y consumo de gimbal mecanico:", "El peso de un cardan comercial motorizado reducia la autonomia a menos de 7 minutos. Se prescindio de gimbal mecanico mediante un soporte rigido impreso en 3D a -90.0° cenital, aprovechando la estabilizacion electronica HyperSmooth propia de la GoPro HERO13."),
        ("Desconexion de cable USB en vuelo:", "La camara no puede volar con cable. Se desarrollo la logica de desconexion rapida (deteccion en 10 ms) manteniendo la bandera de grabacion activa mientras la camara graba en su microSD."),
        ("Incompatibilidad de metadatos genericos:", "Las imagenes EXIF estandar no proveian altura relativa para ortomosaicos a escala metrica en WebODM. Se desarrollo el modulo de emulacion de metadatos nativos DJI Mini 2 SE (XMP drone-dji) que resuelve la compatibilidad con un solo clic."),
        ("Lectura de bateria 3S:", "El conversor analogico de Pixhawk requeria calibracion precisa. Se programo el script de calibracion en EEPROM fijando multiplicador 10.1 con lecturas contrastadas con multimetro de banco.")
    ]
    t_desv = []
    for tit, desc in desvios:
        t_desv.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_desv_table = Table(t_desv, colWidths=[150, 354])
    t_desv_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_desv_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # PROXIMA ETAPA: NAVEGACION AUTONOMA
    # =========================================================================
    story.append(Paragraph("8. Proxima Etapa: Navegacion Autonoma por Waypoints", h1))
    story.append(Paragraph(
        "Como siguiente fase de desarrollo del prototipo UAV, se estructuro el plan de navegacion autonoma por grilla fotogrametrica:",
        p
    ))
    
    rutas_futuras = [
        ("Planificador de Grilla Fotogrametrica:", "Calculo automatico de pasadas paralelas sobre poligonos con solapamiento frontal del 80-90% y lateral del 70-80% a 25 m de altura (GSD de ~0.7 cm/pixel)."),
        ("Transmision de Misiones MAVLink:", "Implementacion del protocolo MISSION_ITEM_INT por radio 915 MHz hacia la memoria de la Pixhawk para ejecucion en modo de vuelo AUTO."),
        ("Sincronizacion de Eventos de Carga Util:", "Inicio automatico de grabacion al alcanzar el primer waypoint de relevamiento y retorno automatico a base (RTL) al finalizar la grilla."),
        ("Protecciones de Seguridad (Fail-Safe):", "Retorno automatico inmediato si la bateria LiPo 3S desciende de 10.5 V (FS_BATT_ENABLE=2) o ante perdida sostenida de enlace de 915 MHz por mas de 5 segundos.")
    ]
    t_fut = []
    for tit, desc in rutas_futuras:
        t_fut.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_fut_table = Table(t_fut, colWidths=[150, 354])
    t_fut_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_fut_table)
    story.append(Spacer(1, 8))

    # =========================================================================
    # ANEXOS Y REPOSITORIO
    # =========================================================================
    story.append(Paragraph("9. Anexos: Recursos y Repositorio de Codigo", h1))
    story.append(Paragraph(
        "Todo el codigo fuente, scripts de prueba, datos sinteticos e instructivos se encuentran sincronizados en el repositorio GitHub oficial:<br/>"
        "<b>https://github.com/UTEC-PRIA/Deteccion-de-hormigas-cortadoras</b> (Rama <code>main</code>)",
        p
    ))

    recursos_tabla = [
        [Paragraph("<b>Archivo / Carpeta</b>", p_bold), Paragraph("<b>Descripcion y Proposito</b>", p_bold)],
        [Paragraph("web_dashboard.py", p_code), Paragraph("Servidor local FastAPI y logica de autoescaneo, telemetria y descarga.", p)],
        [Paragraph("vincular_vuelo_dji.py", p_code), Paragraph("Motor de division de video 4K en fotos a 1 FPS e inyeccion batch de metadatos DJI.", p)],
        [Paragraph("configurar_bateria_3s.py", p_code), Paragraph("Script para calibrar los parametros ADC de bateria 3S en la EEPROM de Pixhawk.", p)],
        [Paragraph("generar_datos_artificiales.py", p_code), Paragraph("Generador de datasets sinteticos con video 4K, telemetria a 4 Hz y fotos DJI.", p)],
        [Paragraph("datos_artificiales/", p_code), Paragraph("Carpeta con mision sintetica completa para pruebas inmediatas sin vuelo.", p)],
        [Paragraph("docs/ROADMAP_NAVEGACION_WAYPOINTS_AUTONOMA.md", p_code), Paragraph("Documento de arquitectura para la futura fase de navegacion autonoma.", p)],
        [Paragraph("GUIA_PROMPTS_DIAGRAMAS_IA.md", p_code), Paragraph("Guia de prompts tecnicos para generar diagramas Mermaid e imagenes con IA.", p)],
    ]
    t_rec = Table(recursos_tabla, colWidths=[180, 324])
    t_rec.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_rec)

    # Construir PDF con NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Documento PDF generado exitosamente: {ruta_pdf}")
    return ruta_pdf

if __name__ == "__main__":
    salida = "Informe_Tecnico_Completo_UAV_UTEC_PRIA.pdf"
    if len(sys.argv) > 1:
        salida = sys.argv[1]
    generar_pdf(salida)
