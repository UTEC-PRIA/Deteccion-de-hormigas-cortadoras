"""
Telemetry Manager — MAVLink communication with Pixhawk via SiK radio.
Supports real-time telemetry logging, flight state detection, and simulation mode.
"""
import asyncio
import csv
import json
import logging
import math
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class TelemetryManager:
    """Manages MAVLink telemetry connection to Pixhawk flight controller."""

    FLIGHT_MODES = {
        0: "STABILIZE", 1: "ACRO", 2: "ALT_HOLD", 3: "AUTO",
        4: "GUIDED", 5: "LOITER", 6: "RTL", 7: "CIRCLE",
        9: "LAND", 11: "DRIFT", 13: "SPORT", 14: "FLIP",
        15: "AUTOTUNE", 16: "POSHOLD", 17: "BRAKE",
    }

    def __init__(self):
        self.connection = None
        self.is_connected = False
        self.is_simulation = False
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # Current telemetry data
        self.current_data = {
            "lat": 0.0, "lon": 0.0, "alt": 0.0,
            "relative_alt": 0.0, "speed": 0.0, "heading": 0,
            "battery_voltage": 0.0, "battery_percent": -1,
            "flight_mode": "UNKNOWN", "armed": False,
            "gps_fix": 0, "satellites": 0,
            "timestamp": None,
            "mission_count": 0,
            "mission_current": 0,
            "mission_loaded": False,
        }
        self.flight_state = "UNKNOWN"  # DISARMED, ARMED, TAKEOFF, IN_FLIGHT, RTL, LANDING, LANDED
        self.flight_trace = []  # List of {lat, lon} for map trace
        self.mission_start_time = None

        # CSV logging
        self._csv_file = None
        self._csv_writer = None
        self._csv_path = None

        # Simulation
        self._sim_phase = 0
        self._sim_tick = 0
        self._sim_home = {"lat": -30.9000, "lon": -55.5500}
        self._sim_waypoints = []

        # Event callbacks
        self._state_callbacks = []

    def on_state_change(self, callback):
        """Register a callback for flight state changes."""
        self._state_callbacks.append(callback)

    def _notify_state_change(self, old_state, new_state):
        for cb in self._state_callbacks:
            try:
                cb(old_state, new_state)
            except Exception as e:
                logger.error(f"State callback error: {e}")

    # ── Connection ──────────────────────────────────────

    async def connect(self, port="/dev/ttyUSB0", baudrate=57600):
        """Connect to Pixhawk via serial (MAVLink)."""
        if self.is_connected:
            return True
        try:
            from pymavlink import mavutil
            logger.info(f"Connecting to MAVLink on {port} at {baudrate} baud...")
            self.connection = mavutil.mavlink_connection(port, baud=baudrate, source_system=254)
            logger.info("Waiting for heartbeat...")
            self.connection.wait_heartbeat(timeout=10)
            logger.info(f"Heartbeat received (system {self.connection.target_system})")
            self.is_connected = True
            self.is_simulation = False
            self._start_read_loop()
            return True
        except Exception as e:
            logger.error(f"MAVLink connection failed: {e}")
            self.connection = None
            return False

    async def auto_connect(self, baudrate=None):
        """
        Automatically scan all serial ports. If found, start MAVProxy Router
        to share the port with Mission Planner, and connect to tcp:5761.
        """
        if self.is_connected:
            return True

        # 1. Try UDP connection to MAVProxy first (port 14551 = our app's port)
        from mavproxy_router import router
        
        if router.is_running:
            logger.info("MAVProxy router is running. Connecting to udpin:0.0.0.0:14551...")
            success = await self.connect(port="udpin:0.0.0.0:14551")
            if success:
                return True
        else:
            try:
                logger.info("Checking if an external MAVProxy is sending UDP to 14551...")
                success = await self.connect(port="udpin:0.0.0.0:14551", baudrate=57600)
                if success:
                    logger.info("Connected via UDP.")
                    return True
            except Exception:
                pass

        # 2. If not running, start MAVProxy router (it will auto-detect USB ports internally)
        logger.info("Starting MAVProxy router to share connection...")
        res = await router.start()
        
        if res.get("success"):
            logger.info("MAVProxy router started successfully. Connecting to udpin:0.0.0.0:14551...")
            return await self.connect(port="udpin:0.0.0.0:14551")
            
        logger.error(f"Auto-connect failed: {res.get('error', 'Could not start MAVProxy')}")
        return False

    async def connect_simulation(self):
        """Start in simulation mode with fake telemetry data."""
        if self.is_connected:
            return True
        logger.info("Starting telemetry simulation mode...")
        self.is_connected = True
        self.is_simulation = True
        self._sim_phase = 0
        self._sim_tick = 0
        self._build_sim_waypoints()
        self._start_read_loop()
        return True

    async def disconnect(self):
        """Disconnect from MAVLink or stop simulation."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None
        if self.connection:
            self.connection.close()
            self.connection = None
        self.stop_logging()
        self.is_connected = False
        self.is_simulation = False
        self.flight_state = "UNKNOWN"
        self.flight_trace = []
        logger.info("Telemetry disconnected.")

    # ── CSV Logging ─────────────────────────────────────

    def start_logging(self, csv_path):
        """Start logging telemetry to CSV file."""
        self.stop_logging()
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        self._csv_path = csv_path
        self._csv_file = open(csv_path, "w", newline="")
        self._csv_writer = csv.writer(self._csv_file)
        self._csv_writer.writerow([
            "timestamp", "lat", "lon", "alt", "relative_alt",
            "speed", "heading", "battery_percent", "flight_mode", "armed"
        ])
        self.mission_start_time = datetime.now(timezone.utc).isoformat()
        logger.info(f"Telemetry logging started → {csv_path}")

    def stop_logging(self):
        """Stop CSV logging."""
        if self._csv_file:
            self._csv_file.close()
            self._csv_file = None
            self._csv_writer = None
            logger.info("Telemetry logging stopped.")

    def _log_row(self):
        if self._csv_writer:
            d = self.current_data
            self._csv_writer.writerow([
                d["timestamp"], d["lat"], d["lon"], d["alt"],
                d["relative_alt"], d["speed"], d["heading"],
                d["battery_percent"], d["flight_mode"], d["armed"]
            ])
            self._csv_file.flush()

    # ── Read Loop ───────────────────────────────────────

    def _start_read_loop(self):
        self._running = True
        target = self._simulation_loop if self.is_simulation else self._mavlink_loop
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()

    def _mavlink_loop(self):
        """Background thread: read MAVLink messages."""
        while self._running:
            try:
                msg = self.connection.recv_match(blocking=True, timeout=1)
                if msg:
                    self._process_message(msg)
            except Exception as e:
                logger.error(f"MAVLink read error: {e}")
                time.sleep(0.5)

    def _process_message(self, msg):
        msg_type = msg.get_type()
        with self._lock:
            if msg_type == "GLOBAL_POSITION_INT":
                self.current_data["lat"] = msg.lat / 1e7
                self.current_data["lon"] = msg.lon / 1e7
                self.current_data["alt"] = msg.alt / 1000.0
                self.current_data["relative_alt"] = msg.relative_alt / 1000.0
                self.current_data["heading"] = msg.hdg / 100 if msg.hdg != 65535 else 0
                self.current_data["timestamp"] = datetime.now(timezone.utc).isoformat()
                self._update_trace()
                self._log_row()
            elif msg_type == "VFR_HUD":
                self.current_data["speed"] = round(msg.groundspeed, 1)
                if hasattr(msg, "heading"):
                    self.current_data["heading"] = msg.heading
            elif msg_type == "SYS_STATUS":
                self.current_data["battery_voltage"] = msg.voltage_battery / 1000.0
                self.current_data["battery_percent"] = msg.battery_remaining
            elif msg_type == "GPS_RAW_INT":
                self.current_data["gps_fix"] = msg.fix_type
                self.current_data["satellites"] = msg.satellites_visible
            elif msg_type == "HEARTBEAT":
                custom_mode = msg.custom_mode
                self.current_data["flight_mode"] = self.FLIGHT_MODES.get(custom_mode, f"MODE_{custom_mode}")
                from pymavlink import mavutil
                armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                self.current_data["armed"] = armed
                self._detect_state_change()
            elif msg_type == "MISSION_COUNT":
                self.current_data["mission_count"] = msg.count
                logger.info(f"Incoming mission detected: {msg.count} waypoints.")
            elif msg_type == "MISSION_ACK":
                self.current_data["mission_loaded"] = True
                logger.info("Mission successfully loaded and ACKed by drone.")
            elif msg_type == "MISSION_CURRENT":
                self.current_data["mission_current"] = msg.seq

    def _update_trace(self):
        d = self.current_data
        if d["lat"] != 0 and d["lon"] != 0:
            self.flight_trace.append({"lat": d["lat"], "lon": d["lon"]})
            if len(self.flight_trace) > 5000:
                self.flight_trace = self.flight_trace[-5000:]

    def _detect_state_change(self):
        d = self.current_data
        old_state = self.flight_state
        mode = d["flight_mode"]
        armed = d["armed"]

        if not armed:
            new_state = "LANDED" if old_state in ("LANDING", "RTL", "IN_FLIGHT") else "DISARMED"
        elif mode == "LAND":
            new_state = "LANDING"
        elif mode == "RTL":
            new_state = "RTL"
        elif mode in ("AUTO", "GUIDED", "LOITER", "POSHOLD"):
            new_state = "IN_FLIGHT"
        elif armed and d["relative_alt"] < 2:
            new_state = "ARMED"
        else:
            new_state = "TAKEOFF" if d["relative_alt"] < 10 else "IN_FLIGHT"

        if new_state != old_state:
            self.flight_state = new_state
            logger.info(f"Flight state: {old_state} → {new_state}")
            self._notify_state_change(old_state, new_state)

    # ── Simulation ──────────────────────────────────────

    def _build_sim_waypoints(self):
        h = self._sim_home
        d = 0.0008  # ~80m offset
        self._sim_waypoints = [
            (h["lat"], h["lon"]),
            (h["lat"] - d, h["lon"]),
            (h["lat"] - d, h["lon"] - d),
            (h["lat"] - 2*d, h["lon"] - d),
            (h["lat"] - 2*d, h["lon"]),
            (h["lat"] - 3*d, h["lon"]),
            (h["lat"] - 3*d, h["lon"] - d),
            (h["lat"], h["lon"]),  # RTL
        ]

    def _simulation_loop(self):
        """Simulate a full mission flight."""
        # Phases: 0=IDLE, 1=ARMED, 2=TAKEOFF, 3=FLYING, 4=RTL, 5=LAND, 6=DISARMED
        phases = [
            {"name": "DISARMED", "mode": "STABILIZE", "duration": 5, "armed": False},
            {"name": "ARMED", "mode": "STABILIZE", "duration": 3, "armed": True},
            {"name": "TAKEOFF", "mode": "GUIDED", "duration": 6, "armed": True},
            {"name": "IN_FLIGHT", "mode": "AUTO", "duration": 60, "armed": True},
            {"name": "RTL", "mode": "RTL", "duration": 10, "armed": True},
            {"name": "LANDING", "mode": "LAND", "duration": 6, "armed": True},
            {"name": "LANDED", "mode": "STABILIZE", "duration": 999, "armed": False},
        ]
        phase_idx = 0
        tick = 0
        wp_idx = 0
        wp_progress = 0.0
        alt = 0.0
        target_alt = 45.0
        battery = 100.0
        home = self._sim_home

        while self._running:
            phase = phases[phase_idx]
            old_state = self.flight_state

            with self._lock:
                self.current_data["flight_mode"] = phase["mode"]
                self.current_data["armed"] = phase["armed"]
                self.current_data["gps_fix"] = 3
                self.current_data["satellites"] = 14
                self.current_data["battery_percent"] = max(0, int(battery))
                self.current_data["battery_voltage"] = 11.1 + (battery / 100) * 1.5
                self.current_data["timestamp"] = datetime.now(timezone.utc).isoformat()

                if phase["name"] == "DISARMED" or phase["name"] == "ARMED":
                    self.current_data["lat"] = home["lat"]
                    self.current_data["lon"] = home["lon"]
                    self.current_data["alt"] = 0
                    self.current_data["relative_alt"] = 0
                    self.current_data["speed"] = 0
                    self.current_data["heading"] = 0

                elif phase["name"] == "TAKEOFF":
                    frac = tick / max(phase["duration"], 1)
                    alt = target_alt * min(frac, 1.0)
                    self.current_data["lat"] = home["lat"]
                    self.current_data["lon"] = home["lon"]
                    self.current_data["alt"] = alt
                    self.current_data["relative_alt"] = alt
                    self.current_data["speed"] = 2.0
                    battery -= 0.3

                elif phase["name"] == "IN_FLIGHT":
                    wps = self._sim_waypoints
                    if wp_idx < len(wps) - 1:
                        wp_progress += 0.03
                        if wp_progress >= 1.0:
                            wp_progress = 0.0
                            wp_idx += 1
                        if wp_idx < len(wps) - 1:
                            a = wps[wp_idx]
                            b = wps[wp_idx + 1]
                            lat = a[0] + (b[0] - a[0]) * wp_progress
                            lon = a[1] + (b[1] - a[1]) * wp_progress
                            hdg = math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])) % 360
                            self.current_data["lat"] = lat
                            self.current_data["lon"] = lon
                            self.current_data["heading"] = int(hdg)
                    self.current_data["alt"] = target_alt
                    self.current_data["relative_alt"] = target_alt
                    self.current_data["speed"] = 5.5
                    battery -= 0.15

                elif phase["name"] == "RTL":
                    frac = tick / max(phase["duration"], 1)
                    cur_lat = self.current_data["lat"]
                    cur_lon = self.current_data["lon"]
                    self.current_data["lat"] = cur_lat + (home["lat"] - cur_lat) * 0.1
                    self.current_data["lon"] = cur_lon + (home["lon"] - cur_lon) * 0.1
                    self.current_data["alt"] = target_alt
                    self.current_data["relative_alt"] = target_alt
                    self.current_data["speed"] = 6.0
                    battery -= 0.2

                elif phase["name"] == "LANDING":
                    frac = tick / max(phase["duration"], 1)
                    alt = target_alt * (1.0 - min(frac, 1.0))
                    self.current_data["lat"] = home["lat"]
                    self.current_data["lon"] = home["lon"]
                    self.current_data["alt"] = alt
                    self.current_data["relative_alt"] = alt
                    self.current_data["speed"] = 1.0
                    battery -= 0.1

                elif phase["name"] == "LANDED":
                    self.current_data["lat"] = home["lat"]
                    self.current_data["lon"] = home["lon"]
                    self.current_data["alt"] = 0
                    self.current_data["relative_alt"] = 0
                    self.current_data["speed"] = 0

                self._update_trace()
                self._log_row()

            # Update flight state
            self.flight_state = phase["name"]
            if phase["name"] != old_state:
                logger.info(f"[SIM] Flight state: {old_state} → {phase['name']}")
                self._notify_state_change(old_state, phase["name"])

            tick += 1
            if tick >= phase["duration"] and phase_idx < len(phases) - 1:
                phase_idx += 1
                tick = 0

            time.sleep(1)

    # ── Public API ──────────────────────────────────────

    def get_current_data(self):
        with self._lock:
            return dict(self.current_data)

    def get_status(self):
        return {
            "connected": self.is_connected,
            "simulation": self.is_simulation,
            "flight_state": self.flight_state,
            "data": self.get_current_data(),
            "trace_length": len(self.flight_trace),
        }

    def get_trace(self):
        with self._lock:
            return list(self.flight_trace)

    @staticmethod
    def list_serial_ports():
        """List available serial ports on the system (USB only)."""
        ports = []
        try:
            import serial.tools.list_ports
            for p in serial.tools.list_ports.comports():
                # Only include USB-connected serial ports (SiK radio, Pixhawk, etc.)
                if any(x in p.device for x in ['USB', 'ACM']):
                    ports.append({"device": p.device, "description": p.description})
        except ImportError:
            import glob
            for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
                ports.extend([{"device": d, "description": ""} for d in glob.glob(pattern)])
        return ports
