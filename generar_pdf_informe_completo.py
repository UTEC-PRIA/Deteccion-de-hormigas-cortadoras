#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador Exhaustivo del Documento PDF Completo:
INFORME TECNICO Y MANUAL OPERATIVO INTEGRAL (CON DIAGRAMAS E ILUSTRACIONES)
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
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
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Encabezado (desde la pagina 2)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 32, "UTEC - PRIA | Prototipo UAV de Deteccion de Hormigas Cortadoras")
            self.drawRightString(letter[0] - 54, letter[1] - 32, "Informe Tecnico y Operativo Consolidado")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 38, letter[0] - 54, letter[1] - 38)
            
        # Pie de pagina
        texto_pie = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 32, texto_pie)
        self.drawString(54, 32, "Cuadricoptero F450 + GoPro HERO13 Nadir (-90°) + Telemetria 915 MHz + Formato DJI Mini 2 SE")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)
        self.restoreState()

def generar_pdf(ruta_pdf):
    doc = SimpleDocTemplate(
        ruta_pdf,
        pagesize=letter,
        leftMargin=50,
        rightMargin=50,
        topMargin=46,
        bottomMargin=46
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

    # Tipografias y Estilos
    t_portada = ParagraphStyle(
        'TituloPortada', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=c_primario, spaceAfter=5
    )
    sub_portada = ParagraphStyle(
        'SubPortada', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=c_secundario, spaceAfter=10
    )
    h1 = ParagraphStyle(
        'H1', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=11.5, leading=15, textColor=c_primario,
        spaceBefore=12, spaceAfter=5, keepWithNext=True
    )
    h2 = ParagraphStyle(
        'H2', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9.5, leading=13, textColor=c_secundario,
        spaceBefore=7, spaceAfter=3, keepWithNext=True
    )
    p = ParagraphStyle(
        'Cuerpo', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.2, leading=11.5, textColor=c_texto, spaceAfter=3.5
    )
    p_bold = ParagraphStyle('CuerpoB', parent=p, fontName='Helvetica-Bold')
    p_code = ParagraphStyle(
        'Codigo', parent=styles['Normal'],
        fontName='Courier', fontSize=7.2, leading=9.5, textColor=colors.HexColor("#0F172A")
    )
    caption = ParagraphStyle(
        'Caption', parent=styles['Normal'],
        fontName='Helvetica-Oblique', fontSize=7.5, leading=10, textColor=colors.HexColor("#475569"),
        alignment=1, spaceBefore=3, spaceAfter=6
    )

    story = []
    base_img = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "imagenes")

    # =========================================================================
    # PORTADA E IDENTIFICACION INSTITUCIONAL
    # =========================================================================
    story.append(Paragraph("UNIVERSIDAD TECNOLOGICA DEL URUGUAY (UTEC)", ParagraphStyle('Inst', fontName='Helvetica-Bold', fontSize=9, textColor=c_acento, leading=11)))
    story.append(Paragraph("PROGRAMA DE INVESTIGACION EN INFORMATICA APLICADA (PRIA) | SISTEMAS SILVOPASTORILES", ParagraphStyle('Prog', fontName='Helvetica', fontSize=7.5, textColor=colors.HexColor("#64748B"), leading=9.5)))
    story.append(Spacer(1, 3))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primario, spaceBefore=0, spaceAfter=6))
    
    story.append(Paragraph("INFORME TECNICO Y MANUAL OPERATIVO INTEGRAL", t_portada))
    story.append(Paragraph("Plataforma Aerofotogrametrica UAV para Deteccion de Hormigas Cortadoras:<br/>Cuadricoptero F450 + GoPro HERO13 Nadir (-90°) + Telemetria 915 MHz y Formato Nativo DJI Mini 2 SE", sub_portada))

    meta_tabla = [
        [Paragraph("<b>Proyecto:</b>", p), Paragraph("Deteccion y monitoreo de caminos y nidos de hormigas cortadoras (*Acromyrmex* y *Atta*) en sistemas silvopastoriles.", p)],
        [Paragraph("<b>Plataforma Aerea:</b>", p), Paragraph("Cuadricoptero F450 | Controladora Pixhawk 2.4.8 (ArduCopter 4.x) | Brujula y GNSS u-blox M8N en mastil.", p)],
        [Paragraph("<b>Carga Util Optica:</b>", p), Paragraph("GoPro HERO13 Black en anclaje rigido Nadir (-90.0°) con estabilizacion electronica HyperSmooth.", p)],
        [Paragraph("<b>Enlace de Datos:</b>", p), Paragraph("Radio SiK 915 MHz 500 mW (MAVLink serie a 57600 baudios, COM10) + Enlace USB-C Open GoPro.", p)],
        [Paragraph("<b>Estacion Terrena:</b>", p), Paragraph("Dashboard Web local (http://localhost:8000) bajo FastAPI con autoescaneo activo de hardware previo.", p)],
        [Paragraph("<b>Formato de Salida:</b>", p), Paragraph("Fotogramas 4K con metadatos nativos <b>DJI Mini 2 SE</b> (EXIF WGS-84 + XMP drone-dji) para WebODM y QGIS.", p)],
    ]
    t_m = Table(meta_tabla, colWidths=[115, 397])
    t_m.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_m)
    story.append(Spacer(1, 6))

    # =========================================================================
    # 1. RESUMEN EJECUTIVO
    # =========================================================================
    story.append(Paragraph("1. Resumen Ejecutivo de Desarrollos e Implementaciones", h1))
    story.append(Paragraph(
        "El presente documento consolida la totalidad de la arquitectura de hardware, desarrollos de software, algoritmos de georreferenciacion, "
        "protocolos de calibracion y ensayos de campo realizados para la puesta a punto del prototipo aereo de investigacion:",
        p
    ))

    resumen_items = [
        ("Configuracion de Hardware F450:", "Ensamble completo de cuadricoptero con controladora Pixhawk 2.4.8, receptor GNSS u-blox M8N en mastil vertical aislado de 14 cm, y radioenlace de 915 MHz a 500 mW comunicando con estacion terrena en COM10."),
        ("Calibracion de Bateria LiPo 3S:", "Configuracion precisa de divisor resistivo de tension y corriente en la EEPROM de Pixhawk (Pines ADC 13 y 14, multiplicador 10.1). Alarmas de seguridad en 10.5 V (baja) y 10.2 V (critico con retorno RTL)."),
        ("Soporte Optico Cenital sin Gimbal:", "Anclaje rigido Nadir (-90.0°) impreso en 3D adosado al vientre del dron. Se prescinde de cardan mecanico para maximizar la autonomia de vuelo, aprovechando la estabilizacion electronica HyperSmooth de la GoPro HERO13."),
        ("Estacion Terrena (Dashboard Web):", "Servidor local en FastAPI y panel HTML5/JS (http://localhost:8000) con autoescaneo activo de hardware previo, monitoreo en vivo de altura relativa, satelites y bateria, y guardado simultaneo en telemetria.csv y telemetria.tlog."),
        ("Captura de Video 4K a 30 FPS:", "Configuracion automatica de la camara en Modo Video 4K (Preset 1000, 3840x2160 @ 30 FPS). Comprobacion activa del sensor de codificacion interno de la camara (status 10 = 1) antes del despegue."),
        ("Desacople Dinamico en Vuelo:", "Operacion en dos fases: configuracion inicial en tierra por cable USB y posterior desconexion fisica para el vuelo, donde la camara continua grabando de forma autonoma e ininterrumpida en su tarjeta microSD."),
        ("Motor de Georreferenciacion DJI:", "Modulo que descompone el video 4K en fotogramas a 1 FPS con OpenCV, calcula tiempos sub-segundo exactos, interpola la posicion GPS de cada cuadro e inyecta metadatos nativos DJI Mini 2 SE en lote (batch)."),
        ("Roadmap de Navegacion Autonoma:", "Planificacion tecnica para la futura ejecucion de grillas fotogrametricas automatizadas mediante protocolo MAVLink MISSION_ITEM_INT con calculo de solape frontal (90%) y lateral (75%).")
    ]
    t_res = []
    for tit, desc in resumen_items:
        t_res.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_res_table = Table(t_res, colWidths=[150, 362])
    t_res_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t_res_table)

    # =========================================================================
    # 2. SINTESIS DEL SISTEMA Y ARQUITECTURA EN BLOQUES
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Sintesis del Sistema y Arquitectura General en Bloques", h1))
    story.append(Paragraph(
        "El sistema integra armonicamente el segmento aereo de vuelo, los enlaces de radiofrecuencia y cable, la estacion de control en tierra "
        "y el pipeline de procesamiento post-vuelo para generar ortomosaicos georreferenciados a escala milimetrica:",
        p
    ))

    # Insertar Diagrama de Arquitectura
    img_arq = os.path.join(base_img, "diagrama_arquitectura_sistema.png")
    if os.path.exists(img_arq):
        story.append(Image(img_arq, width=500, height=310))
        story.append(Paragraph("<b>Figura 1:</b> Arquitectura integral del sistema aerofotogrametrico UAV (Segmento Aereo, Enlaces, GCS y Motor de Georreferenciacion).", caption))

    story.append(Paragraph(
        "La informacion fluye de manera coordinada: la controladora Pixhawk registra las variables inerciales y satelitales mientras la GoPro "
        "captura el terreno a 4K 30 FPS. Al finalizar el vuelo, ambos flujos temporales convergen en el motor de vinculacion, produciendo "
        "imagenes compatibles con cualquier plataforma de fotogrametria profesional sin intervencion manual.",
        p
    ))

    # =========================================================================
    # 3. CICLO OPERATIVO EN TRES FASES
    # =========================================================================
    story.append(Spacer(1, 4))
    story.append(Paragraph("3. Ciclo Operativo de Mision en Tres Fases (Operator-Proof)", h1))
    story.append(Paragraph(
        "El flujo en campo fue disenado para evitar errores operativos humanos, estableciendo un protocolo claro de tres etapas consecutivas:",
        p
    ))

    # Insertar Diagrama de Ciclo Operativo
    img_ciclo = os.path.join(base_img, "diagrama_flujo_estados.png")
    if os.path.exists(img_ciclo):
        story.append(Image(img_ciclo, width=500, height=240))
        story.append(Paragraph("<b>Figura 2:</b> Ciclo operativo en tres fases: Pre-Vuelo por USB, Vuelo Autonomo en SD y Post-Vuelo con Extraccion y Georreferenciacion.", caption))

    # =========================================================================
    # 4. ESPECIFICACIONES DE HARDWARE Y CALIBRACION DE BATERIA
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Prototipo UAV: Componentes y Calibracion de Bateria LiPo 3S", h1))
    story.append(Paragraph(
        "A continuacion se detallan los parametros fisicos del vehiculo aereo y la calibracion de seguridad del subsistema de energia:",
        p
    ))

    spec_tabla = [
        [Paragraph("<b>Subsistema</b>", p_bold), Paragraph("<b>Componente Seleccionado</b>", p_bold), Paragraph("<b>Especificacion y Rol Operativo</b>", p_bold)],
        [Paragraph("Estructura", p), Paragraph("Chasis F450 (Flame Wheel 450 mm)", p), Paragraph("Plataforma cuadricoptero rigida con tren de despegue elevado.", p)],
        [Paragraph("Autopiloto", p), Paragraph("Pixhawk 2.4.8 (STM32F427)", p), Paragraph("Firmware ArduCopter 4.x, control de actitud y modos Loiter/Auto/RTL.", p)],
        [Paragraph("Navegacion", p), Paragraph("Radiolink SE100 (u-blox M8N GNSS)", p), Paragraph("Mastil vertical de 14 cm. Recepcion simultanea GPS + GLONASS (14-18 sats).", p)],
        [Paragraph("Radioenlace", p), Paragraph("SiK / 3DR Radio 915 MHz (500 mW)", p), Paragraph("Transmision MAVLink de telemetria a 4 Hz hacia estacion terrena (COM10).", p)],
        [Paragraph("Alimentacion", p), Paragraph("Bateria LiPo 3S (11.1 V nom, 12.6 V max)", p), Paragraph("Sensor analogico de tension y corriente en Pines ADC 13 y 14 de Pixhawk.", p)],
        [Paragraph("Camara", p), Paragraph("GoPro HERO13 Black (Sensor 27 MP)", p), Paragraph("Video continuo 4K 30 FPS en soporte Nadir (-90.0°) con HyperSmooth.", p)],
    ]
    t_spec = Table(spec_tabla, colWidths=[90, 190, 232])
    t_spec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_spec)
    story.append(Spacer(1, 4))

    # Insertar Grafico de Bateria LiPo 3S
    img_bat = os.path.join(base_img, "curva_calibracion_bateria_3s.png")
    if os.path.exists(img_bat):
        story.append(Image(img_bat, width=440, height=230))
        story.append(Paragraph("<b>Figura 3:</b> Curva de descarga de bateria LiPo 3S y umbrales de seguridad calibrados en la EEPROM de la controladora Pixhawk.", caption))

    bat_params = [
        [Paragraph("<b>Parametro</b>", p_code), Paragraph("<b>Valor</b>", p_code), Paragraph("<b>Accion de Seguridad / Funcion en Pixhawk</b>", p)],
        [Paragraph("BATT_MONITOR", p_code), Paragraph("4.0", p_code), Paragraph("Habilita sensado analogico de tension y corriente simultaneo.", p)],
        [Paragraph("BATT_VOLT_PIN", p_code), Paragraph("13.0", p_code), Paragraph("Pin fisico ADC 13 de la Pixhawk para la lectura de tension.", p)],
        [Paragraph("BATT_VOLT_MULT", p_code), Paragraph("10.1", p_code), Paragraph("Multiplicador calibrado del divisor resistivo (lectura real 11.8 V comprobada).", p)],
        [Paragraph("BATT_LOW_VOLT", p_code), Paragraph("10.5 V", p_code), Paragraph("Alarma de bateria baja (3.5 V por celda). Alerta visible en panel web.", p)],
        [Paragraph("BATT_CRT_VOLT", p_code), Paragraph("10.2 V", p_code), Paragraph("Voltaje critico (3.4 V por celda). Dispara retorno y aterrizaje automatico (RTL).", p)],
    ]
    t_bat = Table(bat_params, colWidths=[105, 65, 342])
    t_bat.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_bat)

    # =========================================================================
    # 5. ESTACION TERRENA Y DASHBOARD WEB
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Estacion Terrena: Dashboard Web y Autoescaneo Activo", h1))
    story.append(Paragraph(
        "El dashboard unificado opera bajo FastAPI en <b>http://localhost:8000</b>. "
        "A continuacion se presentan las capturas reales de la interfaz en operacion:",
        p
    ))

    img_scan = os.path.join(base_img, "dashboard_autoescaneo_ok.png")
    img_rec = os.path.join(base_img, "dashboard_grabando_en_vivo.png")

    if os.path.exists(img_scan):
        story.append(Image(img_scan, width=450, height=270))
        story.append(Paragraph("<b>Figura 4:</b> Autoescaneo activo de hardware completado: Radio 915 MHz activa (179 paq/s), Bateria LiPo 3S (11.8V, 62%) y GoPro conectada con 93% de carga.", caption))

    if os.path.exists(img_rec):
        story.append(Image(img_rec, width=450, height=270))
        story.append(Paragraph("<b>Figura 5:</b> Estado de grabacion en vivo con telemetria a 4 Hz (altura relativa, modo de vuelo, coordenadas y rumbo actualizandose en tiempo real).", caption))

    # =========================================================================
    # 6. MOTOR DE GEORREFERENCIACION Y METADATOS DJI MINI 2 SE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("6. Motor de Post-Procesamiento y Estandarizacion DJI Mini 2 SE", h1))
    story.append(Paragraph(
        "Para que las imagenes resultantes puedan ser cargadas de forma nativa e inmediata en plataformas fotogrametricas como WebODM, "
        "Pix4D y sistemas SIG (QGIS / AntTrack), el modulo de vinculacion post-vuelo (<code>vincular_vuelo_dji.py</code>) descompone "
        "el video 4K a 1 FPS e incrusta el conjunto de etiquetas exacto que produce un dron <b>DJI Mini 2 SE</b>:",
        p
    ))

    meta_dji_tabla = [
        [Paragraph("<b>Etiqueta EXIF / XMP</b>", p_bold), Paragraph("<b>Valor de Muestra</b>", p_bold), Paragraph("<b>Funcion e Importancia en Fotogrametria</b>", p_bold)],
        [Paragraph("Make", p_code), Paragraph("DJI", p_code), Paragraph("Identificador de fabricante reconocido automaticamente por WebODM.", p)],
        [Paragraph("Model", p_code), Paragraph("Mini 2 SE", p_code), Paragraph("Modelo de camara emulado para aplicar parametros de calibracion optica.", p)],
        [Paragraph("GPSLatitude", p_code), Paragraph("-34.895420 S", p_code), Paragraph("Latitud geodesica WGS-84 interpolada al instante exacto del cuadro.", p)],
        [Paragraph("GPSLongitude", p_code), Paragraph("-56.162350 W", p_code), Paragraph("Longitud geodesica WGS-84 interpolada al instante exacto del cuadro.", p)],
        [Paragraph("GPSAltitude", p_code), Paragraph("70.00 m MSL", p_code), Paragraph("Altitud ortometrica absoluta sobre el nivel medio del mar.", p)],
        [Paragraph("XMP-drone-dji:RelativeAltitude", p_code), Paragraph("+25.00 m", p_code), Paragraph("<b>Altura sobre el suelo (despegue):</b> escala el tamano real del pixel (GSD).", p)],
        [Paragraph("XMP-drone-dji:GimbalPitchDegree", p_code), Paragraph("-90.0°", p_code), Paragraph("Camara apuntando perpendicularmente hacia el suelo (posicion Nadir cenital).", p)],
        [Paragraph("XMP-drone-dji:GimbalRollDegree", p_code), Paragraph("0.0°", p_code), Paragraph("Horizonte nivelado electronicamente por HyperSmooth.", p)],
        [Paragraph("XMP-drone-dji:FlightYawDegree", p_code), Paragraph("145.8°", p_code), Paragraph("Rumbo real de desplazamiento de la aeronave respecto al norte geografico.", p)],
        [Paragraph("XMP-drone-dji:FlightRollDegree", p_code), Paragraph("1.2°", p_code), Paragraph("Angulo real de alabeo fisico del cuadricoptero F450 en vuelo.", p)],
        [Paragraph("XMP-drone-dji:FlightPitchDegree", p_code), Paragraph("-1.5°", p_code), Paragraph("Angulo real de cabeceo fisico del cuadricoptero F450 en vuelo.", p)],
        [Paragraph("DateTimeOriginal", p_code), Paragraph("2026:11:19 17:30:00", p_code), Paragraph("Marca de tiempo sincronizada con precision de sub-segundo con GPS.", p)],
    ]
    t_dji = Table(meta_dji_tabla, colWidths=[140, 105, 267])
    t_dji.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_dji)
    story.append(Spacer(1, 4))

    story.append(Paragraph(
        "<b>Eficiencia del proceso por lotes:</b> En lugar de procesar imagen por imagen, el sistema genera un archivo CSV temporal consolidado "
        "y realiza una unica invocacion a ExifTool (<code>-csv=metadata.csv</code>). Esto permite georreferenciar mas de 300 fotogramas 4K "
        "en menos de 1.5 segundos, eliminando demoras en campo.",
        p
    ))

    # =========================================================================
    # 7. PROTOCOLO OPERATIVO DETALLADO DE CAMPO
    # =========================================================================
    story.append(Paragraph("7. Protocolo Operativo Detallado de Campo (Paso a Paso)", h1))
    
    pasos_campo = [
        [Paragraph("<b>Fase de Mision</b>", p_bold), Paragraph("<b>Procedimiento del Operador y Comportamiento del Sistema</b>", p_bold)],
        [
            Paragraph("<b>1. Pre-Vuelo (USB conectado)</b>", p),
            Paragraph(
                "1. Conectar receptor de 915 MHz y cable USB-C de la GoPro a la laptop de campo.<br/>"
                "2. Encender dron (LiPo 3S conectada) y GoPro (pantalla en modo GoPro Connect).<br/>"
                "3. Abrir http://localhost:8000. El autoescaneo confirma radio, bateria 3S y camara en verde.<br/>"
                "4. Presionar <b>[Sincronizar Relojes]</b> para calibrar la hora de la camara (<0.05 s).<br/>"
                "5. Ingresar nombre del vuelo y seleccionar frecuencia de extraccion (1 foto/s = 90% solape).<br/>"
                "6. Presionar <b>[Comenzar Grabacion]</b>: la camara se configura a 4K 30 FPS, el sensor confirma grabacion (status 10 = 1) e inicia el registro a 4 Hz.",
                p
            )
        ],
        [
            Paragraph("<b>2. Vuelo (Autonomia en SD)</b>", p),
            Paragraph(
                "1. <b>Desconectar el cable USB de la camara:</b> la GoPro HERO13 continuara grabando de forma autonoma e ininterrumpida en su tarjeta microSD con su bateria Enduro interna.<br/>"
                "2. El panel web confirma el estado activo en rojo pulsante: <b>GRABANDO EN VUELO (Autonoma en SD)</b>.<br/>"
                "3. Despegar y volar el dron sobre la parcela de interes. La radio de 915 MHz transmite en tiempo real altura, posicion GPS, actitud y tension LiPo 3S.",
                p
            )
        ],
        [
            Paragraph("<b>3. Post-Vuelo (Descarga y Proceso)</b>", p),
            Paragraph(
                "1. Aterrizar el vehiculo y volver a conectar el cable USB-C de la GoPro a la laptop.<br/>"
                "2. Presionar <b>[Finalizar y Procesar]</b>: el sistema detiene la grabacion, descarga el video 4K original a vuelos/MISION/video/, divide los cuadros a 1 FPS con OpenCV, interpola las coordenadas exactas de cada cuadro e incrusta los metadatos DJI Mini 2 SE en vuelos/MISION/fotos/.<br/>"
                "3. Presionar <b>[Abrir Carpeta de Fotos (DJI)]</b> para cargar el conjunto en WebODM o AntTrack.",
                p
            )
        ],
    ]
    t_pasos = Table(pasos_campo, colWidths=[120, 392])
    t_pasos.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_pasos)

    # =========================================================================
    # 8. DIFICULTADES TECNICAS Y MEDIDAS ADOPTADAS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("8. Dificultades Tecnicas Superadas y Medidas Adoptadas", h1))
    
    desvios = [
        ("Peso util y consumo de gimbal mecanico:", "El peso de un cardan comercial motorizado de 3 ejes reducia la autonomia de vuelo del F450 a menos de 7 minutos. Se prescindio del gimbal mecanico mediante un soporte rigido cenital impreso en 3D a -90.0°, aprovechando la estabilizacion electronica HyperSmooth con bloqueo de horizonte propia de la GoPro HERO13."),
        ("Desconexion del cable USB en vuelo:", "La aeronave debe volar sin cables. Se implemento un controlador de desconexion rapida (deteccion en 10 ms sin congelar el dashboard) que mantiene el estado de grabacion activo mientras la camara opera de forma autonoma con su bateria interna en su tarjeta microSD."),
        ("Incompatibilidad de metadatos genericos:", "Las imagenes con metadatos EXIF genericos carecian de parametros de altura relativa respecto al suelo (RelativeAltitude), impidiendo calcular la escala metrica en WebODM. Se desarrollo el vinculador de metadatos nativos DJI Mini 2 SE (XMP drone-dji) que soluciona la compatibilidad de forma directa."),
        ("Calibracion de bateria LiPo 3S:", "El conversor analogico de la Pixhawk 2.4.8 requeria calibracion precisa para evitar lecturas erroneas. Se programo el script de calibracion en EEPROM fijando multiplicador 10.1 con lecturas contrastadas con multimetro de banco.")
    ]
    t_desv = []
    for tit, desc in desvios:
        t_desv.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_desv_table = Table(t_desv, colWidths=[150, 362])
    t_desv_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_desv_table)
    story.append(Spacer(1, 6))

    # =========================================================================
    # 9. PROXIMA ETAPA: NAVEGACION AUTONOMA POR WAYPOINTS
    # =========================================================================
    story.append(Paragraph("9. Proxima Etapa: Navegacion Autonoma por Waypoints (ArduCopter)", h1))
    story.append(Paragraph(
        "Como siguiente fase de desarrollo del prototipo UAV, se estructuro la arquitectura de navegacion automatizada por grilla de escaneo:",
        p
    ))

    # Insertar Grafico de Grilla Fotogrametrica
    img_grilla = os.path.join(base_img, "diagrama_grilla_waypoints_futuro.png")
    if os.path.exists(img_grilla):
        story.append(Image(img_grilla, width=440, height=270))
        story.append(Paragraph("<b>Figura 6:</b> Especificacion de mision fotogrametrica autonoma en zigzag con solapes del 90% (frontal) y 75% (lateral) sobre parcela silvopastoril.", caption))

    rutas_futuras = [
        ("Planificador de Grilla Fotogrametrica:", "Calculo automatico de pasadas paralelas sobre poligonos con solapamiento frontal del 80-90% y lateral del 70-80% a 25 m de altura (GSD resultante de ~0.7 cm/pixel)."),
        ("Transmision de Misiones MAVLink:", "Implementacion del protocolo MISSION_ITEM_INT por radio de 915 MHz hacia la memoria EEPROM de la Pixhawk para ejecucion en modo de vuelo AUTO."),
        ("Sincronizacion de Eventos de Carga Util:", "Inicio automatico de grabacion de video 4K al alcanzar el primer waypoint de relevamiento y retorno automatico a base (RTL) al finalizar la grilla."),
        ("Politicas de Retorno Seguro (Fail-Safe):", "Retorno automatico inmediato si la bateria LiPo 3S desciende de 10.5 V (FS_BATT_ENABLE = 2) o ante perdida sostenida de enlace por mas de 5 segundos.")
    ]
    t_fut = []
    for tit, desc in rutas_futuras:
        t_fut.append([Paragraph(f"<b>{tit}</b>", p_bold), Paragraph(desc, p)])
    t_fut_table = Table(t_fut, colWidths=[150, 362])
    t_fut_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_fut_table)

    # =========================================================================
    # 10. ANEXOS Y RECURSOS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("10. Anexos: Recursos, Muestras de Datos y Repositorio", h1))
    story.append(Paragraph(
        "Todo el codigo fuente, scripts de prueba, datos sinteticos e instructivos se encuentran sincronizados en el repositorio GitHub oficial:<br/>"
        "<b>https://github.com/UTEC-PRIA/Deteccion-de-hormigas-cortadoras</b> (Rama <code>main</code>)",
        p
    ))

    recursos_tabla = [
        [Paragraph("<b>Archivo / Carpeta</b>", p_bold), Paragraph("<b>Descripcion y Proposito Tecnico</b>", p_bold)],
        [Paragraph("web_dashboard.py", p_code), Paragraph("Servidor local FastAPI, autoescaneo activo de hardware, telemetria a 4 Hz y descarga USB.", p)],
        [Paragraph("vincular_vuelo_dji.py", p_code), Paragraph("Motor de division de video 4K en cuadros a 1 FPS e inyeccion batch de metadatos DJI Mini 2 SE.", p)],
        [Paragraph("configurar_bateria_3s.py", p_code), Paragraph("Script para calibrar los parametros ADC de bateria LiPo 3S en la EEPROM de Pixhawk.", p)],
        [Paragraph("generar_datos_artificiales.py", p_code), Paragraph("Generador de datasets sinteticos con video 4K, telemetria a 4 Hz y fotos DJI para pruebas.", p)],
        [Paragraph("datos_artificiales/", p_code), Paragraph("Carpeta con mision sintetica completa para pruebas y validaciones sin necesidad de volar.", p)],
        [Paragraph("docs/ROADMAP_NAVEGACION_WAYPOINTS_AUTONOMA.md", p_code), Paragraph("Documento de arquitectura para la futura fase de navegacion autonoma.", p)],
        [Paragraph("GUIA_PROMPTS_DIAGRAMAS_IA.md", p_code), Paragraph("Guia de prompts tecnicos para generar diagramas Mermaid e ilustraciones con IA.", p)],
    ]
    t_rec = Table(recursos_tabla, colWidths=[175, 337])
    t_rec.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_rec)
    story.append(Spacer(1, 4))

    # Muestra de telemetria CSV
    story.append(Paragraph("10.1. Muestra Real de Registros en <code>telemetria.csv</code> (Frecuencia 4 Hz)", h2))
    story.append(Paragraph(
        "A continuacion se presenta un fragmento de las lineas registradas a traves de la radio de 915 MHz, "
        "con coordenadas WGS-84, altitud MSL, altitud relativa sobre el despegue, actitud angular, satelites y voltaje de bateria 3S:",
        p
    ))

    muestra_csv = [
        [Paragraph("<b>timestamp_utc</b>", p_code), Paragraph("<b>lat</b>", p_code), Paragraph("<b>lon</b>", p_code), Paragraph("<b>alt_rel</b>", p_code), Paragraph("<b>yaw</b>", p_code), Paragraph("<b>vel</b>", p_code), Paragraph("<b>bat_v</b>", p_code), Paragraph("<b>modo</b>", p_code)],
        [Paragraph("2026-11-19 17:30:00.000", p_code), Paragraph("-34.89542", p_code), Paragraph("-56.16235", p_code), Paragraph("25.0 m", p_code), Paragraph("145.8°", p_code), Paragraph("3.5 m/s", p_code), Paragraph("11.8 V", p_code), Paragraph("LOITER", p_code)],
        [Paragraph("2026-11-19 17:30:00.250", p_code), Paragraph("-34.89542", p_code), Paragraph("-56.16234", p_code), Paragraph("25.1 m", p_code), Paragraph("146.0°", p_code), Paragraph("3.5 m/s", p_code), Paragraph("11.8 V", p_code), Paragraph("LOITER", p_code)],
        [Paragraph("2026-11-19 17:30:00.500", p_code), Paragraph("-34.89543", p_code), Paragraph("-56.16233", p_code), Paragraph("25.0 m", p_code), Paragraph("146.1°", p_code), Paragraph("3.5 m/s", p_code), Paragraph("11.7 V", p_code), Paragraph("LOITER", p_code)],
        [Paragraph("2026-11-19 17:30:00.750", p_code), Paragraph("-34.89543", p_code), Paragraph("-56.16232", p_code), Paragraph("24.9 m", p_code), Paragraph("146.2°", p_code), Paragraph("3.5 m/s", p_code), Paragraph("11.7 V", p_code), Paragraph("LOITER", p_code)],
        [Paragraph("2026-11-19 17:30:01.000", p_code), Paragraph("-34.89544", p_code), Paragraph("-56.16231", p_code), Paragraph("25.0 m", p_code), Paragraph("146.3°", p_code), Paragraph("3.5 m/s", p_code), Paragraph("11.7 V", p_code), Paragraph("LOITER", p_code)],
    ]
    t_csv = Table(muestra_csv, colWidths=[120, 56, 56, 48, 42, 45, 45, 60])
    t_csv.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_fondo_tabla),
        ('BOX', (0, 0), (-1, -1), 0.5, c_borde),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_csv)

    # Construir PDF con NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Documento PDF generado exitosamente: {ruta_pdf}")
    return ruta_pdf

if __name__ == "__main__":
    salida = "Informe_Tecnico_Completo_UAV_UTEC_PRIA.pdf"
    if len(sys.argv) > 1:
        salida = sys.argv[1]
    generar_pdf(salida)
