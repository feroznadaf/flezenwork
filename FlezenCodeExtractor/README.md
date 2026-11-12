# Flezen Bulk Code Extractor

**A Production-Quality Windows Desktop Automation & OCR Application**  
*Built for High-Throughput URL Processing, Image Capture, 12-Character Alphanumeric Code Extraction, and Multi-Tab Excel Reporting.*

---

## 1. Executive Summary & Architecture Overview

**Flezen Bulk Code Extractor** is a high-performance Windows desktop application designed to eliminate manual data entry across large batches of Flezen file-sharing links. The system takes documents such as `PWN_Studio_Hiring_Test_Links_Part_1.pdf` (1,000 links across 24 pages), extracts and deduplicates all URLs in sequential order, automates image rendering and screen capture, runs high-precision OCR with OpenCV multi-pass preprocessing, validates the required `XXXX-XXXX-XXXX` alphanumeric code format, and generates comprehensive Excel workbooks with multiple categorization tabs.

### Architecture Highlights
- **Modern Linear / Stripe / Raycast Dark Dashboard**: CustomTkinter desktop interface featuring real-time stat cards, dynamic ETA countdown, search & filtering, live activity logs, and a side-by-side screenshot inspector.
- **Dual-Mode Automation Engine**:
  1. **Playwright Chromium Browser**: For desktop/mobile web rendering, automated cookie dialog suppression, and element screenshot capture.
  2. **Android ADB Native Engine**: Built-in portable ADB integration allowing zero-configuration connection to physical Android devices or emulators (LDPlayer, BlueStacks, Nox, MEmu, Android Studio). Dispatches `am start -a android.intent.action.VIEW -d "<url>"` directly to `com.devlooper.flezen`, grabs framebuffer screenshots, and sends back key events.
  3. **Local Screenshot Batch OCR Mode**: For processing existing captured screenshots offline.
- **OCR Engine with OpenCV Preprocessing**:
  - Uses bundled portable **Tesseract 5.4.0** with English trained data (no system installation or administrative privileges required).
  - Multi-pass image variants: Cubic scaling (2.5x), CLAHE contrast enhancement, Otsu binarization, inverted thresholding, and adaptive Gaussian binarization.
  - Multi-PSM execution (PSM 6, 7, 11, 3) with character whitelist.
  - Pattern matching with configurable regex (`[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}`).
  - Preserves leading zeros, normalizes lowercase characters, and calculates average OCR confidence.
- **Crash-Resilient SQLite Persistence**:
  - Automatically commits results immediately after every link.
  - Sessions can be paused, resumed, or restored after accidental app shutdown.
- **Multi-Tab Excel Reporting**:
  - Styled with OpenPyXL using executive navy headers, alternating row striping, and color-coded status badges.
  - Generates 5 dedicated sheets: `All Results`, `Successful`, `Failed`, `Needs Review`, and `Duplicate Codes`.

---

## 2. Flezen Platform Investigation & Findings

During Stage 2 engineering investigation of `flezen.com/s/...` URLs:
1. **Desktop Web Behavior**:
   - The Flezen website is an ad-supported mobile gateway. Navigating to `https://flezen.com/s/<share_id>` serves an app download / redirect landing page:
     ```html
     <div id="video-open-app-area" onclick="openInApp();">
     <p class="text-xs text-gray-700">Flezen is a mobile app. To open this file, install Flezen on your Android or iOS device.</p>
     ```
   - Direct viewing of the file on desktop web is gated. The REST endpoint `/api/s/<id>` returns `{"error": "Valid API key required"}`.
2. **Android App Execution**:
   - When a Flezen link is opened on Android, it triggers the Android Intent:
     ```
     intent://flezen.com/s/<id>#Intent;scheme=flezen;package=com.devlooper.flezen;end
     ```
   - The Flezen Android app (`com.devlooper.flezen`) renders the actual image file containing the 12-character alphanumeric code.
3. **Application Solution**:
   - Flezen Bulk Code Extractor provides **both** Playwright browser automation (for web links, authenticated web sessions, or standard web image hosting) and **Android ADB Automation** (for automated device execution with `com.devlooper.flezen`), as well as **Local Image Batch Mode**.

---

## 3. Project Directory Structure

