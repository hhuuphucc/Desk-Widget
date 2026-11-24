"""Classic Paper Serif & Minimal E-Ink Sans Dashboard Renderer."""

from __future__ import annotations

import calendar as pycal
import ctypes
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math
import os
import random
import subprocess
import sys
from typing import Any
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from calendar_client import (
    EN_WEEKDAYS,
    CalendarSummary,
    VN_WEEKDAYS,
    extract_meeting_links,
    format_event_time,
)
from system_client import SystemStats
from weather_client import WeatherData, day_abbr_for_lang, format_city_name, weather_desc_for_lang


RESOURCE_DIR = str(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))))
ASSETS_DIR = os.path.join(RESOURCE_DIR, "assets")


def convert_temp(temp_c: float | int, unit: str = "C") -> int:
    u = (unit or "C").strip().upper()
    if u == "F":
        return int(round(float(temp_c) * 9.0 / 5.0 + 32.0))
    return int(round(float(temp_c)))


def format_temp(temp_c: float | int, unit: str = "C", with_unit: bool = True) -> str:
    u = "F" if (unit or "C").strip().upper() == "F" else "C"
    val = convert_temp(temp_c, u)
    return f"{val}°{u}" if with_unit else f"{val}°"


@dataclass(frozen=True)
class ThemePalette:
    is_dark: bool
    style: str
    bezel: str
    bezel_border: str
    bezel_shadow: str
    paper: str
    ink: str
    muted: str
    out_month: str
    track: str
    fill: str
    accent: str
    accent_dark: str
    warn: str
    event_bg: str
    selected_bg: str
    today_bg: str
    btn_bg: str
    border_muted: str
    pill: str
    divider_soft: str
    card_border: str


MINIMAL_SANS_LIGHT = ThemePalette(
    is_dark=False,
    style="sans",
    bezel="#F5F5F2",
    bezel_border="#C8C8C2",
    bezel_shadow="#AEAEA8",
    paper="#E6E6E2",
    ink="#181818",
    muted="#555552",
    out_month="#9C9C96",
    track="#D0D0CA",
    fill="#3C3C38",
    accent="#BD261E",
    accent_dark="#8C1913",
    warn="#BD261E",
    event_bg="#ECC2BD",
    selected_bg="#D4D4CE",
    today_bg="#DDDCD6",
    btn_bg="#DEDED8",
    border_muted="#A8A8A2",
    pill="#DCDCD6",
    divider_soft="#B2B2AC",
    card_border="#B2B2AC",
)

MINIMAL_SANS_DARK = ThemePalette(
    is_dark=True,
    style="sans",
    bezel="#282926",
    bezel_border="#454742",
    bezel_shadow="#141513",
    paper="#1D1E1C",
    ink="#ECECE7",
    muted="#A2A29B",
    out_month="#5E6059",
    track="#2E302C",
    fill="#D2D2CA",
    accent="#E85B52",
    accent_dark="#FFD6D2",
    warn="#E85B52",
    event_bg="#592622",
    selected_bg="#343632",
    today_bg="#2B2D29",
    btn_bg="#2B2D29",
    border_muted="#4B4D47",
    pill="#353732",
    divider_soft="#3E403B",
    card_border="#3E403B",
)

PAPER_SERIF_LIGHT = ThemePalette(
    is_dark=False,
    style="serif",
    bezel="#EFEFE9",
    bezel_border="#CFD4D9",
    bezel_shadow="#B8BFC6",
    paper="#F7F7F5",
    ink="#181B20",
    muted="#4C5560",
    out_month="#9AA3AD",
    track="#E4E7EB",
    fill="#4E657A",
    accent="#4E657A",
    accent_dark="#22364A",
    warn="#A66A38",
    event_bg="#DCE4EC",
    selected_bg="#CFD9E3",
    today_bg="#EAECEF",
    btn_bg="#ECEFF2",
    border_muted="#B7C0C9",
    pill="#DCE4EC",
    divider_soft="#C6CDD4",
    card_border="#CFD5DC",
)

PAPER_SERIF_DARK = ThemePalette(
    is_dark=True,
    style="serif",
    bezel="#1E2125",
    bezel_border="#343940",
    bezel_shadow="#0E1012",
    paper="#15171A",
    ink="#ECEFF4",
    muted="#A8B2BE",
    out_month="#575F69",
    track="#24282E",
    fill="#7E9BB8",
    accent="#7E9BB8",
    accent_dark="#DCE7F3",
    warn="#C88D55",
    event_bg="#2A3846",
    selected_bg="#354657",
    today_bg="#22272D",
    btn_bg="#23272D",
    border_muted="#3E454E",
    pill="#2A3846",
    divider_soft="#353B43",
    card_border="#2E333A",
)

# Backwards-compatible aliases
LIGHT_ESL = MINIMAL_SANS_LIGHT
DARK_ESL = MINIMAL_SANS_DARK
BOTANICAL_LIGHT = ThemePalette(
    is_dark=False,
    style="botanical",
    bezel="#EDF3F7",
    bezel_border="#C0D3DF",
    bezel_shadow="#A8BDCB",
    paper="#F6FAFC",
    ink="#18242C",
    muted="#496170",
    out_month="#7A909E",
    track="#DCE7EE",
    fill="#2B6E90",
    accent="#2B6E90",
    accent_dark="#173E54",
    warn="#B5673B",
    event_bg="#D8EAF4",
    selected_bg="#C5DFEE",
    today_bg="#E4F0F7",
    btn_bg="#E8F1F6",
    border_muted="#B7CBD8",
    pill="#D8EAF4",
    divider_soft="#D2E0E9",
    card_border="#C2D4E0",
)
BOTANICAL_DARK = ThemePalette(
    is_dark=True,
    style="botanical",
    bezel="#141D24",
    bezel_border="#2B3B48",
    bezel_shadow="#070C10",
    paper="#0F171D",
    ink="#E8F1F6",
    muted="#9FB4C2",
    out_month="#657B8A",
    track="#1F2D37",
    fill="#69B3D6",
    accent="#69B3D6",
    accent_dark="#D8EAF4",
    warn="#D68F5E",
    event_bg="#1D3748",
    selected_bg="#27485D",
    today_bg="#1B2B36",
    btn_bg="#1C2832",
    border_muted="#354857",
    pill="#1D3748",
    divider_soft="#23313D",
    card_border="#2C3D4B",
)

# Modern Desktop Widget Presets (adapted for landscape desktop cards on Windows & macOS)
MACOS_LIGHT = ThemePalette(
    is_dark=False,
    style="macos",
    bezel="#ECEFF5",
    bezel_border="#CBD4E1",
    bezel_shadow="#AEB9C9",
    paper="#E9EDF4",
    ink="#1D1D1F",
    muted="#515154",
    out_month="#9A9EA6",
    track="#E2E7F0",
    fill="#007AFF",
    accent="#007AFF",
    accent_dark="#004999",
    warn="#FF3B30",
    event_bg="#DCEEFF",
    selected_bg="#CCE4FF",
    today_bg="#FFE5E5",
    btn_bg="#F2F4F8",
    border_muted="#C5D0E0",
    pill="#DCEEFF",
    divider_soft="#D7DFEC",
    card_border="#C9D3E2",
)

MACOS_DARK = ThemePalette(
    is_dark=True,
    style="macos",
    bezel="#1C1C1E",
    bezel_border="#3A3A3C",
    bezel_shadow="#0C0C0E",
    paper="#1C1C1E",
    ink="#F5F5F7",
    muted="#AEAEB2",
    out_month="#636366",
    track="#3A3A3C",
    fill="#0A84FF",
    accent="#0A84FF",
    accent_dark="#DCEEFF",
    warn="#FF453A",
    event_bg="#143D66",
    selected_bg="#1E4D7B",
    today_bg="#4D1E22",
    btn_bg="#3A3A3C",
    border_muted="#48484A",
    pill="#143D66",
    divider_soft="#38383A",
    card_border="#3A3A3E",
)

PIXEL_LIGHT = ThemePalette(
    is_dark=False,
    style="pixel",
    bezel="#F3EEF9",
    bezel_border="#D8CCE8",
    bezel_shadow="#B8AAD0",
    paper="#F3EEF9",
    ink="#1D1B20",
    muted="#49454F",
    out_month="#9C95A3",
    track="#D7CFE5",
    fill="#6750A4",
    accent="#6750A4",
    accent_dark="#21005D",
    warn="#B3261E",
    event_bg="#DFD2F6",
    selected_bg="#EADDFF",
    today_bg="#F3E5F5",
    btn_bg="#E4DCF2",
    border_muted="#C8BBE0",
    pill="#EADDFF",
    divider_soft="#D5CBE6",
    card_border="#CEC1E2",
)

PIXEL_DARK = ThemePalette(
    is_dark=True,
    style="pixel",
    bezel="#141218",
    bezel_border="#3B3842",
    bezel_shadow="#070609",
    paper="#141218",
    ink="#E6E0E9",
    muted="#CAC4D0",
    out_month="#686270",
    track="#322E3D",
    fill="#CBBFFF",
    accent="#CBBFFF",
    accent_dark="#EADDFF",
    warn="#F2B8B5",
    event_bg="#382C56",
    selected_bg="#4F378B",
    today_bg="#2B243C",
    btn_bg="#2B2930",
    border_muted="#49454F",
    pill="#4F378B",
    divider_soft="#363240",
    card_border="#3B3842",
)

XIAOMI_LIGHT = ThemePalette(
    is_dark=False,
    style="xiaomi",
    bezel="#F3F4F6",
    bezel_border="#DCE0E6",
    bezel_shadow="#B8BEC9",
    paper="#F3F4F6",
    ink="#191C22",
    muted="#505662",
    out_month="#9CA3B0",
    track="#E5E8EE",
    fill="#FF6900",
    accent="#FF6900",
    accent_dark="#9E3B00",
    warn="#FF3B30",
    event_bg="#FFE7D6",
    selected_bg="#FFD7BA",
    today_bg="#FFF1E6",
    btn_bg="#EEF0F4",
    border_muted="#D4D8E0",
    pill="#FFE8D6",
    divider_soft="#E2E5EB",
    card_border="#D4D9E2",
)

XIAOMI_DARK = ThemePalette(
    is_dark=True,
    style="xiaomi",
    bezel="#08090C",
    bezel_border="#282D3A",
    bezel_shadow="#020305",
    paper="#08090C",
    ink="#F4F6FA",
    muted="#A5AEBF",
    out_month="#5A6375",
    track="#222733",
    fill="#FF6900",
    accent="#FF6900",
    accent_dark="#FFD4B3",
    warn="#FF5A36",
    event_bg="#3D1F0D",
    selected_bg="#592D12",
    today_bg="#2A190E",
    btn_bg="#1F242E",
    border_muted="#323948",
    pill="#4A240A",
    divider_soft="#242936",
    card_border="#282D3A",
)


def _is_paper(th: ThemePalette) -> bool:
    return th.style in ("serif", "botanical")


def is_modern_desktop_style(style_or_theme: str | ThemePalette) -> bool:
    st = style_or_theme.style if isinstance(style_or_theme, ThemePalette) else str(style_or_theme or "")
    return st.strip().lower() in ("macos", "pixel", "xiaomi")


def _modern_card_spec(th: ThemePalette) -> dict:
    """Visual geometry & distinct Bento module palettes per desktop OS style."""
    if th.style == "macos":
        c = "#2C2C2E" if th.is_dark else "#FFFFFF"
        b = "#3D3D40" if th.is_dark else "#D6DEE9"
        return {
            "outer_r": 18,
            "inner_r": 12,
            "bento_sys": c,
            "bento_wx": c,
            "bento_cal": c,
            "bento_border": b,
            "bar_ram": "#30D158" if th.is_dark else "#34C759",
            "bar_cpu": "#0A84FF" if th.is_dark else "#007AFF",
            "bar_gpu": "#BF5AF2" if th.is_dark else "#AF52DE",
            "bar_high": "#FF453A" if th.is_dark else "#FF3B30",
            "today_fill": "#FF453A" if th.is_dark else "#FF3B30",
        }
    if th.style == "xiaomi":
        c = "#151821" if th.is_dark else "#FFFFFF"
        b = "#262B38" if th.is_dark else "#E0E4EC"
        return {
            "outer_r": 16,
            "inner_r": 13,
            "bento_sys": c,
            "bento_wx": c,
            "bento_cal": c,
            "bento_border": b,
            "bar_ram": "#26C6DA" if th.is_dark else "#00A8E8",
            "bar_cpu": "#FF7A1A" if th.is_dark else "#FF6900",
            "bar_gpu": "#00D69F" if th.is_dark else "#00B578",
            "bar_high": "#FF5A36" if th.is_dark else "#E63B1E",
            "today_fill": "#FF6900",
        }
    # pixel (Material You expressive multi-pastel containers)
    return {
        "outer_r": 20,
        "inner_r": 15,
        "bento_sys": "#1B2821" if th.is_dark else "#E2F1E8",
        "bento_wx": "#2C2018" if th.is_dark else "#FCECE0",
        "bento_cal": "#211C30" if th.is_dark else "#EBE4F8",
        "bento_border": "#363242" if th.is_dark else "#D8CEE8",
        "bar_ram": "#76D8A4" if th.is_dark else "#1E7B55",
        "bar_cpu": "#CBBFFF" if th.is_dark else "#6750A4",
        "bar_gpu": "#FFB685" if th.is_dark else "#C2591A",
        "bar_high": "#F2B8B5" if th.is_dark else "#B3261E",
        "today_fill": "#6750A4" if not th.is_dark else "#8C6DE8",
    }

