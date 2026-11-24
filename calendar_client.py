"""Google Calendar (.ics / embed URL / local .ics) fetcher, parser, and monthly indexer."""

from __future__ import annotations

import calendar as pycal
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import os
import re
from typing import Iterable
from urllib.parse import parse_qs, quote, urlparse
from dateutil.rrule import rrulestr
from dateutil import tz
import requests


VN_WEEKDAYS = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
EN_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
ICS_WEEKDAYS = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
VN_WEEKDAY_FULL = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
EN_WEEKDAY_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def parse_clock_time(raw_str: str, default_val: tuple[int, int] = (9, 0)) -> tuple[int, int]:
    """Parse 24h ('17:00') or 12h ('5:00PM', '5:00 PM') clock strings to (hour, minute)."""
    txt = (raw_str or "").strip().upper()
    m = re.match(r"^(\d{1,2})\s*[:hH]\s*(\d{2})\s*(AM|PM)?$", txt)
    if not m:
        return default_val
    hh = int(m.group(1))
    mm = int(m.group(2))
    ampm = m.group(3)
    if ampm == "PM" and hh < 12:
        hh += 12
    elif ampm == "AM" and hh == 12:
        hh = 0
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        return default_val
    return (hh, mm)


def _escape_ics(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def build_rrule_from_preset(
    preset: str,
    start_d: date,
    custom_interval: int = 1,
    custom_freq: str = "YEARLY",
    custom_weekdays: list[int] | None = None,
) -> str:
    """Build an RFC-5545 RRULE string from preset or custom recurrence options."""
    p = (preset or "none").strip().lower()
    wd_code = ICS_WEEKDAYS[start_d.weekday()]
    if p == "daily":
        return "FREQ=DAILY"
    if p == "weekly":
        return f"FREQ=WEEKLY;BYDAY={wd_code}"
    if p == "monthly_day":
        return f"FREQ=MONTHLY;BYMONTHDAY={start_d.day}"
    if p == "monthly_nth":
        nth = (start_d.day - 1) // 7 + 1
        return f"FREQ=MONTHLY;BYDAY={nth}{wd_code}"
    if p == "yearly":
        return f"FREQ=YEARLY;BYMONTH={start_d.month};BYMONTHDAY={start_d.day}"
    if p == "weekdays":
        return "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
    if p == "custom":
        freq = (custom_freq or "YEARLY").strip().upper()
        if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
            freq = "YEARLY"
        interval = max(1, min(999, int(custom_interval or 1)))
        parts = [f"FREQ={freq}"]
        if interval > 1:
            parts.append(f"INTERVAL={interval}")
        if freq == "WEEKLY" and custom_weekdays:
            codes = [ICS_WEEKDAYS[i] for i in sorted(set(custom_weekdays)) if 0 <= i <= 6]
            if codes:
                parts.append("BYDAY=" + ",".join(codes))
        elif freq == "MONTHLY":
            parts.append(f"BYMONTHDAY={start_d.day}")
        elif freq == "YEARLY":
            parts.append(f"BYMONTH={start_d.month};BYMONTHDAY={start_d.day}")
        return ";".join(parts)
    return ""


def describe_repeat_options(start_d: date, lang: str = "vi") -> list[tuple[str, str]]:
    """Return [(preset_key, localized_label), ...] matching Google Calendar's recurrence menu."""
    is_en = (lang or "vi").strip().lower() == "en"
    wd = (EN_WEEKDAY_FULL if is_en else VN_WEEKDAY_FULL)[start_d.weekday()]
    nth = (start_d.day - 1) // 7 + 1
    if is_en:
        ord_map = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
        nth_lbl = ord_map.get(nth, f"{nth}th")
        return [
            ("none", "Does not repeat"),
            ("daily", "Daily"),
            ("weekly", f"Weekly on {wd}"),
            ("monthly_day", f"Monthly on day {start_d.day}"),
            ("monthly_nth", f"Monthly on the {nth_lbl} {wd}"),
            ("yearly", f"Annually on {start_d.strftime('%b')} {start_d.day}"),
            ("weekdays", "Every weekday (Monday to Friday)"),
            ("custom", "Custom..."),
        ]
    nth_vi = "đầu tiên" if nth == 1 else f"thứ {nth}"
    return [
        ("none", "Không lặp lại"),
        ("daily", "Hàng ngày"),
        ("weekly", f"Hàng tuần vào {wd}"),
        ("monthly_day", f"Hàng tháng vào ngày {start_d.day}"),
        ("monthly_nth", f"Hàng tháng vào {wd} {nth_vi}"),
        ("yearly", f"Hàng năm vào ngày {start_d.day} tháng {start_d.month}"),
        ("weekdays", "Mọi ngày trong tuần (từ Thứ Hai tới Thứ Sáu)"),
        ("custom", "Tùy chỉnh..."),
    ]


def format_event_time(ev: "CalendarEvent", lang: str = "vi", with_range: bool = False) -> str:
    if ev.is_all_day:
        return "All day" if (lang or "vi").strip().lower() == "en" else "Cả ngày"
    if with_range:
        return f"{ev.start.strftime('%H:%M')}–{ev.end.strftime('%H:%M')}"
    return ev.start.strftime("%H:%M")


@dataclass
class CalendarSource:
    name: str
    url: str
    enabled: bool = True


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    is_all_day: bool
    is_done: bool
    is_ongoing: bool
    location: str = ""
    description: str = ""
    calendar_name: str = ""
    conference_url: str = ""
    uid: str = ""
    is_recurring: bool = False

    @property
    def time_label(self) -> str:
        if self.is_all_day:
            return "Cả ngày"
        return self.start.strftime("%H:%M")

    @property
    def time_range_label(self) -> str:
        if self.is_all_day:
            return "Cả ngày"
        return f"{self.start.strftime('%H:%M')}–{self.end.strftime('%H:%M')}"


def _classify_meeting_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    path = (parsed.path or "").lower()

    if "zoom.us" in host or "zoom.com" in host or url.lower().startswith("zoommtg://"):
        return "Mở Zoom"
    if "discord.com" in host or "discord.gg" in host or url.lower().startswith("discord://"):
        return "Mở Discord"
    if "meet.google.com" in host:
        return "Mở Meet"
    if "teams.microsoft.com" in host or "teams.live.com" in host or url.lower().startswith("msteams://"):
        return "Mở Teams"
    if "webex.com" in host:
        return "Mở Webex"
    if "skype.com" in host:
        return "Mở Skype"
    if "zalo.me" in host or "zalo.vn" in host:
        return "Mở Zalo"
    if host == "t.me" or "telegram.me" in host or "telegram.org" in host or url.lower().startswith("tg://"):
        return "Mở Telegram"
    if host == "m.me" or "messenger.com" in host:
        return "Mở Messenger"
    if "slack.com" in host or url.lower().startswith("slack://"):
        return "Mở Slack"
    if "larksuite.com" in host or "feishu.cn" in host:
        return "Mở Lark"
    if "gather.town" in host:
        return "Mở Gather"
    if "docs.google.com" in host:
        if "/spreadsheets" in path:
            return "Mở Sheets"
        if "/presentation" in path:
            return "Mở Slides"
        if "/forms" in path:
            return "Mở Forms"
        return "Mở Docs"
    if "drive.google.com" in host:
        return "Mở Drive"
    if "notion.so" in host or "notion.site" in host or url.lower().startswith("notion://"):
        return "Mở Notion"
    if "figma.com" in host:
        return "Mở Figma"
    if "canva.com" in host:
        return "Mở Canva"
    if "miro.com" in host:
        return "Mở Miro"
    if "github.com" in host:
        return "Mở GitHub"
    if "gitlab.com" in host:
        return "Mở GitLab"
    if "youtube.com" in host or "youtu.be" in host:
        return "Mở YouTube"
    if "facebook.com" in host or "fb.com" in host:
        return "Mở Facebook"
    if "maps.google." in host or "maps.app.goo.gl" in host or ("google." in host and "/maps" in path):
        return "Mở Maps"
    if "loom.com" in host:
        return "Mở Loom"
    if "trello.com" in host:
        return "Mở Trello"
    if "atlassian.net" in host:
        return "Mở Jira"
    if "calendly.com" in host:
        return "Mở Calendly"
    if host:
        short = host[:16] + ("…" if len(host) > 16 else "")
        return f"Mở {short}"
    return "Mở Link"


def extract_meeting_links(
    ev: CalendarEvent,
    include_maps_for_address: bool = False,
    lang: str = "vi",
) -> list[tuple[str, str]]:
    """Extract unique (button_label, url) app/web links from an event."""
    raw_texts = [ev.conference_url, ev.location, ev.description]
    seen_urls: set[str] = set()
    results: list[tuple[str, str]] = []
    is_en = (lang or "vi").strip().lower() == "en"

    def _lbl(raw_lbl: str) -> str:
        if is_en and raw_lbl.startswith("Mở "):
            return "Open " + raw_lbl[3:]
        return raw_lbl

    scheme_pat = r"(?:https?|zoommtg|discord|msteams|tg|slack|notion)://[^\s<>\"'\\]+"
    for blob in raw_texts:
        if not blob:
            continue
        for m in re.finditer(scheme_pat, blob, re.IGNORECASE):
            url = m.group(0).rstrip(".,);]>")
            if url not in seen_urls:
                seen_urls.add(url)
                results.append((_lbl(_classify_meeting_url(url)), url))

    # Fallback: detect Zoom Meeting ID if no zoom.us URL is already present
    if not any("zoom.us" in u.lower() or "zoommtg://" in u.lower() for _, u in results):
        m_id = re.search(r"Meeting\s*ID\s*[:：]\s*([0-9][0-9\s-]{7,15}[0-9])", ev.description or "", re.IGNORECASE)
        if m_id:
            digits = re.sub(r"\D", "", m_id.group(1))
            if 9 <= len(digits) <= 11:
                z_url = f"https://zoom.us/j/{digits}"
                if z_url not in seen_urls:
                    seen_urls.add(z_url)
                    results.append((_lbl("Mở Zoom"), z_url))

    # Optional: if location is a physical address (no URL inside), offer Google Maps link
    loc = (ev.location or "").strip()
    if include_maps_for_address and loc and not re.search(r"https?://", loc, re.IGNORECASE):
        maps_url = f"https://www.google.com/maps/search/?api=1&query={quote(loc)}"
        results.append((_lbl("Mở Maps"), maps_url))

    return results


@dataclass
class CalendarSummary:
    events_today: list[CalendarEvent]
    upcoming_events: list[CalendarEvent]
    done_count: int
    has_urls: bool
    events_by_date: dict[date, list[CalendarEvent]] = field(default_factory=dict)
    error: str | None = None
    last_synced: datetime | None = None


def normalize_calendar_url(raw_url: str) -> str:
    """Normalize webcal:// and Google Calendar /embed?src=... URLs to .ics URLs."""
    u = raw_url.strip()
    if not u:
        return ""
    if u.lower().startswith("webcal://"):
        u = "https://" + u[len("webcal://"):]

    parsed = urlparse(u)
    if "calendar.google.com" in parsed.netloc.lower() and (
        "/embed" in parsed.path.lower() or "/render" in parsed.path.lower()
    ):
        qs = parse_qs(parsed.query)
        cal_id = (qs.get("src") or qs.get("cid") or [""])[0].strip()
        if cal_id:
            return f"https://calendar.google.com/calendar/ical/{quote(cal_id, safe='')}/public/basic.ics"
    return u


def _get_tz(tz_name: str):
    zone = tz.gettz(tz_name)
    if zone is not None:
        return zone
    return timezone(timedelta(hours=7))


def _unfold_ics(raw_text: str) -> list[str]:
    normalized = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    for line in normalized.split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)
    return lines