```
FlezenCodeExtractor/
├── app/
│   ├── __init__.py
│   ├── config.py              # Application settings, paths, theme tokens
│   ├── database.py            # SQLite database manager & session tracking
│   ├── importer.py            # PDF, CSV, Excel, TXT parser & deduplicator
│   ├── ocr_engine.py          # Tesseract OCR & OpenCV multi-pass preprocessing
│   ├── browser_engine.py      # Playwright Chromium browser automation
│   ├── adb_engine.py          # Android ADB automation (am start, screencap, keyevent)
│   ├── worker.py              # Multi-threaded background execution coordinator
│   ├── exporter.py            # OpenPyXL multi-sheet Excel generator
│   └── ui/
│       ├── __init__.py
│       ├── theme.py           # Linear dark theme colors & fonts
│       ├── components.py      # Metric stat cards & ETA progress bar
│       ├── table_view.py      # Searchable, filterable results table with context menu
│       ├── inspector.py       # Screenshot preview pane & manual code editor
│       ├── preview_dialog.py  # Link import confirmation modal
│       ├── settings_dialog.py # Configuration dialog for OCR and engine options
│       └── main_window.py     # Main desktop window layout & controllers
├── database/                  # SQLite storage: flezen_extractor.db
├── screenshots/               # Captured screenshots (0001.png, 0002.png, ...)
├── failed/                    # Error captures
├── exports/                   # Output Excel workbooks
├── logs/                      # Application execution logs
├── platform-tools/            # Bundled portable Android ADB binaries
├── tesseract-portable/        # Bundled portable Tesseract OCR 5.4.0 + tessdata
├── tests/                     # Automated end-to-end test suite
├── main.py                    # Application launcher
├── requirements.txt           # Python package requirements
├── setup.bat                  # 1-click installer and launcher
├── run.bat                    # Quick launcher
└── build_exe.bat              # Standalone Windows executable packager
```

---

## 4. Setup & Installation

### Quick Start (Windows)
1. Double-click `setup.bat`. This automatically:
   - Installs all Python dependencies from `requirements.txt`.
   - Downloads Playwright Chromium binaries.
   - Launches the **Flezen Bulk Code Extractor** desktop interface.
2. For subsequent launches, simply run `run.bat` or `python main.py`.

### Manual Installation
```powershell
cd "e:\flezen work\FlezenCodeExtractor"
pip install -r requirements.txt
python -m playwright install chromium
python main.py
```

*Note: Tesseract OCR (v5.4.0) and Android ADB are pre-bundled in `tesseract-portable/` and `platform-tools/`. You do NOT need to install Tesseract or ADB globally.*

---

## 5. User Operation Guide

### Step 1: Import Document
- Click **"📁 Import Links"** in the top toolbar.
- Select `PWN_Studio_Hiring_Test_Links_Part_1.pdf` (or any CSV, Excel, or TXT file).
- The **Import Preview** dialog will display:
  - Total Raw URLs found (1,000)
  - Total Unique URLs (1,000)
  - Duplicate URLs excluded (0)
  - Scrollable preview of serial numbers and links.
- Click **"✓ Confirm & Load"**.

### Step 2: Configure Engine & Settings
- Click **"⚙ Settings"** in the header.
- Select your desired automation mode:
  - **Browser Mode**: Uses Playwright Chromium.
  - **ADB Mode**: Connects to Android device or emulator. Click **🔄** to auto-detect devices.
  - **Local Folder Mode**: Runs OCR on an existing folder of screenshots.
- Adjust batch size (default: 5) and rendering delay (default: 3.5 - 4.0 seconds).
- Configure OCR code regex pattern (default: `[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}`) and confidence threshold (default: 75%).
- Click **"✓ Save Configuration"**.

### Step 3: Run Extraction
- Click **"▶ Start Processing"**.
- The metrics cards and progress bar will update continuously:
  - Current processed count and percentage.
  - Dynamic ETA countdown.
  - Success, Needs Review, Failed, and Duplicate counts.
- You can **Pause** (⏸), **Resume** (▶), or **Stop** (⏹) at any time without data loss.

### Step 4: Review & Edit Codes
- Click any row in the table to display its screenshot in the right **Inspector Pane**.
- Click **"🔍 Open Full Image"** to view high-resolution image in Windows default viewer.
- If OCR was uncertain, edit the code directly in the input box and click **"✓ Save & Verify"**.
- Click **"⚡ Re-run OCR"** to re-analyze the image with alternative image filters.

### Step 5: Export to Excel
- Click **"📊 Export to Excel"**.
- Choose your destination folder.
- A styled `.xlsx` workbook will be created containing separate sheets:
  1. `All Results`
  2. `Successful`
  3. `Failed`
  4. `Needs Review`
  5. `Duplicate Codes`

---

## 6. Automated Testing & Verification

Run the test suite to verify all backend modules:
```powershell
python tests/test_system_e2e.py
```
Outputs:
- ✓ Importer verified: 1,000/1,000 unique links preserved in sequential order.
- ✓ SQLite persistence verified with multi-session tracking.
- ✓ Tesseract OCR verified with leading zero preservation and confidence scoring.
- ✓ Multi-tab Excel export verified.

