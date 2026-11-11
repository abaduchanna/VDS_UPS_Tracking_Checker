"""
UPS Tracking Checker (PySide6/Qt build)
========================================
Same tool as the Tkinter build - paste tracking numbers, checks them via
headless Microsoft Edge (multi-track batches of up to 25 at a time, with
a one-by-one fallback), saves CSV. Only the UI toolkit differs; see
VDS_UPS_Tracking_Checker.py's module docstring for the full feature
description.
"""
from typing import Optional, Callable, List, Dict

import sys
import threading
import os
import time
import re
import csv
import tempfile
import subprocess
import shutil
from datetime import datetime

# --- 3SVerse runtime tamper guard (t197): frozen EXE main debugger = silent exit ---
import runtime_guard as _rguard3sv
_rguard3sv.enforce()

if not sys.version_info >= (3, 10):
    print("Python 3.10+ required.")
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.edge.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
except ImportError as e:
    from PySide6.QtWidgets import QApplication, QMessageBox
    _app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(None, "Missing Dependency",
        f"Required package is missing: {e}\n\nPlease run: pip install selenium")
    sys.exit(1)

from theme_manager_qt import ThemeManagerQt

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

# ── Multi-track mode (ups.com/track textarea, up to 25 numbers per submit) ──
MULTI_TRACK_URL = "https://www.ups.com/track?loc=en_US&requester=ST"
MULTI_BATCH_SIZE = 25          # UPS textarea limit: "Enter up to 25 tracking numbers"
MULTI_MAX_PAGES = 5            # click Next (stApp_pagination_nextBtn) at most 5 pages


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


