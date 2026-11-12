import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from typing import Callable, Optional

from app.importer import ImportResult
from app.ui.theme import COLORS, FONTS, apply_treeview_theme

class ImportPreviewDialog(ctk.CTkToplevel):
    """Modal dialog displaying file import statistics and preview before session creation."""

    def __init__(self, master, import_result: ImportResult, on_confirm: Callable[[], None]):
        super().__init__(master)
        self.import_result = import_result
        self.on_confirm = on_confirm

        self.title("Import Links Preview")
        self.geometry("720x540")
        self.minsize(640, 480)
        self.configure(fg_color=COLORS["bg_root"])
        self.transient(master)
        self.grab_set()

        self._build_header()
        self._build_stats_cards()
        self._build_preview_table()
        self._build_actions()

    def _build_header(self):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(20, 10))

        title = ctk.CTkLabel(
            head,
            text="Document Links Verified",
            font=FONTS["title_md"],
            text_color=COLORS["text_white"]
        )
        title.pack(anchor="w")

        filename = Path_short = self.import_result.file_path.split("\\")[-1]
        subtitle = ctk.CTkLabel(
            head,
            text=f"Source: {filename} ({self.import_result.file_type})",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"]
        )
        subtitle.pack(anchor="w")

    def _build_stats_cards(self):
        stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20, pady=8)

        cards = [
            ("Total Found", str(self.import_result.total_raw_found), COLORS["primary"]),
            ("Unique Links", str(self.import_result.total_unique), COLORS["success"]),
            ("Duplicates Excluded", str(len(self.import_result.duplicates)), COLORS["duplicate"]),
        ]

        for idx, (title, val, color) in enumerate(cards):
            card = ctk.CTkFrame(stats_frame, fg_color=COLORS["bg_card"], corner_radius=8,
                                border_width=1, border_color=COLORS["border"])
            card.pack(side="left", fill="both", expand=True, padx=(0 if idx == 0 else 8, 0))

            lbl_t = ctk.CTkLabel(card, text=title, font=FONTS["caption"], text_color=COLORS["text_secondary"])
            lbl_t.pack(anchor="w", padx=12, pady=(10, 2))

            lbl_v = ctk.CTkLabel(card, text=val, font=FONTS["title_md"], text_color=color)
            lbl_v.pack(anchor="w", padx=12, pady=(0, 10))

    def _build_preview_table(self):
        preview_container = tk.Frame(self, bg=COLORS["bg_card"])
        preview_container.pack(fill="both", expand=True, padx=20, pady=10)

        style = ttk.Style()
        apply_treeview_theme(style)

        self.tree = ttk.Treeview(
            preview_container,
            columns=("serial", "url"),
            show="headings",
            style="Dark.Treeview"
        )
        self.tree.heading("serial", text="Serial #", anchor="center")
        self.tree.heading("url", text="Flezen URL Target", anchor="w")

        self.tree.column("serial", width=90, anchor="center")
        self.tree.column("url", width=550, anchor="w")

        scroll = ttk.Scrollbar(preview_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Insert first 100 links for preview
        for serial, url in self.import_result.links[:100]:
            self.tree.insert("", "end", values=(f"#{serial:04d}", url))

    def _build_actions(self):
        act_frame = ctk.CTkFrame(self, fg_color="transparent")
        act_frame.pack(fill="x", padx=20, pady=(10, 20))

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

        btn_confirm = ctk.CTkButton(
            act_frame,
            text=f"✓ Confirm & Load {self.import_result.total_unique} Links",
            font=FONTS["body_bold"],
            fg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color=COLORS["text_white"],
            height=34,
            command=self._on_click_confirm
        )
        btn_confirm.pack(side="right")

    def _on_click_confirm(self):
        self.destroy()
        if self.on_confirm:
            self.on_confirm()

