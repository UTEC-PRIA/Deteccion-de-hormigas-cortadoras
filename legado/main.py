"""
Drone Mission Dashboard — FastAPI Server
REST API + WebSocket for real-time telemetry streaming.
"""
import asyncio
import json
import logging
import os
import subprocess

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

import uvicorn

from mission_manager import MissionManager
from mavproxy_router import router as mavproxy_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

manager = MissionManager()

# WebSocket clients
ws_clients: set[WebSocket] = set()

# Path to Mission Planner exe (auto-detected)
_WINEPREFIX = os.path.expanduser("~/.wine-mp")
_MP_EXE = os.path.join(_WINEPREFIX, "drive_c/Program Files (x86)/Mission Planner/MissionPlanner.exe")


async def broadcast_ws(msg: dict):
    dead = set()
    for ws in ws_clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Drone Mission Dashboard starting...")
    yield
    logger.info("Shutting down...")
    mavproxy_router.stop()
    await manager.reset()


app = FastAPI(title="Drone Mission Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"))


# ── Pages ───────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# ── Mission API ─────────────────────────────────────

class MissionCreateRequest(BaseModel):
    capture_mode: str = "photo"
    capture_interval: int = 2

@app.post("/api/mission/create")
async def api_create_mission(req: MissionCreateRequest):
    config = manager.create_mission(req.capture_mode, req.capture_interval)
    return {"success": True, "mission": config}

@app.get("/api/mission/status")
async def api_mission_status():
    return manager.get_status()

@app.get("/api/mission/list")
async def api_mission_list():
    return {"success": True, "missions": manager.list_missions()}

@app.post("/api/mission/reset")
async def api_mission_reset():
    await manager.reset()
    return {"success": True}


# ── GoPro API (Fully Wireless) ──────────────────────

class GoProConnectRequest(BaseModel):
    mode: str = "auto"  # "auto" (BLE wakeup + nmcli), "wireless" (BLE→WiFi SDK), "wifi_direct", "simulation"
    simulation: bool = False
    ssid: Optional[str] = None
    password: Optional[str] = None

@app.post("/api/gopro/connect")
async def api_gopro_connect(req: GoProConnectRequest):
    success = await manager.connect_gopro(
        mode=req.mode, simulation=req.simulation, ssid=req.ssid, password=req.password
    )
    if success:
        return {"success": True, "status": manager.gopro.get_status()}
    raise HTTPException(status_code=500, detail="Failed to connect GoPro. Check that it is on and in pairing mode.")

@app.get("/api/gopro/status")
async def api_gopro_status():
    return manager.gopro.get_status()

class CaptureRequest(BaseModel):
    mode: str = "photo"      # "photo" or "video"
    interval: int = 2        # seconds, only for photo timelapse

@app.post("/api/gopro/start_capture")
async def api_start_capture(req: CaptureRequest = CaptureRequest()):
    result = await manager.start_capture(mode=req.mode, interval=req.interval)
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Capture start failed"))

@app.post("/api/gopro/stop_capture")
async def api_stop_capture():
    result = await manager.gopro.stop_capture()
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Capture stop failed"))


# ── Telemetry API ───────────────────────────────────

class TelemetryConnectRequest(BaseModel):
    port: str = "/dev/ttyUSB0"
    baudrate: int = 57600
    simulation: bool = False

@app.post("/api/telemetry/connect")
async def api_telemetry_connect(req: TelemetryConnectRequest):
    success = await manager.connect_telemetry(
        port=req.port, baudrate=req.baudrate, simulation=req.simulation
    )
    if success:
        return {"success": True, "status": manager.telemetry.get_status()}
    raise HTTPException(status_code=500, detail="Failed to connect telemetry")

@app.post("/api/telemetry/disconnect")
async def api_telemetry_disconnect():
    await manager.telemetry.disconnect()
    return {"success": True}

class TelemetryAutoConnectRequest(BaseModel):
    baudrate: Optional[int] = None  # None = try all common baudrates

@app.post("/api/telemetry/auto_connect")
async def api_telemetry_auto_connect(req: TelemetryAutoConnectRequest):
    success = await manager.telemetry.auto_connect(baudrate=req.baudrate)
    if success:
        if manager.current_mission:
            tlog_path = os.path.join(manager.get_mission_dir(), "telemetry", "telemetry_log.csv")
            manager.telemetry.start_logging(tlog_path)
        return {"success": True, "status": manager.telemetry.get_status()}
    raise HTTPException(status_code=500, detail="Auto-connect failed: no MAVLink heartbeat found.")

@app.get("/api/telemetry/status")
async def api_telemetry_status():
    return manager.telemetry.get_status()

@app.get("/api/telemetry/ports")
async def api_telemetry_ports():
    return {"ports": manager.telemetry.list_serial_ports()}

