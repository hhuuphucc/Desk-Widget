"""Modern Material-inspired UI helpers for Tkinter dialogs (Windows & macOS)."""

from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass
from datetime import date, timedelta
import sys
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk

BG_SHELL = "#F0F4F9"
BG_CARD = "#FFFFFF"
BG_FIELD = "#E9EEF6"
BG_FIELD_HOVER = "#DCE4F0"
BORDER_SUBTLE = "#DCE2EC"
ACCENT = "#0B57D0"
ACCENT_HOVER = "#0842A0"
TONAL_BG = "#C2E7FF"
TONAL_HOVER = "#A8DAFA"
TONAL_FG = "#001D35"
DANGER_BG = "#FCE8E6"
DANGER_HOVER = "#F8D2CE"
DANGER_FG = "#B3261E"
INK = "#1F1F1F"
MUTED = "#444746"
SUBTLE = "#747775"


@dataclass(frozen=True)
class DialogPalette:
    style: str
    is_dark: bool
    shell: str
    card: str
    field: str
    field_hover: str
    border: str
    divider: str
    accent: str
    accent_hover: str
    accent_fg: str
    tonal_bg: str
    tonal_hover: str
    tonal_fg: str
    danger_bg: str
    danger_hover: str
    danger_fg: str
    ink: str
    muted: str
    subtle: str
    check_shape: str  # "rounded" | "circle"
    check_radius: int
    card_radius: int


_DIALOG_THEMES: dict[tuple[str, bool], DialogPalette] = {
    ("pixel", False): DialogPalette(
        style="pixel", is_dark=False, shell="#F3EEF9", card="#FFFFFF", field="#ECE4F6", field_hover="#DFD3F0",
        border="#D8CCE8", divider="#EAE3F3", accent="#6750A4", accent_hover="#4F378B", accent_fg="#FFFFFF",
        tonal_bg="#EADDFF", tonal_hover="#D8C2FF", tonal_fg="#21005D",
        danger_bg="#FCE8E6", danger_hover="#F8D2CE", danger_fg="#B3261E",
        ink="#1D1B20", muted="#49454F", subtle="#79747E", check_shape="rounded", check_radius=6, card_radius=16,
    ),
    ("pixel", True): DialogPalette(
        style="pixel", is_dark=True, shell="#141218", card="#211F26", field="#2B2930", field_hover="#36343B",
        border="#3B3842", divider="#2E2B35", accent="#8C6DE8", accent_hover="#A085F5", accent_fg="#FFFFFF",
        tonal_bg="#4F378B", tonal_hover="#6348A8", tonal_fg="#EADDFF",
        danger_bg="#4D1E1B", danger_hover="#632622", danger_fg="#F2B8B5",
        ink="#E6E0E9", muted="#CAC4D0", subtle="#938F99", check_shape="rounded", check_radius=6, card_radius=16,
    ),
    ("macos", False): DialogPalette(
        style="macos", is_dark=False, shell="#ECEFF4", card="#FFFFFF", field="#E5E9F0", field_hover="#D8DFE9",
        border="#CDD5E0", divider="#E2E7EE", accent="#007AFF", accent_hover="#0062CC", accent_fg="#FFFFFF",
        tonal_bg="#DCEEFF", tonal_hover="#C6E2FF", tonal_fg="#004080",
        danger_bg="#FFE5E5", danger_hover="#FFD1D1", danger_fg="#FF3B30",
        ink="#1D1D1F", muted="#515154", subtle="#86868B", check_shape="rounded", check_radius=5, card_radius=11,
    ),
    ("macos", True): DialogPalette(
        style="macos", is_dark=True, shell="#1C1C1E", card="#2C2C2E", field="#3A3A3C", field_hover="#48484A",
        border="#424245", divider="#38383A", accent="#0A84FF", accent_hover="#3399FF", accent_fg="#FFFFFF",
        tonal_bg="#143D66", tonal_hover="#1D4E80", tonal_fg="#BFE0FF",
        danger_bg="#4D1C1E", danger_hover="#662427", danger_fg="#FF453A",
        ink="#F5F5F7", muted="#AEAEB2", subtle="#8E8E93", check_shape="rounded", check_radius=5, card_radius=11,
    ),
    ("xiaomi", False): DialogPalette(
        style="xiaomi", is_dark=False, shell="#F4F5F7", card="#FFFFFF", field="#FFF1E6", field_hover="#FFE2CC",
        border="#E2E5EB", divider="#ECEEF2", accent="#FF6900", accent_hover="#E05500", accent_fg="#FFFFFF",
        tonal_bg="#FFE8D6", tonal_hover="#FFD4B3", tonal_fg="#8C3400",
        danger_bg="#FFF0ED", danger_hover="#FFDAD3", danger_fg="#E63B1E",
        ink="#191C22", muted="#505662", subtle="#868D9B", check_shape="circle", check_radius=9, card_radius=14,
    ),
    ("xiaomi", True): DialogPalette(
        style="xiaomi", is_dark=True, shell="#0A0C10", card="#161920", field="#202530", field_hover="#2A303E",
        border="#2B3242", divider="#232834", accent="#FF6900", accent_hover="#FF8533", accent_fg="#FFFFFF",
        tonal_bg="#4A240A", tonal_hover="#66320F", tonal_fg="#FFD4B3",
        danger_bg="#4A1E18", danger_hover="#612820", danger_fg="#FF7A59",
        ink="#F4F6FA", muted="#A5AEBF", subtle="#778091", check_shape="circle", check_radius=9, card_radius=14,
    ),
    ("serif", False): DialogPalette(
        style="serif", is_dark=False, shell="#EFEFE9", card="#F7F7F5", field="#E6E9ED", field_hover="#DCE1E8",
        border="#CFD5DC", divider="#DCE1E6", accent="#4E657A", accent_hover="#384C5E", accent_fg="#FFFFFF",
        tonal_bg="#DCE4EC", tonal_hover="#C9D6E2", tonal_fg="#22364A",
        danger_bg="#F5E5DF", danger_hover="#EDD3C9", danger_fg="#9E4826",
        ink="#181B20", muted="#4C5560", subtle="#7E8894", check_shape="rounded", check_radius=4, card_radius=8,
    ),
    ("serif", True): DialogPalette(
        style="serif", is_dark=True, shell="#1E2125", card="#15171A", field="#23272D", field_hover="#2C323A",
        border="#343940", divider="#2A2F36", accent="#5A7E9E", accent_hover="#6D93B5", accent_fg="#FFFFFF",
        tonal_bg="#2A3846", tonal_hover="#354657", tonal_fg="#DCE7F3",
        danger_bg="#472824", danger_hover="#5C342F", danger_fg="#E5988B",
        ink="#ECEFF4", muted="#A8B2BE", subtle="#747D88", check_shape="rounded", check_radius=4, card_radius=8,
    ),
    ("botanical", False): DialogPalette(
        style="botanical", is_dark=False, shell="#EDF3F7", card="#F6FAFC", field="#E1ECF2", field_hover="#D2E2EC",
        border="#C2D4E0", divider="#D2E0E9", accent="#2B6E90", accent_hover="#205672", accent_fg="#FFFFFF",
        tonal_bg="#D8EAF4", tonal_hover="#C5DFEE", tonal_fg="#164259",
        danger_bg="#F5E5DF", danger_hover="#EDD3C9", danger_fg="#9E4826",
        ink="#18242C", muted="#496170", subtle="#7A909E", check_shape="rounded", check_radius=5, card_radius=10,
    ),
    ("botanical", True): DialogPalette(
        style="botanical", is_dark=True, shell="#141D24", card="#0F171D", field="#1C2832", field_hover="#253542",
        border="#2C3D4B", divider="#23313D", accent="#347EA3", accent_hover="#4190B8", accent_fg="#FFFFFF",
        tonal_bg="#1D3748", tonal_hover="#27485D", tonal_fg="#CFE7F5",
        danger_bg="#472824", danger_hover="#5C342F", danger_fg="#E5988B",
        ink="#E8F1F6", muted="#9FB4C2", subtle="#657B8A", check_shape="rounded", check_radius=5, card_radius=10,
    ),
    ("sans", False): DialogPalette(
        style="sans", is_dark=False, shell="#E6E6E2", card="#F5F5F2", field="#DCDCD6", field_hover="#CECEC6",
        border="#B2B2AC", divider="#C8C8C2", accent="#BD261E", accent_hover="#991B15", accent_fg="#FFFFFF",
        tonal_bg="#ECC2BD", tonal_hover="#E3ABA4", tonal_fg="#66110C",
        danger_bg="#ECC2BD", danger_hover="#E3ABA4", danger_fg="#8C1913",
        ink="#181818", muted="#555552", subtle="#7B7B75", check_shape="rounded", check_radius=3, card_radius=6,
    ),
    ("sans", True): DialogPalette(
        style="sans", is_dark=True, shell="#1D1E1C", card="#282926", field="#343632", field_hover="#41443E",
        border="#454742", divider="#3E403B", accent="#C93B32", accent_hover="#DE4D44", accent_fg="#FFFFFF",
        tonal_bg="#592622", tonal_hover="#70312C", tonal_fg="#FFD6D2",
        danger_bg="#592622", danger_hover="#70312C", danger_fg="#FFABA5",
        ink="#ECECE7", muted="#A2A29B", subtle="#767870", check_shape="rounded", check_radius=3, card_radius=6,
    ),
}


