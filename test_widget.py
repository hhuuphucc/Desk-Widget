"""Automated unit and rendering verification for ESL Desk Widget."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import unittest

from calendar_client import CalendarEvent, extract_meeting_links, normalize_calendar_url, parse_ics_for_date
from renderer import (
    BOTANICAL_DARK,
    BOTANICAL_LIGHT,
    MACOS_DARK,
    MACOS_LIGHT,
    MINIMAL_SANS_DARK,
    MINIMAL_SANS_LIGHT,
    PAPER_SERIF_DARK,
    PAPER_SERIF_LIGHT,
    PIXEL_DARK,
    PIXEL_LIGHT,
    XIAOMI_DARK,
    XIAOMI_LIGHT,
    _load_circle_logo,
    convert_temp,
    export_esl_bitmap,
    format_temp,
    is_modern_desktop_style,
    patch_widget_system_stats,
    render_screen,
    render_widget_cached,
    render_widget_with_hits,
    resolve_theme,
)
from system_client import SystemMonitor, SystemStats, _detect_mac_gpu_name, _read_mac_gpu, _short_gpu_name, top_ram_processes
from weather_client import DayForecast, WeatherClient, WeatherData, detect_location, detect_location_with_tz


SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Google Inc//Google Calendar 70.9054//EN
BEGIN:VEVENT
UID:all-day-1
DTSTART;VALUE=DATE:20261123
DTEND;VALUE=DATE:20261124
SUMMARY:Tuần lễ sách và văn hóa đọc (Nhà Văn hóa Thanh Niên)
END:VEVENT
BEGIN:VEVENT
UID:done-1
DTSTART;TZID=Asia/Ho_Chi_Minh:20261123T090000
DTEND;TZID=Asia/Ho_Chi_Minh:20261123T100000
SUMMARY:Họp standup buổi sáng
END:VEVENT
BEGIN:VEVENT
UID:ongoing-1
DTSTART;TZID=Asia/Ho_Chi_Minh:20261123T190000
DTEND;TZID=Asia/Ho_Chi_Minh:20261123T200000
SUMMARY:Review code ESL Desk Widget
END:VEVENT
BEGIN:VEVENT
UID:recur-1
DTSTART;TZID=Asia/Ho_Chi_Minh:20261116T210000
DTEND;TZID=Asia/Ho_Chi_Minh:20261116T213000
RRULE:FREQ=WEEKLY;COUNT=5
SUMMARY:Đọc sách buổi tối
END:VEVENT
END:VCALENDAR
"""


