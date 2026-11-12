import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from app.ui.theme import COLORS, FONTS, apply_treeview_theme
from app.config import SCREENSHOTS_DIR

class ResultsTableView(ctk.CTkFrame):
    def __init__(self, master, on_select_row: Optional[Callable[[Dict[str, Any]], None]] = None,
                 on_manual_edit: Optional[Callable[[int, str], None]] = None, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=10,
                         border_width=1, border_color=COLORS["border"], **kwargs)

        self.on_select_row = on_select_row
        self.on_manual_edit = on_manual_edit
        self._row_data_map: Dict[str, Dict[str, Any]] = {}

        # Top Bar: Filter Tabs & Search Box
        self._build_filter_bar()

        # Treeview Table
        self._build_treeview()

        # Context Menu
        self._build_context_menu()

    def _build_filter_bar(self):
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=12, pady=(10, 8))

        # Filter Tabs Segmented Button
        self.current_filter = "ALL"
        self.filter_buttons = {}
        tab_names = [
            ("ALL", "All Links"),
            ("SUCCESS", "Successful"),
            ("NEEDS_REVIEW", "Needs Review"),
            ("FAILED", "Failed"),
            ("DUPLICATES", "Duplicates")
        ]
        
        tab_container = ctk.CTkFrame(filter_frame, fg_color=COLORS["bg_card_alt"], corner_radius=6)
        tab_container.pack(side="left")

        for key, label in tab_names:
            btn = ctk.CTkButton(
                tab_container,
                text=label,
                font=FONTS["caption"],
                width=80,
                height=26,
                corner_radius=5,
                fg_color=COLORS["primary"] if key == "ALL" else "transparent",
                text_color=COLORS["text_white"] if key == "ALL" else COLORS["text_secondary"],
                hover_color=COLORS["primary_hover"],
                command=lambda k=key: self._on_filter_changed(k)
            )
            btn.pack(side="left", padx=2, pady=2)
            self.filter_buttons[key] = btn

        # Search Bar
        self.search_entry = ctk.CTkEntry(
            filter_frame,
            placeholder_text="🔍 Search code, serial #, or URL...",
            font=FONTS["caption"],
            width=240,
            height=28,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", lambda e: self._on_search())

    def _build_treeview(self):
        tree_container = tk.Frame(self, bg=COLORS["bg_card"])
        tree_container.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        # Apply custom clam theme
        style = ttk.Style()
        apply_treeview_theme(style)

        columns = ("serial", "url", "code", "screenshot", "confidence", "status", "verification")
        self.tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="headings",
            style="Dark.Treeview",
            selectmode="browse"
        )

        # Headings & Column Widths
        col_defs = [
            ("serial", "No.", 60, "center"),
            ("url", "Flezen URL", 280, "w"),
            ("code", "Extracted Code", 160, "center"),
            ("screenshot", "Screenshot", 110, "center"),
            ("confidence", "Confidence", 95, "center"),
            ("status", "Status", 115, "center"),
            ("verification", "Verification", 115, "center"),
        ]

        for col_id, title, width, align in col_defs:
            self.tree.heading(col_id, text=title, anchor=align)
            self.tree.column(col_id, width=width, minwidth=50, anchor=align)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Color Tags
        self.tree.tag_configure("SUCCESS", foreground=COLORS["success"])
        self.tree.tag_configure("FAILED", foreground=COLORS["danger"])
        self.tree.tag_configure("NEEDS_REVIEW", foreground=COLORS["warning"])
        self.tree.tag_configure("DUPLICATE", foreground=COLORS["duplicate"])
        self.tree.tag_configure("VERIFIED", foreground=COLORS["info"])
        self.tree.tag_configure("PENDING", foreground=COLORS["text_muted"])

        # Bindings
        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _build_context_menu(self):
        self.menu = tk.Menu(self, tearoff=0, bg=COLORS["bg_card_alt"], fg=COLORS["text_white"],
                            activebackground=COLORS["primary"], activeforeground=COLORS["text_white"],
                            font=FONTS["caption"])
        self.menu.add_command(label="📋 Copy Extracted Code", command=self._copy_code)
        self.menu.add_command(label="🔗 Copy URL", command=self._copy_url)
        self.menu.add_separator()
        self.menu.add_command(label="🖼 Open Screenshot", command=self._open_screenshot)
        self.menu.add_command(label="✓ Mark as Verified", command=self._mark_verified)

    def _show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.menu.post(event.x_root, event.y_root)

    def set_rows(self, rows: List[Dict[str, Any]]):
        """Populate treeview with list of link dictionaries."""
        self.tree.delete(*self.tree.get_children())
        self._row_data_map.clear()

        # Identify duplicates in this batch
        code_counts = {}
        for r in rows:
            c = (r.get("code") or "").strip()
            if c:
                code_counts[c] = code_counts.get(c, 0) + 1

        for r in rows:
            item_id = str(r["id"])
            self._row_data_map[item_id] = r

            serial_str = f"#{r['serial_no']:04d}"
            code_str = r.get("code") or "—"
            shot_str = r.get("screenshot_filename") or "—"
            conf = r.get("confidence")
            conf_str = f"{float(conf):.1f}%" if conf and conf > 0 else "—"
            status = r.get("processing_status", "PENDING")
            verif = r.get("verification_status", "UNVERIFIED")

            tag = status
            if code_str != "—" and code_counts.get(code_str, 0) > 1:
                tag = "DUPLICATE"
            elif verif == "VERIFIED":
                tag = "VERIFIED"

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(serial_str, r.get("url", ""), code_str, shot_str, conf_str, status, verif),
                tags=(tag,)
            )

    def update_single_row(self, row: Dict[str, Any]):
        """Fast incremental update for a single processed link."""
        item_id = str(row["id"])
        self._row_data_map[item_id] = row

        if self.tree.exists(item_id):
            serial_str = f"#{row['serial_no']:04d}"
            code_str = row.get("code") or "—"
            shot_str = row.get("screenshot_filename") or "—"
            conf = row.get("confidence")
            conf_str = f"{float(conf):.1f}%" if conf and conf > 0 else "—"
            status = row.get("processing_status", "PENDING")
            verif = row.get("verification_status", "UNVERIFIED")

            tag = status
            if verif == "VERIFIED":
                tag = "VERIFIED"

            self.tree.item(
                item_id,
                values=(serial_str, row.get("url", ""), code_str, shot_str, conf_str, status, verif),
                tags=(tag,)
            )
            # Ensure visible
            self.tree.see(item_id)

    def get_selected_row(self) -> Optional[Dict[str, Any]]:
        sel = self.tree.selection()
        if sel:
            return self._row_data_map.get(sel[0])
        return None

    def get_selected_ids(self) -> List[int]:
        sel = self.tree.selection()
        return [int(item_id) for item_id in sel if item_id.isdigit()]

    def _on_row_selected(self, event):
        row = self.get_selected_row()
        if row and self.on_select_row:
            self.on_select_row(row)

    def _on_filter_changed(self, new_filter: str):
        self.current_filter = new_filter
        for k, btn in self.filter_buttons.items():
            if k == new_filter:
                btn.configure(fg_color=COLORS["primary"], text_color=COLORS["text_white"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        if hasattr(self, "filter_callback") and self.filter_callback:
            self.filter_callback(new_filter, self.search_entry.get().strip())

    def _on_search(self):
        q = self.search_entry.get().strip()
        if hasattr(self, "filter_callback") and self.filter_callback:
            self.filter_callback(self.current_filter, q)

    def _copy_code(self):
        row = self.get_selected_row()
        if row and row.get("code"):
            self.clipboard_clear()
            self.clipboard_append(row["code"])

    def _copy_url(self):
        row = self.get_selected_row()
        if row and row.get("url"):
            self.clipboard_clear()
            self.clipboard_append(row["url"])

    def _open_screenshot(self):
        row = self.get_selected_row()
        if row and row.get("screenshot_filename"):
            shot_path = SCREENSHOTS_DIR / row["screenshot_filename"]
            if shot_path.exists():
                os.startfile(str(shot_path))

    def _mark_verified(self):
        row = self.get_selected_row()
        if row and self.on_manual_edit:
            code = row.get("code") or ""
            self.on_manual_edit(row["id"], code)

