from theme_manager import ThemeManager, apply_theme_to_window, get_copyright_year
from datetime import date, datetime
#!/usr/bin/env python3
import shutil
import subprocess
import datetime as _doc_dt
_DOC_YEAR = _doc_dt.date.today().year

f"""
UPS Tracking Checker - GUI Application with Microsoft Edge Bot
==============================================================
Paste tracking numbers, checks each one via headless Edge, saves CSV.

  - Real-time progress updates with colored log
  - Automatic CSV saving every 10 results
  - Edge browser automation (headless)
  - Cancel operation at any time

Ship this file together with verge_icon.ico and Verge_Logo.png
in the same folder for the window/taskbar icon and header logo.

Developed by Abad Umair Channa | Copyright © {date.today().year} | All rights reserved.
"""

import sys
import queue
import threading
import os
import time
import re
import csv
import tempfile
from typing import Callable, Dict, List, Optional
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from header_manager import FixedHeaderManager
from logo_handler import LogoHandler
import base64
if not sys.version_info >= (3, 10):
    print("Python 3.10+ required.")
    sys.exit(1)

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.edge.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError as e:
    messagebox.showerror("Missing Dependency",
        f"Required package is missing: {e}\n\n"
        "Please run: pip install selenium")
    sys.exit(1)

# Optional PIL for logo / icon handling
try:
    from PIL import Image as _PI, ImageTk as _PIT
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pillow",
                        "--quiet", "--disable-pip-version-check"],
                       capture_output=True)
        from PIL import Image as _PI, ImageTk as _PIT
        HAS_PIL = True
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
# BRAND / WINDOW CONFIG  (kept in sync with Verge_Inventory_Aging_Processor.pyw)
# ─────────────────────────────────────────────────────────────────────────────
NAVY  = "#2A3641"
EMBEDDED_LOGO_B64 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "embedded_logo_b64.txt"), "r").read().strip() if not getattr(sys, "frozen", False) else open(os.path.join(getattr(sys, "_MEIPASS", "."), "assets", "embedded_logo_b64.txt"), "r").read().strip()
EMBEDDED_ICON_B64 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "embedded_icon_b64.txt"), "r").read().strip() if not getattr(sys, "frozen", False) else open(os.path.join(getattr(sys, "_MEIPASS", "."), "assets", "embedded_icon_b64.txt"), "r").read().strip()

RED   = "#6E8595"
WHITE = "#ffffff"
LIGHT = "#E6E7E8"
LOG_BG   = "#10182e"
LOG_FG   = "#a8d8ff"

ICON_ICO_NAME = "verge_icon.ico"
LOGO_PNG_NAME = "Verge_Logo.png"
COPYRIGHT_TEXT = f"Developed by Abad Umair Channa | Copyright © {date.today().year} | All rights reserved."
ICON_ICO_B64 = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon_ico_b64.txt"), "r").read().strip() if not getattr(sys, "frozen", False) else open(os.path.join(getattr(sys, "_MEIPASS", "."), "assets", "icon_ico_b64.txt"), "r").read().strip()


def _script_dir() -> str:
    """Directory containing this .pyw (or .exe when frozen)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _resource_path(name: str) -> str:
    """Resolve a bundled resource (logo PNG) whether running from source or
    from a PyInstaller one-file EXE (extra files are extracted to _MEIPASS)."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", _script_dir())
        return os.path.join(base, name)
    return os.path.join(_script_dir(), name)




def _extract_embedded_icon(b64, filename):
    """Decode an embedded base64 icon to a temp file; return path or None."""
    try:
        if not b64:
            return None
        import base64 as _b64, tempfile, os
        target = os.path.join(tempfile.gettempdir(), filename)
        with open(target, "wb") as fh:
            fh.write(_b64.b64decode(b64))
        return target if os.path.isfile(target) else None
    except Exception:
        return None

