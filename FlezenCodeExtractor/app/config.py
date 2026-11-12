import os
import shutil
from pathlib import Path

# Paths
APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent

SCREENSHOTS_DIR = PROJECT_DIR / "screenshots"
FAILED_DIR = PROJECT_DIR / "failed"
EXPORTS_DIR = PROJECT_DIR / "exports"
DATABASE_DIR = PROJECT_DIR / "database"
LOGS_DIR = PROJECT_DIR / "logs"

# Ensure runtime directories exist
for p in [SCREENSHOTS_DIR, FAILED_DIR, EXPORTS_DIR, DATABASE_DIR, LOGS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

DB_PATH = DATABASE_DIR / "flezen_extractor.db"

# Bundled Portable Tools
BUNDLED_TESSERACT = PROJECT_DIR / "tesseract-portable" / "tesseract.exe"
BUNDLED_TESSDATA = PROJECT_DIR / "tesseract-portable" / "tessdata"
BUNDLED_ADB = PROJECT_DIR / "platform-tools" / "platform-tools" / "adb.exe"

def get_tesseract_path() -> str:
    """Return path to Tesseract executable, preferring bundled portable version."""
    if BUNDLED_TESSERACT.exists():
        return str(BUNDLED_TESSERACT)
    which_path = shutil.which("tesseract")
    if which_path:
        return which_path
    common_paths = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe"
    ]
    for cp in common_paths:
        if cp.exists():
            return str(cp)
    return "tesseract"

def get_tessdata_prefix() -> str:
    """Return path to tessdata directory."""
    if BUNDLED_TESSDATA.exists():
        return str(BUNDLED_TESSDATA)
    # Check Tesseract install dir
    tess_path = Path(get_tesseract_path()).parent / "tessdata"
    if tess_path.exists():
        return str(tess_path)
    return ""

def get_adb_path() -> str:
    """Return path to ADB executable, preferring bundled platform-tools version."""
    if BUNDLED_ADB.exists():
        return str(BUNDLED_ADB)
    which_path = shutil.which("adb")
    if which_path:
        return which_path
    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
    ]
    for cp in common_paths:
        if cp.exists():
            return str(cp)
    return "adb"

# Default OCR & Automation Settings
DEFAULT_CODE_PATTERN = r"[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}"
DEFAULT_BATCH_SIZE = 5
DEFAULT_CONFIDENCE_THRESHOLD = 75.0
DEFAULT_PAGE_TIMEOUT_MS = 25000
DEFAULT_RENDER_WAIT_SEC = 3.5
DEFAULT_ADB_WAIT_SEC = 4.0

# UI Theme Tokens (Dark Linear / Raycast Style)
THEME = {
    "bg_dark": "#0D0F17",
    "surface": "#141724",
    "surface_card": "#1A1E2E",
    "surface_hover": "#22273B",
    "border": "#282E42",
    "border_focus": "#6366F1",
    
    "primary": "#6366F1",       # Indigo
    "primary_hover": "#4F46E5",
    "accent": "#8B5CF6",        # Purple
    
    "success": "#10B981",       # Emerald
    "warning": "#F59E0B",       # Amber
    "danger": "#EF4444",        # Crimson
    "info": "#3B82F6",          # Blue
    "duplicate": "#EC4899",     # Pink / Magenta
    
    "text_primary": "#F8FAFC",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    
    "font_family": "Segoe UI",
}

