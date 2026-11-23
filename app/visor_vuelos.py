#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera <mision>/visor.html: mapa de la trayectoria y las fotos georreferenciadas.
Uso: .venv/bin/python visor_vuelos.py [carpeta_mision]   (por defecto, la mision mas reciente)
No modifica fotos, videos ni telemetria."""
import sys, os, csv, json, glob, subprocess
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import re
import rutas
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

BASE = os.path.dirname(os.path.abspath(__file__))

def leer_telemetria(carpeta):
    r = []
    with open(os.path.join(carpeta, "telemetria.csv"), encoding="utf-8") as f:
        for x in csv.DictReader(f):
            try:
                t = datetime.fromisoformat(x["timestamp_utc"]).replace(tzinfo=timezone.utc).timestamp()
                r.append([round(t, 2), float(x["latitud"]), float(x["longitud"]), float(x["altitud_relativa"]),
                          float(x["velocidad_ms"]), float(x["voltaje_bateria"]), int(x["satelites"]),
                          x["modo_vuelo"], float(x["rumbo_yaw"])])
            except (ValueError, KeyError, TypeError):
                continue
    return r

def leer_fotos(carpeta):
    d = os.path.join(carpeta, "fotos")
    if not glob.glob(os.path.join(d, "*.[jJ][pP][gG]")):
        return []
    res = subprocess.run(["exiftool", "-json", "-n", "-q", "-ext", "jpg", "-GPSLatitude", "-GPSLongitude",
                          "-RelativeAltitude", "-FlightYawDegree", "-DateTimeOriginal", d],
                         capture_output=True, text=True)
    if not res.stdout.strip():
        raise RuntimeError("exiftool no devolvio datos: " + res.stderr)
    salida = []
    for x in json.loads(res.stdout):
        num = lambda k: (float(x[k]) if x.get(k) not in (None, "") else None)
        salida.append({"n": os.path.basename(x["SourceFile"]), "lat": num("GPSLatitude"), "lon": num("GPSLongitude"),
                       "alt": num("RelativeAltitude"), "yaw": num("FlightYawDegree"), "f": x.get("DateTimeOriginal", "")})
    salida.sort(key=lambda q: q["n"])
    return salida

def miniatura(args):
    carpeta, n = args
    dest = os.path.join(carpeta, "miniaturas", n)
    src = os.path.join(carpeta, "fotos", n)
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(src):
        return
    with Image.open(src) as im:
        im.draft("RGB", (640, 360))
        im.thumbnail((480, 480))
        im.convert("RGB").save(dest, quality=75)

HTML = r"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Visor de vuelo</title><style>/*CSS*/</style><style>
*{box-sizing:border-box}body{margin:0;font:14px system-ui,sans-serif;color:#1e293b;display:flex;flex-direction:column;height:100vh}
header{background:#0f2942;color:#fff;padding:10px 16px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
header b{font-size:16px}header span{color:#cbd5e1}select,label{font:inherit}
main{flex:1;display:flex;min-height:0}#map{flex:1;min-width:0}
aside{width:340px;overflow:auto;padding:12px;border-left:1px solid #cbd5e1;background:#f8fafc}
aside img{width:100%;border-radius:6px;cursor:pointer}aside canvas{width:100%;height:90px;background:#fff;border:1px solid #e2e8f0}
.av{background:#fffbeb;border:1px solid #fde68a;color:#92400e;padding:8px;border-radius:6px;margin:8px 0}
footer{padding:8px 16px;display:flex;gap:12px;align-items:center;border-top:1px solid #cbd5e1}#sl{flex:1}
#leg i{display:inline-block;width:120px;height:10px;background:linear-gradient(90deg,hsl(240 85% 48%),hsl(120 85% 48%),hsl(0 85% 48%))}
#lst button{border:0;background:none;color:#1a5f7a;cursor:pointer;padding:2px 0;display:block}
@media(max-width:760px){main{flex-direction:column}aside{width:100%;height:42%;border-left:0}}
</style></head><body><header><b id="ti"></b><span id="res"></span>
<label>Color <select id="col"><option value="3">Altura (m)</option><option value="4">Velocidad (m/s)</option><option value="5">Voltaje (V)</option></select></label>
<label><input type="checkbox" id="vf" checked> Fotos</label><span id="leg"><em id="lmin"></em> <i></i> <em id="lmax"></em></span></header>
<main><div id="map"></div><aside><div id="foto"><p>Pulsa Reproducir o haz clic en cualquier punto de la trayectoria.</p></div><div id="avisos"></div>
<h4>Altura relativa (m)</h4><canvas id="c3" width="640" height="180"></canvas><h4>Voltaje (V)</h4><canvas id="c5" width="640" height="180"></canvas>
<details><summary id="sg"></summary><div id="lst"></div></details></aside></main>
<footer><button id="pl">▶ Reproducir</button><select id="ve"><option>1</option><option selected>2</option><option>5</option><option>10</option></select>x<input type="range" id="sl" min="0" value="0"><span id="st"></span></footer>
<script>/*JS*/</script><script>
const D=/*DATOS*/;const T=D.t,F=D.f,$=i=>document.getElementById(i);
const G=F.filter(p=>p.lat!==null&&p.lon!==null&&(p.lat||p.lon)),N=F.filter(p=>!G.includes(p));
$('ti').textContent=D.nombre;document.title='Visor '+D.nombre;
const map=L.map('map',{maxZoom:22,preferCanvas:true});
const sat=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxZoom:22,maxNativeZoom:18,attribution:'Imagen © Esri'}).addTo(map);
const osm=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:22,maxNativeZoom:19,attribution:'© OpenStreetMap'});
const tr=L.layerGroup().addTo(map),fo=L.layerGroup().addTo(map);
L.control.layers({'Satélite':sat,'Calles':osm,'Sin fondo':L.layerGroup()},{'Trayectoria':tr,'Fotos':fo}).addTo(map);L.control.scale({imperial:false}).addTo(map);
function pinta(){tr.clearLayers();const k=+$('col').value,v=T.map(p=>p[k]),a=v.reduce((x,y)=>Math.min(x,y)),b=v.reduce((x,y)=>Math.max(x,y));
$('lmin').textContent=a.toFixed(1);$('lmax').textContent=b.toFixed(1);
for(let i=1;i<T.length;i++){const h=240-240*(b>a?(T[i][k]-a)/(b-a):.5);L.polyline([[T[i-1][1],T[i-1][2]],[T[i][1],T[i][2]]],{color:`hsl(${h},85%,48%)`,weight:4,interactive:false,dashArray:T[i][0]-T[i-1][0]>2?'4 6':null}).addTo(tr)}}
let elige=ver;
function ver(p){const c=$('foto');c.replaceChildren();const im=new Image();im.src='miniaturas/'+encodeURIComponent(p.n);im.title='Abrir original';im.onclick=()=>open('fotos/'+encodeURIComponent(p.n));
const d=document.createElement('p');d.textContent=`${p.n} | ${p.f} | `+(p.lat===null?'SIN GPS':`${p.lat.toFixed(7)}, ${p.lon.toFixed(7)} | altura ${p.alt} m | rumbo ${p.yaw}°`);c.append(im,d)}
G.forEach(p=>L.circleMarker([p.lat,p.lon],{radius:5,color:'#fff',weight:1,fillColor:'#f97316',fillOpacity:.9,bubblingMouseEvents:false}).bindTooltip(p.n).on('click',()=>elige(p)).addTo(fo));
N.forEach(p=>{const b=document.createElement('button');b.textContent=p.n;b.onclick=()=>ver(p);$('lst').append(b)});
$('sg').textContent='Fotos sin GPS: '+N.length;$('vf').onchange=e=>e.target.checked?fo.addTo(map):fo.remove();$('col').onchange=pinta;
const av=t=>{const d=document.createElement('div');d.className='av';d.textContent=t;$('avisos').append(d)};
if(!F.length)av('Esta misión todavía no tiene fotos. Vuelve a generar el visor cuando termine el procesamiento.');if(N.length)av(N.length+' fotos sin GPS (no aparecen en el mapa).');
function graf(id,k){const c=$(id),x=c.getContext('2d'),v=T.map(p=>p[k]),a=v.reduce((m,n)=>Math.min(m,n)),b=v.reduce((m,n)=>Math.max(m,n));x.strokeStyle='#1a5f7a';x.lineWidth=2;x.beginPath();
v.forEach((y,i)=>{const X=(T[i][0]-T[0][0])/Math.max(1,T[T.length-1][0]-T[0][0])*640,Y=165-(y-a)/((b-a)||1)*150;i?x.lineTo(X,Y):x.moveTo(X,Y)});x.stroke();x.fillStyle='#475569';x.font='20px sans-serif';x.fillText(b.toFixed(1),4,20);x.fillText(a.toFixed(1),4,176)}
if(T.length){pinta();graf('c3',3);graf('c5',5);let d=0;for(let i=1;i<T.length;i++)d+=map.distance([T[i-1][1],T[i-1][2]],[T[i][1],T[i][2]]);
$('res').textContent=`${((T[T.length-1][0]-T[0][0])/60).toFixed(1)} min | ${d.toFixed(0)} m de recorrido | ${T.length} registros | ${G.length}/${F.length} fotos con GPS`;
map.fitBounds(L.latLngBounds(T.map(p=>[p[1],p[2]])).pad(.15));const mk=L.circleMarker([T[0][1],T[0][2]],{radius:9,color:'#0ea5e9',weight:4,fillOpacity:.2}).addTo(map);
$('sl').max=T.length-1;const mv=()=>{const p=T[+$('sl').value];mk.setLatLng([p[1],p[2]]);$('st').textContent=`${new Date(p[0]*1000).toLocaleTimeString()} | ${p[7]} | ${p[3].toFixed(1)} m | ${p[4].toFixed(1)} m/s | ${p[5].toFixed(2)} V | ${p[6]} sats`};$('sl').oninput=()=>{mv();sinc()};mv();
const S=F.map(p=>({p,t:new Date(p.f.replace(/^(\d+):(\d+):(\d+) /,'$1-$2-$3T')).getTime()/1000})).filter(o=>o.t&&o.p.lat!==null).sort((a,b)=>a.t-b.t);let ult=null;
function sinc(){const t=T[+$('sl').value][0];let b=null;for(const o of S)if(!b||Math.abs(o.t-t)<Math.abs(b.t-t))b=o;if(b&&Math.abs(b.t-t)<=3&&b.p!==ult){ult=b.p;ver(b.p)}}
const ht=o=>{let b=0;for(let i=1;i<T.length;i++)if(Math.abs(T[i][0]-o)<Math.abs(T[b][0]-o))b=i;return b};
function cercanas(lat,lon,p){const c=S.map(o=>({o,d:map.distance([lat,lon],[o.p.lat,o.p.lon])})).filter(q=>q.d<=3&&q.o.p!==p).sort((a,b)=>a.d-b.d).slice(0,8);
if(!c.length)return;const d=document.createElement('div');d.id='otras';d.append('Otras imágenes a menos de 3 m:');d.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:4px';
c.forEach(q=>{const i=new Image();i.src='miniaturas/'+encodeURIComponent(q.o.p.n);i.title=q.o.p.n+' a '+q.d.toFixed(1)+' m';i.onclick=()=>elige(q.o.p);d.append(i)});$('foto').append(d)}
elige=p=>{const o=S.find(q=>q.p===p);if(o){$('sl').value=ht(o.t);mv()}ult=p;ver(p);cercanas(p.lat,p.lon,p)};
map.on('click',e=>{let b=-1,bd=30;T.forEach((p,i)=>{const d=map.latLngToContainerPoint([p[1],p[2]]).distanceTo(e.containerPoint);if(d<bd){bd=d;b=i}});if(b<0)return;
$('sl').value=b;mv();ult=null;sinc();if(ult)cercanas(T[b][1],T[b][2],ult);else{const m=document.createElement('p');m.textContent='No hay imagen para este instante.';$('foto').replaceChildren(m)}});
let run=null;$('pl').onclick=()=>{if(run){clearInterval(run);run=null;$('pl').textContent='▶ Reproducir';return}$('pl').textContent='⏸ Pausa';let tv=T[+$('sl').value][0];
run=setInterval(()=>{tv+=.25*+$('ve').value;let i=+$('sl').value;while(i<T.length-1&&T[i+1][0]<=tv)i++;$('sl').value=i;mv();sinc();if(i>=T.length-1)$('pl').onclick()},250)};
}else map.setView([0,0],2);
</script></body></html>"""