def _unescape_ics(value: str) -> str:
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def _parse_ics_datetime(raw_val: str, params: dict[str, str], default_tz) -> tuple[datetime, bool]:
    val = raw_val.strip()
    is_date_only = params.get("VALUE") == "DATE" or (len(val) == 8 and val.isdigit())
    if is_date_only:
        d = datetime.strptime(val[:8], "%Y%m%d").date()
        return datetime.combine(d, time(0, 0), tzinfo=default_tz), True

    if val.endswith("Z"):
        dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.astimezone(default_tz), False

    if "T" in val:
        dt_naive = datetime.strptime(val[:15], "%Y%m%dT%H%M%S")
        tzid = params.get("TZID")
        src_tz = tz.gettz(tzid) if tzid else default_tz
        if src_tz is None:
            src_tz = default_tz
        return dt_naive.replace(tzinfo=src_tz).astimezone(default_tz), False

    d = datetime.strptime(val[:8], "%Y%m%d").date()
    return datetime.combine(d, time(0, 0), tzinfo=default_tz), True


def _split_prop(line: str) -> tuple[str, dict[str, str], str] | None:
    if ":" not in line:
        return None
    left, val = line.split(":", 1)
    parts = left.split(";")
    name = parts[0].upper()
    params: dict[str, str] = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v.strip('"')
    return name, params, val


