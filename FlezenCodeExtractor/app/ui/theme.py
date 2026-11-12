import tkinter as tk
from tkinter import ttk

# Modern Dark Linear / Stripe Dashboard Theme Palette
COLORS = {
    "bg_root": "#0B0D14",
    "bg_sidebar": "#111420",
    "bg_card": "#171B2B",
    "bg_card_alt": "#1D2236",
    "bg_input": "#1C2033",
    "border": "#282E47",
    "border_light": "#373E5C",

    # Accent & Actions
    "primary": "#6366F1",         # Indigo
    "primary_hover": "#4F46E5",
    "primary_subtle": "#25284D",
    "accent_cyan": "#06B6D4",
    "accent_purple": "#8B5CF6",

    # Status Highlights
    "success": "#10B981",         # Emerald
    "success_bg": "#064E3B",
    "success_text": "#34D399",

    "warning": "#F59E0B",         # Amber
    "warning_bg": "#78350F",
    "warning_text": "#FBBF24",

    "danger": "#EF4444",          # Crimson
    "danger_bg": "#7F1D1D",
    "danger_text": "#F87171",

    "info": "#3B82F6",            # Sky blue
    "info_bg": "#1E3A8A",
    "info_text": "#60A5FA",

    "duplicate": "#EC4899",       # Magenta
    "duplicate_bg": "#831843",
    "duplicate_text": "#F472B6",

    # Typography
    "text_white": "#FFFFFF",
    "text_primary": "#F1F5F9",
    "text_secondary": "#94A3B8",
    "text_muted": "#64748B",
    "text_disabled": "#475569",
}

FONTS = {
    "title_lg": ("Segoe UI", 18, "bold"),
    "title_md": ("Segoe UI", 14, "bold"),
    "title_sm": ("Segoe UI", 12, "bold"),
    "body": ("Segoe UI", 10),
    "body_bold": ("Segoe UI", 10, "bold"),
    "caption": ("Segoe UI", 9),
    "code": ("Consolas", 11, "bold"),
    "stat_num": ("Segoe UI", 22, "bold"),
}

def apply_treeview_theme(style: ttk.Style):
    """Custom ttk.Treeview theme for the dark dashboard."""
    style.theme_use("clam")
    
    # Configure Treeview Header
    style.configure(
        "Dark.Treeview.Heading",
        background=COLORS["bg_card_alt"],
        foreground=COLORS["text_secondary"],
        font=FONTS["body_bold"],
        borderwidth=0,
        relief="flat",
        padding=(8, 8)
    )
    style.map(
        "Dark.Treeview.Heading",
        background=[("active", COLORS["border_light"])]
    )

    # Configure Treeview Rows
    style.configure(
        "Dark.Treeview",
        background=COLORS["bg_card"],
        foreground=COLORS["text_primary"],
        fieldbackground=COLORS["bg_card"],
        font=FONTS["body"],
        rowheight=32,
        borderwidth=0,
        relief="flat"
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", COLORS["primary_subtle"])],
        foreground=[("selected", COLORS["text_white"])]
    )

