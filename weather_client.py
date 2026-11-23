"""Open-Meteo daily & full-week (T2-CN) weather fetcher with IP geolocation and caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from dateutil import tz
import requests


WMO_VIETNAMESE = {
    0: ("Quang đãng", "sun"),
    1: ("Nắng nhẹ", "sun"),
    2: ("Ít mây", "partly"),
    3: ("Nhiều mây", "cloud"),
    45: ("Sương mù", "cloud"),
    48: ("Sương mù", "cloud"),
    51: ("Mưa phùn", "rain"),
    53: ("Mưa phùn", "rain"),
    55: ("Mưa phùn", "rain"),
    61: ("Mưa nhẹ", "rain"),
    63: ("Mưa vừa", "rain"),
    65: ("Mưa to", "rain"),
    80: ("Mưa rào", "rain"),
    81: ("Mưa rào", "rain"),
    82: ("Mưa lớn", "rain"),
    95: ("Có dông", "storm"),
    96: ("Dông", "storm"),
    99: ("Dông mạnh", "storm"),
}

WMO_ENGLISH = {
    0: ("Clear", "sun"),
    1: ("Mostly clear", "sun"),
    2: ("Partly cloudy", "partly"),
    3: ("Overcast", "cloud"),
    45: ("Fog", "cloud"),
    48: ("Fog", "cloud"),
    51: ("Drizzle", "rain"),
    53: ("Drizzle", "rain"),
    55: ("Dense drizzle", "rain"),
    61: ("Light rain", "rain"),
    63: ("Rain", "rain"),
    65: ("Heavy rain", "rain"),
    80: ("Showers", "rain"),
    81: ("Showers", "rain"),
    82: ("Heavy showers", "rain"),
    95: ("Thunderstorm", "storm"),
    96: ("Thunderstorm", "storm"),
    99: ("Severe storm", "storm"),
}

VN_DAY_ABBR = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
EN_DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

CITY_VN_MAP = {
    "Hanoi": "Hà Nội",
    "Ha Noi": "Hà Nội",
    "Ho Chi Minh City": "TP.HCM",
    "Ho Chi Minh": "TP.HCM",
    "Da Nang": "Đà Nẵng",
    "Hai Phong": "Hải Phòng",
    "Can Tho": "Cần Thơ",
    "Nha Trang": "Nha Trang",
    "Hue": "Huế",
    "Da Lat": "Đà Lạt",
    "Vung Tau": "Vũng Tàu",
}

CITY_EN_MAP = {
    "Hà Nội": "Hanoi",
    "TP.HCM": "Ho Chi Minh",
    "Đà Nẵng": "Da Nang",
    "Hải Phòng": "Hai Phong",
    "Cần Thơ": "Can Tho",
    "Huế": "Hue",
    "Đà Lạt": "Da Lat",
    "Vũng Tàu": "Vung Tau",
}


def format_city_name(city: str, lang: str = "vi") -> str:
    clean = (city or "").strip()
    if (lang or "vi").lower() == "en":
        return CITY_EN_MAP.get(clean, clean or "Current location")
    return CITY_VN_MAP.get(clean, clean or "Vị trí hiện tại")


@dataclass
class DayForecast:
    date_obj: date
    weekday: str
    temp_min: int
    temp_max: int
    rain_prob: int
    icon: str
    desc: str
    rain_sum_mm: float = 0.0
    wind_max_kmh: int = 0
    uv_max: float = 0.0
    hourly_slots: list[tuple[str, int, str, int]] = field(default_factory=list)
    weather_code: int = -1
    hourly_codes: list[int] = field(default_factory=list)


@dataclass
class WeatherData:
    city: str
    current_temp: int
    current_desc: str
    current_icon: str
    today_min: int
    today_max: int
    today_rain_prob: int
    weekly: list[DayForecast]
    fetched_at: datetime
    current_humidity: int = 0
    current_wind: int = 0
    timezone: str = ""
    current_code: int = -1
    error: str | None = None


def _map_wmo(code: int, lang: str = "vi") -> tuple[str, str]:
    is_en = (lang or "vi").strip().lower() == "en"
    table = WMO_ENGLISH if is_en else WMO_VIETNAMESE
    if code in table:
        return table[code]
    if 50 <= code <= 69 or 80 <= code <= 86:
        return ("Rain", "rain") if is_en else ("Có mưa", "rain")
    if code >= 90:
        return ("Thunderstorm", "storm") if is_en else ("Có dông", "storm")
    return ("Cloudy", "cloud") if is_en else ("Nhiều mây", "cloud")


def weather_desc_for_lang(code: int, fallback: str, lang: str = "vi") -> str:
    if code >= 0:
        return _map_wmo(code, lang=lang)[0]
    if (lang or "vi").strip().lower() == "en":
        for k, (vi_txt, _) in WMO_VIETNAMESE.items():
            if vi_txt == fallback:
                return WMO_ENGLISH.get(k, (fallback, ""))[0]
        if fallback == "Mưa":
            return "Rain"
    return fallback


def day_abbr_for_lang(d_obj: date, fallback: str = "", lang: str = "vi") -> str:
    if (lang or "vi").strip().lower() == "en":
        return EN_DAY_ABBR[d_obj.weekday()]
    return fallback or VN_DAY_ABBR[d_obj.weekday()]


def _normalize_city(name: str) -> str:
    clean = name.strip()
    return CITY_VN_MAP.get(clean, clean or "Vị trí hiện tại")


def detect_location_with_tz(timeout: int = 6) -> tuple[str, float, float, str | None] | None:
    """Auto-detect current (city, latitude, longitude, iana_timezone) from public IP geolocation."""
    providers = [
        (
            "https://ipwho.is/",
            lambda d: d.get("success") is True,
            "city",
            "region",
            "latitude",
            "longitude",
            lambda d: (d.get("timezone") or {}).get("id") if isinstance(d.get("timezone"), dict) else None,
        ),
        (
            "http://ip-api.com/json/?fields=status,city,regionName,lat,lon,timezone",
            lambda d: d.get("status") == "success",
            "city",
            "regionName",
            "lat",
            "lon",
            lambda d: d.get("timezone"),
        ),
    ]
    for url, ok_fn, c_key, r_key, lat_key, lon_key, tz_fn in providers:
        try:
            resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Desk-Widget/1.0"})
            resp.raise_for_status()
            data = resp.json()
            if not ok_fn(data):
                continue
            raw_city = data.get(c_key) or data.get(r_key) or ""
            lat = float(data[lat_key])
            lon = float(data[lon_key])
            raw_tz = str(tz_fn(data) or "").strip()
            tz_id = raw_tz if (raw_tz and tz.gettz(raw_tz) is not None) else None
            return (_normalize_city(str(raw_city)), lat, lon, tz_id)
        except Exception:
            continue
    return None


def detect_location(timeout: int = 6) -> tuple[str, float, float] | None:
    """Auto-detect current (city, latitude, longitude) from public IP geolocation."""
    res = detect_location_with_tz(timeout=timeout)
    if res is None:
        return None
    city, lat, lon, _ = res
    return (city, lat, lon)


class WeatherClient:
    def __init__(self) -> None:
        self._cache: WeatherData | None = None
        self._cache_key: tuple[float, float, str] | None = None
        self._loc_cache: tuple[str, float, float] | None = None
        self._loc_tz: str | None = None
        self._loc_checked_at: datetime | None = None

    def get_detected_timezone(self) -> str | None:
        if self._cache is not None and self._cache.timezone:
            if tz.gettz(self._cache.timezone) is not None:
                return self._cache.timezone
        return self._loc_tz

    def resolve_location(self, weather_cfg: dict, force: bool = False) -> tuple[str, float, float]:
        fallback_city = str(weather_cfg.get("city") or "Hà Nội")
        fallback_lat = float(weather_cfg.get("latitude", 21.0285))
        fallback_lon = float(weather_cfg.get("longitude", 105.8542))

        if not weather_cfg.get("auto_location", True):
            return (fallback_city, fallback_lat, fallback_lon)

        now = datetime.now()
        cache_mins = max(5, int(weather_cfg.get("cache_minutes", 15)))
        if (
            not force
            and self._loc_cache is not None
            and self._loc_checked_at is not None
            and (now - self._loc_checked_at) < timedelta(minutes=cache_mins)
        ):
            return self._loc_cache

        detected = detect_location_with_tz()
        self._loc_checked_at = now
        if detected is not None:
            city, lat, lon, tz_id = detected
            self._loc_cache = (city, lat, lon)
            if tz_id:
                self._loc_tz = tz_id
            return (city, lat, lon)

        return self._loc_cache or (fallback_city, fallback_lat, fallback_lon)

    def get_weather(
        self,
        city: str,
        latitude: float,
        longitude: float,
        cache_minutes: int = 15,
        force: bool = False,
    ) -> WeatherData:
        now = datetime.now()
        key = (round(latitude, 4), round(longitude, 4), city)
        if (
            not force
            and self._cache is not None
            and self._cache_key == key
            and (now - self._cache.fetched_at) < timedelta(minutes=cache_minutes)
        ):
            return self._cache

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m",
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,precipitation_sum,wind_speed_10m_max,uv_index_max"
            ),
            "hourly": "temperature_2m,weather_code,precipitation_probability",
            "timezone": "auto",
            "past_days": 6,
            "forecast_days": 7,
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            cur = data["current"]
            cur_code = int(cur["weather_code"])
            cur_temp = round(float(cur["temperature_2m"]))
            cur_desc, cur_icon = _map_wmo(cur_code)
            cur_hum = int(round(float(cur.get("relative_humidity_2m") or 0)))
            cur_wind = int(round(float(cur.get("wind_speed_10m") or 0)))

            # Group key hourly slots (06:00, 12:00, 18:00, 21:00) per date
            hourly = data.get("hourly") or {}
            h_times = hourly.get("time") or []
            h_temps = hourly.get("temperature_2m") or []
            h_codes = hourly.get("weather_code") or []
            h_rains = hourly.get("precipitation_probability") or []
            hourly_by_day: dict[str, list[tuple[str, int, str, int]]] = {}
            hourly_codes_by_day: dict[str, list[int]] = {}
            target_hours = {"06:00", "12:00", "18:00", "21:00"}
            for i, ts in enumerate(h_times):
                if "T" not in ts:
                    continue
                d_part, t_part = ts.split("T", 1)
                if t_part in target_hours:
                    hc = int(h_codes[i] or 0)
                    desc_h, _ = _map_wmo(hc)
                    hourly_by_day.setdefault(d_part, []).append(
                        (
                            t_part,
                            round(float(h_temps[i] or 0)),
                            desc_h,
                            int(h_rains[i] or 0),
                        )
                    )
                    hourly_codes_by_day.setdefault(d_part, []).append(hc)

            daily = data["daily"]
            times = daily["time"]
            tmaxs = daily["temperature_2m_max"]
            tmins = daily["temperature_2m_min"]
            codes = daily["weather_code"]
            rains = daily.get("precipitation_probability_max") or [0] * len(times)
            rain_sums = daily.get("precipitation_sum") or [0.0] * len(times)
            winds = daily.get("wind_speed_10m_max") or [0.0] * len(times)
            uvs = daily.get("uv_index_max") or [0.0] * len(times)

            tz_id = str(data.get("timezone") or "").strip()
            zone = tz.gettz(tz_id) if tz_id else None
            today_d = datetime.now(zone).date() if zone is not None else now.date()
            monday_d = today_d - timedelta(days=today_d.weekday())
            sunday_d = monday_d + timedelta(days=6)

            week_days: list[DayForecast] = []
            today_fc: DayForecast | None = None
            for idx, d_str in enumerate(times):
                d_obj = datetime.strptime(d_str, "%Y-%m-%d").date()
                wd = VN_DAY_ABBR[d_obj.weekday()]
                d_code = int(codes[idx])
                desc, icon = _map_wmo(d_code)
                fc = DayForecast(
                    date_obj=d_obj,
                    weekday=wd,
                    temp_min=round(float(tmins[idx])),
                    temp_max=round(float(tmaxs[idx])),
                    rain_prob=int(rains[idx] or 0),
                    icon=icon,
                    desc=desc,
                    rain_sum_mm=round(float(rain_sums[idx] or 0.0), 1),
                    wind_max_kmh=round(float(winds[idx] or 0.0)),
                    uv_max=round(float(uvs[idx] or 0.0), 1),
                    hourly_slots=hourly_by_day.get(d_str, []),
                    weather_code=d_code,
                    hourly_codes=hourly_codes_by_day.get(d_str, []),
                )
                if d_obj == today_d:
                    today_fc = fc
                if monday_d <= d_obj <= sunday_d:
                    week_days.append(fc)

            week_days.sort(key=lambda d: d.date_obj)

            result = WeatherData(
                city=city,
                current_temp=cur_temp,
                current_desc=cur_desc,
                current_icon=cur_icon,
                today_min=today_fc.temp_min if today_fc else cur_temp,
                today_max=today_fc.temp_max if today_fc else cur_temp,
                today_rain_prob=today_fc.rain_prob if today_fc else 0,
                weekly=week_days,
                fetched_at=now,
                current_humidity=cur_hum,
                current_wind=cur_wind,
                timezone=tz_id if zone is not None else (self._loc_tz or ""),
                current_code=cur_code,
            )
            self._cache = result
            self._cache_key = key
            return result
        except Exception as exc:
            if self._cache is not None:
                return self._cache
            return WeatherData(
                city=city,
                current_temp=0,
                current_desc="Chờ mạng",
                current_icon="cloud",
                today_min=0,
                today_max=0,
                today_rain_prob=0,
                weekly=[],
                fetched_at=now,
                error=str(exc),
            )


def geocode_city(query: str) -> tuple[str, float, float] | None:
    """Resolve a city name to (display_name, lat, lon) using Open-Meteo Geocoding."""
    q = query.strip()
    if not q:
        return None
    try:
        resp = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": q, "count": 1, "language": "vi", "format": "json"},
            timeout=8,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        top = results[0]
        return (top.get("name") or q, float(top["latitude"]), float(top["longitude"]))
    except Exception:
        return None