def _parse_iso_duration(dur: str) -> timedelta:
    match = re.match(
        r"^([+-])?P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$",
        dur,
    )
    if not match:
        return timedelta(hours=1)
    sign = -1 if match.group(1) == "-" else 1
    weeks = int(match.group(2) or 0)
    days = int(match.group(3) or 0)
    hours = int(match.group(4) or 0)
    minutes = int(match.group(5) or 0)
    seconds = int(match.group(6) or 0)
    return sign * timedelta(weeks=weeks, days=days, hours=hours, minutes=minutes, seconds=seconds)


def _parse_raw_events(ics_text: str, default_tz) -> list[dict]:
    lines = _unfold_ics(ics_text)
    events: list[dict] = []
    cur: dict | None = None

    for line in lines:
        upper = line.strip().upper()
        if upper == "BEGIN:VEVENT":
            cur = {"exdates": [], "rrule": None}
            continue
        if upper == "END:VEVENT":
            if cur is not None and "dtstart" in cur:
                events.append(cur)
            cur = None
            continue
        if cur is None:
            continue

        parsed = _split_prop(line)
        if not parsed:
            continue
        name, params, val = parsed

        if name == "UID":
            cur["uid"] = val.strip()
        elif name == "SUMMARY":
            cur["summary"] = _unescape_ics(val).replace("\n", " ")
        elif name == "LOCATION":
            cur["location"] = _unescape_ics(val).replace("\n", " ")
        elif name == "DESCRIPTION":
            cur["description"] = _unescape_ics(val)
        elif name in ("X-GOOGLE-CONFERENCE", "URL"):
            cur["conference_url"] = val.strip()
        elif name == "STATUS":
            cur["status"] = val.strip().upper()
        elif name == "RRULE":
            cur["rrule"] = val.strip()
        elif name == "DTSTART":
            dt, is_all_day = _parse_ics_datetime(val, params, default_tz)
            cur["dtstart"] = dt
            cur["is_all_day"] = is_all_day
        elif name == "DTEND":
            dt, _ = _parse_ics_datetime(val, params, default_tz)
            cur["dtend"] = dt
        elif name == "DURATION":
            cur["duration"] = _parse_iso_duration(val.strip())
        elif name == "RECURRENCE-ID":
            dt, _ = _parse_ics_datetime(val, params, default_tz)
            cur["recurrence_id"] = dt
        elif name == "EXDATE":
            for item in val.split(","):
                if item.strip():
                    dt, _ = _parse_ics_datetime(item, params, default_tz)
                    cur["exdates"].append(dt)

    return events