def construir(carpeta, fotos):
    tel = leer_telemetria(carpeta)
    datos = json.dumps({"nombre": os.path.basename(carpeta), "t": tel, "f": fotos}).replace("<", "\\u003c")
    lee = lambda n: open(os.path.join(BASE, "static", "leaflet", n), encoding="utf-8").read()
    return tel, HTML.replace("/*CSS*/", lee("leaflet.css")).replace("/*JS*/", lee("leaflet.js")).replace("/*DATOS*/", datos)

router = APIRouter()
_cache = {}

def _carpeta(m):
    c = rutas.buscar(m)
    if not c:
        raise HTTPException(404)
    return c

def _foto(m, n):
    r = os.path.join(_carpeta(m), "fotos", n)
    if not re.fullmatch(r"[\w.-]+\.(jpg|JPG|jpeg|JPEG)", n) or not os.path.isfile(r):
        raise HTTPException(404)
    return r

def _fotos(m):
    c = _carpeta(m)
    d = os.path.join(c, "fotos")
    if not os.path.isdir(d):
        return []
    k = os.stat(d).st_mtime_ns
    if _cache.get(m, (None,))[0] != k:
        _cache[m] = (k, leer_fotos(c))
    return _cache[m][1]

@router.get("/api/vuelos")
def api_vuelos():
    return [os.path.basename(c) for c in rutas.carpetas()]

