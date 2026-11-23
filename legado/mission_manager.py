"""
Mission Manager — Orchestrates the full drone mission lifecycle.
State machine coordinating telemetry, GoPro, and sync engine.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import asyncio

from telemetry_manager import TelemetryManager
from gopro_manager import GoProManager
from sync_engine import SyncEngine

logger = logging.getLogger(__name__)

MISSIONS_DIR = os.path.join(os.path.dirname(__file__), "misiones")


class MissionManager:
    """Central orchestrator for drone missions."""

    STATES = [
        "IDLE",         # No mission active
        "CONFIGURING",  # Mission created, setting up
        "PRE_FLIGHT",   # GoPro + Telemetry connected, ready to fly
        "IN_FLIGHT",    # Drone is flying, logging telemetry
        "LANDING",      # Landing detected
        "DOWNLOADING",  # Downloading media from GoPro
        "SYNCING",      # Generating geotagged dataset
        "COMPLETE",     # Mission finished
    ]

    def __init__(self):
        self.telemetry = TelemetryManager()
        self.gopro = GoProManager()
        self.state = "IDLE"
        self.current_mission = None  # dict with mission config
        self.download_progress = {"current": 0, "total": 0, "filename": "", "percent": 0}
        self._state_listeners = []
        try:
            self._main_loop = asyncio.get_event_loop()
        except RuntimeError:
            self._main_loop = None

        # Listen for telemetry state changes
        self.telemetry.on_state_change(self._on_flight_state_change)

    def on_state_change(self, callback):
        self._state_listeners.append(callback)

    def _set_state(self, new_state):
        old = self.state
        self.state = new_state
        logger.info(f"Mission state: {old} → {new_state}")
        for cb in self._state_listeners:
            try:
                cb(old, new_state)
            except Exception:
                pass

    def _on_flight_state_change(self, old_state, new_state):
        """React to telemetry flight state changes."""
        if new_state == "IN_FLIGHT" and self.state == "PRE_FLIGHT":
            self._set_state("IN_FLIGHT")
        elif new_state in ("TAKEOFF", "IN_FLIGHT") and not self.gopro.capture_active:
            # Auto-start capture using the mission's configured mode
            if self._main_loop:
                asyncio.run_coroutine_threadsafe(
                    self.start_capture(mode=self.current_mission.get("capture_mode", "photo") if self.current_mission else "photo",
                                       interval=self.current_mission.get("capture_interval", 2) if self.current_mission else 2),
                    self._main_loop
                )
            if self.state == "PRE_FLIGHT":
                self._set_state("IN_FLIGHT")
        elif new_state in ("RTL", "LANDING") and self.state == "IN_FLIGHT":
            self._set_state("LANDING")
        elif new_state == "LANDED" and self.state in ("IN_FLIGHT", "LANDING"):
            self._set_state("LANDING")

    # ── Mission CRUD ────────────────────────────────────

    def create_mission(self, capture_mode="photo", capture_interval=2):
        """Create a new mission with auto-incremented ID."""
        mission_id = self._next_mission_id()
        mission_dir = os.path.join(MISSIONS_DIR, mission_id)
        os.makedirs(os.path.join(mission_dir, "raw"), exist_ok=True)
        os.makedirs(os.path.join(mission_dir, "telemetry"), exist_ok=True)
        os.makedirs(os.path.join(mission_dir, "dataset"), exist_ok=True)

        config = {
            "mission_id": mission_id,
            "capture_mode": capture_mode,
            "capture_interval": capture_interval,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "created",
        }

        config_path = os.path.join(mission_dir, "mission_config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        self.current_mission = config
        self._set_state("CONFIGURING")
        logger.info(f"Mission created: {mission_id}")
        return config

    def _next_mission_id(self):
        os.makedirs(MISSIONS_DIR, exist_ok=True)
        existing = []
        for d in os.listdir(MISSIONS_DIR):
            if d.startswith("M") and d[1:].isdigit():
                existing.append(int(d[1:]))
        next_num = max(existing, default=0) + 1
        return f"M{next_num:03d}"

    def list_missions(self):
        """List all missions with their configs."""
        missions = []
        if not os.path.exists(MISSIONS_DIR):
            return missions
        for d in sorted(os.listdir(MISSIONS_DIR), reverse=True):
            config_path = os.path.join(MISSIONS_DIR, d, "mission_config.json")
            if os.path.exists(config_path):
                try:
                    with open(config_path) as f:
                        cfg = json.load(f)
                    # Count files
                    raw_dir = os.path.join(MISSIONS_DIR, d, "raw")
                    num_files = len(os.listdir(raw_dir)) if os.path.exists(raw_dir) else 0
                    dataset_dir = os.path.join(MISSIONS_DIR, d, "dataset")
                    has_dataset = any(f.endswith(".csv") for f in os.listdir(dataset_dir)) if os.path.exists(dataset_dir) else False
                    cfg["num_files"] = num_files
                    cfg["has_dataset"] = has_dataset
                    missions.append(cfg)
                except Exception:
                    pass
        return missions

    def get_mission_dir(self, mission_id=None):
        mid = mission_id or (self.current_mission["mission_id"] if self.current_mission else None)
        if not mid:
            return None
        return os.path.join(MISSIONS_DIR, mid)

    # ── Pre-flight ──────────────────────────────────────

    async def connect_telemetry(self, port=None, baudrate=57600, simulation=False):
        """Connect telemetry (real or simulation)."""
        if simulation:
            success = await self.telemetry.connect_simulation()
        else:
            success = await self.telemetry.connect(port=port, baudrate=baudrate)

        if success and self.current_mission:
            # Start logging
            tlog_path = os.path.join(
                self.get_mission_dir(),
                "telemetry", "telemetry_log.csv"
            )
            self.telemetry.start_logging(tlog_path)

        return success

    async def connect_gopro(self, mode="wireless", simulation=False, ssid=None, password=None):
        """Connect GoPro wirelessly (BLE→WiFi) or via simulation."""
        if simulation:
            result = await self.gopro.connect_simulation()
            return result.get("success", False) if isinstance(result, dict) else result
        elif mode == "auto":
            result = await self.gopro.connect_auto(ssid=ssid, password=password)
            return result.get("success", False) if isinstance(result, dict) else result
        elif mode == "wifi_direct" or mode == "wifi_manual":
            result = await self.gopro.connect_wifi_direct(ssid=ssid, password=password)
            return result.get("success", False) if isinstance(result, dict) else result
        else:
            result = await self.gopro.connect_wireless()
            return result.get("success", False) if isinstance(result, dict) else result

    async def start_capture(self, mode: str = None, interval: int = None):
        """Start GoPro capture. Uses mission config if mode/interval not specified."""
        if not self.current_mission:
            return {"success": False, "error": "No mission configured"}

        if mode is None:
            mode = self.current_mission.get("capture_mode", "photo")
        if interval is None:
            interval = self.current_mission.get("capture_interval", 2)

        # Store the chosen mode back to mission
        self.current_mission["capture_mode"] = mode
        self.current_mission["capture_interval"] = interval

        result = await self.gopro.configure_and_start_capture(mode, interval)

        if result.get("success"):
            self._set_state("PRE_FLIGHT")
            self.current_mission["capture_start_time"] = self.gopro.capture_start_time
            # Save updated config
            config_path = os.path.join(self.get_mission_dir(), "mission_config.json")
            with open(config_path, "w") as f:
                json.dump(self.current_mission, f, indent=2)

        return result

    def mark_ready_to_fly(self):
        """Manually mark pre-flight as ready (for when operator takes off)."""
        if self.state == "CONFIGURING":
            self._set_state("PRE_FLIGHT")
        return True

    # ── Post-flight ─────────────────────────────────────

    async def start_download(self):
        """Download media from GoPro after landing."""
        if not self.current_mission:
            return {"success": False, "error": "No mission active"}

        self._set_state("DOWNLOADING")
        raw_dir = os.path.join(self.get_mission_dir(), "raw")

        def on_progress(current, total, filename):
            self.download_progress = {
                "current": current,
                "total": total,
                "filename": filename,
                "percent": round((current / total) * 100, 1) if total > 0 else 0,
            }

        result = await self.gopro.download_mission_media(raw_dir, on_progress)

        if result.get("success"):
            self._set_state("SYNCING")
        else:
            self._set_state("LANDING")
        return result

    async def generate_dataset(self):
        """Generate geotagged dataset from telemetry + media."""
        if not self.current_mission:
            return {"success": False, "error": "No mission active"}

        mission_dir = self.get_mission_dir()

        if self.gopro.is_simulation or self.telemetry.is_simulation:
            result = SyncEngine.generate_simulation_dataset(mission_dir)
        else:
            result = SyncEngine.generate_dataset(mission_dir)

        if result.get("success"):
            self.current_mission["status"] = "complete"
            self.current_mission["dataset_path"] = result.get("path")
            self.current_mission["dataset_entries"] = result.get("entries")
            config_path = os.path.join(mission_dir, "mission_config.json")
            with open(config_path, "w") as f:
                json.dump(self.current_mission, f, indent=2)
            self._set_state("COMPLETE")

        return result

    # ── Status ──────────────────────────────────────────

    def get_status(self):
        return {
            "state": self.state,
            "mission": self.current_mission,
            "telemetry": self.telemetry.get_status(),
            "gopro": self.gopro.get_status(),
            "download_progress": self.download_progress,
        }

    async def reset(self):
        """Reset to IDLE state for a new mission."""
        await self.telemetry.disconnect()
        await self.gopro.disconnect()
        self.current_mission = None
        self.download_progress = {"current": 0, "total": 0, "filename": "", "percent": 0}
        self._set_state("IDLE")

    def get_dataset_path(self, mission_id):
        """Get path to dataset CSV for a mission."""
        mission_dir = os.path.join(MISSIONS_DIR, mission_id)
        dataset_dir = os.path.join(mission_dir, "dataset")
        if os.path.exists(dataset_dir):
            for f in os.listdir(dataset_dir):
                if f.endswith(".csv"):
                    return os.path.join(dataset_dir, f)
        return None