def get_dialog_theme(style: str = "pixel", is_dark: bool = False) -> DialogPalette:
    """Return harmonized light/dark dialog palette matching the active widget style."""
    st = (style or "pixel").strip().lower()
    if st in ("esl",):
        st = "sans"
    elif st not in ("macos", "pixel", "xiaomi", "botanical", "serif", "sans"):
        st = "pixel"
    return _DIALOG_THEMES[(st, bool(is_dark))]

_STYLED_ROOTS: set[int] = set()


def apply_modern_ttk_style(win: tk.Misc, palette: DialogPalette | None = None) -> None:
    """Configure clean flat ttk styles for Combobox, Scrollbar & Treeview matching `palette`."""
    p = palette or get_dialog_theme("pixel", False)
    root = win.winfo_toplevel()
    rid = id(root)
    style = ttk.Style(root)
    if rid not in _STYLED_ROOTS:
        try:
            if style.theme_use() != "clam":
                style.theme_use("clam")
        except Exception:
            pass
        _STYLED_ROOTS.add(rid)

    disabled_bg = "#2A303B" if p.is_dark else "#F1F3F4"
    disabled_fg = "#6D7480" if p.is_dark else "#9AA0A6"
    style.configure(
        "Modern.TCombobox",
        fieldbackground=p.field,
        background=p.field,
        foreground=p.ink,
        arrowcolor=p.muted,
        borderwidth=0,
        relief="flat",
        arrowsize=13,
        padding=(8, 6),
    )
    style.map(
        "Modern.TCombobox",
        fieldbackground=[("readonly", p.field), ("disabled", disabled_bg)],
        foreground=[("readonly", p.ink), ("disabled", disabled_fg)],
        background=[("active", p.field_hover)],
    )
    style.configure(
        "Modern.Treeview",
        background=p.card,
        fieldbackground=p.card,
        foreground=p.ink,
        rowheight=32,
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 9),
    )
    style.configure(
        "Modern.Treeview.Heading",
        background=p.field,
        foreground=p.muted,
        borderwidth=0,
        relief="flat",
        font=("Segoe UI", 9, "bold"),
        padding=(8, 6),
    )
    style.map(
        "Modern.Treeview",
        background=[("selected", p.tonal_bg)],
        foreground=[("selected", p.tonal_fg)],
    )


