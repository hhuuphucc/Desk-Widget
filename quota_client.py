"""Antigravity model quota state & reset-window calculator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class QuotaStatus:
    model_name: str
    five_hour_pct: int
    five_hour_remain: int
    weekly_pct: int
    weekly_remain: int
    header_status: str
    is_stale: bool


def _clamp_pct(val: int | float) -> int:
    return max(0, min(100, int(round(val))))


def _next_5h_boundary(now: datetime) -> datetime:
    """Compute the next 5-hour block boundary from midnight if no explicit reset_at is set."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_since = (now - midnight).total_seconds() / 3600.0
    next_block = (int(hours_since // 5) + 1) * 5
    return midnight + timedelta(hours=next_block)


def build_quota_status(quota_cfg: dict, now: datetime | None = None) -> QuotaStatus:
    if now is None:
        now = datetime.now()

    model_name = str(quota_cfg.get("model_name") or "Gemini 4 · Antigravity").strip()
    five_pct = _clamp_pct(quota_cfg.get("five_hour_pct", 0))
    week_pct = _clamp_pct(quota_cfg.get("weekly_pct", 0))

    reset_str = str(quota_cfg.get("five_hour_reset_at") or "").strip()
    if reset_str:
        reset_label = reset_str
    else:
        reset_label = _next_5h_boundary(now).strftime("%H:%M")

    updated_raw = str(quota_cfg.get("updated_at") or "").strip()
    is_stale = False
    updated_label = now.strftime("%H:%M")
    if updated_raw:
        try:
            updated_dt = datetime.fromisoformat(updated_raw)
            updated_label = updated_dt.strftime("%H:%M")
            is_stale = (now - updated_dt) > timedelta(minutes=90)
        except ValueError:
            pass

    stale_suffix = " cũ" if is_stale else ""
    header_status = f"Quota {updated_label}{stale_suffix} · Tới {reset_label}"

    return QuotaStatus(
        model_name=model_name,
        five_hour_pct=five_pct,
        five_hour_remain=100 - five_pct,
        weekly_pct=week_pct,
        weekly_remain=100 - week_pct,
        header_status=header_status,
        is_stale=is_stale,
    )
