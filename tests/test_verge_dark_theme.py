"""VergeDesk-splash dark theme regression tests.

The user's reference image pins the dark palette: near-black bg (#0B0E13),
huge subtle navy circles top-right (#0E1728), teal arc bottom-left (#0B1919),
dark card surfaces (#171A1F) and the vivid Verge blue accent (#2C5FE3).
These tests pin those exact values and the band-texture wiring so neither
the palette nor the texture can silently regress.
"""
import ast
import glob
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

DARK = {
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

LIGHT_BG = "#E6E7E8"  # light theme must stay untouched


def _read(rel):
    return open(os.path.join(ROOT, rel), encoding="utf-8").read()


def test_dark_palette_exact():
    src = _read("theme_manager.py")
    m = re.search(r'"dark":\s*\{(.*?)\}', src, re.S)
    assert m, "dark theme block missing"
    block = m.group(1)
    for key, val in DARK.items():
        assert f'"{key}": "{val}"' in block, f"dark[{key}] != {val}"


def test_light_theme_untouched():
    src = _read("theme_manager.py")
    assert f'"bg": "{LIGHT_BG}"' in src, "light theme bg was modified"


def test_brand_colors_updated_everywhere():
    for f in ("theme_manager.py", "header_manager.py"):
        src = _read(f)
        assert 'BRAND_NAVY = "#0B0E13"' in src, f"{f}: BRAND_NAVY not splash black"
        assert 'BRAND_RED = "#2C5FE3"' in src, f"{f}: BRAND_RED not Verge blue"


def test_no_legacy_colors_in_dark_block():
    """Legacy slate values must be gone from the dark palette (the LIGHT
    theme legitimately keeps them)."""
    src = _read("theme_manager.py")
    m = re.search(r'"dark":\s*\{(.*?)\}', src, re.S)
    block = m.group(1)
    for legacy in ("#2A3641", "#344052", "#3D4A5E", "#4A5A70", "#1E2832",
                   "#6E8595", "#8A9AAB", "#C5D0DC", "#E6E7E8"):
        assert legacy not in block, f"legacy {legacy} survived in dark block"
    hm = _read("header_manager.py")
    for legacy in ("#2A3641", "#6E8595", "#5A7080", "#c7cbe0"):
        assert legacy not in hm, f"legacy {legacy} survived in header_manager"


def test_band_texture_engine_present():
    src = _read("theme_manager.py")
    assert "def draw_band_texture(canvas" in src
    assert "BAND_BG = \"#0B0E13\"" in src
    for circle in ("#0E1728", "#101B30"):      # header: navy circles
        assert circle in src, f"header circle {circle} missing"
    for circle in ("#0B1919",):                # footer: teal arc
        assert circle in src, f"footer circle {circle} missing"
    assert 'tags=("band_texture",)' in src     # items lowered under text
    assert 'canvas.tag_lower("band_texture")' in src


def test_band_texture_wired_into_bands():
    src = _read("header_manager.py")
    assert "self.texture_canvas" in src, "header texture canvas missing"
    assert "self.footer_canvas" in src, "footer texture canvas missing"
    assert "def _repaint_band" in src
    assert "def _repaint_footer" in src
    assert 'painter(canvas, "header")' in src
    assert 'painter(canvas, "footer")' in src
    assert '<Configure>' in src, "bands not resize-safe"
    # title/copyright are re-drawn ON the canvases that cover their labels
    assert 'tags=("band_title",)' in src
    assert 'tags=("band_text",)' in src


def test_app_scripts_use_splash_colors():
    apps = [p for p in glob.glob(os.path.join(ROOT, "verge_*.py"))]
    assert len(apps) == 1, f"expected exactly one app script, found {apps}"
    src = open(apps[0], encoding="utf-8").read()
    assert 'NAVY  = "#0B0E13"' in src or re.search(r'NAVY\s*=\s*"#0B0E13"', src)
    assert re.search(r'RED\s*=\s*"#2C5FE3"', src)
    assert re.search(r'LIGHT\s*=\s*"#171A1F"', src)
    assert '"#10141B"' in src and '"#C9D1DC"' in src
    for legacy in ("#10182e", "#a8d8ff", "#1a2550", "#2a3560", "#dde6f0",
                   "#e8eff8", "#b0c4de", "#4a6080", "#9d9db8", "#16213a"):
        assert legacy not in src, f"legacy color {legacy} survived in app script"
    assert "fg=NAVY" not in src, "fg=NAVY would be unreadable on dark surfaces"


def test_app_scripts_still_import_clean():
    """The typing-import class of bug: module-level NameError must not return."""
    import builtins
    apps = glob.glob(os.path.join(ROOT, "verge_*.py"))
    tree = ast.parse(open(apps[0], encoding="utf-8").read())
    defined = set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            defined |= {(a.asname or a.name).split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            defined |= {(a.asname or a.name) for a in node.names if a.name != "*"}
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, ast.arg):
            defined.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
    used = {n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    missing = sorted(used - defined)
    assert not missing, f"names used but never defined/imported: {missing}"


def test_band_canvas_never_hijacks_lift_and_has_failsafe():
    """Regression (user-visible): tk.Canvas hijacks .lift()/.lower() for
    canvas-ITEM stacking (tag_raise/tag_lower) — NOT window stacking. The old
    code called texture_canvas.lift(title_label), which raised TclError that
    the except block swallowed; the already-placed full-area canvas then sat
    on TOP of the header, hiding the Verge logo, divider, theme toggle AND
    the title. The fix raises the edge widgets via tk.call('raise', ...) and
    destroys the canvas if anything fails, so brand controls can never be
    hidden again."""
    src = _read("header_manager.py")
    assert "texture_canvas.lift(" not in src, \
        "Canvas.lift(widget) hijacks tag_raise — must never be called"
    assert "footer_canvas.lift(" not in src, \
        "Canvas.lift(widget) hijacks tag_raise — must never be called"
    assert 'self.header_frame.tk.call("raise", _edge._w)' in src, \
        "edge widgets (logo/divider/toggle frames) must be raised via the low-level window raise"
    assert src.count("_canvas.destroy()") >= 2, \
        "destroy failsafes missing for header/footer texture canvases"
    # texture must repaint on the CANVAS's own Configure too — the frame's
    # Configure fires before place() resizes the canvas (canvas still 1x1),
    # so without this the texture silently never paints.
    assert 'self.texture_canvas.bind("<Configure>", self._repaint_band)' in src, \
        "texture canvas must repaint on its own <Configure> events"
    assert 'self.footer_canvas.bind("<Configure>", self._repaint_footer)' in src, \
        "footer canvas must repaint on its own <Configure> events"
    assert "import tkinter as tk" in src, \
        "add_copyright must lazily import tkinter (tk was undefined)"


def test_live_header_stack_keeps_logo_and_toggle_topmost():
    """Live display test (skipped on headless CI): at the logo and the theme
    toggle, the TOPMOST widget must be the logo label / toggle button — never
    the full-area texture canvas. At the title center the canvas IS expected
    on top, because it repaints the centered title text there."""
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        import pytest
        pytest.skip("no display available")
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        import pytest
        pytest.skip("cannot open display")
    root.geometry("900x600+0+0")
    try:
        from header_manager import FixedHeaderManager
        from theme_manager import ThemeManager

        hm = FixedHeaderManager(root, title="Stack Probe")
        hm.add_theme_toggle(
            ThemeManager(default="dark", app_name="stack-probe"), callback=None)
        logo = os.path.join(ROOT, "Verge_Logo.png")
        if os.path.exists(logo):
            hm.set_logo(logo_path=logo, text="Verge")
        root.update_idletasks()
        root.update()

        def topmost(w):
            x = w.winfo_rootx() + w.winfo_width() // 2
            y = w.winfo_rooty() + w.winfo_height() // 2
            return root.winfo_containing(x, y)

        assert topmost(hm.logo_label) == hm.logo_label, \
            f"logo covered by {topmost(hm.logo_label)}"
        assert topmost(hm.theme_toggle_btn) == hm.theme_toggle_btn, \
            f"theme toggle covered by {topmost(hm.theme_toggle_btn)}"
        assert hm.texture_canvas is not None, "texture canvas missing"
        assert topmost(hm.title_label) is hm.texture_canvas, \
            "texture canvas must sit above the title label (it repaints the title)"
    finally:
        root.destroy()
