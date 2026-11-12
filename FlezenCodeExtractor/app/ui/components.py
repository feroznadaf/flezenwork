import customtkinter as ctk
from typing import Optional, Callable, Any
from app.ui.theme import COLORS, FONTS

class StatCard(ctk.CTkFrame):
    """Modern dark dashboard metric card."""
    def __init__(self, master, title: str, initial_value: str = "0",
                 accent_color: str = COLORS["primary"], icon: str = "", **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=10,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs
        )
        self.accent_color = accent_color

        # Top Bar with accent indicator and title
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=14, pady=(12, 4))

        # Accent dot
        dot = ctk.CTkLabel(
            top_frame,
            text="●",
            font=("Segoe UI", 12),
            text_color=accent_color,
            width=16
        )
        dot.pack(side="left")

        title_label = ctk.CTkLabel(
            top_frame,
            text=f"{icon} {title}".strip(),
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"]
        )
        title_label.pack(side="left", padx=4)

        # Value label
        self.value_label = ctk.CTkLabel(
            self,
            text=initial_value,
            font=FONTS["stat_num"],
            text_color=COLORS["text_white"]
        )
        self.value_label.pack(anchor="w", padx=16, pady=(0, 12))

    def update_value(self, new_value: Any):
        self.value_label.configure(text=str(new_value))

class ProgressBarWithETA(ctk.CTkFrame):
    """Progress tracker displaying percentage, completed count, and remaining time."""
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            corner_radius=8,
            border_width=1,
            border_color=COLORS["border"],
            **kwargs
        )
        
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.pack(fill="x", padx=14, pady=(10, 4))

        self.label_status = ctk.CTkLabel(
            info_frame,
            text="Ready to process",
            font=FONTS["body_bold"],
            text_color=COLORS["text_primary"]
        )
        self.label_status.pack(side="left")

        self.label_eta = ctk.CTkLabel(
            info_frame,
            text="ETA: —",
            font=FONTS["caption"],
            text_color=COLORS["text_secondary"]
        )
        self.label_eta.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self,
            progress_color=COLORS["primary"],
            fg_color=COLORS["bg_card_alt"],
            height=8,
            corner_radius=4
        )
        self.progress_bar.pack(fill="x", padx=14, pady=(0, 10))
        self.progress_bar.set(0.0)

    def set_progress(self, current: int, total: int, eta_seconds: Optional[float] = None):
        if total <= 0:
            pct = 0.0
            pct_text = "0%"
        else:
            pct = min(1.0, current / total)
            pct_text = f"{int(pct * 100)}%"

        self.progress_bar.set(pct)
        self.label_status.configure(text=f"Processed: {current} / {total} ({pct_text})")

        if eta_seconds is not None and eta_seconds > 0 and current < total:
            mins, secs = divmod(int(eta_seconds), 60)
            hrs, mins = divmod(mins, 60)
            if hrs > 0:
                eta_str = f"ETA: ~{hrs}h {mins}m"
            elif mins > 0:
                eta_str = f"ETA: ~{mins}m {secs}s"
            else:
                eta_str = f"ETA: ~{secs}s"
            self.label_eta.configure(text=eta_str)
        elif current >= total and total > 0:
            self.label_eta.configure(text="Complete ✓")
        else:
            self.label_eta.configure(text="ETA: —")