class TestESLWidget(unittest.TestCase):
    def test_ics_parsing_and_rrule(self) -> None:
        tz_vn = timezone(timedelta(hours=7))
        now = datetime(2026, 11, 23, 19, 25, tzinfo=tz_vn)
        summary = parse_ics_for_date([SAMPLE_ICS], now=now, tz_name="Asia/Ho_Chi_Minh")
        self.assertEqual(summary.done_count, 1)
        self.assertEqual(len(summary.events_today), 4)
        self.assertTrue(summary.events_today[0].is_all_day)
        self.assertEqual(summary.events_today[1].is_done, True)
        self.assertEqual(summary.events_today[2].is_ongoing, True)
        self.assertEqual(summary.events_today[3].title, "Đọc sách buổi tối")
        self.assertIn(date(2026, 11, 23), summary.events_by_date)
        self.assertIn(date(2026, 11, 30), summary.events_by_date)

    def test_embed_url_normalization(self) -> None:
        embed = "https://calendar.google.com/calendar/embed?src=sample123456%40import.calendar.google.com&ctz=Asia%2FHo_Chi_Minh"
        expected = "https://calendar.google.com/calendar/ical/sample123456%40import.calendar.google.com/public/basic.ics"
        self.assertEqual(normalize_calendar_url(embed), expected)
        self.assertEqual(normalize_calendar_url("webcal://example.com/a.ics"), "https://example.com/a.ics")

    def test_meeting_links_and_theme(self) -> None:
        now = datetime(2026, 11, 23, 20, 30)
        ev_zoom = CalendarEvent(
            title="WORKSHOP 07",
            start=now,
            end=now + timedelta(hours=2),
            is_all_day=False,
            is_done=False,
            is_ongoing=True,
            description="https://zoom.us/j/94552704597?pwd=abc\nMeeting ID: 945 5270 4597",
        )
        ev_discord = CalendarEvent(
            title="OFFICE HOUR 05",
            start=now,
            end=now + timedelta(hours=1),
            is_all_day=False,
            is_done=False,
            is_ongoing=False,
            location="https://discord.com/channels/123/456",
        )
        ev_multi = CalendarEvent(
            title="Design Review",
            start=now,
            end=now + timedelta(hours=1),
            is_all_day=False,
            is_done=False,
            is_ongoing=False,
            location="Nhà Văn hóa Thanh Niên",
            description=(
                "Meet: https://meet.google.com/abc-defg-hij\n"
                "Slides: https://docs.google.com/presentation/d/123\n"
                "Figma: https://www.figma.com/file/xyz\n"
                "Zalo: https://zalo.me/g/abc123\n"
                "Repo: https://github.com/org/repo"
            ),
        )
        self.assertEqual(extract_meeting_links(ev_zoom), [("Mở Zoom", "https://zoom.us/j/94552704597?pwd=abc")])
        self.assertEqual(extract_meeting_links(ev_zoom, lang="en"), [("Open Zoom", "https://zoom.us/j/94552704597?pwd=abc")])
        self.assertEqual(extract_meeting_links(ev_discord), [("Mở Discord", "https://discord.com/channels/123/456")])
        multi_labels = [lbl for lbl, _ in extract_meeting_links(ev_multi, include_maps_for_address=True)]
        self.assertEqual(multi_labels, ["Mở Meet", "Mở Slides", "Mở Figma", "Mở Zalo", "Mở GitHub", "Mở Maps"])
        import renderer as _r_sun

        _prev_sun = _r_sun.get_sun_location()
        _r_sun.set_sun_location(None, None)  # no location yet -> 06:00-18:00 fallback
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 5, 59), style="sans"), MINIMAL_SANS_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 6, 0), style="sans"), MINIMAL_SANS_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 17, 59), style="sans"), MINIMAL_SANS_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="sans"), MINIMAL_SANS_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="serif"), PAPER_SERIF_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 10, 0), style="serif"), PAPER_SERIF_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="botanical"), BOTANICAL_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 10, 0), style="botanical"), BOTANICAL_LIGHT)

        # 'auto' follows real sunrise/sunset at the installed location & timezone
        tz_vn = timezone(timedelta(hours=7))
        hn = (21.0285, 105.8542)
        rise, sset = _r_sun.sun_times(date(2026, 11, 24), hn[0], hn[1], tz_vn)
        self.assertEqual((rise.hour, sset.hour), (6, 17))
        self.assertTrue(abs((rise.hour * 60 + rise.minute) - (6 * 60 + 13)) <= 3)
        self.assertTrue(abs((sset.hour * 60 + sset.minute) - (17 * 60 + 15)) <= 3)
        self.assertTrue(_r_sun.auto_is_dark(datetime(2026, 11, 24, 6, 0, tzinfo=tz_vn), *hn))
        self.assertFalse(_r_sun.auto_is_dark(datetime(2026, 11, 24, 6, 30, tzinfo=tz_vn), *hn))
        self.assertFalse(_r_sun.auto_is_dark(datetime(2026, 11, 24, 17, 0, tzinfo=tz_vn), *hn))
        self.assertTrue(_r_sun.auto_is_dark(datetime(2026, 11, 24, 17, 40, tzinfo=tz_vn), *hn))
        # Summer days are longer: 18:20 is still light in June
        self.assertFalse(_r_sun.auto_is_dark(datetime(2026, 6, 21, 18, 20, tzinfo=tz_vn), *hn))
        # Same instant, other side of the world (New York, UTC-5) -> night there
        self.assertTrue(_r_sun.auto_is_dark(datetime(2026, 11, 24, 12, 0, tzinfo=tz_vn), 40.71, -74.0))
        # Polar night: sun never rises
        self.assertEqual(_r_sun.sun_times(date(2026, 12, 21), 69.65, 18.96, timezone(timedelta(hours=1))), (None, None))
        _r_sun.set_sun_location(*hn)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 24, 17, 40, tzinfo=tz_vn), style="botanical"), BOTANICAL_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 24, 17, 0, tzinfo=tz_vn), style="botanical"), BOTANICAL_LIGHT)
        _r_sun.set_sun_location(*_prev_sun) if _prev_sun else _r_sun.set_sun_location(None, None)
        self.assertEqual(resolve_theme("system", style="botanical", system_is_dark=True), BOTANICAL_DARK)
        self.assertEqual(resolve_theme("system", style="botanical", system_is_dark=False), BOTANICAL_LIGHT)
        self.assertNotEqual(BOTANICAL_LIGHT.accent, PAPER_SERIF_LIGHT.accent)
        self.assertEqual(resolve_theme("light", style="macos"), MACOS_LIGHT)
        self.assertEqual(resolve_theme("dark", style="macos"), MACOS_DARK)
        self.assertEqual(resolve_theme("light", style="pixel"), PIXEL_LIGHT)
        self.assertEqual(resolve_theme("dark", style="pixel"), PIXEL_DARK)
        self.assertEqual(resolve_theme("light", style="xiaomi"), XIAOMI_LIGHT)
        self.assertEqual(resolve_theme("dark", style="xiaomi"), XIAOMI_DARK)

        from unittest.mock import MagicMock, patch
        import renderer
        with patch.object(renderer.sys, "platform", "darwin"), patch(
            "renderer.subprocess.run", return_value=MagicMock(returncode=0, stdout="Dark\n")
        ):
            self.assertTrue(renderer.is_system_dark_mode())
        with patch.object(renderer.sys, "platform", "darwin"), patch(
            "renderer.subprocess.run", return_value=MagicMock(returncode=1, stdout="")
        ):
            self.assertFalse(renderer.is_system_dark_mode())

    def test_system_monitor(self) -> None:
        stats = SystemMonitor().read(sample_interval=0.2)
        self.assertTrue(0 <= stats.ram_pct <= 100)
        self.assertGreater(stats.ram_total_gb, 0)
        self.assertTrue(0 <= stats.cpu_pct <= 100)
        ram_procs = top_ram_processes(5)
        self.assertGreater(len(ram_procs), 0)
        from system_client import top_cpu_processes

        cpu_procs = top_cpu_processes(0.3, 5)
        for item in cpu_procs:
            self.assertTrue(0.0 <= item["pct"] <= 100.0)

        # Verify zero-block real-time polling + cross-thread shared CPU baseline + partial SYSTEM patch
        mon = SystemMonitor()
        rt_stats = mon.read(sample_interval=0.28, include_cpu_temp=False)
        self.assertTrue(0 <= rt_stats.cpu_pct <= 100)
        thread_res: list[int] = []
        t = __import__("threading").Thread(target=lambda: thread_res.append(mon.read(sample_interval=None, include_cpu_temp=False).cpu_pct))
        t.start()
        t.join(timeout=2)
        self.assertEqual(len(thread_res), 1)
        self.assertTrue(0 <= thread_res[0] <= 100)
        cal = parse_ics_for_date([], tz_name="Asia/Ho_Chi_Minh")
        weather = WeatherData("Hà Nội", 24, "Mây", "cloud", 19, 27, 20, [], datetime.now())
        _, _, _, _, cache = render_widget_cached(cal, weather, stats, style="botanical", theme_mode="dark")
        updated_stats = SystemStats(88, 76, 18.2, 24.0, 64, "RTX 3050 Ti", 2048, 4096, 65.0, 61.0)
        patched_img, patched_hits, _ = patch_widget_system_stats(cache, updated_stats, temp_unit="C", lang="vi")
        self.assertEqual(patched_img.size, (480, 224))
        self.assertEqual({h.payload for h in patched_hits if h.action == "inspect_system"}, {"ram", "cpu", "gpu"})

    def test_auto_location_resolve(self) -> None:
        client = WeatherClient()
        city, lat, lon = client.resolve_location(
            {"auto_location": False, "city": "Đà Nẵng", "latitude": 16.0544, "longitude": 108.2022}
        )
        self.assertEqual(city, "Đà Nẵng")
        self.assertAlmostEqual(lat, 16.0544, places=3)

        detected = detect_location()
        if detected is not None:
            d_city, d_lat, d_lon = detected
            self.assertTrue(len(d_city) > 0)
            self.assertTrue(-90 <= d_lat <= 90)
            self.assertTrue(-180 <= d_lon <= 180)

        detected_tz = detect_location_with_tz()
        if detected_tz is not None:
            self.assertEqual(len(detected_tz), 4)

    def test_temp_conversion_and_formatting(self) -> None:
        self.assertEqual(convert_temp(0, "C"), 0)
        self.assertEqual(convert_temp(0, "F"), 32)
        self.assertEqual(convert_temp(100, "F"), 212)
        self.assertEqual(format_temp(25, "C"), "25°C")
        self.assertEqual(format_temp(25, "F"), "77°F")
        self.assertEqual(format_temp(25, "F", with_unit=False), "77°")

    def test_macos_helpers_mocked(self) -> None:
        from unittest.mock import patch
        sample_ioreg = (
            '  | |   "PerformanceStatistics" = {"Device Utilization %"=27,'
            '"In use system memory"=536870912,"Temperature(C)"=46}\n'
        )
        with patch("system_client.subprocess.check_output", return_value=sample_ioreg):
            util, name, v_used, _, gtemp = _read_mac_gpu("Apple M3 Pro")
        self.assertEqual(util, 27)
        self.assertEqual(name, "Apple M3 Pro")
        self.assertEqual(v_used, 512)
        self.assertEqual(gtemp, 46.0)

        with patch("system_client.subprocess.check_output", return_value="Apple M2 Max\n"):
            self.assertEqual(_detect_mac_gpu_name(), "Apple M2 Max")
        self.assertEqual(_short_gpu_name("Intel(R) Iris(R) Plus"), "Iris(R) Plus")

    def test_circle_logo_mask_and_no_personal_icons(self) -> None:
        import tempfile
        from PIL import Image

        base = os.path.dirname(os.path.abspath(__file__))
        self.assertTrue(os.path.exists(os.path.join(base, "app_icon.ico")))

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            Image.new("RGB", (120, 80), (40, 120, 200)).save(tmp_path)
            badge = _load_circle_logo(tmp_path, size=34, border_color="#B7C0C9")
            self.assertIsNotNone(badge)
            assert badge is not None
            self.assertEqual(badge.size, (34, 34))
            self.assertEqual(badge.getpixel((0, 0))[3], 0)
            self.assertGreater(badge.getpixel((17, 17))[3], 200)

            # Custom widget bg syncs with circular header logo when logo_mode="__widget_bg__"
            img_synced, _, _ = render_screen(
                parse_ics_for_date([], tz_name="Asia/Ho_Chi_Minh"),
                WeatherData("Hà Nội", 24, "Mưa", "rain", 19, 27, 50, [], datetime.now()),
                SystemStats(10, 40, 8.0, 16.0, 5, "GPU"),
                owner_name="My Widget",
                logo_path="__widget_bg__",
                bg_path=tmp_path,
            )
            self.assertEqual(img_synced.size, (480, 224))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_frozen_data_dir_and_build_script(self) -> None:
        from unittest.mock import patch
        import build_app
        import widget

        self.assertTrue(callable(build_app.build))
        with patch.object(widget, "IS_FROZEN", False):
            self.assertEqual(widget._get_user_data_dir(), os.path.dirname(os.path.abspath(widget.__file__)))
        with patch.object(widget, "IS_FROZEN", True), patch.object(widget, "IS_WINDOWS", True), patch.dict(
            os.environ, {"APPDATA": r"C:\TempAppData"}
        ):
            self.assertEqual(widget._get_user_data_dir(), os.path.join(r"C:\TempAppData", "desk-widget"))
        with patch.object(widget, "IS_FROZEN", True), patch.object(widget, "IS_WINDOWS", False), patch.object(
            widget, "IS_MACOS", True
        ):
            self.assertTrue(
                widget._get_user_data_dir().replace("\\", "/").endswith("Library/Application Support/desk-widget")
            )

        import plistlib
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            ver_path = build_app._write_win_version_file(os.path.join(td, "win_version_info.txt"))
            with open(ver_path, "r", encoding="utf-8") as vf:
                ver_txt = vf.read()
            self.assertIn("Copyright (c) 2026 hhuuphucc (MIT License)", ver_txt)
            self.assertIn("LegalCopyright", ver_txt)

            mac_app = os.path.join(td, "desk-widget.app")
            os.makedirs(os.path.join(mac_app, "Contents"), exist_ok=True)
            plist_file = os.path.join(mac_app, "Contents", "Info.plist")
            with open(plist_file, "wb") as pf:
                plistlib.dump({"CFBundleName": "old"}, pf)
            build_app._patch_macos_info_plist(mac_app)
            with open(plist_file, "rb") as pf:
                patched = plistlib.load(pf)
            self.assertEqual(patched["CFBundleIdentifier"], "com.deskwidget.app")
            self.assertEqual(patched["NSHumanReadableCopyright"], "Copyright (c) 2026 hhuuphucc (MIT License)")

    def test_update_checker(self) -> None:
        from unittest.mock import MagicMock, patch
        from updater import check_for_update, is_newer_version, parse_version, pick_asset_for_platform

        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertTrue(is_newer_version("v1.1.0", "1.0.0"))
        self.assertFalse(is_newer_version("v1.0.0", "1.0.0"))

        assets = [
            {"name": "desk-widget-windows-x64.exe", "browser_download_url": "https://example.com/win.exe"},
            {"name": "desk-widget-macos-apple-silicon.dmg", "browser_download_url": "https://example.com/mac-arm.dmg"},
            {"name": "desk-widget-macos-intel.dmg", "browser_download_url": "https://example.com/mac-intel.dmg"},
        ]
        self.assertEqual(pick_asset_for_platform(assets, "win32", "AMD64")["name"], "desk-widget-windows-x64.exe")
        self.assertEqual(
            pick_asset_for_platform(assets, "darwin", "arm64")["name"], "desk-widget-macos-apple-silicon.dmg"
        )
        self.assertEqual(pick_asset_for_platform(assets, "darwin", "x86_64")["name"], "desk-widget-macos-intel.dmg")

        self.assertEqual(check_for_update(repo="").status, "not_configured")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.2.0",
            "html_url": "https://github.com/demo/desk-widget/releases/tag/v1.2.0",
            "body": "Bug fixes and improvements",
            "assets": assets,
        }
        with patch("updater.requests.get", return_value=mock_resp):
            res = check_for_update(
                repo="demo/desk-widget", current_version="1.0.0", sys_platform="win32", machine="AMD64"
            )
        self.assertEqual(res.status, "update_available")
        self.assertEqual(res.latest_version, "1.2.0")
        self.assertEqual(res.download_url, "https://example.com/win.exe")

    def test_render_preview_and_esl_export(self) -> None:
        tz_vn = timezone(timedelta(hours=7))
        now = datetime(2026, 11, 23, 19, 25, tzinfo=tz_vn)
        cal = parse_ics_for_date([SAMPLE_ICS], now=now, tz_name="Asia/Ho_Chi_Minh")
        weather = WeatherClient().get_weather("Hà Nội", 21.0184, 105.8461)
        if weather.error:
            weather = WeatherData(
                city="Hà Nội",
                current_temp=24,
                current_desc="Mưa phùn",
                current_icon="rain",
                today_min=19,
                today_max=27,
                today_rain_prob=49,
                weekly=[
                    DayForecast(date(2026, 11, 23), "T2", 19, 27, 49, "rain", "Mưa phùn"),
                    DayForecast(date(2026, 11, 24), "T3", 18, 22, 60, "rain", "Mưa"),
                    DayForecast(date(2026, 11, 25), "T4", 16, 19, 50, "rain", "Mưa"),
                    DayForecast(date(2026, 11, 26), "T5", 15, 22, 10, "cloud", "Nhiều mây"),
                    DayForecast(date(2026, 11, 27), "T6", 16, 25, 10, "cloud", "Nhiều mây"),
                    DayForecast(date(2026, 11, 28), "T7", 17, 26, 10, "partly", "Ít mây"),
                    DayForecast(date(2026, 11, 29), "CN", 17, 25, 10, "sun", "Nắng nhẹ"),
                ],
                fetched_at=now,
            )
        stats = SystemStats(
            cpu_pct=24,
            ram_pct=56,
            ram_used_gb=13.5,
            ram_total_gb=23.7,
            gpu_pct=12,
            gpu_name="RTX 3050 Ti",
            gpu_vram_used_mb=512,
            gpu_vram_total_mb=4096,
            cpu_temp_c=59.0,
            gpu_temp_c=50.0,
        )
        screen, hits, _ = render_screen(
            cal, weather, stats, owner_name="Desk Widget", theme_mode="light", style="botanical", temp_unit="C", lang="vi", now=now
        )
        screen_en, _, _ = render_screen(
            cal, weather, stats, owner_name="Desk Widget", theme_mode="light", style="serif", temp_unit="F", lang="en", now=now
        )
        self.assertEqual(screen_en.size, (480, 224))
        framed, scaled_hits, _, _ = render_widget_with_hits(
            cal, weather, stats, owner_name="Desk Widget", theme_mode="light", style="serif", temp_unit="F", lang="en", show_esl_frame=True, scale=1.25, now=now
        )
        self.assertEqual(screen.size, (480, 224))
        self.assertGreater(framed.width, 480)
        self.assertTrue(any(h.action == "select_date" and h.payload == date(2026, 11, 23) for h in scaled_hits))
        self.assertTrue(any(h.action == "select_date" and h.payload == date(2026, 11, 23) and h.y1 < 85 for h in scaled_hits))
        self.assertTrue(any(h.action == "next_month" for h in scaled_hits))
        self.assertTrue(any(h.action == "toggle_temp_unit" for h in scaled_hits))
        self.assertEqual(sum(1 for h in scaled_hits if h.action == "select_weather_day"), 7)
        self.assertEqual({h.payload for h in scaled_hits if h.action == "inspect_system"}, {"ram", "cpu", "gpu"})

        out_dir = os.environ.get("ESL_PREVIEW_DIR", os.path.dirname(os.path.abspath(__file__)))
        preview_path = os.path.join(out_dir, "preview_widget.png")
        esl_path = os.path.join(out_dir, "preview_esl_296x128.png")
        framed.save(preview_path)
        export_esl_bitmap(screen, esl_path, (296, 128))
        self.assertTrue(os.path.exists(preview_path))
        self.assertTrue(os.path.exists(esl_path))

    def test_open_access_and_copyright(self) -> None:
        from calendar_client import CalendarClient
        import updater
        import widget

        self.assertEqual(updater.APP_COPYRIGHT, "Copyright (c) 2026 hhuuphucc")
        self.assertEqual(updater.APP_EMAIL, "hhuuphucc@gmail.com")
        self.assertEqual(updater.GITHUB_PROFILE_URL, "https://github.com/hhuuphucc")
        self.assertEqual(updater.APP_LICENSE, "MIT License")
        self.assertEqual(widget.__copyright__, updater.APP_COPYRIGHT)
        self.assertEqual(widget.__license__, updater.APP_LICENSE)
        self.assertNotIn("auth", widget.DEFAULT_CONFIG)

        empty_cal = CalendarClient().fetch([], tz_name="Asia/Ho_Chi_Minh")
        self.assertFalse(empty_cal.has_urls)

    def test_event_reminders_recurring_and_oneoff(self) -> None:
        from calendar_client import find_due_reminders

        tz_vn = timezone(timedelta(hours=7))
        ics_payload = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:all-day-rem
