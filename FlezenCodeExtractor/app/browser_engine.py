import time
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Error as PlaywrightError

from app.config import (
    SCREENSHOTS_DIR,
    FAILED_DIR,
    DEFAULT_PAGE_TIMEOUT_MS,
    DEFAULT_RENDER_WAIT_SEC,
)

class BrowserAutomationEngine:
    """Automates web navigation, image rendering detection, and screenshot capture."""

    def __init__(self, headless: bool = True, use_mobile_emulation: bool = False,
                 page_timeout_ms: int = DEFAULT_PAGE_TIMEOUT_MS,
                 render_wait_sec: float = DEFAULT_RENDER_WAIT_SEC):
        self.headless = headless
        self.use_mobile_emulation = use_mobile_emulation
        self.page_timeout_ms = page_timeout_ms
        self.render_wait_sec = render_wait_sec
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start(self):
        if not self._playwright:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context_args = {
                "viewport": {"width": 1280, "height": 850},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            }
            if self.use_mobile_emulation:
                pixel_device = self._playwright.devices.get("Pixel 5", {})
                context_args.update(pixel_device)

            self._context = self._browser.new_context(**context_args)
            self._page = self._context.new_page()
            self._page.set_default_timeout(self.page_timeout_ms)

    def close(self):
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._page = None

    def process_url(self, serial_no: int, url: str) -> Tuple[Optional[str], str, Optional[str]]:
        """
        Navigates to URL, waits for rendering, captures image screenshot.
        Returns:
            (screenshot_filename, status_note, error_message)
        """
        if not self._page:
            self.start()

        shot_filename = f"{serial_no:04d}.png"
        shot_path = SCREENSHOTS_DIR / shot_filename

        try:
            # 1. Navigate
            response = self._page.goto(url, wait_until="domcontentloaded", timeout=self.page_timeout_ms)
            status_code = response.status if response else 0

            if status_code >= 400:
                self._page.screenshot(path=str(FAILED_DIR / shot_filename))
                return None, "HTTP_ERROR", f"HTTP {status_code}"

            # 2. Dismiss cookie dialogs if present
            self._dismiss_cookie_banners()

            # 3. Wait for rendering
            time.sleep(self.render_wait_sec)

            # 4. Check for rendered image elements
            img_element = self._find_target_image_element()
            if img_element and img_element.is_visible():
                # Element screenshot at native resolution
                img_element.screenshot(path=str(shot_path))
                return shot_filename, "IMAGE_CAPTURED", None

            # 5. Check if page is an App Gate (Mobile App Required)
            body_text = self._page.inner_text("body").lower()
            if "open this file" in body_text or "install flezen" in body_text or "open in app" in body_text:
                self._page.screenshot(path=str(shot_path))
                return shot_filename, "APP_GATE_DETECTED", "File requires Flezen Android App"

            # 6. Capture full viewport screenshot
            self._page.screenshot(path=str(shot_path), full_page=False)
            return shot_filename, "PAGE_CAPTURED", None

        except PlaywrightError as pe:
            error_msg = str(pe).splitlines()[0] if str(pe) else "Playwright Error"
            try:
                self._page.screenshot(path=str(FAILED_DIR / shot_filename))
            except Exception:
                pass
            return None, "FAILED", error_msg
        except Exception as e:
            return None, "FAILED", str(e)

    def _dismiss_cookie_banners(self):
        """Attempts to click cookie dismiss / accept buttons to prevent obstructing views."""
        selectors = [
            "#cookie-accept-all",
            "#cookie-essentials",
            "button:has-text('Accept analytics')",
            "button:has-text('Use essentials')",
            "button:has-text('Accept All')",
            "button:has-text('I Agree')",
        ]
        for sel in selectors:
            try:
                btn = self._page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(timeout=1500)
                    break
            except Exception:
                continue

    def _find_target_image_element(self):
        """Locates the primary content image (ignoring logos and small icons)."""
        images = self._page.query_selector_all("img")
        for img in images:
            try:
                src = img.get_attribute("src") or ""
                if "Flezen.png" in src or "logo" in src.lower() or "icon" in src.lower():
                    continue
                box = img.bounding_box()
                if box and box["width"] > 150 and box["height"] > 80:
                    return img
            except Exception:
                continue
        # Check canvas or preview container
        canvas = self._page.query_selector("canvas")
        if canvas and canvas.is_visible():
            return canvas
        return None

