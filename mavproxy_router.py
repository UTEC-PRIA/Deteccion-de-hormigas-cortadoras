"""
MAVProxy Router — Serial → TCP Multiplexer
Allows Mission Planner AND our FastAPI app to simultaneously receive MAVLink telemetry
from a single SiK radio connected via USB.

Architecture:
    SiK Radio (USB serial) → MAVProxy → TCP:5760 (Mission Planner)
                                      → TCP:5761 (Our app)
                                      → UDP:14550 (optional extra)
"""
import asyncio
import logging
import subprocess
import threading
import glob
import time
import os

logger = logging.getLogger(__name__)

COMMON_BAUDRATES = [57600, 115200, 9600, 38400, 19200]


class MAVProxyRouter:
    """Manages a MAVProxy process that multiplexes a single serial port to multiple TCP sinks."""

    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._running = False
        self._port: str | None = None
        self._baudrate: int | None = None

    @property
    def is_running(self):
        if self._process is None:
            return False
        return self._process.poll() is None

    def get_status(self):
        return {
            "running": self.is_running,
            "port": self._port,
            "baudrate": self._baudrate,
            "tcp_mission_planner": "tcp://localhost:5760",
            "tcp_our_app": "tcp://localhost:5761",
        }

    def _detect_port_and_baud(self):
        """Probe serial ports with common baudrates to find the SiK radio."""
        candidates = []
        for pattern in ["/dev/ttyUSB*", "/dev/ttyACM*"]:
            candidates.extend(sorted(glob.glob(pattern)))

        if not candidates:
            return None, None

        try:
            from pymavlink import mavutil
        except ImportError:
            logger.error("pymavlink not installed")
            return None, None

        for port in candidates:
            for baud in COMMON_BAUDRATES:
                logger.info(f"Probing {port} @ {baud}...")
                try:
                    conn = mavutil.mavlink_connection(port, baud=baud, autoreconnect=False)
                    hb = conn.wait_heartbeat(timeout=5)
                    conn.close()
                    if hb:
                        logger.info(f"✅ Heartbeat found on {port} @ {baud}")
                        return port, baud
                except Exception as e:
                    logger.debug(f"  {port}@{baud}: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass

        return None, None

    async def start(self, port=None, baudrate=None):
        """Start MAVProxy. Auto-detects port/baudrate if not provided."""
        if self.is_running:
            return {"success": True, "message": "Already running", **self.get_status()}

        if port is None or baudrate is None:
            logger.info("Auto-detecting serial port and baudrate...")
            port, baudrate = await asyncio.to_thread(self._detect_port_and_baud)

        if port is None:
            return {"success": False, "error": "No MAVLink device found on any serial port."}

        self._port = port
        self._baudrate = baudrate

        cmd = [
            "mavproxy.py",
            f"--master={port}",
            f"--baudrate={baudrate}",
            "--out=tcpin:0.0.0.0:5760",   # Mission Planner connects here
            "--out=tcpin:0.0.0.0:5761",   # Our app connects here
            "--out=udpout:0.0.0.0:14550", # QGC / extra clients
            "--daemon",
            "--non-interactive",
            "--default-modules=''",
        ]

        logger.info(f"Starting MAVProxy: {' '.join(cmd)}")
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            # Give it 2s to start up
            await asyncio.sleep(2)

            if not self.is_running:
                out, _ = self._process.communicate(timeout=3)
                return {"success": False, "error": f"MAVProxy exited: {out[:500]}"}

            logger.info("MAVProxy router started successfully.")
            return {"success": True, **self.get_status()}

        except FileNotFoundError:
            return {"success": False, "error": "mavproxy.py not found. Run: pip install MAVProxy"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def stop(self):
        """Stop MAVProxy."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._port = None
        self._baudrate = None
        logger.info("MAVProxy router stopped.")
        return {"success": True}


# Singleton instance
router = MAVProxyRouter()
