"""
Theme Manager - Standardized for VDS/VidaPay Ecosystem
Developed by www.3SVerse.com | Copyright © {year} | All rights reserved.
"""
import os

_THEME_MANAGER_VERSION = "2.1.0"
import json
from datetime import datetime

# ── Lazy tkinter import ──
# tkinter is imported inside methods that need it, not at module level.
# This prevents ModuleNotFoundError when the module is imported before
# tkinter availability is verified.


class ThemeManager:
    """Manages light/dark themes with protected widget tags."""


    BRAND_NAVY = "#0B0E13"
    BRAND_RED = "#2C5FE3"
    BRAND_WHITE = "#ffffff"

    THEMES = {
        "light": {
            "bg": "#E6E7E8",
            "panel": "#ffffff",
            "panel_alt": "#D6D9DC",
            "text": "#2A3641",
            "text_dim": "#6E8595",
            "input": "#ffffff",
            "border": "#C5C8CC",
            "navy": "#2A3641",
            "red": "#6E8595",
            "log_bg": "#2A3641",
            "log_fg": "#e2e8f0",
        },
        "dark": {
            "bg": "#0B0E13",
            "panel": "#171A1F",
            "panel_alt": "#2A2C31",
            "text": "#F5F7FA",
            "text_dim": "#8A93A0",
            "input": "#1E2228",
            "border": "#262B33",
            "navy": "#0B0E13",
            "red": "#2C5FE3",
            "log_bg": "#10141B",
            "log_fg": "#C9D1DC",
        }
    }

    _PROTECTED_TAGS = {"header", "header_label", "brand", "logo", "run", "sched", "stop", "footer"}

    def __init__(self, default="dark", app_name="VDS"):
        self.app_name = app_name
        self.CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "verge-telecom", app_name)
        self.CONFIG_FILE = os.path.join(self.CONFIG_DIR, "theme.json")
        self.current_theme = self._load_theme() or default
        os.makedirs(self.CONFIG_DIR, exist_ok=True)

    def _load_theme(self):
        if os.path.exists(self.CONFIG_FILE):
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    return json.load(f).get("theme", "dark")
            except Exception:
                pass
        return None

    def save_theme(self, theme_name):
        self.current_theme = theme_name
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump({"theme": theme_name}, f)
        except Exception:
            pass

    def get_colors(self):
        return self.THEMES.get(self.current_theme, self.THEMES["dark"]).copy()

    def toggle(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.save_theme(self.current_theme)
        return self.current_theme

    def apply_theme_to_window(self, window):
        """Apply theme to a tkinter window."""
        import tkinter as tk
        from tkinter import ttk

        colors = self.get_colors()
        style = ttk.Style(window)
        style.theme_use("clam")

        # Configure ttk styles
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["text"], font=("Segoe UI", 9))
        style.configure("TCombobox", fieldbackground=colors.get("input", "#ffffff"), background=colors.get("panel_alt", "#eef0f6"), foreground=colors.get("text", "#16213a"))
        style.configure("TButton", background=colors["panel_alt"], foreground=colors["text"], font=("Segoe UI", 9))
        style.map("TButton", background=[("active", self.BRAND_RED)], foreground=[("active", self.BRAND_WHITE)])
        style.configure("TEntry", fieldbackground=colors["input"], foreground=colors["text"])
        style.configure("TNotebook", background=colors["bg"])
        style.configure("TNotebook.Tab", background=colors["panel_alt"], foreground=colors["text"], font=("Segoe UI", 9))
        style.map("TNotebook.Tab", background=[("selected", colors["panel"])])
        style.configure("Treeview", background=colors["panel"], foreground=colors["text"], fieldbackground=colors["panel"])
        style.configure("Treeview.Heading", background=self.BRAND_NAVY, foreground=self.BRAND_WHITE, font=("Segoe UI", 9, "bold"))
        style.map("Treeview.Heading", background=[("active", self.BRAND_NAVY)], foreground=[("active", self.BRAND_WHITE)])
        style.configure("Horizontal.TProgressbar", background=colors["red"], troughcolor=colors["panel_alt"])
        style.configure("TCheckbutton", background=colors["bg"], foreground=colors["text"])
        style.configure("TRadiobutton", background=colors["bg"], foreground=colors["text"])
        style.configure("TLabelframe", background=colors["bg"], foreground=colors["text"])
        style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["text"], font=("Segoe UI", 9, "bold"))

        window.configure(background=colors["bg"])
        self._walk(window, colors)
        from partner_theme_runtime import enforce_brand_interactions
        enforce_brand_interactions(window, self.BRAND_NAVY, self.BRAND_RED)

        # Keep Windows native chrome synchronized without changing this
        # partner app's own logo, icon, header, or background artwork.
        try:
            from native_titlebar import sync_titlebar
            sync_titlebar(window, dark=(self.current_theme == "dark"))
        except Exception:
            pass

    def _walk(self, widget, colors):
        """Walk widget tree and apply colors, skipping protected widgets."""
        import tkinter as tk

        for child in widget.winfo_children():
            # Skip ALL protected tags — header, footer, logo, etc.
            tag = getattr(child, "_tag", None)
            if tag in self._PROTECTED_TAGS:
                continue
            tags = set(child.bindtags())
            if tags & self._PROTECTED_TAGS:
                continue

            wtype = child.winfo_class()
            bg = colors["bg"]
            panel = colors.get("panel", colors["bg"])
            panel_alt = colors.get("panel_alt", colors["bg"])
            text_fg = colors["text"]
            input_bg = colors.get("input", panel)

            try:
                if wtype in ("Frame", "Tk", "Toplevel"):
                    child.configure(bg=bg)
                elif wtype in ("Labelframe", "labelframe", "TLabelframe"):
                    child.configure(bg=panel)
                elif wtype == "Label":
                    child.configure(bg=bg, fg=text_fg)
                elif wtype == "Button":
                    child.configure(bg=panel_alt, fg=text_fg,
                                    activebackground=panel,
                                    activeforeground=text_fg)
                elif wtype == "Entry":
                    child.configure(bg=input_bg, fg=text_fg,
                                    insertbackground=text_fg,
                                    disabledbackground=panel_alt)
                elif wtype == "Text":
                    child.configure(bg=panel, fg=text_fg,
                                    insertbackground=text_fg,
                                    selectbackground=colors.get("red", "#6E8595"),
                                    selectforeground="#ffffff")
                elif wtype == "Listbox":
                    child.configure(bg=input_bg, fg=text_fg,
                                    selectbackground=colors.get("red", "#6E8595"),
                                    selectforeground="#ffffff")
                elif wtype in ("Canvas", "canvas"):
                    child.configure(bg=bg, highlightbackground=colors.get("border", bg))
                elif wtype == "PanedWindow":
                    child.configure(bg=bg)
                elif wtype == "Checkbutton":
                    child.configure(bg=bg, fg=text_fg,
                                    activebackground=bg,
                                    activeforeground=text_fg,
                                    selectcolor=panel)
                elif wtype == "Radiobutton":
                    child.configure(bg=bg, fg=text_fg,
                                    activebackground=bg,
                                    activeforeground=text_fg,
                                    selectcolor=panel)
                elif wtype == "Scale":
                    child.configure(bg=bg, fg=text_fg,
                                    troughcolor=panel_alt,
                                    activebackground=colors.get("red", "#6E8595"))
                elif wtype == "Spinbox":
                    child.configure(bg=input_bg, fg=text_fg,
                                    insertbackground=text_fg,
                                    buttonbackground=panel_alt)
                elif wtype == "OptionMenu":
                    child.configure(bg=panel_alt, fg=text_fg,
                                    activebackground=panel,
                                    activeforeground=text_fg)
                elif wtype == "Message":
                    child.configure(bg=bg, fg=text_fg)
                elif wtype == "Scrollbar":
                    child.configure(bg=panel_alt, troughcolor=bg,
                                    activebackground=colors.get("red", "#6E8595"))
            except tk.TclError:
                pass

            # Always recurse regardless of widget type
            self._walk(child, colors)

    def create_theme_toggle_button(self, parent, callback=None):
        """Create a theme toggle button.

        Blend into the parent header: parent-matching background is
        Tkinter's equivalent of transparency (Tk widgets have no alpha).
        Shows a SUN while the dark theme is active (click -> light) and a
        MOON while light is active (click -> dark)."""
        import tkinter as tk

        try:
            bg = parent.cget("bg")
        except Exception:
            # ttk parents have no -bg option; use the brand band navy.
            bg = self.BRAND_NAVY

        btn = tk.Label(
            parent,
            text="\u2600" if self.current_theme == "dark" else "\u263e",
            bg=bg,
            fg=self.BRAND_WHITE,
            font=("Segoe UI Symbol", 13),
            cursor="hand2",
            padx=8,
            pady=2,
        )
        btn._tag = "header_label"  # theme walks must never recolor it
        btn.bind("<Button-1>", lambda e: self._on_toggle(btn, callback))
        return btn

    def _on_toggle(self, btn, callback):
        new_theme = self.toggle()
        btn.configure(text="\u2600" if new_theme == "dark" else "\u263e")
        if callback:
            callback(new_theme)

    @staticmethod
    def get_copyright_year():
        return datetime.now().year

    @staticmethod
    def get_copyright_text():
        return f"Developed by www.3SVerse.com | Copyright © {datetime.now().year} | All rights reserved."


