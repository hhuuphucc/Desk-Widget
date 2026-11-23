"""Lightweight floating E-Ink ESL desktop widget (Windows & macOS Intel/Apple Silicon)."""

from __future__ import annotations

from datetime import date, datetime
import json
import os
import plistlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser
from PIL import Image, ImageDraw, ImageTk
from dateutil import tz
import psutil

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    HWND_TOPMOST = wintypes.HWND(-1)
    HWND_NOTOPMOST = wintypes.HWND(-2)
    HWND_BOTTOM = wintypes.HWND(1)
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_NOACTIVATE = 0x0010
    GA_ROOT = 2

    _USER32 = ctypes.WinDLL("user32", use_last_error=True)
    _USER32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _USER32.GetAncestor.restype = wintypes.HWND
    _USER32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _USER32.SetWindowPos.restype = wintypes.BOOL
    _USER32.GetForegroundWindow.argtypes = []
    _USER32.GetForegroundWindow.restype = wintypes.HWND
else:
    _USER32 = None  # type: ignore[assignment]

from calendar_client import (
    EN_WEEKDAYS,
    CalendarClient,
    CalendarSummary,
    VN_WEEKDAYS,
    _get_tz,
    extract_meeting_links,
    format_event_time,
)
from renderer import (
    PAPER_SERIF_LIGHT,
    HitRegion,
    ThemePalette,
    export_esl_bitmap,
    format_temp,
    render_widget_with_hits,
    resolve_theme,
)
from system_client import SystemMonitor, SystemStats, top_cpu_processes, top_gpu_processes, top_ram_processes
from updater import APP_VERSION, GITHUB_REPO, UpdateCheckResult, check_for_update
from weather_client import (
    DayForecast,
    WeatherClient,
    WeatherData,
    day_abbr_for_lang,
    format_city_name,
    geocode_city,
    weather_desc_for_lang,
)


IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_DIR = str(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))


def _get_user_data_dir() -> str:
    """Store user config & custom assets locally in source mode, or in OS app-data when frozen (.exe/.app)."""
    if not IS_FROZEN:
        return os.path.dirname(os.path.abspath(__file__))
    if IS_WINDOWS:
        root = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(root, "desk-widget")
    if IS_MACOS:
        return os.path.join(os.path.expanduser("~"), "Library", "Application Support", "desk-widget")
    return os.path.join(os.path.expanduser("~"), ".config", "desk-widget")


BASE_DIR = _get_user_data_dir()
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
PID_PATH = os.path.join(BASE_DIR, "widget.pid")
ICON_PATH = os.path.join(RESOURCE_DIR, "app_icon.ico")
MAC_PLIST_LABEL = "com.deskwidget.app"
MAC_PLIST_PATH = os.path.expanduser(f"~/Library/LaunchAgents/{MAC_PLIST_LABEL}.plist")
TRANSPARENT_KEY = "systemTransparent" if IS_MACOS else "#010101"

DEFAULT_CONFIG = {
    "owner_name": "Desk Widget",
    "owner_align": "center",
    "bg_image": "",
    "logo_mode": "widget_bg",
    "logo_path": "",
    "calendars": [],
    "refresh_seconds": 60,
    "timezone": "Asia/Ho_Chi_Minh",
    "style": "serif",
    "theme": "auto",
    "temp_unit": "C",
    "language": "vi",
    "auto_start": True,
    "icon_path": ICON_PATH,
    "always_on_top": False,
    "scale": 1.0,
    "window_x": None,
    "window_y": None,
    "weather": {
        "auto_location": True,
        "city": "Hà Nội",
        "latitude": 21.0184,
        "longitude": 105.8461,
        "cache_minutes": 15,
    },
}


def _startup_shortcut_path() -> str:
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", "desk-widget.lnk")


def is_autostart_enabled() -> bool:
    if IS_WINDOWS:
        lnk = _startup_shortcut_path()
        return bool(lnk and os.path.exists(lnk))
    if IS_MACOS:
        return os.path.exists(MAC_PLIST_PATH)
    return False


def _active_icon_path(cfg: dict) -> str:
    p = str(cfg.get("icon_path") or "").strip()
    if p and os.path.exists(p):
        return p
    if os.path.exists(ICON_PATH):
        return ICON_PATH
    return ""


def _update_shortcuts_icon(ico_path: str) -> None:
    """Update Desktop and Startup shortcut icons (Windows only)."""
    if not IS_WINDOWS:
        return
    if IS_FROZEN:
        target_path = sys.executable
        arg_str = ""
        work_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        vbs_path = os.path.join(RESOURCE_DIR, "start_widget.vbs")
        target_path = "wscript.exe"
        arg_str = f'"{vbs_path}"'
        work_dir = BASE_DIR
    ps_cmd = (
        "$wsh = New-Object -ComObject WScript.Shell; "
        "$dirs = @([Environment]::GetFolderPath('Desktop'), (Join-Path $env:APPDATA 'Microsoft\\Windows\\Start Menu\\Programs\\Startup')); "
        "foreach ($d in $dirs) { "
        "  $oldLnk = Join-Path $d 'ESL Desk Widget.lnk'; "
        "  if (Test-Path $oldLnk) { Remove-Item $oldLnk -Force } "
        "  $lnk = Join-Path $d 'desk-widget.lnk'; "
        "  $sc = $wsh.CreateShortcut($lnk); "
        f"  $sc.TargetPath = '{target_path}'; "
        f"  $sc.Arguments = '{arg_str}'; "
        f"  $sc.WorkingDirectory = '{work_dir}'; "
        f"  $sc.IconLocation = '{ico_path},0'; "
        "  $sc.Description = 'desk-widget'; "
        "  $sc.Save() "
        "}"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], creationflags=flags, check=False)
    subprocess.run(["ie4uinit.exe", "-show"], creationflags=flags, check=False)


def _convert_image_to_ico(src_path: str, dst_ico: str) -> None:
    """Convert PNG/JPG/ICO to a crisp squircle-masked multi-size Windows .ico."""
    if src_path.lower().endswith(".ico"):
        import shutil
        shutil.copy2(src_path, dst_ico)
        return
    im = Image.open(src_path).convert("RGBA")
    side = min(im.width, im.height)
    left = (im.width - side) // 2
    top = (im.height - side) // 2
    im = im.crop((left, top, left + side, top + side)).resize((512, 512), Image.Resampling.LANCZOS)

    mask = Image.new("L", (1024, 1024), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((8, 8, 1015, 1015), radius=220, fill=255)
    mask = mask.resize((512, 512), Image.Resampling.LANCZOS)
    im.putalpha(mask)

    canvas = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    inner = im.resize((236, 236), Image.Resampling.LANCZOS)
    canvas.paste(inner, (10, 10), inner)
    canvas.save(dst_ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])


def set_autostart(enabled: bool, ico_path: str = "") -> None:
    """Create or remove auto-start entry (Windows Startup shortcut or macOS LaunchAgent)."""
    if IS_MACOS:
        if not enabled:
            try:
                subprocess.run(["launchctl", "unload", MAC_PLIST_PATH], check=False, stderr=subprocess.DEVNULL)
            except Exception:
                pass
            if os.path.exists(MAC_PLIST_PATH):
                try:
                    os.remove(MAC_PLIST_PATH)
                except Exception:
                    pass
            return

        os.makedirs(os.path.dirname(MAC_PLIST_PATH), exist_ok=True)
        prog_args = [sys.executable] if IS_FROZEN else [sys.executable, os.path.join(RESOURCE_DIR, "widget.py")]
        plist_data = {
            "Label": MAC_PLIST_LABEL,
            "ProgramArguments": prog_args,
            "WorkingDirectory": BASE_DIR,
            "RunAtLoad": True,
            "KeepAlive": False,
        }
        with open(MAC_PLIST_PATH, "wb") as f:
            plistlib.dump(plist_data, f)
        try:
            subprocess.run(["launchctl", "unload", MAC_PLIST_PATH], check=False, stderr=subprocess.DEVNULL)
            subprocess.run(["launchctl", "load", MAC_PLIST_PATH], check=False, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return

    if not IS_WINDOWS:
        return

    lnk = _startup_shortcut_path()
    if not lnk:
        return
    if not enabled:
        if os.path.exists(lnk):
            try:
                os.remove(lnk)
            except Exception:
                pass
        return

    os.makedirs(os.path.dirname(lnk), exist_ok=True)
    use_ico = ico_path if (ico_path and os.path.exists(ico_path)) else ICON_PATH
    if IS_FROZEN:
        target_path = sys.executable
        arg_str = ""
        work_dir = os.path.dirname(os.path.abspath(sys.executable))
    else:
        vbs_path = os.path.join(RESOURCE_DIR, "start_widget.vbs")
        target_path = "wscript.exe"
        arg_str = f'"{vbs_path}"'
        work_dir = BASE_DIR
    ps_cmd = (
        "$wsh = New-Object -ComObject WScript.Shell; "
        f"$sc = $wsh.CreateShortcut('{lnk}'); "
        f"$sc.TargetPath = '{target_path}'; "
        f"$sc.Arguments = '{arg_str}'; "
        f"$sc.WorkingDirectory = '{work_dir}'; "
        f"$sc.IconLocation = '{use_ico},0'; "
        "$sc.Description = 'desk-widget'; "
        "$sc.Save()"
    )
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], creationflags=flags, check=False)


