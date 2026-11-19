#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador del Manual Operativo y Muestra de Datos en PDF
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
        fontSize=22,
        leading=26,
        textColor=c_primario,
        spaceAfter=10
    )
    
    subtitulo_portada = ParagraphStyle(
        'SubtituloPortada',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=c_secundario,
        spaceAfter=25
    )

    encabezado_1 = ParagraphStyle(
        'Encabezado1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=c_primario,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    encabezado_2 = ParagraphStyle(
        'Encabezado2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=c_secundario,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    cuerpo = ParagraphStyle(
        'Cuerpo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=c_texto,
        spaceAfter=6
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
        leading=10.5,
        textColor=colors.HexColor("#2D3748")
    )

    callout_texto = ParagraphStyle(
        'CalloutTexto',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12.5,
        textColor=c_verde
    )

    story = []

    # =========================================================================
    # PORTADA
    # =========================================================================
    story.append(Spacer(1, 15))
    story.append(Paragraph("UNIVERSIDAD TECNOLOGICA DEL URUGUAY (UTEC)", ParagraphStyle('UTEC', fontName='Helvetica-Bold', fontSize=10, textColor=c_acento, leading=12)))
    story.append(Paragraph("PROGRAMA DE INVESTIGACION APLICADA (PRIA)", ParagraphStyle('PRIA', fontName='Helvetica', fontSize=9, textColor=colors.HexColor("#718096"), leading=11)))
    story.append(Spacer(1, 15))
    story.append(HRFlowable(width="100%", thickness=2, color=c_primario, spaceBefore=0, spaceAfter=15))
    
    story.append(Paragraph("Manual Operativo de Telemetria, Sincronizacion y Georreferenciacion en Formato DJI Mini 2 SE", titulo_principal))
    story.append(Paragraph("Sistema de integracion entre cuadricoptero F450 (Pixhawk 2.4.8 / ArduPilot) y camara GoPro HERO13 Black para deteccion de caminos de hormigas cortadoras.", subtitulo_portada))
    
    # Cuadro informativo de version y estado
    info_meta = [
        [Paragraph("<b>Plataforma UAV:</b>", cuerpo), Paragraph("HAWK'S WORK F450 | Pixhawk 2.4.8 | GNSS Radiolink SE100 M8N", cuerpo)],
        [Paragraph("<b>Sensor Optico:</b>", cuerpo), Paragraph("GoPro HERO13 Black (Video 4K / Foto a intervalos)", cuerpo)],
        [Paragraph("<b>Enlace de Datos:</b>", cuerpo), Paragraph("Radiotelemetria SiK 915 MHz (500 mW) + USB Open GoPro", cuerpo)],
        [Paragraph("<b>Compatibilidad:</b>", cuerpo), Paragraph("Windows 10/11 y Ubuntu Linux (100% Funcional sin programacion)", cuerpo)],
        [Paragraph("<b>Formato de Salida:</b>", cuerpo), Paragraph("Nativo DJI Mini 2 SE (EXIF estandar + XMP drone-dji)", cuerpo)],
    ]
    t_meta = Table(info_meta, colWidths=[130, 374])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 20))

    # =========================================================================
    # SECCION 1: EXPLICACION SIMPLE PARA OPERADORES
    # =========================================================================
    story.append(Paragraph("1. ¿Que hace este sistema y como funciona?", encabezado_1))
    story.append(Paragraph(
        "El objetivo principal del proyecto es sobrevolar parcelas rurales con el dron F450 y filmar o fotografiar el terreno con la camara GoPro HERO13 para localizar nidos y caminos de hormigas cortadoras. "
        "Para que las imagenes sirvan cientificamente, cada foto debe tener incrustada la posicion exacta donde estaba el dron (latitud, longitud y altura real sobre el suelo) en el milisegundo preciso del disparo.",
        cuerpo
    ))
    story.append(Paragraph(
        "<b>El problema habitual:</b> La camara GoPro y la computadora de vuelo del dron (Pixhawk) son dos equipos independientes. Si sus relojes difieren por apenas 2 segundos, a 5 metros por segundo de vuelo, las fotos quedaran desplazadas 10 metros de su lugar verdadero.",
        cuerpo
    ))
    story.append(Paragraph(
        "<b>La solucion implementada:</b> Este sistema resuelve todo el ciclo en 3 pasos muy sencillos que se ejecutan haciendo un solo clic:",
        cuerpo
    ))

    pasos_resumen = [
        [Paragraph("<b>Fase</b>", cuerpo_negrita), Paragraph("<b>Momento</b>", cuerpo_negrita), Paragraph("<b>Accion del operador</b>", cuerpo_negrita), Paragraph("<b>Resultado automatico</b>", cuerpo_negrita)],
        [Paragraph("<b>1. Pre-Vuelo</b>", cuerpo), Paragraph("Antes de volar (en taller o vehiculo)", cuerpo), Paragraph("Conectar GoPro y Pixhawk a la PC con cable USB y hacer doble clic en <i>1_sincronizar_relojes</i>.", cuerpo), Paragraph("El reloj de la camara se calibra con la hora atomica del GPS a precision de milisegundos.", cuerpo)],
        [Paragraph("<b>2. Vuelo</b>", cuerpo), Paragraph("Durante el relevamiento", cuerpo), Paragraph("Conectar la antena de 915 MHz a la PC y hacer doble clic en <i>2_grabar_telemetria</i>.", cuerpo), Paragraph("La PC recolecta y guarda la trayectoria completa del dron en vivo en un archivo CSV ordenado.", cuerpo)],
        [Paragraph("<b>3. Post-Vuelo</b>", cuerpo), Paragraph("Al finalizar el vuelo", cuerpo), Paragraph("Conectar la memoria de la GoPro y hacer doble clic en <i>3_vincular_vuelo_dji</i>.", cuerpo), Paragraph("Cruza tiempos, calcula posicion y actitud de cada foto y las deja en formato nativo DJI Mini 2 SE.", cuerpo)],
    ]
    t_resumen = Table(pasos_resumen, colWidths=[70, 95, 175, 164])
    t_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_resumen)
    story.append(Spacer(1, 15))

    # =========================================================================
    # SECCION 2: MUESTRA REAL DE DATOS (COMO SALEN LOS DATOS)
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("2. Muestra y Estructura de los Datos Resultantes", encabezado_1))
    story.append(Paragraph(
        "Al finalizar el proceso, las fotografias de la GoPro HERO13 son transformadas internamente para que contengan exactamente la misma estructura de metadatos que genera un dron <b>DJI Mini 2 SE</b>. "
        "A continuacion se muestra la comparacion y el significado practico de cada dato incrustado:",
        cuerpo
    ))

    # Tabla comparativa de metadatos
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
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_datos)
    story.append(Spacer(1, 12))

    # Muestra del CSV en vivo
    story.append(Paragraph("2.1. Archivo CSV generado en tiempo real durante el vuelo (telemetria.csv)", encabezado_2))
    story.append(Paragraph(
        "Mientras el dron vuela, la antena de 915 MHz conectada a la PC escribe continuamente un registro en tiempo real. "
        "Cada fila representa 250 milisegundos de vuelo (4 lecturas por segundo):",
        cuerpo
    ))

    muestra_csv = [
        [Paragraph("<b>timestamp_utc</b>", codigo), Paragraph("<b>latitud</b>", codigo), Paragraph("<b>longitud</b>", codigo), Paragraph("<b>alt_rel</b>", codigo), Paragraph("<b>yaw</b>", codigo), Paragraph("<b>bat_v</b>", codigo), Paragraph("<b>modo</b>", codigo)],
        [Paragraph("2026-11-20 10:14:02.250", codigo), Paragraph("-34.582104", codigo), Paragraph("-58.421590", codigo), Paragraph("25.30", codigo), Paragraph("145.8", codigo), Paragraph("11.6V", codigo), Paragraph("AUTO", codigo)],
        [Paragraph("2026-11-20 10:14:02.500", codigo), Paragraph("-34.582110", codigo), Paragraph("-58.421598", codigo), Paragraph("25.35", codigo), Paragraph("145.9", codigo), Paragraph("11.6V", codigo), Paragraph("AUTO", codigo)],
        [Paragraph("2026-11-20 10:14:02.750", codigo), Paragraph("-34.582116", codigo), Paragraph("-58.421605", codigo), Paragraph("25.40", codigo), Paragraph("146.0", codigo), Paragraph("11.5V", codigo), Paragraph("AUTO", codigo)],
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

    # Muestra de subtitulos SRT para video
    story.append(Paragraph("2.2. Archivo de Subtitulos generado para grabaciones de Video (.SRT)", encabezado_2))
    story.append(Paragraph(
        "Si el relevamiento se realizo grabando video continuo en lugar de fotos, el sistema produce automaticamente un archivo con la misma extension (.SRT). "
        "Al reproducir el video en reproductores como VLC o cargarlo en herramientas de vision por computadora, la telemetria se visualiza sincronizada segundo a segundo:",
        cuerpo
    ))
    
    bloque_srt = [
        [Paragraph(
            "1<br/>"
            "00:00:00,000 --&gt; 00:00:01,000<br/>"
            "[latitude: -34.582104] [longitude: -58.421590] [rel_alt: 25.300 abs_alt: 68.500] [flight_yaw: 145.8] [iso: 100] [shutter: 1/240]<br/><br/>"
            "2<br/>"
            "00:00:01,000 --&gt; 00:00:02,000<br/>"
            "[latitude: -34.582125] [longitude: -58.421612] [rel_alt: 25.320 abs_alt: 68.520] [flight_yaw: 146.1] [iso: 100] [shutter: 1/240]",
            codigo
        )]
    ]
    t_srt = Table(bloque_srt, colWidths=[504])
    t_srt.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#38BDF8")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#0F172A")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_srt)

    # =========================================================================
    # SECCION 3: GUIA OPERATIVA PASO A PASO PARA EL CAMPO
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Guia Operativa Paso a Paso (Protocolo de Campo)", encabezado_1))
    story.append(Paragraph(
        "Siga esta lista de verificacion antes, durante y despues de cada sesion de vuelo en el campo:",
        cuerpo
    ))

    # Cuadro destacado de advertencia sobre antenas
    aviso_antena = [
        [Paragraph(
            "<b>REGLA CRITICA DE SEGURIDAD PARA LAS RADIOS DE 915 MHz:</b><br/>"
            "NUNCA conecte la radio USB a la computadora ni alimente el dron sin antes haber enroscado las antenas. "
            "Al ser modulos de 500 mW (alta potencia), transmitir sin antena puede quemar el chip amplificador de radio en segundos.",
            callout_texto
        )]
    ]
    t_aviso = Table(aviso_antena, colWidths=[504])
    t_aviso.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), c_verde_fondo),
        ('BOX', (0, 0), (-1, -1), 1, c_verde),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(t_aviso)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.1. En la Base (Antes de despegar)", encabezado_2))
    story.append(Paragraph(
        "1. <b>Configurar la GoPro:</b> Encienda la camara. Deslice la pantalla hacia abajo &gt; <i>Preferencias</i> &gt; <i>Conexiones</i> &gt; <i>Conexion USB</i> &gt; Verifique que este seleccionado <b>GoPro Connect</b>.<br/>"
        "2. <b>Conectar al PC:</b> Conecte la GoPro mediante cable USB-C a la laptop. Conecte la Pixhawk por cable USB (o encienda el dron para enlace por radio).<br/>"
        "3. <b>Sincronizar:</b> Ejecute con doble clic <code>1_sincronizar_relojes.bat</code> (en Windows) o <code>./1_sincronizar_relojes.sh</code> (en Ubuntu).<br/>"
        "4. <b>Verificar:</b> La consola confirmara: <i>Sincronizacion realizada exitosamente (Diferencia &lt; 0.05 s)</i> y reportara la bateria.<br/>"
        "5. <b>Desconectar:</b> Desconecte el cable USB de la camara y montela firmemente orientada hacia abajo (Nadir) en el soporte del dron.",
        cuerpo
    ))

    story.append(Paragraph("3.2. Durante la Mision de Vuelo", encabezado_2))
    story.append(Paragraph(
        "1. <b>Conectar Antena:</b> Enrosque la antena al modulo de telemetria USB y conectelo a la computadora.<br/>"
        "2. <b>Iniciar Grabador:</b> Ejecute con doble clic <code>2_grabar_telemetria.bat</code> (Windows) o <code>./2_grabar_telemetria.sh</code> (Ubuntu).<br/>"
        "3. <b>Seleccionar Puerto:</b> El programa listara los puertos disponibles. Presione ENTER para aceptar la opcion sugerida (ej. COM5 o /dev/ttyUSB0).<br/>"
        "4. <b>Confirmar Enlace:</b> Apenas se encienda el dron, vera en pantalla: <i>Modo: LOITER | Sats: 14 | AltRel: 0.0m | Bat: 12.4V</i>.<br/>"
        "5. <b>Iniciar Camara y Despegar:</b> Presione grabar en la GoPro e inicie el vuelo planificado en Mission Planner.<br/>"
        "6. <b>Al Aterrizar:</b> Presione <code>Ctrl + C</code> en la ventana del grabador de telemetria. El archivo quedara cerrado y guardado.",
        cuerpo
    ))

    story.append(Paragraph("3.3. Post-Vuelo (Vinculacion de Datos)", encabezado_2))
    story.append(Paragraph(
        "1. <b>Descargar Fotos:</b> Conecte la tarjeta microSD de la GoPro a la computadora y copie la carpeta con las fotos (ej. <code>C:\\Vuelos\\Mision_1</code>).<br/>"
        "2. <b>Ejecutar Vinculador:</b> Ejecute con doble clic <code>3_vincular_vuelo_dji.bat</code> (Windows) o <code>./3_vincular_vuelo_dji.sh</code> (Ubuntu).<br/>"
        "3. <b>Arrastrar Archivos:</b> Cuando lo solicite, arrastre a la ventana el archivo <code>telemetria.csv</code> (o el <code>.BIN</code> de la Pixhawk) y presione ENTER. Luego arrastre la carpeta con las fotos y presione ENTER.<br/>"
        "4. <b>Resultado:</b> El sistema calculara la posicion milisegundo a milisegundo e inyectara los metadatos DJI. Al finalizar, cada imagen contendra sus coordenadas y altura real sobre el suelo.",
        cuerpo
    ))

    # =========================================================================
    # SECCION 4: RESOLUCION DE PROBLEMAS COMUNES
    # =========================================================================
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Preguntas Frecuentes y Resolucion de Problemas", encabezado_1))
    
    faq_data = [
        [Paragraph("<b>Problema observado</b>", cuerpo_negrita), Paragraph("<b>Causa y solucion inmediata</b>", cuerpo_negrita)],
        [
            Paragraph("La PC no detecta la GoPro por cable USB.", cuerpo),
            Paragraph("Asegurese de que la opcion en la pantalla de la GoPro sea <b>GoPro Connect</b> y no MTP. Si uso un cable USB generico de celular que solo carga bateria, reemplacelo por un cable de datos.", cuerpo)
        ],
        [
            Paragraph("El grabador dice: <i>Acceso denegado al puerto COM</i>.", cuerpo),
            Paragraph("Mission Planner ya tiene abierto el puerto COM en exclusivo. Solucion: Cierre Mission Planner, o en el grabador elija la opcion <b>U</b> (UDP) para recibir los datos reenviados por Mission Planner.", cuerpo)
        ],
        [
            Paragraph("En Ubuntu dice: <i>Permission denied: /dev/ttyUSB0</i>.", cuerpo),
            Paragraph("Su usuario no pertenece al grupo 'dialout'. Ejecute en terminal: <code>sudo usermod -a -G dialout $USER</code> y reinicie la sesion del sistema.", cuerpo)
        ],
        [
            Paragraph("¿Puedo usar el log .BIN de la Pixhawk en vez de la radio?", cuerpo),
            Paragraph("Si, totalmente. El programa <code>3_vincular_vuelo_dji</code> acepta indistintamente archivos <code>.csv</code>, <code>.BIN</code> descargados de Mission Planner o registros <code>.tlog</code>.", cuerpo)
        ],
    ]
    t_faq = Table(faq_data, colWidths=[170, 334])
    t_faq.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), c_secundario),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, c_fondo_tabla]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_faq)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Documento PDF generado exitosamente en: {ruta_salida}")

if __name__ == "__main__":
    salida = sys.argv[1] if len(sys.argv) > 1 else "Manual_Operativo_Telemetria_GoPro_DJI.pdf"
    construir_pdf(salida)
