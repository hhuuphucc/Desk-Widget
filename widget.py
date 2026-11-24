"""Lightweight floating E-Ink ESL desktop widget (Windows & macOS Intel/Apple Silicon)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
import os
import plistlib
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote
import uuid
import webbrowser
from PIL import Image, ImageDraw, ImageOps, ImageTk
from dateutil import tz
import psutil

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    import winsound

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
    _USER32.LoadImageW.argtypes = [
        wintypes.HINSTANCE,
        wintypes.LPCWSTR,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.UINT,
    ]
    _USER32.LoadImageW.restype = wintypes.HANDLE
    _USER32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _USER32.SendMessageW.restype = ctypes.c_ssize_t
else:
    _USER32 = None  # type: ignore[assignment]

from calendar_client import (
    EN_WEEKDAYS,
    CalendarClient,
    CalendarEvent,
    CalendarSummary,
    VN_WEEKDAYS,
    _get_tz,
    build_rrule_from_preset,
    describe_repeat_options,
    extract_meeting_links,
    find_due_local_reminders,
    find_due_reminders,
    format_event_time,
    local_events_to_ics,
    parse_clock_time,
    parse_ics_for_date,
)
from modern_ui import (
    ACCENT as MUI_ACCENT,
    ACCENT_HOVER as MUI_ACCENT_HOVER,
    BG_CARD as MUI_CARD,
    BG_FIELD as MUI_FIELD,
    BG_FIELD_HOVER as MUI_FIELD_HOVER,
    BG_SHELL as MUI_SHELL,
    BORDER_SUBTLE as MUI_BORDER,
    DANGER_BG as MUI_DANGER_BG,
    DANGER_FG as MUI_DANGER_FG,
    DANGER_HOVER as MUI_DANGER_HOVER,
    DialogPalette,
    INK as MUI_INK,
    MUTED as MUI_MUTED,
    SUBTLE as MUI_SUBTLE,
    TONAL_BG as MUI_TONAL_BG,
    TONAL_FG as MUI_TONAL_FG,
    TONAL_HOVER as MUI_TONAL_HOVER,
    apply_modern_ttk_style,
    attach_placeholder,
    format_pretty_date,
    get_dialog_theme,
    make_info_button,
    make_modern_checkbox,
    make_pill_button,
    make_pill_dropdown,
    make_rounded_entry,
    make_rounded_rect_photo,
    mousewheel_units,
    open_date_picker,
    read_entry_clean,
    retheme_dialog_tree,
)
from renderer import (
    PAPER_SERIF_LIGHT,
    HitRegion,
    SystemPatchCache,
    ThemePalette,
    auto_is_dark,
    compose_bg_layer,
    format_temp,
    is_modern_desktop_style,
    is_system_dark_mode,
    patch_widget_system_stats,
    render_widget_cached,
    render_widget_with_hits,
    resolve_theme,
    set_sun_location,
)
from system_client import SystemMonitor, SystemStats, top_cpu_processes, top_gpu_processes, top_ram_processes
from updater import (
    APP_AUTHOR,
    APP_COPYRIGHT,
    APP_EMAIL,
    APP_LICENSE,
    APP_VERSION,
    GITHUB_PROFILE_URL,
    GITHUB_REPO,
    REPO_URL,
    UpdateCheckResult,
    check_for_update,
)

__copyright__ = APP_COPYRIGHT
__license__ = APP_LICENSE
from weather_client import (
    WORLD_TIMEZONES,
    DayForecast,
    WeatherClient,
    WeatherData,
    day_abbr_for_lang,
    format_city_name,
    geocode_city,
    geocode_city_with_tz,
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
    "bg_mode": "default",
    "bg_image": "",
    "bg_pos": "cover",
    "bg_tone": "original",
    "bg_zoom": 1.0,
    "bg_offset_x": 0.0,
    "bg_offset_y": 0.0,
    "bg_opacity": 0.55,
    "logo_mode": "widget_bg",
    "logo_path": "",
    "logo_pos": "before_title",
    "last_media_dir": "",
    "calendars": [],
    "refresh_seconds": 60,
    "sys_refresh_seconds": 2.0,
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
    "local_events": [],
    "reminder": {
        "enabled": True,
        "minutes_before": 15,
        "sound": True,
    },
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
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("deskwidget.app")
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_ICON_PHOTO_CACHE: dict[tuple[int, str], ImageTk.PhotoImage] = {}


def _apply_win32_icons(win: tk.Tk | tk.Toplevel, ico_path: str) -> None:
    if not IS_WINDOWS or _USER32 is None:
        return
    try:
        if not win.winfo_exists():
            return
        hwnd = _USER32.GetAncestor(win.winfo_id(), GA_ROOT) or wintypes.HWND(win.winfo_id())
        for icon_type, size in ((0, 16), (1, 48)):
            hicon = _USER32.LoadImageW(None, ico_path, 1, size, size, 0x00000010)
            if hicon:
                _USER32.SendMessageW(hwnd, 0x0080, icon_type, hicon)
    except Exception:
        pass


def _build_maps_url(loc_text: str) -> str:
    """Resolve event location text to a Google Maps URL (homepage when blank, or direct URL/search)."""
    raw = (loc_text or "").strip()
    if not raw:
        return "https://www.google.com/maps"
    low = raw.lower()
    if low.startswith(("https://", "http://")):
        return raw
    return f"https://www.google.com/maps/search/?api=1&query={quote(raw)}"


def _set_window_icon(win: tk.Tk | tk.Toplevel, ico_path: str) -> None:
    """Apply window icon cleanly on both Windows (.ico + AppUserModelID) and macOS/Linux (iconphoto)."""
    if not ico_path or not os.path.exists(ico_path):
        return
    if IS_WINDOWS:
        try:
            if isinstance(win, tk.Tk):
                win.iconbitmap(default=ico_path)
            else:
                win.iconbitmap(ico_path)
        except Exception:
            pass
    try:
        cache_key = (id(win.winfo_toplevel() if isinstance(win, tk.Tk) else win.master), ico_path)
        photo = _ICON_PHOTO_CACHE.get(cache_key)
        if photo is None:
            img = Image.open(ico_path).convert("RGBA").resize((128, 128), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img, master=win)
            _ICON_PHOTO_CACHE[cache_key] = photo
        win.iconphoto(isinstance(win, tk.Tk), photo)
        win._desk_icon_ref = photo  # type: ignore[attr-defined]
    except Exception:
        pass
    if IS_WINDOWS:
        try:
            win.after(60, lambda: _apply_win32_icons(win, ico_path))
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
        self._sys_cache: SystemPatchCache | None = None
        self._last_sys_sig: tuple | None = None
        self._active_theme: ThemePalette = PAPER_SERIF_LIGHT
        self._hit_map: list[HitRegion] = []
        self.last_screen: Image.Image | None = None
        self._photo: ImageTk.PhotoImage | None = None
        self._detail_win: tk.Toplevel | None = None
        self._detail_key: tuple[str, object] | None = None
        self._settings_win: tk.Toplevel | None = None
        self._settings_logo_sync = None
        self._preview_style: str | None = None
        self._preview_theme: str | None = None
        self._preview_scale: float | None = None
        self._preview_align: str | None = None
        self._preview_logo_mode: str | None = None
        self._preview_logo_pos: str | None = None
        self._preview_bg_mode: str | None = None
        self._preview_bg_pos: str | None = None
        self._preview_bg_tone: str | None = None
        self._preview_bg_zoom: float | None = None
        self._preview_bg_offset_x: float | None = None
        self._preview_bg_offset_y: float | None = None
        self._preview_bg_opacity: float | None = None
        self._reminders_win: tk.Toplevel | None = None
        self._event_editor_win: tk.Toplevel | None = None
        self._reminder_win: tk.Toplevel | None = None
        self._notified_reminders: set[str] = set()
        self._snooze_reminders: dict[str, tuple[datetime, CalendarEvent]] = {}
        self._last_fg: int | None = None

        self._refresh_lock = threading.Lock()
        self._sys_lock = threading.Lock()
        self._drag_x = 0
        self._drag_y = 0
        self._moved = False
        self._exiting = False

        self.root = tk.Tk()
        self.root.title("desk-widget")
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        if IS_MACOS:
            try:
                self.root.createcommand("::tk::mac::Quit", self.quit)
            except Exception:
                pass
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
        try:
            _w0 = self.cfg.get("weather") or {}
            set_sun_location(_w0.get("latitude"), _w0.get("longitude"))
        except Exception:
            pass
        if bool(self.cfg.get("auto_start", True)) and not is_autostart_enabled():
            set_autostart(True, _active_icon_path(self.cfg))
        self._render_initial_placeholder()
        self._position_window()
        self.root.after(120, self._apply_z_order)
        self.root.after(500, self._z_order_watchdog)

        self.trigger_refresh(force_weather=True)
        self._schedule_next_refresh()
        self._schedule_sys_refresh()
        self._schedule_reminder_check()
        self._last_observed_dark: bool | None = None
        self.root.after(3000, self._theme_watchdog)
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
            label="Settings..." if is_en else "Cài đặt...",
            command=self.open_settings,
        )
        upd_lbl = f"Check for updates (v{APP_VERSION})..." if is_en else f"Kiểm tra cập nhật (v{APP_VERSION})..."
        self.menu.add_command(
            label=upd_lbl,
            command=lambda: self._check_updates_async(silent=False),
        )
        self.menu.add_separator()
        self.menu.add_command(label="Quit" if is_en else "Thoát", command=self.quit)

    def _active_now(self) -> datetime:
        tz_name = str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))
        return datetime.now(_get_tz(tz_name))

    def _effective_bg_mode(self) -> str:
        raw = getattr(self, "_preview_bg_mode", None) or self.cfg.get("bg_mode")
        if raw:
            m = str(raw).strip().lower()
            if m == "custom":
                bp = str(self.cfg.get("bg_image") or "").strip()
                return "custom" if (bp and os.path.exists(bp)) else "default"
            if m in ("default", "none"):
                return "default"
        bp = str(self.cfg.get("bg_image") or "").strip()
        return "custom" if (bp and os.path.exists(bp)) else "default"

    def _resolve_widget_bg_path(self) -> str | None:
        if self._effective_bg_mode() != "custom":
            return "__none__"
        bp = str(self.cfg.get("bg_image") or "").strip()
        return bp if (bp and os.path.exists(bp)) else "__none__"

    def _resolve_header_logo_path(self) -> str | None:
        mode = str(getattr(self, "_preview_logo_mode", None) or self.cfg.get("logo_mode", "widget_bg")).strip().lower()
        if mode == "none":
            return None
        if mode == "custom":
            lp = str(self.cfg.get("logo_path") or "").strip()
            return lp if (lp and os.path.exists(lp)) else None
        return "__widget_bg__"

    def _clear_live_preview(self) -> None:
        self._preview_style = None
        self._preview_theme = None
        self._preview_scale = None
        self._preview_align = None
        self._preview_logo_mode = None
        self._preview_logo_pos = None
        self._preview_bg_mode = None
        self._preview_bg_pos = None
        self._preview_bg_tone = None
        self._preview_bg_zoom = None
        self._preview_bg_offset_x = None
        self._preview_bg_offset_y = None
        self._preview_bg_opacity = None

    def _render_initial_placeholder(self) -> None:
        now = self._active_now()
        tz_name = str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))
        local_ics = local_events_to_ics(list(self.cfg.get("local_events", [])), tz_name=tz_name)
        has_cals = any(c.get("enabled", True) and str(c.get("url", "")).strip() for c in self.cfg.get("calendars", []))
        if local_ics:
            cal = parse_ics_for_date(
                [("Personal" if self._lang() == "en" else "Nhắc riêng", local_ics)],
                now=now,
                tz_name=tz_name,
                view_year=self.view_year,
                view_month=self.view_month,
            )
        else:
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
        effective_theme = str(getattr(self, "_preview_theme", None) or self.cfg.get("theme", "auto"))
        eff_style = str(getattr(self, "_preview_style", None) or self.cfg.get("style", "serif"))
        eff_scale = getattr(self, "_preview_scale", None)
        if eff_scale is None:
            eff_scale = float(self.cfg.get("scale", 1.0))
        eff_align = str(getattr(self, "_preview_align", None) or self.cfg.get("owner_align", "center"))
        eff_logo_pos = str(getattr(self, "_preview_logo_pos", None) or self.cfg.get("logo_pos", "before_title"))
        eff_bg_pos = str(getattr(self, "_preview_bg_pos", None) or self.cfg.get("bg_pos", "cover"))
        eff_bg_tone = str(getattr(self, "_preview_bg_tone", None) or self.cfg.get("bg_tone", "original"))
        eff_bg_zoom = float(getattr(self, "_preview_bg_zoom", None) if getattr(self, "_preview_bg_zoom", None) is not None else self.cfg.get("bg_zoom", 1.0))
        eff_bg_ox = float(getattr(self, "_preview_bg_offset_x", None) if getattr(self, "_preview_bg_offset_x", None) is not None else self.cfg.get("bg_offset_x", 0.0))
        eff_bg_oy = float(getattr(self, "_preview_bg_offset_y", None) if getattr(self, "_preview_bg_offset_y", None) is not None else self.cfg.get("bg_offset_y", 0.0))
        eff_bg_op = float(getattr(self, "_preview_bg_opacity", None) if getattr(self, "_preview_bg_opacity", None) is not None else self.cfg.get("bg_opacity", 0.55))
        img, hits, screen, th, sys_cache = render_widget_cached(
            self._last_cal,
            self._last_weather,
            self._last_stats,
            owner_name=str(self.cfg.get("owner_name", "Desk Widget")),
            owner_align=eff_align,
            theme_mode=effective_theme,
            style=eff_style,
            temp_unit=str(self.cfg.get("temp_unit", "C")),
            lang=self._lang(),
            logo_path=self._resolve_header_logo_path(),
            bg_path=self._resolve_widget_bg_path(),
            show_esl_frame=False,
            scale=float(eff_scale),
            now=now,
            view_year=self.view_year,
            view_month=self.view_month,
            selected_date=self.selected_date,
            selected_weather_date=self.selected_weather_date,
            logo_pos=eff_logo_pos,
            bg_pos=eff_bg_pos,
            bg_tone=eff_bg_tone,
            bg_zoom=eff_bg_zoom,
            bg_offset_x=eff_bg_ox,
            bg_offset_y=eff_bg_oy,
            bg_opacity=eff_bg_op,
        )
        self._sys_cache = sys_cache
        self._last_sys_sig = self._stats_sig(self._last_stats)
        self._active_theme = th
        self._last_observed_dark = th.is_dark
        self._hit_map = hits
        self.last_screen = screen
        self._apply_image(img)
        if not self.cfg.get("always_on_top", False):
            self.root.after(20, self._apply_z_order)

    @staticmethod
    def _stats_sig(stats: SystemStats | None) -> tuple | None:
        if stats is None:
            return None
        return (
            stats.cpu_pct,
            stats.ram_pct,
            round(stats.ram_used_gb, 1),
            stats.gpu_pct,
            round((stats.gpu_vram_used_mb or 0) / 1024.0, 1) if stats.gpu_vram_used_mb is not None else None,
            stats.cpu_temp_c,
            stats.gpu_temp_c,
        )

    def _theme_watchdog(self) -> None:
        try:
            mode = str(self.cfg.get("theme", "auto")).strip().lower()
            if mode in ("system", "os", "auto") and self._last_cal is not None:
                now = self._active_now()
                cur_dark = is_system_dark_mode() if mode in ("system", "os") else auto_is_dark(now)
                if self._last_observed_dark is not None and cur_dark != self._last_observed_dark:
                    self._redraw_from_state(now=now)
                else:
                    self._last_observed_dark = cur_dark
        except Exception:
            pass
        try:
            self.root.after(3000, self._theme_watchdog)
        except Exception:
            pass

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
        use_alpha = is_modern_desktop_style(getattr(self, "_active_theme", PAPER_SERIF_LIGHT))
        img_for_tk = (
            rgba_img
            if (IS_MACOS and self._mac_transparent)
            else _prepare_for_tk(rgba_img, with_transparency=use_alpha)
        )
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
            self._close_detail_popup()
            self._last_cal = self.calendar_client.render_month_from_cache(tz_name, self.view_year, self.view_month)
            self._redraw_from_state()

    def _close_detail_popup(self) -> None:
        if self._detail_win is not None and self._detail_win.winfo_exists():
            self._detail_win.destroy()
        self._detail_win = None
        self._detail_key = None

    def _create_popup_window(self, title: str, pop_w: int = 360, pop_h: int = 270) -> tk.Toplevel:
        self._close_detail_popup()
        th = self._active_theme
        win = tk.Toplevel(self.root)
        win.withdraw()
        self._detail_win = win
        win.title(title)
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
        _set_window_icon(win, _active_icon_path(self.cfg))
        win.bind("<Escape>", lambda _e: self._close_detail_popup())
        return win

    @staticmethod
    def _reveal_popup_window(win: tk.Toplevel) -> None:
        if not win.winfo_exists():
            return
        win.update_idletasks()
        win.deiconify()
        win.lift()

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
        ttk.Button(
            header,
            text="+ Add reminder" if is_en else "+ Thêm nhắc",
            command=lambda d=target_date: self._open_event_editor(default_date=d),
        ).pack(side="right", padx=(8, 0))
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
        self._reveal_popup_window(win)

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
        self._reveal_popup_window(win)

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
                    rows = top_cpu_processes(1.5, 12)
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
        self._reveal_popup_window(win)

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
        if hasattr(self, "var_topmost"):
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

    def _dialog_parent(self) -> tk.Tk | tk.Toplevel:
        if self._settings_win is not None and self._settings_win.winfo_exists():
            return self._settings_win
        return self.root

    def _dialog_palette(self, style_override: str | None = None, theme_override: str | None = None) -> DialogPalette:
        st = style_override or str(getattr(self, "_preview_style", None) or self.cfg.get("style", "serif"))
        tm = theme_override or str(getattr(self, "_preview_theme", None) or self.cfg.get("theme", "auto"))
        resolved = resolve_theme(tm, now=self._active_now(), style=st)
        return get_dialog_theme(st, is_dark=resolved.is_dark)

    def _default_media_dir(self) -> str:
        saved = str(self.cfg.get("last_media_dir") or "").strip()
        if saved and os.path.isdir(saved):
            return saved
        for cand in (
            os.path.expanduser("~/Pictures"),
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Downloads"),
            os.path.expanduser("~"),
        ):
            if os.path.isdir(cand):
                return cand
        return BASE_DIR

    def _open_image_picker_dialog(self, kind: str = "bg") -> None:
        is_en = self._lang() == "en"
        is_bg = kind == "bg"
        parent_w = self._dialog_parent()
        p = self._dialog_palette()

        win = tk.Toplevel(parent_w)
        win.withdraw()
        win.title(
            ("Widget Background, Framing & Tone" if is_en else "Nền Widget, Căn chỉnh & Âm bản")
            if is_bg
            else ("Header Logo & Position" if is_en else "Đổi logo & Vị trí")
        )
        win.configure(bg=p.shell)
        win.resizable(False, False)
        _set_window_icon(win, _active_icon_path(self.cfg))
        apply_modern_ttk_style(win, p)
        win.bind("<Escape>", lambda _e: win.destroy())

        outer = tk.Frame(win, bg=p.shell, padx=16, pady=14)
        outer.pack(fill="both", expand=True)

        card = tk.Frame(outer, bg=p.card, highlightbackground=p.border, highlightthickness=1, padx=14, pady=12)
        card.pack(fill="both", expand=True, pady=(0, 12))

        mode_map = (
            (
                {"default": "Default (Per style)", "custom": "Custom background"}
                if is_en
                else {"default": "Mặc định theo Style", "custom": "Cá nhân hóa ảnh nền"}
            )
            if is_bg
            else (
                {"widget_bg": "Default", "custom": "Custom circle", "none": "Hidden"}
                if is_en
                else {"widget_bg": "Mặc định", "custom": "Ảnh riêng", "none": "Ẩn icon"}
            )
        )
        mode_rev = {v: k for k, v in mode_map.items()}
        if is_bg:
            cur_mode_key = str(getattr(self, "_preview_bg_mode", None) or self._effective_bg_mode()).lower()
            if cur_mode_key not in mode_map:
                cur_mode_key = "default"
        else:
            cur_mode_key = str(getattr(self, "_preview_logo_mode", None) or self.cfg.get("logo_mode", "widget_bg")).lower()
            if cur_mode_key == "wallpaper" or cur_mode_key not in mode_map:
                cur_mode_key = "widget_bg"
        var_mode = tk.StringVar(value=mode_map[cur_mode_key])

        pos_map = (
            {
                "cover": "Fill center" if is_en else "Phủ giữa",
                "top": "Top focus" if is_en else "Canh trên",
                "bottom": "Bottom focus" if is_en else "Canh dưới",
                "left": "Left panel" if is_en else "Cột trái",
                "right": "Right panel" if is_en else "Cột phải",
                "bottom_right": "Bottom-right" if is_en else "Góc phải dưới",
            }
            if is_bg
            else {
                "before_title": "Left of title" if is_en else "Cạnh tên (Bên trái)",
                "after_title": "Right of title" if is_en else "Cạnh tên (Bên phải)",
                "far_left": "Top-left corner" if is_en else "Góc trái trên thanh tiêu đề",
                "far_right": "Top-right corner" if is_en else "Góc phải trên thanh tiêu đề",
            }
        )
        pos_rev = {v: k for k, v in pos_map.items()}
        if is_bg:
            cur_pos_key = str(getattr(self, "_preview_bg_pos", None) or self.cfg.get("bg_pos", "cover")).lower()
        else:
            cur_pos_key = str(getattr(self, "_preview_logo_pos", None) or self.cfg.get("logo_pos", "before_title")).lower()
        var_pos = tk.StringVar(value=pos_map.get(cur_pos_key, next(iter(pos_map.values()))))

        tone_map = {"original": "Original" if is_en else "Ảnh gốc", "negative": "Negative" if is_en else "Âm bản"}
        tone_rev = {v: k for k, v in tone_map.items()}
        cur_tone_key = str(getattr(self, "_preview_bg_tone", None) or self.cfg.get("bg_tone", "original")).lower()
        if cur_tone_key not in tone_map:
            cur_tone_key = "original"
        var_tone = tk.StringVar(value=tone_map[cur_tone_key])

        cur_zoom = float(
            getattr(self, "_preview_bg_zoom", None)
            if getattr(self, "_preview_bg_zoom", None) is not None
            else self.cfg.get("bg_zoom", 1.0)
        )
        cur_ox = float(
            getattr(self, "_preview_bg_offset_x", None)
            if getattr(self, "_preview_bg_offset_x", None) is not None
            else self.cfg.get("bg_offset_x", 0.0)
        )
        cur_oy = float(
            getattr(self, "_preview_bg_offset_y", None)
            if getattr(self, "_preview_bg_offset_y", None) is not None
            else self.cfg.get("bg_offset_y", 0.0)
        )
        cur_op = float(
            getattr(self, "_preview_bg_opacity", None)
            if getattr(self, "_preview_bg_opacity", None) is not None
            else self.cfg.get("bg_opacity", 0.55)
        )
        cur_op = max(0.15, min(1.0, cur_op))
        bg_frame_state = {"zoom": cur_zoom, "ox": cur_ox, "oy": cur_oy, "opacity": cur_op, "src_path": "", "src_img": None}

        cur_img_path = str(self.cfg.get("bg_image" if is_bg else "logo_path") or "").strip()
        var_path = tk.StringVar(value=cur_img_path)
        var_dir = tk.StringVar(value=self._default_media_dir())
        var_hide_logo = tk.BooleanVar(value=(not is_bg and cur_mode_key == "none"))

        tk.Label(
            card,
            text=(
                ("1. Background mode, tone & preset:" if is_en else "1. Chế độ nền, tông ảnh & vị trí:")
                if is_bg
                else ("1. Placement & icon visibility:" if is_en else "1. Vị trí & hiển thị icon trên thanh tiêu đề:")
            ),
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))
        top_row = tk.Frame(card, bg=p.card)
        top_row.pack(fill="x", pady=(0, 10))
        if is_bg:
            make_pill_dropdown(
                top_row,
                var_mode,
                values=list(mode_map.values()),
                palette=p,
                parent_bg=p.card,
                width_px=200,
                height=32,
            ).pack(side="left", padx=(0, 6))

        dd_tone = None
        if is_bg:
            dd_tone = make_pill_dropdown(
                top_row,
                var_tone,
                values=list(tone_map.values()),
                palette=p,
                parent_bg=p.card,
                width_px=106,
                height=32,
            )
            dd_tone.pack(side="left", padx=(0, 6))

        def _on_pos_preset(_opt=None) -> None:
            if is_bg:
                bg_frame_state["zoom"] = 1.0
                bg_frame_state["ox"] = 0.0
                bg_frame_state["oy"] = 0.0
                _update_preview()

        dd_pos = make_pill_dropdown(
            top_row,
            var_pos,
            values=list(pos_map.values()),
            palette=p,
            parent_bg=p.card,
            width_px=132 if is_bg else 250,
            height=32,
            command=_on_pos_preset if is_bg else None,
        )
        dd_pos.pack(side="left")

        if is_bg:
            info_title = "Quick background placement" if is_en else "Chức năng Vị trí ảnh nền"
            info_msg = (
                "• Best for transparent PNG stickers/emblems: quickly pins the graphic to Left panel, Right panel, Top, Bottom, or Bottom-right.\n\n"
                "• For full rectangular wallpapers: sets the initial edge anchor before cropping; you can simply drag on the canvas and use −/+ Zoom to frame freely."
                if is_en
                else "• Hữu ích nhất với ảnh PNG nền trong suốt (hoa văn, sticker): đặt nhanh hình sang Cột trái, Cột phải, Canh trên/dưới hoặc thu gọn ở Góc phải dưới.\n\n"
                "• Với ảnh nền chụp kín khung thông thường: chỉ chỉnh điểm neo mép ban đầu; bạn có thể kéo trực tiếp trên khung ảnh và bấm −/+ Zoom để căn tự do."
            )
            make_info_button(
                top_row,
                title=info_title,
                message=info_msg,
                palette=p,
                parent_bg=p.card,
                size=24,
                ok_text="Got it" if is_en else "Đã hiểu",
            ).pack(side="left", padx=(6, 0))

        if not is_bg:
            make_modern_checkbox(
                top_row,
                text="Hide icon" if is_en else "Ẩn icon",
                variable=var_hide_logo,
                palette=p,
                parent_bg=p.card,
            ).pack(side="left", padx=(14, 0))
            make_info_button(
                top_row,
                title="Header Logo" if is_en else "Logo trên thanh tiêu đề",
                message=(
                    "• Custom logo images are automatically cropped into a clean circle matching the header bar.\n\n"
                    "• Choose placement beside the widget title or in a corner, or check 'Hide icon' to remove it."
                    if is_en
                    else "• Ảnh logo riêng được tự động cắt gọn thành hình tròn vừa vặn trên thanh tiêu đề.\n\n"
                    "• Có thể đặt cạnh tên widget hoặc góc trái/phải; chọn 'Ẩn icon' nếu muốn giấu hoàn toàn biểu tượng."
                ),
                palette=p,
                parent_bg=p.card,
                size=24,
                ok_text="Got it" if is_en else "Đã hiểu",
            ).pack(side="left", padx=(8, 0))

        crop_canvas: tk.Canvas | None = None
        var_zoom_lbl = tk.StringVar()
        var_op_lbl = tk.StringVar()
        prev_lbl: tk.Label | None = None

        if is_bg:
            tk.Label(
                card,
                text=("2. Frame & align on widget canvas (drag to pan, scroll or -/+ to zoom):" if is_en else "2. Căn chỉnh vừa khung Widget (kéo ảnh để di chuyển, +/- để thu phóng):"),
                bg=p.card,
                fg=p.accent,
                font=("Segoe UI", 10, "bold"),
            ).pack(anchor="w", pady=(0, 6))

            cw_prev, ch_prev = 384, 179
            crop_wrap = tk.Frame(card, bg=p.card)
            crop_wrap.pack(fill="x", pady=(0, 8))
            crop_canvas = tk.Canvas(
                crop_wrap,
                width=cw_prev,
                height=ch_prev,
                bg=p.shell,
                highlightbackground=p.border,
                highlightthickness=1,
                bd=0,
                cursor="fleur",
            )
            crop_canvas.pack(side="left")

            ctrl_col = tk.Frame(crop_wrap, bg=p.card, padx=10)
            ctrl_col.pack(side="left", fill="y")

            tk.Label(
                ctrl_col,
                textvariable=var_zoom_lbl,
                bg=p.card,
                fg=p.ink,
                font=("Segoe UI", 10, "bold"),
                anchor="w",
            ).pack(anchor="w", pady=(2, 6))

            zoom_btns = tk.Frame(ctrl_col, bg=p.card)
            zoom_btns.pack(anchor="w", pady=(0, 8))

            def _nudge_zoom(delta: float) -> None:
                if mode_rev.get(var_mode.get(), "default") != "custom":
                    return
                bg_frame_state["zoom"] = max(0.4, min(3.0, round(float(bg_frame_state["zoom"]) + delta, 2)))
                _update_preview()

            def _nudge_opacity(delta: float) -> None:
                if mode_rev.get(var_mode.get(), "default") != "custom":
                    return
                bg_frame_state["opacity"] = max(0.15, min(1.0, round(float(bg_frame_state["opacity"]) + delta, 2)))
                _update_preview()

            def _reset_framing() -> None:
                bg_frame_state["zoom"] = 1.0
                bg_frame_state["ox"] = 0.0
                bg_frame_state["oy"] = 0.0
                bg_frame_state["opacity"] = 0.55
                var_pos.set(pos_map["cover"])
                _update_preview()

            for b_t, b_fn in (("−", lambda: _nudge_zoom(-0.1)), ("+", lambda: _nudge_zoom(0.1))):
                make_pill_button(
                    zoom_btns,
                    b_t,
                    b_fn,
                    bg=p.field,
                    fg=p.ink,
                    hover_bg=p.field_hover,
                    parent_bg=p.card,
                    pad_x=11,
                    height=26,
                    radius=8,
                    font=("Segoe UI", 11, "bold"),
                ).pack(side="left", padx=(0, 6))

            tk.Label(
                ctrl_col,
                textvariable=var_op_lbl,
                bg=p.card,
                fg=p.ink,
                font=("Segoe UI", 9, "bold"),
                anchor="w",
            ).pack(anchor="w", pady=(0, 4))

            op_btns = tk.Frame(ctrl_col, bg=p.card)
            op_btns.pack(anchor="w", pady=(0, 8))
            for b_t, b_fn in (("−", lambda: _nudge_opacity(-0.10)), ("+", lambda: _nudge_opacity(0.10))):
                make_pill_button(
                    op_btns,
                    b_t,
                    b_fn,
                    bg=p.field,
                    fg=p.ink,
                    hover_bg=p.field_hover,
                    parent_bg=p.card,
                    pad_x=11,
                    height=26,
                    radius=8,
                    font=("Segoe UI", 11, "bold"),
                ).pack(side="left", padx=(0, 6))

            make_pill_button(
                ctrl_col,
                "Reset" if is_en else "Đặt lại",
                _reset_framing,
                bg=p.tonal_bg,
                fg=p.tonal_fg,
                hover_bg=p.tonal_hover,
                parent_bg=p.card,
                pad_x=12,
                height=26,
                radius=8,
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w")

            drag_origin = {"x": 0, "y": 0, "ox": 0.0, "oy": 0.0}

            def _drag_start(ev: tk.Event) -> None:
                if mode_rev.get(var_mode.get(), "default") != "custom":
                    return
                drag_origin["x"] = ev.x
                drag_origin["y"] = ev.y
                drag_origin["ox"] = float(bg_frame_state["ox"])
                drag_origin["oy"] = float(bg_frame_state["oy"])

            def _drag_move(ev: tk.Event) -> None:
                if mode_rev.get(var_mode.get(), "default") != "custom":
                    return
                dx_n = (ev.x - drag_origin["x"]) / (cw_prev * 0.5)
                dy_n = (ev.y - drag_origin["y"]) / (ch_prev * 0.5)
                bg_frame_state["ox"] = max(-1.5, min(1.5, drag_origin["ox"] + dx_n))
                bg_frame_state["oy"] = max(-1.5, min(1.5, drag_origin["oy"] + dy_n))
                _update_preview()

            def _wheel_zoom(ev: tk.Event) -> None:
                if mode_rev.get(var_mode.get(), "default") != "custom" or not getattr(ev, "delta", 0):
                    return
                _nudge_zoom(0.1 if ev.delta > 0 else -0.1)

            crop_canvas.bind("<ButtonPress-1>", _drag_start)
            crop_canvas.bind("<B1-Motion>", _drag_move)
            crop_canvas.bind("<MouseWheel>", _wheel_zoom)

        tk.Label(
            card,
            text=(
                ("3. Custom background image:" if is_en else "3. Chọn ảnh nền cá nhân:")
                if is_bg
                else ("2. Custom logo image:" if is_en else "2. Chọn ảnh logo riêng:")
            ),
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
        ).pack(anchor="w", pady=(0, 6))

        def _browse_from(init_dir: str | None = None) -> None:
            start_d = (init_dir or var_dir.get() or self._default_media_dir()).strip()
            if not os.path.isdir(start_d):
                start_d = self._default_media_dir()
            picked = filedialog.askopenfilename(
                parent=win,
                initialdir=start_d,
                title=("Choose image" if is_en else "Chọn file ảnh"),
                filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All files", "*.*")],
            )
            if picked:
                var_path.set(picked)
                var_mode.set(mode_map["custom"])
                if not is_bg:
                    var_hide_logo.set(False)
                if is_bg:
                    bg_frame_state["zoom"] = 1.0
                    bg_frame_state["ox"] = 0.0
                    bg_frame_state["oy"] = 0.0
                parent_d = os.path.dirname(picked)
                if parent_d and os.path.isdir(parent_d):
                    var_dir.set(parent_d)
                    self.cfg["last_media_dir"] = parent_d
                _update_preview()

        path_row = tk.Frame(card, bg=p.card)
        path_row.pack(fill="x", pady=(0, 4))
        p_shell, ent_path = make_rounded_entry(
            path_row,
            var_path,
            width_px=346 if is_bg else 264,
            height=32,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            font=("Consolas", 9),
        )
        p_shell.pack(side="left", padx=(0, 8))
        make_pill_button(
            path_row,
            "Choose folder..." if is_en else "Chọn thư mục...",
            lambda: _browse_from(None),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=12,
            height=32,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8 if not is_bg else 0))
        if not is_bg:
            prev_lbl = tk.Label(path_row, bg=p.field, width=36, height=34)
            prev_lbl.configure(width=0, height=0)
            prev_lbl.pack(side="left")

        def _update_preview(*_a) -> None:
            if is_bg and crop_canvas is not None:
                z_pct = int(round(float(bg_frame_state["zoom"]) * 100))
                op_val = max(0.15, min(1.0, float(bg_frame_state["opacity"])))
                op_pct = int(round(op_val * 100))
                var_zoom_lbl.set(f"Zoom: {z_pct}%")
                var_op_lbl.set((f"Strength: {op_pct}%" if is_en else f"Độ rõ nền: {op_pct}%"))
                cw_p, ch_p = 384, 179
                th_prev = resolve_theme(
                    str(getattr(self, "_preview_theme", None) or self.cfg.get("theme", "auto")),
                    now=self._active_now(),
                    style=str(getattr(self, "_preview_style", None) or self.cfg.get("style", "serif")),
                )
                base_img = Image.new("RGBA", (cw_p, ch_p), th_prev.paper)
                mk = mode_rev.get(var_mode.get(), "default")
                fp = var_path.get().strip()
                if mk == "custom" and fp and os.path.exists(fp):
                    try:
                        if bg_frame_state["src_path"] != fp or bg_frame_state["src_img"] is None:
                            with Image.open(fp) as _raw_src:
                                bg_frame_state["src_img"] = ImageOps.exif_transpose(_raw_src).convert("RGBA")
                            bg_frame_state["src_path"] = fp
                        src_rgba = bg_frame_state["src_img"]
                        pos_k = pos_rev.get(var_pos.get(), "cover")
                        tone_k = tone_rev.get(var_tone.get(), "original")
                        fg_layer = compose_bg_layer(
                            src_rgba,
                            cw_p,
                            ch_p,
                            pos=pos_k,
                            zoom=float(bg_frame_state["zoom"]),
                            offset_x=float(bg_frame_state["ox"]),
                            offset_y=float(bg_frame_state["oy"]),
                            tone=tone_k,
                            div_x_px=int(round(cw_p * 202 / 480.0)),
                            center_y_px=int(round(ch_p * 127 / 224.0)),
                            emblem_size=int(round(ch_p * 154 / 224.0)),
                            alpha_scale=op_val,
                        )
                        base_img.alpha_composite(fg_layer, (0, 0))
                        # Show the same protective frosted readability layer as the real widget
                        if src_rgba.getchannel("A").getextrema()[0] >= 245 and op_val > 0.25:
                            s_a = max(0, min(162, int(round((op_val - 0.18) * 190))))
                            if s_a > 0:
                                sc_im = Image.new("RGBA", (cw_p, ch_p), (0, 0, 0, 0))
                                sc_d = ImageDraw.Draw(sc_im)
                                pr = tuple(int(th_prev.paper.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                                sc_c = (*pr, s_a)
                                dx_p = int(round(cw_p * 202 / 480.0))
                                sc_d.rounded_rectangle((5, 2, cw_p - 6, int(round(ch_p * 23 / 224.0))), radius=5, fill=sc_c)
                                sc_d.rounded_rectangle((5, int(round(ch_p * 28 / 224.0)), dx_p - 4, ch_p - 4), radius=6, fill=sc_c)
                                sc_d.rounded_rectangle((dx_p + 4, int(round(ch_p * 28 / 224.0)), cw_p - 6, ch_p - 4), radius=6, fill=sc_c)
                                base_img.alpha_composite(sc_im, (0, 0))
                    except Exception:
                        pass
                ph = ImageTk.PhotoImage(base_img.convert("RGB"), master=win)
                crop_canvas._prev_ph = ph  # type: ignore[attr-defined]
                crop_canvas.delete("all")
                crop_canvas.create_image(0, 0, anchor="nw", image=ph)
                # Subtle guide lines & sample widget labels to verify contrast live
                hdr_y = int(round(ch_p * 25 / 224.0))
                div_x_c = int(round(cw_p * 202 / 480.0))
                wx_y = int(round(ch_p * 127 / 224.0))
                g_col = p.accent if mk == "custom" else p.subtle
                crop_canvas.create_line(4, hdr_y, cw_p - 4, hdr_y, fill=g_col, dash=(3, 3))
                crop_canvas.create_line(div_x_c, hdr_y, div_x_c, ch_p - 4, fill=g_col, dash=(3, 3))
                crop_canvas.create_line(4, wx_y, div_x_c, wx_y, fill=g_col, dash=(3, 3))
                if mk == "custom" and fp and os.path.exists(fp):
                    crop_canvas.create_text(14, hdr_y + 12, text="SYSTEM  54%", anchor="w", fill=th_prev.accent, font=("Segoe UI", 8, "bold"))
                    crop_canvas.create_text(div_x_c + 12, hdr_y + 12, text="TODAY · CALENDAR", anchor="w", fill=th_prev.ink, font=("Segoe UI", 8, "bold"))
                if mk != "custom":
                    msg_c = "Using default Style background" if is_en else "Đang dùng nền mặc định theo Style"
                    crop_canvas.create_rectangle(cw_p // 2 - 125, ch_p // 2 - 15, cw_p // 2 + 125, ch_p // 2 + 15, fill=p.card, outline=p.border)
                    crop_canvas.create_text(cw_p // 2, ch_p // 2, text=msg_c, fill=p.muted, font=("Segoe UI", 9, "bold"))
                return

            if prev_lbl is None:
                return
            fp = var_path.get().strip()
            if fp and os.path.exists(fp):
                try:
                    im = Image.open(fp).convert("RGBA")
                    im = ImageOps.contain(im, (34, 34), Image.Resampling.LANCZOS)
                    ph = ImageTk.PhotoImage(im, master=win)
                    prev_lbl._img_ref = ph  # type: ignore[attr-defined]
                    prev_lbl.configure(image=ph, bg=p.card)
                    return
                except Exception:
                    pass
            prev_lbl.configure(image="", bg=p.card)

        def _sync_mode_ui(*_a) -> None:
            if is_bg:
                mk = mode_rev.get(var_mode.get(), "default")
                st_custom = "normal" if mk == "custom" else "disabled"
                dd_pos.configure(state=st_custom)
                if dd_tone is not None:
                    dd_tone.configure(state=st_custom)
                ent_path.configure(state=st_custom)
            else:
                hidden = bool(var_hide_logo.get())
                dd_pos.configure(state="disabled" if hidden else "normal")
                ent_path.configure(state="disabled" if hidden else "normal")
            _update_preview()

        var_mode.trace_add("write", _sync_mode_ui)
        var_hide_logo.trace_add("write", _sync_mode_ui)
        if is_bg:
            var_tone.trace_add("write", lambda *_a: _update_preview())
        _sync_mode_ui()

        def _apply() -> None:
            if is_bg:
                chosen_mode = mode_rev.get(var_mode.get(), "default")
            else:
                chosen_mode = "none" if var_hide_logo.get() else ("custom" if var_path.get().strip() else cur_mode_key)
                if chosen_mode == "none" and not var_hide_logo.get():
                    chosen_mode = "custom"
            chosen_pos = pos_rev.get(var_pos.get(), "cover" if is_bg else "before_title")
            chosen_tone = tone_rev.get(var_tone.get(), "original") if is_bg else "original"
            chosen_p = var_path.get().strip()
            if chosen_mode == "custom":
                if not chosen_p:
                    messagebox.showwarning(
                        "No image selected" if is_en else "Chưa chọn ảnh",
                        (
                            "Please choose an image file or switch mode to Default."
                            if is_bg
                            else "Please choose a logo image or check 'Hide icon'."
                        )
                        if is_en
                        else (
                            "Hãy chọn file ảnh hoặc chuyển chế độ về Mặc định."
                            if is_bg
                            else "Hãy chọn file ảnh logo hoặc tích chọn 'Ẩn icon'."
                        ),
                        parent=win,
                    )
                    return
                if not os.path.exists(chosen_p):
                    messagebox.showwarning(
                        "File not found" if is_en else "Không tìm thấy file",
                        "Selected image file does not exist." if is_en else "Đường dẫn ảnh không tồn tại.",
                        parent=win,
                    )
                    return
            try:
                if chosen_mode == "custom" and chosen_p and chosen_p != cur_img_path:
                    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    dst_name = f"custom_bg_{stamp}.png" if is_bg else f"custom_logo_{stamp}.png"
                    dst_path = os.path.join(BASE_DIR, dst_name)
                    os.makedirs(BASE_DIR, exist_ok=True)
                    Image.open(chosen_p).convert("RGBA").save(dst_path, format="PNG")
                    parent_d = os.path.dirname(chosen_p)
                    if parent_d and os.path.isdir(parent_d):
                        self.cfg["last_media_dir"] = parent_d
                    if is_bg:
                        self.cfg["bg_image"] = dst_path
                    else:
                        self.cfg["logo_path"] = dst_path
                if is_bg:
                    z_save = round(float(bg_frame_state["zoom"]), 3)
                    ox_save = round(float(bg_frame_state["ox"]), 4)
                    oy_save = round(float(bg_frame_state["oy"]), 4)
                    op_save = round(float(bg_frame_state["opacity"]), 2)
                    self.cfg["bg_mode"] = chosen_mode
                    self.cfg["bg_pos"] = chosen_pos
                    self.cfg["bg_tone"] = chosen_tone
                    self.cfg["bg_zoom"] = z_save
                    self.cfg["bg_offset_x"] = ox_save
                    self.cfg["bg_offset_y"] = oy_save
                    self.cfg["bg_opacity"] = op_save
                    if chosen_mode == "default":
                        self.cfg["bg_image"] = ""
                    if getattr(self, "_preview_bg_mode", None) is not None or self._settings_win is not None:
                        self._preview_bg_mode = chosen_mode
                        self._preview_bg_pos = chosen_pos
                        self._preview_bg_tone = chosen_tone
                        self._preview_bg_zoom = z_save
                        self._preview_bg_offset_x = ox_save
                        self._preview_bg_offset_y = oy_save
                        self._preview_bg_opacity = op_save
                    if self._settings_logo_sync is not None:
                        self._settings_logo_sync(
                            None,
                            bg_pos=chosen_pos,
                            bg_mode=chosen_mode,
                            bg_tone=chosen_tone,
                            bg_zoom=z_save,
                            bg_offset_x=ox_save,
                            bg_offset_y=oy_save,
                            bg_opacity=op_save,
                        )
                else:
                    self.cfg["logo_mode"] = chosen_mode
                    self.cfg["logo_pos"] = chosen_pos
                    if hasattr(self, "var_logo_mode"):
                        self.var_logo_mode.set(chosen_mode)
                    if getattr(self, "_preview_logo_mode", None) is not None or self._settings_win is not None:
                        self._preview_logo_mode = chosen_mode
                        self._preview_logo_pos = chosen_pos
                    if self._settings_logo_sync is not None:
                        self._settings_logo_sync(chosen_mode, logo_pos=chosen_pos)
                save_config(self.cfg)
                win.destroy()
                self._redraw_from_state()
            except Exception as exc:
                messagebox.showerror(
                    "Image error" if is_en else "Lỗi xử lý ảnh",
                    f"{exc}",
                    parent=win,
                )

        btn_bar = tk.Frame(outer, bg=p.shell)
        btn_bar.pack(fill="x")
        make_pill_button(
            btn_bar,
            "Cancel" if is_en else "Hủy",
            win.destroy,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.shell,
            pad_x=16,
            height=32,
            font=("Segoe UI", 10),
        ).pack(side="right", padx=(8, 0))
        make_pill_button(
            btn_bar,
            "Apply" if is_en else "Áp dụng",
            _apply,
            bg=p.accent,
            fg=p.accent_fg,
            hover_bg=p.accent_hover,
            parent_bg=p.shell,
            pad_x=18,
            height=32,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")
        self._reveal_popup_window(win)

    def _choose_widget_bg(self) -> None:
        self._open_image_picker_dialog(kind="bg")

    def _choose_custom_logo(self) -> None:
        self._open_image_picker_dialog(kind="logo")

    def _toggle_autostart(self) -> None:
        val = bool(self.var_autostart.get())
        self.cfg["auto_start"] = val
        save_config(self.cfg)
        set_autostart(val, _active_icon_path(self.cfg))

    def _change_icon(self) -> None:
        parent_w = self._dialog_parent()
        path = filedialog.askopenfilename(
            parent=parent_w,
            title="Chọn ảnh logo / icon mới",
            filetypes=[("Image / Icon", "*.png *.jpg *.jpeg *.webp *.ico"), ("All files", "*.*")],
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
            if self._settings_win is not None and self._settings_win.winfo_exists():
                _set_window_icon(self._settings_win, dst_ico)
            _update_shortcuts_icon(dst_ico)
            messagebox.showinfo(
                "Đã đổi icon",
                "Đã cập nhật icon mới cho widget!" if not IS_WINDOWS else "Đã cập nhật icon mới cho widget và shortcut Desktop!\n(Nếu Desktop chưa đổi ngay, bấm F5 ngoài Desktop.)",
                parent=parent_w,
            )
        except Exception as exc:
            messagebox.showerror("Lỗi đổi icon", f"Không chuyển được ảnh thành icon:\n{exc}", parent=parent_w)

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
            set_sun_location(lat, lon)
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
                list(cfg.get("calendars", [])),
                tz_name=effective_tz,
                view_year=self.view_year,
                view_month=self.view_month,
                local_events=list(cfg.get("local_events", [])),
                local_label="Personal" if self._lang() == "en" else "Nhắc riêng",
            )
            stats = self.sys_monitor.read(sample_interval=None, include_cpu_temp=True)

            def _update_ui() -> None:
                self._last_cal = cal
                self._last_weather = weather
                self._last_stats = stats
                self._redraw_from_state(now=now)
                self._check_due_reminders()

            self.root.after(0, _update_ui)
        finally:
            self._refresh_lock.release()

    def _schedule_next_refresh(self) -> None:
        interval_ms = max(15, int(self.cfg.get("refresh_seconds", 60))) * 1000
        self.root.after(interval_ms, self._on_timer)

    def _on_timer(self) -> None:
        self.trigger_refresh(force_weather=False)
        self._schedule_next_refresh()

    def _schedule_sys_refresh(self) -> None:
        interval_ms = max(1000, int(round(float(self.cfg.get("sys_refresh_seconds", 2.0)) * 1000)))
        self.root.after(interval_ms, self._on_sys_timer)

    def _on_sys_timer(self) -> None:
        threading.Thread(target=self._sys_worker, daemon=True).start()
        self._schedule_sys_refresh()

    def _sys_worker(self) -> None:
        if self._sys_cache is None or not self._sys_lock.acquire(blocking=False):
            return
        try:
            stats = self.sys_monitor.read(sample_interval=None, include_cpu_temp=True)
            sig = self._stats_sig(stats)
            if sig == self._last_sys_sig:
                return

            def _patch_ui() -> None:
                if self._sys_cache is None:
                    return
                self._last_stats = stats
                self._last_sys_sig = sig
                img, hits, screen = patch_widget_system_stats(
                    self._sys_cache,
                    stats,
                    temp_unit=str(self.cfg.get("temp_unit", "C")),
                    lang=self._lang(),
                )
                self._hit_map = hits
                self.last_screen = screen
                self._apply_image(img)

            self.root.after(0, _patch_ui)
        except Exception:
            pass
        finally:
            self._sys_lock.release()

    def _schedule_reminder_check(self) -> None:
        if not self._exiting:
            self.root.after(15_000, self._on_reminder_timer)

    def _on_reminder_timer(self) -> None:
        if self._exiting:
            return
        self._check_due_reminders()
        self._schedule_reminder_check()

    def _play_reminder_sound(self) -> None:
        rem_cfg = self.cfg.get("reminder") if isinstance(self.cfg.get("reminder"), dict) else {}
        if not bool((rem_cfg or {}).get("sound", True)):
            return
        try:
            if IS_WINDOWS:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
                return
            if IS_MACOS:
                glass = "/System/Library/Sounds/Glass.aiff"
                if os.path.exists(glass):
                    subprocess.Popen(["afplay", glass], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return
            self.root.bell()
        except Exception:
            try:
                self.root.bell()
            except Exception:
                pass

    def _send_os_banner(self, title: str, message: str) -> None:
        if not IS_MACOS:
            return
        try:
            safe_title = title.replace("\\", "\\\\").replace('"', '\\"')
            safe_msg = message.replace("\\", "\\\\").replace('"', '\\"')
            subprocess.Popen(
                ["osascript", "-e", f'display notification "{safe_msg}" with title "{safe_title}"'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def _close_reminder_popup(self) -> None:
        if self._reminder_win is not None and self._reminder_win.winfo_exists():
            self._reminder_win.destroy()
        self._reminder_win = None

    @staticmethod
    def _format_reminder_countdown(ev: CalendarEvent, mins_left: int, now: datetime, is_en: bool) -> str:
        days_gap = (ev.start.date() - now.date()).days
        if days_gap == 1:
            return f"Tomorrow · {ev.start.strftime('%b %d')}" if is_en else f"Ngày mai · {ev.start.strftime('%d/%m')}"
        if days_gap > 1:
            return f"In {days_gap} days · {ev.start.strftime('%b %d')}" if is_en else f"Còn {days_gap} ngày · {ev.start.strftime('%d/%m')}"
        if mins_left <= 0:
            return "Starting now" if is_en else "Đang bắt đầu ngay"
        if mins_left == 1:
            return "Starting in 1 min" if is_en else "Sắp diễn ra (còn 1 phút)"
        if mins_left < 60:
            return f"Starting in {mins_left} min" if is_en else f"Sắp diễn ra (còn {mins_left} phút)"
        hh, mm = mins_left // 60, mins_left % 60
        return f"In {hh}h {mm:02d}m" if is_en else f"Sắp diễn ra (còn {hh}g{mm:02d}p)"

    def _check_due_reminders(self) -> None:
        now = self._active_now()
        tz_name = str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))

        # Re-show any snoozed reminder once its snooze timestamp arrives
        for snooze_key in list(self._snooze_reminders):
            due_at, snoozed_ev = self._snooze_reminders[snooze_key]
            if now >= due_at:
                del self._snooze_reminders[snooze_key]
                secs_left = (snoozed_ev.start - now).total_seconds()
                mins_left = max(0, int((secs_left + 30.0) // 60)) if secs_left > 0 else 0
                self._play_reminder_sound()
                self._open_reminder_popup(snooze_key, snoozed_ev, mins_left)
                return

        # 1) Custom personal / local reminders (any date, yearly/custom RRULE, all-day or timed)
        local_events = list(self.cfg.get("local_events", []))
        due_local = find_due_local_reminders(
            local_events,
            now=now,
            tz_name=tz_name,
            notified_keys=self._notified_reminders,
        )
        if due_local:
            occ_key, ev, mins_left = due_local[0]
            self._notified_reminders.add(occ_key)
            is_en = self._lang() == "en"
            banner_hdr = self._format_reminder_countdown(ev, mins_left, now, is_en)
            self._play_reminder_sound()
            self._send_os_banner(f"desk-widget · {banner_hdr}", f"{format_event_time(ev, self._lang(), with_range=True)} — {ev.title}")
            self._open_reminder_popup(occ_key, ev, mins_left)
            return

        # 2) Global reminder for Google Calendar (.ics) timed events today
        rem_cfg = self.cfg.get("reminder") if isinstance(self.cfg.get("reminder"), dict) else {}
        if not bool((rem_cfg or {}).get("enabled", True)):
            return
        if self._last_cal is None or not self._last_cal.events_today:
            return
        try:
            lead_mins = int((rem_cfg or {}).get("minutes_before", 15))
        except Exception:
            lead_mins = 15

        due_items = find_due_reminders(
            self._last_cal.events_today,
            now=now,
            minutes_before=lead_mins,
            notified_keys=self._notified_reminders,
        )
        if not due_items:
            return
        occ_key, ev, mins_left = due_items[0]
        self._notified_reminders.add(occ_key)
        is_en = self._lang() == "en"
        banner_hdr = self._format_reminder_countdown(ev, mins_left, now, is_en)
        self._play_reminder_sound()
        self._send_os_banner(f"desk-widget · {banner_hdr}", f"{ev.time_range_label} — {ev.title}")
        self._open_reminder_popup(occ_key, ev, mins_left)

    def _open_reminder_popup(self, occ_key: str, ev: CalendarEvent, mins_left: int) -> None:
        self._close_reminder_popup()
        th = self._active_theme
        lang = self._lang()
        is_en = lang == "en"

        win = tk.Toplevel(self.root)
        win.withdraw()
        self._reminder_win = win
        win.title("Event Reminder" if is_en else "Nhắc nhở sự kiện")
        win.configure(bg=th.paper, highlightbackground=th.accent, highlightthickness=2)
        win.resizable(False, False)
        win.wm_attributes("-topmost", True)

        pop_w, pop_h = 370, 210
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        px = max(12, sw - pop_w - 18)
        py = max(40 if IS_MACOS else 12, sh - pop_h - (84 if IS_MACOS else 62))
        win.geometry(f"{pop_w}x{pop_h}+{px}+{py}")
        _set_window_icon(win, _active_icon_path(self.cfg))
        win.bind("<Escape>", lambda _e: self._close_reminder_popup())

        header = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        header.pack(fill="x")
        rem_txt = self._format_reminder_countdown(ev, mins_left, self._active_now(), is_en)
        rec_tag = (" · ↻ Recurring" if is_en else " · ↻ Lặp lại") if ev.is_recurring else ""
        tk.Label(
            header,
            text=f"{rem_txt}{rec_tag}",
            font=("Segoe UI", 10, "bold"),
            fg=th.accent,
            bg=th.paper,
        ).pack(side="left")
        if ev.calendar_name:
            tk.Label(
                header,
                text=f"[{ev.calendar_name}]",
                font=("Segoe UI", 9),
                fg=th.muted,
                bg=th.paper,
            ).pack(side="right")

        tk.Frame(win, bg=th.ink, height=1).pack(fill="x", padx=12)

        body = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        body.pack(fill="both", expand=True)
        date_pfx = f"{ev.start.strftime('%d/%m/%Y')} · "
        tk.Label(
            body,
            text=f"{date_pfx}{format_event_time(ev, lang, with_range=True)}",
            font=("Segoe UI", 10, "bold"),
            fg=th.ink,
            bg=th.paper,
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            body,
            text=ev.title,
            font=("Segoe UI", 11, "bold"),
            fg=th.ink,
            bg=th.paper,
            anchor="w",
            justify="left",
            wraplength=342,
        ).pack(fill="x", pady=(2, 4))
        if ev.location:
            tk.Label(
                body,
                text=ev.location,
                font=("Segoe UI", 9),
                fg=th.muted,
                bg=th.paper,
                anchor="w",
                wraplength=342,
            ).pack(fill="x")

        links = extract_meeting_links(ev, include_maps_for_address=True, lang=lang)
        if links:
            link_bar = tk.Frame(body, bg=th.paper, pady=4)
            link_bar.pack(fill="x")
            for lbl, url in links[:3]:
                tk.Button(
                    link_bar,
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

        btn_bar = tk.Frame(win, bg=th.paper, padx=12, pady=8)
        btn_bar.pack(fill="x", side="bottom")

        def _snooze_5m() -> None:
            self._snooze_reminders[occ_key] = (self._active_now() + timedelta(minutes=5), ev)
            self._close_reminder_popup()

        ttk.Button(
            btn_bar,
            text="Dismiss" if is_en else "Đã hiểu",
            command=self._close_reminder_popup,
        ).pack(side="right", padx=(6, 0))
        ttk.Button(
            btn_bar,
            text="Snooze 5m" if is_en else "Nhắc lại sau 5 phút",
            command=_snooze_5m,
        ).pack(side="right")

        self._reveal_popup_window(win)

    def _reload_local_calendar_now(self) -> None:
        tz_name = str(self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))
        local_events = list(self.cfg.get("local_events", []))
        local_label = "Personal" if self._lang() == "en" else "Nhắc riêng"
        local_ics = local_events_to_ics(local_events, tz_name=tz_name)
        self.calendar_client._local_payload = (local_label, local_ics) if local_ics else None
        self._last_cal = self.calendar_client.render_month_from_cache(tz_name, self.view_year, self.view_month)
        self._redraw_from_state()
        if (
            self._detail_win is not None
            and self._detail_win.winfo_exists()
            and self._detail_key is not None
            and self._detail_key[0] == "cal"
            and isinstance(self._detail_key[1], date)
        ):
            self._open_day_detail_popup(self._detail_key[1])
        self._check_due_reminders()

    def _open_reminders_manager(self) -> None:
        is_en = self._lang() == "en"
        if self._reminders_win is not None and self._reminders_win.winfo_exists():
            self._reminders_win.lift()
            return
        p = self._dialog_palette()
        win = tk.Toplevel(self.root)
        win.withdraw()
        self._reminders_win = win
        win.title("Reminders & Custom Events" if is_en else "Nhắc lịch & Sự kiện cá nhân")
        win.configure(bg=p.shell)
        win.resizable(False, False)
        _set_window_icon(win, _active_icon_path(self.cfg))
        apply_modern_ttk_style(win, p)
        win.bind("<Escape>", lambda _e: win.destroy())

        outer = tk.Frame(win, bg=p.shell, padx=18, pady=16)
        outer.pack(fill="both", expand=True)

        hdr = tk.Frame(outer, bg=p.shell)
        hdr.pack(fill="x", pady=(0, 12))
        hdr_left = tk.Frame(hdr, bg=p.shell)
        hdr_left.pack(side="left", fill="x", expand=True)
        tk.Label(
            hdr_left,
            text="Reminders & Custom Events" if is_en else "Nhắc lịch & Sự kiện cá nhân",
            bg=p.shell,
            fg=p.ink,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).pack(anchor="w")
        tk.Label(
            hdr_left,
            text="Works on any date, even without Google Calendar — supports yearly/monthly repeat"
            if is_en
            else "Đặt nhắc cho mọi ngày (lặp theo năm/tháng/tuần hoặc một lần), kèm vị trí Maps",
            bg=p.shell,
            fg=p.muted,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        card = tk.Frame(
            outer,
            bg=p.card,
            highlightbackground=p.border,
            highlightthickness=1,
            padx=8,
            pady=8,
        )
        card.pack(fill="both", expand=True, pady=(0, 12))

        cols = ("title", "date", "repeat", "location", "notify")
        tree = ttk.Treeview(card, columns=cols, show="headings", height=9, style="Modern.Treeview")
        headers = (
            ("Title", "Date / Time", "Repeat", "Location", "Notify")
            if is_en
            else ("Tiêu đề", "Ngày / Giờ", "Lặp lại", "Vị trí", "Thông báo")
        )
        widths = (180, 145, 175, 130, 155)
        for c_id, h_txt, w_px in zip(cols, headers, widths):
            tree.heading(c_id, text=h_txt)
            tree.column(c_id, width=w_px, anchor="w")
        sb = ttk.Scrollbar(card, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y", padx=(6, 0))

        unit_lbls = (
            {"minutes": "min", "hours": "hr", "days": "day(s)", "weeks": "wk(s)"}
            if is_en
            else {"minutes": "phút", "hours": "giờ", "days": "ngày", "weeks": "tuần"}
        )

        def _format_notify_summary(item: dict) -> str:
            rules = item.get("notifications")
            if isinstance(rules, list) and rules:
                parts: list[str] = []
                for r in rules[:2]:
                    if not isinstance(r, dict):
                        continue
                    u_k = str(r.get("unit") or "days")
                    u_v = int(r.get("value", 1))
                    u_s = unit_lbls.get(u_k, u_k)
                    if bool(item.get("all_day", True)) or u_k in ("days", "weeks"):
                        parts.append(f"-{u_v} {u_s} @ {r.get('at') or '09:00'}")
                    else:
                        parts.append(f"-{u_v} {u_s}")
                extra = f" (+{len(rules) - 2})" if len(rules) > 2 else ""
                return ", ".join(parts) + extra if parts else ("Off" if is_en else "Tắt")
            if bool(item.get("notify_enabled", True)):
                u_k = str(item.get("notify_unit") or "days")
                u_v = int(item.get("notify_value", 1))
                u_s = unit_lbls.get(u_k, u_k)
                if bool(item.get("all_day", True)) or u_k in ("days", "weeks"):
                    at_s = str(item.get("notify_at") or "09:00")
                    return f"-{u_v} {u_s} @ {at_s}"
                return f"-{u_v} {u_s}"
            return "Off" if is_en else "Tắt"

        def _refresh_list() -> None:
            for iid in tree.get_children():
                tree.delete(iid)
            items = list(self.cfg.get("local_events", []))
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                prefix = "" if bool(item.get("enabled", True)) else ("[Off] " if is_en else "[Tắt] ")
                title = f"{prefix}{item.get('title', '')}"
                sd_s = str(item.get("start_date") or "")
                try:
                    sd_obj = date.fromisoformat(sd_s)
                    rep_map = dict(describe_repeat_options(sd_obj, self._lang()))
                    rep_txt = rep_map.get(str(item.get("repeat") or "none"), str(item.get("rrule") or ""))
                    pretty_sd = format_pretty_date(sd_obj, self._lang())
                except Exception:
                    rep_txt = str(item.get("repeat") or "none")
                    pretty_sd = sd_s
                if bool(item.get("all_day", True)):
                    dt_txt = f"{pretty_sd} · " + ("All day" if is_en else "Cả ngày")
                else:
                    dt_txt = f"{pretty_sd} · {item.get('start_time', '09:00')}"
                loc = str(item.get("location") or "")
                not_txt = _format_notify_summary(item)
                tree.insert("", "end", iid=str(idx), values=(title, dt_txt, rep_txt, loc, not_txt))

        def _selected_idx() -> int | None:
            sel = tree.selection()
            if not sel:
                return None
            try:
                return int(sel[0])
            except Exception:
                return None

        def _add_new() -> None:
            self._open_event_editor(default_date=self.selected_date or self._active_now().date(), on_saved=_refresh_list)

        def _edit_sel() -> None:
            idx = _selected_idx()
            if idx is None:
                return
            self._open_event_editor(existing_idx=idx, on_saved=_refresh_list)

        def _toggle_sel() -> None:
            idx = _selected_idx()
            items = list(self.cfg.get("local_events", []))
            if idx is None or not (0 <= idx < len(items)):
                return
            items[idx]["enabled"] = not bool(items[idx].get("enabled", True))
            self.cfg["local_events"] = items
            save_config(self.cfg)
            self._reload_local_calendar_now()
            _refresh_list()

        def _del_sel() -> None:
            idx = _selected_idx()
            items = list(self.cfg.get("local_events", []))
            if idx is None or not (0 <= idx < len(items)):
                return
            items.pop(idx)
            self.cfg["local_events"] = items
            save_config(self.cfg)
            self._reload_local_calendar_now()
            _refresh_list()

        tree.bind("<Double-1>", lambda _e: _edit_sel())

        make_pill_button(
            hdr,
            "+ Add event" if is_en else "+ Tạo nhắc lịch",
            _add_new,
            bg=p.accent,
            fg=p.accent_fg,
            hover_bg=p.accent_hover,
            parent_bg=p.shell,
            pad_x=16,
            height=34,
        ).pack(side="right", padx=(12, 0))

        btn_bar = tk.Frame(outer, bg=p.shell)
        btn_bar.pack(fill="x")
        make_pill_button(
            btn_bar,
            "Edit" if is_en else "Sửa",
            _edit_sel,
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.shell,
            pad_x=16,
            height=32,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        make_pill_button(
            btn_bar,
            "Enable / Disable" if is_en else "Bật / Tắt",
            _toggle_sel,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.shell,
            pad_x=14,
            height=32,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        make_pill_button(
            btn_bar,
            "Delete" if is_en else "Xóa",
            _del_sel,
            bg=p.danger_bg,
            fg=p.danger_fg,
            hover_bg=p.danger_hover,
            parent_bg=p.shell,
            pad_x=14,
            height=32,
            font=("Segoe UI", 9),
        ).pack(side="left")
        make_pill_button(
            btn_bar,
            "Close" if is_en else "Đóng",
            win.destroy,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.shell,
            pad_x=18,
            height=32,
            font=("Segoe UI", 9),
        ).pack(side="right")

        _refresh_list()
        self._reveal_popup_window(win)

    def _open_event_editor(
        self,
        existing_idx: int | None = None,
        default_date: date | None = None,
        on_saved=None,
    ) -> None:
        is_en = self._lang() == "en"
        if self._event_editor_win is not None and self._event_editor_win.winfo_exists():
            self._event_editor_win.destroy()

        items = list(self.cfg.get("local_events", []))
        cur: dict = {}
        if existing_idx is not None and 0 <= existing_idx < len(items) and isinstance(items[existing_idx], dict):
            cur = dict(items[existing_idx])

        p = self._dialog_palette()
        win = tk.Toplevel(self.root)
        win.withdraw()
        self._event_editor_win = win
        win.title(
            ("Edit Reminder / Event" if existing_idx is not None else "New Reminder / Event")
            if is_en
            else ("Sửa nhắc lịch" if existing_idx is not None else "Tạo sự kiện & nhắc lịch")
        )
        win.configure(bg=p.shell)
        win.resizable(False, False)
        _set_window_icon(win, _active_icon_path(self.cfg))
        apply_modern_ttk_style(win, p)
        win.bind("<Escape>", lambda _e: win.destroy())

        outer = tk.Frame(win, bg=p.shell, padx=18, pady=16)
        outer.pack(fill="both", expand=True)

        init_d = default_date or self._active_now().date()
        try:
            init_sd = date.fromisoformat(str(cur.get("start_date") or init_d.isoformat()))
        except Exception:
            init_sd = init_d
        try:
            init_ed = date.fromisoformat(str(cur.get("end_date") or init_sd.isoformat()))
        except Exception:
            init_ed = init_sd
        if init_ed < init_sd:
            init_ed = init_sd

        var_title = tk.StringVar(value=str(cur.get("title") or ""))
        var_start_d = tk.StringVar(value=init_sd.isoformat())
        var_end_d = tk.StringVar(value=init_ed.isoformat())
        var_all_day = tk.BooleanVar(value=bool(cur.get("all_day", True)))
        var_start_t = tk.StringVar(value=str(cur.get("start_time") or "09:00"))
        var_end_t = tk.StringVar(value=str(cur.get("end_time") or "10:00"))
        var_loc = tk.StringVar(value=str(cur.get("location") or ""))

        # Top Bar: [✕] [Title input w/ underline] [Save pill]
        top_bar = tk.Frame(outer, bg=p.shell)
        top_bar.pack(fill="x", pady=(0, 12))

        btn_close = tk.Label(
            top_bar,
            text="✕",
            bg=p.shell,
            fg=p.muted,
            font=("Segoe UI", 13),
            width=3,
            cursor="hand2",
        )
        btn_close.pack(side="left", padx=(0, 6))
        btn_close.bind("<Enter>", lambda _e: btn_close.configure(fg=p.ink))
        btn_close.bind("<Leave>", lambda _e: btn_close.configure(fg=p.muted))
        btn_close.bind("<Button-1>", lambda _e: win.destroy())

        title_wrap = tk.Frame(top_bar, bg=p.shell)
        title_wrap.pack(side="left", fill="x", expand=True, padx=(0, 16))
        ent_title = tk.Entry(
            title_wrap,
            textvariable=var_title,
            bg=p.shell,
            fg=p.ink,
            insertbackground=p.accent,
            font=("Segoe UI", 16),
            bd=0,
            relief="flat",
            highlightthickness=0,
            width=30,
        )
        ent_title.pack(fill="x", ipady=2)
        title_rule = tk.Frame(title_wrap, bg=p.subtle, height=1)
        title_rule.pack(fill="x", pady=(2, 0))
        ent_title.bind("<FocusIn>", lambda _e: title_rule.configure(bg=p.accent, height=2))
        ent_title.bind("<FocusOut>", lambda _e: title_rule.configure(bg=p.subtle, height=1))
        attach_placeholder(
            ent_title,
            var_title,
            "Add title" if is_en else "Thêm tiêu đề",
            fg=p.ink,
            ph_fg=p.subtle,
        )

        # Save action holder populated below after validators exist
        save_action = [lambda: None]
        make_pill_button(
            top_bar,
            "Save" if is_en else "Lưu",
            lambda: save_action[0](),
            bg=p.accent,
            fg=p.accent_fg,
            hover_bg=p.accent_hover,
            parent_bg=p.shell,
            pad_x=22,
            height=34,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        # Date / Time / Recurrence strip (indented cleanly to match title)
        sched_box = tk.Frame(outer, bg=p.shell)
        sched_box.pack(fill="x", padx=(38, 0), pady=(0, 14))

        dt_strip = tk.Frame(sched_box, bg=p.shell)
        dt_strip.pack(fill="x", pady=(0, 8))

        def _make_date_chip(parent_w: tk.Misc, target_var: tk.StringVar, on_picked) -> tk.Label:
            lbl = tk.Label(
                parent_w,
                bg=p.shell,
                fg=p.ink,
                font=("Segoe UI", 10),
                compound="center",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )

            def _sync_chip() -> None:
                try:
                    d_o = date.fromisoformat(target_var.get().strip())
                except Exception:
                    d_o = init_d
                txt = format_pretty_date(d_o, self._lang())
                f_o = lbl.cget("font")
                import tkinter.font as _tkf

                w_px = max(92, _tkf.Font(root=win, font=f_o).measure(txt) + 24)
                img_i = make_rounded_rect_photo(lbl, w_px, 34, 8, p.field)
                img_h = make_rounded_rect_photo(lbl, w_px, 34, 8, p.field_hover)
                lbl._chip_imgs = (img_i, img_h)  # type: ignore[attr-defined]
                lbl.configure(text=txt, image=img_i)

            lbl._sync_chip = _sync_chip  # type: ignore[attr-defined]
            lbl.bind("<Enter>", lambda _e: lbl.configure(image=lbl._chip_imgs[1]))
            lbl.bind("<Leave>", lambda _e: lbl.configure(image=lbl._chip_imgs[0]))

            def _open_cal(_e) -> None:
                try:
                    cur_d = date.fromisoformat(target_var.get().strip())
                except Exception:
                    cur_d = init_d
                open_date_picker(win, lbl, cur_d, self._lang(), on_picked, palette=p)

            lbl.bind("<Button-1>", _open_cal)
            _sync_chip()
            return lbl

        chip_sd_holder: list[tk.Label] = []
        chip_ed_holder: list[tk.Label] = []

        def _on_pick_sd(picked: date) -> None:
            var_start_d.set(picked.isoformat())
            try:
                ed_cur = date.fromisoformat(var_end_d.get().strip())
            except Exception:
                ed_cur = picked
            if ed_cur < picked:
                var_end_d.set(picked.isoformat())
                if chip_ed_holder:
                    chip_ed_holder[0]._sync_chip()  # type: ignore[attr-defined]
            if chip_sd_holder:
                chip_sd_holder[0]._sync_chip()  # type: ignore[attr-defined]
            _refresh_rep_options()

        def _on_pick_ed(picked: date) -> None:
            try:
                sd_cur = date.fromisoformat(var_start_d.get().strip())
            except Exception:
                sd_cur = picked
            if picked < sd_cur:
                picked = sd_cur
            var_end_d.set(picked.isoformat())
            if chip_ed_holder:
                chip_ed_holder[0]._sync_chip()  # type: ignore[attr-defined]

        chip_sd = _make_date_chip(dt_strip, var_start_d, _on_pick_sd)
        chip_sd.pack(side="left")
        chip_sd_holder.append(chip_sd)

        tk.Label(
            dt_strip,
            text="to" if is_en else "tới",
            bg=p.shell,
            fg=p.muted,
            font=("Segoe UI", 10),
        ).pack(side="left", padx=8)

        chip_ed = _make_date_chip(dt_strip, var_end_d, _on_pick_ed)
        chip_ed.pack(side="left")
        chip_ed_holder.append(chip_ed)

        tm_wrap = tk.Frame(dt_strip, bg=p.shell)
        _, ent_st = make_rounded_entry(
            tm_wrap, var_start_t, width_px=72, height=34, radius=8, fill=p.field, parent_bg=p.shell, fg=p.ink, insert_bg=p.accent, ph_fg=p.subtle, disabled_fg=p.subtle
        )
        ent_st.master.pack(side="left", padx=(10, 4))
        tk.Label(tm_wrap, text="–", bg=p.shell, fg=p.muted, font=("Segoe UI", 10)).pack(side="left", padx=2)
        _, ent_et = make_rounded_entry(
            tm_wrap, var_end_t, width_px=72, height=34, radius=8, fill=p.field, parent_bg=p.shell, fg=p.ink, insert_bg=p.accent, ph_fg=p.subtle, disabled_fg=p.subtle
        )
        ent_et.master.pack(side="left", padx=(4, 0))

        rep_strip = tk.Frame(sched_box, bg=p.shell)
        rep_strip.pack(fill="x")
        make_modern_checkbox(
            rep_strip,
            text="All day" if is_en else "Cả ngày",
            variable=var_all_day,
            palette=p,
            parent_bg=p.shell,
        ).pack(side="left", padx=(0, 12))

        var_rep_lbl = tk.StringVar()
        cb_rep = make_pill_dropdown(
            rep_strip,
            var_rep_lbl,
            values=[],
            palette=p,
            parent_bg=p.shell,
            width_px=275,
            height=32,
        )
        cb_rep.pack(side="left")
        rep_lbl_to_key: dict[str, str] = {}
        rep_key_to_lbl: dict[str, str] = {}
        current_rep_key = [str(cur.get("repeat") or ("yearly" if existing_idx is None else "none"))]

        def _refresh_rep_options(*_a) -> None:
            try:
                d_val = date.fromisoformat(var_start_d.get().strip())
            except Exception:
                d_val = init_d
            opts = describe_repeat_options(d_val, self._lang())
            rep_lbl_to_key.clear()
            rep_key_to_lbl.clear()
            for k, lbl in opts:
                rep_lbl_to_key[lbl] = k
                rep_key_to_lbl[k] = lbl
            cb_rep.configure(values=[lbl for _, lbl in opts])
            var_rep_lbl.set(rep_key_to_lbl.get(current_rep_key[0], opts[0][1]))

        custom_row = tk.Frame(sched_box, bg=p.shell)
        var_c_int = tk.StringVar(value=str(int(cur.get("custom_interval", 1) or 1)))
        cfreq_pairs = (
            [("DAILY", "day(s)"), ("WEEKLY", "week(s)"), ("MONTHLY", "month(s)"), ("YEARLY", "year(s)")]
            if is_en
            else [("DAILY", "ngày"), ("WEEKLY", "tuần"), ("MONTHLY", "tháng"), ("YEARLY", "năm")]
        )
        cfreq_k2l = dict(cfreq_pairs)
        cfreq_l2k = {v: k for k, v in cfreq_pairs}
        var_c_freq = tk.StringVar(value=cfreq_k2l.get(str(cur.get("custom_freq") or "YEARLY").upper(), cfreq_pairs[3][1]))
        c_wd_vars = [tk.BooleanVar(value=(i in (cur.get("custom_weekdays") or []))) for i in range(7)]

        tk.Label(custom_row, text="Every" if is_en else "Mỗi", bg=p.shell, fg=p.muted, font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 6)
        )
        _, ent_cint = make_rounded_entry(
            custom_row, var_c_int, width_px=48, height=30, radius=8, fill=p.field, parent_bg=p.shell, fg=p.ink, insert_bg=p.accent, ph_fg=p.subtle, disabled_fg=p.subtle
        )
        ent_cint.master.pack(side="left", padx=(0, 6))
        cb_cfreq = make_pill_dropdown(
            custom_row,
            var_c_freq,
            values=[v for _, v in cfreq_pairs],
            palette=p,
            parent_bg=p.shell,
            width_px=96,
            height=30,
        )
        cb_cfreq.pack(side="left", padx=(0, 10))
        wd_frame = tk.Frame(custom_row, bg=p.shell)
        wd_lbls = EN_WEEKDAYS if is_en else VN_WEEKDAYS
        for wi, wlbl in enumerate(wd_lbls):
            make_modern_checkbox(wd_frame, text=wlbl, variable=c_wd_vars[wi], palette=p, parent_bg=p.shell).pack(
                side="left", padx=3
            )

        def _sync_rep_ui(*_a) -> None:
            sel_k = rep_lbl_to_key.get(var_rep_lbl.get(), current_rep_key[0])
            current_rep_key[0] = sel_k
            if sel_k == "custom":
                custom_row.pack(fill="x", pady=(8, 0))
                if cfreq_l2k.get(var_c_freq.get()) == "WEEKLY":
                    wd_frame.pack(side="left")
                else:
                    wd_frame.pack_forget()
            else:
                custom_row.pack_forget()

        cb_rep.bind("<<ComboboxSelected>>", _sync_rep_ui)
        cb_cfreq.bind("<<ComboboxSelected>>", _sync_rep_ui)
        _refresh_rep_options()
        _sync_rep_ui()

        # Elevated card ("Chi tiết sự kiện")
        card = tk.Frame(
            outer,
            bg=p.card,
            highlightbackground=p.border,
            highlightthickness=1,
            padx=18,
            pady=14,
        )
        card.pack(fill="both", expand=True)

        tab_bar = tk.Frame(card, bg=p.card)
        tab_bar.pack(fill="x")
        tab_lbl_wrap = tk.Frame(tab_bar, bg=p.card)
        tab_lbl_wrap.pack(side="left")
        tk.Label(
            tab_lbl_wrap,
            text="Event details" if is_en else "Chi tiết sự kiện",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
        ).pack(padx=4, pady=(0, 5))
        tk.Frame(tab_lbl_wrap, bg=p.accent, height=2).pack(fill="x")
        tk.Frame(card, bg=p.divider, height=1).pack(fill="x", pady=(0, 14))

        # Location row (no Google Meet row per user request)
        loc_row = tk.Frame(card, bg=p.card)
        loc_row.pack(fill="x", pady=(0, 12))
        tk.Label(loc_row, text="📍", bg=p.card, fg=p.muted, font=("Segoe UI", 12), width=3, anchor="w").pack(
            side="left"
        )
        _, ent_loc = make_rounded_entry(
            loc_row,
            var_loc,
            width_px=316,
            height=36,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            ph_fg=p.subtle,
            disabled_fg=p.subtle,
            placeholder="Add location" if is_en else "Thêm vị trí",
        )
        ent_loc.master.pack(side="left", padx=(4, 8))
        make_pill_button(
            loc_row,
            "Maps",
            lambda: webbrowser.open(_build_maps_url(read_entry_clean(ent_loc, var_loc))),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=14,
            height=34,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")
        make_info_button(
            loc_row,
            title="Event Location & Maps" if is_en else "Vị trí & Google Maps",
            message=(
                "• Leave empty & click 'Maps': opens Google Maps so you can look up a place and copy its address or link back here.\n\n"
                "• Type an address/place or paste a Google Maps link: click 'Maps' to preview it directly."
                if is_en
                else "• Khi ô vị trí đang trống: bấm 'Maps' sẽ mở thẳng Google Maps để bạn tìm địa điểm rồi copy địa chỉ hoặc link dán lại vào đây.\n\n"
                "• Khi đã nhập tên địa điểm, địa chỉ hoặc dán link Google Maps: bấm 'Maps' sẽ mở trực tiếp địa điểm đó."
            ),
            palette=p,
            parent_bg=p.card,
            size=22,
            ok_text="Got it" if is_en else "Đã hiểu",
        ).pack(side="left", padx=(6, 0))

        # Multi-notification rows + "+ Thêm thông báo"
        unit_pairs = (
            [("minutes", "minutes"), ("hours", "hours"), ("days", "days"), ("weeks", "weeks")]
            if is_en
            else [("minutes", "phút"), ("hours", "giờ"), ("days", "ngày"), ("weeks", "tuần")]
        )
        unit_key_to_lbl = dict(unit_pairs)
        unit_lbl_to_key = {v: k for k, v in unit_pairs}

        not_outer = tk.Frame(card, bg=p.card)
        not_outer.pack(fill="x", pady=(0, 12))
        tk.Label(not_outer, text="🔔", bg=p.card, fg=p.muted, font=("Segoe UI", 12), width=3, anchor="nw").pack(
            side="left", pady=(4, 0)
        )
        not_col = tk.Frame(not_outer, bg=p.card)
        not_col.pack(side="left", fill="x", expand=True, padx=(4, 0))
        not_rows_wrap = tk.Frame(not_col, bg=p.card)
        not_rows_wrap.pack(fill="x")

        notif_entries: list[dict] = []

        def _refresh_notif_visibility() -> None:
            is_ad = bool(var_all_day.get())
            for r in notif_entries:
                u_k = unit_lbl_to_key.get(r["unit_var"].get(), "days")
                need_at = is_ad or u_k in ("days", "weeks")
                if need_at:
                    r["at_lbl"].pack(side="left", padx=(6, 4))
                    r["at_shell"].pack(side="left")
                else:
                    r["at_lbl"].pack_forget()
                    r["at_shell"].pack_forget()
            if not notif_entries:
                lbl_no_notif.pack(anchor="w", pady=(4, 4))
            else:
                lbl_no_notif.pack_forget()

        def _add_notif_row(val_init: int = 1, unit_init: str = "days", at_init: str = "5:00PM") -> None:
            rf = tk.Frame(not_rows_wrap, bg=p.card)
            rf.pack(fill="x", pady=(0, 6))

            badge_img = make_rounded_rect_photo(rf, 96, 32, 8, p.field)
            badge = tk.Label(
                rf,
                text="Notify" if is_en else "Thông báo",
                image=badge_img,
                compound="center",
                bg=p.card,
                fg=p.ink,
                font=("Segoe UI", 10),
            )
            badge._pill_refs = (badge_img,)  # type: ignore[attr-defined]
            badge.pack(side="left")

            tk.Label(
                rf,
                text="before" if is_en else "trước",
                bg=p.card,
                fg=p.muted,
                font=("Segoe UI", 10),
            ).pack(side="left", padx=(8, 6))

            v_val = tk.StringVar(value=str(val_init))
            v_unit = tk.StringVar(value=unit_key_to_lbl.get(unit_init, unit_pairs[2][1]))
            v_at = tk.StringVar(value=at_init)

            val_shell, _ = make_rounded_entry(
                rf, v_val, width_px=48, height=32, radius=8, fill=p.field, parent_bg=p.card, fg=p.ink, insert_bg=p.accent, ph_fg=p.subtle, disabled_fg=p.subtle
            )
            val_shell.pack(side="left", padx=(0, 6))

            cb_u = make_pill_dropdown(
                rf,
                v_unit,
                values=[v for _, v in unit_pairs],
                palette=p,
                parent_bg=p.card,
                width_px=86,
                height=32,
            )
            cb_u.pack(side="left")
            cb_u.bind("<<ComboboxSelected>>", lambda _e: _refresh_notif_visibility())

            at_lbl = tk.Label(rf, text="at" if is_en else "lúc", bg=p.card, fg=p.muted, font=("Segoe UI", 10))
            at_shell, _ = make_rounded_entry(
                rf, v_at, width_px=82, height=32, radius=8, fill=p.field, parent_bg=p.card, fg=p.ink, insert_bg=p.accent, ph_fg=p.subtle, disabled_fg=p.subtle
            )

            row_rec = {
                "frame": rf,
                "val_var": v_val,
                "unit_var": v_unit,
                "at_var": v_at,
                "at_lbl": at_lbl,
                "at_shell": at_shell,
            }
            notif_entries.append(row_rec)

            def _rm_row(_e=None) -> None:
                if row_rec in notif_entries:
                    notif_entries.remove(row_rec)
                rf.destroy()
                _refresh_notif_visibility()

            btn_rm = tk.Label(
                rf,
                text="✕",
                bg=p.card,
                fg=p.muted,
                font=("Segoe UI", 10),
                padx=6,
                cursor="hand2",
            )
            btn_rm.pack(side="right")
            btn_rm.bind("<Enter>", lambda _e: btn_rm.configure(fg=p.danger_fg))
            btn_rm.bind("<Leave>", lambda _e: btn_rm.configure(fg=p.muted))
            btn_rm.bind("<Button-1>", _rm_row)
            _refresh_notif_visibility()

        lbl_no_notif = tk.Label(
            not_col,
            text="No notifications" if is_en else "Không có thông báo",
            bg=p.card,
            fg=p.subtle,
            font=("Segoe UI", 10),
        )

        init_rules = cur.get("notifications")
        if isinstance(init_rules, list):
            for nr in init_rules:
                if isinstance(nr, dict):
                    _add_notif_row(
                        int(nr.get("value", 1)),
                        str(nr.get("unit") or "days"),
                        str(nr.get("at") or "5:00PM"),
                    )
        elif bool(cur.get("notify_enabled", True)):
            def_u = str(cur.get("notify_unit") or ("days" if var_all_day.get() else "minutes"))
            def_v = int(cur.get("notify_value", 1 if var_all_day.get() else 15))
            def_at = str(cur.get("notify_at") or "5:00PM")
            _add_notif_row(def_v, def_u, def_at)
        else:
            _refresh_notif_visibility()

        btn_add_notif = tk.Label(
            not_col,
            text="+ Add notification" if is_en else "+ Thêm thông báo",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        btn_add_notif.pack(anchor="w", pady=(2, 0))
        btn_add_notif.bind(
            "<Button-1>",
            lambda _e: _add_notif_row(1 if var_all_day.get() else 15, "days" if var_all_day.get() else "minutes", "5:00PM"),
        )

        # Description / Notes multi-line soft field
        desc_row = tk.Frame(card, bg=p.card)
        desc_row.pack(fill="both", expand=True)
        tk.Label(desc_row, text="≡", bg=p.card, fg=p.muted, font=("Segoe UI", 13), width=3, anchor="nw").pack(
            side="left", pady=(4, 0)
        )
        notes_wrap = tk.Frame(desc_row, bg=p.field, padx=10, pady=8)
        notes_wrap.pack(side="left", fill="both", expand=True, padx=(4, 0))
        txt_notes = tk.Text(
            notes_wrap,
            height=4,
            width=44,
            bg=p.field,
            fg=p.ink,
            insertbackground=p.accent,
            font=("Segoe UI", 10),
            bd=0,
            relief="flat",
            highlightthickness=0,
            wrap="word",
        )
        txt_notes.pack(fill="both", expand=True)
        notes_ph = "Add description" if is_en else "Thêm nội dung mô tả"
        init_notes = str(cur.get("notes") or "")
        notes_ph_active = [False]
        if init_notes:
            txt_notes.insert("1.0", init_notes)
        else:
            notes_ph_active[0] = True
            txt_notes.insert("1.0", notes_ph)
            txt_notes.configure(fg=p.subtle)

        def _notes_focus_in(_e=None) -> None:
            if notes_ph_active[0]:
                notes_ph_active[0] = False
                txt_notes.delete("1.0", "end")
                txt_notes.configure(fg=p.ink)

        def _notes_focus_out(_e=None) -> None:
            if not txt_notes.get("1.0", "end-1c").strip():
                notes_ph_active[0] = True
                txt_notes.delete("1.0", "end")
                txt_notes.insert("1.0", notes_ph)
                txt_notes.configure(fg=p.subtle)

        txt_notes.bind("<FocusIn>", _notes_focus_in)
        txt_notes.bind("<FocusOut>", _notes_focus_out)

        def _sync_states(*_a) -> None:
            is_ad = bool(var_all_day.get())
            if is_ad:
                tm_wrap.pack_forget()
            else:
                tm_wrap.pack(side="left")
            _refresh_notif_visibility()

        var_all_day.trace_add("write", _sync_states)
        _sync_states()

        def _save_event() -> None:
            title_v = read_entry_clean(ent_title, var_title)
            if not title_v:
                messagebox.showwarning(
                    "Missing title" if is_en else "Thiếu tiêu đề",
                    "Please enter a title for the reminder/event." if is_en else "Vui lòng nhập tiêu đề sự kiện / nhắc nhở.",
                    parent=win,
                )
                return
            try:
                sd = date.fromisoformat(var_start_d.get().strip())
                ed = date.fromisoformat((var_end_d.get().strip() or sd.isoformat()))
            except ValueError:
                messagebox.showwarning(
                    "Invalid date" if is_en else "Sai định dạng ngày",
                    "Dates must be YYYY-MM-DD (e.g. 2026-12-02)." if is_en else "Ngày phải theo định dạng YYYY-MM-DD (ví dụ 2026-12-02).",
                    parent=win,
                )
                return
            if ed < sd:
                ed = sd

            all_day_v = bool(var_all_day.get())
            sh, sm = parse_clock_time(var_start_t.get(), (9, 0))
            eh, em = parse_clock_time(var_end_t.get(), ((sh + 1) % 24, sm))

            parsed_rules: list[dict] = []
            for r in notif_entries:
                try:
                    nv = max(0, min(999, int(r["val_var"].get().strip() or "0")))
                except ValueError:
                    messagebox.showwarning(
                        "Invalid number" if is_en else "Số thông báo sai",
                        "Notification lead value must be an integer." if is_en else "Giá trị nhắc trước phải là số nguyên.",
                        parent=win,
                    )
                    return
                rh, rm = parse_clock_time(r["at_var"].get(), (17, 0))
                parsed_rules.append(
                    {
                        "type": "notification",
                        "value": nv,
                        "unit": unit_lbl_to_key.get(r["unit_var"].get(), "days"),
                        "at": f"{rh:02d}:{rm:02d}",
                    }
                )

            first_rule = parsed_rules[0] if parsed_rules else {"value": 1, "unit": "days", "at": "17:00"}

            rep_k = rep_lbl_to_key.get(var_rep_lbl.get(), current_rep_key[0])
            try:
                c_int = max(1, min(999, int(var_c_int.get().strip() or "1")))
            except ValueError:
                c_int = 1
            c_freq = cfreq_l2k.get(var_c_freq.get(), "YEARLY")
            c_wds = [i for i, v in enumerate(c_wd_vars) if v.get()]
            rrule_str = build_rrule_from_preset(rep_k, sd, c_int, c_freq, c_wds)
            notes_val = "" if notes_ph_active[0] else txt_notes.get("1.0", "end-1c").strip()

            ev_dict = {
                "id": str(cur.get("id") or f"local-{uuid.uuid4().hex[:10]}"),
                "enabled": bool(cur.get("enabled", True)),
                "title": title_v,
                "start_date": sd.isoformat(),
                "end_date": ed.isoformat(),
                "all_day": all_day_v,
                "start_time": f"{sh:02d}:{sm:02d}",
                "end_time": f"{eh:02d}:{em:02d}",
                "repeat": rep_k,
                "custom_interval": c_int,
                "custom_freq": c_freq,
                "custom_weekdays": c_wds,
                "rrule": rrule_str,
                "location": read_entry_clean(ent_loc, var_loc),
                "notes": notes_val,
                "notifications": parsed_rules,
                "notify_enabled": bool(parsed_rules),
                "notify_value": int(first_rule["value"]),
                "notify_unit": str(first_rule["unit"]),
                "notify_at": str(first_rule["at"]),
            }

            updated = list(self.cfg.get("local_events", []))
            if existing_idx is not None and 0 <= existing_idx < len(updated):
                updated[existing_idx] = ev_dict
            else:
                updated.append(ev_dict)
            self.cfg["local_events"] = updated
            save_config(self.cfg)
            self._notified_reminders = {k for k in self._notified_reminders if ev_dict["id"] not in k}
            win.destroy()
            self._reload_local_calendar_now()
            if on_saved is not None:
                on_saved()

        save_action[0] = _save_event
        ent_title.focus_set()
        self._reveal_popup_window(win)

    def open_settings(
        self,
        draft: dict | None = None,
        restore_pos: tuple[int, int] | None = None,
    ) -> None:
        is_en = self._lang() == "en"
        if draft is None and self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            return
        if self._settings_win is not None and self._settings_win.winfo_exists():
            try:
                self._settings_win.destroy()
            except Exception:
                pass

        d_src = draft or {}
        style_labels = {
            "macos": "macOS (Apple)",
            "pixel": "Pixel (Material 3)",
            "xiaomi": "Xiaomi HyperOS",
            "botanical": "Ocean Calm",
            "serif": "Paper Serif",
            "sans": "Sans (E-Ink)",
        }
        style_swatches = {
            "macos": ("#FF3B30", "#007AFF", "#28C840"),
            "pixel": ("#6B5B95", "#D7F0E0", "#FDE5D7"),
            "xiaomi": ("#FF6900", "#1498D5", "#1F2430"),
            "botanical": ("#2B6E90", "#D8EAF4", "#5AA5CC"),
            "serif": ("#2B4C7E", "#EFE7D6", "#9E3B2B"),
            "sans": ("#1A1A1A", "#E8E8E4", "#C82829"),
        }
        style_sub_labels = {
            "macos": ("Apple Clean", "Gọn gàng kiểu Mac"),
            "pixel": ("Pastel Bento", "Bento đa sắc nhẹ"),
            "xiaomi": ("Hyper Glass", "Sắc nét HyperOS"),
            "botanical": ("Mist Blue", "Xanh dương dịu mắt"),
            "serif": ("Editorial Ink", "Báo giấy cổ điển"),
            "sans": ("Crisp E-Ink", "Tối giản tương phản"),
        }
        style_rev = {v: k for k, v in style_labels.items()}
        s_init = str(d_src.get("style", self.cfg.get("style", "serif"))).lower()
        if s_init == "esl":
            s_init = "sans"
        elif s_init not in style_labels:
            s_init = "serif"
        t_init = str(d_src.get("theme", self.cfg.get("theme", "auto"))).lower()
        if t_init not in ("auto", "system", "light", "dark"):
            t_init = "auto"

        active_tab_key = str(d_src.get("active_tab", "appearance"))
        if active_tab_key not in ("appearance", "personalize", "calendars", "system", "about"):
            active_tab_key = "appearance"

        p = self._dialog_palette(style_override=s_init, theme_override=t_init)
        cur_p = [p]

        win = tk.Toplevel(self.root)
        win.withdraw()
        self._settings_win = win
        win.title(f"Desk Widget Settings (v{APP_VERSION})" if is_en else f"Cài đặt Desk Widget (v{APP_VERSION})")
        win.configure(bg=p.shell)
        win.resizable(False, False)
        _set_window_icon(win, _active_icon_path(self.cfg))
        apply_modern_ttk_style(win, p)

        outer = tk.Frame(win, bg=p.shell, padx=18, pady=14)
        outer.pack(fill="both", expand=True)

        # Header Bar
        style_hdr = tk.Frame(outer, bg=p.shell)
        style_hdr.pack(fill="x", pady=(0, 12))
        dots_f = tk.Frame(style_hdr, bg=p.shell)
        dots_f._skip_retheme = True  # type: ignore[attr-defined]
        dot_lbls: list[tk.Label] = []
        for dc in ("#FF5F57", "#FEBC2E", "#28C840"):
            d_img = make_rounded_rect_photo(dots_f, 11, 11, 5, dc)
            dl = tk.Label(dots_f, image=d_img, bg=p.shell, bd=0, highlightthickness=0)
            dl._pill_refs = (d_img,)  # type: ignore[attr-defined]
            dl.pack(side="left", padx=2)
            dot_lbls.append(dl)
        if p.style == "macos":
            dots_f.pack(side="left", padx=(2, 10))
        lbl_hdr_title = tk.Label(
            style_hdr,
            text=("Settings" if is_en else "Cài đặt") + f" · {style_labels[s_init]}",
            bg=p.shell,
            fg=p.ink,
            font=("Segoe UI", 12, "bold"),
        )
        lbl_hdr_title.pack(side="left")
        badge_img = make_rounded_rect_photo(style_hdr, 84, 24, 12, p.tonal_bg)
        b_lbl = tk.Label(
            style_hdr,
            text="Dark" if p.is_dark else "Light",
            image=badge_img,
            compound="center",
            bg=p.shell,
            fg=p.tonal_fg,
            font=("Segoe UI", 9, "bold"),
        )
        b_lbl._pill_refs = (badge_img,)  # type: ignore[attr-defined]

        def _retheme_badge(_op, np: DialogPalette, _cm) -> None:
            nb = make_rounded_rect_photo(style_hdr, 84, 24, 12, np.tonal_bg)
            b_lbl._pill_refs = (nb,)  # type: ignore[attr-defined]
            b_lbl.configure(image=nb, bg=np.shell, fg=np.tonal_fg, text="Dark" if np.is_dark else "Light")

        b_lbl._retheme_fn = _retheme_badge  # type: ignore[attr-defined]
        b_lbl.pack(side="right")

        # Main Split: Left Sidebar + Right Content Card
        main_split = tk.Frame(outer, bg=p.shell)
        main_split.pack(fill="both", expand=True)

        sidebar = tk.Frame(main_split, bg=p.shell)
        sidebar.pack(side="left", fill="y", padx=(0, 14))

        content_card = tk.Frame(
            main_split,
            bg=p.card,
            highlightbackground=p.border,
            highlightthickness=1,
            width=588,
            height=406,
        )
        content_card.pack(side="left", fill="both", expand=True)

        # Declare all persistent settings state vars across all 4 tabs
        var_owner = tk.StringVar(value=str(d_src.get("owner_name", self.cfg.get("owner_name", "Desk Widget"))))
        align_labels = {"left": "Left", "center": "Center", "right": "Right"} if is_en else {"left": "Trái", "center": "Giữa", "right": "Phải"}
        align_rev = {v: k for k, v in align_labels.items()}
        var_align_set = tk.StringVar(
            value=align_labels.get(str(d_src.get("owner_align", self.cfg.get("owner_align", "center"))), align_labels["center"])
        )

        var_scale = tk.DoubleVar(value=float(d_src.get("scale", self.cfg.get("scale", 1.0))))
        var_style_set = tk.StringVar(value=style_labels[s_init])
        var_theme_set = tk.StringVar(value=t_init)
        var_temp_set = tk.StringVar(value=str(d_src.get("temp_unit", self.cfg.get("temp_unit", "C"))).upper())
        lang_labels = {"vi": "Tiếng Việt", "en": "English"}
        lang_rev = {v: k for k, v in lang_labels.items()}
        var_lang_set = tk.StringVar(value=lang_labels.get(str(d_src.get("language", self._lang())), "Tiếng Việt"))
        var_autostart_set = tk.BooleanVar(value=bool(d_src.get("auto_start", is_autostart_enabled())))
        var_topmost_set = tk.BooleanVar(value=bool(d_src.get("always_on_top", self.cfg.get("always_on_top", False))))

        raw_logo_mode = str(d_src.get("logo_mode", self.cfg.get("logo_mode", "widget_bg"))).lower()
        if raw_logo_mode == "wallpaper":
            raw_logo_mode = "widget_bg"
        logo_labels = (
            {"widget_bg": "Default", "custom": "Custom circle", "none": "Hidden"}
            if is_en
            else {"widget_bg": "Mặc định", "custom": "Ảnh riêng", "none": "Ẩn icon"}
        )
        logo_rev = {v: k for k, v in logo_labels.items()}
        var_logo_set = tk.StringVar(value=logo_labels.get(raw_logo_mode, logo_labels["widget_bg"]))

        logo_pos_labels = (
            {
                "before_title": "Left of title",
                "after_title": "Right of title",
                "far_left": "Top-left",
                "far_right": "Top-right",
            }
            if is_en
            else {
                "before_title": "Trái chữ",
                "after_title": "Phải chữ",
                "far_left": "Góc trái",
                "far_right": "Góc phải",
            }
        )
        logo_pos_rev = {v: k for k, v in logo_pos_labels.items()}
        raw_logo_pos = str(d_src.get("logo_pos", self.cfg.get("logo_pos", "before_title"))).lower()
        var_logo_pos = tk.StringVar(value=logo_pos_labels.get(raw_logo_pos, logo_pos_labels["before_title"]))

        rem_cfg = self.cfg.get("reminder") if isinstance(self.cfg.get("reminder"), dict) else {}
        var_rem_enabled = tk.BooleanVar(value=bool(d_src.get("rem_enabled", (rem_cfg or {}).get("enabled", True))))
        var_rem_mins = tk.StringVar(value=str(d_src.get("rem_mins", int((rem_cfg or {}).get("minutes_before", 15)))))
        var_rem_sound = tk.BooleanVar(value=bool(d_src.get("rem_sound", (rem_cfg or {}).get("sound", True))))

        w_cfg = self.cfg["weather"]
        var_auto_loc = tk.BooleanVar(value=bool(d_src.get("auto_location", w_cfg.get("auto_location", True))))
        var_city = tk.StringVar(value=str(d_src.get("city", w_cfg.get("city", "Hà Nội"))))
        var_lat = tk.StringVar(value=str(d_src.get("latitude", w_cfg.get("latitude", 21.0184))))
        var_lon = tk.StringVar(value=str(d_src.get("longitude", w_cfg.get("longitude", 105.8461))))
        var_tz = tk.StringVar(value=str(d_src.get("timezone", self.cfg.get("timezone", "Asia/Ho_Chi_Minh"))))
        tz_labels: dict[str, str] = {iana: lbl for iana, lbl in WORLD_TIMEZONES}
        cur_tz_id = var_tz.get().strip() or "Asia/Ho_Chi_Minh"
        if cur_tz_id not in tz_labels:
            tz_labels[cur_tz_id] = cur_tz_id
        tz_rev: dict[str, str] = {lbl: iana for iana, lbl in tz_labels.items()}
        var_tz_disp = tk.StringVar(value=tz_labels.get(cur_tz_id, cur_tz_id))

        cal_rows: list[dict] = []

        bg_mode_labels = (
            {"default": "Default (Per style)", "custom": "Custom background"}
            if is_en
            else {"default": "Mặc định theo Style", "custom": "Cá nhân hóa ảnh nền"}
        )
        bg_mode_rev = {v: k for k, v in bg_mode_labels.items()}
        raw_bg_mode = str(d_src.get("bg_mode", self._effective_bg_mode())).lower()
        var_bg_mode = tk.StringVar(value=bg_mode_labels.get(raw_bg_mode, bg_mode_labels["default"]))

        bg_pos_labels = (
            {
                "cover": "Fill center",
                "top": "Top",
                "bottom": "Bottom",
                "left": "Left panel",
                "right": "Right panel",
                "bottom_right": "Bottom-right",
            }
            if is_en
            else {
                "cover": "Phủ giữa",
                "top": "Canh trên",
                "bottom": "Canh dưới",
                "left": "Cột trái",
                "right": "Cột phải",
                "bottom_right": "Góc phải dưới",
            }
        )
        bg_pos_rev = {v: k for k, v in bg_pos_labels.items()}
        raw_bg_pos = str(d_src.get("bg_pos", self.cfg.get("bg_pos", "cover"))).lower()
        var_bg_pos = tk.StringVar(value=bg_pos_labels.get(raw_bg_pos, bg_pos_labels["cover"]))
        var_bg_tone = tk.StringVar(value=str(d_src.get("bg_tone", self.cfg.get("bg_tone", "original"))).lower())
        var_bg_zoom = tk.DoubleVar(value=float(d_src.get("bg_zoom", self.cfg.get("bg_zoom", 1.0))))
        var_bg_ox = tk.DoubleVar(value=float(d_src.get("bg_offset_x", self.cfg.get("bg_offset_x", 0.0))))
        var_bg_oy = tk.DoubleVar(value=float(d_src.get("bg_offset_y", self.cfg.get("bg_offset_y", 0.0))))
        var_bg_op = tk.DoubleVar(value=float(d_src.get("bg_opacity", self.cfg.get("bg_opacity", 0.55))))

        def _sync_media_fields(
            m=None,
            logo_pos=None,
            bg_pos=None,
            bg_mode=None,
            bg_tone=None,
            bg_zoom=None,
            bg_offset_x=None,
            bg_offset_y=None,
            bg_opacity=None,
        ) -> None:
            if m is not None and m in logo_labels:
                var_logo_set.set(logo_labels[m])
            if logo_pos is not None and logo_pos in logo_pos_labels:
                var_logo_pos.set(logo_pos_labels[logo_pos])
            if bg_pos is not None and bg_pos in bg_pos_labels:
                var_bg_pos.set(bg_pos_labels[bg_pos])
            if bg_tone is not None:
                var_bg_tone.set(str(bg_tone).lower())
            if bg_zoom is not None:
                var_bg_zoom.set(float(bg_zoom))
            if bg_offset_x is not None:
                var_bg_ox.set(float(bg_offset_x))
            if bg_offset_y is not None:
                var_bg_oy.set(float(bg_offset_y))
            if bg_opacity is not None:
                var_bg_op.set(float(bg_opacity))
            if bg_mode is not None and bg_mode in bg_mode_labels:
                var_bg_mode.set(bg_mode_labels[bg_mode])

        self._settings_logo_sync = _sync_media_fields
        win.bind("<Destroy>", lambda e: setattr(self, "_settings_logo_sync", None) if e.widget is win else None)

        def _sync_live_widget_preview(_e=None) -> None:
            self._preview_style = style_rev.get(var_style_set.get(), s_init)
            self._preview_theme = var_theme_set.get()
            try:
                self._preview_scale = float(var_scale.get())
            except Exception:
                self._preview_scale = None
            self._preview_align = align_rev.get(var_align_set.get(), "center")
            self._preview_logo_mode = logo_rev.get(var_logo_set.get(), "widget_bg")
            self._preview_logo_pos = logo_pos_rev.get(var_logo_pos.get(), "before_title")
            self._preview_bg_mode = bg_mode_rev.get(var_bg_mode.get(), "default")
            self._preview_bg_pos = bg_pos_rev.get(var_bg_pos.get(), "cover")
            self._preview_bg_tone = var_bg_tone.get()
            self._preview_bg_zoom = float(var_bg_zoom.get())
            self._preview_bg_offset_x = float(var_bg_ox.get())
            self._preview_bg_offset_y = float(var_bg_oy.get())
            self._preview_bg_opacity = float(var_bg_op.get())
            self._redraw_from_state()

        style_tile_refs: dict[str, dict] = {}

        def _refresh_appearance_badges() -> None:
            ap = cur_p[0]
            new_style = style_rev.get(var_style_set.get(), s_init)
            new_theme = var_theme_set.get()
            lbl_hdr_title.configure(text=("Settings" if is_en else "Cài đặt") + f" · {style_labels.get(new_style, new_style)}")
            prev_p = self._dialog_palette(style_override=new_style, theme_override=new_theme)
            b_lbl.configure(text="Dark" if prev_p.is_dark else "Light")
            cards_grid.configure(bg=ap.card)
            for sk, tref in style_tile_refs.items():
                is_sel = sk == new_style
                t_bg = ap.tonal_bg if is_sel else ap.field
                t_bd = ap.accent if is_sel else ap.border
                t_fg = ap.tonal_fg if is_sel else ap.ink
                s_fg = ap.tonal_fg if is_sel else ap.muted
                tref["tile"].configure(bg=t_bg, highlightbackground=t_bd, highlightthickness=2 if is_sel else 1)
                tref["sw_row"].configure(bg=t_bg)
                for sw_l in tref["sw_lbls"]:
                    sw_l.configure(bg=t_bg)
                tref["chk"].configure(text="✓" if is_sel else "", bg=t_bg, fg=ap.accent)
                tref["t_lbl"].configure(bg=t_bg, fg=t_fg)
                tref["s_lbl"].configure(bg=t_bg, fg=s_fg)

        def _live_switch_palette(_e=None) -> None:
            new_style = style_rev.get(var_style_set.get(), s_init)
            new_theme = var_theme_set.get()
            new_p = self._dialog_palette(style_override=new_style, theme_override=new_theme)
            old_p = cur_p[0]
            if new_p != old_p:
                retheme_dialog_tree(win, old_p, new_p)
                cur_p[0] = new_p
                dots_f.configure(bg=new_p.shell)
                for dl in dot_lbls:
                    dl.configure(bg=new_p.shell)
                if new_p.style == "macos":
                    if not dots_f.winfo_manager():
                        dots_f.pack(side="left", padx=(2, 10), before=lbl_hdr_title)
                else:
                    dots_f.pack_forget()
                sidebar.configure(bg=new_p.shell)
                for ni in nav_items.values():
                    cv = ni["canvas"]
                    nw_i = int(cv.cget("width"))
                    nh_i = int(cv.cget("height"))
                    n_idle = make_rounded_rect_photo(sidebar, nw_i, nh_i, 10, new_p.shell)
                    n_hover = make_rounded_rect_photo(sidebar, nw_i, nh_i, 10, new_p.field)
                    n_act = make_rounded_rect_photo(sidebar, nw_i, nh_i, 10, new_p.accent)
                    cv._nav_refs = (n_idle, n_hover, n_act)  # type: ignore[attr-defined]
                    cv.configure(bg=new_p.shell)
                    ni["img_idle"] = n_idle
                    ni["img_hover"] = n_hover
                    ni["img_active"] = n_act
                _select_tab(active_tab_key)
            _refresh_appearance_badges()
            _sync_live_widget_preview()

        def _cancel_settings(_e=None) -> None:
            self._clear_live_preview()
            try:
                win.destroy()
            except Exception:
                pass
            self._redraw_from_state()

        win.bind("<Escape>", _cancel_settings)
        win.protocol("WM_DELETE_WINDOW", _cancel_settings)

        # ── Tab Pages & Sidebar Navigation ───────────────────────────────────────
        tab_specs = (
            ("appearance", "Appearance" if is_en else "Giao diện"),
            ("personalize", "Title, Logo & Bg" if is_en else "Tiêu đề, Logo & Nền"),
            ("calendars", "Calendars" if is_en else "Lịch & Nhắc nhở"),
            ("system", "Weather & System" if is_en else "Thời tiết & Hệ thống"),
            ("about", "About" if is_en else "Giới thiệu"),
        )
        tab_pages: dict[str, tk.Frame] = {}
        nav_items: dict[str, dict] = {}

        for key, _lbl in tab_specs:
            pg = tk.Frame(content_card, bg=p.card, padx=18, pady=15)
            tab_pages[key] = pg

        sidebar._skip_retheme = True  # type: ignore[attr-defined]

        def _select_tab(key: str) -> None:
            nonlocal active_tab_key
            active_tab_key = key
            ap = cur_p[0]
            for k_it, pg_it in tab_pages.items():
                if k_it == key:
                    pg_it.pack(fill="both", expand=True)
                else:
                    pg_it.pack_forget()
            for k_it, ni in nav_items.items():
                is_act = k_it == key
                cv = ni["canvas"]
                cv.itemconfigure(ni["bg_id"], image=ni["img_active"] if is_act else ni["img_idle"])
                cv.itemconfigure(
                    ni["txt_id"],
                    fill=ap.accent_fg if is_act else ap.muted,
                    font=("Segoe UI", 10, "bold" if is_act else "normal"),
                )

        for key, nav_txt in tab_specs:
            nav_w, nav_h = 196, 38
            img_idle = make_rounded_rect_photo(sidebar, nav_w, nav_h, 10, p.shell)
            img_hover = make_rounded_rect_photo(sidebar, nav_w, nav_h, 10, p.field)
            img_active = make_rounded_rect_photo(sidebar, nav_w, nav_h, 10, p.accent)
            cv = tk.Canvas(
                sidebar,
                width=nav_w,
                height=nav_h,
                bg=p.shell,
                highlightthickness=0,
                bd=0,
                cursor="hand2",
            )
            bg_id = cv.create_image(0, 0, anchor="nw", image=img_idle)
            txt_id = cv.create_text(
                14,
                nav_h // 2,
                anchor="w",
                text=nav_txt,
                fill=p.muted,
                font=("Segoe UI", 10),
            )
            cv._nav_refs = (img_idle, img_hover, img_active)  # type: ignore[attr-defined]
            cv.pack(fill="x", pady=(0, 5))
            nav_items[key] = {
                "canvas": cv,
                "bg_id": bg_id,
                "txt_id": txt_id,
                "img_idle": img_idle,
                "img_hover": img_hover,
                "img_active": img_active,
            }
            cv.bind("<Button-1>", lambda _ev, k=key: _select_tab(k))
            cv.bind(
                "<Enter>",
                lambda _ev, k=key: nav_items[k]["canvas"].itemconfigure(nav_items[k]["bg_id"], image=nav_items[k]["img_hover"])
                if active_tab_key != k
                else None,
            )
            cv.bind(
                "<Leave>",
                lambda _ev, k=key: nav_items[k]["canvas"].itemconfigure(nav_items[k]["bg_id"], image=nav_items[k]["img_idle"])
                if active_tab_key != k
                else None,
            )

        # ── TAB 1: Appearance (6 Visual Style Cards + Dropdowns) ─────────────────
        pg_app = tab_pages["appearance"]
        tk.Label(
            pg_app,
            text="Widget & Settings Style" if is_en else "Phong cách Widget & Cài đặt",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        cards_grid = tk.Frame(pg_app, bg=p.card)
        cards_grid._skip_retheme = True  # type: ignore[attr-defined]
        cards_grid.pack(fill="x", pady=(0, 10))
        for col_idx in range(3):
            cards_grid.columnconfigure(col_idx, weight=1)

        def _pick_style_card(s_key: str) -> None:
            var_style_set.set(style_labels[s_key])
            _live_switch_palette()

        for idx, (s_key, s_title) in enumerate(style_labels.items()):
            r_i, c_i = divmod(idx, 3)
            is_cur = s_key == s_init
            tile_bg = p.tonal_bg if is_cur else p.field
            tile_bd = p.accent if is_cur else p.border
            tile_fg = p.tonal_fg if is_cur else p.ink
            sub_fg = p.tonal_fg if is_cur else p.muted
            sub_txt = style_sub_labels[s_key][0 if is_en else 1]

            tile = tk.Frame(
                cards_grid,
                bg=tile_bg,
                highlightbackground=tile_bd,
                highlightthickness=2 if is_cur else 1,
                padx=10,
                pady=6,
                cursor="hand2",
            )
            tile.grid(row=r_i, column=c_i, sticky="ew", padx=(0 if c_i == 0 else 6, 0 if c_i == 2 else 6), pady=(0, 6))

            sw_row = tk.Frame(tile, bg=tile_bg, cursor="hand2")
            sw_row.pack(fill="x", pady=(0, 4))
            sw_lbls: list[tk.Label] = []
            for sc in style_swatches[s_key]:
                sw_img = make_rounded_rect_photo(sw_row, 14, 14, 7, sc)
                sw_lbl = tk.Label(sw_row, image=sw_img, bg=tile_bg, bd=0, cursor="hand2")
                sw_lbl._pill_refs = (sw_img,)  # type: ignore[attr-defined]
                sw_lbl.pack(side="left", padx=(0, 4))
                sw_lbl.bind("<Button-1>", lambda _ev, k=s_key: _pick_style_card(k))
                sw_lbls.append(sw_lbl)
            chk_lbl = tk.Label(
                sw_row,
                text="✓" if is_cur else "",
                bg=tile_bg,
                fg=p.accent,
                font=("Segoe UI", 10, "bold"),
                cursor="hand2",
            )
            chk_lbl.pack(side="right")

            t_lbl = tk.Label(tile, text=s_title, bg=tile_bg, fg=tile_fg, font=("Segoe UI", 9, "bold"), anchor="w", cursor="hand2")
            t_lbl.pack(anchor="w")
            s_lbl = tk.Label(tile, text=sub_txt, bg=tile_bg, fg=sub_fg, font=("Segoe UI", 8), anchor="w", cursor="hand2")
            s_lbl.pack(anchor="w")

            style_tile_refs[s_key] = {
                "tile": tile,
                "sw_row": sw_row,
                "sw_lbls": sw_lbls,
                "chk": chk_lbl,
                "t_lbl": t_lbl,
                "s_lbl": s_lbl,
            }

            for w_part in (tile, sw_row, chk_lbl, t_lbl, s_lbl):
                w_part.bind("<Button-1>", lambda _ev, k=s_key: _pick_style_card(k))

        tk.Frame(pg_app, bg=p.divider, height=1).pack(fill="x", pady=(2, 14))

        tk.Label(
            pg_app,
            text="Display Options" if is_en else "Tùy chọn hiển thị",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        app_opts = tk.Frame(pg_app, bg=p.card)
        app_opts.pack(fill="x")
        app_opts.columnconfigure(1, weight=1)
        app_opts.columnconfigure(3, weight=1)

        tk.Label(app_opts, text="Theme:" if is_en else "Chế độ sáng/tối:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 10)
        )
        theme_cell = tk.Frame(app_opts, bg=p.card)
        theme_cell.grid(row=0, column=1, sticky="w", padx=(0, 14), pady=(0, 10))
        make_pill_dropdown(
            theme_cell,
            var_theme_set,
            values=["auto", "system", "light", "dark"],
            palette=p,
            parent_bg=p.card,
            width_px=130,
            height=32,
            command=lambda _v: _live_switch_palette(),
        ).pack(side="left")
        make_info_button(
            theme_cell,
            title="Light/Dark mode" if is_en else "Chế độ sáng/tối",
            message=(
                "• auto: follows sunrise and sunset at the widget's location (the same location & timezone used for weather). "
                "Light after sunrise, dark after sunset — it shifts automatically with the seasons.\n\n"
                "• system: follows the Windows/macOS light/dark setting.\n\n"
                "• light / dark: always light or always dark."
                if is_en
                else "• auto: theo giờ mặt trời mọc và lặn tại vị trí của widget (cùng vị trí & múi giờ dùng cho thời tiết). "
                "Sáng sau khi mặt trời mọc, tối sau khi mặt trời lặn — tự thay đổi theo mùa.\n\n"
                "• system: theo chế độ sáng/tối của Windows/macOS.\n\n"
                "• light / dark: luôn sáng hoặc luôn tối."
            ),
            palette=p,
            parent_bg=p.card,
            size=22,
            ok_text="Got it" if is_en else "Đã hiểu",
        ).pack(side="left", padx=(6, 0))

        tk.Label(app_opts, text="Scale:" if is_en else "Cỡ widget:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).grid(
            row=0, column=2, sticky="w", padx=(0, 8), pady=(0, 10)
        )
        make_pill_dropdown(
            app_opts,
            var_scale,
            values=["0.85", "1.0", "1.2", "1.25", "1.4"],
            palette=p,
            parent_bg=p.card,
            width_px=116,
            height=32,
            command=lambda _v: _sync_live_widget_preview(),
        ).grid(row=0, column=3, sticky="w", pady=(0, 10))

        tk.Label(app_opts, text="Temp:" if is_en else "Đơn vị nhiệt:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).grid(
            row=1, column=0, sticky="w", padx=(0, 8)
        )
        make_pill_dropdown(
            app_opts,
            var_temp_set,
            values=["C", "F"],
            palette=p,
            parent_bg=p.card,
            width_px=130,
            height=32,
        ).grid(row=1, column=1, sticky="w", padx=(0, 14))

        tk.Label(app_opts, text="Language:" if is_en else "Ngôn ngữ:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).grid(
            row=1, column=2, sticky="w", padx=(0, 8)
        )
        make_pill_dropdown(
            app_opts,
            var_lang_set,
            values=["Tiếng Việt", "English"],
            palette=p,
            parent_bg=p.card,
            width_px=116,
            height=32,
        ).grid(row=1, column=3, sticky="w")

        # ── TAB 2: Personalize (Header Title, Logo & Background) ─────────────────
        pg_per = tab_pages["personalize"]
        tk.Label(
            pg_per,
            text="Widget Header" if is_en else "Tiêu đề Widget",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        owner_row = tk.Frame(pg_per, bg=p.card)
        owner_row.pack(fill="x", pady=(0, 12))
        tk.Label(owner_row, text="Title:" if is_en else "Tên:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).pack(side="left")
        owner_shell, _ = make_rounded_entry(
            owner_row,
            var_owner,
            width_px=250,
            height=32,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            ph_fg=p.subtle,
            disabled_fg=p.subtle,
        )
        owner_shell.pack(side="left", padx=(8, 12))
        tk.Label(owner_row, text="Align:" if is_en else "Căn lề:", bg=p.card, fg=p.muted, font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 6)
        )
        make_pill_dropdown(
            owner_row,
            var_align_set,
            values=list(align_labels.values()),
            palette=p,
            parent_bg=p.card,
            width_px=112,
            height=32,
            command=lambda _v: _sync_live_widget_preview(),
        ).pack(side="left")

        tk.Frame(pg_per, bg=p.divider, height=1).pack(fill="x", pady=(2, 14))

        tk.Label(
            pg_per,
            text="Header Logo" if is_en else "Biểu tượng / Logo",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        logo_row = tk.Frame(pg_per, bg=p.card)
        logo_row.pack(fill="x", pady=(0, 14))
        var_logo_summary = tk.StringVar()
        tk.Label(
            logo_row,
            textvariable=var_logo_summary,
            bg=p.card,
            fg=p.ink,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(side="left")
        make_pill_button(
            logo_row,
            "Change logo & placement..." if is_en else "Đổi logo & vị trí...",
            self._choose_custom_logo,
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        tk.Frame(pg_per, bg=p.divider, height=1).pack(fill="x", pady=(2, 14))

        tk.Label(
            pg_per,
            text="Widget Background" if is_en else "Nền Widget",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        bg_row = tk.Frame(pg_per, bg=p.card)
        bg_row.pack(fill="x", pady=(0, 8))
        var_bg_summary = tk.StringVar()
        tk.Label(
            bg_row,
            textvariable=var_bg_summary,
            bg=p.card,
            fg=p.ink,
            font=("Segoe UI", 10),
            anchor="w",
        ).pack(side="left")
        make_pill_button(
            bg_row,
            "Change background & placement..." if is_en else "Đổi nền & vị trí...",
            self._choose_widget_bg,
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        def _refresh_media_summaries(*_a) -> None:
            lm_txt = var_logo_set.get()
            if logo_rev.get(lm_txt, "widget_bg") == "none":
                var_logo_summary.set(lm_txt)
            else:
                var_logo_summary.set(f"{lm_txt} · {var_logo_pos.get()}")
            bm_txt = var_bg_mode.get()
            if bg_mode_rev.get(bm_txt, "default") == "default":
                var_bg_summary.set(bm_txt)
            else:
                t_lbl = ("Negative" if is_en else "Âm bản") if var_bg_tone.get() == "negative" else ("Original" if is_en else "Ảnh gốc")
                op_p = int(round(float(var_bg_op.get()) * 100))
                var_bg_summary.set(f"{bm_txt} · {t_lbl} · {op_p}%")

        for _mv in (var_logo_set, var_logo_pos, var_bg_mode, var_bg_pos, var_bg_tone, var_bg_zoom, var_bg_op):
            _mv.trace_add("write", _refresh_media_summaries)
        _refresh_media_summaries()

        # ── TAB 3: Calendars & Reminders ─────────────────────────────────────────
        pg_cal = tab_pages["calendars"]
        hdr_cal = tk.Frame(pg_cal, bg=p.card)
        hdr_cal.pack(fill="x", pady=(0, 4))
        tk.Label(
            hdr_cal,
            text="Calendars (.ics links)" if is_en else "Danh sách lịch (.ics)",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        make_info_button(
            hdr_cal,
            title="How to get an .ics link" if is_en else "Cách lấy link lịch (.ics)",
            message=(
                "• Google Calendar (web): Settings → select a calendar on the left → Integrate calendar → copy 'Secret address in iCal format' (.ics).\n\n"
                "• Outlook / Apple Calendar: copy the published iCal/ICS link, or paste a local .ics file path directly."
                if is_en
                else "• Google Calendar (máy tính): Cài đặt → chọn lịch bên trái → Tích hợp lịch → sao chép 'Địa chỉ bí mật ở định dạng iCal' (.ics).\n\n"
                "• Outlook / Apple Calendar: sao chép link chia sẻ iCal/ICS, hoặc dán đường dẫn file .ics lưu trên máy."
            ),
            palette=p,
            parent_bg=p.card,
            size=22,
            ok_text="Got it" if is_en else "Đã hiểu",
        ).pack(side="left", padx=(6, 0))

        tk.Label(
            pg_cal,
            text=(
                "Secret/public .ics URLs, Google Calendar embed URLs, or local .ics files"
                if is_en
                else "Hỗ trợ link .ics bí mật, công khai, Google embed URL hoặc file .ics trên máy"
            ),
            bg=p.card,
            fg=p.muted,
            font=("Segoe UI", 9),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        col_hdr = tk.Frame(pg_cal, bg=p.card)
        col_hdr.pack(fill="x", pady=(0, 2))
        tk.Label(col_hdr, text="On" if is_en else "Bật", width=3, bg=p.card, fg=p.subtle, font=("Segoe UI", 9), anchor="w").pack(
            side="left"
        )
        tk.Label(col_hdr, text="Name" if is_en else "Tên lịch", width=15, bg=p.card, fg=p.subtle, font=("Segoe UI", 9), anchor="w").pack(
            side="left", padx=(4, 4)
        )
        tk.Label(col_hdr, text="Calendar URL / .ics path" if is_en else "Link URL / .ics", bg=p.card, fg=p.subtle, font=("Segoe UI", 9), anchor="w").pack(
            side="left"
        )

        cal_scroll_wrap = tk.Frame(pg_cal, bg=p.card, height=144)
        cal_scroll_wrap.pack(fill="x", pady=(0, 6))
        cal_scroll_wrap.pack_propagate(False)
        cal_canvas = tk.Canvas(cal_scroll_wrap, bg=p.card, highlightthickness=0, bd=0)
        cal_canvas.pack(side="left", fill="both", expand=True)
        cal_list_frame = tk.Frame(cal_canvas, bg=p.card)
        cal_win_id = cal_canvas.create_window((0, 0), window=cal_list_frame, anchor="nw")
        cal_list_frame.bind("<Configure>", lambda _e: cal_canvas.configure(scrollregion=cal_canvas.bbox("all")))
        cal_canvas.bind("<Configure>", lambda e: cal_canvas.itemconfigure(cal_win_id, width=e.width))

        def _on_cal_wheel(ev: tk.Event) -> None:
            units = mousewheel_units(int(getattr(ev, "delta", 0) or 0))
            if units:
                cal_canvas.yview_scroll(units, "units")

        cal_canvas.bind("<MouseWheel>", _on_cal_wheel)
        cal_list_frame.bind("<MouseWheel>", _on_cal_wheel)

        def _add_cal_row(name_val: str = "", url_val: str = "", enabled_val: bool = True) -> None:
            row_f = tk.Frame(cal_list_frame, bg=p.card)
            row_f.pack(fill="x", pady=3)
            row_f.bind("<MouseWheel>", _on_cal_wheel)
            v_en = tk.BooleanVar(value=enabled_val)
            v_name = tk.StringVar(value=name_val)
            v_url = tk.StringVar(value=url_val)

            make_modern_checkbox(row_f, text="", variable=v_en, palette=p, parent_bg=p.card).pack(side="left", padx=(0, 6))
            n_shell, _ = make_rounded_entry(
                row_f,
                v_name,
                width_px=118,
                height=30,
                radius=8,
                fill=p.field,
                parent_bg=p.card,
                fg=p.ink,
                insert_bg=p.accent,
                ph_fg=p.subtle,
                disabled_fg=p.subtle,
            )
            n_shell.pack(side="left", padx=(0, 8))
            u_shell, _ = make_rounded_entry(
                row_f,
                v_url,
                width_px=316,
                height=30,
                radius=8,
                fill=p.field,
                parent_bg=p.card,
                fg=p.ink,
                insert_bg=p.accent,
                ph_fg=p.subtle,
                disabled_fg=p.subtle,
                font=("Consolas", 9),
            )
            u_shell.pack(side="left", padx=(0, 8))

            def _remove() -> None:
                cal_rows.remove(entry)
                row_f.destroy()

            make_pill_button(
                row_f,
                "Del" if is_en else "Xóa",
                _remove,
                bg=p.danger_bg,
                fg=p.danger_fg,
                hover_bg=p.danger_hover,
                parent_bg=p.card,
                pad_x=11,
                height=28,
                radius=8,
                font=("Segoe UI", 9, "bold"),
            ).pack(side="left")
            entry = {"frame": row_f, "enabled": v_en, "name": v_name, "url": v_url}
            cal_rows.append(entry)

        existing_cals = d_src["calendars"] if "calendars" in d_src else self.cfg.get("calendars", [])
        if existing_cals:
            for c in existing_cals:
                _add_cal_row(
                    name_val=str(c.get("name") or ""),
                    url_val=str(c.get("url") or ""),
                    enabled_val=bool(c.get("enabled", True)),
                )
        else:
            _add_cal_row(name_val="Personal" if is_en else "Cá nhân", url_val="", enabled_val=True)

        make_pill_button(
            hdr_cal,
            "+ Add calendar" if is_en else "+ Thêm link lịch",
            lambda: _add_cal_row(name_val=f"Cal {len(cal_rows) + 1}" if is_en else f"Lịch {len(cal_rows) + 1}", url_val="", enabled_val=True),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=12,
            height=28,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        tk.Frame(pg_cal, bg=p.divider, height=1).pack(fill="x", pady=(2, 10))

        tk.Label(
            pg_cal,
            text="Reminders" if is_en else "Nhắc nhở sự kiện",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 6))

        rem_row = tk.Frame(pg_cal, bg=p.card)
        rem_row.pack(fill="x", pady=(0, 8))
        make_modern_checkbox(
            rem_row,
            text="Remind before:" if is_en else "Nhắc trước:",
            variable=var_rem_enabled,
            palette=p,
            parent_bg=p.card,
        ).pack(side="left")
        cb_rem_mins = make_pill_dropdown(
            rem_row,
            var_rem_mins,
            values=["0", "5", "10", "15", "20", "30", "45", "60"],
            palette=p,
            parent_bg=p.card,
            width_px=74,
            height=30,
        )
        cb_rem_mins.pack(side="left", padx=(8, 6))
        tk.Label(rem_row, text="min" if is_en else "phút", bg=p.card, fg=p.muted, font=("Segoe UI", 10)).pack(
            side="left", padx=(0, 14)
        )
        chk_rem_sound = make_modern_checkbox(
            rem_row,
            text="Sound" if is_en else "Âm báo",
            variable=var_rem_sound,
            palette=p,
            parent_bg=p.card,
        )
        chk_rem_sound.pack(side="left")

        rem_btn_row = tk.Frame(pg_cal, bg=p.card)
        rem_btn_row.pack(fill="x")
        make_pill_button(
            rem_btn_row,
            "Custom Reminders..." if is_en else "Quản lý nhắc lịch cá nhân...",
            self._open_reminders_manager,
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        def _sync_rem_state(*_args) -> None:
            st = "normal" if var_rem_enabled.get() else "disabled"
            cb_rem_mins.configure(state=st)
            chk_rem_sound.configure(state=st)

        var_rem_enabled.trace_add("write", _sync_rem_state)
        _sync_rem_state()

        # ── TAB 4: Weather & System ──────────────────────────────────────────────
        pg_sys = tab_pages["system"]
        tk.Label(
            pg_sys,
            text="Weather & Timezone (Open-Meteo)" if is_en else "Thời tiết & Múi giờ (Open-Meteo)",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        auto_loc_row = tk.Frame(pg_sys, bg=p.card)
        auto_loc_row.pack(fill="x", pady=(0, 10))
        make_modern_checkbox(
            auto_loc_row,
            text=(
                "Auto-detect location & timezone via IP (uncheck to edit manually)"
                if is_en
                else "Tự động lấy vị trí & múi giờ theo IP (bỏ chọn để tự sửa)"
            ),
            variable=var_auto_loc,
            palette=p,
            parent_bg=p.card,
        ).pack(side="left")
        make_info_button(
            auto_loc_row,
            title="IP Location & City Lookup" if is_en else "Định vị IP & Tìm tọa độ",
            message=(
                "• IP auto-detection estimates your city from your internet provider, which can sometimes point to a nearby province or ISP hub.\n\n"
                "• For exact local weather: uncheck this option, type your city name (e.g. Hanoi, Tokyo), then click 'Find coordinates' or press Enter to update lat/lon and timezone."
                if is_en
                else "• Định vị theo IP lấy vị trí ước lượng theo nhà mạng (đôi khi bị lệch sang tỉnh lân cận hoặc điểm đặt máy chủ).\n\n"
                "• Để thời tiết chính xác đúng khu vực: bỏ chọn ô này, nhập tên thành phố rồi bấm 'Tìm tọa độ' (hoặc nhấn Enter) để tự cập nhật vĩ độ, kinh độ và múi giờ."
            ),
            palette=p,
            parent_bg=p.card,
            size=22,
            ok_text="Got it" if is_en else "Đã hiểu",
        ).pack(side="left", padx=(6, 0))

        city_row = tk.Frame(pg_sys, bg=p.card)
        city_row.pack(fill="x", pady=(0, 10))
        tk.Label(city_row, text="City:" if is_en else "Thành phố:", bg=p.card, fg=p.ink, font=("Segoe UI", 10)).pack(
            side="left"
        )
        city_shell, ent_city = make_rounded_entry(
            city_row,
            var_city,
            width_px=235,
            height=32,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            ph_fg=p.subtle,
            disabled_fg=p.subtle,
        )
        city_shell.pack(side="left", padx=(8, 10))
        ent_city.bind("<Return>", lambda _e: _lookup_city())

        def _set_tz_selection(tz_id: str) -> None:
            clean_id = (tz_id or "").strip()
            if not clean_id:
                return
            if clean_id not in tz_labels:
                tz_labels[clean_id] = clean_id
                tz_rev[clean_id] = clean_id
                cb_tz.configure(values=list(tz_labels.values()))
            var_tz.set(clean_id)
            var_tz_disp.set(tz_labels[clean_id])

        def _lookup_city() -> None:
            if bool(var_auto_loc.get()):
                return
            res = geocode_city_with_tz(var_city.get())
            if res:
                name, lat, lon, tz_id = res
                var_city.set(name)
                var_lat.set(f"{lat:.4f}")
                var_lon.set(f"{lon:.4f}")
                if tz_id:
                    _set_tz_selection(tz_id)
            else:
                messagebox.showwarning(
                    "Not found" if is_en else "Không tìm thấy",
                    "Could not resolve coordinates for this city." if is_en else "Không tìm thấy tọa độ thành phố này.",
                    parent=win,
                )

        btn_lookup = make_pill_button(
            city_row,
            "Find coordinates" if is_en else "Tìm tọa độ",
            _lookup_city,
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        )
        btn_lookup.pack(side="left")

        coord_row = tk.Frame(pg_sys, bg=p.card)
        coord_row.pack(fill="x", pady=(0, 8))
        tk.Label(coord_row, text="Lat:" if is_en else "Vĩ độ:", bg=p.card, fg=p.muted, font=("Segoe UI", 10)).pack(side="left")
        lat_shell, ent_lat = make_rounded_entry(
            coord_row,
            var_lat,
            width_px=116,
            height=32,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            ph_fg=p.subtle,
            disabled_fg=p.subtle,
        )
        lat_shell.pack(side="left", padx=(8, 16))
        tk.Label(coord_row, text="Lon:" if is_en else "Kinh độ:", bg=p.card, fg=p.muted, font=("Segoe UI", 10)).pack(side="left")
        lon_shell, ent_lon = make_rounded_entry(
            coord_row,
            var_lon,
            width_px=116,
            height=32,
            radius=8,
            fill=p.field,
            parent_bg=p.card,
            fg=p.ink,
            insert_bg=p.accent,
            ph_fg=p.subtle,
            disabled_fg=p.subtle,
        )
        lon_shell.pack(side="left", padx=(8, 0))

        tz_row = tk.Frame(pg_sys, bg=p.card)
        tz_row.pack(fill="x", pady=(0, 12))
        tk.Label(tz_row, text="Timezone:" if is_en else "Múi giờ:", bg=p.card, fg=p.muted, font=("Segoe UI", 10)).pack(side="left")
        cb_tz = make_pill_dropdown(
            tz_row,
            var_tz_disp,
            values=list(tz_labels.values()),
            palette=p,
            parent_bg=p.card,
            width_px=340,
            height=32,
            max_visible_items=10,
            menu_width=340,
            command=lambda chosen_lbl: var_tz.set(tz_rev.get(chosen_lbl, var_tz.get())),
        )
        cb_tz.pack(side="left", padx=(8, 0))

        def _sync_loc_state(*_args) -> None:
            disabled = bool(var_auto_loc.get())
            state = "disabled" if disabled else "normal"
            for w_item in (ent_city, ent_lat, ent_lon, cb_tz):
                w_item.configure(state=state)
            btn_lookup._enabled = not disabled  # type: ignore[attr-defined]
            btn_lookup.configure(
                fg=p.subtle if disabled else p.tonal_fg,
                cursor="arrow" if disabled else "hand2",
            )

        var_auto_loc.trace_add("write", _sync_loc_state)
        _sync_loc_state()

        tk.Frame(pg_sys, bg=p.divider, height=1).pack(fill="x", pady=(2, 14))

        tk.Label(
            pg_sys,
            text="System & Window" if is_en else "Hệ thống & Cửa sổ",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))

        sys_chk_row = tk.Frame(pg_sys, bg=p.card)
        sys_chk_row.pack(fill="x", pady=(0, 12))
        if is_en:
            autostart_set_lbl = "Auto-start on macOS login" if IS_MACOS else "Auto-start on Windows login"
        else:
            autostart_set_lbl = "Tự mở cùng macOS" if IS_MACOS else "Tự mở cùng Windows"
        make_modern_checkbox(sys_chk_row, text=autostart_set_lbl, variable=var_autostart_set, palette=p, parent_bg=p.card).pack(
            side="left", padx=(0, 20)
        )
        make_modern_checkbox(
            sys_chk_row,
            text="Always on top" if is_en else "Luôn nổi trên cùng",
            variable=var_topmost_set,
            palette=p,
            parent_bg=p.card,
        ).pack(side="left")

        sys_btn_row = tk.Frame(pg_sys, bg=p.card)
        sys_btn_row.pack(fill="x")
        make_pill_button(
            sys_btn_row,
            "Send behind" if is_en else "Ẩn ra sau ngay",
            lambda: (var_topmost_set.set(False), self._send_to_back()),
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 10))
        make_pill_button(
            sys_btn_row,
            "Change App Icon..." if is_en else "Đổi icon app...",
            self._change_icon,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.card,
            pad_x=14,
            height=30,
            radius=8,
            font=("Segoe UI", 9),
        ).pack(side="left")

        # ── TAB 5: About & Author ────────────────────────────────────────────────
        pg_about = tab_pages["about"]
        about_top = tk.Frame(pg_about, bg=p.card)
        about_top.pack(fill="x", pady=(0, 8))
        tk.Label(
            about_top,
            text=f"Desk Widget  v{APP_VERSION}",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        lic_img = make_rounded_rect_photo(about_top, 92, 24, 12, p.tonal_bg)
        lic_lbl = tk.Label(
            about_top,
            text=APP_LICENSE,
            image=lic_img,
            compound="center",
            bg=p.card,
            fg=p.tonal_fg,
            font=("Segoe UI", 8, "bold"),
        )
        lic_lbl._pill_refs = (lic_img,)  # type: ignore[attr-defined]

        def _retheme_lic(_op, np: DialogPalette, _cm) -> None:
            nl = make_rounded_rect_photo(about_top, 92, 24, 12, np.tonal_bg)
            lic_lbl._pill_refs = (nl,)  # type: ignore[attr-defined]
            lic_lbl.configure(image=nl, bg=np.card, fg=np.tonal_fg)

        lic_lbl._retheme_fn = _retheme_lic  # type: ignore[attr-defined]
        lic_lbl.pack(side="left", padx=(10, 0))

        tk.Label(
            pg_about,
            text=(
                "Lightweight cross-platform desktop widget (Windows & macOS) that brings Google/ICS calendars, smart local reminders, 7-day weather forecasts, and live RAM/CPU/GPU stats directly onto your desktop in 6 Light/Dark styles."
                if is_en
                else "Widget desktop gọn nhẹ cho Windows & macOS, hiển thị trực quan lịch Google/ICS, nhắc lịch cá nhân thông minh, dự báo thời tiết 7 ngày và giám sát hiệu năng RAM/CPU/GPU với 6 phong cách Light/Dark đồng bộ."
            ),
            bg=p.card,
            fg=p.ink,
            font=("Segoe UI", 9),
            anchor="w",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        tk.Label(
            pg_about,
            text=(
                '"A small, open-source passion project built for fun and non-commercial use."'
                if is_en
                else '"Một dự án cá nhân nhỏ được làm vì sở thích, mã nguồn mở và không vì mục đích thương mại."'
            ),
            bg=p.card,
            fg=p.muted,
            font=("Segoe UI", 9, "italic"),
            anchor="w",
            wraplength=520,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))

        tk.Frame(pg_about, bg=p.divider, height=1).pack(fill="x", pady=(0, 14))

        tk.Label(
            pg_about,
            text="Author & Links" if is_en else "Tác giả & Liên hệ",
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        ).pack(anchor="w", pady=(0, 8))

        auth_row = tk.Frame(pg_about, bg=p.card)
        auth_row.pack(fill="x", pady=(0, 8))
        tk.Label(auth_row, text="Author:" if is_en else "Tác giả:", width=9, bg=p.card, fg=p.muted, font=("Segoe UI", 10), anchor="w").pack(
            side="left"
        )
        tk.Label(
            auth_row,
            text=f"Phúc Trần ({APP_AUTHOR})",
            bg=p.card,
            fg=p.ink,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")

        gh_row = tk.Frame(pg_about, bg=p.card)
        gh_row.pack(fill="x", pady=(0, 8))
        tk.Label(gh_row, text="GitHub:", width=9, bg=p.card, fg=p.muted, font=("Segoe UI", 10), anchor="w").pack(side="left")
        gh_link = tk.Label(
            gh_row,
            text=GITHUB_PROFILE_URL,
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "underline"),
            cursor="hand2",
        )
        gh_link.pack(side="left")
        gh_link.bind("<Button-1>", lambda _e: webbrowser.open(GITHUB_PROFILE_URL))
        make_pill_button(
            gh_row,
            "Open GitHub" if is_en else "Mở GitHub",
            lambda: webbrowser.open(GITHUB_PROFILE_URL),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=12,
            height=28,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        mail_row = tk.Frame(pg_about, bg=p.card)
        mail_row.pack(fill="x", pady=(0, 14))
        tk.Label(mail_row, text="Email:", width=9, bg=p.card, fg=p.muted, font=("Segoe UI", 10), anchor="w").pack(side="left")
        mail_link = tk.Label(
            mail_row,
            text=APP_EMAIL,
            bg=p.card,
            fg=p.accent,
            font=("Segoe UI", 10, "underline"),
            cursor="hand2",
        )
        mail_link.pack(side="left")
        mail_link.bind("<Button-1>", lambda _e: webbrowser.open(f"mailto:{APP_EMAIL}"))

        def _copy_email() -> None:
            try:
                win.clipboard_clear()
                win.clipboard_append(APP_EMAIL)
                win.update()
                btn_copy_mail.configure(text="✓ OK")
                win.after(1600, lambda: btn_copy_mail.configure(text="Copy" if is_en else "Sao chép") if win.winfo_exists() else None)
            except Exception:
                pass

        btn_copy_mail = make_pill_button(
            mail_row,
            "Copy" if is_en else "Sao chép",
            _copy_email,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.card,
            pad_x=12,
            height=28,
            radius=8,
            font=("Segoe UI", 9),
        )
        btn_copy_mail.pack(side="right", padx=(6, 0))
        make_pill_button(
            mail_row,
            "Send Email" if is_en else "Gửi Mail",
            lambda: webbrowser.open(f"mailto:{APP_EMAIL}"),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=12,
            height=28,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right")

        tk.Frame(pg_about, bg=p.divider, height=1).pack(fill="x", pady=(0, 14))

        upd_about_row = tk.Frame(pg_about, bg=p.card)
        upd_about_row.pack(fill="x")
        make_pill_button(
            upd_about_row,
            f"Check for updates (v{APP_VERSION})..." if is_en else f"Kiểm tra cập nhật (v{APP_VERSION})...",
            lambda: self._check_updates_async(silent=False),
            bg=p.tonal_bg,
            fg=p.tonal_fg,
            hover_bg=p.tonal_hover,
            parent_bg=p.card,
            pad_x=16,
            height=30,
            radius=8,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left")

        win.update_idletasks()
        max_tab_w = max((pg.winfo_reqwidth() for pg in tab_pages.values()), default=588)
        max_tab_h = max((pg.winfo_reqheight() for pg in tab_pages.values()), default=406)
        content_card.configure(width=max(588, max_tab_w + 16), height=max(418, max_tab_h + 18))
        content_card.pack_propagate(False)

        _select_tab(active_tab_key)

        # Footer Bar
        btn_row = tk.Frame(outer, bg=p.shell)
        btn_row.pack(fill="x", pady=(12, 0))
        lbl_copy = tk.Label(
            btn_row,
            text=f"Desk Widget v{APP_VERSION} · {APP_COPYRIGHT} ({APP_LICENSE})",
            bg=p.shell,
            fg=p.subtle,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        lbl_copy.pack(side="left")
        lbl_copy.bind("<Button-1>", lambda _e: webbrowser.open(REPO_URL))

        def _save() -> None:
            new_cals: list[dict] = []
            for idx, r in enumerate(cal_rows):
                u = r["url"].get().strip()
                nm = r["name"].get().strip() or f"Lịch {idx + 1}"
                en = bool(r["enabled"].get())
                if not u:
                    continue
                if "•" in u:
                    _select_tab("calendars")
                    messagebox.showwarning(
                        "Link .ics bị che",
                        f"Link của [{nm}] đang chứa dấu che (••••).\n\n"
                        "Trên Google Calendar, hãy bấm nút Con mắt (Hiện) hoặc nút Sao chép bên phải ô link iCal.",
                        parent=win,
                    )
                    return
                if not (u.lower().startswith(("http://", "https://", "webcal://")) or os.path.exists(u)):
                    _select_tab("calendars")
                    messagebox.showwarning(
                        "Link không hợp lệ",
                        f"Link của [{nm}] phải bắt đầu bằng https://, webcal:// hoặc là đường dẫn file .ics tồn tại trên máy.",
                        parent=win,
                    )
                    return
                new_cals.append({"name": nm, "url": u, "enabled": en})

            try:
                rem_mins = int(var_rem_mins.get().strip())
                if not (0 <= rem_mins <= 240):
                    raise ValueError
            except ValueError:
                _select_tab("calendars")
                messagebox.showerror(
                    "Invalid reminder" if is_en else "Thời gian nhắc không hợp lệ",
                    "Reminder lead time must be an integer from 0 to 240 minutes."
                    if is_en
                    else "Số phút nhắc trước phải là số nguyên từ 0 đến 240.",
                    parent=win,
                )
                return

            prev_rem = self.cfg.get("reminder") if isinstance(self.cfg.get("reminder"), dict) else {}
            new_rem = {
                "enabled": bool(var_rem_enabled.get()),
                "minutes_before": rem_mins,
                "sound": bool(var_rem_sound.get()),
            }
            self.cfg["owner_name"] = var_owner.get().strip() or "Desk Widget"
            self.cfg["owner_align"] = align_rev.get(var_align_set.get(), "center")
            if hasattr(self, "var_align"):
                self.var_align.set(self.cfg["owner_align"])
            self.cfg["calendars"] = new_cals
            self.cfg["reminder"] = new_rem
            if (
                bool((prev_rem or {}).get("enabled", True)) != new_rem["enabled"]
                or int((prev_rem or {}).get("minutes_before", 15)) != rem_mins
            ):
                self._notified_reminders.clear()
                self._snooze_reminders.clear()
            self.cfg["weather"]["auto_location"] = bool(var_auto_loc.get())
            try:
                self.cfg["weather"]["city"] = var_city.get().strip() or "Hà Nội"
                self.cfg["weather"]["latitude"] = float(var_lat.get())
                self.cfg["weather"]["longitude"] = float(var_lon.get())
            except ValueError:
                _select_tab("system")
                messagebox.showerror("Lỗi", "Latitude/Longitude phải là số hợp lệ.", parent=win)
                return
            tz_val = tz_rev.get(var_tz_disp.get(), var_tz.get()).strip()
            if not var_auto_loc.get():
                if not tz_val or tz.gettz(tz_val) is None:
                    _select_tab("system")
                    messagebox.showerror(
                        "Lỗi",
                        "Múi giờ không hợp lệ (hãy chọn từ danh sách múi giờ).",
                        parent=win,
                    )
                    return
                self.cfg["timezone"] = tz_val
            self.cfg["scale"] = float(var_scale.get())
            self.cfg["style"] = style_rev.get(var_style_set.get(), "serif")
            if hasattr(self, "var_style"):
                self.var_style.set(self.cfg["style"])
            self.cfg["theme"] = var_theme_set.get()
            if hasattr(self, "var_theme"):
                self.var_theme.set(self.cfg["theme"])
            self.cfg["temp_unit"] = str(var_temp_set.get() or "C").upper()
            if hasattr(self, "var_temp_unit"):
                self.var_temp_unit.set(self.cfg["temp_unit"])
            self.cfg["language"] = lang_rev.get(var_lang_set.get(), "vi")
            if hasattr(self, "var_lang"):
                self.var_lang.set(self.cfg["language"])
            self.cfg["always_on_top"] = bool(var_topmost_set.get())
            if hasattr(self, "var_topmost"):
                self.var_topmost.set(self.cfg["always_on_top"])
            self.cfg["logo_mode"] = logo_rev.get(var_logo_set.get(), "widget_bg")
            self.cfg["logo_pos"] = logo_pos_rev.get(var_logo_pos.get(), "before_title")
            self.cfg["bg_mode"] = bg_mode_rev.get(var_bg_mode.get(), "default")
            self.cfg["bg_pos"] = bg_pos_rev.get(var_bg_pos.get(), "cover")
            self.cfg["bg_tone"] = "negative" if var_bg_tone.get() == "negative" else "original"
            self.cfg["bg_zoom"] = float(var_bg_zoom.get())
            self.cfg["bg_offset_x"] = float(var_bg_ox.get())
            self.cfg["bg_offset_y"] = float(var_bg_oy.get())
            self.cfg["bg_opacity"] = float(var_bg_op.get())
            if self.cfg["bg_mode"] == "default":
                self.cfg["bg_image"] = ""
            auto_val = bool(var_autostart_set.get())
            self.cfg["auto_start"] = auto_val
            if hasattr(self, "var_autostart"):
                self.var_autostart.set(auto_val)
            set_autostart(auto_val, _active_icon_path(self.cfg))
            self._clear_live_preview()
            save_config(self.cfg)
            self._apply_z_order()
            self._build_menu()
            try:
                _w0 = self.cfg.get("weather") or {}
                set_sun_location(_w0.get("latitude"), _w0.get("longitude"))
            except Exception:
                pass
            win.destroy()
            self.trigger_refresh(force_weather=True)

        make_pill_button(
            btn_row,
            "Cancel" if is_en else "Hủy",
            _cancel_settings,
            bg=p.field,
            fg=p.ink,
            hover_bg=p.field_hover,
            parent_bg=p.shell,
            pad_x=18,
            height=34,
            font=("Segoe UI", 10),
        ).pack(side="right", padx=(8, 0))
        make_pill_button(
            btn_row,
            "Save & Refresh" if is_en else "Lưu & Cập nhật",
            _save,
            bg=p.accent,
            fg=p.accent_fg,
            hover_bg=p.accent_hover,
            parent_bg=p.shell,
            pad_x=20,
            height=34,
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")

        if restore_pos is not None:
            win.update_idletasks()
            win.geometry(f"+{restore_pos[0]}+{restore_pos[1]}")
            win.deiconify()
            win.lift()
        else:
            self._reveal_popup_window(win)

    @staticmethod
    def _cleanup_pid_file() -> None:
        try:
            if os.path.exists(PID_PATH):
                with open(PID_PATH, "r", encoding="utf-8") as f:
                    pid_txt = f.read().strip()
                if pid_txt == str(os.getpid()):
                    os.remove(PID_PATH)
        except Exception:
            pass

    def quit(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._close_detail_popup()
        self._close_reminder_popup()
        for win_attr in ("_settings_win", "_reminders_win", "_event_editor_win"):
            w = getattr(self, win_attr, None)
            if w is not None:
                try:
                    if w.winfo_exists():
                        w.destroy()
                except Exception:
                    pass
                setattr(self, win_attr, None)
        self._cleanup_pid_file()
        try:
            self.root.quit()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            self._cleanup_pid_file()


if __name__ == "__main__":
    _replace_existing_instance()
    app = ESLDeskWidget()
    app.run()
    sys.exit(0)