def _enable_dpi_awareness() -> None:
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _set_window_icon(win: tk.Tk | tk.Toplevel, ico_path: str) -> None:
    """Apply window icon cleanly on both Windows (.ico) and macOS/Linux (iconphoto)."""
    if not ico_path or not os.path.exists(ico_path):
        return
    if IS_WINDOWS:
        try:
            win.iconbitmap(ico_path)
        except Exception:
            pass
        return
    try:
        img = Image.open(ico_path).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        win.iconphoto(True, photo)
        win._desk_icon_ref = photo  # type: ignore[attr-defined]
    except Exception:
        pass


def _replace_existing_instance() -> None:
    """Terminate any older running desk-widget instance so only one widget exists."""
    my_pid = os.getpid()
    skip_pids = {my_pid, os.getppid()}
    try:
        skip_pids.add(psutil.Process(os.getppid()).ppid())
    except Exception:
        pass
    exe_base = os.path.basename(sys.executable).lower()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            pid = proc.info["pid"]
            if pid in skip_pids:
                continue
            name = (proc.info["name"] or "").lower()
            cmd = " ".join(proc.info["cmdline"] or []).lower()
            is_source_dup = "python" in name and "widget.py" in cmd
            is_frozen_dup = IS_FROZEN and (name == exe_base or "desk-widget" in name)
            if is_source_dup or is_frozen_dup:
                proc.terminate()
                proc.wait(timeout=2)
        except Exception:
            pass
    try:
        os.makedirs(os.path.dirname(PID_PATH), exist_ok=True)
        with open(PID_PATH, "w", encoding="utf-8") as f:
            f.write(str(my_pid))
    except Exception:
        pass


def load_config() -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
            for k, v in user_cfg.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                elif k in cfg:
                    cfg[k] = v
            # Migrate legacy ical_urls if calendars is empty
            if not cfg.get("calendars") and user_cfg.get("ical_urls"):
                cfg["calendars"] = [
                    {"name": f"Lịch {i + 1}", "url": u, "enabled": True}
                    for i, u in enumerate(user_cfg["ical_urls"])
                    if str(u).strip()
                ]
        except Exception:
            pass
    return cfg


def save_config(cfg: dict) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def _prepare_for_tk(rgba_img: Image.Image, with_transparency: bool = True) -> Image.Image:
    """Flatten RGBA cleanly; preserve anti-aliasing when opaque, key-mask when beveled."""
    if not with_transparency:
        return rgba_img.convert("RGB")
    bg = Image.new("RGB", rgba_img.size, (1, 1, 1))
    alpha = rgba_img.getchannel("A")
    mask = alpha.point(lambda p: 255 if p >= 128 else 0)
    rgb = rgba_img.convert("RGB")
    bg.paste(rgb, (0, 0), mask)
    return bg