@router.get("/api/vuelos/{m}/fotos")
def api_fotos(m: str):
    return {"carpeta": _carpeta(m), "fotos": _fotos(m)}

@router.get("/api/vuelos/{m}/tags/{n}")
def api_tags(m: str, n: str):
    res = subprocess.run(["exiftool", "-json", "-G1", "-c", "%.7f", _foto(m, n)], capture_output=True, text=True)
    if not res.stdout.strip():
        raise HTTPException(500)
    t = json.loads(res.stdout)[0]
    t.pop("SourceFile", None)
    return t

@router.get("/vuelos/{m}/visor.html", response_class=HTMLResponse)
def ver_visor(m: str):
    return construir(_carpeta(m), _fotos(m))[1]

@router.get("/vuelos/{m}/fotos/{n}")
def ver_foto(m: str, n: str):
    return FileResponse(_foto(m, n))

@router.get("/vuelos/{m}/miniaturas/{n}")
def ver_miniatura(m: str, n: str):
    _foto(m, n)
    c = _carpeta(m)
    os.makedirs(os.path.join(c, "miniaturas"), exist_ok=True)
    miniatura((c, n))
    return FileResponse(os.path.join(c, "miniaturas", n))

def generar(carpeta):
    carpeta = os.path.abspath(carpeta)
    fotos = leer_fotos(carpeta)
    if fotos:
        os.makedirs(os.path.join(carpeta, "miniaturas"), exist_ok=True)
        with ThreadPoolExecutor() as ex:
            list(ex.map(miniatura, [(carpeta, f["n"]) for f in fotos]))
    tel, html = construir(carpeta, fotos)
    ruta = os.path.join(carpeta, "visor.html")
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(html)
    con = sum(f["lat"] is not None for f in fotos)
    print(f"{ruta}\n{len(tel)} registros, {len(fotos)} fotos ({con} con GPS)")

if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else rutas.carpetas()[0]
    generar(c)
