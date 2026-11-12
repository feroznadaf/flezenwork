import os
import customtkinter as ctk
from PIL import Image
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from app.ui.theme import COLORS, FONTS
from app.config import SCREENSHOTS_DIR, FAILED_DIR
from app.ocr_engine import OCREngine

class LinkInspectorPane(ctk.CTkFrame):
    """Side panel for reviewing screenshots, editing OCR results, and verifying codes."""

    def __init__(self, master, on_save_edit: Optional[Callable[[int, str, str], None]] = None,
                 ocr_engine: Optional[OCREngine] = None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=10,
                         border_width=1, border_color=COLORS["border"], **kwargs)

        self.on_save_edit = on_save_edit
        self.ocr_engine = ocr_engine or OCREngine()
        self.current_row: Optional[Dict[str, Any]] = None

        self._build_header()
        self._build_image_preview()
        self._build_editor()

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=16, pady=(14, 8))

        self.title_label = ctk.CTkLabel(
            header_frame,
            text="Inspector — Select a Link",
            font=FONTS["title_sm"],
            text_color=COLORS["text_white"]
        )
        self.title_label.pack(side="left")

        self.status_badge = ctk.CTkLabel(
            header_frame,
            text="—",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"],
            fg_color=COLORS["bg_card_alt"],
            corner_radius=4,
            padx=8,
            pady=2
        )
        self.status_badge.pack(side="right")

    def _build_image_preview(self):
        preview_container = ctk.CTkFrame(self, fg_color=COLORS["bg_root"], corner_radius=8,
                                         border_width=1, border_color=COLORS["border"])
        preview_container.pack(fill="both", expand=True, padx=16, pady=4)

        self.image_label = ctk.CTkLabel(
            preview_container,
            text="No Screenshot Available",
            font=FONTS["caption"],
            text_color=COLORS["text_muted"]
        )
        self.image_label.pack(fill="both", expand=True, padx=8, pady=8)

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 8))

        self.btn_open_ext = ctk.CTkButton(
            btn_row,
            text="🔍 Open Full Image",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_secondary"],
            height=26,
            command=self._open_external_image
        )
        self.btn_open_ext.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_rerun_ocr = ctk.CTkButton(
            btn_row,
            text="⚡ Re-run OCR",
            font=FONTS["caption"],
            fg_color=COLORS["primary_subtle"],
            hover_color=COLORS["primary"],
            text_color=COLORS["text_white"],
            height=26,
            command=self._rerun_ocr
        )
        self.btn_rerun_ocr.pack(side="right", fill="x", expand=True, padx=(4, 0))

    def _build_editor(self):
        editor_frame = ctk.CTkFrame(self, fg_color="transparent")
        editor_frame.pack(fill="x", padx=16, pady=(0, 14))

        # URL
        url_label = ctk.CTkLabel(editor_frame, text="Flezen URL:", font=FONTS["caption"],
                                 text_color=COLORS["text_secondary"])
        url_label.pack(anchor="w", pady=(4, 2))

        self.url_display = ctk.CTkLabel(
            editor_frame,
            text="—",
            font=("Segoe UI", 9),
            text_color=COLORS["info_text"],
            wraplength=280,
            justify="left"
        )
        self.url_display.pack(anchor="w", pady=(0, 8))

        # Extracted Code
        code_label = ctk.CTkLabel(editor_frame, text="Extracted Code (XXXX-XXXX-XXXX):",
                                  font=FONTS["body_bold"], text_color=COLORS["text_primary"])
        code_label.pack(anchor="w", pady=(4, 2))

        self.code_entry = ctk.CTkEntry(
            editor_frame,
            placeholder_text="e.g. A1B2-C3D4-E5F6",
            font=FONTS["code"],
            height=34,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_white"]
        )
        self.code_entry.pack(fill="x", pady=(0, 10))

        # Action Buttons
        act_row = ctk.CTkFrame(editor_frame, fg_color="transparent")
        act_row.pack(fill="x")

        self.btn_save = ctk.CTkButton(
            act_row,
            text="✓ Save & Verify",
            font=FONTS["body_bold"],
            fg_color=COLORS["success"],
            hover_color="#059669",
            text_color=COLORS["text_white"],
            height=32,
            command=self._save_and_verify
        )
        self.btn_save.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_copy = ctk.CTkButton(
            act_row,
            text="📋 Copy Code",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_primary"],
            height=32,
            command=self._copy_code
        )
        self.btn_copy.pack(side="right", padx=(4, 0))

    def load_link(self, row: Dict[str, Any]):
        self.current_row = row
        serial = row.get("serial_no", 0)
        self.title_label.configure(text=f"Link #{serial:04d}")

        status = row.get("processing_status", "PENDING")
        self.status_badge.configure(
            text=status,
            text_color=COLORS.get(f"{status.lower()}_text", COLORS["text_secondary"])
        )

        self.url_display.configure(text=row.get("url", "—"))
        
        current_code = row.get("code") or ""
        self.code_entry.delete(0, "end")
        self.code_entry.insert(0, current_code)

        # Load screenshot preview
        shot_name = row.get("screenshot_filename")
        self._load_screenshot_preview(shot_name)

    def _load_screenshot_preview(self, shot_filename: Optional[str]):
        if not shot_filename:
            self.image_label.configure(text="No Screenshot Captured", image=None)
            return

        shot_path = SCREENSHOTS_DIR / shot_filename
        if not shot_path.exists():
            shot_path = FAILED_DIR / shot_filename

        if not shot_path.exists():
            self.image_label.configure(text=f"Image {shot_filename} not found", image=None)
            return

        try:
            pil_img = Image.open(shot_path)
            # Resize keeping aspect ratio to fit inside inspector pane (~280x220)
            max_w, max_h = 280, 220
            w, h = pil_img.size
            ratio = min(max_w / w, max_h / h)
            new_size = (int(w * ratio), int(h * ratio))
            resized = pil_img.resize(new_size, Image.Resampling.LANCZOS)

            ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=new_size)
            self.image_label.configure(image=ctk_img, text="")
            self.image_label._image = ctk_img  # prevent garbage collection
        except Exception as e:
            self.image_label.configure(text=f"Error loading image: {e}", image=None)

    def _open_external_image(self):
        if not self.current_row:
            return
        shot_name = self.current_row.get("screenshot_filename")
        if shot_name:
            shot_path = SCREENSHOTS_DIR / shot_name
            if not shot_path.exists():
                shot_path = FAILED_DIR / shot_name
            if shot_path.exists():
                os.startfile(str(shot_path))

    def _rerun_ocr(self):
        if not self.current_row:
            return
        shot_name = self.current_row.get("screenshot_filename")
        if not shot_name:
            return

        shot_path = SCREENSHOTS_DIR / shot_name
        if not shot_path.exists():
            shot_path = FAILED_DIR / shot_name
        if not shot_path.exists():
            return

        code, conf, status, details = self.ocr_engine.extract_code(shot_path)
        if code:
            self.code_entry.delete(0, "end")
            self.code_entry.insert(0, code)
            self.status_badge.configure(text=f"{status} ({conf:.1f}%)")
        else:
            self.status_badge.configure(text=f"NO CODE ({details})")

    def _save_and_verify(self):
        if not self.current_row:
            return
        link_id = self.current_row["id"]
        edited_code = self.code_entry.get().strip().upper()
        if self.on_save_edit:
            self.on_save_edit(link_id, edited_code, "VERIFIED")
        self.status_badge.configure(text="VERIFIED", text_color=COLORS["success"])

    def _copy_code(self):
        code = self.code_entry.get().strip()
        if code:
            self.clipboard_clear()
            self.clipboard_append(code)

