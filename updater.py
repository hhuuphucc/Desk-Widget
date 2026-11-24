"""GitHub Releases update checker (cross-platform Windows & macOS Intel/Apple Silicon)."""

from __future__ import annotations

from dataclasses import dataclass
import platform
import re
import sys
import requests

APP_VERSION = "1.2.0"
APP_AUTHOR = "hhuuphucc"
APP_EMAIL = "hhuuphucc@gmail.com"
APP_COPYRIGHT = "Copyright (c) 2026 hhuuphucc"
APP_LICENSE = "MIT License"
GITHUB_REPO = "hhuuphucc/Desk-Widget"
GITHUB_PROFILE_URL = "https://github.com/hhuuphucc"
REPO_URL = f"https://github.com/{GITHUB_REPO}"


@dataclass
class UpdateCheckResult:
    status: str  # "update_available" | "up_to_date" | "not_configured" | "error"
    current_version: str
    latest_version: str = ""
    release_url: str = ""
    download_url: str = ""
    asset_name: str = ""
    notes: str = ""
    error: str = ""


def parse_version(tag: str) -> tuple[int, ...]:
    cleaned = (tag or "").strip().lstrip("vV")
    nums = [int(n) for n in re.findall(r"\d+", cleaned.split("-", 1)[0])]
    return tuple(nums) if nums else (0,)


def is_newer_version(remote_tag: str, current_version: str = APP_VERSION) -> bool:
    r = list(parse_version(remote_tag))
    c = list(parse_version(current_version))
    max_len = max(len(r), len(c))
    r.extend([0] * (max_len - len(r)))
    c.extend([0] * (max_len - len(c)))
    return tuple(r) > tuple(c)


def pick_asset_for_platform(
    assets: list[dict],
    sys_platform: str | None = None,
    machine: str | None = None,
) -> dict | None:
    """Pick the best matching GitHub Release asset for the user's OS & CPU architecture."""
    if not assets:
        return None
    plat = (sys_platform or sys.platform).lower()
    mach = (machine or platform.machine()).lower()

    if plat == "win32":
        for a in assets:
            nm = str(a.get("name") or "").lower()
            if nm.endswith(".exe"):
                return a
        return None

    if plat == "darwin":
        is_arm = mach in ("arm64", "aarch64")
        preferred = ("apple-silicon", "arm64") if is_arm else ("intel", "x86_64", "x64")
        for a in assets:
            nm = str(a.get("name") or "").lower()
            if nm.endswith(".dmg") and any(k in nm for k in preferred):
                return a
        for a in assets:
            nm = str(a.get("name") or "").lower()
            if nm.endswith(".dmg"):
                return a
        return None

    return None


def check_for_update(
    repo: str = GITHUB_REPO,
    current_version: str = APP_VERSION,
    timeout: int = 8,
    sys_platform: str | None = None,
    machine: str | None = None,
) -> UpdateCheckResult:
    clean_repo = (repo or "").strip().strip("/")
    if not clean_repo or "/" not in clean_repo:
        return UpdateCheckResult(status="not_configured", current_version=current_version)

    url = f"https://api.github.com/repos/{clean_repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"Desk-Widget/{current_version}",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 404:
            return UpdateCheckResult(
                status="up_to_date",
                current_version=current_version,
                latest_version=current_version,
                release_url=f"https://github.com/{clean_repo}/releases",
            )
        resp.raise_for_status()
        data = resp.json()
        tag = str(data.get("tag_name") or "").strip()
        rel_url = str(data.get("html_url") or f"https://github.com/{clean_repo}/releases")
        notes = str(data.get("body") or "").strip()
        assets = list(data.get("assets") or [])
        chosen = pick_asset_for_platform(assets, sys_platform=sys_platform, machine=machine)
        dl_url = str((chosen or {}).get("browser_download_url") or rel_url)
        asset_name = str((chosen or {}).get("name") or "")

        if tag and is_newer_version(tag, current_version):
            return UpdateCheckResult(
                status="update_available",
                current_version=current_version,
                latest_version=tag.lstrip("vV"),
                release_url=rel_url,
                download_url=dl_url,
                asset_name=asset_name,
                notes=notes[:320],
            )
        return UpdateCheckResult(
            status="up_to_date",
            current_version=current_version,
            latest_version=tag.lstrip("vV") or current_version,
            release_url=rel_url,
        )
    except Exception as exc:
        return UpdateCheckResult(
            status="error",
            current_version=current_version,
            error=str(exc),
        )
