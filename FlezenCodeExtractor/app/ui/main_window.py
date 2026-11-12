import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import customtkinter as ctk
from tkinter import filedialog, messagebox

from app.config import (
    SCREENSHOTS_DIR,
    EXPORTS_DIR,
    DEFAULT_CODE_PATTERN,
    DEFAULT_BATCH_SIZE,
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_RENDER_WAIT_SEC,
    DEFAULT_ADB_WAIT_SEC,
)
from app.ui.theme import COLORS, FONTS
from app.ui.components import StatCard, ProgressBarWithETA
from app.ui.table_view import ResultsTableView
from app.ui.inspector import LinkInspectorPane
from app.ui.preview_dialog import ImportPreviewDialog
from app.ui.settings_dialog import SettingsDialog
from app.database import DatabaseManager
from app.importer import LinkImporter, ImportResult
from app.ocr_engine import OCREngine
from app.worker import ExtractionWorker
from app.exporter import ExcelExporter

class MainWindow(ctk.CTk):
    """Main Desktop Window for Flezen Bulk Code Extractor."""

    def __init__(self):
        super().__init__()

        # Window Setup
        self.title("Flezen Bulk Code Extractor")
        self.geometry("1400x880")
        self.minsize(1100, 720)
        self.configure(fg_color=COLORS["bg_root"])

        # Core Engines & State
        self.db = DatabaseManager()
        self.active_session_id: Optional[int] = None
        self.active_session_name: str = "No Active Session"
        self.ocr_engine = OCREngine()
        self.worker: Optional[ExtractionWorker] = None

        self.settings: Dict[str, Any] = {
            "mode": "browser",
            "browser_headless": True,
            "batch_size": DEFAULT_BATCH_SIZE,
            "render_wait_sec": DEFAULT_RENDER_WAIT_SEC,
            "adb_device": "auto",
            "code_pattern": DEFAULT_CODE_PATTERN,
            "confidence_threshold": DEFAULT_CONFIDENCE_THRESHOLD
        }

        # Build UI
        self._build_header()
        self._build_metrics_row()
        self._build_progress_bar()
        self._build_toolbar()
        self._build_center_area()
        self._build_log_console()

        # Load existing session if present
        self._restore_latest_session()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_sidebar"], height=60, corner_radius=0,
                              border_width=0)
        header.pack(fill="x")

        # Brand / Title
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=20, pady=12)

        icon_label = ctk.CTkLabel(
            brand_frame,
            text="⚡",
            font=("Segoe UI", 16),
            text_color=COLORS["accent_cyan"]
        )
        icon_label.pack(side="left", padx=(0, 8))

        title_label = ctk.CTkLabel(
            brand_frame,
            text="FLEZEN",
            font=("Segoe UI", 14, "bold"),
            text_color=COLORS["text_white"]
        )
        title_label.pack(side="left")

        subtitle = ctk.CTkLabel(
            brand_frame,
            text="BULK CODE EXTRACTOR",
            font=("Segoe UI", 12),
            text_color=COLORS["primary"]
        )
        subtitle.pack(side="left", padx=(6, 0))

        # Center Session info
        self.lbl_session = ctk.CTkLabel(
            header,
            text=self.active_session_name,
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"]
        )
        self.lbl_session.pack(side="left", padx=30)

        # Right Actions
        right_frame = ctk.CTkFrame(header, fg_color="transparent")
        right_frame.pack(side="right", padx=20)

        # Mode Badge
        self.lbl_mode_pill = ctk.CTkLabel(
            right_frame,
            text="MODE: BROWSER",
            font=FONTS["caption"],
            fg_color=COLORS["primary_subtle"],
            text_color=COLORS["text_white"],
            corner_radius=12,
            padx=12,
            pady=3
        )
        self.lbl_mode_pill.pack(side="left", padx=10)

        btn_settings = ctk.CTkButton(
            right_frame,
            text="⚙ Settings",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card"],
            hover_color=COLORS["bg_card_alt"],
            text_color=COLORS["text_primary"],
            width=90,
            height=30,
            command=self._open_settings_dialog
        )
        btn_settings.pack(side="left")

    def _build_metrics_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(16, 10))

        self.card_total = StatCard(row, title="Total Imported", initial_value="0",
                                   accent_color=COLORS["info"], icon="📋")
        self.card_total.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_processed = StatCard(row, title="Processed", initial_value="0",
                                       accent_color=COLORS["primary"], icon="⚙")
        self.card_processed.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_success = StatCard(row, title="Successful Codes", initial_value="0",
                                     accent_color=COLORS["success"], icon="✓")
        self.card_success.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_review = StatCard(row, title="Needs Review", initial_value="0",
                                    accent_color=COLORS["warning"], icon="⚠")
        self.card_review.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_failed = StatCard(row, title="Failed Links", initial_value="0",
                                    accent_color=COLORS["danger"], icon="✗")
        self.card_failed.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.card_duplicates = StatCard(row, title="Duplicate Codes", initial_value="0",
                                        accent_color=COLORS["duplicate"], icon="⚏")
        self.card_duplicates.pack(side="left", fill="both", expand=True)

    def _build_progress_bar(self):
        self.progress_widget = ProgressBarWithETA(self)
        self.progress_widget.pack(fill="x", padx=20, pady=(0, 10))

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=46, corner_radius=8,
                           border_width=1, border_color=COLORS["border"])
        bar.pack(fill="x", padx=20, pady=(0, 12))

        # Import File
        self.btn_import = ctk.CTkButton(
            bar,
            text="📁 Import Links",
            font=FONTS["body_bold"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_white"],
            height=32,
            command=self._on_click_import
        )
        self.btn_import.pack(side="left", padx=(10, 6), pady=6)

        # Start Processing
        self.btn_start = ctk.CTkButton(
            bar,
            text="▶ Start Processing",
            font=FONTS["body_bold"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_white"],
            height=32,
            command=self._start_processing
        )
        self.btn_start.pack(side="left", padx=6, pady=6)

        # Pause / Resume
        self.btn_pause = ctk.CTkButton(
            bar,
            text="⏸ Pause",
            font=FONTS["body"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["warning"],
            text_color=COLORS["text_secondary"],
            height=32,
            state="disabled",
            command=self._toggle_pause
        )
        self.btn_pause.pack(side="left", padx=6, pady=6)

        # Stop
        self.btn_stop = ctk.CTkButton(
            bar,
            text="⏹ Stop",
            font=FONTS["body"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["danger"],
            text_color=COLORS["text_secondary"],
            height=32,
            state="disabled",
            command=self._stop_processing
        )
        self.btn_stop.pack(side="left", padx=6, pady=6)

        # Retry Failed
        self.btn_retry = ctk.CTkButton(
            bar,
            text="🔄 Retry Failed",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["warning"],
            text_color=COLORS["text_primary"],
            height=32,
            command=self._retry_failed
        )
        self.btn_retry.pack(side="left", padx=6, pady=6)

        # Process Selected
        self.btn_selected = ctk.CTkButton(
            bar,
            text="🎯 Process Selected",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_primary"],
            height=32,
            command=self._process_selected
        )
        self.btn_selected.pack(side="left", padx=6, pady=6)

        # Right side: Export & Folder
        self.btn_folder = ctk.CTkButton(
            bar,
            text="📂 Screenshots",
            font=FONTS["caption"],
            fg_color=COLORS["bg_card_alt"],
            hover_color=COLORS["border_light"],
            text_color=COLORS["text_secondary"],
            height=32,
            command=lambda: os.startfile(str(SCREENSHOTS_DIR))
        )
        self.btn_folder.pack(side="right", padx=(6, 10), pady=6)

        self.btn_export = ctk.CTkButton(
            bar,
            text="📊 Export to Excel",
            font=FONTS["body_bold"],
            fg_color=COLORS["success"],
            hover_color="#059669",
            text_color=COLORS["text_white"],
            height=32,
            command=self._export_to_excel
        )
        self.btn_export.pack(side="right", padx=6, pady=6)

    def _build_center_area(self):
        center = ctk.CTkFrame(self, fg_color="transparent")
        center.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # Left / Center: Results Table
        self.table_view = ResultsTableView(
            center,
            on_select_row=self._on_table_row_selected,
            on_manual_edit=self._on_manual_code_saved
        )
        self.table_view.filter_callback = self._on_filter_and_search
        self.table_view.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Right: Inspector Pane
        self.inspector = LinkInspectorPane(
            center,
            on_save_edit=self._on_manual_code_saved,
            ocr_engine=self.ocr_engine,
            width=340
        )
        self.inspector.pack(side="right", fill="both")

    def _build_log_console(self):
        log_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=120, corner_radius=8,
                                 border_width=1, border_color=COLORS["border"])
        log_frame.pack(fill="x", padx=20, pady=(0, 14))

        head = ctk.CTkFrame(log_frame, fg_color="transparent")
        head.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkLabel(head, text="Live Activity Log", font=FONTS["caption"],
                     text_color=COLORS["text_secondary"]).pack(side="left")

        btn_clear = ctk.CTkButton(head, text="Clear", font=("Segoe UI", 8), width=45, height=20,
                                  fg_color="transparent", text_color=COLORS["text_muted"],
                                  command=self._clear_logs)
        btn_clear.pack(side="right")

        self.log_text = ctk.CTkTextbox(
            log_frame,
            fg_color=COLORS["bg_root"],
            text_color=COLORS["text_secondary"],
            font=("Consolas", 9),
            corner_radius=4,
            height=75
        )
        self.log_text.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        self.log_text.configure(state="disabled")

    # --- SESSION MANAGEMENT & LOGIC ---

    def _restore_latest_session(self):
        latest = self.db.get_latest_session()
        if latest:
            self.active_session_id = latest["id"]
            self.active_session_name = f"Session #{latest['id']}: {latest['session_name']}"
            self.lbl_session.configure(text=self.active_session_name)
            self._refresh_table()
            self._update_metrics()
            self._append_log(f"Restored previous session: {self.active_session_name}", "INFO")

    def _on_click_import(self):
        file_path = filedialog.askopenfilename(
            title="Select Links File",
            filetypes=[
                ("All Supported Files", "*.pdf;*.csv;*.xlsx;*.txt"),
                ("PDF Documents", "*.pdf"),
                ("CSV Files", "*.csv"),
                ("Excel Workbooks", "*.xlsx"),
                ("Text Files", "*.txt")
            ]
        )
        if not file_path:
            return

        self._append_log(f"Importing links from: {file_path}...", "INFO")
        result = LinkImporter.import_file(file_path)

        if result.error:
            messagebox.showerror("Import Error", result.error)
            self._append_log(f"Import failed: {result.error}", "DANGER")
            return

        if not result.links:
            messagebox.showwarning("No Links Found", "No valid URLs were found in the selected file.")
            return

        # Show preview dialog
        ImportPreviewDialog(self, result, on_confirm=lambda: self._create_new_session(result))

    def _create_new_session(self, result: ImportResult):
        file_name = Path(result.file_path).name
        sess_id = self.db.create_session(
            source_file=file_name,
            total_links=result.total_unique,
            session_name=f"{file_name} ({result.total_unique} links)"
        )
        self.db.insert_links(sess_id, result.links)
        self.active_session_id = sess_id
        self.active_session_name = f"Session #{sess_id}: {file_name}"
        self.lbl_session.configure(text=self.active_session_name)

        self._refresh_table()
        self._update_metrics()
        self._append_log(f"Loaded session with {result.total_unique} links ({len(result.duplicates)} duplicates skipped).", "SUCCESS")

    def _refresh_table(self):
        if not self.active_session_id:
            return
        rows = self.db.get_session_links(
            self.active_session_id,
            status_filter=self.table_view.current_filter,
            search_query=self.table_view.search_entry.get().strip()
        )
        self.table_view.set_rows(rows)

    def _update_metrics(self, eta_seconds: Optional[float] = None):
        if not self.active_session_id:
            return
        m = self.db.get_session_metrics(self.active_session_id)
        self.card_total.update_value(m["total"])
        self.card_processed.update_value(m["processed"])
        self.card_success.update_value(m["successful"])
        self.card_review.update_value(m["needs_review"])
        self.card_failed.update_value(m["failed"])
        self.card_duplicates.update_value(m["duplicates"])

        self.progress_widget.set_progress(m["processed"], m["total"], eta_seconds)

    def _on_filter_and_search(self, status_filter: str, search_query: str):
        if not self.active_session_id:
            return
        rows = self.db.get_session_links(self.active_session_id, status_filter, search_query)
        self.table_view.set_rows(rows)

    def _on_table_row_selected(self, row: Dict[str, Any]):
        self.inspector.load_link(row)

    def _on_manual_code_saved(self, link_id: int, new_code: str, verification_status: str = "VERIFIED"):
        self.db.manual_update_code(link_id, new_code, verification_status)
        self._refresh_table()
        self._update_metrics()
        self._append_log(f"Updated Link #{link_id} code to: {new_code} ({verification_status})", "SUCCESS")

    # --- WORKER CONTROLS ---

    def _start_processing(self, specific_ids: Optional[List[int]] = None):
        if not self.active_session_id:
            messagebox.showwarning("No Active Session", "Please import a links document first.")
            return

        if self.worker and self.worker.is_running:
            return

        self.btn_start.configure(state="disabled")
        self.btn_pause.configure(state="normal", text="⏸ Pause")
        self.btn_stop.configure(state="normal")
        self.btn_import.configure(state="disabled")

        self.worker = ExtractionWorker(
            db=self.db,
            session_id=self.active_session_id,
            mode=self.settings["mode"],
            batch_size=self.settings["batch_size"],
            ocr_engine=self.ocr_engine,
            browser_headless=self.settings["browser_headless"],
            browser_mobile=False,
            adb_device=self.settings["adb_device"],
            adb_wait=self.settings.get("render_wait_sec", 4.0),
            on_link_complete=self._on_worker_link_complete,
            on_metrics_update=self._on_worker_metrics_update,
            on_log=self._append_log,
            on_finished=self._on_worker_finished
        )
        self.worker.start(specific_ids)

    def _toggle_pause(self):
        if not self.worker or not self.worker.is_running:
            return
        if self.worker.is_paused:
            self.worker.resume()
            self.btn_pause.configure(text="⏸ Pause", fg_color=COLORS["bg_card_alt"])
        else:
            self.worker.pause()
            self.btn_pause.configure(text="▶ Resume", fg_color=COLORS["warning"])

    def _stop_processing(self):
        if self.worker and self.worker.is_running:
            self.worker.stop()
            self.btn_pause.configure(state="disabled")
            self.btn_stop.configure(state="disabled")

    def _retry_failed(self):
        if not self.active_session_id:
            return
        self.db.reset_failed_links(self.active_session_id)
        self._refresh_table()
        self._update_metrics()
        self._start_processing()

    def _process_selected(self):
        selected_ids = self.table_view.get_selected_ids()
        if not selected_ids:
            messagebox.showinfo("Select Links", "Please click one or more links in the table first.")
            return
        self._start_processing(specific_ids=selected_ids)

    def _on_worker_link_complete(self, row: Dict[str, Any]):
        # Schedule GUI table update on main thread
        self.after(0, lambda: self.table_view.update_single_row(row))

    def _on_worker_metrics_update(self, metrics: Dict[str, Any], eta_seconds: Optional[float]):
        self.after(0, lambda: self._update_metrics(eta_seconds))

    def _on_worker_finished(self):
        def _finish_ui():
            self.btn_start.configure(state="normal")
            self.btn_pause.configure(state="disabled", text="⏸ Pause")
            self.btn_stop.configure(state="disabled")
            self.btn_import.configure(state="normal")
            self._update_metrics(None)
            self._refresh_table()
        self.after(0, _finish_ui)

    def _export_to_excel(self):
        if not self.active_session_id:
            messagebox.showwarning("No Data", "No active session to export.")
            return

        rows = self.db.get_session_links(self.active_session_id)
        if not rows:
            messagebox.showwarning("No Data", "No links found in active session.")
            return

        default_dest = str(EXPORTS_DIR / f"Flezen_Extracted_Codes_{self.active_session_id}.xlsx")
        dest = filedialog.asksaveasfilename(
            title="Save Results Excel File",
            initialfile=Path(default_dest).name,
            defaultextension=".xlsx",
            filetypes=[("Excel Workbook", "*.xlsx")]
        )
        if not dest:
            return

        try:
            saved_path = ExcelExporter.export(rows, self.active_session_name, dest)
            self._append_log(f"Exported Excel report to: {saved_path}", "SUCCESS")
            open_prompt = messagebox.askyesno("Export Complete", f"Successfully exported {len(rows)} records!\n\nOpen file now?")
            if open_prompt:
                os.startfile(saved_path)
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export Excel: {e}")
            self._append_log(f"Excel export failed: {e}", "DANGER")

    def _open_settings_dialog(self):
        def _save_callback(new_settings):
            self.settings.update(new_settings)
            self.ocr_engine.set_pattern(new_settings["code_pattern"])
            self.ocr_engine.confidence_threshold = new_settings["confidence_threshold"]
            self.lbl_mode_pill.configure(text=f"MODE: {new_settings['mode'].upper()}")
            self._append_log(f"Settings updated: Mode={new_settings['mode'].upper()}, Pattern={new_settings['code_pattern']}", "INFO")

        SettingsDialog(self, self.settings, on_save=_save_callback)

    def _append_log(self, message: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        prefix = f"[{timestamp}] "
        full_msg = f"{prefix}{message}\n"

        def _do_append():
            self.log_text.configure(state="normal")
            self.log_text.insert("end", full_msg)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.after(0, _do_append)

    def _clear_logs(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