def _expand_events(
    raw_events: list[dict],
    window_start: datetime,
    window_end: datetime,
    now: datetime,
    default_tz,
    calendar_name: str = "",
) -> list[CalendarEvent]:
    overrides: dict[str, set[datetime]] = {}
    for ev in raw_events:
        if "recurrence_id" in ev and "uid" in ev:
            overrides.setdefault(ev["uid"], set()).add(ev["recurrence_id"])

    expanded: list[CalendarEvent] = []
    for ev in raw_events:
        if ev.get("status") == "CANCELLED":
            continue

        dtstart: datetime = ev["dtstart"]
        is_all_day: bool = ev.get("is_all_day", False)
        if "dtend" in ev:
            duration = ev["dtend"] - dtstart
        elif "duration" in ev:
            duration = ev["duration"]
        else:
            duration = timedelta(days=1) if is_all_day else timedelta(hours=1)
        if duration <= timedelta(0):
            duration = timedelta(days=1) if is_all_day else timedelta(minutes=30)

        title = ev.get("summary") or "(Không có tiêu đề)"
        location = ev.get("location", "")
        description = ev.get("description", "")
        conference_url = ev.get("conference_url", "")
        uid = ev.get("uid", "")

        occurrences: Iterable[datetime]
        if ev.get("rrule") and "recurrence_id" not in ev:
            try:
                rule = rrulestr(ev["rrule"], dtstart=dtstart)
                search_start = window_start - duration - timedelta(days=1)
                occurrences = rule.between(search_start, window_end, inc=True)
            except Exception:
                occurrences = [dtstart]
        else:
            occurrences = [dtstart]

        exdates = set(ev.get("exdates", []))
        ex_dates_only = {d.date() for d in exdates}
        ov_set = overrides.get(uid, set())
        ov_dates_only = {d.date() for d in ov_set}

        for occ_start in occurrences:
            if occ_start.tzinfo is None:
                occ_start = occ_start.replace(tzinfo=default_tz)
            else:
                occ_start = occ_start.astimezone(default_tz)

            if ev.get("rrule") and "recurrence_id" not in ev:
                if occ_start in exdates or (is_all_day and occ_start.date() in ex_dates_only):
                    continue
                if occ_start in ov_set or (is_all_day and occ_start.date() in ov_dates_only):
                    continue

            occ_end = occ_start + duration
            if occ_end <= window_start or occ_start >= window_end:
                continue

            is_ongoing = (not is_all_day) and (occ_start <= now < occ_end)
            is_done = (not is_all_day) and (occ_end <= now)
            is_rec = bool(ev.get("rrule") or "recurrence_id" in ev)
            expanded.append(
                CalendarEvent(
                    title=title,
                    start=occ_start,
                    end=occ_end,
                    is_all_day=is_all_day,
                    is_done=is_done,
                    is_ongoing=is_ongoing,
                    location=location,
                    description=description,
                    calendar_name=calendar_name,
                    conference_url=conference_url,
                    uid=uid,
                    is_recurring=is_rec,
                )
            )

    return expanded


