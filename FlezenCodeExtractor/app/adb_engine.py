import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from app.config import (
    get_adb_path,
    SCREENSHOTS_DIR,
    FAILED_DIR,
    DEFAULT_ADB_WAIT_SEC,
)

class ADBAutomationEngine:
    """Controls an Android Device or Emulator to open Flezen links in the native app."""

    def __init__(self, device_id: Optional[str] = None, wait_sec: float = DEFAULT_ADB_WAIT_SEC):
        self.adb_bin = get_adb_path()
        self.device_id = device_id
        self.wait_sec = wait_sec

    def list_devices(self) -> List[Dict[str, str]]:
        """Return list of connected Android devices with their status and model."""
        try:
            res = subprocess.run([self.adb_bin, "devices", "-l"],
                                 capture_output=True, text=True, timeout=8)
            lines = res.stdout.strip().splitlines()
            devices = []
            for line in lines[1:]: # skip "List of devices attached"
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    dev_id = parts[0]
                    state = parts[1]
                    model = "Unknown"
                    for p in parts[2:]:
                        if p.startswith("model:"):
                            model = p.split(":", 1)[1]
                    devices.append({
                        "id": dev_id,
                        "state": state,
                        "model": model,
                        "raw": line
                    })
            return devices
        except Exception:
            return []

    def get_active_device(self) -> Optional[str]:
        if self.device_id and self.device_id != "auto":
            return self.device_id
        devices = self.list_devices()
        authorized = [d for d in devices if d["state"] == "device"]
        if authorized:
            return authorized[0]["id"]
        return None

    def process_url(self, serial_no: int, url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Dispatches Android Intent to open the URL in Flezen app, captures screencap.
        Returns:
            (screenshot_filename, status_note, error_message)
        """
        dev = self.get_active_device()
        if not dev:
            return None, "NO_DEVICE", "No authorized Android device or emulator detected via ADB."

        shot_filename = f"{serial_no:04d}.png"
        shot_path = SCREENSHOTS_DIR / shot_filename

        try:
            # 1. Launch Intent on Android
            cmd = [
                self.adb_bin, "-s", dev, "shell", "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", url
            ]
            subprocess.run(cmd, capture_output=True, timeout=10)

            # 2. Wait for app rendering
            time.sleep(self.wait_sec)

            # 3. Capture screenshot directly from framebuffer
            cap_cmd = [self.adb_bin, "-s", dev, "exec-out", "screencap", "-p"]
            cap_res = subprocess.run(cap_cmd, capture_output=True, timeout=12)

            if cap_res.returncode == 0 and len(cap_res.stdout) > 1000:
                with open(shot_path, "wb") as f:
                    f.write(cap_res.stdout)
                
                # 4. Send Android Back key to reset app state for next URL
                back_cmd = [self.adb_bin, "-s", dev, "shell", "input", "keyevent", "4"]
                subprocess.run(back_cmd, capture_output=True, timeout=5)

                return shot_filename, "ADB_CAPTURED", None
            else:
                err = cap_res.stderr.decode("utf-8", errors="ignore") or "Empty screencap payload"
                return None, "FAILED", f"Screencap failed: {err}"

        except subprocess.TimeoutExpired:
            return None, "TIMEOUT", "ADB operation timed out"
        except Exception as e:
            return None, "FAILED", str(e)