@app.get("/api/telemetry/trace")
async def api_telemetry_trace():
    return {"trace": manager.telemetry.get_trace()}


# ── MAVProxy Router API ──────────────────────────────

class MAVProxyStartRequest(BaseModel):
    port: Optional[str] = None       # None = auto-detect
    baudrate: Optional[int] = None   # None = auto-detect

@app.post("/api/mavproxy/start")
async def api_mavproxy_start(req: MAVProxyStartRequest):
    result = await mavproxy_router.start(port=req.port, baudrate=req.baudrate)
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "MAVProxy failed to start"))

@app.post("/api/mavproxy/stop")
async def api_mavproxy_stop():
    return mavproxy_router.stop()

@app.get("/api/mavproxy/status")
async def api_mavproxy_status():
    return mavproxy_router.get_status()


# ── Mission Planner API ──────────────────────────────

@app.get("/api/mission_planner/status")
async def api_mp_status():
    """Check if Mission Planner exe exists (Wine installation)."""
    installed = os.path.exists(_MP_EXE)
    # Also search for it
    if not installed:
        import glob
        found = glob.glob(os.path.join(_WINEPREFIX, "**", "MissionPlanner.exe"), recursive=True)
        installed = bool(found)
    return {"installed": installed, "exe_path": _MP_EXE, "wineprefix": _WINEPREFIX}

@app.post("/api/mission_planner/launch")
async def api_mp_launch():
    """Launch Mission Planner via Wine in background, using Xvfb if no display."""
    exe = _MP_EXE
    import glob
    if not os.path.exists(exe):
        found = glob.glob(os.path.join(_WINEPREFIX, "**", "MissionPlanner.exe"), recursive=True)
        if found:
            exe = found[0]
        else:
            raise HTTPException(status_code=404, detail="Mission Planner not installed. Run scripts/install_mission_planner.sh first.")

    env = {**os.environ}
    display = os.environ.get("DISPLAY", ":0")
    env["DISPLAY"] = display

    # MAVProxy router continues running in UDP mode.
    # Telemetry manager continues listening on udpin:0.0.0.0:14551 to track mission state.

    # Use native mono to launch Mission Planner
    subprocess.Popen(["mono", exe], env=env, start_new_session=True)

    return {"success": True, "message": "Telemetría local desconectada. Mission Planner ejecutándose..."}


# ── Download & Sync API ─────────────────────────────

@app.post("/api/download/start")
async def api_download_start():
    result = await manager.start_download()
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Download failed"))

@app.get("/api/download/progress")
async def api_download_progress():
    return manager.download_progress

@app.post("/api/sync/generate")
async def api_sync_generate():
    result = await manager.generate_dataset()
    if result.get("success"):
        return result
    raise HTTPException(status_code=500, detail=result.get("error", "Sync failed"))

@app.get("/api/dataset/{mission_id}")
async def api_get_dataset(mission_id: str):
    path = manager.get_dataset_path(mission_id)
    if path and os.path.exists(path):
        return FileResponse(path, media_type="text/csv", filename=os.path.basename(path))
    raise HTTPException(status_code=404, detail="Dataset not found")

@app.get("/api/dataset/{mission_id}/preview")
async def api_preview_dataset(mission_id: str):
    path = manager.get_dataset_path(mission_id)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Dataset not found")
    import csv
    rows = []
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return {"success": True, "data": rows}


# ── Convenience: quick start simulation ─────────────

@app.post("/api/simulation/start")
async def api_sim_start():
    """One-click start: creates mission, connects sim GoPro + telemetry, starts capture."""
    config = manager.create_mission("photo", 2)
    await manager.connect_gopro(simulation=True)
    await manager.connect_telemetry(simulation=True)
    await manager.start_capture(mode="photo", interval=2)
    return {"success": True, "mission": config}


# ── WebSocket ───────────────────────────────────────

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(ws_clients)} total)")
    try:
        while True:
            if manager.telemetry.is_connected:
                data = manager.telemetry.get_current_data()
                trace = manager.telemetry.get_trace()
                await websocket.send_json({
                    "type": "telemetry",
                    "data": data,
                    "flight_state": manager.telemetry.flight_state,
                    "mission_state": manager.state,
                    "trace": trace[-200:],
                    "gopro": manager.gopro.get_status(),
                    "mavproxy": mavproxy_router.get_status(),
                })
            else:
                await websocket.send_json({
                    "type": "status",
                    "mission_state": manager.state,
                    "download_progress": manager.download_progress,
                    "gopro": manager.gopro.get_status(),
                    "mavproxy": mavproxy_router.get_status(),
                })
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        ws_clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(ws_clients)} remaining)")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
