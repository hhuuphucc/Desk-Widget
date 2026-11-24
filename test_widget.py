"""Automated unit and rendering verification for ESL Desk Widget."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
import unittest

from calendar_client import CalendarEvent, extract_meeting_links, normalize_calendar_url, parse_ics_for_date
from renderer import (
    BOTANICAL_DARK,
    BOTANICAL_LIGHT,
    MINIMAL_SANS_DARK,
    MINIMAL_SANS_LIGHT,
    PAPER_SERIF_DARK,
    PAPER_SERIF_LIGHT,
    _load_circle_logo,
    convert_temp,
    export_esl_bitmap,
    format_temp,
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
        embed = "https://calendar.google.com/calendar/embed?src=d6me8po8ned0nb06db1tf8v1uv909bt8%40import.calendar.google.com&ctz=Asia%2FHo_Chi_Minh"
        expected = "https://calendar.google.com/calendar/ical/d6me8po8ned0nb06db1tf8v1uv909bt8%40import.calendar.google.com/public/basic.ics"
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
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 5, 59), style="sans"), MINIMAL_SANS_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 6, 0), style="sans"), MINIMAL_SANS_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 17, 59), style="sans"), MINIMAL_SANS_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="sans"), MINIMAL_SANS_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="serif"), PAPER_SERIF_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 10, 0), style="serif"), PAPER_SERIF_LIGHT)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 18, 0), style="botanical"), BOTANICAL_DARK)
        self.assertEqual(resolve_theme("auto", datetime(2026, 11, 23, 10, 0), style="botanical"), BOTANICAL_LIGHT)
        self.assertEqual(resolve_theme("system", style="botanical", system_is_dark=True), BOTANICAL_DARK)
        self.assertEqual(resolve_theme("system", style="botanical", system_is_dark=False), BOTANICAL_LIGHT)

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
        self.assertEqual(updater.APP_LICENSE, "MIT License")
        self.assertEqual(widget.__copyright__, updater.APP_COPYRIGHT)
        self.assertEqual(widget.__license__, updater.APP_LICENSE)
        self.assertNotIn("auth", widget.DEFAULT_CONFIG)

        empty_cal = CalendarClient().fetch([], tz_name="Asia/Ho_Chi_Minh")
        self.assertFalse(empty_cal.has_urls)


if __name__ == "__main__":
    unittest.main()
