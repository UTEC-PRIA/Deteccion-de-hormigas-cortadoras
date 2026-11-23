#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del Manual Operativo y Muestra de Datos en PDF (Actualizado con Dashboard Web)
Proyecto UAV UTEC-PRIA - Deteccion de Hormigas Cortadoras
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
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
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.HexColor("#4A5568"))
        
        # Encabezado (desde la pagina 2)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "UTEC PRIA | Proyecto UAV Deteccion de Hormigas Cortadoras")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)
            
        # Pie de pagina
        texto_pie = f"Pagina {self._pageNumber} de {page_count}"
        self.drawRightString(letter[0] - 54, 36, texto_pie)
        self.drawString(54, 36, "Manual de Operaciones y Estructura de Datos (Formato DJI Mini 2 SE)")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 48, letter[0] - 54, 48)
        self.restoreState()

def construir_pdf(ruta_salida):
    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Colores corporativos
    c_primario = colors.HexColor("#0F2942")     # Azul marino profundo
    c_secundario = colors.HexColor("#1A5F7A")   # Azul petroleo
    c_acento = colors.HexColor("#2C7A7B")       # Turquesa sobrio
    c_fondo_tabla = colors.HexColor("#F8FAFC")  # Gris muy suave
    c_texto = colors.HexColor("#1A202C")        # Gris carbon oscuro
    c_verde = colors.HexColor("#22543D")        # Verde bosque
    c_verde_fondo = colors.HexColor("#F0FDF4")  # Fondo verde claro

    # Estilos de texto
    titulo_principal = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primario,
        spaceAfter=8
    )
    
    subtitulo_portada = ParagraphStyle(
        'SubtituloPortada',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=c_secundario,
        spaceAfter=20
    )

    encabezado_1 = ParagraphStyle(
        'Encabezado1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=c_primario,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    encabezado_2 = ParagraphStyle(
        'Encabezado2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=c_secundario,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True
    )

    cuerpo = ParagraphStyle(
        'Cuerpo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=c_texto,
        spaceAfter=5
    )

    cuerpo_negrita = ParagraphStyle(
        'CuerpoNegrita',
        parent=cuerpo,
        fontName='Helvetica-Bold'
    )

    codigo = ParagraphStyle(
        'Codigo',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#2D3748")
    )

    callout_texto = ParagraphStyle(
        'CalloutTexto',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_verde
    )

    story = []

    # =========================================================================
    # PORTADA
    # =========================================================================
    story.append(Paragraph("UNIVERSIDAD TECNOLOGICA DEL URUGUAY (UTEC)", ParagraphStyle('UTEC', fontName='Helvetica-Bold', fontSize=10, textColor=c_acento, leading=12)))
    story.append(Paragraph("PROGRAMA DE INVESTIGACION APLICADA (PRIA)", ParagraphStyle('PRIA', fontName='Helvetica', fontSize=8.5, textColor=colors.HexColor("#718096"), leading=11)))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primario, spaceBefore=0, spaceAfter=12))
    
    story.append(Paragraph("Manual Operativo: Dashboard Web, Telemetria en Vivo y Formato DJI Mini 2 SE", titulo_principal))
    story.append(Paragraph("Sistema integral con interfaz grafica local (http://localhost:8000) para control de vuelo F450 (Pixhawk / ArduPilot), telemetria 915 MHz, sincronizacion y descarga automatica de fotos GoPro HERO13 Black.", subtitulo_portada))
    
    info_meta = [
        [Paragraph("<b>Plataforma UAV:</b>", cuerpo), Paragraph("Cuadricoptero F450 | Pixhawk 2.4.8 | GNSS Radiolink SE100 M8N", cuerpo)],
        [Paragraph("<b>Sensor Optico:</b>", cuerpo), Paragraph("GoPro HERO13 Black (Foto por intervalo / Video 4K / USB Open GoPro)", cuerpo)],
        [Paragraph("<b>Interfaz de Operador:</b>", cuerpo), Paragraph("Dashboard Web local (http://localhost:8000) con telemetria en vivo", cuerpo)],
        [Paragraph("<b>Enlace en el Aire:</b>", cuerpo), Paragraph("Radios de telemetria SiK 915 MHz (500 mW)", cuerpo)],
        [Paragraph("<b>Formato de Salida:</b>", cuerpo), Paragraph("Nativo DJI Mini 2 SE (EXIF estandar + XMP drone-dji) para WebODM / GIS", cuerpo)],
    ]
    t_meta = Table(info_meta, colWidths=[130, 374])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # =========================================================================
    # SECCION 1: INTERFAZ WEB LOCALHOST (COMO SE USA)
    # =========================================================================
    story.append(Paragraph("1. Operacion Mediante el Dashboard Web (http://localhost:8000)", encabezado_1))
    story.append(Paragraph(
        "Para que cualquier operador pueda utilizar el sistema en campo sin tocar codigo ni terminales, se dispone de un servidor web local. "
        "Al hacer doble clic en <b>iniciar_dashboard.bat</b> (Windows) o ejecutar <b>./iniciar_dashboard.sh</b> (Ubuntu), se abre de forma automatica su navegador en <code>http://localhost:8000</code>.",
        cuerpo
    ))

    elementos_web = [
        [Paragraph("<b>Componente en Pantalla</b>", cuerpo_negrita), Paragraph("<b>Funcionamiento y Accion</b>", cuerpo_negrita)],
        [
            Paragraph("<b>Panel Pre-Vuelo (Cables conectados)</b>", cuerpo),
            Paragraph("Muestra el estado de la GoPro y la Pixhawk. Al pulsar <b>[Sincronizar Relojes]</b>, el reloj de la camara se calibra con la hora exacta del GPS y el sistema toma nota de las fotos previas.", cuerpo)
        ],
        [
            Paragraph("<b>Boton [Comenzar Grabacion]</b>", cuerpo),
            Paragraph("Conecta la antena de 915 MHz e inicia la grabacion continua de la trayectoria del dron en vivo.", cuerpo)
        ],
        [
            Paragraph("<b>Panel de Telemetria en Vivo</b>", cuerpo),
            Paragraph("Muestra en tiempo real: Altura sobre el suelo (metros), Modo de vuelo (Loiter, Auto, etc.), Voltaje de bateria de la LiPo, Satelites GPS, Rumbo (grados) y Coordenadas.", cuerpo)
        ],
        [
            Paragraph("<b>Boton [Finalizar y Procesar]</b>", cuerpo),
            Paragraph("Detiene la telemetria, se conecta a la GoPro por cable USB, <b>descarga automaticamente a la computadora solo las fotos nuevas del vuelo</b> y les inyecta los metadatos de DJI Mini 2 SE.", cuerpo)
        ],
    ]
    t_web = Table(elementos_web, colWidths=[160, 344])
    t_web.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_web)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECCION 2: MUESTRA DE DATOS RESULTANTES
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Muestra y Estructura de los Datos Resultantes", encabezado_1))
    story.append(Paragraph(
        "Al finalizar el proceso, las fotografias de la GoPro HERO13 son transformadas internamente para que contengan exactamente la misma estructura de metadatos que genera un dron <b>DJI Mini 2 SE</b>. "
        "A continuacion se muestra la comparacion y el significado practico de cada dato incrustado:",
        cuerpo
    ))

    datos_muestra = [
        [Paragraph("<b>Etiqueta de Metadato</b>", cuerpo_negrita), Paragraph("<b>Valor Inyectado de Ejemplo</b>", cuerpo_negrita), Paragraph("<b>Significado practico en fotogrametria e IA</b>", cuerpo_negrita)],
        [Paragraph("<b>Make</b>", codigo), Paragraph("DJI", codigo), Paragraph("Fabricante reconocido automaticamente por WebODM, Pix4D y Metashape.", cuerpo)],
        [Paragraph("<b>Model</b>", codigo), Paragraph("Mini 2 SE", codigo), Paragraph("Modelo de aeronave. El software aplica los perfiles de calibracion adecuados.", cuerpo)],
        [Paragraph("<b>GPSLatitude</b>", codigo), Paragraph("-34.582104 (34°34'55.6\" S)", codigo), Paragraph("Coordenada Norte/Sur de la posicion de la camara al disparar.", cuerpo)],
        [Paragraph("<b>GPSLongitude</b>", codigo), Paragraph("-58.421590 (58°25'17.7\" W)", codigo), Paragraph("Coordenada Este/Oeste de la posicion de la camara al disparar.", cuerpo)],
        [Paragraph("<b>GPSAltitude</b>", codigo), Paragraph("68.50 m (MSL)", codigo), Paragraph("Altura sobre el nivel medio del mar segun el elipsoide WGS-84.", cuerpo)],
        [Paragraph("<b>drone-dji:RelativeAltitude</b>", codigo), Paragraph("+25.30 m", codigo), Paragraph("<b>Altura sobre el suelo / despegue.</b> Fundamental para calcular la escala metrica del pixel y medir el ancho de los caminos de hormigas.", cuerpo)],
        [Paragraph("<b>drone-dji:AbsoluteAltitude</b>", codigo), Paragraph("+68.50 m", codigo), Paragraph("Altura geodesica de vuelo con signo positivo para referencia topografica.", cuerpo)],
        [Paragraph("<b>drone-dji:GimbalPitchDegree</b>", codigo), Paragraph("-90.0°", codigo), Paragraph("Inclinacion del lente. -90° significa vista perpendicular hacia el suelo (Nadir), estandar para mapas.", cuerpo)],
        [Paragraph("<b>drone-dji:FlightYawDegree</b>", codigo), Paragraph("145.8°", codigo), Paragraph("Rumbo o brújula del dron (0° a 360°). Indica hacia donde apuntaba el frente de la nave.", cuerpo)],
        [Paragraph("<b>drone-dji:FlightRollDegree</b>", codigo), Paragraph("1.2°", codigo), Paragraph("Inclinacion lateral del dron por correccion de viento. Permite ortorrectificar la foto.", cuerpo)],
        [Paragraph("<b>drone-dji:FlightPitchDegree</b>", codigo), Paragraph("-0.5°", codigo), Paragraph("Inclinacion longitudinal de avance. Corrige distorsion en mosaicos 2D.", cuerpo)],
        [Paragraph("<b>drone-dji:FlightXSpeed / YSpeed</b>", codigo), Paragraph("2.3 m/s / 0.8 m/s", codigo), Paragraph("Velocidades vectoriales. Util para descartar fotos movidas por rafagas de viento.", cuerpo)],
    ]
    t_datos = Table(datos_muestra, colWidths=[140, 150, 214])
    t_datos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_primario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_datos)
    story.append(Spacer(1, 10))

    # Muestra del CSV en vivo
    story.append(Paragraph("2.1. Archivo CSV generado en tiempo real durante el vuelo (telemetria.csv)", encabezado_2))
    muestra_csv = [
        [Paragraph("<b>timestamp_utc</b>", codigo), Paragraph("<b>latitud</b>", codigo), Paragraph("<b>longitud</b>", codigo), Paragraph("<b>alt_rel</b>", codigo), Paragraph("<b>yaw</b>", codigo), Paragraph("<b>bat_v</b>", codigo), Paragraph("<b>modo</b>", codigo)],
        [Paragraph("2026-11-20 10:14:02.250", codigo), Paragraph("-34.582104", codigo), Paragraph("-58.421590", codigo), Paragraph("25.30", codigo), Paragraph("145.8", codigo), Paragraph("11.6V", codigo), Paragraph("AUTO", codigo)],
        [Paragraph("2026-11-20 10:14:02.500", codigo), Paragraph("-34.582110", codigo), Paragraph("-58.421598", codigo), Paragraph("25.35", codigo), Paragraph("145.9", codigo), Paragraph("11.6V", codigo), Paragraph("AUTO", codigo)],
    ]
    t_csv = Table(muestra_csv, colWidths=[120, 70, 70, 50, 45, 45, 104])
    t_csv.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2D3748")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#A0AEC0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_csv)
    story.append(Spacer(1, 10))

    # =========================================================================
    # SECCION 3: PROTOCOLO DE CAMPO
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Protocolo de Operacion de Campo (Checklist)", encabezado_1))

    aviso_antena = [
        [Paragraph(
            "<b>REGLA OBLIGATORIA DE SEGURIDAD PARA RADIOS DE 915 MHz:</b><br/>"
            "Enrosque firmemente las antenas ANTES de conectar las radios a la computadora o encender el dron. "
            "Emitir radiofrecuencia a 500 mW sin antena puede danar el transmisor en cuestion de segundos.",
            callout_texto
        )]
    ]
    t_aviso = Table(aviso_antena, colWidths=[504])
    t_aviso.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_verde_fondo),
        ('BOX', (0, 0), (-1, -1), 1, c_verde),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_aviso)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.1. En la Base (Antes de despegar)", encabezado_2))
    story.append(Paragraph(
        "1. Conecte la GoPro por USB-C (en modo <i>GoPro Connect</i>) y la Pixhawk por USB.<br/>"
        "2. Ejecute <code>iniciar_dashboard.bat</code> (Windows) o <code>./iniciar_dashboard.sh</code> (Ubuntu). Se abrira <code>http://localhost:8000</code>.<br/>"
        "3. Haga clic en <b>[Sincronizar Relojes]</b>. Verifique el aviso verde de confirmacion y el porcentaje de bateria.<br/>"
        "4. Desconecte la camara y montela perpendicular al suelo (Nadir) en el dron.",
        cuerpo
    ))

    story.append(Paragraph("3.2. Durante el Vuelo", encabezado_2))
    story.append(Paragraph(
        "1. Conecte la antena receptora USB de 915 MHz a la laptop.<br/>"
        "2. En la pagina web, haga clic en <b>[Comenzar Grabacion]</b>. Vera la telemetria actualizandose en vivo.<br/>"
        "3. Inicie la grabacion o toma de fotos en la GoPro y realice el vuelo planificado.<br/>"
        "4. Al aterrizar el dron, conecte la GoPro por cable USB a la computadora y haga clic en <b>[Finalizar y Procesar]</b>.<br/>"
        "5. El sistema descargara automaticamente las fotos nuevas tomadas en el vuelo, les inyectara los metadatos DJI Mini 2 SE y le ofrecera un boton para abrir la carpeta de resultados.",
        cuerpo
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Documento PDF actualizado: {ruta_salida}")

if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "informes", "Manual_Operativo_Telemetria_GoPro_DJI.pdf")
    construir_pdf(salida)
