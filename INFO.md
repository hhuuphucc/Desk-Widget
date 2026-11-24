# Important Notes & Complete User Guide / Lưu ý đầy đủ (`INFO.md`)

**English** · [Tiếng Việt](#tiếng-việt) · [Back to `README.md`](README.md)

---

## English

Comprehensive guide covering location/IP detection, timezones, weather, Google Calendar `.ics`, real-time hardware monitoring, accounts/privacy, and Windows/macOS behavior.

### 1. Travelling Anywhere in the World (`Auto-detect via IP`)

When **`Auto-detect location & calendar timezone via IP`** is enabled in **Settings**:

- Whenever you connect to Wi-Fi or a new network in another province, state, or country — once the default `15`-minute cache expires or when you click **Refresh now** — the widget re-queries public IP geolocation (`ipwho.is`, with `ip-api.com` as fallback) to update:
  - **City / Region** name shown on the weather header
  - **`Lat/Lon`** coordinates and 7-day forecast (via **Open-Meteo** global data)
  - **Clock & Calendar Timezone** (combining `timezone="auto"` from Open-Meteo and the IP geolocation timezone)
- **Two normal IP-geolocation exceptions (PCs & Macs have no GPS):**
  1. **Mobile 4G/5G hotspots or regional ISPs:** Network carriers often route traffic through a central gateway in a larger nearby city, so IP geolocation may report that gateway city instead of your exact district/town.
  2. **VPN / Proxy active:** If you use a VPN connected to another region/country, the widget sees the VPN exit server's IP and shows that server's city, weather, and timezone.

### 2. Pinning Any City, Province, or State Manually

1. Open **Settings** (double-click any empty area on the widget or **Right-click → `Settings...`**).
2. **Uncheck** `Auto-detect location & calendar timezone via IP` — this unlocks `City`, `Find coords`, `Lat/Lon`, and `Timezone` (those 5 controls stay greyed out while Auto-IP is enabled).
3. Enter a place name and click **`Find coords`** (uses Open-Meteo's global Geocoding API).
- **Important tips:**
  - `Find coords` picks the **first popular match** (`count=1`). Ambiguous or accented local names may match a different town; use clear international spelling (e.g., `San Jose`, `Tokyo`, `Da Lat`, `New York`) or type exact **`Lat/Lon`** numbers manually.
  - Clicking `Find coords` fills **only `Lat/Lon`**. If the target city is in a different timezone and you want the widget clock and calendar events to follow it, update the **`Timezone`** field manually using a standard IANA ID (`Asia/Ho_Chi_Minh`, `Asia/Tokyo`, `America/New_York`, `Europe/London`, etc.).

### 3. Weather & `°C` / `°F` Notes

- Click directly on the temperature readout next to `SYSTEM` to switch between **`°C`** and **`°F`** instantly without opening Settings.
- Forecasts use **Open-Meteo** (no API key required) and cache for `15` minutes by default. If your PC/Mac is offline, weather shows `Chờ mạng` or retains the last cached reading when available.

### 4. Google Calendar (`.ics`) & Month Grid Notes

- **Supported sources:** Secret iCal URLs, public `.ics` links, Google Calendar `/embed?src=...` links (auto-converted to `/public/basic.ics`), `webcal://` links, and local `.ics` file paths.
- **Avoid masked bullets (`••••`):** Always click the **eye icon** or **Copy button** beside **Secret address in iCal format** in Google Calendar — Settings automatically rejects links containing `•`.
- **Cache & instant refresh:** Calendar data is cached for `15` minutes (`cache_minutes`); click **Right-click → `Refresh now`** whenever you want newly added meetings to show up immediately.
- **Month switching `<` / `>`:** Navigating months in the `TODAY` mini-calendar recalculates instantly from the in-memory `.ics` payload cache (fast, zero extra network calls), including recurring events (`RRULE`) and all-day events.
- **1-click popup links:** Clicking a day cell or truncated event row detects links inside event locations/descriptions — including `Zoom` (even `Meeting ID: ...` text fallback), `Google Meet`, `Teams`, `Discord`, `Zalo`, `Telegram`, `Messenger`, `Slack`, `Lark`, `Gather`, `Google Docs/Sheets/Slides/Forms/Drive`, `Notion`, `Figma`, `Canva`, `Miro`, `GitHub`, `GitLab`, `YouTube`, `Facebook`, and physical street addresses (creates a **Google Maps** search button).
- **Pre-event Reminders & Custom Local Events:** Supports both automatic reminders for `.ics` timed events (`0–240` min before in **Settings**) and **Custom Reminders / Events** created directly in the app for **any date** (even days without Google Calendar events) — with All-day or timed hours, **Yearly / Monthly / Weekly / Daily / Weekdays / Custom** recurrence, **Location** (1-click **Open Maps**), and flexible alert lead time (`minutes / hours / days / weeks` before at `HH:MM`). For `.ics` feeds, external all-day entries are skipped intentionally unless added with a custom reminder time.

### 5. Real-Time System Monitor (`RAM / CPU / GPU & Temperature`)

- **Very light background footprint:** Updating every `2 seconds` repaints only the `SYSTEM` quadrant (`patch_widget_system_stats`), using roughly **`~0.1%–0.2%` steady CPU**.
- **Brief CPU burst inside the `CPU` popup:** Clicking `CPU` runs `top_cpu_processes`, which snapshots all running OS processes twice over `0.8s`. Seeing `[Widget]` briefly around `~10–15%` inside that popup is normal one-off scanning overhead, not steady background usage.
- **Windows `svchost.exe (N)` & `MemCompression`:** Detail popups group processes by executable name. `svchost.exe (N)` is normal Windows service host processes (`N` instances grouped), and `MemCompression` is Windows compressing standby memory pages in RAM instead of swapping to disk — neither is a widget bug.
- **GPU & Temperature differences by hardware:**
  - **Windows + NVIDIA GPU:** Reads GPU %, VRAM `GB`, and GPU temp directly via `nvml.dll` (zero background console spawn; `nvidia-smi` fallback).
  - **Windows Intel/AMD iGPU only (no NVIDIA):** GPU `%` and VRAM may remain at `0%` / `0.0/0.0G` because NVML is NVIDIA-specific, while RAM, CPU, and CPU/thermal zone temp still update normally.
  - **macOS (Apple Silicon M1–M4 & Intel):** Reads GPU utilization via throttled `ioreg IOAccelerator` (unified Apple Silicon memory does not report separate VRAM capacity in GB). CPU temperature relies on `IOHWSensor` (mostly Intel) unless you install a rootless sensor CLI such as `brew install smctemp` or `brew install osx-cpu-temp`.

### 6. Interactions, Single-Instance, Export & Layout Quirks

- **Single-instance safety:** Opening the app a second time automatically closes the previous `widget.pid` instance so you never get duplicate overlapping widgets.
- **Z-order (`Always on top` vs `Send behind`):** On Windows, fullscreen apps (games, fullscreen video, slides) keep focus naturally and `Send behind` pushes the widget cleanly to desktop level; macOS toggles `-topmost` / `lower()` cleanly.
- **E-Ink 3-Color ESL Export (`296×128 PNG/BMP`):** Converts the current widget canvas into a 3-color Black/White/Red bitmap sized for `2.9"` (`296×128`) electronic shelf labels (sharpest when using **Minimal Sans** style).
- **macOS right-click:** Supports two-finger tap (`Button-2`), `Control + Click`, and standard right-click (`Button-3`).

### 7. Storage, Updates, First-Run Warnings & License

- **No Login Required:** All features (Calendars, Weather, Styles, Themes, Custom Backgrounds, ESL Export, Updates) work immediately out of the box without any account or login gate.
- **Where personal data is stored:** Your `config.json`, custom backgrounds/icons, and `widget.pid` are stored locally on your machine outside the app binary in `%APPDATA%\desk-widget` (Windows) or `~/Library/Application Support/desk-widget` (macOS).
- **First-run OS warnings & Updates:**
  - **Windows SmartScreen:** Click **More info → Run anyway** on unsigned `.exe`. If Desktop shortcut icons look cached after `App Icon...`, press **`F5`** on the Desktop.
  - **macOS Gatekeeper:** Move `desk-widget.app` to **Applications**, **Right-click → Open** (or **System Settings → Privacy & Security → Open Anyway**, or `xattr -dr com.apple.quarantine /Applications/desk-widget.app`). Note: macOS `.dmg` releases are built on GitHub Actions CI and verified with mocked unit tests rather than hands-on Mac hardware testing.
  - **Auto-start & Updates:** Toggle auto-start in **Settings** (manages Windows Startup `.lnk` or macOS `LaunchAgent`). Clicking **Check for updates** checks GitHub Releases (subject to GitHub's public unauthenticated API rate limit if clicked repeatedly) and opens the matching `.exe`, `apple-silicon.dmg`, or `intel.dmg` link in your browser — it never silently overwrites files without confirmation.
- **License & Copyright:** Open-source under **MIT License** — **`Copyright (c) 2026 hhuuphucc`**. Anyone may use, modify, and redistribute it while keeping the copyright notice and `LICENSE` file.

---

## Tiếng Việt

[English](#english) · **Tiếng Việt** · [Quay lại `README.md`](README.md)

Tổng hợp đầy đủ mọi lưu ý thực tế về định vị IP, múi giờ, thời tiết, lịch `.ics`, giám sát phần cứng real-time, tài khoản/bảo mật và khác biệt trên **Windows / macOS**.

### 1. Khi đi sang tỉnh / thành / bang / nước khác (Bật `Tự động theo IP`)

Khi ô **`Tự động cập nhật vị trí & múi giờ lịch theo mạng IP`** được bật trong **Cài đặt**:

- Khi kết nối Wi-Fi / mạng ở nơi mới — sau khi hết chu kỳ cache mặc định **`15` phút** hoặc khi bạn bấm **`Làm mới ngay`** — widget tự dò lại qua `ipwho.is` (dự phòng `ip-api.com`) để cập nhật:
  - **Tên thành phố / vùng** (`city` / `region`)
  - **Tọa độ `Lat/Lon`** và dự báo thời tiết 7 ngày (qua dữ liệu toàn cầu **Open-Meteo**)
  - **Múi giờ đồng hồ & lịch** (kết hợp `timezone="auto"` từ Open-Meteo và múi giờ trả về từ IP)
- **2 ngoại lệ cần biết (vì định vị bằng IP, máy tính không có GPS):**
  1. **Mạng 4G/5G hoặc nhà mạng tỉnh:** Đôi khi IP được định tuyến qua trạm tổng ở thành phố lớn lân cận, nên widget có thể hiển thị tên thành phố trung tâm thay vì đúng huyện/tỉnh bạn đang đứng.
  2. **Đang bật VPN / Proxy:** Nếu bật VPN sang vùng hoặc nước khác, widget sẽ nhận nhầm vị trí, thời tiết và múi giờ của máy chủ VPN đó.

### 2. Khi muốn cố định bất kỳ thành phố / tỉnh / bang nào trên thế giới

1. Mở **Cài đặt** (nhấn đúp vào khoảng trống trên widget hoặc **Chuột phải → `Cài đặt...`**).
2. **Bỏ tích** `Tự động cập nhật vị trí & múi giờ lịch theo mạng IP` — toàn bộ 5 mục (`Thành phố`, nút `Tìm tọa độ`, `Lat`, `Lon`, `Múi giờ`) sẽ mở khóa hết màu xám để bạn nhập tay.
3. Gõ tên thành phố/bang rồi bấm **`Tìm tọa độ`** (tìm trên dữ liệu toàn cầu của Open-Meteo).
- **Lưu ý nhỏ để dùng chuẩn:**
  - Nếu nơi đó có tên trùng ở nhiều quốc gia (hoặc tên tiếng Việt ít phổ biến), hàm tìm hiện lấy **kết quả phổ biến đầu tiên (`count=1`)**, nên gõ tên quốc tế rõ ràng (ví dụ `San Jose`, `Tokyo`, `Da Lat`, `New York`) hoặc tự điền thẳng cặp số **`Lat/Lon`** sẽ chuẩn nhất.
  - Khi nhập tay thành phố khác múi giờ, nút **`Tìm tọa độ`** chỉ tự điền **`Lat/Lon`**. Nếu muốn đồng hồ & lịch trên widget chạy theo múi giờ của nơi đó, bạn nhập thêm vào ô **`Múi giờ`** (chuẩn IANA, ví dụ `Asia/Ho_Chi_Minh`, `Asia/Tokyo`, `America/New_York`, `Europe/London`).

### 3. Thời tiết & Đổi đơn vị `°C` / `°F`

- Có thể bấm trực tiếp vào **dòng nhiệt độ cạnh chữ `HỆ THỐNG`** trên card để đổi nhanh **`°C` ↔ `°F`** mà không cần mở Cài đặt.
- Thời tiết lấy từ **Open-Meteo** (miễn phí, không cần API key) và cache **`15` phút**. Nếu máy mất mạng, widget báo `Chờ mạng` hoặc giữ bản cache gần nhất nếu có sẵn.

### 4. Google Calendar (`.ics`) & Lịch tháng

- **Nguồn lịch hỗ trợ:** Link iCal bí mật, link `.ics` công khai, link Google Calendar `/embed?src=...` (tự quy đổi sang `/public/basic.ics`), link `webcal://`, hoặc file `.ics` lưu trên máy.
- **Tránh copy dấu che `••••`:** Trong Google Calendar, luôn bấm **biểu tượng con mắt (Hiện)** hoặc nút **Sao chép** ở dòng **Địa chỉ bí mật ở định dạng iCal** — app sẽ cảnh báo nếu link chứa ký tự `•`.
- **Cache & đồng bộ ngay:** Dữ liệu lịch cache mặc định `15` phút; nếu vừa thêm lịch họp mới và muốn hiện ngay, bấm **Chuột phải → `Làm mới ngay`**.
- **Đổi tháng `<` / `>`:** Bấm chuyển tháng trên lưới `HÔM NAY` xử lý tức thì từ cache `.ics` trong RAM (không phải tải lại mạng), hỗ trợ cả lịch lặp (`RRULE`) và sự kiện cả ngày.
- **Nút mở nhanh trong popup sự kiện:** Khi bấm vào ngày hoặc sự kiện bị cắt chữ, app tự nhận diện link `Zoom` (kể cả dòng `Meeting ID: ...` không kèm URL), `Meet`, `Teams`, `Discord`, `Zalo`, `Telegram`, `Messenger`, `Slack`, `Lark`, `Gather`, `Google Docs/Sheets/Slides/Forms/Drive`, `Notion`, `Figma`, `Canva`, `Miro`, `GitHub`, `GitLab`, `YouTube`, `Facebook` và địa chỉ vật lý (tự tạo nút **Mở Maps**).
- **Nhắc nhở & Tự tạo lịch cá nhân:** Hỗ trợ vừa tự nhắc sự kiện `.ics` có giờ cụ thể (`0–240` phút trong **Cài đặt**), vừa tự tạo **Sự kiện / Nhắc lịch cá nhân** cho **bất kỳ ngày nào** (kể cả ngày không có lịch Google) — chọn **Cả ngày** hoặc giờ cụ thể, lặp **Hàng năm / Hàng tháng / Hàng tuần / Hàng ngày / T2–T6 / Tùy chỉnh**, **Thêm vị trí** (tự gắn nút **Mở Maps**) và hẹn báo trước theo **phút / giờ / ngày / tuần** (`lúc HH:MM`). Sự kiện cả ngày từ `.ics` ngoài vẫn được bỏ qua mặc định để tránh báo nhầm nửa đêm.

### 5. Giám sát hệ thống Real-time (`RAM / CPU / GPU & Nhiệt độ`)

- **Chạy nền rất nhẹ:** Cập nhật mỗi `2 giây` chỉ vẽ lại đúng vùng `HỆ THỐNG` (`patch_widget_system_stats`), mức ăn CPU lúc chạy bình thường chỉ khoảng **`~0.1%–0.2%`**.
- **Vì sao bấm popup `CPU` thấy `[Widget]` lên ~10–15%?** Khi bấm thanh `CPU`, app chụp toàn bộ tiến trình đang chạy 2 lần trong `0.8s` để xếp hạng — con số đó chỉ là đỉnh ngắn đúng lúc mở popup, không phải mức ăn nền bình thường.
- **`svchost.exe (N)` và `MemCompression` trên Windows là gì?** Bảng chi tiết gom nhóm các tiến trình trùng tên: `svchost.exe (N)` là nhóm dịch vụ nền chuẩn của Windows (`N` tiến trình), còn `MemCompression` là cơ chế nén RAM của Windows 10/11 giúp giảm ghi đĩa — cả hai đều bình thường, không phải lỗi rò rỉ từ widget.
- **Khác biệt phần cứng GPU & Nhiệt độ:**
  - **Windows dùng card NVIDIA:** Đọc trực tiếp qua `nvml.dll` (không nháy cửa sổ phụ; dự phòng `nvidia-smi`), hiện đủ `% GPU`, `VRAM GB` và nhiệt độ GPU cạnh nhiệt độ CPU.
  - **Windows chỉ dùng card tích hợp Intel / AMD (không có NVIDIA):** GPU `%` và VRAM sẽ giữ `0%` / `0.0/0.0G` (do NVML chỉ hỗ trợ NVIDIA), còn RAM, CPU và nhiệt độ hệ thống vẫn chạy bình thường.
  - **macOS (Apple Silicon M1–M4 & Intel):** Đọc GPU qua `ioreg IOAccelerator` có giới hạn nhịp đọc nhẹ (chip Apple Silicon dùng Unified Memory nên không tách riêng dung lượng VRAM kiểu `GB`). Nhiệt độ CPU cần cài thêm công cụ không `sudo` như `brew install smctemp` hoặc `brew install osx-cpu-temp` nếu `IOHWSensor` bị hệ điều hành ẩn.

### 6. Thao tác cửa sổ, Chống trùng & Xuất ảnh ESL

- **Chế độ đơn tiến trình (`widget.pid`):** Mở lại widget lần nữa sẽ tự đóng tiến trình cũ đang chạy để tránh 2 widget đè lên nhau.
- **Nổi / Ẩn cửa sổ (`Luôn nổi trên cùng` / `Ẩn ra sau ngay`):** Trên Windows, khi mở app toàn màn hình (xem phim, chơi game, trình chiếu) hoặc bấm `Ẩn ra sau ngay`, widget sẽ lùi gọn xuống nền Desktop; trên macOS app bật/tắt `-topmost` và `lower()` theo quy tắc cửa sổ Cocoa.
- **Xuất ảnh E-Ink 3 màu (`296×128 PNG/BMP`):** Chuyển card hiện tại thành ảnh 3 màu Đen/Trắng/Đỏ đúng chuẩn màn hình ESL `2.9"` (`296×128`) — hiển thị sắc nét nhất khi dùng phong cách **Minimal Sans**.
- **Chuột phải trên macOS:** Hỗ trợ chạm 2 ngón (`Button-2`), `Control + Click` và chuột phải thường (`Button-3`).

### 7. Lưu trữ, Bản quyền, Cảnh báo hệ điều hành & Cập nhật

- **Không cần đăng nhập:** Toàn bộ tính năng (thêm lịch `.ics`, thời tiết, giao diện, đổi nền/logo/icon, xuất ảnh ESL, cập nhật) mở sẵn cho mọi người tải về dùng và tùy biến ngay lập tức.
- **Nơi lưu dữ liệu cá nhân:** Cấu hình (`config.json`), ảnh nền/icon tùy chỉnh và `widget.pid` lưu hoàn toàn trên máy bạn (tách biệt ngoài file chạy) tại `%APPDATA%\desk-widget` (Windows) hoặc `~/Library/Application Support/desk-widget` (macOS).
- **Cảnh báo lần đầu, Tự khởi động & Kiểm tra cập nhật:**
  - **Windows SmartScreen:** Bấm **More info → Run anyway** ở lần mở `.exe` đầu tiên. Sau khi đổi icon app (`Đổi icon app...`), nếu icon ngoài Desktop chưa đổi ngay thì nhấn **`F5`** ngoài Desktop.
  - **macOS Gatekeeper:** Kéo `desk-widget.app` vào **Applications**, nhấn **Chuột phải → Open** *(hoặc **System Settings → Privacy & Security → Open Anyway**, hay chạy `xattr -dr com.apple.quarantine /Applications/desk-widget.app`)*. *(Bản `.dmg` được GitHub Actions tự build và kiểm tra qua unit test giả lập, chưa test GUI trực tiếp trên máy Mac thật.)*
  - **Tự khởi động:** Bật/tắt trong **Cài đặt** (quản lý shortcut Startup `.lnk` trên Windows hoặc `LaunchAgent` trên macOS).
  - **Kiểm tra cập nhật:** Quét GitHub Releases (có thể chạm giới hạn request/giờ của GitHub API công khai nếu bấm liên tục nhiều chục lần) rồi mở đúng link tải `.exe`, `apple-silicon.dmg` hoặc `intel.dmg` trên trình duyệt — không tự ý tải/ghi đè âm thầm.
- **Bản quyền (`MIT License`):** Giữ dòng **`Copyright (c) 2026 hhuuphucc`** và file `LICENSE` khi sửa đổi hoặc phân phối lại.