def event_occurrence_key(ev: CalendarEvent) -> str:
    """Stable key identifying a specific occurrence (distinguishes recurring days)."""
    ident = (ev.uid or ev.title or "").strip()
    return f"{ev.calendar_name}|{ident}|{ev.start.isoformat()}"


def find_due_reminders(
    events: list[CalendarEvent],
    now: datetime,
    minutes_before: int = 15,
    notified_keys: set[str] | None = None,
) -> list[tuple[str, CalendarEvent, int]]:
    """Return un-notified timed events starting within minutes_before (supports recurring & one-off)."""
    lead_mins = max(0, min(240, int(minutes_before)))
    upper_secs = max(30, lead_mins * 60)
    seen = notified_keys or set()
    due: list[tuple[str, CalendarEvent, int]] = []

    for ev in events:
        if ev.is_all_day or ev.is_done:
            continue
        start_dt = ev.start
        cmp_now = now
        if start_dt.tzinfo is not None and cmp_now.tzinfo is None:
            cmp_now = cmp_now.replace(tzinfo=start_dt.tzinfo)
        elif start_dt.tzinfo is None and cmp_now.tzinfo is not None:
            cmp_now = cmp_now.replace(tzinfo=None)

        secs_left = (start_dt - cmp_now).total_seconds()
        if -60.0 <= secs_left <= upper_secs:
            key = event_occurrence_key(ev)
            if key in seen:
                continue
            mins_left = max(0, int((secs_left + 30.0) // 60)) if secs_left > 0 else 0
            due.append((key, ev, mins_left))

    due.sort(key=lambda item: (item[1].start, item[1].title))
    return due


def _parse_local_event_item(item: dict, default_tz) -> dict | None:
    """Normalize a local_events config item into raw VEVENT fields."""
    if not isinstance(item, dict) or not bool(item.get("enabled", True)):
        return None
    title = str(item.get("title") or "").strip()
    if not title:
        return None
    s_str = str(item.get("start_date") or "").strip()
    e_str = str(item.get("end_date") or s_str).strip()
    try:
        sd = date.fromisoformat(s_str)
        ed = date.fromisoformat(e_str)
    except ValueError:
        return None
    if ed < sd:
        ed = sd
    all_day = bool(item.get("all_day", True))
    if all_day:
        dtstart = datetime.combine(sd, time(0, 0), tzinfo=default_tz)
        dtend = datetime.combine(ed + timedelta(days=1), time(0, 0), tzinfo=default_tz)
    else:
        sh, sm = parse_clock_time(str(item.get("start_time") or "09:00"), (9, 0))
        eh, em = parse_clock_time(str(item.get("end_time") or f"{(sh + 1) % 24:02d}:{sm:02d}"), ((sh + 1) % 24, sm))
        dtstart = datetime.combine(sd, time(sh, sm), tzinfo=default_tz)
        dtend = datetime.combine(ed, time(eh, em), tzinfo=default_tz)
        if dtend <= dtstart:
            dtend = dtstart + timedelta(hours=1)

    rrule = str(item.get("rrule") or "").strip()
    if not rrule:
        preset = str(item.get("repeat") or "none").strip().lower()
        if preset != "none":
            rrule = build_rrule_from_preset(
                preset,
                sd,
                custom_interval=int(item.get("custom_interval", 1) or 1),
                custom_freq=str(item.get("custom_freq") or "YEARLY"),
                custom_weekdays=item.get("custom_weekdays") if isinstance(item.get("custom_weekdays"), list) else None,
            )

    raw_ev: dict = {
        "uid": str(item.get("id") or f"local-{s_str}-{title[:16]}"),
        "summary": title,
        "dtstart": dtstart,
        "dtend": dtend,
        "is_all_day": all_day,
        "location": str(item.get("location") or "").strip(),
        "description": str(item.get("notes") or "").strip(),
        "exdates": [],
    }
    if rrule:
        raw_ev["rrule"] = rrule
    return raw_ev


def local_events_to_ics(local_events: list[dict], tz_name: str = "Asia/Ho_Chi_Minh") -> str:
    """Serialize user's local_events list into a valid VCALENDAR ICS string."""
    default_tz = _get_tz(tz_name)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//hhuuphucc//desk-widget//EN"]
    count = 0
    for item in local_events or []:
        raw_ev = _parse_local_event_item(item, default_tz)
        if raw_ev is None:
            continue
        count += 1
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{_escape_ics(raw_ev['uid'])}")
        lines.append(f"SUMMARY:{_escape_ics(raw_ev['summary'])}")
        if raw_ev["is_all_day"]:
            lines.append(f"DTSTART;VALUE=DATE:{raw_ev['dtstart'].strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{raw_ev['dtend'].strftime('%Y%m%d')}")
        else:
            lines.append(f"DTSTART;TZID={tz_name}:{raw_ev['dtstart'].strftime('%Y%m%dT%H%M%S')}")
            lines.append(f"DTEND;TZID={tz_name}:{raw_ev['dtend'].strftime('%Y%m%dT%H%M%S')}")
        if raw_ev.get("rrule"):
            lines.append(f"RRULE:{raw_ev['rrule']}")
        if raw_ev.get("location"):
            lines.append(f"LOCATION:{_escape_ics(raw_ev['location'])}")
        if raw_ev.get("description"):
            lines.append(f"DESCRIPTION:{_escape_ics(raw_ev['description'])}")
        lines.append("END:VEVENT")
    if count == 0:
        return ""
    lines.append("END:VCALENDAR")
    return "\n".join(lines) + "\n"


def find_due_local_reminders(
    local_events: list[dict],
    now: datetime,
    tz_name: str = "Asia/Ho_Chi_Minh",
    notified_keys: set[str] | None = None,
) -> list[tuple[str, CalendarEvent, int]]:
    """Evaluate custom local events with per-event lead time (minutes/hours/days/weeks at HH:MM)."""
    default_tz = _get_tz(tz_name)
    if now.tzinfo is None:
        cmp_now = now.replace(tzinfo=default_tz)
    else:
        cmp_now = now.astimezone(default_tz)
    seen = notified_keys or set()
    due: list[tuple[str, CalendarEvent, int]] = []

    for item in local_events or []:
        if not isinstance(item, dict) or not bool(item.get("notify_enabled", True)):
            continue
        raw_ev = _parse_local_event_item(item, default_tz)
        if raw_ev is None:
            continue

        raw_rules = item.get("notifications")
        if isinstance(raw_rules, list) and raw_rules:
            rules = [r for r in raw_rules if isinstance(r, dict)]
        else:
            rules = [
                {
                    "value": item.get("notify_value", 1 if raw_ev["is_all_day"] else 15),
                    "unit": item.get("notify_unit") or ("days" if raw_ev["is_all_day"] else "minutes"),
                    "at": item.get("notify_at") or "09:00",
                }
            ]
        if not rules:
            continue

        max_look = 10
        norm_rules: list[tuple[int, str, str]] = []
        for r in rules:
            unit = str(r.get("unit") or ("days" if raw_ev["is_all_day"] else "minutes")).strip().lower()
            try:
                val = max(0, int(r.get("value", 1 if raw_ev["is_all_day"] else 15)))
            except Exception:
                val = 1 if raw_ev["is_all_day"] else 15
            at_str = str(r.get("at") or "09:00")
            norm_rules.append((val, unit, at_str))
            if unit == "days":
                max_look = max(max_look, val + 3)
            elif unit == "weeks":
                max_look = max(max_look, val * 7 + 3)
            elif unit == "hours":
                max_look = max(max_look, (val // 24) + 3)

        win_start = cmp_now - timedelta(days=1)
        win_end = cmp_now + timedelta(days=max_look)
        occs = _expand_events([raw_ev], win_start, win_end, cmp_now, default_tz, calendar_name="")

        for occ in occs:
            for val, unit, at_str in norm_rules:
                nh, nm = parse_clock_time(at_str, (9, 0))
                if occ.is_all_day or unit in ("days", "weeks"):
                    days_off = val * 7 if unit == "weeks" else (val if unit == "days" else 0)
                    trig_d = occ.start.date() - timedelta(days=days_off)
                    notify_dt = datetime.combine(trig_d, time(nh, nm), tzinfo=default_tz)
                    if unit == "hours":
                        notify_dt -= timedelta(hours=val)
                    elif unit == "minutes":
                        notify_dt -= timedelta(minutes=val)
                    diff_secs = (cmp_now - notify_dt).total_seconds()
                    if not (0.0 <= diff_secs <= 900.0):
                        continue
                else:
                    mins_off = val * 60 if unit == "hours" else val
                    notify_dt = occ.start - timedelta(minutes=mins_off)
                    if not (notify_dt <= cmp_now <= occ.start + timedelta(seconds=60)):
                        continue

                occ_key = f"local|{occ.uid or occ.title}|{occ.start.date().isoformat()}|{unit}:{val}:{nh:02d}{nm:02d}"
                if occ_key in seen:
                    continue
                secs_left = (occ.start - cmp_now).total_seconds()
                mins_left = max(0, int((secs_left + 30.0) // 60)) if secs_left > 0 else 0
                due.append((occ_key, occ, mins_left))

    due.sort(key=lambda x: (x[1].start, x[1].title))
    return due


def _index_events_by_date(
    events: list[CalendarEvent],
    range_start: date,
    range_end: date,
) -> dict[date, list[CalendarEvent]]:
    by_date: dict[date, list[CalendarEvent]] = {}
    for ev in events:
        first_d = ev.start.date()
        last_dt = ev.end - timedelta(seconds=1) if ev.end > ev.start else ev.start
        last_d = last_dt.date()
        cur_d = max(first_d, range_start)
        end_d = min(last_d, range_end)
        while cur_d <= end_d:
            by_date.setdefault(cur_d, []).append(ev)
            cur_d += timedelta(days=1)

    for d_key in by_date:
        by_date[d_key].sort(key=lambda e: (0 if e.is_all_day else 1, e.start, e.title))
    return by_date


def _coerce_sources(sources: list[CalendarSource | dict | str]) -> list[CalendarSource]:
    out: list[CalendarSource] = []
    for idx, item in enumerate(sources):
        if isinstance(item, CalendarSource):
            if item.enabled and item.url.strip():
                out.append(item)
        elif isinstance(item, dict):
            if item.get("enabled", True) and str(item.get("url", "")).strip():
                out.append(
                    CalendarSource(
                        name=str(item.get("name") or f"Lịch {idx + 1}").strip(),
                        url=str(item.get("url")).strip(),
                        enabled=True,
                    )
                )
        elif isinstance(item, str) and item.strip():
            out.append(CalendarSource(name=f"Lịch {idx + 1}", url=item.strip(), enabled=True))
    return out


def parse_ics_for_date(
    ics_contents: list[str | tuple[str, str]],
    now: datetime | None = None,
    tz_name: str = "Asia/Ho_Chi_Minh",
    view_year: int | None = None,
    view_month: int | None = None,
) -> CalendarSummary:
    """Parse ICS payloads (either raw text or (name, raw_text)) for today, 30d, and target month."""
    default_tz = _get_tz(tz_name)
    if now is None:
        now = datetime.now(default_tz)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=default_tz)
    else:
        now = now.astimezone(default_tz)

    today: date = now.date()
    y = view_year or today.year
    m = view_month or today.month
    _, last_dom = pycal.monthrange(y, m)
    month_first = date(y, m, 1)
    month_last = date(y, m, last_dom)

    today_start = datetime.combine(today, time(0, 0), tzinfo=default_tz)
    today_end = today_start + timedelta(days=1)
    upcoming_end = today_start + timedelta(days=30)

    month_start_dt = datetime.combine(month_first, time(0, 0), tzinfo=default_tz)
    month_end_dt = datetime.combine(month_last + timedelta(days=1), time(0, 0), tzinfo=default_tz)

    win_start = min(today_start, month_start_dt)
    win_end = max(upcoming_end, month_end_dt)

    all_events: list[CalendarEvent] = []
    for item in ics_contents:
        if isinstance(item, tuple):
            cal_name, text = item
        else:
            cal_name, text = "", item
        raw = _parse_raw_events(text, default_tz)
        all_events.extend(_expand_events(raw, win_start, win_end, now, default_tz, calendar_name=cal_name))

    today_list: list[CalendarEvent] = []
    upcoming_list: list[CalendarEvent] = []

    for ev in all_events:
        if ev.start < today_end and ev.end > today_start:
            today_list.append(ev)
        elif ev.start >= today_end and ev.start < upcoming_end:
            upcoming_list.append(ev)

    today_list.sort(key=lambda e: (0 if e.is_all_day else 1, e.start, e.title))
    upcoming_list.sort(key=lambda e: (e.start, 0 if e.is_all_day else 1, e.title))

    done_count = sum(1 for e in today_list if e.is_done)
    events_by_date = _index_events_by_date(all_events, month_first, month_last)

    return CalendarSummary(
        events_today=today_list,
        upcoming_events=upcoming_list[:4],
        done_count=done_count,
        has_urls=True,
        events_by_date=events_by_date,
        last_synced=now,
    )


class CalendarClient:
    """Stateful calendar client caching raw ICS payloads per named calendar source."""

    def __init__(self) -> None:
        self._raw_payloads: list[tuple[str, str]] = []
        self._local_payload: tuple[str, str] | None = None
        self._last_error: str | None = None
        self._has_urls: bool = False
        self._last_synced: datetime | None = None

    def fetch(
        self,
        sources: list[CalendarSource | dict | str],
        tz_name: str = "Asia/Ho_Chi_Minh",
        view_year: int | None = None,
        view_month: int | None = None,
        timeout: int = 12,
        local_events: list[dict] | None = None,
        local_label: str = "Nhắc riêng",
    ) -> CalendarSummary:
        default_tz = _get_tz(tz_name)
        now = datetime.now(default_tz)
        active = _coerce_sources(sources)
        self._has_urls = bool(active)

        local_ics = local_events_to_ics(local_events or [], tz_name=tz_name)
        self._local_payload = (local_label, local_ics) if local_ics else None

        if not active:
            self._raw_payloads = []
            self._last_error = None
            self._last_synced = now
            if self._local_payload is not None:
                return parse_ics_for_date(
                    [self._local_payload],
                    now=now,
                    tz_name=tz_name,
                    view_year=view_year,
                    view_month=view_month,
                )
            return CalendarSummary(
                events_today=[],
                upcoming_events=[],
                done_count=0,
                has_urls=False,
                last_synced=now,
            )

        payloads: list[tuple[str, str]] = []
        errors: list[str] = []
        for src in active:
            raw_url = src.url.strip()
            if "•" in raw_url:
                errors.append(
                    f"[{src.name}] Link bị che (••••). Hãy bấm nút Hiện (con mắt) hoặc Sao chép trên Google Calendar."
                )
                continue

            # Support local .ics file path
            if os.path.exists(raw_url) and os.path.isfile(raw_url):
                try:
                    with open(raw_url, "r", encoding="utf-8") as f:
                        payloads.append((src.name, f.read()))
                except Exception as exc:
                    errors.append(f"[{src.name}] {exc}")
                continue

            norm_url = normalize_calendar_url(raw_url)
            if not norm_url.lower().startswith(("http://", "https://")):
                errors.append(f"[{src.name}] Link không hợp lệ (cần https://... hoặc file .ics).")
                continue

            try:
                resp = requests.get(norm_url, timeout=timeout, headers={"User-Agent": "Desk-Widget/1.0"})
                if resp.status_code == 404 and "/public/basic.ics" in norm_url:
                    errors.append(
                        f"[{src.name}] Google trả về 404 (lịch chưa bật công khai). Hãy dùng link .ics gốc hoặc bí mật."
                    )
                    continue
                resp.raise_for_status()
                resp.encoding = resp.encoding or "utf-8"
                payloads.append((src.name, resp.text))
            except Exception as exc:
                errors.append(f"[{src.name}] {exc}")

        self._last_synced = now
        if not payloads:
            self._last_error = errors[0] if errors else "Không tải được lịch"
            if self._raw_payloads or self._local_payload is not None:
                merged = list(self._raw_payloads)
                if self._local_payload is not None:
                    merged.append(self._local_payload)
                summary = parse_ics_for_date(
                    merged,
                    now=now,
                    tz_name=tz_name,
                    view_year=view_year,
                    view_month=view_month,
                )
                summary.error = self._last_error
                return summary
            return CalendarSummary(
                events_today=[],
                upcoming_events=[],
                done_count=0,
                has_urls=True,
                error=self._last_error,
                last_synced=now,
            )

        self._raw_payloads = payloads
        self._last_error = errors[0] if errors else None
        merged = list(payloads)
        if self._local_payload is not None:
            merged.append(self._local_payload)
        summary = parse_ics_for_date(
            merged,
            now=now,
            tz_name=tz_name,
            view_year=view_year,
            view_month=view_month,
        )
        summary.error = self._last_error
        return summary

    def render_month_from_cache(
        self,
        tz_name: str,
        view_year: int,
        view_month: int,
    ) -> CalendarSummary:
        default_tz = _get_tz(tz_name)
        now = datetime.now(default_tz)
        if not self._has_urls and self._local_payload is None:
            return CalendarSummary(
                events_today=[],
                upcoming_events=[],
                done_count=0,
                has_urls=False,
                last_synced=now,
            )
        if not self._raw_payloads and self._local_payload is None:
            return CalendarSummary(
                events_today=[],
                upcoming_events=[],
                done_count=0,
                has_urls=True,
                error=self._last_error,
                last_synced=now,
            )
        merged = list(self._raw_payloads)
        if self._local_payload is not None:
            merged.append(self._local_payload)
        summary = parse_ics_for_date(
            merged,
            now=now,
            tz_name=tz_name,
            view_year=view_year,
            view_month=view_month,
        )
        summary.error = self._last_error
        return summary


def fetch_google_calendar(
    sources: list[CalendarSource | dict | str],
    tz_name: str = "Asia/Ho_Chi_Minh",
    timeout: int = 12,
) -> CalendarSummary:
    return CalendarClient().fetch(sources, tz_name=tz_name, timeout=timeout)