class UPSTrackingBot:
    """UPS tracking bot with callback support for GUI integration"""

    def __init__(self, headless: bool = True, progress_callback: Optional[Callable] = None):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.results: List[Dict[str, str]] = []
        self.saved_count = 0
        self.profile_dir = tempfile.mkdtemp(prefix="ups_edge_profile_")
        self.progress_callback = progress_callback
        self.is_cancelled = False

    def make_options(self):
        options = Options()
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
            try:
                self.driver.quit()
            except Exception:
                pass
        get_edge_major_version()
        self.log("Launching Microsoft Edge...")

        self.driver = None
        last_error = None

        try:
            self.log("Trying Selenium Manager (auto-download)...")
            self.driver = webdriver.Edge(service=Service(), options=self.make_options())
        except Exception as e1:
            last_error = e1
            self.log(f"Selenium Manager failed: {e1}")

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
        seen = set()
        unique = []
        for tn in tracking:
            if tn not in seen:
                seen.add(tn)
                unique.append(tn)
        return unique

    def wait_for_ups_result(self, tracking_number: str) -> str:
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        deadline = time.time() + 40
        last_text = ""
        while time.time() < deadline:
            if self.is_cancelled:
                return ""
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
                last_text = body_text
                if tracking_number in body_text and any(w in body_text for w in STATUS_WORDS):
                    return body_text
                try:
                    if self.driver.find_element(By.ID, "stApp_nameKey").text.strip():
                        return body_text
                except Exception:
                    pass
                try:
                    if self.driver.find_element(By.ID, "st_App_PkgStsMonthNum").text.strip():
                        return body_text
                except Exception:
                    pass
                if any(w in body_text for w in STATUS_WORDS):
                    return body_text
            except Exception:
                pass
            time.sleep(1)
        return last_text

    def is_delivered(self, body_text: str) -> bool:
        try:
            status_elem = self.driver.find_element(By.ID, "stApp_nameKey")
            if re.search(r"\bDelivered\b", status_elem.text.strip(), re.IGNORECASE):
                return True
        except Exception:
            pass
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
            self.log(f"Timeout checking {tracking_number}")
            return {"Tracking": tracking_number, "Result": "Not delivered"}
        except Exception as e:
            self.log(f"ERROR checking {tracking_number}: {e}")
            return {"Tracking": tracking_number, "Result": f"ERROR: {e}"}

    # ── Multi-track batch mode ────────────────────────────────────────────
    # One submit = textarea #stApp_trackingNumber filled one-per-line (<=25),
    # Track click, then scrape the result cards page by page (Next button,
    # max 5 pages). Card ids are re-indexed 0..n on EVERY page.

    def _multi_first_number(self, driver=None):
        d = driver or self.driver
        try:
            return d.find_element(By.ID, "stApp_stApp_namecard_TV_trkNum0").text.strip()
        except Exception:
            return None

    def _multi_next_btn(self):
        """Return the clickable Next button, or None if disabled/absent."""
        try:
            nxt = self.driver.find_element(By.ID, "stApp_pagination_nextBtn")
        except Exception:
            return None
        cls = (nxt.get_attribute("class") or "")
        if "disabled" in cls or (nxt.get_attribute("aria-disabled") or "") == "true":
            return None
        return nxt

    def _multi_scrape_page(self, page_no: int) -> List[Dict[str, str]]:
        """Scrape every result card on the CURRENT page (indexes 0..n)."""
        rows = []
        try:
            cards = self.driver.find_elements(By.CSS_SELECTOR, "ups-card")
        except Exception:
            cards = []
        for idx in range(len(cards)):
            number = ""
            try:
                el = self.driver.find_element(By.ID, f"stApp_stApp_namecard_TV_trkNum{idx}")
                number = (el.text or "").strip()
                if not number:
                    href = el.get_attribute("href") or ""
                    if "tracknum=" in href:
                        number = href.split("tracknum=")[1].split("&")[0]
            except Exception:
                continue
            status = date_s = loc = tm = ""
            try:
                status = self.driver.find_element(
                    By.ID, f"stApp_stApp_namecard_TV_status{idx}").text.strip()
            except Exception:
                pass
            for eid, slot in ((f"st_App_namecard_PkgStsMonthNum{idx}", "date"),
                              (f"st_App_namecard_PkgStsLoc{idx}", "loc"),
                              (f"st_App_namecard_PkgStsTime{idx}", "time")):
                try:
                    val = re.sub(r"\s+", " ",
                                 self.driver.find_element(By.ID, eid).text).strip()
                except Exception:
                    val = ""
                if slot == "date":
                    date_s = val
                elif slot == "loc":
                    loc = val
                else:
                    tm = val
            if not status:
                status = "NO STATUS"
            if status.lower().startswith("delivered"):
                m = re.search(r"([A-Za-z]+)\s+(\d{1,2})", date_s, re.IGNORECASE)
                if m:
                    month = MONTH_MAP.get(m.group(1).title().replace(".", ""))
                    if month:
                        result = f"Delivered {month}/{int(m.group(2))}/{datetime.now().year}"
                    else:
                        result = "Delivered"
                else:
                    result = "Delivered"
            else:
                result = status
            rows.append({"Tracking": number, "Result": result, "Status": status,
                         "Date": date_s, "Location": loc, "Time": tm,
                         "Page": page_no})
        return rows

    def check_multi_batch(self, batch: List[str]) -> List[Dict[str, str]]:
        """Submit up to 25 tracking numbers at once and scrape ALL result
        pages (Next button, max MULTI_MAX_PAGES). Returns [] on any failure so
        the caller can fall back to the proven one-by-one path."""
        self.driver.get(MULTI_TRACK_URL)
        box = WebDriverWait(self.driver, 30).until(
            EC.element_to_be_clickable((By.ID, "stApp_trackingNumber")))
        box.clear()
        box.send_keys("\n".join(batch))
        self.log(f"Submitted {len(batch)} tracking numbers (multi-track)...")
        try:
            self.driver.find_element(By.ID, "stApp_btnTrack").click()
        except Exception:
            self.driver.find_element(
                By.XPATH, "//button[.//span[normalize-space()='Track']]").click()
        try:
            WebDriverWait(self.driver, 45).until(EC.presence_of_element_located(
                (By.ID, "stApp_trackapackage_title")))
        except TimeoutException:
            self.log("Multi-track results page did not load (timeout).")
            return []
        time.sleep(1.5)
        rows, page = [], 1
        while page <= MULTI_MAX_PAGES:
            if self.is_cancelled:
                break
            rows.extend(self._multi_scrape_page(page))
            nxt = self._multi_next_btn()
            if nxt is None:
                break
            before = self._multi_first_number()
            try:
                nxt.click()
            except Exception:
                break
            try:
                WebDriverWait(self.driver, 20).until(
                    lambda d: self._multi_first_number(d) not in (None, before))
            except TimeoutException:
                self.log("Next page did not change results — stopping pagination.")
                break
            page += 1
            time.sleep(1.0)
        self.log(f"Multi-track batch complete: {len(rows)} results collected.")
        return rows

    def save_results(self, output_file: str, force: bool = False):
        SAVE_EVERY = 10
        total_results = len(self.results)
        if not force and total_results - self.saved_count < SAVE_EVERY:
            return
        if total_results <= self.saved_count:
            return
        new_rows = self.results[self.saved_count:total_results]
        with open(output_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            for row in new_rows:
                writer.writerow([row.get("Tracking", ""), row.get("Result", ""),
                                 row.get("Date", ""), row.get("Location", ""),
                                 row.get("Time", ""), row.get("Page", "")])
        self.saved_count = total_results
        self.log(f"Saved {len(new_rows)} results. Total saved: {self.saved_count}")

    def process_all(self, tracking_numbers: List[str], output_file: str):
        total = len(tracking_numbers)
        self.log(f"Total unique tracking numbers: {total}")
        if not tracking_numbers:
            self.log("No valid tracking numbers found.")
            return
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["Tracking", "Result", "Date", "Location", "Time", "Page"])
        self.log(f"Output file: {output_file}")

        batches = [tracking_numbers[i:i + MULTI_BATCH_SIZE]
                   for i in range(0, total, MULTI_BATCH_SIZE)]
        done = 0
        use_multi = total > 1
        if use_multi:
            self.log(f"Multi-track mode: {len(batches)} batch(es) of up to "
                     f"{MULTI_BATCH_SIZE} numbers, max {MULTI_MAX_PAGES} result-pages each.\n")
        for bi, batch in enumerate(batches, 1):
            if self.is_cancelled:
                self.log("\nOperation cancelled by user.")
                break
            rows = []
            if use_multi:
                self.log(f"\nBatch {bi}/{len(batches)}: {len(batch)} tracking numbers...")
                try:
                    rows = self.check_multi_batch(batch)
                except Exception as e:
                    self.log(f"Multi-track batch failed ({e}) — one-by-one fallback.")
                    rows = []
                if not rows and not self.is_cancelled:
                    for tn in batch:
                        if self.is_cancelled:
                            break
                        self.log(f"[fallback] {tn}...")
                        rows.append(self.check_tracking(tn))
            else:
                tn = batch[0]
                self.log(f"[1/1] {tn}...")
                rows = [self.check_tracking(tn)]
            for row in rows:
                self.results.append(row)
                done += 1
                self.update_progress(done, total, row.get("Tracking", ""),
                                     row.get("Result", ""))
                self.save_results(output_file, force=False)
        self.save_results(output_file, force=True)
        delivered_count = sum(1 for r in self.results if r.get("Result", "").startswith("Delivered"))
        self.log(f"\nFinal CSV saved to: {output_file}")
        self.log(f"Summary: {delivered_count} out of {len(self.results)} packages delivered.")
        return delivered_count, len(self.results)

    def cancel(self):
        self.is_cancelled = True

    def close(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        try:
            shutil.rmtree(self.profile_dir, ignore_errors=True)
        except Exception:
            pass


# ==========================================================
# QT UI LAYER
# ==========================================================
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QPlainTextEdit, QProgressBar, QMessageBox
)