def apply_theme_to_window(window, theme_manager=None):
    """Convenience function."""
    if theme_manager is None:
        theme_manager = ThemeManager()
    theme_manager.apply_theme_to_window(window)


def get_copyright_year():
    return ThemeManager.get_copyright_year()


# ── VDS-style abstract band texture (brand-fixed, theme-independent) ──
# Mirrors the VDSDesk splash reference: near-black brand band with huge,
# subtle abstract circles - navy tints hugging the TOP-RIGHT of the header
# band, a teal arc peeking from the BOTTOM-LEFT of the footer band.
# Colors are sampled from the user-provided reference image.

BAND_BG = "#0B0E13"

_HEADER_CIRCLES = (
    # (fill, center_x_rel, center_y_rel, radius_rel_to_height)
    ("#0E1728", 0.94, 0.10, 1.55),   # large navy circle hugging the top-right corner
    ("#101B30", 0.72, 1.15, 1.00),   # softer companion circle below-left of it
)

_FOOTER_CIRCLES = (
    ("#0B1919", 0.05, 1.75, 1.90),   # teal tint peeking from the bottom-left
    ("#0E1728", 0.38, 2.30, 1.55),   # faint navy companion arc
)


def draw_band_texture(canvas, zone="header"):
    """Paint the VDS-style abstract circles onto a brand band canvas.

    zone="header": big navy-tinted circles anchored to the top-right.
    zone="footer": teal-tinted arc peeking from the bottom-left.

    Geometry is computed from the canvas's CURRENT size, so this is safe to
    call again on every <Configure> (resize) event. Items are tagged
    "band_texture" and stacked below everything else on the canvas, so text
    and widgets drawn after this stay visible on top.
    """
    try:
        width = int(canvas.winfo_width())
        height = int(canvas.winfo_height())
    except Exception:
        return
    if width <= 2 or height <= 2:
        return
    canvas.delete("band_texture")
    circles = _HEADER_CIRCLES if zone == "header" else _FOOTER_CIRCLES
    for color, cx_rel, cy_rel, r_rel in circles:
        radius = height * r_rel
        cx = width * cx_rel
        cy = height * cy_rel
        canvas.create_oval(
            cx - radius, cy - radius, cx + radius, cy + radius,
            fill=color, outline="", width=0, tags=("band_texture",),
        )
    try:
        canvas.tag_lower("band_texture")
    except Exception:
        pass