def _set_window_icon(root):
    """Set taskbar + titlebar icon from embedded base64 ICO."""
    import base64, tempfile, atexit, os, sys

    # 1. Try sys._MEIPASS (PyInstaller onefile extraction dir)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        ico_path = os.path.join(meipass, "verge_icon.ico")
        if os.path.exists(ico_path):
            try:
                root.iconbitmap(default=ico_path)
                root.after(200, lambda p=ico_path: root.iconbitmap(default=p))
                return
            except Exception:
                pass

    # 2. Try next to the exe/script
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, "verge_icon.ico")
    if os.path.exists(ico_path):
        try:
            root.iconbitmap(default=ico_path)
            root.after(200, lambda p=ico_path: root.iconbitmap(default=p))
            return
        except Exception:
            pass

    # 3. Decode EMBEDDED_ICON_B64 to %TEMP% (no spaces, always writable)
    try:
        data = base64.b64decode(EMBEDDED_ICON_B64.strip())
        tmp_dir = os.environ.get("TEMP", tempfile.gettempdir())
        ico_path = os.path.join(tmp_dir, "verge_app_icon.ico")
        with open(ico_path, "wb") as f:
            f.write(data)
        root.iconbitmap(default=ico_path)
        root.after(200, lambda p=ico_path: root.iconbitmap(default=p))
        return
    except Exception:
        pass


def run_cmd(args, timeout=5) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (result.stdout or "") + (result.stderr or "")
    except Exception:
        return ""


def extract_major(version_text: str) -> Optional[int]:
    match = re.search(r"(\d+)\.\d+\.\d+\.\d+", version_text or "")
    return int(match.group(1)) if match else None


def get_edge_major_version() -> Optional[int]:
    if sys.platform == "win32":
        edge_paths = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Edge\Application\msedge.exe"),
        ]
        for path in edge_paths:
            if os.path.exists(path):
                version_text = run_cmd([path, "--version"])
                major = extract_major(version_text)
                if major:
                    return major
        try:
            import winreg
            reg_paths = [
                r"Software\Microsoft\Edge\BLBeacon",
                r"Software\WOW6432Node\Microsoft\Edge\BLBeacon",
            ]
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for reg_path in reg_paths:
                    try:
                        key = winreg.OpenKey(root, reg_path)
                        version, _ = winreg.QueryValueEx(key, "version")
                        major = extract_major(version)
                        if major:
                            return major
                    except Exception:
                        pass
        except Exception:
            pass
    return None




MONTH_MAP = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4,
    "Jun": 6, "Jul": 7, "Aug": 8,
    "Sep": 9, "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}

STATUS_WORDS = (
    "Delivered", "Out for Delivery", "On the Way", "Label Created",
    "Delivery Attempted", "Exception", "Processing", "Returned",
    "Shipment Ready", "The delivery date will be provided",
)