from header_manager_qt import FixedHeaderManagerQt

EMBEDDED_ICON_B64 = (
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "embedded_icon_b64.txt"), "r").read().strip()
    if not getattr(sys, "frozen", False)
    else open(os.path.join(getattr(sys, "_MEIPASS", "."), "assets", "embedded_icon_b64.txt"), "r").read().strip()
)
ICON_ICO_NAME = "VDS_icon.ico"
LOGO_PNG_NAME = "VDS_Logo.png"
APP_TITLE = "VDS Desk Solutions - UPS Tracking Checker"

LOG_COLORS = {
    "success": "#68D391",
    "error": "#FC8181",
    "info": "#90CDF4",
    "warning": "#F6E05E",
    "": "#a8d8ff",
}


def _extract_embedded_icon(b64, filename):
    try:
        if not b64:
            return None
        import base64 as _b64
        target = os.path.join(tempfile.gettempdir(), filename)
        with open(target, "wb") as fh:
            fh.write(_b64.b64decode(b64))
        return target if os.path.isfile(target) else None
    except Exception:
        return None


def _set_window_icon_qt(window):
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        ico_path = os.path.join(meipass, ICON_ICO_NAME)
        if os.path.exists(ico_path):
            window.setWindowIcon(QIcon(ico_path))
            return
    base_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.abspath(__file__))
    ico_path = os.path.join(base_dir, ICON_ICO_NAME)
    if os.path.exists(ico_path):
        window.setWindowIcon(QIcon(ico_path))
        return
    try:
        ico_path = _extract_embedded_icon(EMBEDDED_ICON_B64, "vds_app_icon.ico")
        if ico_path:
            window.setWindowIcon(QIcon(ico_path))
    except Exception:
        pass


