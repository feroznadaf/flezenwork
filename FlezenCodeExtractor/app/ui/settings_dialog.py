import customtkinter as ctk
from typing import Dict, Any, Callable
from app.ui.theme import COLORS, FONTS
from app.config import (
    get_tesseract_path,
    get_adb_path,
    DEFAULT_CODE_PATTERN,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_RENDER_WAIT_SEC,
    DEFAULT_ADB_WAIT_SEC,
)
from app.adb_engine import ADBAutomationEngine

class SettingsDialog(ctk.CTkToplevel):
    """Configuration dialog for OCR parameters, engine modes, and batch settings."""

    def __init__(self, master, current_settings: Dict[str, Any], on_save: Callable[[Dict[str, Any]], None]):
        super().__init__(master)
        self.settings = current_settings.copy()
        self.on_save = on_save

        self.title("Settings & Engine Configuration")
        self.geometry("640x620")
        self.minsize(580, 540)
        self.configure(fg_color=COLORS["bg_root"])
        self.transient(master)
        self.grab_set()

        self._build_content()

    def _build_content(self):
        pad_x, pad_y = 24, 16

        # Scrollable container
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=pad_x, pady=pad_y)

        # Title
        lbl_head = ctk.CTkLabel(container, text="Configuration & Automation Settings",
                                font=FONTS["title_md"], text_color=COLORS["text_white"])
        lbl_head.pack(anchor="w", pady=(0, 16))

        # --- SECTION 1: EXECUTION ENGINE ---
        sec1 = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=8,
                            border_width=1, border_color=COLORS["border"])
        sec1.pack(fill="x", pady=8)

        lbl_sec1 = ctk.CTkLabel(sec1, text="1. Automation Mode", font=FONTS["body_bold"],
                                text_color=COLORS["text_primary"])
        lbl_sec1.pack(anchor="w", padx=16, pady=(12, 6))

        self.var_mode = ctk.StringVar(value=self.settings.get("mode", "browser"))
        
        mode_frame = ctk.CTkFrame(sec1, fg_color="transparent")
        mode_frame.pack(fill="x", padx=16, pady=(0, 12))

        rb1 = ctk.CTkRadioButton(mode_frame, text="Desktop Browser (Playwright Chromium)",
                                 variable=self.var_mode, value="browser", font=FONTS["body"],
                                 fg_color=COLORS["primary"])
        rb1.pack(anchor="w", pady=4)

        rb2 = ctk.CTkRadioButton(mode_frame, text="Android App via ADB (Physical Phone or Emulator)",
                                 variable=self.var_mode, value="adb", font=FONTS["body"],
                                 fg_color=COLORS["primary"])
        rb2.pack(anchor="w", pady=4)

        rb3 = ctk.CTkRadioButton(mode_frame, text="Local Screenshot Folder (Offline Batch OCR)",
                                 variable=self.var_mode, value="local", font=FONTS["body"],
                                 fg_color=COLORS["primary"])
        rb3.pack(anchor="w", pady=4)

        # --- SECTION 2: BROWSER & ADB PARAMETERS ---
        sec2 = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=8,
                            border_width=1, border_color=COLORS["border"])
        sec2.pack(fill="x", pady=8)

        lbl_sec2 = ctk.CTkLabel(sec2, text="2. Engine Options & Delays", font=FONTS["body_bold"],
                                text_color=COLORS["text_primary"])
        lbl_sec2.pack(anchor="w", padx=16, pady=(12, 6))

        opt_frame = ctk.CTkFrame(sec2, fg_color="transparent")
        opt_frame.pack(fill="x", padx=16, pady=(0, 12))

        # Browser Headless toggle
        self.var_headless = ctk.BooleanVar(value=self.settings.get("browser_headless", True))
        chk_headless = ctk.CTkCheckBox(opt_frame, text="Run Browser Headless (Background)",
                                      variable=self.var_headless, font=FONTS["body"],
                                      fg_color=COLORS["primary"])
        chk_headless.pack(anchor="w", pady=4)

        # Batch Size
        batch_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        batch_row.pack(fill="x", pady=6)

        ctk.CTkLabel(batch_row, text="Default Batch Size (Links per batch):",
                      font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(side="left")

        self.var_batch = ctk.IntVar(value=self.settings.get("batch_size", DEFAULT_BATCH_SIZE))
        self.spin_batch = ctk.CTkComboBox(batch_row, values=["1", "5", "10", "20", "50"],
                                          variable=ctk.StringVar(value=str(self.var_batch.get())),
                                          width=80, height=28, fg_color=COLORS["bg_input"])
        self.spin_batch.pack(side="right")

        # Page wait delay
        delay_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        delay_row.pack(fill="x", pady=6)

        ctk.CTkLabel(delay_row, text="Rendering / Loading Delay (Seconds):",
                      font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(side="left")

        self.var_delay = ctk.DoubleVar(value=self.settings.get("render_wait_sec", DEFAULT_RENDER_WAIT_SEC))
        self.entry_delay = ctk.CTkEntry(delay_row, width=80, height=28,
                                        textvariable=ctk.StringVar(value=str(self.var_delay.get())),
                                        fg_color=COLORS["bg_input"])
        self.entry_delay.pack(side="right")

        # ADB Device row
        adb_row = ctk.CTkFrame(opt_frame, fg_color="transparent")
        adb_row.pack(fill="x", pady=6)

        ctk.CTkLabel(adb_row, text="ADB Target Device / Emulator:",
                      font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(side="left")

        self.combo_adb = ctk.CTkComboBox(adb_row, values=["auto"], width=160, height=28,
                                         fg_color=COLORS["bg_input"])
        self.combo_adb.set(self.settings.get("adb_device", "auto"))
        self.combo_adb.pack(side="right", padx=(4, 0))

        btn_refresh_adb = ctk.CTkButton(adb_row, text="🔄", width=32, height=28,
                                        fg_color=COLORS["bg_card_alt"], hover_color=COLORS["primary_hover"],
                                        command=self._refresh_adb_devices)
        btn_refresh_adb.pack(side="right")

        # --- SECTION 3: OCR REGEX & ACCURACY ---
        sec3 = ctk.CTkFrame(container, fg_color=COLORS["bg_card"], corner_radius=8,
                            border_width=1, border_color=COLORS["border"])
        sec3.pack(fill="x", pady=8)

        lbl_sec3 = ctk.CTkLabel(sec3, text="3. OCR Code Validation Pattern", font=FONTS["body_bold"],
                                text_color=COLORS["text_primary"])
        lbl_sec3.pack(anchor="w", padx=16, pady=(12, 6))

        ocr_frame = ctk.CTkFrame(sec3, fg_color="transparent")
        ocr_frame.pack(fill="x", padx=16, pady=(0, 12))

        ctk.CTkLabel(ocr_frame, text="Code Regex Pattern (Default: XXXX-XXXX-XXXX):",
                      font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(anchor="w")

        self.entry_pattern = ctk.CTkEntry(
            ocr_frame,
            font=FONTS["code"],
            height=32,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_white"]
        )
        self.entry_pattern.pack(fill="x", pady=(4, 8))
        self.entry_pattern.insert(0, self.settings.get("code_pattern", DEFAULT_CODE_PATTERN))

        # Confidence Threshold Slider
        ctk.CTkLabel(ocr_frame, text="Confidence Acceptance Threshold (%):",
                      font=FONTS["caption"], text_color=COLORS["text_secondary"]).pack(anchor="w")

        conf_row = ctk.CTkFrame(ocr_frame, fg_color="transparent")
        conf_row.pack(fill="x", pady=4)

        self.slider_conf = ctk.CTkSlider(
            conf_row,
            from_=50.0,
            to=95.0,
            number_of_steps=45,
            progress_color=COLORS["primary"],
            command=self._on_slider_moved
        )
        self.slider_conf.set(self.settings.get("confidence_threshold", DEFAULT_CONFIDENCE_THRESHOLD))
        self.slider_conf.pack(side="left", fill="x", expand=True, padx=(0, 12))

        self.lbl_conf_val = ctk.CTkLabel(conf_row, text=f"{int(self.slider_conf.get())}%",
                                         font=FONTS["body_bold"], width=45)
        self.lbl_conf_val.pack(side="right")

        # Tesseract Status
        tess_path = get_tesseract_path()
        ctk.CTkLabel(ocr_frame, text=f"Active Tesseract: {tess_path}",
                      font=("Segoe UI", 8), text_color=COLORS["text_muted"]).pack(anchor="w", pady=(6, 0))

        # --- BOTTOM BUTTONS ---
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=pad_x, pady=(10, pad_y))

        btn_cancel = ctk.CTkButton(
            act_frame,
            text="Cancel",
            font=FONTS["body"],
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_alt"],
            text_color=COLORS["text_secondary"],
            width=100,
            height=34,
            command=self.destroy
        )
        btn_cancel.pack(side="left")

        btn_save = ctk.CTkButton(
            act_frame,
            text="✓ Save Configuration",
            font=FONTS["body_bold"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_white"],
            height=34,
            command=self._on_save
        )
        btn_save.pack(side="right")

    def _on_slider_moved(self, val):
        self.lbl_conf_val.configure(text=f"{int(val)}%")

    def _refresh_adb_devices(self):
        engine = ADBAutomationEngine()
        devs = engine.list_devices()
        options = ["auto"]
        for d in devs:
            options.append(d["id"])
        self.combo_adb.configure(values=options)
        if len(options) > 1:
            self.combo_adb.set(options[1])

    def _on_save(self):
        try:
            batch_val = int(self.spin_batch.get())
        except ValueError:
            batch_val = DEFAULT_BATCH_SIZE

        try:
            delay_val = float(self.entry_delay.get())
        except ValueError:
            delay_val = DEFAULT_RENDER_WAIT_SEC

        new_settings = {
            "mode": self.var_mode.get(),
            "browser_headless": self.var_headless.get(),
            "batch_size": batch_val,
            "render_wait_sec": delay_val,
            "adb_device": self.combo_adb.get(),
            "code_pattern": self.entry_pattern.get().strip() or DEFAULT_CODE_PATTERN,
            "confidence_threshold": float(self.slider_conf.get())
        }
        self.destroy()
        if self.on_save:
            self.on_save(new_settings)

