"""
Drone Mission Dashboard — FastAPI Server
REST API + WebSocket for real-time telemetry streaming.
"""
import asyncio
import json
import logging
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

import uvicorn

from mission_manager import MissionManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

manager = MissionManager()

# WebSocket clients
ws_clients: set[WebSocket] = set()


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
    await manager.reset()


app = FastAPI(title="Drone Mission Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


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
    mode: str = "wireless"  # "wireless" (BLE→WiFi), "wifi_direct" (saved creds), or ignored if simulation
    simulation: bool = False

@app.post("/api/gopro/connect")
async def api_gopro_connect(req: GoProConnectRequest):
    success = await manager.connect_gopro(mode=req.mode, simulation=req.simulation)
    if success:
        return {"success": True, "status": manager.gopro.get_status()}
    raise HTTPException(status_code=500, detail="Failed to connect GoPro. Ensure it is powered on and within BLE range (~10m).")

@app.get("/api/gopro/status")
async def api_gopro_status():
    return manager.gopro.get_status()

@app.post("/api/gopro/start_capture")
async def api_start_capture():
    result = await manager.start_capture()
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

@app.get("/api/telemetry/status")
async def api_telemetry_status():
    return manager.telemetry.get_status()

@app.get("/api/telemetry/ports")
async def api_telemetry_ports():
    return {"ports": manager.telemetry.list_serial_ports()}

@app.get("/api/telemetry/trace")
async def api_telemetry_trace():
    return {"trace": manager.telemetry.get_trace()}


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
    await manager.start_capture()
    return {"success": True, "mission": config}


# ── WebSocket ───────────────────────────────────────

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(ws_clients)} total)")
    try:
        while True:
            # Send telemetry data
            if manager.telemetry.is_connected:
                data = manager.telemetry.get_current_data()
                trace = manager.telemetry.get_trace()
                await websocket.send_json({
                    "type": "telemetry",
                    "data": data,
                    "flight_state": manager.telemetry.flight_state,
                    "mission_state": manager.state,
                    "trace": trace[-200:],  # Last 200 points for map
                })
            else:
                await websocket.send_json({
                    "type": "status",
                    "mission_state": manager.state,
                    "download_progress": manager.download_progress,
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