class UIBridge(QObject):
    """Thread-safe UI update delivery (bot worker thread -> GUI thread)."""
    log = Signal(str, str)
    progress = Signal(int, int, str, str)
    completed = Signal()
    error = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        _set_window_icon_qt(self)
        self.active_bot = None
        self.worker_thread = None
        self.is_processing = False
        self.output_file = None

        self.theme_manager = ThemeManagerQt(default="dark", app_name="VDS-UPS-Tracking-Checker")

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.header_mgr = FixedHeaderManagerQt(outer, title="UPS Tracking Checker")
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOGO_PNG_NAME)
        if os.path.exists(logo_path):
            self.header_mgr.set_logo(logo_path=logo_path, text="VDS")
        self.header_mgr.add_theme_toggle(self.theme_manager, callback=self._apply_theme)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(24, 18, 24, 18)
        outer.addWidget(body, 1)

        panels = QGridLayout()
        panels.setColumnStretch(0, 4)
        panels.setColumnStretch(1, 6)
        body_layout.addLayout(panels, 1)

        left = QVBoxLayout()
        left.addWidget(self._label("Tracking Numbers", bold=True))
        self.input_text = QPlainTextEdit()
        self.input_text.setStyleSheet("font-family: Consolas;")
        left.addWidget(self.input_text, 1)
        btn_row = QHBoxLayout()
        self.paste_btn = QPushButton("Paste from Clipboard")
        self.paste_btn.clicked.connect(self.paste_from_clipboard)
        btn_row.addWidget(self.paste_btn)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_input)
        btn_row.addWidget(self.clear_btn)
        btn_row.addStretch(1)
        left.addLayout(btn_row)
        left_widget = QWidget()
        left_widget.setLayout(left)
        panels.addWidget(left_widget, 0, 0)

        right = QVBoxLayout()
        right.addWidget(self._label("Progress & Results", bold=True))
        self.output_log = QPlainTextEdit()
        self.output_log.setReadOnly(True)
        self.output_log.setStyleSheet("background: #10182e; color: #a8d8ff; font-family: Consolas;")
        right.addWidget(self.output_log, 1)
        right_widget = QWidget()
        right_widget.setLayout(right)
        panels.addWidget(right_widget, 0, 1)

        self.progress_bar = QProgressBar()
        body_layout.addWidget(self.progress_bar)

        act = QHBoxLayout()
        self.start_btn = QPushButton("Start Tracking")
        self.start_btn.clicked.connect(self.start_tracking)
        act.addWidget(self.start_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_tracking)
        self.cancel_btn.setEnabled(False)
        act.addWidget(self.cancel_btn)
        self.open_csv_btn = QPushButton("Open CSV Folder")
        self.open_csv_btn.clicked.connect(self.open_csv_folder)
        self.open_csv_btn.setEnabled(False)
        act.addWidget(self.open_csv_btn)
        self.progress_label = QLabel("Ready")
        act.addWidget(self.progress_label)
        act.addStretch(1)
        self.status_label = QLabel("")
        act.addWidget(self.status_label)
        body_layout.addLayout(act)

        self.header_mgr.add_copyright(self.theme_manager, outer)

        self._bridge = UIBridge()
        self._bridge.log.connect(self.log_message)
        self._bridge.progress.connect(self._on_progress)
        self._bridge.completed.connect(self.on_tracking_completed)
        self._bridge.error.connect(self.on_tracking_error)

        self._apply_theme()
        self.resize(1400, 900)
        QTimer.singleShot(0, self.showMaximized)

    @staticmethod
    def _label(text, bold=False):
        lbl = QLabel(text)
        if bold:
            lbl.setStyleSheet("font-weight: bold;")
        return lbl

    def _apply_theme(self):
        self.theme_manager.apply_theme_to_app(QApplication.instance())
        self.header_mgr.update_for_theme()

    def log_message(self, message: str, level: str = "info"):
        color = LOG_COLORS.get(level, LOG_COLORS["info"])
        ts = datetime.now().strftime("%H:%M:%S")
        self.output_log.appendHtml(f'<span style="color:{color}">[{ts}] {message}</span>')

    def _on_progress(self, current, total, tracking, result):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_label.setText(f"{current}/{total} - {tracking}")
        else:
            self.progress_label.setText(f"{tracking} - {result}")
        self.status_label.setText(f"Checking: {tracking}")
        if "Delivered" in result:
            self.log_message(f"  {tracking}: {result}", "success")
        elif "ERROR" in result:
            self.log_message(f"  {tracking}: {result}", "error")
        else:
            self.log_message(f"  {tracking}: {result}", "info")

    def queue_callback(self, callback_type: str, data):
        if callback_type == "log":
            self._bridge.log.emit(data, "info")
        elif callback_type == "progress":
            self._bridge.progress.emit(data.get("current", 0), data.get("total", 0),
                                        data.get("tracking", ""), data.get("result", ""))

    def paste_from_clipboard(self):
        try:
            text = QApplication.clipboard().text()
            self.input_text.insertPlainText(text)
            self.log_message("Text pasted from clipboard", "info")
        except Exception as e:
            self.log_message(f"Failed to paste: {e}", "error")

    def clear_input(self):
        self.input_text.setPlainText("")
        self.log_message("Input cleared", "info")

    def start_tracking(self):
        try:
            if self.is_processing:
                QMessageBox.warning(self, "Processing", "Already processing!")
                return
            input_content = self.input_text.toPlainText().strip()
            if not input_content:
                QMessageBox.warning(self, "No Input", "Please paste tracking numbers first!")
                return
            tracking_numbers = UPSTrackingBot.extract_tracking_numbers(input_content)
            if not tracking_numbers:
                QMessageBox.warning(self, "No Valid Numbers", "No valid UPS tracking numbers found!")
                return
            self.output_log.setPlainText("")
            self.progress_bar.setValue(0)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.output_file = os.path.join(os.path.expanduser("~/Downloads"),
                                             f"ups_tracking_results_{timestamp}.csv")
            self.is_processing = True
            self.start_btn.setEnabled(False)
            self.cancel_btn.setEnabled(True)
            self.paste_btn.setEnabled(False)
            self.clear_btn.setEnabled(False)
            self.open_csv_btn.setEnabled(False)
            self.log_message(f"Starting tracking for {len(tracking_numbers)} packages...", "info")
            self.log_message(f"Results: {self.output_file}", "info")
            self.status_label.setText(f"Processing {len(tracking_numbers)} numbers...")
            self.worker_thread = threading.Thread(target=self.run_tracking_worker,
                                                   args=(tracking_numbers,), daemon=True)
            self.worker_thread.start()
        except Exception as e:
            import traceback as _tb
            tb = _tb.format_exc()
            self.log_message(f"ERROR in start_tracking:\n{tb}", "error")
            QMessageBox.critical(self, "Error", f"An error occurred:\n\n{e}\n\n{tb}")

    def run_tracking_worker(self, tracking_numbers: List[str]):
        import traceback as _tb

        def _log(msg):
            print(f"[WORKER] {msg}", file=sys.stderr, flush=True)
            self._bridge.log.emit(msg, "info")

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
            self._bridge.completed.emit()
        except Exception as e:
            tb = _tb.format_exc()
            _log(f"ERROR: {e}")
            print(tb, file=sys.stderr, flush=True)
            self._bridge.error.emit(f"ERROR: {e}\n{tb}")
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
            self.log_message("Cancelling... Please wait", "warning")
            self.status_label.setText("Cancelling...")
            self.cancel_btn.setEnabled(False)
            if self.active_bot:
                self.active_bot.cancel()

    def on_tracking_completed(self):
        self.is_processing = False
        self.active_bot = None
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.paste_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        if self.output_file and os.path.exists(self.output_file):
            self.open_csv_btn.setEnabled(True)
        self.status_label.setText("Tracking completed")
        self.progress_label.setText("Complete!")
        self.log_message(f"Tracking complete! Results: {self.output_file}", "success")

    def on_tracking_error(self, error_msg: str):
        self.is_processing = False
        self.active_bot = None
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.paste_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        self.status_label.setText("Error occurred")
        self.log_message(error_msg, "error")
        if "\n" not in error_msg:
            QMessageBox.critical(self, "Tracking Error", f"An error occurred:\n\n{error_msg}")

    def open_csv_folder(self):
        if self.output_file and os.path.exists(self.output_file):
            folder = os.path.dirname(self.output_file)
            if sys.platform == "win32":
                os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.run(["open", folder])
            else:
                subprocess.run(["xdg-open", folder])
        else:
            QMessageBox.warning(self, "No File", "No results file found yet!")

    def closeEvent(self, event):
        if self.is_processing:
            self.log_message("Closing while tracking is in progress...", "warning")
        event.accept()


# ==========================================================
# ENTRY POINT
# ==========================================================
def _enable_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VDSDesk.UPSTrackingChecker")
        except Exception:
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _close_pyi_splash():
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except Exception:
        pass


def main():
    _enable_dpi_awareness()
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    _close_pyi_splash()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