SCREEN_W = 480
SCREEN_H = 224

_EMBLEM_CACHE: dict[tuple[str, int, int], Image.Image] = {}
_CIRCLE_LOGO_CACHE: dict[tuple[str, int, int, str], Image.Image] = {}
_PAPER_CACHE: dict[tuple[int, int, bool], Image.Image] = {}


def get_desktop_wallpaper_path() -> str:
    """Return current desktop wallpaper file path on Windows or macOS, or '' if unavailable."""
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(512)
            if ctypes.windll.user32.SystemParametersInfoW(0x0073, 512, buf, 0) and buf.value:
                if os.path.exists(buf.value):
                    return buf.value
        except Exception:
            pass
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
                wp = str(winreg.QueryValueEx(k, "WallPaper")[0] or "").strip()
                if wp and os.path.exists(wp):
                    return wp
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(
                ["osascript", "-e", 'tell application "System Events" to get picture of current desktop'],
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL,
            ).strip()
            if out and os.path.exists(out):
                return out
        except Exception:
            pass
    return ""


def _load_circle_logo(
    image_path: str | None,
    size: int,
    border_color: str,
    fill_bg: str | None = None,
) -> Image.Image | None:
    """Load an image/emblem/wallpaper, crop square cleanly, and mask into an anti-aliased circle."""
    p = (image_path or "").strip()
    if not p or not os.path.exists(p):
        return None
    try:
        mtime_ns = os.stat(p).st_mtime_ns
    except Exception:
        return None

    key = (p, mtime_ns, size, f"{border_color}|{fill_bg or ''}")
    if key in _CIRCLE_LOGO_CACHE:
        return _CIRCLE_LOGO_CACHE[key]

    try:
        with Image.open(p) as _raw_logo:
            im = ImageOps.exif_transpose(_raw_logo).convert("RGBA")
        alpha_ext = im.getchannel("A").getextrema()
        has_alpha = alpha_ext[0] < 245

        if has_alpha:
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
            w, h = im.size
            side = max(w, h)
            pad = max(2, int(round(side * 0.08)))
            sq_sz = side + pad * 2
            bg_rgba = (*_hex_to_rgb(fill_bg), 255) if fill_bg else (0, 0, 0, 0)
            sq = Image.new("RGBA", (sq_sz, sq_sz), bg_rgba)
            sq.alpha_composite(im, ((sq_sz - w) // 2, (sq_sz - h) // 2))
            im = sq.resize((size, size), Image.Resampling.LANCZOS)
        else:
            w, h = im.size
            side = min(w, h)
            if side <= 0:
                return None
            left = (w - side) // 2
            top = (h - side) // 2
            im = im.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)

        # 4x supersampled circle mask for razor-sharp smooth circular rim
        mask_hi = Image.new("L", (size * 4, size * 4), 0)
        md = ImageDraw.Draw(mask_hi)
        md.ellipse((2, 2, size * 4 - 3, size * 4 - 3), fill=255)
        mask = mask_hi.resize((size, size), Image.Resampling.LANCZOS)

        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(im, (0, 0), mask)
        rim = ImageDraw.Draw(out)
        rim.ellipse((0, 0, size - 1, size - 1), outline=border_color, width=max(1, size // 18))

        if len(_CIRCLE_LOGO_CACHE) > 12:
            _CIRCLE_LOGO_CACHE.clear()
        _CIRCLE_LOGO_CACHE[key] = out
        return out
    except Exception:
        return None


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _get_paper_texture(w: int, h: int, th: ThemePalette) -> Image.Image:
    """Build and cache a tactile cold-pressed rough drawing paper background."""
    key = (w, h, th.is_dark)
    if key in _PAPER_CACHE:
        return _PAPER_CACHE[key]

    br, bg_c, bb = _hex_to_rgb(th.paper)
    rng = random.Random(20261123)

    # Create coarse paper tooth at half-res and blend with fine grain for authentic paper fibers
    half_w, half_h = w // 2, h // 2
    coarse = Image.new("L", (half_w, half_h), 128)
    c_px = coarse.load()
    for y in range(half_h):
        for x in range(half_w):
            c_px[x, y] = max(0, min(255, 128 + rng.randint(-34, 34)))
    coarse = coarse.resize((w, h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))

    fine = Image.new("L", (w, h), 128)
    f_px = fine.load()
    for y in range(h):
        row_bias = rng.randint(-4, 4)
        for x in range(w):
            # Subtle horizontal laid-paper fiber + tooth
            speck = rng.randint(-18, 18) + row_bias
            f_px[x, y] = max(0, min(255, 128 + speck))

    out = Image.new("RGBA", (w, h), (br, bg_c, bb, 255))
    o_px = out.load()
    c2_px = coarse.load()
    f2_px = fine.load()
    amp = 0.30 if not th.is_dark else 0.22

    for y in range(h):
        ny = abs((y / (h - 1)) * 2.0 - 1.0)
        for x in range(w):
            nx = abs((x / (w - 1)) * 2.0 - 1.0)
            # Gentle warm vignette along outer paper edges
            edge = max(0.0, (nx * nx + ny * ny) - 0.85) * (6.0 if not th.is_dark else 3.5)
            tooth = ((c2_px[x, y] - 128) * 0.62 + (f2_px[x, y] - 128) * 0.38) * amp
            delta = tooth - edge
            r = max(0, min(255, int(round(br + delta + (1.2 if not th.is_dark and delta > 0 else 0)))))
            g = max(0, min(255, int(round(bg_c + delta))))
            b = max(0, min(255, int(round(bb + delta - (1.4 if not th.is_dark and delta < 0 else 0)))))
            o_px[x, y] = (r, g, b, 255)

    _PAPER_CACHE[key] = out
    return out


def _default_emblem_path(is_dark: bool) -> str:
    fname = "emblem_dark.png" if is_dark else "emblem_light.png"
    path = os.path.join(ASSETS_DIR, fname)
    return path if os.path.exists(path) else ""


def _bg_is_opaque_photo(bg_path: str | None) -> bool:
    p = (bg_path or "").strip()
    if not p or not os.path.exists(p):
        return False
    try:
        with Image.open(p) as _raw:
            im = _raw.convert("RGBA")
            return im.getchannel("A").getextrema()[0] >= 245
    except Exception:
        return False


def apply_bg_tone(im: Image.Image, tone: str = "original") -> Image.Image:
    """Return RGBA image in either 'original' colors or RGB-inverted 'negative' preserving alpha."""
    rgba = im.convert("RGBA")
    if (tone or "original").strip().lower() != "negative":
        return rgba
    r, g, b, a = rgba.split()
    inv_rgb = ImageOps.invert(Image.merge("RGB", (r, g, b)))
    ir, ig, ib = inv_rgb.split()
    return Image.merge("RGBA", (ir, ig, ib, a))


def compose_bg_layer(
    im: Image.Image,
    cw: int,
    ch: int,
    pos: str = "cover",
    zoom: float = 1.0,
    offset_x: float = 0.0,
    offset_y: float = 0.0,
    tone: str = "original",
    div_x_px: int | None = None,
    center_y_px: int | None = None,
    emblem_size: int | None = None,
    alpha_scale: float = 1.0,
) -> Image.Image:
    """Compose a scaled, panned, tone-adjusted RGBA background layer at exact widget ratio (cw x ch)."""
    rgba = apply_bg_tone(im, tone=tone)
    has_alpha = rgba.getchannel("A").getextrema()[0] < 245
    z = max(0.35, min(3.0, float(zoom)))
    ox = max(-1.5, min(1.5, float(offset_x)))
    oy = max(-1.5, min(1.5, float(offset_y)))
    p_norm = (pos or "cover").strip().lower()
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    if has_alpha:
        base_em = emblem_size if emblem_size is not None else int(round(ch * 0.68))
        target_sz = max(8, int(round((base_em * 0.72 if p_norm == "bottom_right" else base_em) * z)))
        emblem = ImageOps.contain(rgba, (target_sz, target_sz), Image.Resampling.LANCZOS)
        dx_base = (div_x_px if div_x_px is not None else cw // 2)
        cy_base = (center_y_px if center_y_px is not None else ch // 2)
        if p_norm == "left":
            ex = max(6, dx_base // 2 - emblem.width // 2)
            ey = cy_base - emblem.height // 2
        elif p_norm == "right":
            ex = dx_base + max(8, (cw - dx_base - emblem.width) // 2)
            ey = cy_base - emblem.height // 2
        elif p_norm == "top":
            ex = dx_base - emblem.width // 2
            ey = max(8, int(round(ch * 0.14)))
        elif p_norm == "bottom":
            ex = dx_base - emblem.width // 2
            ey = max(8, ch - emblem.height - int(round(ch * 0.06)))
        elif p_norm == "bottom_right":
            ex = max(8, cw - emblem.width - int(round(cw * 0.03)))
            ey = max(8, ch - emblem.height - int(round(ch * 0.04)))
        else:
            ex = dx_base - emblem.width // 2
            ey = cy_base - emblem.height // 2
        ex = int(round(ex + ox * (cw * 0.5)))
        ey = int(round(ey + oy * (ch * 0.5)))
        if alpha_scale < 0.999:
            emblem.putalpha(emblem.getchannel("A").point(lambda a: int(round(a * alpha_scale))))
        layer.paste(emblem, (ex, ey), emblem)
        return layer

    if p_norm == "bottom_right" and abs(z - 1.0) < 0.01 and abs(ox) < 0.01 and abs(oy) < 0.01:
        box_w = max(40, int(round(cw * 0.28)))
        box_h = max(30, int(round(ch * 0.44)))
        fitted = ImageOps.fit(rgba, (box_w, box_h), Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        if alpha_scale < 0.999:
            fitted.putalpha(fitted.getchannel("A").point(lambda a: int(round(a * alpha_scale))))
        px = max(6, cw - box_w - int(round(cw * 0.02)))
        py = max(6, ch - box_h - int(round(ch * 0.03)))
        layer.paste(fitted, (px, py))
        return layer

    w, h = rgba.size
    base_scale = max(cw / max(1, w), ch / max(1, h))
    nw = max(1, int(round(w * base_scale * z)))
    nh = max(1, int(round(h * base_scale * z)))
    fitted = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
    if alpha_scale < 0.999:
        fitted.putalpha(fitted.getchannel("A").point(lambda a: int(round(a * alpha_scale))))
    fx = 0.0 if p_norm == "left" else (1.0 if p_norm == "right" else 0.5)
    fy = 0.0 if p_norm == "top" else (1.0 if p_norm == "bottom" else 0.5)
    dx = int(round((cw - nw) * fx + ox * (cw * 0.5)))
    dy = int(round((ch - nh) * fy + oy * (ch * 0.5)))
    layer.paste(fitted, (dx, dy))
    return layer


def _apply_widget_background(
    canvas: Image.Image,
    bg_path: str | None,
    div_x_px: int,
    center_y_px: int,
    emblem_size: int,
    is_dark: bool,
    bg_pos: str = "cover",
    outer_mask: Image.Image | None = None,
    photo_alpha: float | None = None,
    emblem_alpha: float | None = None,
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
) -> str:
    """Composite custom or local theme background onto widget card with selectable placement, crop & tone."""
    chosen = (bg_path or "").strip()
    path = chosen if (chosen and os.path.exists(chosen)) else _default_emblem_path(is_dark)
    if not path:
        return ""
    pos = (bg_pos or "cover").strip().lower()
    if pos not in ("cover", "center", "top", "bottom", "left", "right", "bottom_right"):
        pos = "cover"
    t_norm = "negative" if (bg_tone or "original").strip().lower() == "negative" else "original"
    z_clamped = max(0.35, min(3.0, float(bg_zoom)))
    ox_clamped = max(-1.5, min(1.5, float(bg_offset_x)))
    oy_clamped = max(-1.5, min(1.5, float(bg_offset_y)))
    try:
        mtime_ns = os.stat(path).st_mtime_ns
        cw, ch = canvas.size
        with Image.open(path) as _raw_bg:
            im = ImageOps.exif_transpose(_raw_bg).convert("RGBA")
        has_alpha = im.getchannel("A").getextrema()[0] < 245
        if has_alpha:
            alpha_scale = (0.56 if not is_dark else 0.58) if emblem_alpha is None else float(emblem_alpha)
        elif pos == "bottom_right" and abs(z_clamped - 1.0) < 0.01 and abs(ox_clamped) < 0.01 and abs(oy_clamped) < 0.01:
            alpha_scale = (0.28 if not is_dark else 0.24) if photo_alpha is None else float(photo_alpha)
        else:
            alpha_scale = (0.20 if not is_dark else 0.18) if photo_alpha is None else float(photo_alpha)

        key = (
            f"bg:{path}:{mtime_ns}:{pos}:{t_norm}:{z_clamped:.3f}:{ox_clamped:.3f}:{oy_clamped:.3f}:{alpha_scale:.2f}:{cw}x{ch}",
            emblem_size,
            int(is_dark),
        )
        if key in _EMBLEM_CACHE:
            layer = _EMBLEM_CACHE[key].copy()
        else:
            layer = compose_bg_layer(
                im,
                cw,
                ch,
                pos=pos,
                zoom=z_clamped,
                offset_x=ox_clamped,
                offset_y=oy_clamped,
                tone=t_norm,
                div_x_px=div_x_px,
                center_y_px=center_y_px,
                emblem_size=emblem_size,
                alpha_scale=alpha_scale,
            )
            if len(_EMBLEM_CACHE) > 12:
                _EMBLEM_CACHE.clear()
            _EMBLEM_CACHE[key] = layer.copy()
        if outer_mask is not None:
            layer.putalpha(Image.composite(layer.getchannel("A"), Image.new("L", (cw, ch), 0), outer_mask))
        canvas.alpha_composite(layer, (0, 0))
        return path
    except Exception:
        return ""


def is_system_dark_mode() -> bool:
    """Detect the current OS Light/Dark mode on Windows, macOS, and Linux desktops."""
    if sys.platform == "win32":
        try:
            import winreg

            key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                for val_name in ("AppsUseLightTheme", "SystemUsesLightTheme"):
                    try:
                        val, _ = winreg.QueryValueEx(key, val_name)
                        return int(val) == 0
                    except OSError:
                        continue
        except Exception:
            return False
        return False

    if sys.platform == "darwin":
        try:
            res = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            return res.returncode == 0 and "dark" in (res.stdout or "").strip().lower()
        except Exception:
            return False

    if sys.platform.startswith("linux"):
        try:
            res = subprocess.run(
                ["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                capture_output=True,
                text=True,
                timeout=1.5,
            )
            if res.returncode == 0 and "prefer-dark" in (res.stdout or "").lower():
                return True
        except Exception:
            pass
    return False


_SUN_LOCATION: tuple[float, float] | None = None
# Sun centre this many degrees below the horizon = official sunrise/sunset (refraction + solar radius)
SUN_HORIZON_DEG = -0.833


def set_sun_location(latitude: float | None, longitude: float | None) -> None:
    """Remember the installed location so 'auto' theme follows local sunrise/sunset."""
    global _SUN_LOCATION
    try:
        lat = float(latitude)  # type: ignore[arg-type]
        lon = float(longitude)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        _SUN_LOCATION = None
        return
    if -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0:
        _SUN_LOCATION = (lat, lon)
    else:
        _SUN_LOCATION = None


def get_sun_location() -> tuple[float, float] | None:
    return _SUN_LOCATION


def _as_utc(when: datetime) -> datetime:
    if when.tzinfo is None:
        when = when.astimezone()  # naive -> treat as this computer's local time
    return when.astimezone(timezone.utc)


def solar_elevation_deg(when: datetime, latitude: float, longitude: float) -> float:
    """Solar elevation angle (degrees) at an instant for a location (NOAA solar position algorithm)."""
    t = _as_utc(when)
    jd = t.timestamp() / 86400.0 + 2440587.5
    jc = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + jc * (36000.76983 + jc * 0.0003032)) % 360.0
    m = 357.52911 + jc * (35999.05029 - 0.0001537 * jc)
    e = 0.016708634 - jc * (0.000042037 + 0.0000001267 * jc)
    mr = math.radians(m)
    c = (
        math.sin(mr) * (1.914602 - jc * (0.004817 + 0.000014 * jc))
        + math.sin(2 * mr) * (0.019993 - 0.000101 * jc)
        + math.sin(3 * mr) * 0.000289
    )
    omega = math.radians(125.04 - 1934.136 * jc)
    app_long = math.radians(l0 + c - 0.00569 - 0.00478 * math.sin(omega))
    eps0 = 23.0 + (26.0 + (21.448 - jc * (46.815 + jc * (0.00059 - jc * 0.001813))) / 60.0) / 60.0
    eps = math.radians(eps0 + 0.00256 * math.cos(omega))
    decl = math.asin(math.sin(eps) * math.sin(app_long))
    y = math.tan(eps / 2.0) ** 2
    l0r = math.radians(l0)
    eq_time = 4.0 * math.degrees(
        y * math.sin(2 * l0r)
        - 2 * e * math.sin(mr)
        + 4 * e * y * math.sin(mr) * math.cos(2 * l0r)
        - 0.5 * y * y * math.sin(4 * l0r)
        - 1.25 * e * e * math.sin(2 * mr)
    )
    minutes_utc = t.hour * 60.0 + t.minute + t.second / 60.0
    true_solar = (minutes_utc + eq_time + 4.0 * longitude) % 1440.0
    hour_angle = math.radians(true_solar / 4.0 - 180.0)
    lat_r = math.radians(latitude)
    cos_zen = math.sin(lat_r) * math.sin(decl) + math.cos(lat_r) * math.cos(decl) * math.cos(hour_angle)
    zenith = math.degrees(math.acos(max(-1.0, min(1.0, cos_zen))))
    return 90.0 - zenith


def is_sun_up(when: datetime, latitude: float, longitude: float) -> bool:
    return solar_elevation_deg(when, latitude, longitude) > SUN_HORIZON_DEG


def sun_times(day: date, latitude: float, longitude: float, tzinfo) -> tuple[datetime | None, datetime | None]:
    """Local (sunrise, sunset) for a calendar day in tzinfo; None when the sun never rises/sets that day."""
    start = datetime(day.year, day.month, day.day, tzinfo=tzinfo)
    prev_up = is_sun_up(start, latitude, longitude)
    rise = sset = None
    for minute in range(1, 24 * 60 + 1):
        cur = start + timedelta(minutes=minute)
        up = is_sun_up(cur, latitude, longitude)
        if up and not prev_up and rise is None:
            rise = cur
        elif prev_up and not up and sset is None:
            sset = cur
        prev_up = up
    return rise, sset


def auto_is_dark(
    now: datetime | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> bool:
    """'auto' theme: dark between local sunset and sunrise at the app location (06:00–18:00 fallback)."""
    if now is None:
        now = datetime.now().astimezone()
    loc = (latitude, longitude) if (latitude is not None and longitude is not None) else _SUN_LOCATION
    if loc is not None:
        try:
            return not is_sun_up(now, float(loc[0]), float(loc[1]))
        except Exception:
            pass
    # Fallback when no location is known yet: light 06:00–17:59
    return now.hour >= 18 or now.hour < 6


def resolve_theme(
    theme_mode: str = "auto",
    now: datetime | None = None,
    style: str = "serif",
    system_is_dark: bool | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> ThemePalette:
    mode = (theme_mode or "auto").strip().lower()
    st = (style or "serif").strip().lower()
    if mode == "dark":
        is_dark = True
    elif mode == "light":
        is_dark = False
    elif mode in ("system", "os"):
        is_dark = is_system_dark_mode() if system_is_dark is None else bool(system_is_dark)
    else:
        is_dark = auto_is_dark(now, latitude, longitude)

    if st in ("sans", "esl"):
        return MINIMAL_SANS_DARK if is_dark else MINIMAL_SANS_LIGHT
    if st == "botanical":
        return BOTANICAL_DARK if is_dark else BOTANICAL_LIGHT
    if st == "macos":
        return MACOS_DARK if is_dark else MACOS_LIGHT
    if st == "pixel":
        return PIXEL_DARK if is_dark else PIXEL_LIGHT
    if st == "xiaomi":
        return XIAOMI_DARK if is_dark else XIAOMI_LIGHT
    return PAPER_SERIF_DARK if is_dark else PAPER_SERIF_LIGHT


@dataclass
class HitRegion:
    x1: int
    y1: int
    x2: int
    y2: int
    action: str
    payload: Any = None

    def contains(self, x: int, y: int) -> bool:
        return self.x1 <= x <= self.x2 and self.y1 <= y <= self.y2


_MAC_FONT_FALLBACKS = {
    "palab.ttf": [
        "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
    "Candara.ttf": [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "Candarab.ttf": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "segoeui.ttf": [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
    "segoeuib.ttf": [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ],
}


def _load_font(filename: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    # 1. Local assets/fonts (if user drops custom TTFs)
    local_font = os.path.join(ASSETS_DIR, "fonts", filename)
    if os.path.exists(local_font):
        return ImageFont.truetype(local_font, size)

    # 2. Windows system fonts
    win_fonts = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", filename)
    if os.path.exists(win_fonts):
        return ImageFont.truetype(win_fonts, size)

    # 3. macOS system fonts (Intel & Apple Silicon)
    for mac_path in _MAC_FONT_FALLBACKS.get(filename, []):
        if os.path.exists(mac_path):
            try:
                return ImageFont.truetype(mac_path, size)
            except Exception:
                continue

    # 4. Generic cross-platform fallbacks
    for generic in (
        os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"),
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/SFNS.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if os.path.exists(generic):
            try:
                return ImageFont.truetype(generic, size)
            except Exception:
                continue
    return ImageFont.load_default()


class _ScaledDraw:
    """Proxy over Pillow ImageDraw that scales vector geometry cleanly for HiDPI supersampling."""

    def __init__(self, raw_draw: ImageDraw.ImageDraw, scale: float = 1.0, ox: float = 0.0, oy: float = 0.0) -> None:
        self._d = raw_draw
        self.scale = float(scale)
        self.ox = float(ox)
        self.oy = float(oy)

    def _x(self, x: float) -> float:
        return (x - self.ox) * self.scale

    def _y(self, y: float) -> float:
        return (y - self.oy) * self.scale

    def _pts(self, xy):
        if isinstance(xy, (list, tuple)) and xy and isinstance(xy[0], (list, tuple)):
            return [(self._x(p[0]), self._y(p[1])) for p in xy]
        return [self._x(xy[0]), self._y(xy[1]), self._x(xy[2]), self._y(xy[3])] if len(xy) == 4 else [
            self._x(v) if i % 2 == 0 else self._y(v) for i, v in enumerate(xy)
        ]

    def _w(self, width: int) -> int:
        return max(1, int(round(width * self.scale)))

    def text(self, xy, text: str, font=None, fill=None) -> None:
        self._d.text((self._x(xy[0]), self._y(xy[1])), text, font=font, fill=fill)

    def textbbox(self, xy, text: str, font=None):
        return self._d.textbbox((self._x(xy[0]), self._y(xy[1])), text, font=font)

    def line(self, xy, fill=None, width: int = 1) -> None:
        self._d.line(self._pts(xy), fill=fill, width=self._w(width))

    def rectangle(self, xy, fill=None, outline=None, width: int = 1) -> None:
        w = self._w(width) if outline is not None else 0
        self._d.rectangle(self._pts(xy), fill=fill, outline=outline, width=w)

    def rounded_rectangle(self, xy, radius: float = 0, fill=None, outline=None, width: int = 1) -> None:
        w = self._w(width) if outline is not None else 0
        r = max(1, int(round(radius * self.scale)))
        self._d.rounded_rectangle(self._pts(xy), radius=r, fill=fill, outline=outline, width=w)

    def ellipse(self, xy, fill=None, outline=None, width: int = 1) -> None:
        w = self._w(width) if outline is not None else 0
        self._d.ellipse(self._pts(xy), fill=fill, outline=outline, width=w)

    def polygon(self, xy, fill=None, outline=None) -> None:
        self._d.polygon(self._pts(xy), fill=fill, outline=outline)

    def point(self, xy, fill=None) -> None:
        x, y = self._x(xy[0]), self._y(xy[1])
        sz = max(1.0, self.scale)
        self._d.rectangle((x, y, x + sz - 1, y + sz - 1), fill=fill)


class Fonts:
    def __init__(self, style: str = "sans", scale: float = 1.0) -> None:
        def _pt(sz: float) -> int:
            return max(8, int(round(sz * scale)))

        if style == "botanical":
            # Botanical Typography: Palatino Linotype Bold + Candara (rendered crisp via 2x/3x HiDPI SSAA)
            self.header_date = _load_font("palab.ttf", _pt(14))
            self.header_sub = _load_font("Candara.ttf", _pt(11))
            self.section = _load_font("palab.ttf", _pt(12))
            self.label = _load_font("Candara.ttf", _pt(11))
            self.pct = _load_font("Candarab.ttf", _pt(11))
            self.small = _load_font("Candara.ttf", _pt(10.5))
            self.small_bold = _load_font("Candarab.ttf", _pt(10.5))
            self.tiny = _load_font("Candara.ttf", _pt(9.5))
            self.tiny_bold = _load_font("Candarab.ttf", _pt(9.5))
            self.event_time = _load_font("Candarab.ttf", _pt(11))
            self.event_title = _load_font("Candara.ttf", _pt(11))
            self.cal_title = _load_font("palab.ttf", _pt(12))
            # Palatino has lining (equal-height) digits; Candara's old-style digits jump up/down inside cells
            self.cal_day = _load_font("pala.ttf", _pt(10.5))
            self.cal_day_bold = _load_font("palab.ttf", _pt(10.5))
        elif style == "serif":
            # Classic Paper Serif: Palatino Linotype Bold cho tiêu đề + Segoe UI rõ nét cho nội dung & số
            self.header_date = _load_font("palab.ttf", _pt(14))
            self.header_sub = _load_font("segoeui.ttf", _pt(10.5))
            self.section = _load_font("palab.ttf", _pt(12))
            self.label = _load_font("segoeui.ttf", _pt(10.5))
            self.pct = _load_font("segoeuib.ttf", _pt(10.5))
            self.small = _load_font("segoeui.ttf", _pt(10))
            self.small_bold = _load_font("segoeuib.ttf", _pt(10))
            self.tiny = _load_font("segoeui.ttf", _pt(9.5))
            self.tiny_bold = _load_font("segoeuib.ttf", _pt(9.5))
            self.event_time = _load_font("segoeuib.ttf", _pt(10.5))
            self.event_title = _load_font("segoeui.ttf", _pt(10.5))
            self.cal_title = _load_font("palab.ttf", _pt(12))
            self.cal_day = _load_font("segoeui.ttf", _pt(10))
            self.cal_day_bold = _load_font("segoeuib.ttf", _pt(10))
        else:
            self.header_date = _load_font("segoeuib.ttf", _pt(14))
            self.header_sub = _load_font("segoeui.ttf", _pt(10.5))
            self.section = _load_font("segoeuib.ttf", _pt(12))
            self.label = _load_font("segoeui.ttf", _pt(10.5))
            self.pct = _load_font("segoeuib.ttf", _pt(10.5))
            self.small = _load_font("segoeui.ttf", _pt(10))
            self.small_bold = _load_font("segoeuib.ttf", _pt(10))
            self.tiny = _load_font("segoeui.ttf", _pt(9.5))
            self.tiny_bold = _load_font("segoeuib.ttf", _pt(9.5))
            self.event_time = _load_font("segoeuib.ttf", _pt(10.5))
            self.event_title = _load_font("segoeui.ttf", _pt(10.5))
            self.cal_title = _load_font("segoeuib.ttf", _pt(11))
            self.cal_day = _load_font("segoeui.ttf", _pt(10))
            self.cal_day_bold = _load_font("segoeuib.ttf", _pt(10))


def _text_width(draw, text: str, font) -> int:
    s = float(getattr(draw, "scale", 1.0))
    box = draw.textbbox((0, 0), text, font=font)
    return int(math.ceil((box[2] - box[0]) / s))


def _draw_text_centered(draw, box, text: str, font, fill, v_sample: str | None = None) -> None:
    """Draw text optically centred inside box=(x1, y1, x2, y2) in logical px.

    Horizontal centring uses the real ink extent of `text`; vertical centring uses the ink extent of
    `v_sample` (default: the text itself) so a row of labels shares one baseline.
    """
    s = float(getattr(draw, "scale", 1.0)) or 1.0
    raw = getattr(draw, "_d", draw)
    hb = raw.textbbox((0, 0), text, font=font)
    vb = raw.textbbox((0, 0), v_sample, font=font) if v_sample else hb
    x1, y1, x2, y2 = box
    tx = (x1 + x2) / 2.0 - (hb[0] + hb[2]) / (2.0 * s)
    ty = (y1 + y2) / 2.0 - (vb[1] + vb[3]) / (2.0 * s)
    # Snap to the device pixel grid so glyphs stay crisp
    tx = round(tx * s) / s
    ty = round(ty * s) / s
    draw.text((tx, ty), text, font=font, fill=fill)


def _truncate_text(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> str:
    if max_w <= 6:
        return ""
    if _text_width(draw, text, font) <= max_w:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if _text_width(draw, text[:mid] + ell, font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo].rstrip() + ell) if lo > 0 else ell


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_w: int, max_lines: int = 2) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        if _text_width(draw, cand, font) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
            if len(lines) >= max_lines:
                break
    if len(lines) < max_lines:
        lines.append(cur)
    elif len(lines) == max_lines:
        used_words = sum(len(l.split()) for l in lines)
        if used_words < len(words):
            tail = " ".join(words[used_words - len(lines[-1].split()):])
            lines[-1] = _truncate_text(draw, tail, font, max_w)
    if lines:
        lines[-1] = _truncate_text(draw, lines[-1], font, max_w)
    return lines


def _draw_fineline_rule(
    draw: ImageDraw.ImageDraw,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: str,
    dot_color: str,
    with_dots: bool = True,
) -> None:
    draw.line((x1, y1, x2, y2), fill=color, width=1)
    if with_dots:
        draw.ellipse((x1 - 1, y1 - 1, x1 + 1, y1 + 1), fill=dot_color)
        draw.ellipse((x2 - 1, y2 - 1, x2 + 1, y2 + 1), fill=dot_color)


def _draw_section_glyph(draw: ImageDraw.ImageDraw, x: int, y: int, th: ThemePalette) -> None:
    """Header glyph for the system column (capsule badge in desktop card styles, sun/moon in paper, chip in sans)."""
    if is_modern_desktop_style(th):
        spec = _modern_card_spec(th)
        cx, cy = x + 6, y + 6
        if th.style == "macos":
            draw.rounded_rectangle((x + 1, y + 1, x + 11, y + 11), radius=3, fill=th.accent)
            draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill="#FFFFFF")
        elif th.style == "xiaomi":
            draw.rounded_rectangle((x + 1, y + 2, x + 11, y + 10), radius=4, fill=spec["bar_cpu"])
            draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill="#FFFFFF")
        else:
            draw.ellipse((x + 1, y + 1, x + 11, y + 11), fill=th.event_bg, outline=th.accent, width=1)
            draw.ellipse((cx - 2, cy - 2, cx + 2, cy + 2), fill=th.accent)
        return

    if not _is_paper(th):
        draw.rectangle((x + 2, y + 2, x + 10, y + 10), fill=th.accent)
        draw.rectangle((x + 4, y + 4, x + 8, y + 8), fill=th.paper)
        for offset in (4, 8):
            draw.line((x + offset, y, x + offset, y + 2), fill=th.accent, width=1)
            draw.line((x + offset, y + 10, x + offset, y + 12), fill=th.accent, width=1)
            draw.line((x, y + offset, x + 2, y + offset), fill=th.accent, width=1)
            draw.line((x + 10, y + offset, x + 12, y + offset), fill=th.accent, width=1)
        return

    cx, cy = x + 6, y + 6
    if th.is_dark:
        # Crescent moon in moonlight blue
        draw.ellipse((cx - 5, cy - 5, cx + 5, cy + 5), fill=th.accent)
        draw.ellipse((cx - 2, cy - 5, cx + 6, cy + 3), fill=th.paper)
    else:
        # Fine-line sun with soft amber rays
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=th.warn, width=1)
        for i in range(8):
            a = i * math.pi / 4
            draw.line(
                (cx + math.cos(a) * 4, cy + math.sin(a) * 4, cx + math.cos(a) * 6, cy + math.sin(a) * 6),
                fill=th.warn,
                width=1,
            )


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color: str) -> None:
    draw.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=color)


def _draw_weather_icon(draw: ImageDraw.ImageDraw, x: int, y: int, kind: str, th: ThemePalette) -> None:
    sun_c = th.warn if _is_paper(th) and not th.is_dark else th.accent
    if kind == "sun":
        cx, cy = x + 7, y + 7
        draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=sun_c)
        for i in range(8):
            a = i * math.pi / 4
            draw.line(
                (cx + math.cos(a) * 4.5, cy + math.sin(a) * 4.5, cx + math.cos(a) * 6.5, cy + math.sin(a) * 6.5),
                fill=sun_c,
                width=1,
            )
    elif kind == "partly":
        draw.ellipse((x + 6, y + 1, x + 12, y + 7), fill=sun_c)
        draw.rounded_rectangle((x + 1, y + 5, x + 11, y + 11), radius=3, fill=th.ink)
    elif kind == "rain":
        draw.rounded_rectangle((x + 1, y + 2, x + 12, y + 8), radius=3, fill=th.ink)
        for dx in (3, 6, 9):
            draw.line((x + dx + 1, y + 9, x + dx, y + 12), fill=th.accent, width=1)
    elif kind == "storm":
        draw.rounded_rectangle((x + 1, y + 2, x + 12, y + 8), radius=3, fill=th.ink)
        draw.line((x + 7, y + 8, x + 5, y + 11, x + 8, y + 11, x + 6, y + 14), fill=th.accent, width=1)
    else:
        draw.rounded_rectangle((x + 1, y + 4, x + 12, y + 10), radius=3, fill=th.ink)


def _draw_progress_bar(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    pct: int,
    th: ThemePalette,
    role: str = "cpu",
) -> None:
    if is_modern_desktop_style(th):
        spec = _modern_card_spec(th)
        bar_y = y + 1
        bar_h = 7 if th.style in ("pixel", "xiaomi") else 5
        rad = bar_h / 2.0
        draw.rounded_rectangle((x, bar_y, x + w, bar_y + bar_h), radius=rad, fill=th.track)
        fill_w = max(0, int(w * (pct / 100.0)))
        if fill_w > 0:
            role_key = f"bar_{role}" if f"bar_{role}" in spec else "bar_cpu"
            bar_color = spec["bar_high"] if pct >= 85 else spec[role_key]
            draw.rounded_rectangle((x, bar_y, max(x + bar_h, x + fill_w), bar_y + bar_h), radius=rad, fill=bar_color)
        return

    if _is_paper(th):
        bar_y = y + 1
        bar_h = 4
        draw.rectangle((x, bar_y, x + w, bar_y + bar_h), fill=th.track)
        fill_w = max(0, int(w * (pct / 100.0)))
        if fill_w > 0:
            bar_color = th.warn if pct >= 85 else (th.warn if not th.is_dark else th.accent)
            draw.rectangle((x, bar_y, x + fill_w, bar_y + bar_h), fill=bar_color)
            draw.ellipse((x + fill_w - 2, bar_y - 1, x + fill_w + 2, bar_y + bar_h + 1), fill=bar_color)
        return

    draw.rectangle((x, y, x + w, y + h), fill=th.track, outline=th.ink, width=1)
    fill_w = max(0, int((w - 2) * (pct / 100.0)))
    if fill_w > 0:
        bar_color = th.accent if pct >= 80 else th.fill
        draw.rectangle((x + 1, y + 1, x + 1 + fill_w, y + h - 1), fill=bar_color)


def _draw_inline_month_grid(
    draw,
    f: Fonts,
    th: ThemePalette,
    calendar_data: CalendarSummary,
    today: date,
    view_year: int,
    view_month: int,
    selected_date: date | None,
    rx: int,
    rw: int,
    top_y: int,
    hits: list[HitRegion],
    lang: str = "vi",
) -> None:
    is_en = (lang or "vi").strip().lower() == "en"
    is_modern = is_modern_desktop_style(th)
    if is_modern:
        draw.line((rx, top_y, rx + rw, top_y), fill=th.divider_soft, width=1)
    else:
        _draw_fineline_rule(draw, rx, top_y, rx + rw, top_y, th.divider_soft, th.accent, with_dots=_is_paper(th))

    wy = top_y + 20
    col_w = rw // 7
    grid_x = rx + (rw - col_w * 7) // 2
    gx1 = grid_x + 1
    gx2 = grid_x + col_w * 7 - 2

    nav_y = top_y + 4
    nav_h = 15
    btn_w = 18
    if is_modern:
        draw.rounded_rectangle((gx1, nav_y, gx1 + btn_w, nav_y + nav_h), radius=5, fill=th.btn_bg)
        _draw_text_centered(draw, (gx1, nav_y, gx1 + btn_w, nav_y + nav_h), "<", f.small_bold, th.ink)
        hits.append(HitRegion(gx1, nav_y, gx1 + btn_w, nav_y + nav_h, "prev_month"))

        nx = gx2 - btn_w
        draw.rounded_rectangle((nx, nav_y, gx2, nav_y + nav_h), radius=5, fill=th.btn_bg)
        _draw_text_centered(draw, (nx, nav_y, gx2, nav_y + nav_h), ">", f.small_bold, th.ink)
        hits.append(HitRegion(nx, nav_y, gx2, nav_y + nav_h, "next_month"))

        if view_year != today.year or view_month != today.month:
            btn_lbl = "Today" if is_en else "Hôm nay"
            btn_tw = _text_width(draw, btn_lbl, f.small_bold) + 10
            tx = nx - btn_tw - 4
            draw.rounded_rectangle((tx, nav_y, tx + btn_tw, nav_y + nav_h), radius=6, fill=th.pill, outline=th.accent, width=1)
            _draw_text_centered(draw, (tx, nav_y, tx + btn_tw, nav_y + nav_h), btn_lbl, f.small_bold, th.accent)
            hits.append(HitRegion(tx, nav_y, tx + btn_tw, nav_y + nav_h, "goto_today"))
            title_end_x = tx - 4
        else:
            title_end_x = nx - 4
    else:
        draw.rectangle((gx1, nav_y, gx1 + btn_w, nav_y + nav_h), fill=th.paper, outline=th.border_muted, width=1)
        _draw_text_centered(draw, (gx1, nav_y, gx1 + btn_w, nav_y + nav_h), "<", f.small_bold, th.ink)
        hits.append(HitRegion(gx1, nav_y, gx1 + btn_w, nav_y + nav_h, "prev_month"))

        nx = gx2 - btn_w
        draw.rectangle((nx, nav_y, gx2, nav_y + nav_h), fill=th.paper, outline=th.border_muted, width=1)
        _draw_text_centered(draw, (nx, nav_y, gx2, nav_y + nav_h), ">", f.small_bold, th.ink)
        hits.append(HitRegion(nx, nav_y, gx2, nav_y + nav_h, "next_month"))

        if view_year != today.year or view_month != today.month:
            btn_lbl = "Today" if is_en else "Hôm nay"
            btn_tw = _text_width(draw, btn_lbl, f.small_bold) + 10
            tx = nx - btn_tw - 4
            draw.rectangle((tx, nav_y, tx + btn_tw, nav_y + nav_h), fill=th.event_bg, outline=th.accent, width=1)
            _draw_text_centered(draw, (tx, nav_y, tx + btn_tw, nav_y + nav_h), btn_lbl, f.small_bold, th.accent_dark)
            hits.append(HitRegion(tx, nav_y, tx + btn_tw, nav_y + nav_h, "goto_today"))
            title_end_x = tx - 4
        else:
            title_end_x = nx - 4

    month_title = f"{pycal.month_name[view_month]} {view_year}" if is_en else f"Tháng {view_month:02d}/{view_year}"
    _draw_text_centered(
        draw,
        (gx1 + btn_w + 4, nav_y, title_end_x, nav_y + nav_h),
        month_title,
        f.cal_title,
        th.ink,
        v_sample="T0123456789/",
    )

    weekdays = EN_WEEKDAYS if is_en else VN_WEEKDAYS
    wd_sample = "".join(weekdays)
    for idx, wd in enumerate(weekdays):
        cx = grid_x + idx * col_w
        color = (th.warn if th.style == "xiaomi" else th.accent) if idx >= 5 else th.muted
        _draw_text_centered(draw, (cx + 1, wy + 1, cx + col_w - 2, wy + 13), wd, f.cal_day_bold, color, v_sample=wd_sample)

    cal_matrix = pycal.Calendar(firstweekday=0).monthdatescalendar(view_year, view_month)
    grid_y = wy + 13
    row_h = 15

    for r_idx, week in enumerate(cal_matrix[:6]):
        cy = grid_y + r_idx * row_h
        for c_idx, d_obj in enumerate(week):
            cx = grid_x + c_idx * col_w
            x1, y1, x2, y2 = cx + 1, cy, cx + col_w - 2, cy + row_h - 2
            in_month = d_obj.month == view_month
            day_events = calendar_data.events_by_date.get(d_obj, [])
            has_events = bool(day_events)
            is_today = d_obj == today
            is_selected = selected_date is not None and d_obj == selected_date

            fill_c = None
            outline_c = None
            outline_w = 1
            txt_c = th.ink if in_month else th.out_month
            font_use = f.cal_day

            if in_month and has_events:
                fill_c = th.event_bg
                txt_c = th.accent_dark
                font_use = f.cal_day_bold
            elif is_selected:
                fill_c = th.selected_bg

            if is_today:
                if is_modern:
                    spec_m = _modern_card_spec(th)
                    if th.style == "macos":
                        fill_c = spec_m["today_fill"]
                        outline_c = spec_m["today_fill"]
                        txt_c = "#FFFFFF"
                    elif th.style == "xiaomi":
                        fill_c = spec_m["today_fill"] if is_selected else th.today_bg
                        outline_c = spec_m["today_fill"]
                        if is_selected:
                            txt_c = "#FFFFFF"
                    else:
                        fill_c = spec_m["today_fill"]
                        outline_c = spec_m["today_fill"]
                        txt_c = "#FFFFFF"
                else:
                    outline_c = th.ink
                outline_w = 1
                font_use = f.cal_day_bold

            if is_selected and not (is_modern and is_today):
                outline_c = th.accent
                outline_w = 2
                font_use = f.cal_day_bold

            if fill_c or outline_c:
                if is_modern:
                    rad_d = 7 if th.style in ("pixel", "macos") else 4
                    draw.rounded_rectangle((x1, y1, x2, y2), radius=rad_d, fill=fill_c, outline=outline_c, width=outline_w)
                else:
                    draw.rectangle((x1, y1, x2, y2), fill=fill_c, outline=outline_c, width=outline_w)

            d_txt = str(d_obj.day)
            _draw_text_centered(draw, (x1, y1, x2, y2), d_txt, font_use, txt_c, v_sample="0123456789")

            if in_month and len(day_events) > 1:
                if is_modern:
                    draw.ellipse((x2 - 5, y2 - 4, x2 - 2, y2 - 1), fill=th.accent)
                else:
                    draw.rectangle((x2 - 4, y2 - 4, x2 - 2, y2 - 2), fill=th.accent)

            hits.append(HitRegion(x1, y1, x2, y2, "select_date", d_obj))


SYS_BOX_X1 = 8
SYS_BOX_Y1 = 27
SYS_BOX_Y2 = 125


@dataclass
class SystemPatchCache:
    """Cached background crop & layout metadata for 2s real-time SYSTEM repaints without full-card redraws."""

    clean_sys_hires: Image.Image
    display_img: Image.Image
    screen_1x: Image.Image
    fonts: Fonts
    theme: ThemePalette
    ss: int
    scale: float
    factor: float
    bezel_ox: int
    bezel_oy: int
    div_x: int
    non_sys_hits: list[HitRegion]


def _draw_system_section(
    draw: _ScaledDraw,
    f: Fonts,
    th: ThemePalette,
    lx: int,
    lw: int,
    system_stats: SystemStats,
    temp_unit: str,
    lang: str,
    hits: list[HitRegion],
) -> None:
    is_en = (lang or "vi").strip().lower() == "en"
    is_mod = is_modern_desktop_style(th)
    hdr_y = 30 if is_mod else (33 if _is_paper(th) else 31)
    glyph_y = 32 if is_mod else (33 if _is_paper(th) else 32)
    meta_y = 32 if is_mod else (34 if _is_paper(th) else 32)
    _draw_section_glyph(draw, lx, glyph_y, th)
    sys_hdr = "SYSTEM" if is_en else "HỆ THỐNG"
    draw.text((lx + 16, hdr_y), sys_hdr, font=f.section, fill=th.accent)

    unit_norm = "F" if (temp_unit or "C").strip().upper() == "F" else "C"
    sys_temp_txt = ""
    if system_stats.cpu_temp_c is not None and system_stats.gpu_temp_c is not None:
        sys_temp_txt = (
            f"{format_temp(system_stats.cpu_temp_c, unit_norm, with_unit=True)}"
            f" · GPU {format_temp(system_stats.gpu_temp_c, unit_norm, with_unit=False)}"
        )
    elif system_stats.cpu_temp_c is not None:
        sys_temp_txt = format_temp(system_stats.cpu_temp_c, unit_norm, with_unit=True)
    elif system_stats.gpu_temp_c is not None:
        sys_temp_txt = f"GPU {format_temp(system_stats.gpu_temp_c, unit_norm, with_unit=True)}"

    if sys_temp_txt:
        hdr_end = lx + 16 + _text_width(draw, sys_hdr, f.section) + 6
        max_tw = max(24, (lx + lw) - hdr_end)
        tw = _text_width(draw, sys_temp_txt, f.small)
        if tw > max_tw:
            if system_stats.cpu_temp_c is not None and system_stats.gpu_temp_c is not None:
                sys_temp_txt = (
                    f"{convert_temp(system_stats.cpu_temp_c, unit_norm)}°/"
                    f"{format_temp(system_stats.gpu_temp_c, unit_norm, with_unit=True)}"
                )
            sys_temp_txt = _truncate_text(draw, sys_temp_txt, f.small, max_tw)
            tw = _text_width(draw, sys_temp_txt, f.small)
        tx = lx + lw - tw
        draw.text((tx, meta_y), sys_temp_txt, font=f.small, fill=th.muted)
        hits.append(HitRegion(tx - 2, 28, lx + lw, 44, "toggle_temp_unit", None))

    y_ram = 47 if _is_paper(th) else 46
    ram_lbl = f"RAM {system_stats.ram_used_gb:.1f}/{system_stats.ram_total_gb:.1f}G"
    ram_pct_txt = f"{system_stats.ram_pct}%"
    draw.text((lx, y_ram), ram_lbl, font=f.label, fill=th.ink)
    draw.text((lx + lw - _text_width(draw, ram_pct_txt, f.pct), y_ram), ram_pct_txt, font=f.pct, fill=th.ink)
    _draw_progress_bar(draw, lx, y_ram + 15, lw, 6, system_stats.ram_pct, th, role="ram")
    hits.append(HitRegion(lx, y_ram, lx + lw, y_ram + 22, "inspect_system", "ram"))

    y_cpu = 72
    cpu_pct_txt = f"{system_stats.cpu_pct}%"
    draw.text((lx, y_cpu), "CPU", font=f.label, fill=th.ink)
    draw.text((lx + lw - _text_width(draw, cpu_pct_txt, f.pct), y_cpu), cpu_pct_txt, font=f.pct, fill=th.ink)
    _draw_progress_bar(draw, lx, y_cpu + 15, lw, 6, system_stats.cpu_pct, th, role="cpu")
    hits.append(HitRegion(lx, y_cpu, lx + lw, y_cpu + 22, "inspect_system", "cpu"))

    y_gpu = 98
    if system_stats.gpu_pct is not None:
        if system_stats.gpu_vram_used_mb is not None and system_stats.gpu_vram_total_mb:
            vram_u = system_stats.gpu_vram_used_mb / 1024.0
            vram_t = system_stats.gpu_vram_total_mb / 1024.0
            gpu_lbl = f"GPU {vram_u:.1f}/{vram_t:.1f}G"
        else:
            gpu_lbl = "GPU"
        gpu_pct_txt = f"{system_stats.gpu_pct}%"
        gpu_val = system_stats.gpu_pct
    else:
        gpu_lbl = "GPU"
        gpu_pct_txt = "N/A"
        gpu_val = 0
    draw.text((lx, y_gpu), gpu_lbl, font=f.label, fill=th.ink)
    draw.text((lx + lw - _text_width(draw, gpu_pct_txt, f.pct), y_gpu), gpu_pct_txt, font=f.pct, fill=th.ink)
    _draw_progress_bar(draw, lx, y_gpu + 15, lw, 6, gpu_val, th, role="gpu")
    hits.append(HitRegion(lx, y_gpu, lx + lw, y_gpu + 22, "inspect_system", "gpu"))


def _draw_meeting_pill(
    draw: ImageDraw.ImageDraw,
    f: Fonts,
    th: ThemePalette,
    label: str,
    url: str,
    right_x: int,
    y: int,
    hits: list[HitRegion],
) -> int:
    txt_w = _text_width(draw, label, f.tiny_bold)
    btn_w = txt_w + 10
    x1 = right_x - btn_w
    y1 = y
    x2 = right_x
    y2 = y + 14
    if is_modern_desktop_style(th):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=5, fill=th.accent)
    else:
        draw.rectangle((x1, y1, x2, y2), fill=th.accent, outline=th.accent_dark, width=1)
    _draw_text_centered(draw, (x1, y1, x2, y2), label, f.tiny_bold, "#FFFFFF")
    hits.append(HitRegion(x1, y1, x2, y2, "open_url", url))
    return btn_w + 5


def _render_screen_hires(
    calendar_data: CalendarSummary,
    weather_data: WeatherData,
    system_stats: SystemStats,
    owner_name: str = "Desk Widget",
    owner_align: str = "center",
    theme_mode: str = "auto",
    style: str = "serif",
    temp_unit: str = "C",
    lang: str = "vi",
    logo_path: str | None = None,
    bg_path: str | None = None,
    ss: int = 2,
    now: datetime | None = None,
    view_year: int | None = None,
    view_month: int | None = None,
    selected_date: date | None = None,
    selected_weather_date: date | None = None,
    logo_pos: str = "before_title",
    bg_pos: str = "cover",
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
    bg_opacity: float | None = None,
) -> tuple[Image.Image, list[HitRegion], ThemePalette, Image.Image, Fonts, int]:
    """Render screen internally at `ss`x supersampled resolution (logical 480x224 coords)."""
    if now is None:
        now = datetime.now()

    is_en = (lang or "vi").strip().lower() == "en"
    th = resolve_theme(theme_mode, now=now, style=style)
    today = now.date()
    vy = view_year or today.year
    vm = view_month or today.month
    div_x = 202
    s = max(1, int(ss))
    cw, ch = SCREEN_W * s, SCREEN_H * s
    is_modern = is_modern_desktop_style(th)

    active_bg_path = ""
    outer_mask: Image.Image | None = None
    no_bg = str(bg_path or "").strip().lower() == "__none__"
    eff_bg_path = None if no_bg else bg_path
    is_opaque_bg = (not no_bg) and _bg_is_opaque_photo(eff_bg_path)
    opaque_user_bg = is_modern and is_opaque_bg
    eff_op = max(0.10, min(1.0, float(bg_opacity))) if bg_opacity is not None else None
    if is_modern:
        spec = _modern_card_spec(th)
        outer_r = int(round(spec["outer_r"] * s))
        outer_mask = Image.new("L", (cw, ch), 0)
        ImageDraw.Draw(outer_mask).rounded_rectangle((0, 0, cw - 1, ch - 1), radius=outer_r, fill=255)
        img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        shell_layer = Image.new("RGBA", (cw, ch), (*_hex_to_rgb(th.paper), 255))
        img.paste(shell_layer, (0, 0), outer_mask)
        if opaque_user_bg:
            active_bg_path = _apply_widget_background(
                img,
                eff_bg_path,
                div_x * s,
                127 * s,
                154 * s,
                th.is_dark,
                bg_pos=bg_pos,
                outer_mask=outer_mask,
                photo_alpha=(eff_op if eff_op is not None else 0.80),
                bg_tone=bg_tone,
                bg_zoom=bg_zoom,
                bg_offset_x=bg_offset_x,
                bg_offset_y=bg_offset_y,
            )
    elif _is_paper(th):
        img = _get_paper_texture(cw, ch, th).copy()
        if not no_bg:
            active_bg_path = _apply_widget_background(
                img,
                eff_bg_path,
                div_x * s,
                127 * s,
                154 * s,
                th.is_dark,
                bg_pos=bg_pos,
                photo_alpha=eff_op,
                emblem_alpha=eff_op,
                bg_tone=bg_tone,
                bg_zoom=bg_zoom,
                bg_offset_x=bg_offset_x,
                bg_offset_y=bg_offset_y,
            )
    else:
        img = Image.new("RGBA", (cw, ch), th.paper)
        if not no_bg:
            active_bg_path = _apply_widget_background(
                img,
                eff_bg_path,
                div_x * s,
                127 * s,
                154 * s,
                th.is_dark,
                bg_pos=bg_pos,
                photo_alpha=eff_op,
                emblem_alpha=eff_op,
                bg_tone=bg_tone,
                bg_zoom=bg_zoom,
                bg_offset_x=bg_offset_x,
                bg_offset_y=bg_offset_y,
            )

    if (not is_modern) and is_opaque_bg and eff_op is not None and eff_op > 0.25:
        # Frosted readability scrim behind text zones so vivid wallpapers never hurt legibility
        scrim_a = max(0, min(162, int(round((eff_op - 0.18) * 190))))
        if scrim_a > 0:
            s_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
            s_draw = _ScaledDraw(ImageDraw.Draw(s_layer), scale=float(s))
            s_fill = (*_hex_to_rgb(th.paper), scrim_a)
            s_draw.rounded_rectangle((6, 2, SCREEN_W - 7, 23), radius=6, fill=s_fill)
            s_draw.rounded_rectangle((5, 27, div_x - 4, SCREEN_H - 5), radius=6, fill=s_fill)
            s_draw.rounded_rectangle((div_x + 4, 27, SCREEN_W - 6, SCREEN_H - 5), radius=6, fill=s_fill)
            img.alpha_composite(s_layer, (0, 0))

    draw = _ScaledDraw(ImageDraw.Draw(img), scale=float(s))
    f = Fonts(style=th.style, scale=float(s))
    hits: list[HitRegion] = []

    if is_modern:
        spec = _modern_card_spec(th)
        if opaque_user_bg:
            b_alpha = max(132, min(202, int(round(124 + 74 * (eff_op if eff_op is not None else 0.80)))))
        else:
            b_alpha = 255
        b_out = (*_hex_to_rgb(spec["bento_border"]), 255)
        b_layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        b_draw = _ScaledDraw(ImageDraw.Draw(b_layer), scale=float(s))
        if opaque_user_bg:
            hdr_fill = (*_hex_to_rgb(th.paper), max(138, min(206, b_alpha)))
            b_draw.rounded_rectangle((4, 2, SCREEN_W - 5, 24), radius=9, fill=hdr_fill)
        for (bx1, by1, bx2, by2), b_key in (
            ((5, 27, 199, 125), "bento_sys"),
            ((5, 129, 199, 219), "bento_wx"),
            ((204, 27, 475, 219), "bento_cal"),
        ):
            b_fill = (*_hex_to_rgb(spec[b_key]), b_alpha)
            b_draw.rounded_rectangle((bx1, by1, bx2, by2), radius=spec["inner_r"], fill=b_fill, outline=b_out, width=1)
        img.alpha_composite(b_layer, (0, 0))
        if not opaque_user_bg and not no_bg:
            # Render transparent PNG custom background or default watermark smoothly above Bento surface
            def_em_a = 0.52 if (eff_bg_path and os.path.exists(str(eff_bg_path))) else 0.36
            active_bg_path = _apply_widget_background(
                img,
                eff_bg_path,
                div_x * s,
                127 * s,
                154 * s,
                th.is_dark,
                bg_pos=bg_pos,
                outer_mask=outer_mask,
                emblem_alpha=(eff_op if (eff_op is not None and eff_bg_path and os.path.exists(str(eff_bg_path))) else def_em_a),
                bg_tone=bg_tone,
                bg_zoom=bg_zoom,
                bg_offset_x=bg_offset_x,
                bg_offset_y=bg_offset_y,
            )
        draw.rounded_rectangle((0, 0, SCREEN_W - 1, SCREEN_H - 1), radius=spec["outer_r"], outline=th.card_border, width=1)
    elif _is_paper(th):
        draw.rectangle((0, 0, SCREEN_W - 1, SCREEN_H - 1), outline=th.card_border, width=1)
        for cx, cy in ((4, 4), (SCREEN_W - 5, 4), (4, SCREEN_H - 5), (SCREEN_W - 5, SCREEN_H - 5)):
            draw.point((cx, cy), fill=th.accent)

    # 1. Top Header Bar (align all items along exact visual centerline y = 12.5)
    bar_mid_y = 12.5

    def _y_for_mid(sample: str, font) -> float:
        box = draw.textbbox((0, 0), sample, font=font)
        return bar_mid_y - ((box[1] + box[3]) / (2.0 * s))

    badge_d = 17
    badge_gap = 5
    resolved_badge_path = (active_bg_path or _default_emblem_path(th.is_dark)) if logo_path == "__widget_bg__" else logo_path
    badge = _load_circle_logo(resolved_badge_path, size=badge_d * s, border_color=th.border_muted, fill_bg=th.paper)
    l_pos = (logo_pos or "before_title").strip().lower()
    if l_pos not in ("before_title", "after_title", "far_left", "far_right"):
        l_pos = "before_title"

    left_x0 = 10
    if th.style == "macos":
        for di, dc in enumerate(("#FF5F57", "#FEBC2E", "#28C840")):
            dcx = 12 + di * 9
            draw.ellipse((dcx - 2.5, bar_mid_y - 2.5, dcx + 2.5, bar_mid_y + 2.5), fill=dc)
        left_x0 = 39
    if badge is not None and l_pos == "far_left":
        by = int(round((bar_mid_y - badge_d / 2.0) * s))
        img.alpha_composite(badge, (int(round(left_x0 * s)), by))
        left_x0 += badge_d + badge_gap

    weekdays = EN_WEEKDAYS if is_en else VN_WEEKDAYS
    wd = weekdays[now.weekday()]
    date_str = f"{wd} {now.strftime('%d/%m')}"
    draw.text((left_x0, _y_for_mid("H0", f.header_date)), date_str, font=f.header_date, fill=th.ink)
    date_w = _text_width(draw, date_str, f.header_date)
    time_sub = f"· {now.strftime('%H:%M')}"
    draw.text((left_x0 + 6 + date_w, _y_for_mid("22:35", f.header_sub)), time_sub, font=f.header_sub, fill=th.muted)
    left_end = left_x0 + 6 + date_w + _text_width(draw, time_sub, f.header_sub)

    hdr_right = system_stats.gpu_name
    hdr_w = _text_width(draw, hdr_right, f.header_sub)
    right_edge = SCREEN_W - 10
    if badge is not None and l_pos == "far_right":
        bx_far = right_edge - badge_d
        by = int(round((bar_mid_y - badge_d / 2.0) * s))
        img.alpha_composite(badge, (int(round(bx_far * s)), by))
        right_edge = bx_far - badge_gap
    right_start = right_edge - hdr_w
    draw.text((right_start, _y_for_mid("RTX", f.header_sub)), hdr_right, font=f.header_sub, fill=th.muted)

    owner_clean = owner_name.strip()
    if owner_clean:
        avail_left = left_end + 10
        avail_right = right_start - 10
        avail_w = max(40, avail_right - avail_left)

        inline_badge = badge if l_pos in ("before_title", "after_title") else None
        badge_w = (badge_d + badge_gap) if inline_badge is not None else 0

        owner_font = f.header_date
        text_w = _text_width(draw, owner_clean, owner_font)
        if badge_w + text_w > avail_w:
            font_file = "palab.ttf" if _is_paper(th) else "segoeuib.ttf"
            for sz in (13, 12, 11, 10):
                cand_font = _load_font(font_file, int(round(sz * s)))
                cand_w = _text_width(draw, owner_clean, cand_font)
                owner_font = cand_font
                text_w = cand_w
                if badge_w + text_w <= avail_w:
                    break

        total_w = badge_w + text_w
        align = (owner_align or "center").strip().lower()
        if align == "left":
            ox = avail_left
        elif align == "right":
            ox = max(avail_left, avail_right - total_w)
        else:
            ideal_center = (SCREEN_W - total_w) // 2
            ox = max(avail_left, min(ideal_center, avail_right - total_w))

        by = int(round((bar_mid_y - badge_d / 2.0) * s))
        if inline_badge is not None and l_pos == "before_title":
            img.alpha_composite(inline_badge, (int(round(ox * s)), by))
            ox += badge_w
        text_avail = (avail_right - ox - (badge_w if l_pos == "after_title" and inline_badge is not None else 0))
        owner_trunc = _truncate_text(draw, owner_clean, owner_font, max(20, text_avail))
        draw.text((ox, _y_for_mid("Hp", owner_font)), owner_trunc, font=owner_font, fill=th.accent)
        if inline_badge is not None and l_pos == "after_title":
            tw_drawn = _text_width(draw, owner_trunc, owner_font)
            img.alpha_composite(inline_badge, (int(round((ox + tw_drawn + badge_gap) * s)), by))
    elif badge is not None and l_pos in ("before_title", "after_title"):
        by = int(round((bar_mid_y - badge_d / 2.0) * s))
        img.alpha_composite(badge, (int(round(((SCREEN_W - badge_d) // 2) * s)), by))

    if not is_modern:
        if not _is_paper(th):
            _draw_fineline_rule(draw, div_x, 30, div_x, SCREEN_H - 8, th.ink, th.accent, with_dots=False)

    # 2. Left Column: RAM / CPU / GPU + 7-day Weather
    lx = 10
    lw = div_x - lx - 10
    sys_x2 = div_x - 4
    clean_sys_hires = img.crop((SYS_BOX_X1 * s, SYS_BOX_Y1 * s, sys_x2 * s, SYS_BOX_Y2 * s))
    unit_norm = "F" if (temp_unit or "C").strip().upper() == "F" else "C"
    _draw_system_section(draw, f, th, lx, lw, system_stats, unit_norm, lang, hits)

    if not is_modern:
        _draw_fineline_rule(draw, lx, 127, lx + lw, 127, th.divider_soft, th.accent, with_dots=_is_paper(th))

    # Weather (Today + interactive 7-day strip)
    wy = 132 if is_modern else 131
    city_disp = format_city_name(weather_data.city, lang)
    if weather_data.error:
        draw.text((lx, wy), f"{city_disp}: {weather_data.error[:22]}", font=f.small, fill=th.accent)
    else:
        _draw_weather_icon(draw, lx, wy + 1, weather_data.current_icon, th)
        city_temp = f"{city_disp} {format_temp(weather_data.current_temp, unit_norm, with_unit=True)}"
        draw.text((lx + 17, wy), city_temp, font=f.small_bold, fill=th.ink)
        cur_desc_disp = weather_desc_for_lang(weather_data.current_code, weather_data.current_desc, lang)
        desc_txt = _truncate_text(
            draw,
            cur_desc_disp,
            f.small,
            lw - _text_width(draw, city_temp, f.small_bold) - 22,
        )
        draw.text((lx + lw - _text_width(draw, desc_txt, f.small), wy + 1), desc_txt, font=f.small, fill=th.muted)

        today_lbl = "Today" if is_en else "Hôm nay"
        rain_lbl = "Rain" if is_en else "Mưa"
        today_line = (
            f"{today_lbl} {format_temp(weather_data.today_min, unit_norm, with_unit=False)}"
            f"–{format_temp(weather_data.today_max, unit_norm, with_unit=False)}"
            f" · {rain_lbl} {weather_data.today_rain_prob}%"
        )
        draw.text((lx, wy + 16), _truncate_text(draw, today_line, f.small, lw), font=f.small, fill=th.ink)

        if weather_data.weekly:
            days_7 = weather_data.weekly[:7]
            col_w = lw // max(1, len(days_7))
            fy = wy + 33
            box_h = 52
            for idx, day in enumerate(days_7):
                cx = lx + idx * col_w
                x1, y1, x2, y2 = cx, fy, cx + col_w - 2, fy + box_h
                is_today_w = day.date_obj == today
                is_sel_w = selected_weather_date is not None and day.date_obj == selected_weather_date

                fill_w = th.event_bg if is_sel_w else (th.today_bg if is_today_w else None)
                out_w = th.accent if is_sel_w else (th.border_muted if is_today_w else None)
                out_thick = 2 if is_sel_w else 1
                if fill_w or out_w:
                    if is_modern:
                        draw.rounded_rectangle((x1, y1, x2, y2), radius=7, fill=fill_w, outline=out_w, width=out_thick)
                    else:
                        draw.rectangle((x1, y1, x2, y2), fill=fill_w, outline=out_w, width=out_thick)

                wd_disp = day_abbr_for_lang(day.date_obj, day.weekday, lang)
                wd_c = (th.warn if th.style == "xiaomi" else th.accent) if day.date_obj.weekday() >= 5 else th.ink
                _draw_text_centered(draw, (x1, y1 + 1, x2, y1 + 13), wd_disp, f.tiny_bold, wd_c, v_sample="T2CN")

                _draw_weather_icon(draw, x1 + (x2 - x1 - 14) // 2, y1 + 14, day.icon, th)

                hi_txt = format_temp(day.temp_max, unit_norm, with_unit=False)
                lo_txt = format_temp(day.temp_min, unit_norm, with_unit=False)
                _draw_text_centered(draw, (x1, y1 + 29, x2, y1 + 39), hi_txt, f.tiny_bold, th.ink, v_sample="0123456789")
                _draw_text_centered(draw, (x1, y1 + 39, x2, y1 + 49), lo_txt, f.tiny, th.muted, v_sample="0123456789")

                hits.append(HitRegion(x1, y1, x2, y2, "select_weather_day", day))

    # 3. Right Column (Calendar): HÔM NAY / TODAY + 1-click app buttons + 1-Month Calendar
    rx = div_x + 12
    rw = SCREEN_W - rx - 10
    cal_hdr_y = 30 if is_modern else (33 if _is_paper(th) else 31)
    cal_meta_y = 32 if is_modern else (34 if _is_paper(th) else 32)
    draw.text((rx, cal_hdr_y), "TODAY" if is_en else "HÔM NAY", font=f.section, fill=(th.warn if th.style == "macos" else th.accent))
    done_txt = f"done {calendar_data.done_count}" if is_en else f"đã xong {calendar_data.done_count}"
    draw.text((rx + rw - _text_width(draw, done_txt, f.small), cal_meta_y), done_txt, font=f.small, fill=th.muted)

    ey = 48 if is_modern else 47
    month_top_y = 92 if len(calendar_data.events_today) > 2 else 88
    if not calendar_data.has_urls:
        msg1 = "No Google Calendar .ics link" if is_en else "Chưa có link .ics Google Calendar"
        msg2 = "Right-click → Settings to add link." if is_en else "Chuột phải → Cài đặt để dán link."
        draw.text((rx, ey), msg1, font=f.event_time, fill=th.ink)
        draw.text((rx, ey + 16), msg2, font=f.small, fill=th.muted)
    elif calendar_data.error and not calendar_data.events_today and not calendar_data.upcoming_events:
        err_prefix = "Calendar error:" if is_en else "Lỗi lịch:"
        err_lines = _wrap_lines(draw, f"{err_prefix} {calendar_data.error}", f.small, rw, max_lines=2)
        for i, line in enumerate(err_lines):
            draw.text((rx, ey + i * 14), line, font=f.small, fill=th.accent)
    elif calendar_data.events_today:
        has_more = len(calendar_data.events_today) > 2
        row_step = 15 if has_more else 17
        for ev in calendar_data.events_today[:2]:
            t_color = th.muted if ev.is_done else (th.accent if ev.is_ongoing else th.ink)
            draw.text((rx, ey), format_event_time(ev, lang), font=f.event_time, fill=t_color)
            if ev.is_all_day or ev.is_ongoing:
                _draw_diamond(draw, rx + 47, ey + 7, 3, th.accent)
            btn_w = 0
            links = extract_meeting_links(ev, lang=lang) if not ev.is_done else []
            if links:
                btn_lbl, btn_url = links[0]
                btn_w = _draw_meeting_pill(draw, f, th, btn_lbl, btn_url, rx + rw, ey, hits)
            t_x = rx + 55
            label_title = f"[{ev.calendar_name}] {ev.title}" if ev.calendar_name else ev.title
            title_txt = _truncate_text(draw, label_title, f.event_title, rw - 55 - btn_w)
            draw.text((t_x, ey), title_txt, font=f.event_title, fill=th.muted if ev.is_done else th.ink)
            if ev.is_done:
                lw_line = _text_width(draw, title_txt, f.event_title)
                draw.line((t_x, ey + 7, t_x + lw_line, ey + 7), fill=th.muted, width=1)
            hits.append(HitRegion(rx, ey, rx + rw - btn_w, ey + 15, "select_date", today))
            ey += row_step
        if has_more:
            n_more = len(calendar_data.events_today) - 2
            more_txt = (
                f"+{n_more} more events (click to view)"
                if is_en
                else f"+{n_more} sự kiện khác (bấm để xem)"
            )
            draw.text((rx, ey), _truncate_text(draw, more_txt, f.small, rw), font=f.small, fill=th.accent)
            hits.append(HitRegion(rx, ey, rx + rw, ey + 13, "select_date", today))
    else:
        no_ev_txt = "No events today" if is_en else "Không có sự kiện hôm nay"
        draw.text((rx, ey), no_ev_txt, font=f.event_title, fill=th.muted)
        if calendar_data.upcoming_events:
            ev0 = calendar_data.upcoming_events[0]
            btn_w = 0
            links = extract_meeting_links(ev0, lang=lang)
            if links:
                btn_lbl, btn_url = links[0]
                btn_w = _draw_meeting_pill(draw, f, th, btn_lbl, btn_url, rx + rw, ey + 16, hits)
            d_str = ev0.start.strftime("%d/%m")
            t_str = format_event_time(ev0, lang)
            prefix = f"[{ev0.calendar_name}] " if ev0.calendar_name else ""
            up_lbl = "Upcoming" if is_en else "Sắp tới"
            next_txt = _truncate_text(draw, f"{up_lbl}: {d_str} · {t_str} · {prefix}{ev0.title}", f.small, rw - btn_w)
            draw.text((rx, ey + 17), next_txt, font=f.small, fill=th.ink)
            hits.append(HitRegion(rx, ey + 15, rx + rw - btn_w, ey + 31, "select_date", ev0.start.date()))

    _draw_inline_month_grid(
        draw, f, th, calendar_data, today, vy, vm, selected_date, rx, rw, month_top_y, hits, lang=lang
    )

    out_screen = img if is_modern else img.convert("RGB")
    return out_screen, hits, th, clean_sys_hires, f, div_x


def render_screen(
    calendar_data: CalendarSummary,
    weather_data: WeatherData,
    system_stats: SystemStats,
    owner_name: str = "Desk Widget",
    owner_align: str = "center",
    theme_mode: str = "auto",
    style: str = "serif",
    temp_unit: str = "C",
    lang: str = "vi",
    logo_path: str | None = None,
    bg_path: str | None = None,
    now: datetime | None = None,
    view_year: int | None = None,
    view_month: int | None = None,
    selected_date: date | None = None,
    selected_weather_date: date | None = None,
    logo_pos: str = "before_title",
    bg_pos: str = "cover",
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
    bg_opacity: float | None = None,
) -> tuple[Image.Image, list[HitRegion], ThemePalette]:
    """Render crisp 480x224 screen image (2x supersampled), hit regions, and active theme."""
    hires, hits, th, _, _, _ = _render_screen_hires(
        calendar_data,
        weather_data,
        system_stats,
        owner_name=owner_name,
        owner_align=owner_align,
        theme_mode=theme_mode,
        style=style,
        temp_unit=temp_unit,
        lang=lang,
        logo_path=logo_path,
        bg_path=bg_path,
        ss=2,
        now=now,
        view_year=view_year,
        view_month=view_month,
        selected_date=selected_date,
        selected_weather_date=selected_weather_date,
        logo_pos=logo_pos,
        bg_pos=bg_pos,
        bg_tone=bg_tone,
        bg_zoom=bg_zoom,
        bg_offset_x=bg_offset_x,
        bg_offset_y=bg_offset_y,
        bg_opacity=bg_opacity,
    )
    return hires.resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS), hits, th


def wrap_esl_bezel(
    screen_img: Image.Image, th: ThemePalette, bezel_scale: float = 1.0
) -> tuple[Image.Image, tuple[int, int]]:
    s = float(bezel_scale)
    pad_left = int(round(44 * s))
    pad_right = int(round(34 * s))
    pad_top = int(round(16 * s))
    pad_bottom = int(round(20 * s))
    w = pad_left + screen_img.width + pad_right
    h = pad_top + screen_img.height + pad_bottom

    frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = _ScaledDraw(ImageDraw.Draw(frame), scale=s)
    lw = w / s
    lh = h / s

    draw.rounded_rectangle((0, 0, lw - 1, lh - 1), radius=14, fill=th.bezel, outline=th.bezel_border, width=2)
    sx, sy = pad_left, pad_top
    draw.rectangle(
        (44 - 2, 16 - 2, 44 + (screen_img.width / s) + 1, 16 + (screen_img.height / s) + 1),
        outline=th.bezel_shadow,
        width=2,
    )
    frame.paste(screen_img, (sx, sy))

    bx = 12
    by1, by2 = 24, lh - 24
    strip_bg = "#383935" if th.is_dark else "#FFFFFF"
    bar_fg = "#DCDCD6" if th.is_dark else "#222222"
    draw.rectangle((bx - 2, by1 - 2, bx + 18, by2 + 2), fill=strip_bg, outline=th.border_muted, width=1)
    y_cur = by1 + 2
    pattern = [2, 1, 3, 1, 1, 2, 1, 2, 3, 1, 1, 2, 2, 1, 3, 1, 2, 1, 1, 2, 3, 1, 2]
    idx = 0
    while y_cur < by2 - 4:
        bar_h = pattern[idx % len(pattern)]
        if idx % 2 == 0:
            draw.rectangle((bx, y_cur, bx + 14, min(y_cur + bar_h, by2 - 2)), fill=bar_fg)
        y_cur += bar_h + 1
        idx += 1

    px = 44 + (screen_img.width / s) + 10
    py = lh / 2 - 28
    draw.rounded_rectangle((px, py, px + 14, py + 56), radius=7, fill=th.pill, outline=th.border_muted, width=1)
    draw.text((px - 1, lh - 28), "ESL", font=_load_font("segoeuib.ttf", max(8, int(round(9 * s)))), fill="#5B9BD5")

    return frame, (pad_left, pad_top)


def render_widget_cached(
    calendar_data: CalendarSummary,
    weather_data: WeatherData,
    system_stats: SystemStats,
    owner_name: str = "Desk Widget",
    owner_align: str = "center",
    theme_mode: str = "auto",
    style: str = "serif",
    temp_unit: str = "C",
    lang: str = "vi",
    logo_path: str | None = None,
    bg_path: str | None = None,
    show_esl_frame: bool = False,
    scale: float = 1.0,
    now: datetime | None = None,
    view_year: int | None = None,
    view_month: int | None = None,
    selected_date: date | None = None,
    selected_weather_date: date | None = None,
    logo_pos: str = "before_title",
    bg_pos: str = "cover",
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
    bg_opacity: float | None = None,
) -> tuple[Image.Image, list[HitRegion], Image.Image, ThemePalette, SystemPatchCache]:
    ss = max(2, int(math.ceil(float(scale) * 2.0)))
    hires, raw_hits, th, clean_sys_hires, f, div_x = _render_screen_hires(
        calendar_data,
        weather_data,
        system_stats,
        owner_name=owner_name,
        owner_align=owner_align,
        theme_mode=theme_mode,
        style=style,
        temp_unit=temp_unit,
        lang=lang,
        logo_path=logo_path,
        bg_path=bg_path,
        ss=ss,
        now=now,
        view_year=view_year,
        view_month=view_month,
        selected_date=selected_date,
        selected_weather_date=selected_weather_date,
        logo_pos=logo_pos,
        bg_pos=bg_pos,
        bg_tone=bg_tone,
        bg_zoom=bg_zoom,
        bg_offset_x=bg_offset_x,
        bg_offset_y=bg_offset_y,
        bg_opacity=bg_opacity,
    )
    screen_1x = hires.resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)
    if abs(scale - 1.0) > 0.02:
        target_w = max(240, int(round(SCREEN_W * scale)))
        target_h = max(112, int(round(SCREEN_H * scale)))
        screen_scaled = hires.resize((target_w, target_h), Image.Resampling.LANCZOS)
        factor = target_w / SCREEN_W
    else:
        screen_scaled = screen_1x
        factor = 1.0

    if show_esl_frame:
        out, (ox, oy) = wrap_esl_bezel(screen_scaled, th, bezel_scale=factor)
    else:
        out, (ox, oy) = screen_scaled.convert("RGBA"), (0, 0)

    scaled_hits = [
        HitRegion(
            x1=int(round(h.x1 * factor + ox)),
            y1=int(round(h.y1 * factor + oy)),
            x2=int(round(h.x2 * factor + ox)),
            y2=int(round(h.y2 * factor + oy)),
            action=h.action,
            payload=h.payload,
        )
        for h in raw_hits
    ]
    non_sys_hits = [h for h in scaled_hits if h.action not in ("toggle_temp_unit", "inspect_system")]
    cache = SystemPatchCache(
        clean_sys_hires=clean_sys_hires,
        display_img=out,
        screen_1x=screen_1x,
        fonts=f,
        theme=th,
        ss=ss,
        scale=float(scale),
        factor=float(factor),
        bezel_ox=int(ox),
        bezel_oy=int(oy),
        div_x=int(div_x),
        non_sys_hits=non_sys_hits,
    )
    return out, scaled_hits, screen_1x, th, cache


def patch_widget_system_stats(
    cache: SystemPatchCache,
    system_stats: SystemStats,
    temp_unit: str = "C",
    lang: str = "vi",
) -> tuple[Image.Image, list[HitRegion], Image.Image]:
    """Fast partial redraw of ONLY the SYSTEM (RAM/CPU/GPU) quadrant (~3-5ms vs ~100ms full card)."""
    sys_x2 = cache.div_x - 4
    lx = 10
    lw = cache.div_x - lx - 10
    patch_hires = cache.clean_sys_hires.copy()
    draw = _ScaledDraw(ImageDraw.Draw(patch_hires), scale=float(cache.ss), ox=float(SYS_BOX_X1), oy=float(SYS_BOX_Y1))
    sys_hits: list[HitRegion] = []
    _draw_system_section(draw, cache.fonts, cache.theme, lx, lw, system_stats, temp_unit, lang, sys_hits)

    pw_1x = sys_x2 - SYS_BOX_X1
    ph_1x = SYS_BOX_Y2 - SYS_BOX_Y1
    patch_1x = patch_hires.resize((pw_1x, ph_1x), Image.Resampling.LANCZOS)
    cache.screen_1x.paste(patch_1x.convert("RGB"), (SYS_BOX_X1, SYS_BOX_Y1))

    dx1 = int(round(SYS_BOX_X1 * cache.factor + cache.bezel_ox))
    dy1 = int(round(SYS_BOX_Y1 * cache.factor + cache.bezel_oy))
    dx2 = int(round(sys_x2 * cache.factor + cache.bezel_ox))
    dy2 = int(round(SYS_BOX_Y2 * cache.factor + cache.bezel_oy))
    pw_d, ph_d = max(1, dx2 - dx1), max(1, dy2 - dy1)
    patch_scaled = patch_1x if (pw_d == pw_1x and ph_d == ph_1x) else patch_hires.resize((pw_d, ph_d), Image.Resampling.LANCZOS)
    cache.display_img.paste(patch_scaled.convert("RGBA"), (dx1, dy1))

    scaled_sys_hits = [
        HitRegion(
            x1=int(round(h.x1 * cache.factor + cache.bezel_ox)),
            y1=int(round(h.y1 * cache.factor + cache.bezel_oy)),
            x2=int(round(h.x2 * cache.factor + cache.bezel_ox)),
            y2=int(round(h.y2 * cache.factor + cache.bezel_oy)),
            action=h.action,
            payload=h.payload,
        )
        for h in sys_hits
    ]
    return cache.display_img, [*cache.non_sys_hits, *scaled_sys_hits], cache.screen_1x


def render_widget_with_hits(
    calendar_data: CalendarSummary,
    weather_data: WeatherData,
    system_stats: SystemStats,
    owner_name: str = "Desk Widget",
    owner_align: str = "center",
    theme_mode: str = "auto",
    style: str = "serif",
    temp_unit: str = "C",
    lang: str = "vi",
    logo_path: str | None = None,
    bg_path: str | None = None,
    show_esl_frame: bool = False,
    scale: float = 1.0,
    now: datetime | None = None,
    view_year: int | None = None,
    view_month: int | None = None,
    selected_date: date | None = None,
    selected_weather_date: date | None = None,
    logo_pos: str = "before_title",
    bg_pos: str = "cover",
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
    bg_opacity: float | None = None,
) -> tuple[Image.Image, list[HitRegion], Image.Image, ThemePalette]:
    out, hits, screen_1x, th, _ = render_widget_cached(
        calendar_data,
        weather_data,
        system_stats,
        owner_name=owner_name,
        owner_align=owner_align,
        theme_mode=theme_mode,
        style=style,
        temp_unit=temp_unit,
        lang=lang,
        logo_path=logo_path,
        bg_path=bg_path,
        show_esl_frame=show_esl_frame,
        scale=scale,
        now=now,
        view_year=view_year,
        view_month=view_month,
        selected_date=selected_date,
        selected_weather_date=selected_weather_date,
        logo_pos=logo_pos,
        bg_pos=bg_pos,
        bg_tone=bg_tone,
        bg_zoom=bg_zoom,
        bg_offset_x=bg_offset_x,
        bg_offset_y=bg_offset_y,
        bg_opacity=bg_opacity,
    )
    return out, hits, screen_1x, th


def render_widget_image(
    calendar_data: CalendarSummary,
    weather_data: WeatherData,
    system_stats: SystemStats,
    owner_name: str = "Desk Widget",
    owner_align: str = "center",
    theme_mode: str = "auto",
    style: str = "serif",
    temp_unit: str = "C",
    lang: str = "vi",
    logo_path: str | None = None,
    bg_path: str | None = None,
    show_esl_frame: bool = False,
    scale: float = 1.0,
    now: datetime | None = None,
    view_year: int | None = None,
    view_month: int | None = None,
    selected_date: date | None = None,
    selected_weather_date: date | None = None,
    logo_pos: str = "before_title",
    bg_pos: str = "cover",
    bg_tone: str = "original",
    bg_zoom: float = 1.0,
    bg_offset_x: float = 0.0,
    bg_offset_y: float = 0.0,
    bg_opacity: float | None = None,
) -> Image.Image:
    out, _, _, _ = render_widget_with_hits(
        calendar_data,
        weather_data,
        system_stats,
        owner_name=owner_name,
        owner_align=owner_align,
        theme_mode=theme_mode,
        style=style,
        temp_unit=temp_unit,
        lang=lang,
        logo_path=logo_path,
        bg_path=bg_path,
        show_esl_frame=show_esl_frame,
        scale=scale,
        now=now,
        view_year=view_year,
        view_month=view_month,
        selected_date=selected_date,
        selected_weather_date=selected_weather_date,
        logo_pos=logo_pos,
        bg_pos=bg_pos,
        bg_tone=bg_tone,
        bg_zoom=bg_zoom,
        bg_offset_x=bg_offset_x,
        bg_offset_y=bg_offset_y,
        bg_opacity=bg_opacity,
    )
    return out


def export_esl_bitmap(screen_img: Image.Image, path: str, target_size: tuple[int, int] = (296, 128)) -> None:
    resized = screen_img.convert("RGB").resize(target_size, Image.Resampling.LANCZOS)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette([255, 255, 255, 0, 0, 0, 200, 30, 25] + [0] * (256 - 3) * 3)
    quantized = resized.quantize(palette=pal_img, dither=Image.Dither.FLOYDSTEINBERG)
    quantized.save(path)