class ESLDeskWidget:
    def __init__(self) -> None:
        _enable_dpi_awareness()
        self.cfg = load_config()
        self.calendar_client = CalendarClient()
        self.weather_client = WeatherClient()
        self.sys_monitor = SystemMonitor()

        today = date.today()
        self.view_year: int = today.year
        self.view_month: int = today.month
        self.selected_date: date | None = None
        self.selected_weather_date: date | None = None

        self._last_cal: CalendarSummary | None = None
        self._last_weather: WeatherData | None = None
        self._last_stats: SystemStats | None = None
        self._active_theme: ThemePalette = PAPER_SERIF_LIGHT
        self._hit_map: list[HitRegion] = []
        self.last_screen: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._detail_win: tk.Toplevel | None = None
        self._detail_key: tuple[str, object] | None = None
        self._settings_win: tk.Toplevel | None = None
        self._last_fg: int | None = None

        self._refresh_lock = threading.Lock()
        self._drag_x = 0
        self._drag_y = 0
        self._moved = False

        self.root = tk.Tk()
        self.root.title("desk-widget")
        _set_window_icon(self.root, _active_icon_path(self.cfg))
        self.root.overrideredirect(True)
        self._mac_transparent = False
        if IS_MACOS:
            try:
                self.root.wm_attributes("-transparent", True)
                self.root.configure(bg=TRANSPARENT_KEY)
                self._mac_transparent = True
            except tk.TclError:
                self.root.configure(bg="#E6E6E2")
        else:
            self.root.configure(bg=TRANSPARENT_KEY)
            try:
                self.root.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
            except tk.TclError:
                pass
        self.root.wm_attributes("-topmost", bool(self.cfg.get("always_on_top", False)))

        lbl_bg = TRANSPARENT_KEY if (not IS_MACOS or self._mac_transparent) else "#E6E6E2"
        self.label = tk.Label(self.root, bg=lbl_bg, bd=0, highlightthickness=0, cursor="fleur")
        self.label.pack()

        self.label.bind("<ButtonPress-1>", self._on_drag_start)
        self.label.bind("<B1-Motion>", self._on_drag_motion)
        self.label.bind("<ButtonRelease-1>", self._on_drag_end)
        self.label.bind("<Motion>", self._on_hover)
        self.label.bind("<Double-Button-1>", self._on_double_click)
        self.label.bind("<Button-3>", self._show_menu)
        if IS_MACOS:
            self.label.bind("<Button-2>", self._show_menu)
            self.label.bind("<Control-Button-1>", self._show_menu)
        self.root.bind("<FocusOut>", lambda _e: self.root.after(40, self._apply_z_order))
        self.root.bind("<Leave>", lambda _e: self.root.after(150, self._apply_z_order))

        self._build_menu()
        if bool(self.cfg.get("auto_start", True)) and not is_autostart_enabled():
            set_autostart(True, _active_icon_path(self.cfg))
        self._render_initial_placeholder()
        self._position_window()
        self.root.after(120, self._apply_z_order)
        self.root.after(500, self._z_order_watchdog)

        self.trigger_refresh(force_weather=True)
        self._schedule_next_refresh()
        self._notified_update_ver: str | None = None
        self.root.after(5000, lambda: self._check_updates_async(silent=True))

    def _lang(self) -> str:
        return "en" if str(self.cfg.get("language", "vi")).strip().lower() == "en" else "vi"

    def _build_menu(self) -> None:
        is_en = self._lang() == "en"
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(
            label="Refresh now" if is_en else "Làm mới ngay",
            command=lambda: self.trigger_refresh(force_weather=True),
        )
        self.menu.add_command(
            label="Settings (Calendar .ics, Weather)..." if is_en else "Cài đặt (Lịch .ics, Thời tiết)...",
            command=self.open_settings,
        )
        self.menu.add_separator()

        self.var_topmost = tk.BooleanVar(value=bool(self.cfg.get("always_on_top", False)))
        self.menu.add_checkbutton(
            label="Always on top" if is_en else "Luôn nổi trên cùng",
            variable=self.var_topmost,
            command=self._toggle_topmost,
        )
        self.menu.add_command(
            label="Send behind windows" if is_en else "Ẩn ra sau các cửa sổ khác",
            command=self._send_to_back,
        )

        style_menu = tk.Menu(self.menu, tearoff=0)
        cur_style = str(self.cfg.get("style", "serif")).lower()
        if cur_style == "esl":
            cur_style = "sans"
        elif cur_style not in ("botanical", "serif", "sans"):
            cur_style = "serif"
        self.var_style = tk.StringVar(value=cur_style)
        style_menu.add_radiobutton(
            label="Botanical (Palatino + Candara)" if is_en else "Botanical (Palatino + Candara)",
            variable=self.var_style,
            value="botanical",
            command=self._on_style_change,
        )
        style_menu.add_radiobutton(
            label="Classic Serif (Palatino + Segoe UI)" if is_en else "Cổ điển · Chữ có chân (Palatino + Segoe UI)",
            variable=self.var_style,
            value="serif",
            command=self._on_style_change,
        )
        style_menu.add_radiobutton(
            label="Minimal Sans (Segoe UI)" if is_en else "Tối giản · Chữ không chân (Minimal Sans)",
            variable=self.var_style,
            value="sans",
            command=self._on_style_change,
        )
        self.menu.add_cascade(label="Visual style" if is_en else "Phong cách giao diện", menu=style_menu)

        theme_menu = tk.Menu(self.menu, tearoff=0)
        self.var_theme = tk.StringVar(value=str(self.cfg.get("theme", "auto")))
        theme_menu.add_radiobutton(
            label="Auto (Day light / Night dark)" if is_en else "Tự động (Sáng ngày / Tối đêm)",
            variable=self.var_theme,
            value="auto",
            command=self._on_theme_change,
        )
        theme_menu.add_radiobutton(
            label="Light (Light E-Ink)" if is_en else "Sáng (Light E-Ink)",
            variable=self.var_theme,
            value="light",
            command=self._on_theme_change,
        )
        theme_menu.add_radiobutton(
            label="Dark (Dark E-Ink)" if is_en else "Tối (Dark E-Ink)",
            variable=self.var_theme,
            value="dark",
            command=self._on_theme_change,
        )
        self.menu.add_cascade(label="E-Ink theme" if is_en else "Giao diện E-Ink", menu=theme_menu)

        align_menu = tk.Menu(self.menu, tearoff=0)
        self.var_align = tk.StringVar(value=str(self.cfg.get("owner_align", "center")))
        align_items = [("Left", "left"), ("Center", "center"), ("Right", "right")] if is_en else [("Trái", "left"), ("Giữa", "center"), ("Phải", "right")]
        for lbl, val in align_items:
            align_menu.add_radiobutton(
                label=lbl,
                variable=self.var_align,
                value=val,
                command=self._on_align_change,
            )
        self.menu.add_cascade(label="Title alignment" if is_en else "Vị trí tên tiêu đề", menu=align_menu)

        temp_menu = tk.Menu(self.menu, tearoff=0)
        self.var_temp_unit = tk.StringVar(value=str(self.cfg.get("temp_unit", "C")).upper())
        temp_menu.add_radiobutton(
            label="Celsius (°C)" if is_en else "Độ C (°C)",
            variable=self.var_temp_unit,
            value="C",
            command=self._on_temp_unit_change,
        )
        temp_menu.add_radiobutton(
            label="Fahrenheit (°F)" if is_en else "Độ F (°F)",
            variable=self.var_temp_unit,
            value="F",
            command=self._on_temp_unit_change,
        )
        self.menu.add_cascade(label="Temperature unit" if is_en else "Đơn vị nhiệt độ", menu=temp_menu)

        lang_menu = tk.Menu(self.menu, tearoff=0)
        self.var_lang = tk.StringVar(value=self._lang())
        lang_menu.add_radiobutton(
            label="Tiếng Việt",
            variable=self.var_lang,
            value="vi",
            command=self._on_language_change,
        )
        lang_menu.add_radiobutton(
            label="English",
            variable=self.var_lang,
            value="en",
            command=self._on_language_change,
        )
        self.menu.add_cascade(label="Language / Ngôn ngữ", menu=lang_menu)

        logo_menu = tk.Menu(self.menu, tearoff=0)
        raw_logo_mode = str(self.cfg.get("logo_mode", "widget_bg")).lower()
        if raw_logo_mode == "wallpaper":
            raw_logo_mode = "widget_bg"
        self.var_logo_mode = tk.StringVar(value=raw_logo_mode)
        logo_menu.add_command(
            label="Change widget background (syncs circle logo)..." if is_en else "Đổi ảnh nền widget (đồng bộ icon tròn)...",
            command=self._choose_widget_bg,
        )
        logo_menu.add_command(
            label="Reset default background" if is_en else "Khôi phục nền mặc định",
            command=self._reset_widget_bg,
        )
        logo_menu.add_separator()
        logo_menu.add_radiobutton(
            label="Header icon: Sync with widget background (circle)" if is_en else "Icon cạnh tên: Đồng bộ nền widget (tròn)",
            variable=self.var_logo_mode,
            value="widget_bg",
            command=self._on_logo_mode_change,
        )
        logo_menu.add_radiobutton(
            label="Header icon: Custom image (circle)" if is_en else "Icon cạnh tên: Dùng ảnh riêng (tròn)",
            variable=self.var_logo_mode,
            value="custom",
            command=self._on_logo_mode_change,
        )
        logo_menu.add_command(
            label="Choose custom header icon..." if is_en else "Chọn ảnh icon riêng...",
            command=self._choose_custom_logo,
        )
        logo_menu.add_radiobutton(
            label="Hide header icon" if is_en else "Ẩn icon cạnh tên",
            variable=self.var_logo_mode,
            value="none",
            command=self._on_logo_mode_change,
        )
        self.menu.add_cascade(label="Background & Logo" if is_en else "Nền & Logo widget", menu=logo_menu)

        self.var_autostart = tk.BooleanVar(value=is_autostart_enabled())
        if is_en:
            autostart_lbl = "Launch on macOS login" if IS_MACOS else "Start with Windows"
        else:
            autostart_lbl = "Tự khởi động cùng macOS" if IS_MACOS else "Tự khởi động cùng Windows"
        self.menu.add_checkbutton(
            label=autostart_lbl,
            variable=self.var_autostart,
            command=self._toggle_autostart,
        )

        self.menu.add_command(label="Change icon / logo..." if is_en else "Đổi icon / logo...", command=self._change_icon)
        self.menu.add_command(label="Export ESL (296×128 PNG)..." if is_en else "Xuất ảnh ESL (296×128 PNG)...", command=self._export_esl)
        upd_lbl = f"Check for updates (v{APP_VERSION})..." if is_en else f"Kiểm tra cập nhật (v{APP_VERSION})..."
        self.menu.add_command(label=upd_lbl, command=lambda: self._check_updates_async(silent=False))
        self.menu.add_separator()
        self.menu.add_command(label="Quit" if is_en else "Thoát", command=self.quit)

    def _active_now(self) -> datetime:
        tz_name = str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))
        return datetime.now(_get_tz(tz_name))

    def _resolve_widget_bg_path(self) -> str | None:
        bp = str(self.cfg.get("bg_image") or "").strip()
        return bp if (bp and os.path.exists(bp)) else None

    def _resolve_header_logo_path(self) -> str | None:
        mode = str(self.cfg.get("logo_mode", "widget_bg")).strip().lower()
        if mode == "none":
            return None
        if mode == "custom":
            lp = str(self.cfg.get("logo_path") or "").strip()
            return lp if (lp and os.path.exists(lp)) else None
        return "__widget_bg__"

    def _render_initial_placeholder(self) -> None:
        now = self._active_now()
        has_cals = any(c.get("enabled", True) and str(c.get("url", "")).strip() for c in self.cfg.get("calendars", []))
        cal = CalendarSummary(events_today=[], upcoming_events=[], done_count=0, has_urls=has_cals)
        w_cfg = self.cfg["weather"]
        weather = WeatherData(
            city=w_cfg["city"],
            current_temp=0,
            current_desc="Đang tải...",
            current_icon="cloud",
            today_min=0,
            today_max=0,
            today_rain_prob=0,
            weekly=[],
            fetched_at=now,
        )
        self._last_cal = cal
        self._last_weather = weather
        self._last_stats = self.sys_monitor.read(include_cpu_temp=False)
        self._redraw_from_state(now=now)

    def _redraw_from_state(self, now: datetime | None = None) -> None:
        if self._last_cal is None or self._last_weather is None or self._last_stats is None:
            return
        if now is None:
            now = self._active_now()
        img, hits, screen, th = render_widget_with_hits(
            self._last_cal,
            self._last_weather,
            self._last_stats,
            owner_name=str(self.cfg.get("owner_name", "Desk Widget")),
            owner_align=str(self.cfg.get("owner_align", "center")),
            theme_mode=str(self.cfg.get("theme", "auto")),
            style=str(self.cfg.get("style", "serif")),
            temp_unit=str(self.cfg.get("temp_unit", "C")),
            lang=self._lang(),
            logo_path=self._resolve_header_logo_path(),
            bg_path=self._resolve_widget_bg_path(),
            show_esl_frame=False,
            scale=float(self.cfg.get("scale", 1.0)),
            now=now,
            view_year=self.view_year,
            view_month=self.view_month,
            selected_date=self.selected_date,
            selected_weather_date=self.selected_weather_date,
        )
        self._active_theme = th
        self._hit_map = hits
        self.last_screen = screen
        self._apply_image(img)
        if not self.cfg.get("always_on_top", False):
            self.root.after(20, self._apply_z_order)

    def _position_window(self) -> None:
        self.root.update_idletasks()
        w = self.root.winfo_reqwidth()
        h = self.root.winfo_reqheight()
        x = self.cfg.get("window_x")
        y = self.cfg.get("window_y")
        if x is None or y is None:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x = max(10, sw - w - 24)
            y = max(38 if IS_MACOS else 10, sh - h - 64)
        self.root.geometry(f"+{int(x)}+{int(y)}")

    def _apply_image(self, rgba_img: Image.Image) -> None:
        img_for_tk = rgba_img if (IS_MACOS and self._mac_transparent) else _prepare_for_tk(rgba_img, with_transparency=False)
        new_photo = ImageTk.PhotoImage(img_for_tk)
        self.label.configure(image=new_photo)
        self._photo = new_photo

    def _find_hit(self, x: int, y: int) -> HitRegion | None:
        for h in self._hit_map:
            if h.contains(x, y):
                return h
        return None

    def _on_hover(self, event: tk.Event) -> None:
        hit = self._find_hit(event.x, event.y)
        self.label.configure(cursor="hand2" if hit else "fleur")

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y
        self._moved = False

    def _on_drag_motion(self, event: tk.Event) -> None:
        dx = event.x - self._drag_x
        dy = event.y - self._drag_y
        if abs(dx) > 3 or abs(dy) > 3:
            self._moved = True
        nx = self.root.winfo_x() + dx
        ny = self.root.winfo_y() + dy
        self.root.geometry(f"+{nx}+{ny}")

    def _on_drag_end(self, event: tk.Event) -> None:
        if self._moved:
            self.cfg["window_x"] = self.root.winfo_x()
            self.cfg["window_y"] = self.root.winfo_y()
            save_config(self.cfg)
            return

        hit = self._find_hit(event.x, event.y)
        if hit is not None:
            self._handle_hit(hit)

    def _on_double_click(self, event: tk.Event) -> None:
        hit = self._find_hit(event.x, event.y)
        if hit is not None:
            return
        self.open_settings()

    def _handle_hit(self, hit: HitRegion) -> None:
        tz_name = self.cfg.get("timezone", "Asia/Ho_Chi_Minh")
        if hit.action == "select_date" and isinstance(hit.payload, date):
            clicked: date = hit.payload
            if (
                self._detail_win is not None
                and self._detail_win.winfo_exists()
                and self._detail_key == ("cal", clicked)
            ):
                self._close_detail_popup()
                self.selected_date = None
                self._redraw_from_state()
                return

            self.selected_weather_date = None
            self.selected_date = clicked
            if clicked.year != self.view_year or clicked.month != self.view_month:
                self.view_year = clicked.year
                self.view_month = clicked.month
                self._last_cal = self.calendar_client.render_month_from_cache(
                    tz_name, self.view_year, self.view_month
                )
            self._redraw_from_state()
            self._open_day_detail_popup(clicked)
        elif hit.action == "select_weather_day" and isinstance(hit.payload, DayForecast):
            fc: DayForecast = hit.payload
            if (
                self._detail_win is not None
                and self._detail_win.winfo_exists()
                and self._detail_key == ("weather", fc.date_obj)
            ):
                self._close_detail_popup()
                self.selected_weather_date = None
                self._redraw_from_state()
                return

            self.selected_date = None
            self.selected_weather_date = fc.date_obj
            self._redraw_from_state()
            self._open_weather_detail_popup(fc)
        elif hit.action == "inspect_system" and isinstance(hit.payload, str):
            kind = hit.payload
            if (
                self._detail_win is not None
                and self._detail_win.winfo_exists()
                and self._detail_key == ("sys", kind)
            ):
                self._close_detail_popup()
                return
            self.selected_date = None
            self.selected_weather_date = None
            self._redraw_from_state()
            self._open_system_detail_popup(kind)
        elif hit.action == "prev_month":
            if self.view_month == 1:
                self.view_month = 12
                self.view_year -= 1
            else:
                self.view_month -= 1
            self._last_cal = self.calendar_client.render_month_from_cache(tz_name, self.view_year, self.view_month)
            self._redraw_from_state()
        elif hit.action == "next_month":
            if self.view_month == 12:
                self.view_month = 1
                self.view_year += 1
            else:
                self.view_month += 1
            self._last_cal = self.calendar_client.render_month_from_cache(tz_name, self.view_year, self.view_month)
            self._redraw_from_state()
        elif hit.action == "toggle_temp_unit":
            cur_u = str(self.cfg.get("temp_unit", "C")).upper()
            new_u = "F" if cur_u == "C" else "C"
            self.cfg["temp_unit"] = new_u
            if hasattr(self, "var_temp_unit"):
                self.var_temp_unit.set(new_u)
            save_config(self.cfg)
            self._redraw_from_state()
            if (
                self._detail_win is not None
                and self._detail_win.winfo_exists()
                and self._detail_key is not None
                and self._detail_key[0] == "weather"
                and self._last_weather is not None
            ):
                target_d = self._detail_key[1]
                fc_match = next((d for d in self._last_weather.weekly if d.date_obj == target_d), None)
                if fc_match is not None:
                    self._open_weather_detail_popup(fc_match)
        elif hit.action == "open_url" and isinstance(hit.payload, str):
            webbrowser.open(hit.payload)
        elif hit.action == "goto_today":
            today = self._active_now().date()
            self.view_year = today.year
            self.view_month = today.month
            self.selected_date = today
            self.selected_weather_date = None
            self._last_cal = self.calendar_client.render_month_from_cache(tz_name, self.view_year, self.view_month)
            self._redraw_from_state()
            self._open_day_detail_popup(today)

    def _close_detail_popup(self) -> None:
        if self._detail_win is not None and self._detail_win.winfo_exists():
            self._detail_win.destroy()
        self._detail_win = None
        self._detail_key = None

    def _create_popup_window(self, title: str, pop_w: int = 360, pop_h: int = 270) -> tk.Toplevel:
        self._close_detail_popup()
        th = self._active_theme
        win = tk.Toplevel(self.root)
        self._detail_win = win
        win.title(title)
        _set_window_icon(win, _active_icon_path(self.cfg))
        win.configure(bg=th.paper, highlightbackground=th.ink, highlightthickness=1)
        win.resizable(False, False)

        wx, wy = self.root.winfo_x(), self.root.winfo_y()
        ww, wh = self.root.winfo_width(), self.root.winfo_height()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()

        px = max(10, min(wx + ww - pop_w, sw - pop_w - 12))
        py = wy + wh + 6
        if py + pop_h > sh - 44:
            py = max(10, wy - pop_h - 6)
        win.geometry(f"{pop_w}x{pop_h}+{px}+{py}")
        win.bind("<Escape>", lambda _e: self._close_detail_popup())
        return win

    def _open_day_detail_popup(self, target_date: date) -> None:
        th = self._active_theme
        lang = self._lang()
        is_en = lang == "en"
        wd = (EN_WEEKDAYS if is_en else VN_WEEKDAYS)[target_date.weekday()]
        title_pfx = "Events" if is_en else "Chi tiết lịch"
        win = self._create_popup_window(f"{title_pfx} — {wd} {target_date.strftime('%d/%m/%Y')}", 370, 280)
        self._detail_key = ("cal", target_date)

        header = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"{wd}, {target_date.strftime('%d/%m/%Y')}",
            font=("Segoe UI", 11, "bold"),
            fg=th.accent,
            bg=th.paper,
        ).pack(side="left")

        events = (self._last_cal.events_by_date.get(target_date, []) if self._last_cal else [])
        ev_cnt_txt = f"{len(events)} event(s)" if is_en else f"{len(events)} sự kiện"
        tk.Label(
            header,
            text=ev_cnt_txt,
            font=("Segoe UI", 9),
            fg=th.muted,
            bg=th.paper,
        ).pack(side="right")

        tk.Frame(win, bg=th.ink, height=1).pack(fill="x", padx=12)

        body = tk.Text(
            win,
            wrap="word",
            bg=th.paper,
            fg=th.ink,
            font=("Segoe UI", 10),
            bd=0,
            padx=12,
            pady=8,
            highlightthickness=0,
        )
        body.pack(fill="both", expand=True)
        body.tag_configure("time", font=("Segoe UI", 10, "bold"), foreground=th.accent)
        body.tag_configure("title", font=("Segoe UI", 10, "bold"), foreground=th.ink)
        body.tag_configure("meta", font=("Segoe UI", 9), foreground=th.muted)

        if not events:
            body.insert("end", "No events on this day.\n" if is_en else "Không có sự kiện nào trong ngày này.\n", "meta")
        else:
            for idx, ev in enumerate(events):
                if idx > 0:
                    body.insert("end", "\n" + "─" * 34 + "\n\n", "meta")
                cal_tag = f"[{ev.calendar_name}] " if ev.calendar_name else ""
                body.insert("end", f"{format_event_time(ev, lang, with_range=True)}  {cal_tag}", "time")
                body.insert("end", f"{ev.title}\n", "title")
                links = extract_meeting_links(ev, include_maps_for_address=True, lang=lang)
                if links:
                    for row_i in range(0, len(links), 3):
                        btn_bar = tk.Frame(body, bg=th.paper, pady=2)
                        for lbl, url in links[row_i:row_i + 3]:
                            tk.Button(
                                btn_bar,
                                text=lbl,
                                command=lambda u=url: webbrowser.open(u),
                                bg=th.accent,
                                fg="#FFFFFF",
                                activebackground=th.accent_dark,
                                activeforeground="#FFFFFF",
                                font=("Segoe UI", 9, "bold"),
                                bd=0,
                                padx=9,
                                pady=2,
                                cursor="hand2",
                            ).pack(side="left", padx=(0, 6))
                        body.window_create("end", window=btn_bar)
                        body.insert("end", "\n")
                if ev.location:
                    loc_lbl = "Location:" if is_en else "Địa điểm:"
                    body.insert("end", f"{loc_lbl} {ev.location}\n", "meta")
                if ev.description:
                    body.insert("end", f"{ev.description.strip()}\n", "meta")

        body.configure(state="disabled")

    def _open_weather_detail_popup(self, fc: DayForecast) -> None:
        th = self._active_theme
        lang = self._lang()
        is_en = lang == "en"
        city = format_city_name(self._last_weather.city if self._last_weather else "", lang)
        wd_disp = day_abbr_for_lang(fc.date_obj, fc.weekday, lang)
        desc_disp = weather_desc_for_lang(fc.weather_code, fc.desc, lang)
        w_title_pfx = "Weather" if is_en else "Thời tiết"
        win = self._create_popup_window(
            f"{w_title_pfx} {city} — {wd_disp} {fc.date_obj.strftime('%d/%m/%Y')}", 350, 260
        )
        self._detail_key = ("weather", fc.date_obj)

        header = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"{city} · {wd_disp} {fc.date_obj.strftime('%d/%m')}",
            font=("Segoe UI", 11, "bold"),
            fg=th.accent,
            bg=th.paper,
        ).pack(side="left")
        tk.Label(
            header,
            text=desc_disp,
            font=("Segoe UI", 10, "bold"),
            fg=th.ink,
            bg=th.paper,
        ).pack(side="right")

        tk.Frame(win, bg=th.ink, height=1).pack(fill="x", padx=12)

        body = tk.Text(
            win,
            wrap="word",
            bg=th.paper,
            fg=th.ink,
            font=("Segoe UI", 10),
            bd=0,
            padx=12,
            pady=8,
            highlightthickness=0,
        )
        body.pack(fill="both", expand=True)
        body.tag_configure("k", font=("Segoe UI", 10, "bold"), foreground=th.ink)
        body.tag_configure("r", font=("Segoe UI", 10, "bold"), foreground=th.accent)
        body.tag_configure("m", font=("Segoe UI", 9), foreground=th.muted)

        unit = str(self.cfg.get("temp_unit", "C")).upper()
        body.insert("end", "Temperature: " if is_en else "Nhiệt độ: ", "k")
        body.insert("end", f"{format_temp(fc.temp_min, unit)} – {format_temp(fc.temp_max, unit)}\n", "r")
        body.insert("end", "Rain chance: " if is_en else "Khả năng mưa: ", "k")
        rain_desc = f"{fc.rain_prob}%  (~{fc.rain_sum_mm} mm)\n" if is_en else f"{fc.rain_prob}%  (lượng mưa ~{fc.rain_sum_mm} mm)\n"
        body.insert("end", rain_desc, "m")
        body.insert("end", "Max wind: " if is_en else "Gió tối đa: ", "k")
        body.insert("end", f"{fc.wind_max_kmh} km/h   ·   ", "m")
        body.insert("end", "UV Index: " if is_en else "Chỉ số UV: ", "k")
        body.insert("end", f"{fc.uv_max}\n", "m")

        if fc.date_obj == self._active_now().date() and self._last_weather:
            cur_line = (
                f"Now: {format_temp(self._last_weather.current_temp, unit)} · Humidity {self._last_weather.current_humidity}% · Wind {self._last_weather.current_wind} km/h\n"
                if is_en
                else f"Hiện tại: {format_temp(self._last_weather.current_temp, unit)} · Độ ẩm {self._last_weather.current_humidity}% · Gió {self._last_weather.current_wind} km/h\n"
            )
            body.insert("end", cur_line, "m")

        if fc.hourly_slots:
            body.insert("end", "\nHourly forecast:\n" if is_en else "\nTheo khung giờ trong ngày:\n", "k")
            for idx_h, (hr, temp_h, desc_h, rain_h) in enumerate(fc.hourly_slots):
                hc = fc.hourly_codes[idx_h] if idx_h < len(fc.hourly_codes) else -1
                d_h = weather_desc_for_lang(hc, desc_h, lang)
                rain_w = "rain" if is_en else "mưa"
                body.insert("end", f"  • {hr}   {format_temp(temp_h, unit)}   {d_h}   ({rain_w} {rain_h}%)\n", "m")

        body.configure(state="disabled")

    def _open_system_detail_popup(self, kind: str) -> None:
        th = self._active_theme
        is_en = self._lang() == "en"
        titles = (
            {"ram": "Top RAM Usage", "cpu": "Top CPU Usage", "gpu": "GPU & Graphics Usage"}
            if is_en
            else {"ram": "Ứng dụng đang dùng RAM", "cpu": "Ứng dụng đang dùng CPU", "gpu": "Ứng dụng đang dùng GPU"}
        )
        win = self._create_popup_window(titles.get(kind, "System" if is_en else "Tiến trình hệ thống"), 390, 300)
        self._detail_key = ("sys", kind)

        header = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        header.pack(fill="x")
        lbl_title = tk.Label(
            header,
            text=titles.get(kind, "System" if is_en else "Hệ thống"),
            font=("Segoe UI", 11, "bold"),
            fg=th.accent,
            bg=th.paper,
        )
        lbl_title.pack(side="left")

        btn_refresh = ttk.Button(header, text="Refresh" if is_en else "Làm mới", width=9)
        btn_refresh.pack(side="right")

        tk.Frame(win, bg=th.ink, height=1).pack(fill="x", padx=12)

        body = tk.Text(
            win,
            wrap="word",
            bg=th.paper,
            fg=th.ink,
            font=("Consolas", 9),
            bd=0,
            padx=12,
            pady=8,
            highlightthickness=0,
        )
        body.pack(fill="both", expand=True)
        body.tag_configure("hdr", font=("Segoe UI", 9, "bold"), foreground=th.accent)
        body.tag_configure("note", font=("Segoe UI", 9), foreground=th.muted)

        def _load() -> None:
            body.configure(state="normal")
            body.delete("1.0", "end")
            body.insert("end", "Đang quét các ứng dụng đang chạy...\n", "note")
            body.configure(state="disabled")
            btn_refresh.configure(state="disabled")

            def _worker() -> None:
                if kind == "ram":
                    rows = top_ram_processes(12)
                    extra = None
                elif kind == "cpu":
                    rows = top_cpu_processes(0.8, 12)
                    extra = None
                else:
                    nv_apps, win_apps = top_gpu_processes(12)
                    rows = nv_apps
                    extra = win_apps

                def _render_rows() -> None:
                    if not win.winfo_exists():
                        return
                    btn_refresh.configure(state="normal")
                    body.configure(state="normal")
                    body.delete("1.0", "end")

                    if kind == "ram":
                        body.insert("end", f"{'Ứng dụng':<24} {'RAM':>9}  {'%':>5}\n", "hdr")
                        for r in rows:
                            cnt = f" ({r['count']})" if r["count"] > 1 else ""
                            name = (r["name"][:20] + cnt)[:24]
                            val = f"{r['mb']/1024:.2f} GB" if r["mb"] >= 1024 else f"{r['mb']:.0f} MB"
                            body.insert("end", f"{name:<24} {val:>9}  {r['pct']:>4.1f}%\n")
                    elif kind == "cpu":
                        body.insert("end", f"{'Ứng dụng':<26} {'CPU %':>8}\n", "hdr")
                        if not rows:
                            body.insert("end", "Các tiến trình đều đang nhàn (< 0.1%).\n", "note")
                        for r in rows:
                            cnt = f" ({r['count']})" if r["count"] > 1 else ""
                            name = (r["name"][:22] + cnt)[:26]
                            body.insert("end", f"{name:<26} {r['pct']:>7.1f}%\n")
                    else:
                        gpu_nm = self._last_stats.gpu_name if self._last_stats else "GPU"
                        if IS_WINDOWS:
                            body.insert("end", f"1) Card rời ({gpu_nm}):\n", "hdr")
                            if not rows:
                                body.insert("end", "  Đang nghỉ (0 ứng dụng dùng GPU rời).\n", "note")
                            else:
                                for r in rows:
                                    body.insert(
                                        "end",
                                        f"  {r['name'][:20]:<20} {r['pct']:>3}%  {r['vram_mb']:>4} MB ({r['type']})\n",
                                    )
                            body.insert("end", "\n2) Toàn bộ GPU Windows (gồm onboard):\n", "hdr")
                            if not extra:
                                body.insert("end", "  Không ghi nhận ứng dụng dùng GPU đáng kể.\n", "note")
                            else:
                                for r in extra:
                                    body.insert("end", f"  {r['name'][:26]:<26} {r['pct']:>5.1f}%\n")
                        else:
                            gpu_u = self._last_stats.gpu_pct if self._last_stats else None
                            u_str = f"{gpu_u}%" if gpu_u is not None else "N/A"
                            body.insert("end", f"1) Chip đồ họa macOS ({gpu_nm}): {u_str}\n", "hdr")
                            body.insert("end", "\n2) Tiến trình tiêu thụ CPU/đồ họa cao:\n", "hdr")
                            if not extra:
                                body.insert("end", "  Các tiến trình đang nhàn (< 0.1%).\n", "note")
                            else:
                                for r in extra:
                                    body.insert("end", f"  {r['name'][:26]:<26} {r['pct']:>5.1f}%\n")

                    body.configure(state="disabled")

                self.root.after(0, _render_rows)

            threading.Thread(target=_worker, daemon=True).start()

        btn_refresh.configure(command=_load)
        _load()

    def _show_menu(self, event: tk.Event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _apply_z_order(self) -> None:
        """Keep widget behind open windows when always_on_top is False."""
        topmost = bool(self.cfg.get("always_on_top", False))
        try:
            self.root.wm_attributes("-topmost", topmost)
        except Exception:
            pass
        if not IS_WINDOWS or _USER32 is None:
            if not topmost:
                has_popup = (
                    (self._detail_win is not None and self._detail_win.winfo_exists())
                    or (self._settings_win is not None and self._settings_win.winfo_exists())
                )
                if not has_popup:
                    try:
                        self.root.lower()
                    except Exception:
                        pass
            return
        try:
            hwnd = _USER32.GetAncestor(self.root.winfo_id(), GA_ROOT) or wintypes.HWND(self.root.winfo_id())
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            if topmost:
                _USER32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags)
            else:
                _USER32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
                fg = _USER32.GetForegroundWindow()
                detail_hwnd = (
                    _USER32.GetAncestor(self._detail_win.winfo_id(), GA_ROOT)
                    if (self._detail_win is not None and self._detail_win.winfo_exists())
                    else None
                )
                settings_hwnd = (
                    _USER32.GetAncestor(self._settings_win.winfo_id(), GA_ROOT)
                    if (self._settings_win is not None and self._settings_win.winfo_exists())
                    else None
                )
                if fg != hwnd and fg != detail_hwnd and fg != settings_hwnd:
                    _USER32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
        except Exception:
            pass

    def _z_order_watchdog(self) -> None:
        """Push widget behind other apps whenever foreground focus changes away."""
        if not IS_WINDOWS or _USER32 is None:
            return
        try:
            if not self.cfg.get("always_on_top", False):
                fg = _USER32.GetForegroundWindow()
                if fg != self._last_fg:
                    self._last_fg = fg
                    self._apply_z_order()
        except Exception:
            pass
        self.root.after(800, self._z_order_watchdog)

    def _toggle_topmost(self) -> None:
        val = bool(self.var_topmost.get())
        self.cfg["always_on_top"] = val
        save_config(self.cfg)
        self._apply_z_order()

    def _send_to_back(self) -> None:
        self.cfg["always_on_top"] = False
        self.var_topmost.set(False)
        save_config(self.cfg)
        if not IS_WINDOWS or _USER32 is None:
            try:
                self.root.wm_attributes("-topmost", False)
            except Exception:
                pass
            self.root.lower()
            return
        try:
            hwnd = _USER32.GetAncestor(self.root.winfo_id(), GA_ROOT) or wintypes.HWND(self.root.winfo_id())
            flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
            self.root.wm_attributes("-topmost", False)
            _USER32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)
            _USER32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0, flags)
        except Exception:
            self.root.lower()

    def _on_style_change(self) -> None:
        self.cfg["style"] = self.var_style.get()
        save_config(self.cfg)
        self._redraw_from_state()

    def _on_theme_change(self) -> None:
        self.cfg["theme"] = self.var_theme.get()
        save_config(self.cfg)
        self._redraw_from_state()

    def _on_align_change(self) -> None:
        self.cfg["owner_align"] = self.var_align.get()
        save_config(self.cfg)
        self._redraw_from_state()

    def _on_temp_unit_change(self) -> None:
        self.cfg["temp_unit"] = str(self.var_temp_unit.get() or "C").upper()
        save_config(self.cfg)
        self._redraw_from_state()
        if (
            self._detail_win is not None
            and self._detail_win.winfo_exists()
            and self._detail_key is not None
            and self._detail_key[0] == "weather"
            and self._last_weather is not None
        ):
            target_d = self._detail_key[1]
            fc_match = next((d for d in self._last_weather.weekly if d.date_obj == target_d), None)
            if fc_match is not None:
                self._open_weather_detail_popup(fc_match)

    def _on_language_change(self) -> None:
        self.cfg["language"] = "en" if str(self.var_lang.get()).lower() == "en" else "vi"
        save_config(self.cfg)
        self._build_menu()
        self._redraw_from_state()

    def _choose_widget_bg(self) -> None:
        is_en = self._lang() == "en"
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose widget background image" if is_en else "Chọn ảnh nền widget (đồng bộ icon tròn)",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")],
        )
        if not path:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_bg = os.path.join(BASE_DIR, f"custom_bg_{stamp}.png")
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            Image.open(path).convert("RGBA").save(dst_bg, format="PNG")
            self.cfg["bg_image"] = dst_bg
            self.cfg["logo_mode"] = "widget_bg"
            if hasattr(self, "var_logo_mode"):
                self.var_logo_mode.set("widget_bg")
            save_config(self.cfg)
            self._redraw_from_state()
        except Exception as exc:
            messagebox.showerror(
                "Background error" if is_en else "Lỗi đổi ảnh nền",
                f"{exc}",
                parent=self.root,
            )

    def _reset_widget_bg(self) -> None:
        self.cfg["bg_image"] = ""
        self.cfg["logo_mode"] = "widget_bg"
        if hasattr(self, "var_logo_mode"):
            self.var_logo_mode.set("widget_bg")
        save_config(self.cfg)
        self._redraw_from_state()

    def _on_logo_mode_change(self) -> None:
        mode = str(self.var_logo_mode.get() or "widget_bg").strip().lower()
        if mode == "custom":
            lp = str(self.cfg.get("logo_path") or "").strip()
            if not lp or not os.path.exists(lp):
                self._choose_custom_logo()
                return
        self.cfg["logo_mode"] = mode
        save_config(self.cfg)
        self._redraw_from_state()

    def _choose_custom_logo(self) -> None:
        is_en = self._lang() == "en"
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Choose header logo image" if is_en else "Chọn ảnh logo tiêu đề",
            filetypes=[("Images", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("All files", "*.*")],
        )
        if not path:
            if hasattr(self, "var_logo_mode"):
                self.var_logo_mode.set(str(self.cfg.get("logo_mode", "wallpaper")).lower())
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_logo = os.path.join(BASE_DIR, f"custom_logo_{stamp}.png")
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            Image.open(path).convert("RGBA").save(dst_logo, format="PNG")
            self.cfg["logo_path"] = dst_logo
            self.cfg["logo_mode"] = "custom"
            if hasattr(self, "var_logo_mode"):
                self.var_logo_mode.set("custom")
            save_config(self.cfg)
            self._redraw_from_state()
        except Exception as exc:
            messagebox.showerror(
                "Logo error" if is_en else "Lỗi chọn logo",
                f"{exc}",
                parent=self.root,
            )

    def _toggle_autostart(self) -> None:
        val = bool(self.var_autostart.get())
        self.cfg["auto_start"] = val
        save_config(self.cfg)
        set_autostart(val, _active_icon_path(self.cfg))

    def _change_icon(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Chọn ảnh logo / icon mới",
            filetypes=[("Image / Icon", "*.png;*.jpg;*.jpeg;*.webp;*.ico"), ("All files", "*.*")],
        )
        if not path:
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst_ico = os.path.join(BASE_DIR, f"custom_icon_{stamp}.ico")
        try:
            os.makedirs(BASE_DIR, exist_ok=True)
            _convert_image_to_ico(path, dst_ico)
            self.cfg["icon_path"] = dst_ico
            save_config(self.cfg)
            _set_window_icon(self.root, dst_ico)
            _update_shortcuts_icon(dst_ico)
            messagebox.showinfo(
                "Đã đổi icon",
                "Đã cập nhật icon mới cho widget!" if not IS_WINDOWS else "Đã cập nhật icon mới cho widget và shortcut Desktop!\n(Nếu Desktop chưa đổi ngay, bấm F5 ngoài Desktop.)",
                parent=self.root,
            )
        except Exception as exc:
            messagebox.showerror("Lỗi đổi icon", f"Không chuyển được ảnh thành icon:\n{exc}", parent=self.root)

    def _export_esl(self) -> None:
        if self.last_screen is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Xuất ảnh chuẩn ESL 296×128",
            defaultextension=".png",
            initialfile="esl_296x128.png",
            filetypes=[("PNG Image", "*.png"), ("BMP Image", "*.bmp")],
        )
        if path:
            export_esl_bitmap(self.last_screen, path, target_size=(296, 128))
            messagebox.showinfo("Hoàn tất", f"Đã lưu ảnh ESL tại:\n{path}", parent=self.root)

    def _check_updates_async(self, silent: bool = False) -> None:
        repo = str(self.cfg.get("update_repo") or GITHUB_REPO or "").strip()
        if silent and not repo:
            return

        def _worker() -> None:
            res = check_for_update(repo=repo, current_version=APP_VERSION)
            self.root.after(0, lambda: self._handle_update_result(res, silent=silent))

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_update_result(self, res: UpdateCheckResult, silent: bool = False) -> None:
        is_en = self._lang() == "en"
        if res.status == "update_available":
            if silent and self._notified_update_ver == res.latest_version:
                return
            self._notified_update_ver = res.latest_version
            file_line = f"\nFile: {res.asset_name}" if res.asset_name else ""
            notes_line = f"\n\n{res.notes}" if res.notes else ""
            title = "Update Available" if is_en else "Có phiên bản mới"
            msg = (
                f"desk-widget v{res.latest_version} is available (current: v{res.current_version}).{file_line}{notes_line}\n\nOpen browser to download?"
                if is_en
                else f"Đã có desk-widget v{res.latest_version} (đang dùng: v{res.current_version}).{file_line}{notes_line}\n\nMở trình duyệt để tải bản mới?"
            )
            if messagebox.askyesno(title, msg, parent=self.root):
                webbrowser.open(res.download_url or res.release_url)
            return

        if silent:
            return

        if res.status == "not_configured":
            messagebox.showinfo(
                "Check for updates" if is_en else "Kiểm tra cập nhật",
                (
                    f"Current version: v{res.current_version}\n\n"
                    "Set GITHUB_REPO = \"<username>/desk-widget\" in updater.py before publishing releases."
                )
                if is_en
                else (
                    f"Phiên bản hiện tại: v{res.current_version}\n\n"
                    "Chưa cấu hình địa chỉ GitHub Releases (hãy điền GITHUB_REPO = \"<ten-ban>/desk-widget\" trong updater.py khi phát hành)."
                ),
                parent=self.root,
            )
        elif res.status == "up_to_date":
            messagebox.showinfo(
                "Up to date" if is_en else "Đã là bản mới nhất",
                f"You are running the latest version (v{res.current_version})."
                if is_en
                else f"Bạn đang dùng phiên bản mới nhất (v{res.current_version}).",
                parent=self.root,
            )
        else:
            messagebox.showwarning(
                "Update check failed" if is_en else "Không kiểm tra được cập nhật",
                f"Could not connect to GitHub Releases:\n{res.error}"
                if is_en
                else f"Không kết nối được GitHub Releases:\n{res.error}",
                parent=self.root,
            )

    def trigger_refresh(self, force_weather: bool = False) -> None:
        threading.Thread(target=self._refresh_worker, args=(force_weather,), daemon=True).start()

    def _refresh_worker(self, force_weather: bool) -> None:
        if not self._refresh_lock.acquire(blocking=False):
            return
        try:
            cfg = self.cfg
            w_cfg = cfg["weather"]
            city, lat, lon = self.weather_client.resolve_location(w_cfg, force=force_weather)
            weather = self.weather_client.get_weather(
                city=city,
                latitude=lat,
                longitude=lon,
                cache_minutes=int(w_cfg.get("cache_minutes", 15)),
                force=force_weather,
            )

            cfg_dirty = False
            if w_cfg.get("auto_location", True):
                if (
                    w_cfg.get("city") != city
                    or round(float(w_cfg.get("latitude", 0)), 4) != round(lat, 4)
                    or round(float(w_cfg.get("longitude", 0)), 4) != round(lon, 4)
                ):
                    w_cfg["city"] = city
                    w_cfg["latitude"] = round(lat, 4)
                    w_cfg["longitude"] = round(lon, 4)
                    cfg_dirty = True

                det_tz = weather.timezone or self.weather_client.get_detected_timezone()
                if det_tz and tz.gettz(det_tz) is not None and cfg.get("timezone") != det_tz:
                    cfg["timezone"] = det_tz
                    cfg_dirty = True

            if cfg_dirty:
                save_config(cfg)

            effective_tz = str(cfg.get("timezone", "Asia/Ho_Chi_Minh"))
            now = datetime.now(_get_tz(effective_tz))
            cal = self.calendar_client.fetch(
                cfg.get("calendars", []),
                tz_name=effective_tz,
                view_year=self.view_year,
                view_month=self.view_month,
            )
            stats = self.sys_monitor.read(sample_interval=0.4, include_cpu_temp=True)

            def _update_ui() -> None:
                self._last_cal = cal
                self._last_weather = weather
                self._last_stats = stats
                self._redraw_from_state(now=now)

            self.root.after(0, _update_ui)
        finally:
            self._refresh_lock.release()

    def _schedule_next_refresh(self) -> None:
        interval_ms = max(15, int(self.cfg.get("refresh_seconds", 60))) * 1000
        self.root.after(interval_ms, self._on_timer)

    def _on_timer(self) -> None:
        self.trigger_refresh(force_weather=False)
        self._schedule_next_refresh()

    def open_settings(self) -> None:
        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        is_en = self._lang() == "en"
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title(f"desk-widget Settings (v{APP_VERSION})" if is_en else f"Cài đặt desk-widget (v{APP_VERSION})")
        _set_window_icon(win, _active_icon_path(self.cfg))
        win.resizable(False, False)
        pad = {"padx": 10, "pady": 4}

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        # Owner display name & alignment
        owner_row = ttk.Frame(frm)
        owner_row.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(owner_row, text="Header title:" if is_en else "Tên trên thanh tiêu đề:", font=("Segoe UI", 9, "bold")).pack(side="left")
        var_owner = tk.StringVar(value=str(self.cfg.get("owner_name", "Desk Widget")))
        ttk.Entry(owner_row, textvariable=var_owner, width=24).pack(side="left", padx=8)
        ttk.Label(owner_row, text="Align:" if is_en else "Vị trí:").pack(side="left", padx=(6, 4))
        align_labels = {"left": "Left", "center": "Center", "right": "Right"} if is_en else {"left": "Trái", "center": "Giữa", "right": "Phải"}
        align_rev = {v: k for k, v in align_labels.items()}
        var_align_set = tk.StringVar(value=align_labels.get(str(self.cfg.get("owner_align", "center")), align_labels["center"]))
        ttk.Combobox(
            owner_row,
            textvariable=var_align_set,
            values=list(align_labels.values()),
            width=7,
            state="readonly",
        ).pack(side="left")

        ttk.Separator(frm, orient="horizontal").grid(row=1, column=0, columnspan=2, sticky="ew", pady=6)

        # Named calendar list (separated rows)
        hdr_cal = ttk.Frame(frm)
        hdr_cal.grid(row=2, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(
            hdr_cal,
            text="Calendars (individual links):" if is_en else "Danh sách lịch (tách từng link riêng):",
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        ttk.Label(
            frm,
            text=(
                "Supports secret/public .ics URLs, Google Calendar embed URLs, or local .ics paths"
                if is_en
                else "Hỗ trợ link .ics bí mật, link .ics công khai, link Google Calendar embed URL hoặc đường dẫn file .ics"
            ),
            foreground="#555555",
        ).grid(row=3, column=0, columnspan=2, sticky="w", padx=10)

        cal_list_frame = ttk.Frame(frm)
        cal_list_frame.grid(row=4, column=0, columnspan=2, sticky="ew", **pad)
        cal_rows: list[dict] = []

        def _add_cal_row(name_val: str = "", url_val: str = "", enabled_val: bool = True) -> None:
            row_f = ttk.Frame(cal_list_frame)
            row_f.pack(fill="x", pady=2)
            v_en = tk.BooleanVar(value=enabled_val)
            v_name = tk.StringVar(value=name_val)
            v_url = tk.StringVar(value=url_val)

            ttk.Checkbutton(row_f, variable=v_en).pack(side="left")
            ttk.Entry(row_f, textvariable=v_name, width=14).pack(side="left", padx=(2, 6))
            ttk.Entry(row_f, textvariable=v_url, width=44, font=("Consolas", 9)).pack(side="left", padx=(0, 6))

            def _remove() -> None:
                cal_rows.remove(entry)
                row_f.destroy()

            ttk.Button(row_f, text="Del" if is_en else "Xóa", width=5, command=_remove).pack(side="left")
            entry = {"frame": row_f, "enabled": v_en, "name": v_name, "url": v_url}
            cal_rows.append(entry)

        # Column labels for calendar rows
        col_hdr = ttk.Frame(cal_list_frame)
        col_hdr.pack(fill="x")
        ttk.Label(col_hdr, text="On" if is_en else "Bật", width=4).pack(side="left")
        ttk.Label(col_hdr, text="Name" if is_en else "Tên lịch", width=15).pack(side="left", padx=(0, 4))
        ttk.Label(col_hdr, text="Calendar URL / .ics path" if is_en else "Link URL / .ics").pack(side="left")

        existing_cals = self.cfg.get("calendars", [])
        if existing_cals:
            for c in existing_cals:
                _add_cal_row(
                    name_val=str(c.get("name") or ""),
                    url_val=str(c.get("url") or ""),
                    enabled_val=bool(c.get("enabled", True)),
                )
        else:
            _add_cal_row(name_val="Personal" if is_en else "Cá nhân", url_val="", enabled_val=True)

        ttk.Button(
            hdr_cal,
            text="+ Add calendar" if is_en else "+ Thêm link lịch",
            command=lambda: _add_cal_row(name_val=f"Cal {len(cal_rows) + 1}" if is_en else f"Lịch {len(cal_rows) + 1}", url_val="", enabled_val=True),
        ).pack(side="right")

        ttk.Separator(frm, orient="horizontal").grid(row=5, column=0, columnspan=2, sticky="ew", pady=6)

        ttk.Label(frm, text="Weather (Open-Meteo):" if is_en else "Thời tiết (Open-Meteo):", font=("Segoe UI", 9, "bold")).grid(
            row=6, column=0, columnspan=2, sticky="w", **pad
        )
        w_cfg = self.cfg["weather"]
        var_auto_loc = tk.BooleanVar(value=bool(w_cfg.get("auto_location", True)))
        var_city = tk.StringVar(value=w_cfg.get("city", "Hà Nội"))
        var_lat = tk.StringVar(value=str(w_cfg.get("latitude", 21.0184)))
        var_lon = tk.StringVar(value=str(w_cfg.get("longitude", 105.8461)))
        var_tz = tk.StringVar(value=str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh")))

        chk_auto = ttk.Checkbutton(
            frm,
            text="Auto-detect location & calendar timezone via IP" if is_en else "Tự động cập nhật vị trí & múi giờ lịch theo mạng (IP)",
            variable=var_auto_loc,
        )
        chk_auto.grid(row=7, column=0, columnspan=2, sticky="w", padx=10, pady=(2, 0))

        city_row = ttk.Frame(frm)
        city_row.grid(row=8, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(city_row, text="City:" if is_en else "Thành phố:").pack(side="left")
        ent_city = ttk.Entry(city_row, textvariable=var_city, width=18)
        ent_city.pack(side="left", padx=6)

        def _lookup_city() -> None:
            res = geocode_city(var_city.get())
            if res:
                name, lat, lon = res
                var_city.set(name)
                var_lat.set(f"{lat:.4f}")
                var_lon.set(f"{lon:.4f}")
            else:
                messagebox.showwarning(
                    "Not found" if is_en else "Không tìm thấy",
                    "Could not resolve coordinates for this city." if is_en else "Không tìm thấy tọa độ thành phố này.",
                    parent=win,
                )

        btn_lookup = ttk.Button(city_row, text="Find coords" if is_en else "Tìm tọa độ", command=_lookup_city)
        btn_lookup.pack(side="left")
        ttk.Label(city_row, text="Lat/Lon:").pack(side="left", padx=(10, 4))
        ent_lat = ttk.Entry(city_row, textvariable=var_lat, width=7)
        ent_lat.pack(side="left")
        ent_lon = ttk.Entry(city_row, textvariable=var_lon, width=7)
        ent_lon.pack(side="left", padx=(4, 0))
        ttk.Label(city_row, text="TZ:" if is_en else "Múi giờ:").pack(side="left", padx=(10, 4))
        ent_tz = ttk.Entry(city_row, textvariable=var_tz, width=16)
        ent_tz.pack(side="left")

        def _sync_loc_state(*_args) -> None:
            state = "disabled" if var_auto_loc.get() else "normal"
            for w_item in (ent_city, btn_lookup, ent_lat, ent_lon, ent_tz):
                w_item.configure(state=state)

        var_auto_loc.trace_add("write", _sync_loc_state)
        _sync_loc_state()

        ttk.Separator(frm, orient="horizontal").grid(row=9, column=0, columnspan=2, sticky="ew", pady=6)

        var_scale = tk.DoubleVar(value=float(self.cfg.get("scale", 1.0)))
        s_init = str(self.cfg.get("style", "serif")).lower()
        if s_init == "esl":
            s_init = "sans"
        elif s_init not in ("botanical", "serif", "sans"):
            s_init = "serif"
        var_style_set = tk.StringVar(value=s_init)
        var_theme_set = tk.StringVar(value=str(self.cfg.get("theme", "auto")))
        var_temp_set = tk.StringVar(value=str(self.cfg.get("temp_unit", "C")).upper())
        lang_labels = {"vi": "Tiếng Việt", "en": "English"}
        lang_rev = {v: k for k, v in lang_labels.items()}
        var_lang_set = tk.StringVar(value=lang_labels[self._lang()])
        var_autostart_set = tk.BooleanVar(value=is_autostart_enabled())

        opt_row = ttk.Frame(frm)
        opt_row.grid(row=10, column=0, columnspan=2, sticky="ew", **pad)
        ttk.Label(opt_row, text="Style:" if is_en else "Phong cách:").pack(side="left")
        ttk.Combobox(opt_row, textvariable=var_style_set, values=["botanical", "serif", "sans"], width=9, state="readonly").pack(
            side="left", padx=(4, 8)
        )
        ttk.Label(opt_row, text="Theme:" if is_en else "Chế độ:").pack(side="left")
        ttk.Combobox(opt_row, textvariable=var_theme_set, values=["auto", "light", "dark"], width=5, state="readonly").pack(
            side="left", padx=(4, 8)
        )
        ttk.Label(opt_row, text="Scale:" if is_en else "Cỡ:").pack(side="left")
        ttk.Combobox(opt_row, textvariable=var_scale, values=[0.85, 1.0, 1.2, 1.25, 1.4], width=5, state="readonly").pack(
            side="left", padx=(4, 8)
        )
        ttk.Label(opt_row, text="Temp:" if is_en else "Nhiệt độ:").pack(side="left")
        ttk.Combobox(opt_row, textvariable=var_temp_set, values=["C", "F"], width=3, state="readonly").pack(
            side="left", padx=(4, 8)
        )
        ttk.Label(opt_row, text="Lang:" if is_en else "Ngôn ngữ:").pack(side="left")
        ttk.Combobox(opt_row, textvariable=var_lang_set, values=["Tiếng Việt", "English"], width=10, state="readonly").pack(
            side="left", padx=(4, 8)
        )
        if is_en:
            autostart_set_lbl = "Auto-start (macOS)" if IS_MACOS else "Auto-start (Windows)"
        else:
            autostart_set_lbl = "Tự mở cùng macOS" if IS_MACOS else "Tự mở cùng Windows"
        ttk.Checkbutton(opt_row, text=autostart_set_lbl, variable=var_autostart_set).pack(side="left")

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=11, column=0, columnspan=2, sticky="e", pady=(10, 2), padx=10)

        def _save() -> None:
            new_cals: list[dict] = []
            for idx, r in enumerate(cal_rows):
                u = r["url"].get().strip()
                nm = r["name"].get().strip() or f"Lịch {idx + 1}"
                en = bool(r["enabled"].get())
                if not u:
                    continue
                if "•" in u:
                    messagebox.showwarning(
                        "Link .ics bị che",
                        f"Link của [{nm}] đang chứa dấu che (••••).\n\n"
                        "Trên Google Calendar, hãy bấm nút Con mắt (Hiện) hoặc nút Sao chép bên phải ô link iCal.",
                        parent=win,
                    )
                    return
                if not (u.lower().startswith(("http://", "https://", "webcal://")) or os.path.exists(u)):
                    messagebox.showwarning(
                        "Link không hợp lệ",
                        f"Link của [{nm}] phải bắt đầu bằng https://, webcal:// hoặc là đường dẫn file .ics tồn tại trên máy.",
                        parent=win,
                    )
                    return
                new_cals.append({"name": nm, "url": u, "enabled": en})

            self.cfg["owner_name"] = var_owner.get().strip() or "Desk Widget"
            self.cfg["owner_align"] = align_rev.get(var_align_set.get(), "center")
            self.var_align.set(self.cfg["owner_align"])
            self.cfg["calendars"] = new_cals
            self.cfg["weather"]["auto_location"] = bool(var_auto_loc.get())
            try:
                self.cfg["weather"]["city"] = var_city.get().strip() or "Hà Nội"
                self.cfg["weather"]["latitude"] = float(var_lat.get())
                self.cfg["weather"]["longitude"] = float(var_lon.get())
            except ValueError:
                messagebox.showerror("Lỗi", "Latitude/Longitude phải là số hợp lệ.", parent=win)
                return
            tz_val = var_tz.get().strip()
            if not var_auto_loc.get():
                if not tz_val or tz.gettz(tz_val) is None:
                    messagebox.showerror(
                        "Lỗi",
                        "Múi giờ không hợp lệ (ví dụ: Asia/Ho_Chi_Minh, Asia/Tokyo, Europe/London).",
                        parent=win,
                    )
                    return
                self.cfg["timezone"] = tz_val
            self.cfg["scale"] = float(var_scale.get())
            self.cfg["style"] = var_style_set.get()
            self.var_style.set(self.cfg["style"])
            self.cfg["theme"] = var_theme_set.get()
            self.var_theme.set(self.cfg["theme"])
            self.cfg["temp_unit"] = str(var_temp_set.get() or "C").upper()
            if hasattr(self, "var_temp_unit"):
                self.var_temp_unit.set(self.cfg["temp_unit"])
            self.cfg["language"] = lang_rev.get(var_lang_set.get(), "vi")
            if hasattr(self, "var_lang"):
                self.var_lang.set(self.cfg["language"])
            auto_val = bool(var_autostart_set.get())
            self.cfg["auto_start"] = auto_val
            self.var_autostart.set(auto_val)
            set_autostart(auto_val, _active_icon_path(self.cfg))
            save_config(self.cfg)
            self._build_menu()
            win.destroy()
            self.trigger_refresh(force_weather=True)

        ttk.Button(btn_row, text="Cancel" if is_en else "Hủy", command=win.destroy).pack(side="right", padx=(6, 0))
        ttk.Button(btn_row, text="Save & Refresh" if is_en else "Lưu & Cập nhật", command=_save).pack(side="right")

    def quit(self) -> None:
        self._close_detail_popup()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    _replace_existing_instance()
    app = ESLDeskWidget()
    app.run()