def make_rounded_rect_photo(
    master: tk.Misc,
    width: int,
    height: int,
    radius: int,
    fill: str,
    outline: str | None = None,
    outline_width: int = 1,
    scale: int = 2,
) -> ImageTk.PhotoImage:
    """Render an anti-aliased rounded rectangle image via 2x Pillow supersampling."""
    w = max(4, int(width))
    h = max(4, int(height))
    sw, sh = w * scale, h * scale
    sr = max(2, min(int(radius * scale), min(sw, sh) // 2))
    im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    if outline:
        draw.rounded_rectangle(
            (0, 0, sw - 1, sh - 1),
            radius=sr,
            fill=fill,
            outline=outline,
            width=max(1, outline_width * scale),
        )
    else:
        draw.rounded_rectangle((0, 0, sw - 1, sh - 1), radius=sr, fill=fill)
    im = im.resize((w, h), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(im, master=master)


def _fit_control_height(parent: tk.Misc, min_height: int, font: tuple, pad_y: int = 10) -> int:
    """Return a DPI-safe pixel height guaranteed to fit font linespace without clipping."""
    try:
        f_obj = tkfont.Font(root=parent.winfo_toplevel(), font=font)
        line_h = int(f_obj.metrics("linespace"))
        return max(int(min_height), line_h + int(pad_y))
    except Exception:
        return int(min_height)


def make_pill_button(
    parent: tk.Misc,
    text: str,
    command,
    bg: str = ACCENT,
    fg: str = "#FFFFFF",
    hover_bg: str = ACCENT_HOVER,
    parent_bg: str = BG_SHELL,
    pad_x: int = 18,
    height: int = 34,
    radius: int | None = None,
    font: tuple = ("Segoe UI", 10, "bold"),
) -> tk.Label:
    """Create a crisp anti-aliased pill/rounded button with hover highlight."""
    eff_h = _fit_control_height(parent, height, font, pad_y=10)
    f_obj = tkfont.Font(root=parent.winfo_toplevel(), font=font)
    w = max(eff_h, f_obj.measure(text) + pad_x * 2)
    r = (eff_h // 2) if radius is None else radius
    img_idle = make_rounded_rect_photo(parent, w, eff_h, r, bg)
    img_hover = make_rounded_rect_photo(parent, w, eff_h, r, hover_bg)
    lbl = tk.Label(
        parent,
        text=text,
        image=img_idle,
        compound="center",
        fg=fg,
        bg=parent_bg,
        font=font,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    lbl._pill_refs = (img_idle, img_hover)  # type: ignore[attr-defined]
    lbl._enabled = True  # type: ignore[attr-defined]

    def _retheme_pill(old_p: DialogPalette, new_p: DialogPalette, cmap: dict[str, str]) -> None:
        bg_l = str(bg).lower()
        if bg_l == old_p.accent.lower():
            nb, nh, nf = new_p.accent, new_p.accent_hover, new_p.accent_fg
        elif bg_l == old_p.tonal_bg.lower():
            nb, nh, nf = new_p.tonal_bg, new_p.tonal_hover, new_p.tonal_fg
        elif bg_l == old_p.danger_bg.lower():
            nb, nh, nf = new_p.danger_bg, new_p.danger_hover, new_p.danger_fg
        elif bg_l == old_p.field.lower():
            nb, nh, nf = new_p.field, new_p.field_hover, new_p.ink
        else:
            nb = cmap.get(bg_l, bg)
            nh = cmap.get(str(hover_bg).lower(), hover_bg)
            nf = cmap.get(str(fg).lower(), fg)
        npbg = cmap.get(str(parent_bg).lower(), parent_bg)
        ni = make_rounded_rect_photo(parent, w, eff_h, r, nb)
        nhov = make_rounded_rect_photo(parent, w, eff_h, r, nh)
        lbl._pill_refs = (ni, nhov)  # type: ignore[attr-defined]
        lbl.configure(image=ni, fg=nf, bg=npbg)

    lbl._retheme_fn = _retheme_pill  # type: ignore[attr-defined]

    def _on_enter(_e) -> None:
        if getattr(lbl, "_enabled", True):
            lbl.configure(image=lbl._pill_refs[1])  # type: ignore[attr-defined]

    def _on_leave(_e) -> None:
        lbl.configure(image=lbl._pill_refs[0])  # type: ignore[attr-defined]

    def _on_click(_e) -> None:
        if getattr(lbl, "_enabled", True) and command is not None:
            command()

    lbl.bind("<Enter>", _on_enter)
    lbl.bind("<Leave>", _on_leave)
    lbl.bind("<Button-1>", _on_click)
    return lbl


def _make_checkbox_photo(
    master: tk.Misc,
    checked: bool,
    disabled: bool,
    p: DialogPalette,
    size: int = 18,
    scale: int = 3,
) -> ImageTk.PhotoImage:
    """Render an anti-aliased 3x supersampled rounded or circular checkbox matching `DialogPalette`."""
    sw, sh = size * scale, size * scale
    im = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    r = (sw // 2) if p.check_shape == "circle" else max(3, int(p.check_radius * scale))
    pad = scale
    box = (pad, pad, sw - pad - 1, sh - pad - 1)
    if checked:
        fill_c = p.subtle if disabled else p.accent
        draw.rounded_rectangle(box, radius=r, fill=fill_c)
        # Crisp white checkmark
        pts = [
            (sw * 0.27, sh * 0.52),
            (sw * 0.43, sh * 0.68),
            (sw * 0.74, sh * 0.34),
        ]
        draw.line(pts, fill="#FFFFFF", width=max(2, int(round(2.1 * scale))), joint="curve")
    else:
        fill_c = p.field if not disabled else p.shell
        out_c = p.subtle if disabled else p.muted
        draw.rounded_rectangle(box, radius=r, fill=fill_c, outline=out_c, width=max(1, int(round(1.4 * scale))))
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(im, master=master)


class ModernCheckbox(tk.Frame):
    """Anti-aliased Pillow checkbox synced to DialogPalette, replacing boxy ttk.Checkbutton."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        variable: tk.BooleanVar,
        palette: DialogPalette | None = None,
        parent_bg: str | None = None,
        command=None,
        font: tuple = ("Segoe UI", 10),
    ) -> None:
        self._p = palette or get_dialog_theme("pixel", False)
        self._bg = parent_bg or self._p.card
        super().__init__(parent, bg=self._bg, bd=0, highlightthickness=0, cursor="hand2")
        self.var = variable
        self._command = command
        self._disabled = False

        self._imgs = {
            (False, False): _make_checkbox_photo(self, False, False, self._p),
            (True, False): _make_checkbox_photo(self, True, False, self._p),
            (False, True): _make_checkbox_photo(self, False, True, self._p),
            (True, True): _make_checkbox_photo(self, True, True, self._p),
        }
        self.icon_lbl = tk.Label(self, bg=self._bg, bd=0, highlightthickness=0, cursor="hand2")
        self.icon_lbl.pack(side="left")

        self.text_lbl = None
        if text:
            self.text_lbl = tk.Label(
                self,
                text=text,
                bg=self._bg,
                fg=self._p.ink,
                font=font,
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            )
            self.text_lbl.pack(side="left", padx=(6, 0))

        self._trace_id = self.var.trace_add("write", lambda *_a: self._sync())
        self.bind("<Destroy>", self._on_destroy, add="+")
        for w in ([self, self.icon_lbl] + ([self.text_lbl] if self.text_lbl else [])):
            w.bind("<Button-1>", self._toggle)
        self._sync()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self and self._trace_id:
            try:
                self.var.trace_remove("write", self._trace_id)
            except Exception:
                pass
            self._trace_id = ""

    def _sync(self) -> None:
        if not self.winfo_exists():
            return
        val = bool(self.var.get())
        self.icon_lbl.configure(image=self._imgs[(val, self._disabled)])
        if self.text_lbl is not None:
            self.text_lbl.configure(fg=self._p.subtle if self._disabled else self._p.ink)

    def _toggle(self, _e=None) -> None:
        if self._disabled:
            return
        self.var.set(not bool(self.var.get()))
        if self._command is not None:
            self._command()

    def _retheme_fn(self, old_p: DialogPalette, new_p: DialogPalette, cmap: dict[str, str]) -> None:
        self._p = new_p
        self._bg = cmap.get(self._bg.lower(), new_p.card)
        self._imgs = {
            (False, False): _make_checkbox_photo(self, False, False, new_p),
            (True, False): _make_checkbox_photo(self, True, False, new_p),
            (False, True): _make_checkbox_photo(self, False, True, new_p),
            (True, True): _make_checkbox_photo(self, True, True, new_p),
        }
        super().configure(bg=self._bg)
        self.icon_lbl.configure(bg=self._bg)
        if self.text_lbl is not None:
            self.text_lbl.configure(bg=self._bg)
        self._sync()

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        if "state" in kw:
            st = str(kw.pop("state")).lower()
            self._disabled = st == "disabled"
            cur = "arrow" if self._disabled else "hand2"
            super().configure(cursor=cur)
            self.icon_lbl.configure(cursor=cur)
            if self.text_lbl is not None:
                self.text_lbl.configure(cursor=cur)
            self._sync()
        if cnf or kw:
            return super().configure(cnf, **kw)
        return None

    config = configure


def make_modern_checkbox(
    parent: tk.Misc,
    text: str,
    variable: tk.BooleanVar,
    palette: DialogPalette | None = None,
    parent_bg: str | None = None,
    command=None,
    font: tuple = ("Segoe UI", 10),
) -> ModernCheckbox:
    return ModernCheckbox(parent, text=text, variable=variable, palette=palette, parent_bg=parent_bg, command=command, font=font)


class ModernDropdown(tk.Label):
    """Anti-aliased rounded pill dropdown replacing boxy ttk.Combobox & dark highlight strips."""

    def __init__(
        self,
        parent: tk.Misc,
        variable: tk.Variable,
        values: list[str],
        palette: DialogPalette | None = None,
        parent_bg: str | None = None,
        width_px: int = 160,
        height: int = 32,
        radius: int = 8,
        command=None,
        font: tuple = ("Segoe UI", 10),
        max_visible_items: int = 10,
        menu_width: int | None = None,
    ) -> None:
        self._p = palette or get_dialog_theme("pixel", False)
        self._pbg = parent_bg or self._p.card
        self._var = variable
        self._values = [str(v) for v in values]
        self._width_px = int(width_px)
        self._font = font
        self._height = _fit_control_height(parent, height, font, pad_y=10)
        self._radius = int(radius)
        self._command = command
        self._max_visible = max(4, int(max_visible_items))
        self._menu_width = int(menu_width) if menu_width is not None else None
        self._disabled = False
        self._pop: tk.Toplevel | None = None

        self._img_idle = make_rounded_rect_photo(parent, self._width_px, self._height, self._radius, self._p.field)
        self._img_hover = make_rounded_rect_photo(parent, self._width_px, self._height, self._radius, self._p.field_hover)
        super().__init__(
            parent,
            image=self._img_idle,
            bg=self._pbg,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.pack_propagate(False)
        super().configure(width=self._width_px, height=self._height)

        self._lbl_val = tk.Label(
            self,
            text=self._display_text(),
            bg=self._p.field,
            fg=self._p.ink,
            font=self._font,
            anchor="w",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._lbl_val.place(x=10, rely=0.5, anchor="w", width=max(24, self._width_px - 32))

        self._lbl_arrow = tk.Label(
            self,
            text="▾",
            bg=self._p.field,
            fg=self._p.muted,
            font=("Segoe UI", 9),
            anchor="e",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._lbl_arrow.place(x=max(24, self._width_px - 22), rely=0.5, anchor="w", width=14)

        self._trace_id = self._var.trace_add("write", lambda *_a: self._sync_text())
        self.bind("<Destroy>", self._on_destroy, add="+")
        for w in (self, self._lbl_val, self._lbl_arrow):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._open_menu)

    def _display_text(self) -> str:
        try:
            v = self._var.get()
            if isinstance(self._var, tk.DoubleVar):
                fv = float(v)
                for cand in self._values:
                    try:
                        if abs(float(cand) - fv) < 1e-9:
                            return cand
                    except Exception:
                        pass
                return f"{fv:g}"
            return str(v)
        except Exception:
            return ""

    def _sync_text(self) -> None:
        if not self.winfo_exists():
            return
        self._lbl_val.configure(text=self._display_text())

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            if self._trace_id:
                try:
                    self._var.trace_remove("write", self._trace_id)
                except Exception:
                    pass
                self._trace_id = ""
            if self._pop is not None and self._pop.winfo_exists():
                try:
                    self._pop.destroy()
                except Exception:
                    pass

    def _on_enter(self, _e=None) -> None:
        if self._disabled:
            return
        super().configure(image=self._img_hover)
        self._lbl_val.configure(bg=self._p.field_hover)
        self._lbl_arrow.configure(bg=self._p.field_hover)

    def _on_leave(self, _e=None) -> None:
        super().configure(image=self._img_idle)
        self._lbl_val.configure(bg=self._p.field)
        self._lbl_arrow.configure(bg=self._p.field)

    def set_values(self, new_values: list[str]) -> None:
        self._values = [str(v) for v in new_values]

    def _retheme_fn(self, old_p: DialogPalette, new_p: DialogPalette, cmap: dict[str, str]) -> None:
        self._p = new_p
        self._pbg = cmap.get(self._pbg.lower(), new_p.card)
        self._img_idle = make_rounded_rect_photo(self.master, self._width_px, self._height, self._radius, new_p.field)
        self._img_hover = make_rounded_rect_photo(self.master, self._width_px, self._height, self._radius, new_p.field_hover)
        super().configure(image=self._img_idle, bg=self._pbg)
        self._lbl_val.configure(bg=new_p.field, fg=new_p.subtle if self._disabled else new_p.ink)
        self._lbl_arrow.configure(bg=new_p.field, fg=new_p.subtle if self._disabled else new_p.muted)

    def configure(self, cnf=None, **kw):  # type: ignore[override]
        if "values" in kw:
            self.set_values(list(kw.pop("values") or []))
        if "state" in kw:
            st = str(kw.pop("state")).lower()
            self._disabled = st == "disabled"
            cur = "arrow" if self._disabled else "hand2"
            fg_v = self._p.subtle if self._disabled else self._p.ink
            fg_a = self._p.subtle if self._disabled else self._p.muted
            super().configure(cursor=cur)
            self._lbl_val.configure(fg=fg_v, cursor=cur)
            self._lbl_arrow.configure(fg=fg_a, cursor=cur)
            if self._disabled:
                self._on_leave()
        if cnf or kw:
            return super().configure(cnf, **kw)
        return None

    config = configure

    def _select(self, opt: str) -> None:
        if self._pop is not None and self._pop.winfo_exists():
            try:
                self._pop.destroy()
            except Exception:
                pass
            self._pop = None
        if isinstance(self._var, tk.DoubleVar):
            try:
                self._var.set(float(opt))
            except ValueError:
                pass
        else:
            self._var.set(opt)
        self._sync_text()
        try:
            self.event_generate("<<ComboboxSelected>>")
        except Exception:
            pass
        if self._command is not None:
            self._command(opt)

    def _open_menu(self, _e=None) -> None:
        if self._disabled or not self._values:
            return
        if self._pop is not None and self._pop.winfo_exists():
            self._pop.destroy()
            self._pop = None
            return

        pop = tk.Toplevel(self.winfo_toplevel())
        pop.withdraw()
        pop.overrideredirect(True)
        pop.configure(bg=self._p.border, padx=1, pady=1)
        self._pop = pop

        box = tk.Frame(pop, bg=self._p.card, pady=4)
        box.pack(fill="both", expand=True)

        cur_txt = self._display_text()
        use_scroll = len(self._values) > self._max_visible
        sel_idx = 0

        def _populate_items(holder: tk.Misc, scroll_fn=None) -> list[tk.Label]:
            nonlocal sel_idx
            items: list[tk.Label] = []
            for idx, opt in enumerate(self._values):
                is_sel = opt == cur_txt
                if is_sel:
                    sel_idx = idx
                rbg = self._p.tonal_bg if is_sel else self._p.card
                rfg = self._p.tonal_fg if is_sel else self._p.ink
                prefix = "✓ " if is_sel else "   "
                item = tk.Label(
                    holder,
                    text=f"{prefix}{opt}",
                    font=("Segoe UI", 10, "bold" if is_sel else "normal"),
                    bg=rbg,
                    fg=rfg,
                    anchor="w",
                    padx=10,
                    pady=5,
                    cursor="hand2",
                )
                item.pack(fill="x")
                if not is_sel:
                    item.bind("<Enter>", lambda _ev, l=item: l.configure(bg=self._p.field))
                    item.bind("<Leave>", lambda _ev, l=item: l.configure(bg=self._p.card))
                item.bind("<Button-1>", lambda _ev, v=opt: self._select(v))
                if scroll_fn is not None:
                    item.bind("<MouseWheel>", scroll_fn)
                items.append(item)
            return items

        if use_scroll:
            row_h = 30
            vis_h = self._max_visible * row_h
            cv = tk.Canvas(box, bg=self._p.card, highlightthickness=0, bd=0, height=vis_h)
            sb = ttk.Scrollbar(box, orient="vertical", command=cv.yview)
            cv.configure(yscrollcommand=sb.set)
            cv.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y", padx=(0, 2))
            inner = tk.Frame(cv, bg=self._p.card)
            win_id = cv.create_window((0, 0), window=inner, anchor="nw")

            def _on_wheel(ev: tk.Event) -> None:
                units = mousewheel_units(int(getattr(ev, "delta", 0) or 0))
                if units:
                    cv.yview_scroll(units, "units")

            inner.bind("<Configure>", lambda _e: cv.configure(scrollregion=cv.bbox("all")))
            cv.bind("<Configure>", lambda e: cv.itemconfigure(win_id, width=e.width))
            cv.bind("<MouseWheel>", _on_wheel)
            inner.bind("<MouseWheel>", _on_wheel)
            _populate_items(inner, scroll_fn=_on_wheel)
            pop.update_idletasks()
            content_w = max(self._menu_width or self._width_px, inner.winfo_reqwidth() + 24)
            cv.configure(width=content_w - 18, height=vis_h)
            if sel_idx > 2 and len(self._values) > self._max_visible:
                cv.yview_moveto(max(0.0, (sel_idx - 2) / max(1, len(self._values))))
        else:
            _populate_items(box)

        pop.update_idletasks()
        ax = self.winfo_rootx()
        ay = self.winfo_rooty() + self.winfo_height() + 4
        req_w = max(self._menu_width or self._width_px, pop.winfo_reqwidth())
        req_h = pop.winfo_reqheight()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ax = max(8, min(ax, sw - req_w - 8))
        if ay + req_h > sh - 40:
            ay = max(8, self.winfo_rooty() - req_h - 4)
        pop.geometry(f"{req_w}x{req_h}+{ax}+{ay}")
        pop.deiconify()
        pop.lift()
        pop.focus_force()
        pop.bind(
            "<FocusOut>",
            lambda _ev: pop.after(60, lambda: pop.destroy() if pop.winfo_exists() and pop.focus_displayof() is None else None),
        )
        pop.bind("<Escape>", lambda _ev: pop.destroy())


def make_pill_dropdown(
    parent: tk.Misc,
    variable: tk.Variable,
    values: list[str],
    palette: DialogPalette | None = None,
    parent_bg: str | None = None,
    width_px: int = 160,
    height: int = 32,
    radius: int = 8,
    command=None,
    font: tuple = ("Segoe UI", 10),
    max_visible_items: int = 10,
    menu_width: int | None = None,
) -> ModernDropdown:
    return ModernDropdown(
        parent,
        variable=variable,
        values=values,
        palette=palette,
        parent_bg=parent_bg,
        width_px=width_px,
        height=height,
        radius=radius,
        command=command,
        font=font,
        max_visible_items=max_visible_items,
        menu_width=menu_width,
    )


def make_rounded_entry(
    parent: tk.Misc,
    textvariable: tk.StringVar,
    width_px: int = 240,
    height: int = 34,
    radius: int = 8,
    fill: str = BG_FIELD,
    parent_bg: str = BG_CARD,
    fg: str = INK,
    font: tuple = ("Segoe UI", 10),
    placeholder: str = "",
    insert_bg: str = ACCENT,
    ph_fg: str = SUBTLE,
    disabled_fg: str = "#9AA0A6",
) -> tuple[tk.Label, tk.Entry]:
    """Create a soft rounded Material-style input field wrapping a borderless tk.Entry."""
    eff_h = _fit_control_height(parent, height, font, pad_y=10)
    bg_img = make_rounded_rect_photo(parent, width_px, eff_h, radius, fill)
    shell = tk.Label(parent, image=bg_img, bg=parent_bg, bd=0, highlightthickness=0)
    shell._pill_refs = (bg_img,)  # type: ignore[attr-defined]
    shell.pack_propagate(False)
    shell.configure(width=width_px, height=eff_h)

    ent = tk.Entry(
        shell,
        textvariable=textvariable,
        bg=fill,
        fg=fg,
        disabledbackground=fill,
        disabledforeground=disabled_fg,
        insertbackground=insert_bg,
        font=font,
        bd=0,
        relief="flat",
        highlightthickness=0,
    )
    ent.place(x=10, rely=0.5, anchor="w", width=max(20, width_px - 20))

    def _retheme_entry(old_p: DialogPalette, new_p: DialogPalette, cmap: dict[str, str]) -> None:
        nf = cmap.get(str(fill).lower(), new_p.field)
        npbg = cmap.get(str(parent_bg).lower(), new_p.card)
        nfg = cmap.get(str(fg).lower(), new_p.ink)
        ndfg = cmap.get(str(disabled_fg).lower(), new_p.subtle)
        ni = make_rounded_rect_photo(parent, width_px, eff_h, radius, nf)
        shell._pill_refs = (ni,)  # type: ignore[attr-defined]
        shell.configure(image=ni, bg=npbg)
        ent.configure(
            bg=nf,
            disabledbackground=nf,
            disabledforeground=ndfg,
            insertbackground=new_p.accent,
        )
        if not getattr(ent, "_ph_active", False):
            ent.configure(fg=nfg)
        else:
            ent.configure(fg=new_p.subtle)

    shell._retheme_fn = _retheme_entry  # type: ignore[attr-defined]
    if placeholder:
        attach_placeholder(ent, textvariable, placeholder, fg=fg, ph_fg=ph_fg)
    return shell, ent


def make_rounded_card(
    parent: tk.Misc,
    width_px: int,
    height_px: int,
    radius: int = 16,
    fill: str = BG_CARD,
    outline: str | None = BORDER_SUBTLE,
    parent_bg: str = BG_SHELL,
) -> tuple[tk.Label, tk.Frame]:
    """Create an anti-aliased rounded white card container."""
    card_img = make_rounded_rect_photo(parent, width_px, height_px, radius, fill, outline=outline)
    backdrop = tk.Label(parent, image=card_img, bg=parent_bg, bd=0, highlightthickness=0)
    backdrop._pill_refs = (card_img,)  # type: ignore[attr-defined]
    backdrop.configure(width=width_px, height=height_px)
    inner = tk.Frame(backdrop, bg=fill, bd=0, highlightthickness=0)
    inner.place(x=12, y=10, width=max(40, width_px - 24), height=max(40, height_px - 20))
    return backdrop, inner


def attach_placeholder(
    widget: tk.Entry,
    var: tk.StringVar,
    placeholder: str,
    fg: str = INK,
    ph_fg: str = SUBTLE,
) -> None:
    """Attach clean focus-aware placeholder behavior without polluting bound StringVar when empty."""
    widget._ph_active = False  # type: ignore[attr-defined]

    def _show_ph() -> None:
        if not var.get():
            widget._ph_active = True  # type: ignore[attr-defined]
            widget.delete(0, "end")
            widget.insert(0, placeholder)
            widget.configure(fg=ph_fg)

    def _clear_ph(_e=None) -> None:
        if getattr(widget, "_ph_active", False):
            widget._ph_active = False  # type: ignore[attr-defined]
            widget.delete(0, "end")
            widget.configure(fg=fg)

    def _on_focus_out(_e=None) -> None:
        if not widget.get().strip():
            var.set("")
            _show_ph()
        else:
            widget._ph_active = False  # type: ignore[attr-defined]
            widget.configure(fg=fg)

    widget.bind("<FocusIn>", _clear_ph, add="+")
    widget.bind("<FocusOut>", _on_focus_out, add="+")
    if not var.get():
        widget.after(10, _show_ph)


def read_entry_clean(entry: tk.Entry, var: tk.StringVar) -> str:
    """Return actual typed text, ignoring placeholder overlay."""
    if getattr(entry, "_ph_active", False):
        return ""
    return var.get().strip()


def format_pretty_date(d_obj: date, lang: str = "vi") -> str:
    if (lang or "vi").strip().lower() == "en":
        return f"{d_obj.strftime('%b')} {d_obj.day}, {d_obj.year}"
    return f"{d_obj.day} thg {d_obj.month}, {d_obj.year}"


def open_date_picker(
    parent: tk.Misc,
    anchor: tk.Misc,
    current_d: date,
    lang: str,
    on_pick,
    palette: DialogPalette | None = None,
) -> tk.Toplevel:
    """Open a clean Material-style floating mini calendar popover to pick any date."""
    p = palette or get_dialog_theme("pixel", False)
    is_en = (lang or "vi").strip().lower() == "en"
    pop = tk.Toplevel(parent)
    pop.withdraw()
    pop.overrideredirect(True)
    pop.configure(bg=p.border, padx=1, pady=1)

    card = tk.Frame(pop, bg=p.card, padx=10, pady=10)
    card.pack(fill="both", expand=True)

    state = {"year": current_d.year, "month": current_d.month}

    hdr = tk.Frame(card, bg=p.card)
    hdr.pack(fill="x", pady=(0, 6))
    lbl_mon = tk.Label(hdr, text="", font=("Segoe UI", 10, "bold"), fg=p.ink, bg=p.card)
    lbl_mon.pack(side="left", padx=4)

    grid_frame = tk.Frame(card, bg=p.card)
    grid_frame.pack()

    def _pick(picked_d: date) -> None:
        try:
            pop.destroy()
        except Exception:
            pass
        on_pick(picked_d)

    def _render() -> None:
        for ch in grid_frame.winfo_children():
            ch.destroy()
        y, m = state["year"], state["month"]
        lbl_mon.configure(text=f"{date(y, m, 1).strftime('%B %Y')}" if is_en else f"Tháng {m}, {y}")
        wds = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"] if is_en else ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
        for c, wd in enumerate(wds):
            tk.Label(grid_frame, text=wd, font=("Segoe UI", 8, "bold"), fg=p.subtle, bg=p.card, width=3).grid(row=0, column=c, pady=(0, 2))
        cal_rows = pycal.Calendar(firstweekday=0).monthdatescalendar(y, m)
        for r_idx, week in enumerate(cal_rows, start=1):
            for c_idx, day_d in enumerate(week):
                in_mon = day_d.month == m
                is_sel = day_d == current_d
                bg_c = p.accent if is_sel else p.card
                fg_c = p.accent_fg if is_sel else (p.ink if in_mon else p.subtle)
                btn = tk.Label(
                    grid_frame,
                    text=str(day_d.day),
                    font=("Segoe UI", 9, "bold" if is_sel else "normal"),
                    bg=bg_c,
                    fg=fg_c,
                    width=3,
                    pady=3,
                    cursor="hand2",
                )
                btn.grid(row=r_idx, column=c_idx, padx=1, pady=1)
                if not is_sel:
                    btn.bind("<Enter>", lambda _e, b=btn: b.configure(bg=p.field))
                    btn.bind("<Leave>", lambda _e, b=btn: b.configure(bg=p.card))
                btn.bind("<Button-1>", lambda _e, d=day_d: _pick(d))

    def _shift_month(delta: int) -> None:
        m = state["month"] + delta
        if m < 1:
            state["month"] = 12
            state["year"] -= 1
        elif m > 12:
            state["month"] = 1
            state["year"] += 1
        else:
            state["month"] = m
        _render()

    nav_r = tk.Label(hdr, text=" › ", font=("Segoe UI", 12, "bold"), fg=p.muted, bg=p.card, cursor="hand2")
    nav_r.pack(side="right")
    nav_r.bind("<Button-1>", lambda _e: _shift_month(1))
    nav_l = tk.Label(hdr, text=" ‹ ", font=("Segoe UI", 12, "bold"), fg=p.muted, bg=p.card, cursor="hand2")
    nav_l.pack(side="right")
    nav_l.bind("<Button-1>", lambda _e: _shift_month(-1))

    _render()
    pop.update_idletasks()
    ax = anchor.winfo_rootx()
    ay = anchor.winfo_rooty() + anchor.winfo_height() + 4
    sw, sh = parent.winfo_screenwidth(), parent.winfo_screenheight()
    pw, ph = pop.winfo_reqwidth(), pop.winfo_reqheight()
    ax = max(8, min(ax, sw - pw - 8))
    if ay + ph > sh - 40:
        ay = max(8, anchor.winfo_rooty() - ph - 4)
    pop.geometry(f"+{ax}+{ay}")
    pop.deiconify()
    pop.lift()
    pop.focus_force()
    pop.bind("<FocusOut>", lambda _e: pop.after(60, lambda: pop.destroy() if pop.winfo_exists() and pop.focus_displayof() is None else None))
    pop.bind("<Escape>", lambda _e: pop.destroy())
    return pop


def mousewheel_units(delta: int, platform: str | None = None) -> int:
    """Normalize Tk <MouseWheel> delta into scroll units for Windows, trackpads, and macOS."""
    if not delta:
        return 0
    plat = (platform or sys.platform).lower()
    if plat == "darwin":
        step = max(1, min(3, abs(int(delta))))
        return -step if delta > 0 else step
    if abs(delta) < 120:
        return -1 if delta > 0 else 1
    steps = int(round(-delta / 120.0))
    return steps if steps != 0 else (-1 if delta > 0 else 1)


def _make_circle_info_photo(
    master: tk.Misc,
    size: int,
    fill: str,
    outline: str,
    ink: str,
    scale: int = 2,
) -> ImageTk.PhotoImage:
    """Render an anti-aliased circular (i) icon button via 2x Pillow supersampling."""
    sz = max(16, int(size))
    ss = sz * scale
    im = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pad = max(1, scale)
    d.ellipse((pad, pad, ss - pad - 1, ss - pad - 1), fill=fill, outline=outline, width=max(1, int(round(1.2 * scale))))
    cx = ss / 2.0
    # Crisp lowercase 'i': dot + rounded vertical stem
    dot_r = max(1.5, sz * 0.068 * scale)
    dot_y = ss * 0.30
    d.ellipse((cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r), fill=ink)
    stem_w = max(2, int(round(sz * 0.105 * scale)))
    x1 = int(round(cx - stem_w / 2.0))
    x2 = x1 + stem_w
    y1 = int(round(ss * 0.43))
    y2 = int(round(ss * 0.74))
    d.rounded_rectangle((x1, y1, x2, y2), radius=max(1, stem_w // 2), fill=ink)
    im = im.resize((sz, sz), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(im, master=master)


def make_info_button(
    parent: tk.Misc,
    title: str,
    message: str,
    palette: DialogPalette | None = None,
    parent_bg: str | None = None,
    size: int = 24,
    ok_text: str = "Đã hiểu",
) -> tk.Label:
    """Create a circular (i) button that toggles a themed info popover on click."""
    p = palette or get_dialog_theme("pixel", False)
    pbg = parent_bg or p.card
    sz = max(18, int(size))

    img_idle = _make_circle_info_photo(parent, sz, fill=p.field, outline=p.subtle, ink=p.accent)
    img_hover = _make_circle_info_photo(parent, sz, fill=p.tonal_bg, outline=p.accent, ink=p.tonal_fg)

    btn = tk.Label(
        parent,
        image=img_idle,
        bg=pbg,
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    btn._imgs = (img_idle, img_hover)
    btn._pop = None
    btn._p = p  # type: ignore[attr-defined]
    btn._pbg = pbg  # type: ignore[attr-defined]

    def _retheme_info(old_p: DialogPalette, new_p: DialogPalette, cmap: dict[str, str]) -> None:
        btn._p = new_p  # type: ignore[attr-defined]
        btn._pbg = cmap.get(str(btn._pbg).lower(), new_p.card)  # type: ignore[attr-defined]
        ni = _make_circle_info_photo(parent, sz, fill=new_p.field, outline=new_p.subtle, ink=new_p.accent)
        nh = _make_circle_info_photo(parent, sz, fill=new_p.tonal_bg, outline=new_p.accent, ink=new_p.tonal_fg)
        btn._imgs = (ni, nh)
        btn.configure(image=ni, bg=btn._pbg)  # type: ignore[attr-defined]

    btn._retheme_fn = _retheme_info  # type: ignore[attr-defined]

    def _close_pop() -> None:
        pop = getattr(btn, "_pop", None)
        btn._pop = None
        if pop is not None:
            try:
                if pop.winfo_exists():
                    pop.destroy()
            except Exception:
                pass

    def _toggle(_ev=None) -> str:
        cur = getattr(btn, "_pop", None)
        if cur is not None:
            try:
                if cur.winfo_exists():
                    _close_pop()
                    return "break"
            except Exception:
                pass
        cp: DialogPalette = getattr(btn, "_p", p)
        top_owner = parent.winfo_toplevel()
        pop = tk.Toplevel(top_owner)
        pop.withdraw()
        pop.overrideredirect(True)
        pop.configure(bg=cp.accent)
        try:
            pop.attributes("-topmost", True)
        except Exception:
            pass
        btn._pop = pop

        body = tk.Frame(pop, bg=cp.card, padx=12, pady=10)
        body.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Label(
            body,
            text=title,
            bg=cp.card,
            fg=cp.accent,
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, 4))
        tk.Label(
            body,
            text=message,
            bg=cp.card,
            fg=cp.ink,
            font=("Segoe UI", 9),
            justify="left",
            wraplength=290,
            anchor="w",
        ).pack(fill="x", pady=(0, 8))

        foot = tk.Frame(body, bg=cp.card)
        foot.pack(fill="x")
        make_pill_button(
            foot,
            ok_text,
            _close_pop,
            bg=cp.tonal_bg,
            fg=cp.tonal_fg,
            hover_bg=cp.tonal_hover,
            parent_bg=cp.card,
            pad_x=10,
            height=24,
            radius=7,
            font=("Segoe UI", 8, "bold"),
        ).pack(side="right")

        pop.update_idletasks()
        ax = btn.winfo_rootx()
        ay = btn.winfo_rooty() + btn.winfo_height() + 5
        sw, sh = parent.winfo_screenwidth(), parent.winfo_screenheight()
        pw, ph = pop.winfo_reqwidth(), pop.winfo_reqheight()
        try:
            owner_r = top_owner.winfo_rootx() + top_owner.winfo_width()
            if owner_r > 0 and ax + pw > owner_r - 8:
                ax = ax - pw + sz
        except Exception:
            pass
        ax = max(8, min(ax, sw - pw - 8))
        if ay + ph > sh - 40:
            ay = max(8, btn.winfo_rooty() - ph - 5)
        pop.geometry(f"+{ax}+{ay}")
        pop.deiconify()
        pop.lift()
        pop.focus_force()
        pop.bind(
            "<FocusOut>",
            lambda _e=None: pop.after(70, lambda: _close_pop() if pop.winfo_exists() and pop.focus_displayof() is None else None),
        )
        pop.bind("<Escape>", lambda _e=None: _close_pop())
        return "break"

    btn.bind("<Enter>", lambda _e=None: btn.configure(image=btn._imgs[1]))
    btn.bind("<Leave>", lambda _e=None: btn.configure(image=btn._imgs[0]))
    btn.bind("<Button-1>", _toggle)
    btn.bind("<Destroy>", lambda _e=None: _close_pop(), add="+")
    return btn


def retheme_dialog_tree(root_win: tk.Misc, old_p: DialogPalette, new_p: DialogPalette) -> None:
    """Recursively update dialog widget colors and modern_ui controls in-place without closing the window."""
    fields = (
        "shell", "card", "field", "field_hover", "border", "divider",
        "accent", "accent_hover", "accent_fg",
        "tonal_bg", "tonal_hover", "tonal_fg",
        "danger_bg", "danger_hover", "danger_fg",
        "ink", "muted", "subtle",
    )
    cmap = {str(getattr(old_p, k)).lower(): str(getattr(new_p, k)) for k in fields}
    if isinstance(root_win, (tk.Tk, tk.Toplevel)):
        apply_modern_ttk_style(root_win, new_p)

    def _walk(w: tk.Misc) -> None:
        if getattr(w, "_skip_retheme", False):
            return
        fn = getattr(w, "_retheme_fn", None)
        if callable(fn):
            try:
                fn(old_p, new_p, cmap)
            except Exception:
                pass
            return
        for opt in ("bg", "fg", "highlightbackground", "insertbackground", "selectbackground", "selectforeground"):
            try:
                cur_v = str(w.cget(opt)).lower()
                if cur_v in cmap:
                    w.configure(**{opt: cmap[cur_v]})
            except Exception:
                pass
        for ch in w.winfo_children():
            _walk(ch)

    _walk(root_win)
