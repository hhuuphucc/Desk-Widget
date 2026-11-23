"""Cross-platform PyInstaller build script for desk-widget (Windows .exe & macOS .app/.dmg)."""

from __future__ import annotations

import argparse
import os
import platform
import plistlib
import shutil
import subprocess
import sys

from updater import APP_AUTHOR, APP_COPYRIGHT, APP_LICENSE, APP_VERSION, parse_version

ROOT = os.path.dirname(os.path.abspath(__file__))


def _write_win_version_file(out_path: str) -> str:
    """Write PyInstaller VSVersionInfo file so Windows Properties shows Copyright & Version."""
    parts = list(parse_version(APP_VERSION))
    while len(parts) < 4:
        parts.append(0)
    ver_tuple = tuple(parts[:4])
    legal_copy = f"{APP_COPYRIGHT} ({APP_LICENSE})"
    content = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={ver_tuple},
    prodvers={ver_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', {APP_AUTHOR!r}),
            StringStruct('FileDescription', 'desk-widget - E-Ink Desktop Widget'),
            StringStruct('FileVersion', {APP_VERSION!r}),
            StringStruct('InternalName', 'desk-widget'),
            StringStruct('LegalCopyright', {legal_copy!r}),
            StringStruct('OriginalFilename', 'desk-widget.exe'),
            StringStruct('ProductName', 'desk-widget'),
            StringStruct('ProductVersion', {APP_VERSION!r})
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)
    return out_path


def _patch_macos_info_plist(app_path: str) -> None:
    """Embed version and Copyright metadata into macOS .app bundle Info.plist."""
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if not os.path.exists(plist_path):
        return
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    data["CFBundleName"] = "desk-widget"
    data["CFBundleDisplayName"] = "desk-widget"
    data["CFBundleIdentifier"] = "com.deskwidget.app"
    data["CFBundleShortVersionString"] = APP_VERSION
    data["CFBundleVersion"] = APP_VERSION
    data["NSHumanReadableCopyright"] = f"{APP_COPYRIGHT} ({APP_LICENSE})"
    data["NSHighResolutionCapable"] = True
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f)


def _ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        print("PyInstaller not found. Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def build(public: bool = False) -> str:
    os.chdir(ROOT)
    _ensure_pyinstaller()

    sep = ";" if sys.platform == "win32" else ":"
    dist_dir = os.path.join(ROOT, "dist")
    build_dir = os.path.join(ROOT, "build")
    staging_assets = os.path.join(build_dir, "_stage_assets")
    if os.path.exists(staging_assets):
        shutil.rmtree(staging_assets)
    os.makedirs(staging_assets, exist_ok=True)

    # Copy non-personal assets (or all assets for local dev build)
    src_assets = os.path.join(ROOT, "assets")
    if os.path.isdir(src_assets):
        for fn in os.listdir(src_assets):
            if public and fn.startswith("emblem_"):
                continue
            src_p = os.path.join(src_assets, fn)
            if os.path.isfile(src_p):
                shutil.copy2(src_p, os.path.join(staging_assets, fn))

    icon_file = os.path.join(ROOT, "app_icon.ico")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        "desk-widget",
        f"--add-data={staging_assets}{sep}assets",
    ]
    if os.path.exists(icon_file):
        cmd.append(f"--add-data={icon_file}{sep}.")
        cmd.extend(["--icon", icon_file])

    if sys.platform == "win32":
        ver_file = _write_win_version_file(os.path.join(build_dir, "win_version_info.txt"))
        cmd.extend(["--version-file", ver_file, "--onefile"])
    else:
        cmd.append("--onedir")

    cmd.append(os.path.join(ROOT, "widget.py"))
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)

    if sys.platform == "win32":
        out_path = os.path.join(dist_dir, "desk-widget.exe")
        print("Built Windows executable:", out_path)
        return out_path

    if sys.platform == "darwin":
        app_path = os.path.join(dist_dir, "desk-widget.app")
        _patch_macos_info_plist(app_path)
        arch = "apple-silicon" if platform.machine().lower() in ("arm64", "aarch64") else "intel"
        dmg_path = os.path.join(dist_dir, f"desk-widget-macos-{arch}.dmg")
        if os.path.exists(dmg_path):
            os.remove(dmg_path)
        if shutil.which("hdiutil") and os.path.isdir(app_path):
            subprocess.check_call(
                [
                    "hdiutil",
                    "create",
                    "-volname",
                    "desk-widget",
                    "-srcfolder",
                    app_path,
                    "-ov",
                    "-format",
                    "UDZO",
                    dmg_path,
                ]
            )
            print("Built macOS DMG:", dmg_path)
            return dmg_path
        print("Built macOS app bundle:", app_path)
        return app_path

    out_dir = os.path.join(dist_dir, "desk-widget")
    print("Built binary bundle:", out_dir)
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Package desk-widget as a standalone desktop app.")
    parser.add_argument(
        "--public",
        action="store_true",
        help="Exclude local assets/emblem_*.png when building a public release from a dev machine.",
    )
    args = parser.parse_args()
    build(public=args.public)


if __name__ == "__main__":
    main()
