"""Cross-platform PyInstaller build script for desk-widget (Windows .exe & macOS .app/.dmg)."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


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
        cmd.append("--onefile")
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
