import time
import threading
from typing import List, Dict, Any, Optional, Callable
from pathlib import Path

from app.database import DatabaseManager
from app.ocr_engine import OCREngine
from app.browser_engine import BrowserAutomationEngine
from app.adb_engine import ADBAutomationEngine
from app.config import SCREENSHOTS_DIR

class ExtractionWorker:
    """Threaded execution coordinator for automated link processing, OCR, and persistence."""

    def __init__(self, db: DatabaseManager, session_id: int,
                 mode: str = "browser",  # 'browser', 'adb', or 'local'
                 batch_size: int = 5,
                 ocr_engine: Optional[OCREngine] = None,
                 browser_headless: bool = True,
                 browser_mobile: bool = False,
                 adb_device: Optional[str] = None,
                 adb_wait: float = 4.0,
                 local_image_dir: Optional[str] = None,
                 on_link_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_metrics_update: Optional[Callable[[Dict[str, Any], Optional[float]], None]] = None,
                 on_log: Optional[Callable[[str, str], None]] = None,
                 on_finished: Optional[Callable[[], None]] = None):

        self.db = db
        self.session_id = session_id
        self.mode = mode
        self.batch_size = batch_size
        self.ocr_engine = ocr_engine or OCREngine()
        self.browser_headless = browser_headless
        self.browser_mobile = browser_mobile
        self.adb_device = adb_device
        self.adb_wait = adb_wait
        self.local_image_dir = local_image_dir

        self.on_link_complete = on_link_complete
        self.on_metrics_update = on_metrics_update
        self.on_log = on_log
        self.on_finished = on_finished

        self._thread: Optional[threading.Thread] = None
        self._stop_requested = threading.Event()
        self._pause_requested = threading.Event()

        self._browser_engine: Optional[BrowserAutomationEngine] = None
        self._adb_engine: Optional[ADBAutomationEngine] = None

        self.is_running = False
        self.is_paused = False

    def start(self, specific_link_ids: Optional[List[int]] = None):
        if self.is_running:
            return
        self._stop_requested.clear()
        self._pause_requested.clear()
        self.is_running = True
        self.is_paused = False

        self._thread = threading.Thread(
            target=self._run_loop,
            args=(specific_link_ids,),
            daemon=True,
            name="ExtractionWorkerThread"
        )
        self._thread.start()

    def pause(self):
        if self.is_running and not self.is_paused:
            self._pause_requested.set()
            self.is_paused = True
            self._log("Processing paused by user.", "INFO")

    def resume(self):
        if self.is_running and self.is_paused:
            self._pause_requested.clear()
            self.is_paused = False
            self._log("Processing resumed.", "INFO")

    def stop(self):
        if self.is_running:
            self._stop_requested.set()
            self._pause_requested.clear()
            self.is_running = False
            self.is_paused = False
            self._log("Stopping extraction worker...", "WARNING")

    def _log(self, msg: str, level: str = "INFO"):
        if self.on_log:
            self.on_log(msg, level)

    def _run_loop(self, specific_link_ids: Optional[List[int]]):
        self._log(f"Starting extraction worker in [{self.mode.upper()}] mode...", "INFO")

        # Initialize engine based on mode
        if self.mode == "browser":
            try:
                self._browser_engine = BrowserAutomationEngine(
                    headless=self.browser_headless,
                    use_mobile_emulation=self.browser_mobile
                )
                self._browser_engine.start()
            except Exception as e:
                self._log(f"Failed to initialize Playwright browser: {e}", "DANGER")
                self.is_running = False
                return
        elif self.mode == "adb":
            self._adb_engine = ADBAutomationEngine(
                device_id=self.adb_device,
                wait_sec=self.adb_wait
            )
            dev = self._adb_engine.get_active_device()
            if not dev:
                self._log("No ADB device found! Please connect device or start emulator.", "DANGER")
                self.is_running = False
                return
            self._log(f"ADB Engine connected to device: {dev}", "SUCCESS")

        # Fetch links to process
        all_links = self.db.get_session_links(self.session_id)
        if specific_link_ids:
            queue = [l for l in all_links if l["id"] in specific_link_ids]
        else:
            # Process pending or failed links
            queue = [l for l in all_links if l["processing_status"] in ("PENDING", "FAILED")]

        total_in_queue = len(queue)
        self._log(f"Queue loaded: {total_in_queue} links to process.", "INFO")

        processed_count = 0
        durations: List[float] = []

        try:
            for link in queue:
                if self._stop_requested.is_set():
                    break

                # Handle Pause
                while self._pause_requested.is_set():
                    time.sleep(0.5)
                    if self._stop_requested.is_set():
                        break

                if self._stop_requested.is_set():
                    break

                t_start = time.time()
                link_id = link["id"]
                serial_no = link["serial_no"]
                url = link["url"]

                self._log(f"Processing #{serial_no:04d}: {url}", "INFO")

                # Step 1: Capture Screenshot
                shot_filename: Optional[str] = None
                capture_status: str = "PENDING"
                error_msg: Optional[str] = None

                if self.mode == "browser" and self._browser_engine:
                    shot_filename, capture_status, error_msg = self._browser_engine.process_url(serial_no, url)
                elif self.mode == "adb" and self._adb_engine:
                    shot_filename, capture_status, error_msg = self._adb_engine.process_url(serial_no, url)
                elif self.mode == "local":
                    # Local image folder mode: check if screenshot already exists
                    possible_name = f"{serial_no:04d}.png"
                    local_dir = Path(self.local_image_dir) if self.local_image_dir else SCREENSHOTS_DIR
                    candidate_file = local_dir / possible_name
                    if candidate_file.exists():
                        shot_filename = possible_name
                        capture_status = "LOCAL_EXISTS"
                    else:
                        capture_status = "FAILED"
                        error_msg = f"Screenshot {possible_name} not found in folder"

                # Step 2: OCR Extraction
                code: Optional[str] = None
                confidence = 0.0
                final_status = "FAILED"
                verification_status = "UNVERIFIED"

                if shot_filename:
                    shot_path = SCREENSHOTS_DIR / shot_filename
                    if not shot_path.exists() and self.local_image_dir:
                        shot_path = Path(self.local_image_dir) / shot_filename

                    code, confidence, ocr_status, details = self.ocr_engine.extract_code(shot_path)
                    final_status = ocr_status
                    if ocr_status == "SUCCESS":
                        self._log(f"✓ #{serial_no:04d} Code: {code} ({confidence:.1f}%)", "SUCCESS")
                    elif ocr_status == "NEEDS_REVIEW":
                        self._log(f"⚠ #{serial_no:04d} Review: {code or details}", "WARNING")
                    else:
                        error_msg = details
                        self._log(f"✗ #{serial_no:04d} OCR Failed: {details}", "DANGER")
                else:
                    final_status = "FAILED"
                    self._log(f"✗ #{serial_no:04d} Capture Failed: {error_msg}", "DANGER")

                # Step 3: Immediate Auto-Save to SQLite
                self.db.update_link_result(
                    link_id=link_id,
                    status=final_status,
                    code=code,
                    confidence=confidence,
                    screenshot_filename=shot_filename,
                    verification_status=verification_status,
                    error_message=error_msg
                )

                t_elapsed = time.time() - t_start
                durations.append(t_elapsed)
                processed_count += 1

                # Calculate ETA
                avg_dur = sum(durations[-10:]) / len(durations[-10:]) if durations else 4.0
                remaining_links = total_in_queue - processed_count
                eta_sec = remaining_links * avg_dur

                # Step 4: Notify GUI
                updated_row = {
                    "id": link_id,
                    "serial_no": serial_no,
                    "url": url,
                    "code": code,
                    "confidence": confidence,
                    "screenshot_filename": shot_filename,
                    "processing_status": final_status,
                    "verification_status": verification_status,
                    "error_message": error_msg
                }

                if self.on_link_complete:
                    self.on_link_complete(updated_row)

                if self.on_metrics_update:
                    metrics = self.db.get_session_metrics(self.session_id)
                    self.on_metrics_update(metrics, eta_sec)

        except Exception as e:
            self._log(f"Worker encountered unexpected error: {e}", "DANGER")
        finally:
            if self._browser_engine:
                self._browser_engine.close()
                self._browser_engine = None

            self.is_running = False
            self.is_paused = False
            self._log("Extraction worker finished run.", "INFO")
            if self.on_finished:
                self.on_finished()

