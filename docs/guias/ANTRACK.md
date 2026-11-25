# Puente hacia AnTrack
`app/antrack.py` deja los datos en el formato A de AnTrack (28/09/2026). No envía nada ni modifica los vuelos.

1. `python app/antrack.py imagenes VUELO` crea `imagenes.csv` en el vuelo: imagen, video, cuadro, fecha, hora, GPS, alturas, rumbo y gimbal, para el servidor de IA. Las imágenes se entregan a resolución original.
2. El servidor de IA deja `detecciones.json` en la carpeta del vuelo:
   `[{"imagen": "GX010035_0201.JPG", "clase": "hormiguero", "confianza": 0.87, "x": 2100, "y": 1700, "ancho": 300, "alto": 200}]`
   (`x`, `y` = centro del recuadro, en píxeles de la imagen original).
3. `python app/antrack.py exportar VUELO` crea en `datos/salida_antrack/` los ZIP (hasta 90 MB y 2000 archivos) y un informe con lo aceptado y lo rechazado.
4. Se sube en AnTrack: Detecciones > Cargar > "Revisar sin guardar" y luego cargar.

## Límites conocidos
- **Posición:** por ahora es la del dron en ese cuadro, no la del recuadro proyectado al suelo (falta calibrar cada cámara).
- **Altura:** relativa al despegue, no al suelo. AnTrack debe confirmar cuál espera.
- **PNG:** AnTrack admite 10 MB. Si el cuadro completo no entra, se recorta alrededor de la detección sin reducir píxeles. El JPG completo no se toca.
- **Tipos:** solo hormiguero, camino y corte de hoja (y sus sinónimos). "Árbol dañado" se rechaza hasta que AnTrack lo agregue.
- **Reexportar:** con el mismo `detecciones.json` los `unique_id` no cambian; AnTrack rechaza los ya cargados.
