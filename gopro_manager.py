"""
GoPro Manager — Fully wireless camera control via BLE + WiFi.
Uses Open GoPro SDK's WirelessGoPro for automatic BLE pairing → WiFi connection.
No USB cable needed at any point.
"""
import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "gopro_credentials.json")


class GoProManager:
    """Manages GoPro camera fully wirelessly via BLE → WiFi."""

    def __init__(self):
        self.gopro = None
        self.is_connected = False
        self.is_simulation = False
        self.mode = None  # "wireless", "simulation"
        self.capture_active = False
        self.capture_mode = None  # "photo" or "video"
        self.capture_start_time = None
        self.wifi_credentials = self._load_credentials()

    # ── Credentials Persistence ─────────────────────────

    def _load_credentials(self):
        if os.path.exists(CREDENTIALS_FILE):
            try:
                with open(CREDENTIALS_FILE, "r") as f:
                    creds = json.load(f)
                    logger.info(f"GoPro WiFi credentials loaded (SSID: {creds.get('ssid', '?')})")
                    return creds
            except Exception:
                pass
        return None

    def _save_credentials(self, ssid, password):
        creds = {
            "ssid": ssid,
            "password": password,
            "paired_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(creds, f, indent=2)
        self.wifi_credentials = creds
        logger.info(f"GoPro WiFi credentials saved (SSID: {ssid})")

    def has_wifi_credentials(self):
        return self.wifi_credentials is not None

    # ── Connection (Fully Wireless) ─────────────────────

    async def connect_wireless(self, target=None):
        """
        Connect to GoPro wirelessly via BLE → WiFi.
        
        The Open GoPro SDK WirelessGoPro handles the full flow:
        1. Scans for GoPro devices via BLE
        2. Pairs if not previously paired
        3. Enables the GoPro's WiFi AP via BLE command
        4. Connects the computer to the GoPro's WiFi using nmcli for reliability
        5. Ready for HTTP commands
        """
        if self.is_connected:
            return {"success": True, "message": "Already connected"}

        try:
            from open_gopro import WirelessGoPro

            logger.info("Scanning for GoPro via BLE...")
            # We disable internal wifi handling to use nmcli directly (much more reliable on Linux)
            if target:
                g = WirelessGoPro(target=target, enable_wifi=False)
            else:
                g = WirelessGoPro(enable_wifi=False)

            await g.open()

            # Manually enable the WiFi AP via BLE
            try:
                # Need to use the enable_wifi_ap command
                logger.info("Enabling WiFi AP via BLE...")
                await g.ble_command.enable_wifi_ap(enable=True)
                await asyncio.sleep(2)
            except Exception as e:
                logger.warning(f"Failed to enable WiFi AP via BLE: {e}")

            # Save WiFi credentials for future reference
            ssid = None
            password = None
            try:
                ssid_resp = await g.ble_command.get_wifi_ssid()
                pass_resp = await g.ble_command.get_wifi_password()
                ssid = ssid_resp.data if hasattr(ssid_resp, 'data') else str(ssid_resp)
                password = pass_resp.data if hasattr(pass_resp, 'data') else str(pass_resp)
                self._save_credentials(ssid, password)
            except Exception as e:
                logger.warning(f"Could not save WiFi credentials: {e}")

            # Close BLE connection as we'll use WiFi (WiredGoPro) for the rest
            await g.close()
            
            if not ssid or not password:
                # If we couldn't get credentials, try connecting if we already have them saved
                if self.has_wifi_credentials():
                    ssid = self.wifi_credentials["ssid"]
                    password = self.wifi_credentials["password"]
                else:
                    return {"success": False, "error": "Could not retrieve WiFi credentials from GoPro."}

            logger.info("GoPro paired via BLE. Handing over to WiFi connection...")
            # Use our existing highly reliable nmcli connection method
            return await self.connect_wifi_direct(ssid=ssid, password=password)

        except Exception as e:
            logger.error(f"Wireless connection failed: {e}")
            self.gopro = None
            self.is_connected = False
            return {"success": False, "error": str(e)}

    async def connect_wifi_direct(self, ssid=None, password=None):
        """
        Connect to GoPro using previously saved WiFi credentials.
        Faster than full BLE pairing — uses nmcli to join the GoPro's WiFi AP directly.
        Requires the GoPro's WiFi AP to be already enabled (e.g., from a previous BLE session).
        """
        if self.is_connected:
            return {"success": True, "message": "Already connected"}

        if ssid and password:
            self._save_credentials(ssid, password)

        if not self.wifi_credentials:
            return {"success": False, "error": "No saved WiFi credentials. Use 'Connect Wireless' first to pair via BLE."}

        conn_ssid = self.wifi_credentials["ssid"]
        conn_password = self.wifi_credentials["password"]

        try:
            logger.info(f"Connecting directly to GoPro WiFi AP: {conn_ssid}...")

            # Use nmcli to connect to GoPro's WiFi network
            result = await asyncio.to_thread(
                subprocess.run,
                ["nmcli", "device", "wifi", "connect", conn_ssid, "password", conn_password],
                capture_output=True, text=True, timeout=30,
            )

            if result.returncode != 0:
                logger.error(f"nmcli failed: {result.stderr}")
                return {
                    "success": False,
                    "error": f"WiFi connection failed. Make sure GoPro WiFi is enabled. ({result.stderr.strip()})"
                }

            logger.info("WiFi connected, initializing GoPro HTTP API...")
            await asyncio.sleep(3)

            from open_gopro import WiredGoPro
            WiredGoPro.HTTP_TIMEOUT = 120
            WiredGoPro.HTTP_GET_RETRIES = 10
            self.gopro = WiredGoPro(ip="10.5.5.9")
            await self.gopro.open()

            self.is_connected = True
            self.mode = "wireless"
            self.is_simulation = False
            logger.info("GoPro connected via direct WiFi.")
            return {"success": True, "message": f"Connected via WiFi ({ssid})"}

        except Exception as e:
            logger.error(f"Direct WiFi connection failed: {e}")
            self.gopro = None
            self.is_connected = False
            return {"success": False, "error": str(e)}

    async def connect_auto(self, ssid, password):
        """
        Hybrid auto-connect: Uses BLE to wake up the GoPro's WiFi (with a timeout),
        then immediately uses nmcli to connect directly.
        """
        if self.is_connected:
            return {"success": True, "message": "Already connected"}

        self._save_credentials(ssid, password)

        logger.info("Attempting BLE wake up (ignoring HTTP connection errors)...")
        try:
            from open_gopro import WirelessGoPro
            async def quick_ble_wake():
                g = WirelessGoPro()
                try:
                    await asyncio.wait_for(g.open(), timeout=20)
                    await g.close()
                except Exception as e:
                    logger.debug(f"BLE wake phase ended with: {e}")
            await quick_ble_wake()
        except Exception as e:
            logger.debug(f"BLE wake wrapper error: {e}")

        logger.info("Proceeding to force connection via WiFi direct (nmcli)...")
        return await self.connect_wifi_direct(ssid=ssid, password=password)

    async def connect_simulation(self):
        """Start in simulation mode (no hardware needed)."""
        self.is_connected = True
        self.is_simulation = True
        self.mode = "simulation"
        self.wifi_credentials = {"ssid": "GP-SIM-12345", "password": "simulated"}
        logger.info("GoPro simulation mode started.")
        return {"success": True, "message": "Simulation mode active"}

    async def disconnect(self):
        """Disconnect from GoPro and restore WiFi."""
        if self.gopro:
            try:
                await self.gopro.close()
            except Exception as e:
                logger.warning(f"Error closing GoPro: {e}")
        self.gopro = None
        self.is_connected = False
        self.capture_active = False

        # Try to reconnect to the previous WiFi network
        try:
            await asyncio.to_thread(
                subprocess.run,
                ["nmcli", "device", "wifi", "connect", "auto"],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass

        logger.info("GoPro disconnected.")

    # ── Capture Configuration ───────────────────────────

    async def configure_and_start_capture(self, mode="photo", interval=2):
        """Configure GoPro capture mode and start capturing."""
        if self.is_simulation:
            self.capture_active = True
            self.capture_mode = mode
            self.capture_start_time = datetime.now(timezone.utc).isoformat()
            return {"success": True, "message": f"[SIM] Capture started: {mode}"}

        if not self.is_connected:
            return {"success": False, "error": "Not connected"}

        try:
            from open_gopro.constants import Toggle
            from open_gopro.proto import EnumPresetGroup

            # Disable auto power down during mission
            try:
                await self.gopro.http_setting.auto_power_down.set(0)
            except Exception:
                pass

            if mode == "photo":
                logger.info(f"Configuring photo timelapse (interval={interval}s)...")
                await self.gopro.http_command.load_preset_group(
                    group=EnumPresetGroup.PRESET_GROUP_ID_PHOTO
                )
                await asyncio.sleep(1)
                await self.gopro.http_command.set_shutter(shutter=Toggle.ENABLE)
            else:
                logger.info("Configuring video recording...")
                await self.gopro.http_command.load_preset_group(
                    group=EnumPresetGroup.PRESET_GROUP_ID_VIDEO
                )
                await asyncio.sleep(1)
                await self.gopro.http_command.set_shutter(shutter=Toggle.ENABLE)

            self.capture_active = True
            self.capture_mode = mode
            self.capture_start_time = datetime.now(timezone.utc).isoformat()
            logger.info(f"Capture started: {mode}")
            return {"success": True, "message": f"Capture started: {mode}"}
        except Exception as e:
            logger.error(f"Configure capture failed: {e}")
            return {"success": False, "error": str(e)}

    async def stop_capture(self):
        """Stop any active capture."""
        if self.is_simulation:
            self.capture_active = False
            return {"success": True}
        if not self.is_connected:
            return {"success": False, "error": "Not connected"}
        try:
            from open_gopro.constants import Toggle
            await self.gopro.http_command.set_shutter(shutter=Toggle.DISABLE)
            self.capture_active = False
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Media Download ──────────────────────────────────

    async def download_mission_media(self, output_dir, progress_callback=None):
        """Download all media from GoPro to mission raw directory."""
        os.makedirs(output_dir, exist_ok=True)

        if self.is_simulation:
            return await self._simulate_download(output_dir, progress_callback)

        if not self.is_connected:
            return {"success": False, "error": "Not connected"}

        try:
            import urllib.request

            logger.info("Fetching media list from GoPro...")
            resp = await self.gopro.http_command.get_media_list()
            if not resp.ok or not resp.data.files:
                return {"success": False, "error": "No media found on camera"}

            # GoPro WiFi AP is always at 10.5.5.9
            ip = "10.5.5.9"
            all_files = []
            for group in resp.data.files:
                if hasattr(group, "filename"):
                    all_files.append(group.filename)
                elif hasattr(group, "fs") and hasattr(group, "d"):
                    for f in group.fs:
                        all_files.append(f"{group.d}/{f.n}")

            total = len(all_files)
            downloaded = 0
            results = []

            for i, camera_file in enumerate(all_files):
                file_name = camera_file.split("/")[-1]
                local_path = os.path.join(output_dir, file_name)

                if os.path.exists(local_path):
                    downloaded += 1
                    continue

                url = f"http://{ip}:8080/videos/DCIM/{camera_file}"
                logger.info(f"Downloading [{i+1}/{total}] {file_name}...")

                def do_download(u=url, p=local_path):
                    urllib.request.urlretrieve(u, p)

                await asyncio.to_thread(do_download)
                downloaded += 1
                results.append(file_name)

                if progress_callback:
                    progress_callback(downloaded, total, file_name)

            return {
                "success": True,
                "downloaded": len(results),
                "total": total,
                "files": results,
            }
        except Exception as e:
            logger.error(f"Media download failed: {e}")
            return {"success": False, "error": str(e)}

    async def _simulate_download(self, output_dir, progress_callback=None):
        """Simulate media download for demo purposes."""
        num_files = 12
        files = []
        for i in range(num_files):
            fname = f"GOPR{i+148:04d}.JPG"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, "w") as f:
                f.write(f"simulated photo {i}")
            files.append(fname)
            if progress_callback:
                progress_callback(i + 1, num_files, fname)
            await asyncio.sleep(0.3)

        logger.info(f"[SIM] Downloaded {num_files} simulated files")
        return {
            "success": True,
            "downloaded": num_files,
            "total": num_files,
            "files": files,
        }

    # ── Camera Settings ─────────────────────────────────

    async def get_settings(self):
        """Get current camera settings."""
        if self.is_simulation:
            return {"success": True, "settings": {"gps": 1, "led": 1}}
        if not self.is_connected:
            return {"success": False, "error": "Not connected"}
        try:
            res = await self.gopro.http_command.get_camera_state()
            settings = res.data.get("settings", {})
            return {
                "success": True,
                "settings": {
                    "video_resolution": settings.get("2"),
                    "frames_per_second": settings.get("3"),
                    "video_lens": settings.get("121"),
                    "gps": settings.get("83"),
                    "led": settings.get("91"),
                    "auto_power_down": settings.get("59"),
                },
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Status ──────────────────────────────────────────

    def get_status(self):
        return {
            "connected": self.is_connected,
            "mode": self.mode,
            "simulation": self.is_simulation,
            "capture_active": self.capture_active,
            "capture_mode": self.capture_mode,
            "capture_start_time": self.capture_start_time,
            "has_wifi_credentials": self.has_wifi_credentials(),
            "wifi_ssid": self.wifi_credentials.get("ssid") if self.wifi_credentials else None,
        }
