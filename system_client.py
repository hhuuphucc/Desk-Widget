"""Real-time cross-platform (Windows & macOS Intel/Apple Silicon) CPU, RAM, GPU usage & temperature inspector."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import sys
import time
import psutil

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


@dataclass
class SystemStats:
    cpu_pct: int
    ram_pct: int
    ram_used_gb: float
    ram_total_gb: float
    gpu_pct: int | None
    gpu_name: str
    gpu_vram_used_mb: int | None = None
    gpu_vram_total_mb: int | None = None
    cpu_temp_c: float | None = None
    gpu_temp_c: float | None = None


def _short_gpu_name(raw: str) -> str:
    name = (
        raw.replace("NVIDIA GeForce ", "")
        .replace(" Laptop GPU", "")
        .replace("AMD Radeon ", "")
        .replace("Intel(R) ", "")
        .strip()
    )
    return name[:18] if name else "GPU"


def _detect_mac_gpu_name() -> str:
    """Detect GPU / Apple Silicon SoC display label on Intel or M-series Mac."""
    try:
        brand = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        ).strip()
        if "apple" in brand.lower():
            return _short_gpu_name(brand)
    except Exception:
        pass

    try:
        out = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            text=True,
            timeout=4,
            stderr=subprocess.DEVNULL,
        )
        m = re.search(r"Chipset Model:\s*(.+)", out)
        if m:
            return _short_gpu_name(m.group(1))
    except Exception:
        pass
    return "Mac GPU"


def _read_mac_gpu(default_name: str = "Mac GPU") -> tuple[int | None, str, int | None, int | None, float | None]:
    """Read macOS GPU utilization (and optional VRAM/temp) via IOAccelerator ioreg (Intel & Apple Silicon)."""
    util: int | None = None
    v_used: int | None = None
    v_total: int | None = None
    gpu_temp_c: float | None = None
    try:
        out = subprocess.check_output(
            ["ioreg", "-r", "-d", "1", "-c", "IOAccelerator"],
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        )
        m_util = re.search(r'"(?:Device Utilization %|GPU Activity\(%\))"\s*=\s*(\d+)', out)
        if m_util:
            util = max(0, min(100, int(m_util.group(1))))

        m_temp = re.search(r'"Temperature\(C\)"\s*=\s*(\d+(?:\.\d+)?)', out)
        if m_temp:
            t_val = float(m_temp.group(1))
            if 5.0 <= t_val <= 130.0:
                gpu_temp_c = round(t_val, 1)

        m_vtot = re.search(r'"VRAM,totalMB"\s*=\s*(\d+)', out)
        if m_vtot:
            v_total = int(m_vtot.group(1))
        m_vuse = re.search(r'"(?:vramUsedBytes|In use system memory)"\s*=\s*(\d+)', out)
        if m_vuse:
            raw_b = int(m_vuse.group(1))
            v_used = raw_b // (1024 * 1024) if raw_b > 16384 else raw_b
    except Exception:
        pass
    return util, default_name, v_used, v_total, gpu_temp_c


class _NvmlUtil(ctypes.Structure):
    _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]


class _NvmlMem(ctypes.Structure):
    _fields_ = [("total", ctypes.c_ulonglong), ("free", ctypes.c_ulonglong), ("used", ctypes.c_ulonglong)]


class _NvmlReader:
    """Zero-subprocess NVIDIA GPU telemetry via Windows nvml.dll (~0.4ms/call vs ~60ms nvidia-smi.exe)."""

    def __init__(self) -> None:
        self._lib = None
        self._handle = None
        self._gpu_name: str = ""
        self._failed: bool = False

    def _ensure_init(self) -> bool:
        if self._handle is not None and self._lib is not None:
            return True
        if self._failed or not IS_WINDOWS:
            return False
        candidates = (
            os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvml.dll"),
            r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll",
        )
        for path in candidates:
            if not os.path.exists(path):
                continue
            try:
                lib = ctypes.WinDLL(path)
                if lib.nvmlInit_v2() != 0:
                    continue
                handle = ctypes.c_void_p()
                if lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(handle)) != 0:
                    lib.nvmlShutdown()
                    continue
                name_buf = ctypes.create_string_buffer(96)
                gname = "NVIDIA GPU"
                if lib.nvmlDeviceGetName(handle, name_buf, 96) == 0:
                    gname = _short_gpu_name(name_buf.value.decode("utf-8", errors="replace"))
                self._lib = lib
                self._handle = handle
                self._gpu_name = gname
                return True
            except Exception:
                continue
        self._failed = True
        return False

    def read(self) -> tuple[int, str, int, int, float | None] | None:
        if not self._ensure_init():
            return None
        try:
            util = _NvmlUtil()
            mem = _NvmlMem()
            if self._lib.nvmlDeviceGetUtilizationRates(self._handle, ctypes.byref(util)) != 0:
                return None
            if self._lib.nvmlDeviceGetMemoryInfo(self._handle, ctypes.byref(mem)) != 0:
                return None
            temp_val = ctypes.c_uint()
            gpu_temp_c: float | None = None
            if self._lib.nvmlDeviceGetTemperature(self._handle, 0, ctypes.byref(temp_val)) == 0:
                if 0 <= temp_val.value <= 130:
                    gpu_temp_c = float(temp_val.value)
            v_used = int(round(mem.used / (1024 * 1024)))
            v_total = int(round(mem.total / (1024 * 1024)))
            return max(0, min(100, int(util.gpu))), self._gpu_name, v_used, v_total, gpu_temp_c
        except Exception:
            return None


def _read_nvidia_gpu() -> tuple[int, str, int, int, float | None] | None:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=2,
            creationflags=flags,
            stderr=subprocess.DEVNULL,
        ).strip()
        if not out:
            return None
        first_line = out.splitlines()[0]
        parts = [p.strip() for p in first_line.split(",")]
        if len(parts) < 4:
            return None
        name = _short_gpu_name(parts[0])
        util = max(0, min(100, int(round(float(parts[1])))))
        v_used = int(round(float(parts[2])))
        v_total = int(round(float(parts[3])))
        gpu_temp_c: float | None = None
        if len(parts) >= 5:
            try:
                t_val = float(parts[4])
                if 0.0 <= t_val <= 130.0:
                    gpu_temp_c = round(t_val, 1)
            except Exception:
                pass
        return util, name, v_used, v_total, gpu_temp_c
    except Exception:
        return None


def _read_cpu_temp_c() -> float | None:
    """Read CPU/system thermal zone temperature in Celsius without elevated privileges."""
    try:
        if hasattr(psutil, "sensors_temperatures"):
            temps_map = psutil.sensors_temperatures(fahrenheit=False) or {}
            preferred = ("coretemp", "k10temp", "zenpower", "cpu_thermal", "acpitz")
            cands: list[float] = []
            for key in preferred:
                for entry in temps_map.get(key, []):
                    if 10.0 <= entry.current <= 125.0:
                        cands.append(float(entry.current))
            if not cands:
                for entries in temps_map.values():
                    for entry in entries:
                        if 10.0 <= entry.current <= 125.0:
                            cands.append(float(entry.current))
            if cands:
                return round(max(cands), 1)
    except Exception:
        pass

    if IS_WINDOWS:
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            out = subprocess.check_output(
                ["typeperf", r"\Thermal Zone Information(*)\Temperature", "-sc", "1"],
                text=True,
                timeout=3,
                creationflags=flags,
                stderr=subprocess.DEVNULL,
            )
            lines = [l for l in out.splitlines() if l.startswith('"')]
            if len(lines) >= 2:
                vals = [v.strip('" ') for v in lines[-1].split('","')][1:]
                c_vals: list[float] = []
                for v in vals:
                    if not v:
                        continue
                    try:
                        num = float(v)
                    except ValueError:
                        continue
                    if 200.0 <= num <= 430.0:
                        c_vals.append(num - 273.15)
                    elif 10.0 <= num <= 125.0:
                        c_vals.append(num)
                if c_vals:
                    return round(max(c_vals), 1)
        except Exception:
            pass
    elif IS_MACOS:
        # Optional user-installed CLI tools (work on Apple Silicon & Intel without sudo)
        for cmd in (["smctemp", "-c"], ["osx-cpu-temp"], ["istats", "cpu", "temp", "--value-only"]):
            if not shutil.which(cmd[0]):
                continue
            try:
                out = subprocess.check_output(cmd, text=True, timeout=2, stderr=subprocess.DEVNULL).strip()
                m = re.search(r"(\d+(?:\.\d+)?)", out)
                if m:
                    val = float(m.group(1))
                    if 10.0 <= val <= 125.0:
                        return round(val, 1)
            except Exception:
                continue

        # Fallback: IOHWSensor thermal reading (mostly Intel Macs)
        try:
            out = subprocess.check_output(
                ["ioreg", "-r", "-c", "IOHWSensor"],
                text=True,
                timeout=2,
                stderr=subprocess.DEVNULL,
            )
            blocks = out.split("+-o ")
            temps: list[float] = []
            for blk in blocks:
                if '"type" = "temperature"' in blk.lower() or '"sensor-type" = "temperature"' in blk.lower():
                    m_val = re.search(r'"current-value"\s*=\s*(\d+)', blk)
                    if m_val:
                        c_val = int(m_val.group(1)) / 65536.0
                        if 10.0 <= c_val <= 125.0:
                            temps.append(c_val)
            if temps:
                return round(max(temps), 1)
        except Exception:
            pass
    return None


def top_ram_processes(limit: int = 12) -> list[dict]:
    """Return top applications grouped by executable name consuming RAM."""
    total_bytes = psutil.virtual_memory().total
    grouped: dict[str, dict] = {}
    for proc in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            name = proc.info["name"] or f"PID {proc.info['pid']}"
            if name.lower() in ("system idle process", "registry"):
                continue
            mem = proc.info["memory_info"]
            if not mem:
                continue
            rss = mem.rss
            entry = grouped.setdefault(name, {"name": name, "rss": 0, "count": 0})
            entry["rss"] += rss
            entry["count"] += 1
        except Exception:
            continue

    ranked = sorted(grouped.values(), key=lambda x: -x["rss"])[:limit]
    for item in ranked:
        item["mb"] = round(item["rss"] / (1024 * 1024), 1)
        item["pct"] = round((item["rss"] / total_bytes) * 100.0, 1) if total_bytes else 0.0
    return ranked


def top_cpu_processes(sample_sec: float = 0.8, limit: int = 12) -> list[dict]:
    """Sample per-process CPU usage across logical cores via cpu_times snapshots."""
    import os
    cores = psutil.cpu_count(logical=True) or 1
    my_pid = os.getpid()

    t0_map: dict[int, tuple[str, float]] = {}
    for p in psutil.process_iter(["pid", "name", "cpu_times"]):
        try:
            pid = p.info["pid"]
            name = p.info["name"] or ""
            if not name or name.lower() in ("system idle process", "idle"):
                continue
            ct = p.info["cpu_times"]
            if ct is None:
                continue
            t0_map[pid] = (name, ct.user + ct.system)
        except Exception:
            continue

    t_start = time.perf_counter()
    time.sleep(sample_sec)
    elapsed = max(0.05, time.perf_counter() - t_start)

    grouped: dict[str, dict] = {}
    for p in psutil.process_iter(["pid", "name", "cpu_times"]):
        try:
            pid = p.info["pid"]
            if pid not in t0_map:
                continue
            name, prev_t = t0_map[pid]
            ct = p.info["cpu_times"]
            if ct is None:
                continue
            delta = max(0.0, (ct.user + ct.system) - prev_t)
            pct = (delta / (elapsed * cores)) * 100.0
            if pct <= 0.05:
                continue
            disp_name = f"{name} [Widget]" if pid == my_pid else name
            entry = grouped.setdefault(disp_name, {"name": disp_name, "pct": 0.0, "count": 0})
            entry["pct"] += pct
            entry["count"] += 1
        except Exception:
            continue

    ranked = sorted(grouped.values(), key=lambda x: -x["pct"])[:limit]
    for item in ranked:
        item["pct"] = round(min(100.0, item["pct"]), 1)
    return ranked


def top_gpu_processes(limit: int = 12) -> tuple[list[dict], list[dict]]:
    """Return (dedicated_gpu_apps, system_gpu_apps)."""
    if not IS_WINDOWS:
        # macOS / non-Windows fallback: return active high-CPU GUI/compute apps gracefully
        return [], top_cpu_processes(sample_sec=0.4, limit=limit)

    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    # 1. NVIDIA discrete GPU processes (pmon catches both Compute and Graphics)
    nvidia_apps: list[dict] = []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "pmon", "-c", "1", "-s", "um"],
            text=True,
            timeout=3,
            creationflags=flags,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) >= 11 and parts[1].isdigit():
                pid = int(parts[1])
                ptype = parts[2]
                sm = 0 if parts[3] == "-" else int(float(parts[3]))
                fb_mb = 0 if parts[9] == "-" else int(float(parts[9]))
                cmd = parts[-1]
                try:
                    cmd = psutil.Process(pid).name()
                except Exception:
                    pass
                nvidia_apps.append({"name": cmd, "pid": pid, "type": ptype, "pct": sm, "vram_mb": fb_mb})
    except Exception:
        pass

    # 2. Windows GPU Engine performance counters (captures iGPU + dGPU apps like browsers/IDE)
    win_grouped: dict[str, dict] = {}
    try:
        out = subprocess.check_output(
            ["typeperf", r"\GPU Engine(*)\Utilization Percentage", "-sc", "1"],
            text=True,
            timeout=6,
            creationflags=flags,
            stderr=subprocess.DEVNULL,
        )
        lines = [l for l in out.splitlines() if l.startswith('"')]
        if len(lines) >= 2:
            headers = [h.strip('"') for h in lines[0].split('","')]
            vals = [v.strip('" ') for v in lines[1].split('","')]
            by_pid: dict[int, float] = {}
            for h, v in zip(headers[1:], vals[1:]):
                if not v:
                    continue
                val = float(v)
                if val <= 0.05:
                    continue
                m = re.search(r"pid_(\d+)", h)
                if m:
                    pid = int(m.group(1))
                    by_pid[pid] = max(by_pid.get(pid, 0.0), val)
            for pid, val in by_pid.items():
                try:
                    pname = psutil.Process(pid).name()
                except Exception:
                    pname = f"PID {pid}"
                entry = win_grouped.setdefault(pname, {"name": pname, "pct": 0.0, "count": 0})
                entry["pct"] += val
                entry["count"] += 1
    except Exception:
        pass

    win_ranked = sorted(win_grouped.values(), key=lambda x: -x["pct"])[:limit]
    for item in win_ranked:
        item["pct"] = round(min(100.0, item["pct"]), 1)

    return nvidia_apps[:limit], win_ranked


class SystemMonitor:
    def __init__(self) -> None:
        psutil.cpu_percent(interval=None)
        self._gpu_name: str = _detect_mac_gpu_name() if IS_MACOS else "GPU"
        self._nvml = _NvmlReader() if IS_WINDOWS else None
        self._cpu_temp_c: float | None = None
        self._cpu_temp_checked_at: float = 0.0
        self._last_gpu_info: tuple[int | None, str, int | None, int | None, float | None] | None = None
        self._gpu_checked_at: float = 0.0

    def read(self, sample_interval: float | None = None, include_cpu_temp: bool = True) -> SystemStats:
        cpu = max(0, min(100, int(round(psutil.cpu_percent(interval=sample_interval)))))
        vm = psutil.virtual_memory()
        ram_pct = max(0, min(100, int(round(vm.percent))))
        ram_used = vm.used / (1024 ** 3)
        ram_total = vm.total / (1024 ** 3)
        now_m = time.monotonic()

        if include_cpu_temp and (
            self._cpu_temp_checked_at == 0.0 or (now_m - self._cpu_temp_checked_at) >= 30.0
        ):
            self._cpu_temp_checked_at = now_m
            t_c = _read_cpu_temp_c()
            if t_c is not None:
                self._cpu_temp_c = t_c

        if IS_MACOS:
            if self._last_gpu_info is None or (now_m - self._gpu_checked_at) >= 3.0:
                self._gpu_checked_at = now_m
                self._last_gpu_info = _read_mac_gpu(self._gpu_name)
            gpu_pct, gpu_name, v_used, v_total, gpu_temp_c = self._last_gpu_info
            return SystemStats(
                cpu_pct=cpu,
                ram_pct=ram_pct,
                ram_used_gb=ram_used,
                ram_total_gb=ram_total,
                gpu_pct=gpu_pct,
                gpu_name=gpu_name,
                gpu_vram_used_mb=v_used,
                gpu_vram_total_mb=v_total,
                cpu_temp_c=self._cpu_temp_c,
                gpu_temp_c=gpu_temp_c,
            )

        gpu_info = self._nvml.read() if self._nvml is not None else None
        if gpu_info is None:
            # Fallback to spawning nvidia-smi.exe at most once per 4s if nvml.dll is unavailable
            if self._last_gpu_info is None or (now_m - self._gpu_checked_at) >= 4.0:
                self._gpu_checked_at = now_m
                smi = _read_nvidia_gpu()
                self._last_gpu_info = smi if smi is not None else (None, self._gpu_name, None, None, None)
            gpu_pct, gpu_name, v_used, v_total, gpu_temp_c = self._last_gpu_info
        else:
            gpu_pct, gpu_name, v_used, v_total, gpu_temp_c = gpu_info
            self._gpu_name = gpu_name

        return SystemStats(
            cpu_pct=cpu,
            ram_pct=ram_pct,
            ram_used_gb=ram_used,
            ram_total_gb=ram_total,
            gpu_pct=gpu_pct,
            gpu_name=gpu_name,
            gpu_vram_used_mb=v_used,
            gpu_vram_total_mb=v_total,
            cpu_temp_c=self._cpu_temp_c,
            gpu_temp_c=gpu_temp_c,
        )
