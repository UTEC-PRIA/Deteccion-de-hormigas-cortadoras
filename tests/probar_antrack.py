"""Puente AnTrack sin hardware: .venv/bin/python tests/probar_antrack.py"""
import sys, os, io, json, tempfile, zipfile
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(P, "app"))
import antrack as a
from PIL import Image
assert a.tipo("Corte de hoja") == "corte_de_hoja" and a.tipo("árbol") is None
with tempfile.TemporaryDirectory() as t:
    D = os.path.join(t, "dji_x", "V"); os.makedirs(D + "/fotos"); os.makedirs(D + "/video"); open(D + "/video/A.MP4", "w").close()
    Image.effect_noise((2400, 1600), 90).convert("RGB").save(D + "/fotos/A_00004s.JPG"); Image.new("RGB", (800, 600)).save(D + "/fotos/A_0003.JPG")
    a.fps = lambda r: 30000 / 1001
    g = {"GPSLatitude": -32.3, "GPSLongitude": -53.8, "RelativeAltitude": 5, "DateTimeOriginal": "2026:11:24 12:00:00"}
    a.datos_imagenes = lambda c, n=None: {"A_00004s.JPG": g, "A_0003.JPG": g}
    b = {"imagen": "A_0003.JPG", "clase": "nido", "confianza": .5, "x": 400, "y": 300, "ancho": 50, "alto": 50}
    json.dump([b, {**b, "x": 500}, {**b, "imagen": "A_00004s.JPG"}, {**b, "clase": "arbol"}, {**b, "confianza": 2}, {"imagen": "A_0003.JPG"}, {**b, "imagen": "Z.JPG"}], open(D + "/detecciones.json", "w"))
    z, inf = a.exportar(D, t + "/s"); z2, inf2 = a.exportar(D, t + "/s")
    assert inf == inf2 and [i[3] for i in sorted(inf)] == ["ACEPTADA"] * 3 + ["RECHAZADA"] * 4, inf
    q = zipfile.ZipFile(z[0]); n = q.namelist(); assert len(n) == 6 and len(set(n)) == 6
    for k in n:
        if k.endswith(".png"): assert len(q.read(k)) <= a.MAX_PNG and Image.open(io.BytesIO(q.read(k))).format == "PNG"
        else:
            j = json.loads(q.read(k)); assert len(j) == 8 and k == j["unique_id"] + ".json" and j["geometry"]["coordinates"] == [-53.8, -32.3, 5]
    f = {json.loads(q.read(k))["detection_frame"] for k in n if k.endswith(".json")}; assert f == {60, 120}, f
    a.datos_imagenes = lambda c, n=None: {"A_00004s.JPG": {**g, "ImageWidth": 2400}, "A_0003.JPG": {"DateTimeOriginal": "2026:11:24 12:00:00"}}
    z, n, s = a.paquete(D, t + "/p"); assert (len(z), n, s) == (1, 1, 1)
    q = zipfile.ZipFile(z[0]); j = json.loads(q.read("imagenes.json")); assert j[0]["cuadro"] == 120 and j[0]["latitud"] == -32.3 and j[0]["ancho"] == 2400
    assert q.read("imagenes/A_00004s.JPG") == open(D + "/fotos/A_00004s.JPG", "rb").read() and q.testzip() is None
print("OK")
