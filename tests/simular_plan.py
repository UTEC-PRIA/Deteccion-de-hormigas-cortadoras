"""Simula un dron por UDP y prueba el plan de vuelo, sin hardware: .venv/bin/python -u tests/simular_plan.py"""
import sys,time,threading,os;P=os.path.dirname(os.path.dirname(os.path.abspath(__file__)));sys.path.insert(0,os.path.join(P,"app"));import tempfile;os.chdir(tempfile.mkdtemp())
import rutas;rutas.F450=os.path.join(os.getcwd(),"vuelos")
import web_dashboard as w, plan_vuelo as pv
from pymavlink import mavutil
from fastapi import HTTPException
S=dict(arm=False,rc=8,mode=5,corrupt=False,alt=5000,items=[],drop=0,par=1.0);U='udpin:127.0.0.1:14601'
def veh():
    m=mavutil.mavlink_connection('udpout:127.0.0.1:14601',source_system=1,source_component=1);t=0;need=None;buf={}
    while 1:
        if time.time()-t>.2:
            t=time.time();m.mav.heartbeat_send(2,3,81|(128 if S['arm'] else 0),S['mode'],3);m.mav.gps_raw_int_send(0,3,-323085000,-538072000,200000,70,90,0,0,20)
            m.mav.global_position_int_send(1,-323085000,-538072000,200000,S['alt'],0,0,0,0);m.mav.rc_channels_send(1,S['rc'],*([1500]*18),0);m.mav.sys_status_send(0,32768,0,0,11500,0,50,0,0,0,0,0,0)
        x=m.recv_match(blocking=True,timeout=.05)
        if not x:continue
        y=x.get_type()
        if y=='MISSION_COUNT':need=x.count;buf={};m.mav.mission_request_send(254,0,0)
        elif y=='MISSION_ITEM_INT' and need:
            if S['drop']>0:S['drop']-=1;m.mav.mission_request_send(254,0,x.seq);continue
            buf[x.seq]=x
            if len(buf)==need:S['items']=[buf[i] for i in range(need)];need=None;m.mav.mission_ack_send(254,0,0)
            else:m.mav.mission_request_send(254,0,x.seq+1)
        elif y=='MISSION_REQUEST_LIST':m.mav.mission_count_send(254,0,len(S['items']))
        elif y=='MISSION_REQUEST_INT':
            i=S['items'][x.seq];m.mav.mission_item_int_send(254,0,x.seq,i.frame,i.command,0,1,i.param1,i.param2,i.param3,i.param4,i.x,i.y,i.z+(3 if S['corrupt'] and x.seq==3 else 0))
        elif y=='SET_MODE':S['mode']=x.custom_mode
        elif y=='PARAM_REQUEST_READ':m.mav.param_value_send(x.param_id.encode(),S['par'],9,1,0)
threading.Thread(target=veh,daemon=True).start()
w.buscar_ip_gopro=lambda:None;pv.conexion['puerto']=lambda:U
A=[{'lat':-32.3085,'lon':-53.8072,'alt':8},{'lat':-32.3087,'lon':-53.8072,'alt':8},{'lat':-32.3087,'lon':-53.8070,'alt':7,'espera':2}]
p=lambda **k:{'nombre':'t','vel':0.6,'fin':'RTL','wps':A,'confirmo':True,**k}
def c(n,f):
    try:print(n,'->',f())
    except HTTPException as e:print(n,'-> HTTP',e.status_code,e.detail)
c('validar',lambda:pv.validar(pv.normalizar(p())));c('lejos',lambda:pv.cargar(p(wps=A+[{'lat':-32.4,'lon':-53.8,'alt':90}]),'1')['errores'][:2])
c('NaN',lambda:pv.cargar(p(vel=float('nan')),'1'));c('sin cabecera',lambda:pv.cargar(p(),''));c('sin confirmar',lambda:pv.cargar(p(confirmo=False),'1'))
c('estado',lambda:pv.estado_dron('1'))
S['arm']=True;c('armado',lambda:pv.cargar(p(),'1'));S['arm']=False;S['rc']=0;c('sin rc',lambda:pv.cargar(p(),'1'));S['rc']=8
S['par']=500.0;c('WPNAV alto',lambda:pv.cargar(p(),'1'));S['par']=1.0
S['corrupt']=True;c('relectura distinta',lambda:pv.cargar(p(),'1'));S['corrupt']=False;S['drop']=2;c('con perdidas',lambda:pv.cargar(p(),'1'))
print('despegue sincronizado',pv.cargar(p(despegue=True,wps=[{'lat':-32.30851,'lon':-53.80721,'alt':8}]+A[1:]),'1')['wps'][0]);pv.cargar(p(),'1')
print([(i.command,i.x,i.y,i.z) for i in S['items']])
c('AUTO sin grabar',lambda:pv.modo(p(modo='AUTO'),'1'))
print(w.start_flight({'mision':'s','puerto':U})['exito']);time.sleep(2)
c('AUTO desarmado',lambda:pv.modo(p(modo='AUTO'),'1'));c('cargar grabando',lambda:pv.cargar(p(),'1'))
S['arm']=True;S['alt']=1000;time.sleep(1.5);c('AUTO bajo',lambda:pv.modo(p(modo='AUTO'),'1'));S['alt']=5000;time.sleep(1.5)
c('plan distinto',lambda:pv.modo(p(modo='AUTO',vel=0.8),'1'));c('AUTO ok',lambda:pv.modo(p(modo='AUTO'),'1'));c('plan distinto',lambda:pv.modo(p(modo='AUTO',vel=0.8),'1'));c('LOITER',lambda:pv.modo({'modo':'LOITER'},'1'));c('LAND',lambda:pv.modo({'modo':'LAND'},'1'))
w.estado.en_grabacion=False;time.sleep(.5);os._exit(0)