class UPSTrackingBot:
    """UPS tracking bot with callback support for GUI integration"""

    def __init__(self, headless: bool = True, progress_callback: Optional[Callable] = None):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.results: List[Dict[str, str]] = []
        self.saved_count = 0
        # Fresh temp profile every run — no persistent profile, no lock conflicts
        self.profile_dir = tempfile.mkdtemp(prefix="ups_edge_profile_")
        self.progress_callback = progress_callback
        self.is_cancelled = False

    def make_options(self):
        options = Options()
        # Always headless — works reliably with UPS.com
        options.add_argument("--headless=new")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        return options

    def start_driver(self):
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
        get_edge_major_version()
        self.log("Launching Microsoft Edge...")

        # Selenium Manager (Service() with no args) auto-downloads the
        # matching msedgedriver. Try that first; if it fails, fall back to
        # webdriver-manager.
        self.driver = None
        last_error = None

        # Strategy 1: Selenium Manager (built into selenium 4.10+)
        try:
            self.log("Trying Selenium Manager (auto-download)...")
            self.driver = webdriver.Edge(service=Service(), options=self.make_options())
        except Exception as e1:
            last_error = e1
            self.log(f"Selenium Manager failed: {e1}")

        # Strategy 2: webdriver-manager
        if self.driver is None:
            try:
                self.log("Trying webdriver-manager...")
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                svc = Service(EdgeChromiumDriverManager().install())
                self.driver = webdriver.Edge(service=svc, options=self.make_options())
            except Exception as e2:
                last_error = e2
                self.log(f"webdriver-manager failed: {e2}")

        if self.driver is None:
            raise RuntimeError(
                f"Microsoft Edge could not launch.\n"
                f"Last error: {last_error}\n\n"
                f"Fix: pip install --upgrade selenium webdriver-manager")

        self.wait = WebDriverWait(self.driver, 40)
        self.driver.set_page_load_timeout(60)
        self.log("Browser ready.\n")

    def log(self, message: str):
        if self.progress_callback:
            self.progress_callback("log", message)
        else:
            print(message)

    def update_progress(self, current: int, total: int, tracking: str, result: str):
        if self.progress_callback:
            self.progress_callback("progress", {
                "current": current, "total": total,
                "tracking": tracking, "result": result})

    @staticmethod
    def extract_tracking_numbers(text: str) -> List[str]:
        text = text.replace(",", "\n")
        candidates = []
        for line in text.splitlines():
            for part in line.split():
                candidates.append(part.strip())
        patterns = [r"\b1Z[A-Z0-9]{16}\b", r"\b\d{9,26}\b", r"\b[A-Z]{2}\d{9}[A-Z]{2}\b"]
        tracking = []
        for cand in candidates:
            clean = re.sub(r"[^A-Za-z0-9]", "", cand).upper()
            for pattern in patterns:
                if re.fullmatch(pattern, clean, re.IGNORECASE):
                    tracking.append(clean)
                    break
        seen = set(); unique = []
        for tn in tracking:
            if tn not in seen:
                seen.add(tn); unique.append(tn)
        return unique

    def wait_for_ups_result(self, tracking_number: str) -> str:
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        deadline = time.time() + 40
        last_text = ""
        while time.time() < deadline:
            if self.is_cancelled: return ""
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                last_text = body_text
                if tracking_number in body_text and any(w in body_text for w in STATUS_WORDS):
                    return body_text
                try:
                    if self.driver.find_element(By.ID, "stApp_nameKey").text.strip():
                        return body_text
                except Exception: pass
                try:
                    if self.driver.find_element(By.ID, "st_App_PkgStsMonthNum").text.strip():
                        return body_text
                except Exception: pass
                if any(w in body_text for w in STATUS_WORDS):
                    return body_text
            except Exception: pass
            time.sleep(1)
        return last_text

    def is_delivered(self, body_text: str) -> bool:
        try:
            status_elem = self.driver.find_element(By.ID, "stApp_nameKey")
            if re.search(r"\bDelivered\b", status_elem.text.strip(), re.IGNORECASE):
                return True
        except Exception: pass
        lines = [re.sub(r"\s+", " ", x).strip() for x in (body_text or "").splitlines() if x.strip()]
        for line in lines[:25]:
            if line.lower() == "delivered" or line.lower().startswith("delivered "):
                return True
        return False

    def get_delivery_date(self) -> Optional[str]:
        try:
            elem = self.wait.until(EC.presence_of_element_located((By.ID, "st_App_PkgStsMonthNum")))
            text = re.sub(r"\s+", " ", elem.text).strip()
            match = re.search(
                r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+([A-Za-z]+)\s+(\d{1,2})",
                text, re.IGNORECASE)
            if match:
                month_num = MONTH_MAP.get(match.group(2).replace(".", ""))
                if month_num:
                    return f"{month_num}/{int(match.group(3))}/{datetime.now().year}"
            match = re.search(r"\b([A-Za-z]+)\s+(\d{1,2})\b", text, re.IGNORECASE)
            if match:
                month_num = MONTH_MAP.get(match.group(1).replace(".", ""))
                if month_num:
                    return f"{month_num}/{int(match.group(2))}/{datetime.now().year}"
            self.log(f"Date selector found but could not parse: {text}")
            return None
        except Exception as e:
            self.log(f"Date extraction error: {e}")
            return None

    def check_tracking(self, tracking_number: str) -> Dict[str, str]:
        try:
            url = (f"https://www.ups.com/track?track=yes&trackNums={tracking_number}"
                   "&loc=en_US&requester=ST/trackdetails")
            self.driver.get(url)
            body_text = self.wait_for_ups_result(tracking_number)
            if self.is_cancelled:
                return {"Tracking": tracking_number, "Result": "Cancelled"}
            if not body_text:
                return {"Tracking": tracking_number, "Result": "Not delivered"}
            if not self.is_delivered(body_text):
                return {"Tracking": tracking_number, "Result": "Not delivered"}
            date_str = self.get_delivery_date()
            if date_str:
                return {"Tracking": tracking_number, "Result": f"Delivered {date_str}"}
            return {"Tracking": tracking_number, "Result": "Delivered"}
        except TimeoutException:
            self.log(f"⚠️ Timeout checking {tracking_number}")
            return {"Tracking": tracking_number, "Result": "Not delivered"}
        except Exception as e:
            self.log(f"❌ ERROR checking {tracking_number}: {e}")
            return {"Tracking": tracking_number, "Result": f"ERROR: {e}"}

    def save_results(self, output_file: str, force: bool = False):
        SAVE_EVERY = 10
        total_results = len(self.results)
        if not force and total_results - self.saved_count < SAVE_EVERY: return
        if total_results <= self.saved_count: return
        new_rows = self.results[self.saved_count:total_results]
        with open(output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in new_rows:
                writer.writerow([row.get("Tracking", ""), row.get("Result", "")])
        self.saved_count = total_results
        self.log(f"Saved {len(new_rows)} results. Total saved: {self.saved_count}")

    def process_all(self, tracking_numbers: List[str], output_file: str):
        total = len(tracking_numbers)
        self.log(f"Total unique tracking numbers: {total}")
        if not tracking_numbers:
            self.log("No valid tracking numbers found."); return
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Tracking", "Result"])
        self.log(f"Output file: {output_file}")
        self.log(f"\nChecking one by one. Saving after every 10 results.\n")
        for i, tn in enumerate(tracking_numbers, 1):
            if self.is_cancelled:
                self.log("\nOperation cancelled by user."); break
            self.log(f"[{i}/{total}] {tn}...")
            row = self.check_tracking(tn)
            self.results.append(row)
            self.update_progress(i, total, tn, row["Result"])
            self.save_results(output_file, force=False)
            if i < total and not self.is_cancelled: time.sleep(2)
        self.save_results(output_file, force=True)
        delivered_count = sum(1 for r in self.results if r["Result"].startswith("Delivered"))
        self.log(f"\nFinal CSV saved to: {output_file}")
        self.log(f"Summary: {delivered_count} out of {len(self.results)} packages delivered.")
        return delivered_count, len(self.results)

    def cancel(self):
        self.is_cancelled = True

    def close(self):
        if self.driver:
            try: self.driver.quit()
            except Exception: pass
            self.driver = None
        # Clean up the temp profile directory
        try:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# GUI  (styled to match Verge_Inventory_Aging_Processor.pyw)
# ═══════════════════════════════════════════════════════════════════════════
class UPSGuiApp:

    def __init__(self, root):
        self.root = root
        self.bot = None
        self.active_bot = None
        self.worker_thread = None
        self.is_processing = False
        self.output_file = None
        self.update_queue = queue.Queue()
        self._logo_img = None

        root.title("Verge Desk Solutions - UPS Tracking Checker")
        # Set the window icon BEFORE _apply_dynamic_geometry() — that method
        # calls update_idletasks() which realizes the window, and the icon
        # must be set before realization or the taskbar/titlebar icon is lost.
        _set_window_icon(root)
        # Dynamic screen resolution support: size to 90% of the screen and
        # center it (DPI-aware), then stay a normal resizable top-level so
        # Windows Snap (50% left/right, corners, Win+arrow) keeps working.
        self._apply_dynamic_geometry()
        self.root.after(10, lambda: self.root.state("zoomed"))
        root.configure(bg=LIGHT)
        root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.theme_manager = ThemeManager("Verge UPS Tracking Checker", app_name="verge-ups-tracking-checker")
        self._styles(); self._header(); self._body(); self._copyright_bar()
        apply_theme_to_window(self.root, self.theme_manager)
        self.process_queue()

    def _apply_dynamic_geometry(self) -> None:
        """Size the window to 90% of the screen and center it.

        Works on any laptop/monitor/PC (1080p, 1440p, 2K, 4K) and respects
        Windows DPI scaling (run after _enable_dpi_awareness()). The window
        stays resizable so Windows Snap gestures keep working — it centers
        on launch, then snaps normally to 50% left/right, corners or via
        Win+arrow shortcuts.
        """
        try:
            root = self.root
            root.update_idletasks()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            w = max(640, min(int(sw * 0.90), sw - 20))
            h = max(480, min(int(sh * 0.90), sh - 40))
            x = max(0, (sw - w) // 2)
            y = max(0, (sh - h) // 2)
            root.geometry(f"{w}x{h}+{x}+{y}")
            # minsize <= half the screen so 50% / corner snap is never blocked
            root.minsize(min(900, max(560, sw // 2)),
                         min(560, max(420, sh // 2)))
            root.resizable(True, True)
        except Exception:
            pass

    # ── styles ─────────────────────────────────────────────────────────────
    def _styles(self):
        s = ttk.Style(); s.theme_use("clam")
        s.configure("Run.TButton", background=RED, foreground=WHITE,
                    font=("Segoe UI", 11, "bold"), padding=(16, 9), borderwidth=0)
        s.map("Run.TButton",
              background=[("active", "#c01820"), ("disabled", "#aaa")])
        s.configure("Browse.TButton", background=NAVY, foreground=WHITE,
                    font=("Segoe UI", 10), padding=(10, 6), borderwidth=0)
        s.map("Browse.TButton", background=[("active", "#1a2550")])
        s.configure("Cancel.TButton", background="#1a2550", foreground=WHITE,
                    font=("Segoe UI", 10), padding=(10, 6), borderwidth=0)
        s.map("Cancel.TButton", background=[("active", "#2a3560")])
        s.configure("Accent.Horizontal.TProgressbar",
                    troughcolor="#dde6f0", background=RED, borderwidth=0)

    # ── header (matches Aging Processor: NAVY 108px, logo left, title center) ──

    def _extract_embedded(self, b64, filename):
        """Decode an embedded base64 asset into a temp file; return path or None."""
        try:
            if not b64:
                return None
            import base64 as _b64, tempfile, os
            target = os.path.join(tempfile.gettempdir(), filename)
            with open(target, "wb") as fh:
                fh.write(_b64.b64decode(b64))
            return target if os.path.isfile(target) else None
        except Exception:
            return None


    def _lock_header_colors(self, widget, navy):
        """Recursively bind <Enter>/<Leave> on all header widgets to force navy."""
        try:
            widget.bind("<Enter>", lambda e, w=widget, c=navy: w.configure(bg=c) if not isinstance(w, type(None)) else None)
            widget.bind("<Leave>", lambda e, w=widget, c=navy: w.configure(bg=c) if not isinstance(w, type(None)) else None)
        except Exception:
            pass
        try:
            for child in widget.winfo_children():
                self._lock_header_colors(child, navy)
        except Exception:
            pass
    def _header(self):
        """Header using FixedHeaderManager."""
        self.header_mgr = FixedHeaderManager(self.root, title="UPS Tracking Checker")
        self.header_mgr.add_theme_toggle(self.theme_manager, callback=self._apply_theme)
        if hasattr(self.header_mgr, "header_frame"):
            self.header_mgr.header_frame._tag = "header"
            for child in self.header_mgr.header_frame.winfo_children():
                child._tag = "header"
                for grandchild in child.winfo_children():
                    grandchild._tag = "header_label"
        try:
            _lp = _resource_path(LOGO_PNG_NAME) if "_resource_path" in dir() else os.path.join(os.path.dirname(os.path.abspath(__file__)), LOGO_PNG_NAME)
            if os.path.exists(_lp):
                self.header_mgr.set_logo(logo_path=_lp, text="Verge")
        except Exception:
            pass


    def _apply_theme(self, colors=None):
        """Apply theme colors to all widgets EXCEPT header (header stays navy)."""
        import tkinter as tk
        if colors is None:
            try:
                colors = self.theme_manager.get_colors()
            except Exception:
                return
        apply_theme_to_window(self.root, self.theme_manager)
        try:
            self.root.configure(bg=colors.get("bg", "#E6E7E8"))
        except Exception:
            pass
        # Walk all widgets and apply colors, but SKIP header widgets
        _PROTECTED = {"header", "header_label", "brand", "logo", "run", "sched", "stop", "footer"}
        def _walk(widget):
            try:
                tag = getattr(widget, "_tag", None)
                if tag not in _PROTECTED:
                    bg = colors.get("bg", "#E6E7E8")
                    fg = colors.get("text", "#16213a")
                    if isinstance(widget, tk.Frame):
                        widget.configure(bg=bg)
                    elif isinstance(widget, tk.Label):
                        widget.configure(bg=bg, fg=fg)
                    elif isinstance(widget, tk.Entry):
                        widget.configure(bg=colors.get("input", "#ffffff"), fg=fg)
                    elif isinstance(widget, tk.Button):
                        widget.configure(bg=bg, fg=fg)
                    else:
                        try:
                            import tkinter.scrolledtext as _st
                            if isinstance(widget, _st.ScrolledText):
                                widget.configure(bg=colors.get("panel", "#ffffff"), fg=fg)
                        except Exception:
                            pass
                for child in widget.winfo_children():
                    _walk(child)
            except Exception:
                pass
        _walk(self.root)


    def _body(self):
        body = tk.Frame(self.root, bg=LIGHT)
        body.pack(fill="both", expand=True, padx=24, pady=18)
        self._body_frame = body  # keep ref for theme updates

        # ── Two-column panel area ──────────────────────────────────────────
        panels = tk.Frame(body, bg=LIGHT)
        panels.pack(fill="both", expand=True)
        self._panels_frame = panels
        # Weighted grid (not equal pack) so the log panel gets more real
        # estate — tracking-number lines are short, but result rows
        # ("Tracking Number: ... - Status: ... - Date: ...") run long.
        panels.grid_rowconfigure(0, weight=1)
        panels.grid_columnconfigure(0, weight=4)   # input: 40%
        panels.grid_columnconfigure(1, weight=6)   # log:   60%

        # Left panel - Tracking Numbers input
        left = tk.Frame(panels, bg=LIGHT)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        tk.Label(left, text="Tracking Numbers",
                 font=("Segoe UI", 10, "bold"), fg=NAVY, bg=LIGHT).pack(anchor="w", pady=(0, 6))
        self.input_text = scrolledtext.ScrolledText(
            left, height=10, font=("Consolas", 9), wrap=tk.WORD,
            bg=WHITE, fg=NAVY, relief="flat",
            highlightbackground="#b0c4de", highlightthickness=1)
        self.input_text.pack(fill="both", expand=True)
        btn_row = tk.Frame(left, bg=LIGHT)
        btn_row.pack(fill="x", pady=(6, 0))
        self.paste_btn = ttk.Button(btn_row, text="Paste from Clipboard",
                                    style="Browse.TButton", command=self.paste_from_clipboard)
        self.paste_btn.pack(side="left", padx=(0, 6))
        self.clear_btn = ttk.Button(btn_row, text="Clear",
                                    style="Browse.TButton", command=self.clear_input)
        self.clear_btn.pack(side="left")

        # Right panel - Progress & Results log
        right = tk.Frame(panels, bg=LIGHT)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        tk.Label(right, text="Progress & Results",
                 font=("Segoe UI", 10, "bold"), fg=NAVY, bg=LIGHT).pack(anchor="w", pady=(0, 6))
        self.output_log = scrolledtext.ScrolledText(
            right, height=10, font=("Consolas", 9), wrap=tk.WORD,
            bg=LOG_BG, fg=LOG_FG, relief="flat")
        self.output_log.pack(fill="both", expand=True)
        for tag, clr in [("success", "#68D391"), ("error", "#FC8181"),
                         ("info", "#90CDF4"), ("warning", "#F6E05E")]:
            self.output_log.tag_config(tag, foreground=clr)

        # ── Progress bar ───────────────────────────────────────────────────
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            body, variable=self.progress_var, mode="determinate",
            style="Accent.Horizontal.TProgressbar")
        self.progress_bar.pack(fill="x", pady=(10, 6))

        # ── Action buttons + inline status ─────────────────────────────────
        act = tk.Frame(body, bg=LIGHT)
        act.pack(fill="x", pady=(0, 6))
        self.start_btn = ttk.Button(act, text="Start Tracking",
                                    style="Run.TButton", command=self.start_tracking)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(act, text="Cancel",
                                     style="Cancel.TButton", command=self.cancel_tracking,
                                     state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_csv_btn = ttk.Button(act, text="Open CSV Folder",
                                       style="Browse.TButton", command=self.open_csv_folder,
                                       state="disabled")
        self.open_csv_btn.pack(side="left", padx=(0, 8))
        self.progress_label = tk.Label(act, text="Ready", bg=LIGHT, fg=NAVY,
                                       font=("Segoe UI", 9))
        self.progress_label.pack(side="left")
        self.status_label = tk.Label(act, text="", bg=LIGHT, fg=NAVY,
                                     font=("Segoe UI", 9))
        self.status_label.pack(side="right")

    def _copyright_bar(self):
        bar = tk.Frame(self.root, bg=NAVY, height=26)
        bar.pack(fill="x", side="bottom"); bar.pack_propagate(False)
        bar._tag = "footer"
        lbl = tk.Label(bar, text=COPYRIGHT_TEXT, bg=NAVY, fg="#c7cbe0",
                 font=("Segoe UI", 8))
        lbl.place(relx=0.5, rely=0.5, anchor="center")
        lbl._tag = "footer"

    # ── GUI logic methods ──────────────────────────────────────────────────
    def log_message(self, level: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}\n"
        tag_map = {"log": "info", "success": "success", "error": "error", "warning": "warning"}
        self.output_log.insert(tk.END, formatted, tag_map.get(level, "info"))
        self.output_log.see(tk.END)

    def update_progress_display(self, data: dict):
        current = data.get("current", 0)
        total = data.get("total", 0)
        tracking = data.get("tracking", "")
        result = data.get("result", "")
        if total > 0:
            self.progress_var.set((current / total) * 100)
            self.progress_label.config(text=f"{current}/{total} - {tracking}")
        else:
            self.progress_label.config(text=f"{tracking} - {result}")
        self.status_label.config(text=f"Checking: {tracking}")
        if "Delivered" in result:
            self.log_message("success", f"  {tracking}: {result}")
        elif "ERROR" in result:
            self.log_message("error", f"  {tracking}: {result}")
        else:
            self.log_message("log", f"  {tracking}: {result}")

    def queue_callback(self, callback_type: str, data):
        self.update_queue.put((callback_type, data))

    def handle_callback(self, callback_type: str, data):
        if callback_type == "log":
            self.log_message("log", data)
        elif callback_type == "progress":
            self.update_progress_display(data)

    def paste_from_clipboard(self):
        try:
            self.input_text.insert(tk.END, self.root.clipboard_get())
            self.log_message("log", "Text pasted from clipboard")
        except Exception as e:
            self.log_message("error", f"Failed to paste: {e}")

    def clear_input(self):
        self.input_text.delete(1.0, tk.END)
        self.log_message("log", "Input cleared")

    def start_tracking(self):
        try:
            if self.is_processing:
                messagebox.showwarning("Processing", "Already processing!"); return
            input_content = self.input_text.get(1.0, tk.END).strip()
            if not input_content:
                messagebox.showwarning("No Input", "Please paste tracking numbers first!"); return
            tracking_numbers = UPSTrackingBot.extract_tracking_numbers(input_content)
            if not tracking_numbers:
                messagebox.showwarning("No Valid Numbers",
                                      "No valid UPS tracking numbers found!"); return
            self.output_log.delete(1.0, tk.END)
            self.progress_var.set(0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.output_file = os.path.join(os.path.expanduser("~/Downloads"),
                                           f"ups_tracking_results_{timestamp}.csv")
            self.is_processing = True
            self.start_btn.config(state="disabled")
            self.cancel_btn.config(state="normal")
            self.paste_btn.config(state="disabled")
            self.clear_btn.config(state="disabled")
            self.open_csv_btn.config(state="disabled")
            self.log_message("log", f"Starting tracking for {len(tracking_numbers)} packages...")
            self.log_message("log", f"Results: {self.output_file}")
            self.status_label.config(text=f"Processing {len(tracking_numbers)} numbers...")
            self.worker_thread = threading.Thread(target=self.run_tracking_worker,
                                                  args=(tracking_numbers,), daemon=True)
            self.worker_thread.start()
        except Exception as e:
            import traceback as _tb
            tb = _tb.format_exc()
            # Show the error in the log panel (red) AND as a popup
            try:
                self.log_message("error", f"❌ ERROR in start_tracking:\n{tb}")
            except Exception:
                pass
            messagebox.showerror("Error", f"An error occurred:\n\n{e}\n\n{tb}")

    def run_tracking_worker(self, tracking_numbers: List[str]):
        """Worker thread — runs the tracking bot. ALL log messages go through
        self.update_queue so the GUI log panel shows them. We also print to
        stderr as a backup so if the GUI is somehow dead, you can still see
        what's happening by running the .pyw from a command prompt."""
        import traceback as _tb
        def _log(msg):
            print(f"[WORKER] {msg}", file=sys.stderr, flush=True)
            self.update_queue.put(("log", msg))

        bot = None
        try:
            _log("Creating UPSTrackingBot...")
            bot = UPSTrackingBot(headless=False, progress_callback=self.queue_callback)
            self.active_bot = bot

            _log("Launching Microsoft Edge (headless)...")
            bot.start_driver()
            _log("Browser ready. Starting tracking...")

            bot.process_all(tracking_numbers, self.output_file)
            _log("All tracking numbers processed.")
            self.update_queue.put(("completed", None))
        except Exception as e:
            tb = _tb.format_exc()
            _log(f"❌ ERROR: {e}")
            print(tb, file=sys.stderr, flush=True)
            self.update_queue.put(("error", f"❌ ERROR: {e}\n{tb}"))
        finally:
            if bot:
                try:
                    bot.close()
                    _log("Browser closed.")
                except Exception as ce:
                    _log(f"Cleanup error: {ce}")
                    print(f"Cleanup error: {ce}", file=sys.stderr, flush=True)

    def cancel_tracking(self):
        if self.is_processing:
            self.log_message("warning", "Cancelling... Please wait")
            self.status_label.config(text="Cancelling...")
            self.cancel_btn.config(state="disabled")
            if hasattr(self, "active_bot") and self.active_bot:
                self.active_bot.cancel()

    def on_tracking_completed(self):
        self.is_processing = False; self.active_bot = None
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.paste_btn.config(state="normal")
        self.clear_btn.config(state="normal")
        if self.output_file and os.path.exists(self.output_file):
            self.open_csv_btn.config(state="normal")
        self.status_label.config(text="Tracking completed")
        self.progress_label.config(text="Complete!")
        self.log_message("success", f"✅ Tracking complete! Results: {self.output_file}")

    def on_tracking_error(self, error_msg: str):
        self.is_processing = False; self.active_bot = None
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.paste_btn.config(state="normal")
        self.clear_btn.config(state="normal")
        self.status_label.config(text="Error occurred")
        messagebox.showerror("Tracking Error",
                            f"An error occurred:\n\n{error_msg}")

    def open_csv_folder(self):
        if self.output_file and os.path.exists(self.output_file):
            folder = os.path.dirname(self.output_file)
            if sys.platform == "win32": os.startfile(folder)
            elif sys.platform == "darwin": subprocess.run(["open", folder])
            else: subprocess.run(["xdg-open", folder])
        else:
            messagebox.showwarning("No File", "No results file found yet!")

    def process_queue(self):
        try:
            while True:
                msg_type, data = self.update_queue.get_nowait()
                if msg_type == "completed":
                    self.on_tracking_completed()
                elif msg_type == "error":
                    if isinstance(data, str) and "\n" in data:
                        # Multi-line traceback → log to panel in red
                        self.log_message("error", data)
                    else:
                        # Single-line error → log to panel AND show popup later
                        self.log_message("error", f"❌ {data}")
                        self.root.after(10, lambda d=data: self.on_tracking_error(d))
                elif msg_type in ("log", "progress"):
                    self.handle_callback(msg_type, data)
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def on_closing(self):
        if self.is_processing:
            self.log_message("warning", "Closing while tracking is in progress...")
        self.root.destroy()


def _enable_dpi_awareness() -> None:
    """Make Windows report physical pixels so winfo_screen* is accurate on
    high-DPI displays (1080p, 1440p, 2K, 4K, DPI-scaled laptops)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        # Set AppUserModelID BEFORE any window is created — must be UNIQUE
        # per app or Windows caches a generic/shared taskbar icon.
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VergeDesk.UPSTrackingChecker")
        except Exception:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # system DPI aware
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def main():
    import tkinter as tk
    _enable_dpi_awareness()
    root = tk.Tk()
    UPSGuiApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
