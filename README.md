# Desk Widget

**English** · [Tiếng Việt](#tiếng-việt) · [Important Notes (`INFO.md`)](INFO.md) · *"A small, open-source passion project built for fun and non-commercial use."*

> ### Download & Run — No Git or Python Required / Tải về chạy ngay (Không cần Git hay Python)
> - **All Releases:** [**GitHub Releases (Latest)**](https://github.com/hhuuphucc/Desk-Widget/releases/latest)
> - **Windows 10/11 (`.exe`):** [**Download `desk-widget-windows-x64.exe`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-windows-x64.exe) *(First run SmartScreen: **More info → Run anyway**)*
> - **macOS Apple Silicon M1–M4 (`.dmg`):** [**Download `desk-widget-macos-apple-silicon.dmg`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-macos-apple-silicon.dmg) *(First run: drag to Applications, **Right-click → Open**)*
> - **macOS Intel (`.dmg`):** [**Download `desk-widget-macos-intel.dmg`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-macos-intel.dmg) *(First run: drag to Applications, **Right-click → Open**)*
> - **Uninstall Commands (Win / macOS):** [**Download `UNINSTALL.txt`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/UNINSTALL.txt) *(or see [Complete Uninstall](#complete-uninstall-remove-100-of-app-downloaded-files--local-data))*
> - **Notes & Troubleshooting:** Read [**`INFO.md`**](INFO.md) for IP geolocation/VPN exceptions, manual `City` / `Lat/Lon` / `Timezone` tips, real-time CPU popup details, and Windows/macOS first-launch notes.

---

## English

A lightweight, cross-platform E-Ink-inspired desktop widget for **Windows** and **macOS (Apple Silicon M1/M2/M3/M4 & Intel)** built with Python (`Tkinter` + `Pillow`). Refreshes in the background every **60 seconds**, automatically syncs location, weather, and calendar timezone via IP, and supports **English / Vietnamese** and **`°C` / `°F`**.

### Key Features

- **6 Visual Styles & Auto Light/Dark Themes (Instant In-Place Preview):**
  - **macOS (`macos`):** Clean Apple-style rounded Bento glass cards.
  - **Pixel (`pixel`):** Soft pastel Material 3 Bento cards.
  - **Xiaomi HyperOS (`xiaomi`):** Crisp HyperOS glass layout.
  - **Ocean Calm / Mist Blue (`botanical`):** Soothing mist-blue soft paper palette with clean column spacing and circular logo / background support.
  - **Paper Serif (`serif`):** Textured cold-pressed paper card with `Palatino Linotype Bold` headings + `Segoe UI` body text (automatically maps to `Georgia Bold` + `Arial`/`SFNS` on macOS).
  - **Sans E-Ink (`sans`):** Minimal high-contrast 3-color E-Ink style (`Segoe UI`, Black / White / Red).
  - **Theme Modes:** `auto` (automatically switches Light/Dark based on local sunrise & sunset at your configured location and timezone, including seasonal DST changes), `system` (follow Windows/macOS Light or Dark appearance automatically), `light`, or `dark`. Switching style or theme updates **both the desktop widget and the Settings window immediately in-place** without flickering or reopening.
- **Multi-Source Google Calendar & 1-Month Grid:**
  - Manage multiple independent `.ics` calendars with custom labels (secret/public `.ics` URLs, Google Calendar `/embed?src=...` links, `webcal://`, or local `.ics` files).
  - Automatically updates calendar & header clock timezone based on IP location when travelling abroad (when IP geolocation is enabled), with automatic seasonal Daylight Saving Time (DST) handling for regions like Europe/US.
  - Interactive **1-month calendar grid** right below `TODAY` (optically centered dates & buttons, `<` / `>` month navigation, and an automatic `Today` button when viewing another month).
  - Click any date or truncated event row to open a detailed popup with **1-click launch buttons** for `Zoom`, `Discord`, `Google Meet`, `Teams`, `Zalo`, `Telegram`, `Messenger`, `Slack`, `Google Docs/Sheets/Slides/Drive`, `Notion`, `Figma`, `GitHub`, `YouTube`, `Google Maps`, and more.
  - **Customizable Event Reminders & Personal Events:** Create custom reminders on **any date** (no Google Calendar link required) with **All-day / Timed**, **Yearly / Monthly / Weekly / Weekdays / Daily / Custom** recurrence, **Location** (+ 1-click **Open Maps**), and flexible alerts (**minutes / hours / days / weeks** before, at custom `HH:MM`, plus **Snooze 5m**). Also notifies before upcoming Google Calendar `.ics` timed events (`0–240` min customizable in **Settings**).
- **7-Day Weather Forecast (`Mon → Sun`) via Open-Meteo:**
  - Auto-detects location & timezone via IP or allows manual city lookup / coordinates / timezone.
  - Instant **`°C` ↔ `°F`** switching (click the temperature next to `SYSTEM`, use the right-click menu, or change it in **Settings**).
  - Click any `Mon..Sun` tile for daily min–max temperature, rain probability, precipitation, wind speed, UV index, and hourly slots.
- **Real-Time System & Hardware Monitor (`RAM / CPU / GPU & Temperature`, 2s refresh):**
  - Displays RAM (`GB` & `%`), CPU (`%`), GPU (Windows zero-subprocess `nvml.dll` with `nvidia-smi` fallback; macOS Intel & Apple Silicon M1–M4 via throttled `ioreg IOAccelerator`), and machine temperature next to `SYSTEM`.
  - Uses ultra-lightweight partial region repainting (`patch_widget_system_stats`, updating only the `SYSTEM` quadrant when values change) so real-time 2-second monitoring keeps idle CPU overhead near zero (`~0.1%`).
  - Click the `RAM`, `CPU`, or `GPU` bars to inspect top resource-consuming processes.
- **Bilingual UI, Custom Background & Header Logo:**
  - Switch UI language between **English** and **Tiếng Việt** anytime.
  - **5-tab Sidebar Settings (`Appearance`, `Title, Logo & Bg`, `Calendars`, `Weather & System`, `About`)** with DPI-aware scaling, scrollable **34-zone world timezone selector**, and clickable **`(i)` info popovers** for quick feature hints.
  - **Custom Background (`Default per style` / `Custom background`):** Drag-to-pan & `−/+` zoom framing on a live widget preview, **Original / Negative** tone toggle, PNG preset placement, and **Background Strength (`15%–100%`, default `55%`)** with an automatic translucent readability layer behind text so info stays sharp even on vivid wallpapers.
  - **Header Logo:** Choose **Default**, **Custom circle** (auto-cropped circular icon), or **Hidden** (`Hide icon`), with selectable placement on the title bar.

---

### Requirements

- **Windows:** Windows 10 / Windows 11, Python 3.10+ (check **Add Python to PATH** during installation).
- **macOS:** macOS (**Apple Silicon M1/M2/M3/M4** & **Intel**), Python 3.10+ with Tkinter (`brew install python python-tk` or [python.org](https://www.python.org/downloads/macos/)).
- **Dependencies:** Listed in [requirements.txt](requirements.txt) (`Pillow`, `requests`, `python-dateutil`, `psutil`).

---

### Installation & Launch

#### Option A: Standalone App (Download & Run — No Python Required)
- Download the pre-built release from [**GitHub Releases**](https://github.com/hhuuphucc/Desk-Widget/releases/latest) (built automatically via [`.github/workflows/release.yml`](.github/workflows/release.yml) for `Windows x64 (.exe)`, `macOS Apple Silicon (.dmg)`, and `macOS Intel (.dmg)`):
  - **Windows:** Double-click `desk-widget-windows-x64.exe`.
    - *First-run notice:* Since the app is not commercially code-signed yet, **Windows SmartScreen** may appear — click **More info → Run anyway**.
  - **macOS:** Open the matching `.dmg` (`apple-silicon` for M1/M2/M3/M4, or `intel` for Intel Macs) and drag `desk-widget.app` to **Applications**.
    - *First-run notice:* On an unsigned app, **Right-click → Open** *(on macOS Sonoma/Sequoia, if Gatekeeper still blocks it, go to **System Settings → Privacy & Security → Open Anyway**, or run `xattr -dr com.apple.quarantine /Applications/desk-widget.app`)*.
    - *macOS status:* Built automatically via GitHub Actions and covered by mocked unit tests; GUI rendering on physical Mac hardware has not been verified hands-on yet—feel free to open an issue if anything looks off.
- Or package it yourself on your machine:
  ```bash
  pip install -r requirements.txt pyinstaller
  python build_app.py --public
  ```
  Outputs `dist/desk-widget.exe` on Windows or `dist/desk-widget-macos-<arch>.dmg` on macOS. Personal configs and custom logos are saved automatically in `%APPDATA%\desk-widget` (Windows) or `~/Library/Application Support/desk-widget` (macOS).

#### Option B: Run from Source (Windows)
```powershell
git clone https://github.com/hhuuphucc/Desk-Widget.git desk-widget
cd desk-widget
pip install -r requirements.txt
copy config.example.json config.json
```
- **Background launch (recommended, no console window):** Double-click `start_widget.vbs`.
- **Console launch (with logs):** Double-click `run_widget.bat` or run `python widget.py`.

#### On macOS (Apple Silicon & Intel)
```bash
git clone https://github.com/hhuuphucc/Desk-Widget.git desk-widget
cd desk-widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
chmod +x start_mac.command
```
- **Background launch:** Double-click `start_mac.command` in Finder or run `./start_mac.command` in Terminal.
- **Console launch:** `python3 widget.py`.
- *(Optional CPU temperature on macOS):* macOS restricts unprivileged hardware thermal sensors by default; install a non-sudo helper such as `brew install smctemp` (Apple Silicon & Intel) or `brew install osx-cpu-temp` (Intel) to show CPU temperature next to `SYSTEM`.
- *(macOS right-click):* Supports two-finger click (`Button-2`), `Control + Click`, and standard right-click (`Button-3`).

*(Single-instance mode: launching the widget again automatically replaces any older running instance.)*

---

### Setup & Customization

Double-click any empty area on the widget (or **Right-click → `Settings...`**):

1. **Header Title & Alignment:** Set any display title and align **Left / Center / Right**.
2. **Add Google Calendar Links:**
   - Open [Google Calendar](https://calendar.google.com) → **Settings** → pick your calendar → scroll to **Integrate calendar**.
   - Click the eye icon or Copy button on **Secret address in iCal format** (avoid selecting masked `••••` bullets).
   - Click **`+ Add calendar`** in widget Settings, enter a name and URL, then click **Save & Refresh**.
3. **Weather & Timezone:** Auto-location & IP timezone sync is enabled by default; uncheck it to unlock `City`, `Find coordinates` (press `Enter` or click to automatically resolve city coordinates & timezone), `Lat/Lon`, and the scrollable **34-zone world timezone** picker. *(See [`INFO.md`](INFO.md#1-travelling-anywhere-in-the-world-auto-detect-via-ip) for IP/VPN caveats and manual coordinate/timezone tips.)*
4. **In Settings vs Right-Click Menu:**
   - **Inside Settings (`5` Tabs):** Change **Visual style** (`macOS` / `Pixel` / `Xiaomi HyperOS` / `Ocean Calm` / `Paper Serif` / `Sans`), **Theme** (`auto` / `system` / `light` / `dark`), **Scale**, **Temperature unit** (`°C` / `°F`), **Language**, **Title & Alignment**, **Header Logo & Background** (with live framing, Negative tone & Strength `%`), **Calendars & Custom Reminders**, **Auto-start**, **Always on top** / **Send behind**, **App Icon**, and **About** links. *(Fresh clones start with a clean neutral card for personal customization.)*
   - **Streamlined Right-Click Menu:** `Refresh now`, `Settings...`, `Check for updates (v1.2.0)...` (automatically picks Windows `.exe`, macOS Apple Silicon `.dmg`, or macOS Intel `.dmg`), and `Quit`.

### Quick Interactions

| Action | Behavior |
|---|---|
| **Drag & Drop** | Reposition widget anywhere on screen (auto-saved) |
| **Click calendar day (`Mon..Sun`)** | Open day details popup with 1-click meeting/link buttons |
| **Click `TODAY` / `Upcoming` event row** | View full event title and details when truncated |
| **Click colored pill (`Open Zoom`, `Open Meet`...)** | Launch meeting link or document directly |
| **Click weather day (`Mon..Sun`)** | Open detailed weather & hourly breakdown popup |
| **Click temperature next to `SYSTEM`** | Toggle `°C` ↔ `°F` immediately |
| **Click `RAM` / `CPU` / `GPU` bars** | Inspect top applications using that resource |
| **Press `Esc`** | Close active popup |
| **Double-click** (empty space) | Open Settings |
| **Right-click** | Open quick context menu |

### Project Structure

```text
desk-widget/
├── INFO.md             # User guide & caveats (IP geolocation, Lat/Lon, CPU popup, Win/macOS tips)
├── widget.py           # Tkinter UI, interactions, 5-tab Settings, reminders & auto-start
├── modern_ui.py        # Material-inspired anti-aliased controls, scrollable dropdowns, (i) popovers & live retheming
├── renderer.py         # Pillow HiDPI renderer (6 Light/Dark styles, custom bg framing, tone & frosted scrim)
├── calendar_client.py  # .ics / embed URL fetcher, parser & meeting-link detector
├── weather_client.py   # Open-Meteo 7-day weather & IP geolocation/timezone client
├── system_client.py    # Windows & macOS (Apple Silicon/Intel) RAM/CPU/GPU/temp monitor
├── updater.py          # App copyright metadata, GitHub Releases checker & OS asset selector
├── build_app.py        # PyInstaller standalone packaging script (.exe / .dmg)
├── config.example.json # Public config template (personal config.json is gitignored)
├── requirements.txt    # Python package dependencies
├── start_widget.vbs    # Silent background launcher for Windows
├── run_widget.bat      # Console launcher for Windows debugging
├── start_mac.command   # Background launcher for macOS (Apple Silicon & Intel)
├── UNINSTALL.txt       # Copy-paste uninstall commands for Windows (PS/CMD) & macOS
├── test_widget.py      # Automated unit tests
└── assets/             # Optional local visual assets (personal images are gitignored)
```

### Complete Uninstall (Remove 100% of App, Downloaded Files & Local Data)

`desk-widget` does not modify the Windows Registry or install background system services. You can also download [`UNINSTALL.txt`](UNINSTALL.txt) directly from the [GitHub Releases](https://github.com/hhuuphucc/Desk-Widget/releases/latest) assets. To remove it completely:

1. **Quit & Turn off Auto-Start:** Right-click the widget → **Settings...** → uncheck **Auto-start** → **Save**, then Right-click → **Quit** *(or run the commands below directly even if the app is still running)*.
2. **Windows (`.exe` or Source):**
   - Run in **PowerShell** (`Win + X → Terminal`) to stop the app, remove Startup/Desktop shortcuts, `%APPDATA%\desk-widget` (`config.json`, custom images/icons, `widget.pid`), and downloaded `desk-widget*.exe` files (additionally delete your cloned `desk-widget` folder if running from source):
     ```powershell
     Get-Process desk-widget -ErrorAction SilentlyContinue | Stop-Process -Force
     Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*widget.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
     Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\desk-widget.lnk" -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'desk-widget.lnk') -Force -ErrorAction SilentlyContinue
     Remove-Item "$env:APPDATA\desk-widget" -Recurse -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path $HOME 'Downloads\desk-widget*.exe') -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'desk-widget*.exe') -Force -ErrorAction SilentlyContinue
     ```
   - Or in **Command Prompt (`cmd.exe`)** — see [`UNINSTALL.txt`](UNINSTALL.txt).
3. **macOS (`.app` / `.dmg` or Source):**
   - Run in **Terminal** (`Cmd + Space → Terminal`) to stop the app, unload `LaunchAgent`, delete `/Applications/desk-widget.app`, downloaded `desk-widget*.dmg` files, and `~/Library/Application Support/desk-widget` *(plus your cloned folder if running from source)*:
     ```bash
     pkill -f desk-widget || true
     pkill -f "widget.py" || true
     launchctl unload "$HOME/Library/LaunchAgents/com.deskwidget.app.plist" 2>/dev/null || true
     rm -f "$HOME/Library/LaunchAgents/com.deskwidget.app.plist"
     rm -rf /Applications/desk-widget.app "$HOME/Applications/desk-widget.app" "$HOME/Library/Application Support/desk-widget"
     rm -f "$HOME/Downloads"/desk-widget*.dmg "$HOME/Desktop"/desk-widget*.dmg
     ```

### Unit Tests

```bash
python test_widget.py -v
```

---

## Tiếng Việt

[English](#english) · **Tiếng Việt** · [Lưu ý & Hướng dẫn chi tiết (`INFO.md`)](INFO.md#tiếng-việt)

> **Tải về chạy ngay (Không cần cài Git hay Python):**
> - **Trang phát hành:** [**GitHub Releases (Bản mới nhất)**](https://github.com/hhuuphucc/Desk-Widget/releases/latest)
> - **Windows 10/11 (`.exe`):** [**Tải `desk-widget-windows-x64.exe`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-windows-x64.exe) *(Lần đầu nếu SmartScreen hỏi: **More info → Run anyway**)*
> - **macOS Apple Silicon M1–M4 (`.dmg`):** [**Tải `desk-widget-macos-apple-silicon.dmg`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-macos-apple-silicon.dmg) *(Kéo vào Applications, **Chuột phải → Open**)*
> - **macOS Intel (`.dmg`):** [**Tải `desk-widget-macos-intel.dmg`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/desk-widget-macos-intel.dmg) *(Kéo vào Applications, **Chuột phải → Open**)*
> - **Lệnh gỡ cài đặt sạch (Win / macOS):** [**Tải `UNINSTALL.txt`**](https://github.com/hhuuphucc/Desk-Widget/releases/latest/download/UNINSTALL.txt) *(hoặc xem mục [Gỡ bỏ hoàn toàn](#gỡ-bỏ-hoàn-toàn-ứng-dụng-xóa-sạch-app-đã-tải--dữ-liệu-khi-không-dùng-nữa))*
> - **Lưu ý quan trọng khi dùng:** Xem file [**`INFO.md`**](INFO.md#tiếng-việt) để biết chi tiết về định vị IP / VPN, tự nhập `Thành phố` / `Lat/Lon` / `Múi giờ`, giải thích chỉ số CPU khi bấm xem chi tiết và lưu ý Windows/macOS.

Widget để bàn nhỏ gọn đa nền tảng cho **Windows** và **macOS (Apple Silicon M1/M2/M3/M4 & Intel)** (`Tkinter` + `Pillow`), hỗ trợ **6 phong cách giao diện Light/Dark đồng bộ** (`macOS`, `Pixel`, `Xiaomi HyperOS`, `Ocean Calm / Mist Blue`, `Paper Serif`, `Sans`). Tự động làm mới mỗi **60 giây** ở luồng nền, tự đồng bộ múi giờ theo IP và hỗ trợ **Tiếng Việt / English** cùng **`°C` / `°F`**.

### Tính năng chính

- **6 phong cách giao diện & chế độ Sáng/Tối (Đổi màu trực tiếp tức thì):**
  - **macOS (`macos`):** Thẻ kính bo tròn gọn gàng kiểu Apple Bento.
  - **Pixel (`pixel`):** Thẻ Bento đa sắc nhẹ theo Material 3.
  - **Xiaomi HyperOS (`xiaomi`):** Thẻ kính sắc nét phong cách HyperOS.
  - **Ocean Calm / Mist Blue (`botanical`):** Tông xanh dương dịu mắt trên nền giấy mịn, bỏ chia dọc rối mắt và hỗ trợ ảnh nền / logo tròn.
  - **Paper Serif (`serif`):** Nền giấy vân mịn, tiêu đề font có chân `Palatino Linotype Bold` + nội dung `Segoe UI` rõ nét (trên macOS tự chuyển sang `Georgia Bold` + `Arial`/`SFNS` hỗ trợ đầy đủ tiếng Việt).
  - **Sans E-Ink (`sans`):** Giao diện tối giản tương phản cao 3 màu (Đen – Trắng – Đỏ).
  - **Chế độ màu:** `auto` (tự động đổi Sáng/Tối theo giờ mặt trời mọc/lặn tại vị trí & múi giờ cài đặt, tự theo mùa & giờ mùa hè/đông), `system` (theo giao diện Windows/macOS), `light`, hoặc `dark`. Khi bấm chọn Style hoặc Sáng/Tối, **cả widget lẫn cửa sổ Cài đặt đổi màu ngay tại chỗ** mà không bị tắt/mở lại cửa sổ.
- **Google Calendar đa nguồn & Lịch 1 tháng:**
  - Quản lý nhiều lịch độc lập kèm **tên lịch riêng** (hỗ trợ link `.ics` bí mật, `.ics` công khai, link Google Calendar `/embed?src=...`, `webcal://`, hoặc file `.ics` trên máy).
  - Tự động cập nhật múi giờ lịch & đồng hồ theo vị trí IP khi đi nước ngoài (nếu bật định vị IP), đồng thời tự chuyển theo quy ước đổi giờ mùa hè/mùa đông (DST) ở châu Âu/Mỹ.
  - Lưới **lịch 1 tháng** ngay trong khung `HÔM NAY` (căn giữa đều chữ & số, nút `<` / `>` đổi tháng thẳng hàng, tự hiện nút `Hôm nay` khi chuyển sang tháng khác).
  - Bấm vào ô ngày hoặc dòng sự kiện rút gọn để mở popup chi tiết đầy đủ kèm **nút mở thẳng 1-click** cho nhiều ứng dụng (`Zoom`, `Discord`, `Google Meet`, `Teams`, `Zalo`, `Telegram`, `Messenger`, `Slack`, `Google Docs/Sheets/Slides/Drive`, `Notion`, `Figma`, `GitHub`, `YouTube`, `Google Maps`...).
  - **Nhắc nhở sự kiện & Tạo lịch cá nhân:** Tự tạo sự kiện/lời nhắc cho **bất kỳ ngày nào** (không cần có sẵn sự kiện Google Calendar) với tùy chọn **Cả ngày / Theo giờ**, lặp lại **Không lặp / Hàng ngày / Hàng tuần / Hàng tháng / Hàng năm / T2–T6 / Tùy chỉnh**, **Thêm vị trí** (kèm nút **Mở Maps**), và hẹn báo trước theo **phút / giờ / ngày / tuần** (`lúc HH:MM`, có **Nhắc lại sau 5 phút**). Đồng thời tự nhắc trước sự kiện `.ics` trong ngày (`0–240` phút trong **Cài đặt**).
- **Thời tiết 7 ngày (`T2 → CN`) qua Open-Meteo:**
  - Tự động xác định vị trí & múi giờ theo mạng (IP) hoặc cho phép nhập tay tên thành phố / tọa độ / múi giờ.
  - Hỗ trợ chuyển đổi đơn vị nhiệt độ **`°C` ↔ `°F`** (nhấn trực tiếp vào dòng nhiệt độ cạnh `HỆ THỐNG`, chọn trong menu chuột phải, hoặc chỉnh trong **Cài đặt**).
  - Bấm vào từng ngày `T2..CN` để xem nhiệt độ min–max, % mưa, lượng mưa, gió, UV và dự báo theo khung giờ.
- **Giám sát hệ thống Real-time mỗi `2 giây` (RAM / CPU / GPU & Nhiệt độ máy):**
  - Hiển thị mức sử dụng RAM (`GB` & `%`), CPU (`%`), GPU (Windows đọc trực tiếp qua `nvml.dll` không mở tiến trình phụ, fallback `nvidia-smi`; macOS Intel & Apple Silicon M1–M4 qua `ioreg IOAccelerator` giới hạn chu kỳ nhẹ) và nhiệt độ máy cạnh chữ `HỆ THỐNG`.
  - Tối ưu chỉ vẽ lại đúng vùng `SYSTEM` khi thông số thay đổi (`patch_widget_system_stats`), nên chạy real-time vẫn cực nhẹ (`~0.1%` CPU trên Windows).
  - Bấm trực tiếp vào từng thanh `RAM`, `CPU`, hoặc `GPU` để xem danh sách ứng dụng đang sử dụng nhiều nhất *(cửa sổ đo CPU tự loại trừ chi phí quét `psutil` của chính widget để giữ số liệu sát thực tế)*.
- **Cài đặt 5 tab hiện đại, Cá nhân hóa ảnh nền & Nút `(i)` giải thích nhanh:**
  - Giao diện **Cài đặt 5 tab** (`Giao diện`, `Tiêu đề, Logo & Nền`, `Lịch & Nhắc nhở`, `Thời tiết & Hệ thống`, `Giới thiệu`) tự co giãn theo DPI Windows/macOS, cuộn chuột mượt trên cả Windows & macOS, kèm các nút tròn **`(i)`** giải thích nhanh ngay tại từng mục.
  - **Ảnh nền cá nhân (`Mặc định theo Style` / `Cá nhân hóa ảnh nền`):** Kéo/thu phóng căn khung trực tiếp `384×179`, chọn tông **Ảnh gốc / Âm bản**, chỉnh **Độ rõ nền (`15%–100%`, mặc định `55%`)** kèm lớp nền mờ tự động bảo vệ chữ luôn rõ ràng trên nền đậm.
  - **Logo thanh tiêu đề:** Hỗ trợ `Mặc định`, `Ảnh riêng` (tự cắt tròn) hoặc `Ẩn icon` kèm tùy chọn vị trí.

### Yêu cầu hệ thống

- **Windows:** Windows 10 / Windows 11, Python 3.10+ (khi cài nhớ tích **Add Python to PATH**).
- **macOS:** macOS (cả **Apple Silicon M1/M2/M3/M4** và **Intel**), Python 3.10+ có sẵn Tkinter (`brew install python python-tk` hoặc bộ cài từ [python.org](https://www.python.org/downloads/macos/)).
- **Thư viện Python:** Xem trong [requirements.txt](requirements.txt) (`Pillow`, `requests`, `python-dateutil`, `psutil`).

### Hướng dẫn cài đặt & khởi chạy

#### Cách 1: Chạy trực tiếp bản đóng gói sẵn (Không cần cài Python)
- Tải file ứng dụng dựng sẵn tại trang [**GitHub Releases**](https://github.com/hhuuphucc/Desk-Widget/releases/latest) (tự động build qua [`.github/workflows/release.yml`](.github/workflows/release.yml) cho đủ cả **Windows `.exe`**, **macOS chip M `.dmg`** và **macOS Intel `.dmg`**):
  - **Windows:** Nhấn đúp `desk-widget-windows-x64.exe`.
    - *Lưu ý lần đầu mở:* Do ứng dụng chưa mua chứng chỉ ký số thương mại, **Windows SmartScreen** có thể hiện cảnh báo — bấm **More info → Run anyway** để chạy.
  - **macOS:** Mở đúng file `.dmg` theo chip máy (`apple-silicon` cho chip M1/M2/M3/M4, hoặc `intel` cho máy Intel) và kéo `desk-widget.app` vào thư mục **Applications**.
    - *Lưu ý lần đầu mở:* Với app chưa ký số, nhấn **Chuột phải → Open** *(trên macOS Sonoma/Sequoia nếu vẫn bị Gatekeeper chặn, vào **System Settings → Privacy & Security → Open Anyway**, hoặc chạy lệnh `xattr -dr com.apple.quarantine /Applications/desk-widget.app`)*.
    - *Lưu ý tương thích macOS:* Bản macOS `.dmg` hiện được build tự động trên GitHub Actions và kiểm tra bằng unit test giả lập (chưa mở GUI trực tiếp trên máy Mac thật); nếu gặp lỗi hiển thị trên Mac, hãy tạo Issue để được hỗ trợ.
- Hoặc tự đóng gói trên máy của bạn:
  ```bash
  pip install -r requirements.txt pyinstaller
  python build_app.py --public
  ```
  File thành phẩm nằm trong thư mục `dist/`. Cấu hình và ảnh tùy biến cá nhân được tự động lưu riêng trong `%APPDATA%\desk-widget` (Windows) hoặc `~/Library/Application Support/desk-widget` (macOS).

#### Cách 2: Chạy từ mã nguồn trên Windows
```powershell
git clone https://github.com/hhuuphucc/Desk-Widget.git desk-widget
cd desk-widget
pip install -r requirements.txt
copy config.example.json config.json
```
- **Chạy ngầm (khuyên dùng, không hiện cửa sổ đen):** Nhấn đúp file `start_widget.vbs`.
- **Chạy kèm cửa sổ log để kiểm tra lỗi:** Nhấn đúp file `run_widget.bat` hoặc chạy `python widget.py`.

#### Trên macOS (Apple Silicon M-series & Intel)
```bash
git clone https://github.com/hhuuphucc/Desk-Widget.git desk-widget
cd desk-widget
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
chmod +x start_mac.command
```
- **Chạy ngầm:** Nhấn đúp `start_mac.command` trong Finder hoặc chạy `./start_mac.command` trong Terminal.
- **Chạy kèm log:** `python3 widget.py`.
- *(Tùy chọn đọc nhiệt độ CPU trên macOS, đặc biệt chip M):* macOS mặc định khóa đọc cảm biến nhiệt ở chế độ không quyền admin; nếu muốn hiện nhiệt độ chip cạnh `HỆ THỐNG`, bạn có thể cài thêm công cụ không cần `sudo` như `brew install smctemp` (hỗ trợ cả Apple Silicon & Intel) hoặc `brew install osx-cpu-temp` (Intel).
- *(Lưu ý chuột phải trên Mac):* Hỗ trợ chạm 2 ngón (`Button-2`), `Control + Click`, hoặc chuột phải thông thường (`Button-3`).

*(Widget chạy chế độ đơn tiến trình: mỗi lần mở lại sẽ tự đóng bản cũ để tránh chạy trùng.)*

### Hướng dẫn kết nối Google Calendar & Tùy chỉnh

Nhấn đúp vào khoảng trống trên widget (hoặc **chuột phải → `Cài đặt...`**) để mở bảng cấu hình:

1. **Tên trên thanh tiêu đề & Vị trí:**
   - Nhập tên hiển thị bất kỳ và chọn căn **Trái / Giữa / Phải**.
2. **Thêm link Google Calendar:**
   - Mở [Google Calendar](https://calendar.google.com) → biểu tượng bánh răng **Cài đặt** → chọn lịch ở cột trái → kéo xuống mục **Tích hợp lịch**.
   - Bấm **biểu tượng con mắt (Hiện)** hoặc nút **Sao chép** ở dòng **Địa chỉ bí mật ở định dạng iCal** (tránh bôi đen trực tiếp nếu Google đang che bằng dấu `••••`).
   - Trong phần **Danh sách lịch** của widget, bấm **`+ Thêm link lịch`**, đặt **Tên lịch** (ví dụ `Cá nhân`, `Công việc`), dán link vào rồi bấm **Lưu & Cập nhật**.
3. **Thời tiết & Tọa độ:**
   - Mặc định bật **Tự động lấy vị trí & múi giờ theo IP**. Nếu muốn cố định thành phố khác, **bỏ tích** để mở khóa `Thành phố`, `Tìm tọa độ` (nhấn `Enter` hoặc bấm nút sẽ tự điền cả `Vĩ độ`, `Kinh độ` và tự đổi `Múi giờ` theo thành phố đó), và danh sách cuộn **34 múi giờ thế giới**. *(Xem thêm các ngoại lệ mạng 4G/VPN & mẹo tìm tọa độ chuẩn tại [`INFO.md`](INFO.md#1-khi-đi-sang-tỉnh--thành--bang--nước-khác-bật-tự-động-theo-ip).)*
4. **Cài đặt giao diện & Menu chuột phải:**
   - **Trong Cài đặt (5 tab):** Đổi `Phong cách` (**macOS / Pixel / Xiaomi HyperOS / Ocean Calm / Paper Serif / Sans**), `Chế độ sáng/tối` (`auto / system / light / dark`), `Cỡ widget`, `Độ C / Độ F`, `Ngôn ngữ`, `Tiêu đề & Căn lề`, `Logo & Nền Widget` (căn khung, Âm bản, Độ rõ nền), `Lịch & Nhắc nhở`, `Tự khởi động`, `Luôn nổi trên cùng` / `Ẩn ra sau ngay`, `Đổi icon app...`, và tab `Giới thiệu`. *(Bản clone mới giữ giao diện trung tính gọn gàng để bạn tự cá nhân hóa.)*
   - **Menu chuột phải gọn nhẹ:** `Làm mới ngay`, `Cài đặt...`, `Kiểm tra cập nhật (v1.2.0)...` (tự chọn đúng bản `Windows .exe`, `macOS Apple Silicon .dmg` hoặc `macOS Intel .dmg`) và `Thoát`.

### Thao tác nhanh trên Widget

| Thao tác | Chức năng |
|---|---|
| **Kéo thả** | Di chuyển vị trí widget trên màn hình (tự lưu tọa độ) |
| **Click ô ngày (`T2..CN` lịch)** | Mở popup chi tiết sự kiện & nút mở nhanh app của ngày đó |
| **Click dòng sự kiện `HÔM NAY` / `Sắp tới`** | Xem tên đầy đủ & chi tiết khi tiêu đề bị rút gọn `...` |
| **Click nút màu (`Mở Zoom`, `Mở Discord`...)** | Mở thẳng link họp / tài liệu bằng trình duyệt hoặc app mặc định |
| **Click ô thời tiết (`T2..CN`)** | Xem chi tiết thời tiết & khung giờ trong ngày |
| **Click dòng nhiệt độ cạnh `HỆ THỐNG`** | Đổi nhanh đơn vị `°C` ↔ `°F` |
| **Click thanh `RAM` / `CPU` / `GPU`** | Xem top ứng dụng đang sử dụng tài nguyên |
| **Nhấn `Esc`** | Đóng nhanh cửa sổ popup đang mở |
| **Nhấn đúp** (vùng trống) | Mở bảng Cài đặt |
| **Chuột phải** | Mở menu tùy chỉnh nhanh |

### Gỡ bỏ hoàn toàn ứng dụng (Xóa sạch app đã tải & dữ liệu khi không dùng nữa)

`desk-widget` **không ghi vào Windows Registry** và không cài dịch vụ nền hệ thống. Bạn cũng có thể tải nhanh file [`UNINSTALL.txt`](UNINSTALL.txt) ngay trong mục Assets trên trang [GitHub Releases](https://github.com/hhuuphucc/Desk-Widget/releases/latest). Để xóa sạch 100% khỏi máy:

1. **Thoát app & Tắt tự khởi động:** Chuột phải vào widget → **Cài đặt...** → bỏ tích **Tự mở cùng Windows / macOS** → **Lưu**, sau đó Chuột phải → **Thoát** *(hoặc chạy thẳng lệnh bên dưới ngay cả khi app đang mở)*.
2. **Trên Windows (bản `.exe` đã tải hoặc mã nguồn):**
   - Mở **PowerShell** (`Win + X → Terminal`), dán các lệnh dưới đây để tắt app, xóa shortcut Startup, shortcut Desktop, thư mục dữ liệu `%APPDATA%\desk-widget` (`config.json`, ảnh nền/icon tùy chỉnh, `widget.pid`) và xóa luôn file `desk-widget*.exe` đã tải về trong `Downloads` / `Desktop` *(nếu chạy từ mã nguồn thì xóa thêm thư mục code)*:
     ```powershell
     Get-Process desk-widget -ErrorAction SilentlyContinue | Stop-Process -Force
     Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*widget.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
     Remove-Item "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\desk-widget.lnk" -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'desk-widget.lnk') -Force -ErrorAction SilentlyContinue
     Remove-Item "$env:APPDATA\desk-widget" -Recurse -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path $HOME 'Downloads\desk-widget*.exe') -Force -ErrorAction SilentlyContinue
     Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) 'desk-widget*.exe') -Force -ErrorAction SilentlyContinue
     ```
   - *(Nếu dùng **Command Prompt `cmd.exe`**, xem sẵn lệnh CMD trong file [`UNINSTALL.txt`](UNINSTALL.txt).)*
3. **Trên macOS (bản `.dmg` / `.app` đã tải hoặc mã nguồn):**
   - Mở **Terminal** (`Cmd + Space → Terminal`) chạy lệnh sau để tắt hẳn app, gỡ `LaunchAgent`, xóa `desk-widget.app`, file `.dmg` đã tải về trong `Downloads` / `Desktop` và dữ liệu tại `~/Library/Application Support/desk-widget` *(cùng thư mục code nếu chạy từ mã nguồn)*:
     ```bash
     pkill -f desk-widget || true
     pkill -f "widget.py" || true
     launchctl unload "$HOME/Library/LaunchAgents/com.deskwidget.app.plist" 2>/dev/null || true
     rm -f "$HOME/Library/LaunchAgents/com.deskwidget.app.plist"
     rm -rf /Applications/desk-widget.app "$HOME/Applications/desk-widget.app" "$HOME/Library/Application Support/desk-widget"
     rm -f "$HOME/Downloads"/desk-widget*.dmg "$HOME/Desktop"/desk-widget*.dmg
     ```

### Kiểm tra hoạt động (Unit Tests)

```powershell
python test_widget.py -v
```