# ── Theme-toggle vector glyph (sun / crescent moon) ─────────────────────────
# Tk renders emoji (☀️/🌙) as flat monochrome outlines, where a small sun is
# easy to mistake for a moon. Drawing the icon as vector art on a canvas gives
# a genuinely transparent background AND an unmistakable glyph: dark theme
# shows a sun (ring + 8 rays — click goes light), light theme shows a real
# crescent (click goes dark).

def draw_theme_glyph(canvas, cx, cy, theme, tags=("theme_toggle",), color="#ffffff"):
    """Paint the theme-toggle glyph for `theme` centered at (cx, cy).

    Items are created with the given `tags`; callers own deleting and
    re-drawing (e.g. on <Configure>) and can tag_bind clicks/cursor on the
    tag — canvas tag bindings also apply to items created later with the
    same tag.
    """
    import math

    if theme == "light":
        # Crescent: outer disc minus an equal-radius disc offset right.
        R = 8.0
        d = 5.5
        half = math.acos(d / (2 * R))
        pts = []
        steps = 36
        sweep = 2 * math.pi - 2 * half
        for i in range(steps + 1):
            a = -half - sweep * i / steps
            pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
        a_end = math.atan2(R * math.sin(half), R * math.cos(half) - d)
        a_start = math.atan2(R * math.sin(-half), R * math.cos(-half) - d)
        for i in range(steps + 1):
            a = a_end + (math.pi - a_end) * i / steps
            pts.append((cx + d + R * math.cos(a), cy + R * math.sin(a)))
        for i in range(steps + 1):
            a = -math.pi + (a_start + math.pi) * i / steps
            pts.append((cx + d + R * math.cos(a), cy + R * math.sin(a)))
        canvas.create_polygon(pts, smooth=True, fill=color,
                              outline="", width=0, tags=tags)
    else:
        # Sun: ring + 8 rays.
        r = 6.0
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                           outline=color, width=2, tags=tags)
        for i in range(8):
            a = math.radians(i * 45)
            canvas.create_line(
                cx + math.cos(a) * (r + 2.5), cy + math.sin(a) * (r + 2.5),
                cx + math.cos(a) * (r + 6.5), cy + math.sin(a) * (r + 6.5),
                fill=color, width=2, tags=tags)


# ── Standard theme-toggle canvas (vector sun/crescent, right-center) ────────
# One shared builder for ALL 3SVerse apps: a vector sun (dark theme) /
# crescent moon (light theme) drawn on a flat canvas — genuinely transparent
# on the navy header, and an unmistakable glyph (Tk renders emoji as flat
# monochrome outlines where a small sun is easy to mistake for a moon).
# Click runs on_click() (app-specific toggle + apply), then redraws.
def create_toggle_canvas(parent, theme_manager, on_click, size=36, bg="#090d26"):
    import tkinter as tk

    canvas = tk.Canvas(parent, width=size, height=size, bg=bg,
                       highlightthickness=0, bd=0, cursor="hand2")

    def render():
        canvas.delete("theme_toggle")
        draw_theme_glyph(
            canvas, size / 2.0, size / 2.0,
            "dark" if getattr(theme_manager, "current_theme", "light") == "dark" else "light",
            tags=("theme_toggle",),
        )

    def _click(_event=None):
        try:
            if on_click:
                on_click()
        finally:
            render()

    canvas.bind("<Button-1>", _click)
    canvas._render_theme_glyph = render
    canvas._tag = "header"
    render()
    return canvas