DTSTART;VALUE=DATE:20261124
DTEND;VALUE=DATE:20261125
SUMMARY:Holiday All Day
END:VEVENT
BEGIN:VEVENT
UID:oneoff-1
DTSTART;TZID=Asia/Ho_Chi_Minh:20261124T140000
DTEND;TZID=Asia/Ho_Chi_Minh:20261124T150000
SUMMARY:One-off Sync
END:VEVENT
BEGIN:VEVENT
UID:daily-1
DTSTART;TZID=Asia/Ho_Chi_Minh:20261123T143000
DTEND;TZID=Asia/Ho_Chi_Minh:20261123T150000
RRULE:FREQ=DAILY;COUNT=4
SUMMARY:Daily Standup
END:VEVENT
END:VCALENDAR
"""
        now = datetime(2026, 11, 24, 13, 45, tzinfo=tz_vn)
        summary = parse_ics_for_date([("Work", ics_payload)], now=now, tz_name="Asia/Ho_Chi_Minh")

        # 15m lead: triggers one-off (starts in 15m), ignores all-day and 14:30 recurring (45m away)
        seen: set[str] = set()
        due_15 = find_due_reminders(summary.events_today, now=now, minutes_before=15, notified_keys=seen)
        self.assertEqual(len(due_15), 1)
        self.assertEqual(due_15[0][1].title, "One-off Sync")
        self.assertFalse(due_15[0][1].is_recurring)
        self.assertEqual(due_15[0][2], 15)
        seen.add(due_15[0][0])

        # Deduplicates already notified event
        self.assertEqual(find_due_reminders(summary.events_today, now=now, minutes_before=15, notified_keys=seen), [])

        # Custom 45m lead picks up recurring event today; next day triggers a separate occurrence key
        due_45 = find_due_reminders(summary.events_today, now=now, minutes_before=45, notified_keys=seen)
        self.assertEqual(len(due_45), 1)
        self.assertEqual(due_45[0][1].title, "Daily Standup")
        self.assertTrue(due_45[0][1].is_recurring)
        seen.add(due_45[0][0])

        next_day_now = datetime(2026, 11, 25, 14, 20, tzinfo=tz_vn)
        next_day_sum = parse_ics_for_date([("Work", ics_payload)], now=next_day_now, tz_name="Asia/Ho_Chi_Minh")
        due_next = find_due_reminders(next_day_sum.events_today, now=next_day_now, minutes_before=15, notified_keys=seen)
        self.assertEqual(len(due_next), 1)
        self.assertEqual(due_next[0][1].title, "Daily Standup")
        self.assertEqual(due_next[0][2], 10)

    def test_custom_local_events_and_yearly_reminders(self) -> None:
        from calendar_client import (
            CalendarClient,
            build_rrule_from_preset,
            describe_repeat_options,
            find_due_local_reminders,
            local_events_to_ics,
            parse_clock_time,
        )

        self.assertEqual(parse_clock_time("5:00PM"), (17, 0))
        self.assertEqual(parse_clock_time("08:30"), (8, 30))

        d_sample = date(2026, 12, 2)  # Wednesday, first Wednesday of Dec 2026
        self.assertEqual(build_rrule_from_preset("yearly", d_sample), "FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=2")
        self.assertEqual(build_rrule_from_preset("monthly_nth", d_sample), "FREQ=MONTHLY;BYDAY=1WE")
        self.assertEqual(build_rrule_from_preset("weekdays", d_sample), "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")
        self.assertEqual(
            build_rrule_from_preset("custom", d_sample, custom_interval=2, custom_freq="WEEKLY", custom_weekdays=[0, 4]),
            "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,FR",
        )
        opts_vi = dict(describe_repeat_options(d_sample, "vi"))
        self.assertEqual(opts_vi["yearly"], "Hàng năm vào ngày 2 tháng 12")

        local_ev = {
            "id": "anniv-1",
            "enabled": True,
            "title": "Kỷ niệm đặc biệt",
            "start_date": "2026-12-02",
            "end_date": "2026-12-02",
            "all_day": True,
            "repeat": "yearly",
            "rrule": "FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=2",
            "location": "Hồ Hoàn Kiếm, Hà Nội",
            "notify_enabled": True,
            "notify_value": 1,
            "notify_unit": "days",
            "notify_at": "5:00PM",
        }
        ics_str = local_events_to_ics([local_ev], tz_name="Asia/Ho_Chi_Minh")
        self.assertIn("RRULE:FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=2", ics_str)

        # Even with 0 Google Calendar URLs, local events populate calendar summary & Map link
        cal = CalendarClient().fetch([], tz_name="Asia/Ho_Chi_Minh", view_year=2026, view_month=12, local_events=[local_ev])
        self.assertTrue(cal.has_urls)
        dec2 = cal.events_by_date.get(date(2026, 12, 2), [])
        self.assertEqual(len(dec2), 1)
        self.assertEqual(dec2[0].location, "Hồ Hoàn Kiếm, Hà Nội")
        self.assertTrue(any(lbl == "Mở Maps" for lbl, _ in extract_meeting_links(dec2[0], include_maps_for_address=True)))

        # Yearly recurrence expands onto Dec 2, 2027 too
        sum_2027 = parse_ics_for_date([("Personal", ics_str)], now=datetime(2027, 12, 2, 9, 0), tz_name="Asia/Ho_Chi_Minh", view_year=2027, view_month=12)
        self.assertEqual(len(sum_2027.events_today), 1)

        # Notification 1 day before 2026-12-02 at 5:00PM -> silent at 16:55, fires at 17:02
        tz_vn = timezone(timedelta(hours=7))
        seen: set[str] = set()
        self.assertEqual(
            find_due_local_reminders([local_ev], datetime(2026, 12, 1, 16, 55, tzinfo=tz_vn), "Asia/Ho_Chi_Minh", seen),
            [],
        )
        due_1702 = find_due_local_reminders([local_ev], datetime(2026, 12, 1, 17, 2, tzinfo=tz_vn), "Asia/Ho_Chi_Minh", seen)
        self.assertEqual(len(due_1702), 1)
        self.assertEqual(due_1702[0][1].title, "Kỷ niệm đặc biệt")
        self.assertTrue(due_1702[0][1].is_recurring)
        seen.add(due_1702[0][0])
        self.assertEqual(
            find_due_local_reminders([local_ev], datetime(2026, 12, 1, 17, 5, tzinfo=tz_vn), "Asia/Ho_Chi_Minh", seen),
            [],
        )

        # Multi-rule notifications on timed event: rule 0 (-1 day @ 5:00PM) + rule 1 (-15 min before 09:00)
        multi_ev = {
            "id": "multi-1",
            "enabled": True,
            "title": "Họp cuối năm",
            "start_date": "2026-12-02",
            "end_date": "2026-12-02",
            "all_day": False,
            "start_time": "09:00",
            "end_time": "10:00",
            "repeat": "none",
            "rrule": "",
            "notifications": [
                {"value": 1, "unit": "days", "at": "5:00PM"},
                {"value": 15, "unit": "minutes", "at": "09:00"},
            ],
        }
        seen_multi: set[str] = set()
        due_m1 = find_due_local_reminders([multi_ev], datetime(2026, 12, 1, 17, 1, tzinfo=tz_vn), "Asia/Ho_Chi_Minh", seen_multi)
        self.assertEqual(len(due_m1), 1)
        seen_multi.add(due_m1[0][0])
        due_m2 = find_due_local_reminders([multi_ev], datetime(2026, 12, 2, 8, 47, tzinfo=tz_vn), "Asia/Ho_Chi_Minh", seen_multi)
        self.assertEqual(len(due_m2), 1)
        self.assertEqual(due_m2[0][2], 13)

    def test_modern_ui_helpers(self) -> None:
        from modern_ui import format_pretty_date, get_dialog_theme, make_pill_dropdown, mousewheel_units

        self.assertEqual(format_pretty_date(date(2026, 12, 2), "vi"), "2 thg 12, 2026")
        self.assertEqual(format_pretty_date(date(2026, 12, 2), "en"), "Dec 2, 2026")
        for st in ("macos", "pixel", "xiaomi", "serif", "botanical", "sans"):
            for dk in (False, True):
                pal = get_dialog_theme(st, dk)
                self.assertEqual(pal.is_dark, dk)
        self.assertEqual(get_dialog_theme("xiaomi", False).check_shape, "circle")
        self.assertEqual(get_dialog_theme("macos", False).check_shape, "rounded")
        self.assertTrue(callable(make_pill_dropdown))
        self.assertEqual(mousewheel_units(0), 0)
        self.assertEqual(mousewheel_units(120, platform="win32"), -1)
        self.assertEqual(mousewheel_units(-240, platform="win32"), 2)
        self.assertEqual(mousewheel_units(30, platform="win32"), -1)
        self.assertEqual(mousewheel_units(1, platform="darwin"), -1)
        self.assertEqual(mousewheel_units(-2, platform="darwin"), 2)
        self.assertEqual(mousewheel_units(-8, platform="darwin"), 3)

        from dateutil import tz as _tz
        from weather_client import WORLD_TIMEZONES, geocode_city_with_tz

        self.assertGreaterEqual(len(WORLD_TIMEZONES), 30)
        for iana, label in WORLD_TIMEZONES:
            self.assertIsNotNone(_tz.gettz(iana), f"Invalid IANA timezone: {iana}")
            self.assertIn("UTC", label)
        self.assertTrue(callable(geocode_city_with_tz))

    def test_desktop_styles_and_placement(self) -> None:
        now = datetime(2026, 11, 24, 13, 30)
        cal = parse_ics_for_date([("Cá nhân", SAMPLE_ICS)], now=now, tz_name="Asia/Ho_Chi_Minh")
        weather = WeatherData(
            city="Hà Nội",
            current_temp=25,
            current_desc="Nắng nhẹ",
            current_icon="partly",
            today_min=20,
            today_max=28,
            today_rain_prob=10,
            weekly=[DayForecast(now.date() + timedelta(days=i), "T3", 20, 28, 10, "sun", "Nắng") for i in range(7)],
            fetched_at=now,
        )
        stats = SystemStats(38, 62, 14.2, 24.0, 22, "RTX 3050 Ti", 1024, 4096, 56.0, 51.0)
        icon_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
        bg_sample = icon_p if os.path.exists(icon_p) else None

        for st in ("macos", "pixel", "xiaomi"):
            self.assertTrue(is_modern_desktop_style(st))
            for mode in ("light", "dark"):
                out, hits, _, th, cache = render_widget_cached(
                    cal,
                    weather,
                    stats,
                    style=st,
                    theme_mode=mode,
                    logo_path=bg_sample,
                    bg_path=bg_sample,
                    logo_pos="far_right" if st == "macos" else ("after_title" if st == "pixel" else "far_left"),
                    bg_pos="bottom_right" if st == "xiaomi" else "left",
                    now=now,
                )
                self.assertEqual(out.mode, "RGBA")
                self.assertEqual(out.size, (480, 224))
                self.assertEqual(th.style, st)
                # Outer rounded corners are transparent, center area is opaque
                self.assertEqual(out.getpixel((0, 0))[3], 0)
                self.assertGreater(out.getpixel((240, 112))[3], 200)
                self.assertTrue(any(h.action == "inspect_system" for h in hits))
                # Verify fast 2s system patch keeps rounded corner alpha clean
                patched, _, _ = patch_widget_system_stats(cache, stats, temp_unit="C", lang="vi")
                self.assertEqual(patched.getpixel((0, 0))[3], 0)

        # Verify bg_path="__none__" cleanly disables background image/watermark across paper & desktop styles
        clean_paper, _, _, _, _ = render_widget_cached(cal, weather, stats, style="botanical", bg_path="__none__", now=now)
        clean_mac, _, _, _, _ = render_widget_cached(cal, weather, stats, style="macos", bg_path="__none__", now=now)
        self.assertEqual(clean_paper.size, (480, 224))
        self.assertEqual(clean_mac.size, (480, 224))

        # Verify background tone (original vs negative RGB inversion keeping alpha) & custom zoom/pan framing
        from renderer import apply_bg_tone, compose_bg_layer
        from PIL import Image as _Img

        swatch = _Img.new("RGBA", (20, 10), (30, 60, 90, 128))
        inv_swatch = apply_bg_tone(swatch, "negative")
        self.assertEqual(inv_swatch.getpixel((5, 5)), (225, 195, 165, 128))
        framed_layer = compose_bg_layer(swatch, 480, 224, pos="cover", zoom=1.35, offset_x=0.25, offset_y=-0.2, tone="negative")
        self.assertEqual(framed_layer.size, (480, 224))
        if bg_sample:
            neg_card, _, _, _, _ = render_widget_cached(
                cal,
                weather,
                stats,
                style="botanical",
                bg_path=bg_sample,
                bg_tone="negative",
                bg_zoom=1.25,
                bg_offset_x=0.2,
                bg_offset_y=-0.15,
                bg_opacity=0.80,
                now=now,
            )
            self.assertEqual(neg_card.size, (480, 224))
            mac_vivid, _, _, _, _ = render_widget_cached(
                cal,
                weather,
                stats,
                style="macos",
                bg_path=bg_sample,
                bg_opacity=0.80,
                now=now,
            )
            self.assertEqual(mac_vivid.size, (480, 224))
        else:
            import tempfile

            with tempfile.TemporaryDirectory() as td:
                op_img_path = Path(td) / "opaque_bg.png"
                _Img.new("RGB", (120, 80), (45, 95, 145)).save(op_img_path)
                for st in ("botanical", "macos"):
                    vivid_card, _, _, _, _ = render_widget_cached(
                        cal,
                        weather,
                        stats,
                        style=st,
                        bg_path=str(op_img_path),
                        bg_opacity=0.80,
                        now=now,
                    )
                    self.assertEqual(vivid_card.size, (480, 224))


if __name__ == "__main__":
    unittest.main()
