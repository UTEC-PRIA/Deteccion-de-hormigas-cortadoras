"""
Sync Engine — Matches GoPro media timestamps with telemetry positions.
Generates geotagged datasets for post-processing.
"""
import csv
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncEngine:
    """Synchronizes GoPro media with drone telemetry data by timestamp matching."""

    @staticmethod
    def generate_dataset(mission_dir, clock_offset_seconds=0):
        """
        Generate a geotagged dataset CSV by matching media EXIF timestamps
        with telemetry log positions.

        Args:
            mission_dir: Path to mission directory (contains raw/, telemetry/)
            clock_offset_seconds: Offset in seconds (gopro_time - system_time)

        Returns:
            dict with success status and dataset path
        """
        telemetry_dir = os.path.join(mission_dir, "telemetry")
        raw_dir = os.path.join(mission_dir, "raw")
        dataset_dir = os.path.join(mission_dir, "dataset")
        os.makedirs(dataset_dir, exist_ok=True)

        # Find telemetry log
        tlog_path = os.path.join(telemetry_dir, "telemetry_log.csv")
        if not os.path.exists(tlog_path):
            logger.error(f"Telemetry log not found: {tlog_path}")
            return {"success": False, "error": "Telemetry log not found"}

        # Read telemetry data
        telemetry_data = SyncEngine.read_telemetry_log(tlog_path)
        if not telemetry_data:
            return {"success": False, "error": "No telemetry data in log"}

        # Read media timestamps
        media_files = SyncEngine.read_media_timestamps(raw_dir)
        if not media_files:
            return {"success": False, "error": "No media files with timestamps found"}

        # Match each media file to closest telemetry position
        dataset = []
        for media in media_files:
            media_ts = media["timestamp"]
            # Apply clock offset
            adjusted_ts = media_ts + timedelta(seconds=clock_offset_seconds)

            closest = SyncEngine.find_closest_position(adjusted_ts, telemetry_data)
            if closest:
                dataset.append({
                    "image": media["filename"],
                    "image_timestamp": media_ts.isoformat(),
                    "telemetry_timestamp": closest["timestamp"],
                    "lat": closest["lat"],
                    "lon": closest["lon"],
                    "alt": closest["alt"],
                    "relative_alt": closest["relative_alt"],
                    "speed": closest["speed"],
                    "heading": closest["heading"],
                    "time_diff_ms": closest["time_diff_ms"],
                })

        if not dataset:
            return {"success": False, "error": "No matches found between media and telemetry"}

        # Write dataset CSV
        mission_id = os.path.basename(mission_dir)
        dataset_path = os.path.join(dataset_dir, f"dataset_{mission_id}.csv")
        fieldnames = [
            "image", "image_timestamp", "telemetry_timestamp",
            "lat", "lon", "alt", "relative_alt",
            "speed", "heading", "time_diff_ms"
        ]

        with open(dataset_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(dataset)

        logger.info(f"Dataset generated: {dataset_path} ({len(dataset)} entries)")
        return {
            "success": True,
            "path": dataset_path,
            "entries": len(dataset),
            "dataset": dataset,
        }

    @staticmethod
    def read_telemetry_log(csv_path):
        """Read telemetry CSV into list of dicts with parsed timestamps."""
        data = []
        try:
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        ts_str = row.get("timestamp", "")
                        if not ts_str:
                            continue
                        ts = datetime.fromisoformat(ts_str)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        data.append({
                            "timestamp": ts_str,
                            "datetime": ts,
                            "lat": float(row.get("lat", 0)),
                            "lon": float(row.get("lon", 0)),
                            "alt": float(row.get("alt", 0)),
                            "relative_alt": float(row.get("relative_alt", 0)),
                            "speed": float(row.get("speed", 0)),
                            "heading": float(row.get("heading", 0)),
                        })
                    except (ValueError, KeyError) as e:
                        continue
        except Exception as e:
            logger.error(f"Error reading telemetry log: {e}")
        return data

    @staticmethod
    def read_media_timestamps(media_dir):
        """Read timestamps from media files (EXIF for photos, mtime fallback)."""
        media = []
        if not os.path.exists(media_dir):
            return media

        try:
            from PIL import Image
            from PIL.ExifTags import Base as ExifBase
            has_pillow = True
        except ImportError:
            has_pillow = False
            logger.warning("Pillow not installed, using file mtime for timestamps")

        photo_extensions = {".jpg", ".jpeg", ".png", ".dng", ".raw"}
        video_extensions = {".mp4", ".mov", ".avi"}
        valid_extensions = photo_extensions | video_extensions

        for fname in sorted(os.listdir(media_dir)):
            fpath = os.path.join(media_dir, fname)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in valid_extensions:
                continue

            timestamp = None

            # Try EXIF first for photos
            if has_pillow and ext in photo_extensions:
                try:
                    img = Image.open(fpath)
                    exif = img._getexif()
                    if exif:
                        # DateTimeOriginal = 36867, DateTimeDigitized = 36868
                        for tag_id in (36867, 36868, 306):
                            val = exif.get(tag_id)
                            if val:
                                try:
                                    timestamp = datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
                                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                                    break
                                except ValueError:
                                    continue
                    img.close()
                except Exception as e:
                    logger.debug(f"EXIF read failed for {fname}: {e}")

            # Fallback to file modification time
            if timestamp is None:
                mtime = os.path.getmtime(fpath)
                timestamp = datetime.fromtimestamp(mtime, tz=timezone.utc)

            media.append({
                "filename": fname,
                "filepath": fpath,
                "timestamp": timestamp,
                "type": "photo" if ext in photo_extensions else "video",
            })

        # Sort by timestamp
        media.sort(key=lambda x: x["timestamp"])
        return media

    @staticmethod
    def find_closest_position(target_time, telemetry_data):
        """Find the telemetry position closest to the given timestamp."""
        if not telemetry_data:
            return None

        best = None
        best_diff = float("inf")

        for entry in telemetry_data:
            diff = abs((entry["datetime"] - target_time).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best = entry

        if best and best_diff < 30:  # Max 30 seconds tolerance
            return {
                "timestamp": best["timestamp"],
                "lat": best["lat"],
                "lon": best["lon"],
                "alt": best["alt"],
                "relative_alt": best["relative_alt"],
                "speed": best["speed"],
                "heading": best["heading"],
                "time_diff_ms": int(best_diff * 1000),
            }
        return None

    @staticmethod
    def generate_simulation_dataset(mission_dir, num_photos=12):
        """Generate a fake dataset for simulation/demo purposes."""
        dataset_dir = os.path.join(mission_dir, "dataset")
        os.makedirs(dataset_dir, exist_ok=True)
        raw_dir = os.path.join(mission_dir, "raw")
        os.makedirs(raw_dir, exist_ok=True)

        mission_id = os.path.basename(mission_dir)
        dataset_path = os.path.join(dataset_dir, f"dataset_{mission_id}.csv")

        base_lat, base_lon = -30.9000, -55.5500
        base_time = datetime.now(timezone.utc)
        dataset = []

        for i in range(num_photos):
            fname = f"GOPR{i+148:04d}.JPG"
            t = base_time + timedelta(seconds=i * 5)
            lat = base_lat - (i * 0.0003)
            lon = base_lon - ((i % 4) * 0.0002)

            # Create empty placeholder file
            open(os.path.join(raw_dir, fname), "w").close()

            dataset.append({
                "image": fname,
                "image_timestamp": t.isoformat(),
                "telemetry_timestamp": t.isoformat(),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "alt": 45.0 + (i * 0.5),
                "relative_alt": 45.0,
                "speed": 5.2,
                "heading": 180 + (i * 15) % 360,
                "time_diff_ms": 120 + i * 10,
            })

        fieldnames = list(dataset[0].keys())
        with open(dataset_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(dataset)

        logger.info(f"[SIM] Dataset generated: {dataset_path} ({num_photos} entries)")
        return {
            "success": True,
            "path": dataset_path,
            "entries": num_photos,
            "dataset": dataset,
        }
