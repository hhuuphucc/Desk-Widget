"""Supabase Auth, 3-tier RBAC (Super Admin / Co-Admin / User), and DPAPI session client."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import sys
import threading
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse
import requests

# Configure these two public Supabase values (Project URL & Publishable/anon key) before publishing.
# NEVER hardcode Admin IDs, passwords, or private backend keys in source files.
SUPABASE_URL = "https://xffjtqiowswkwxgagkiw.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_gc2a4GbJ1uetGrwCOafs5g_HYtpR8qx"

DEFAULT_FEATURE_FLAGS: dict[str, bool] = {
    "allow_settings": True,
    "allow_bg_logo": True,
    "allow_style": True,
    "allow_theme": True,
    "allow_esl_export": True,
    "allow_updates": True,
}

ADMIN_ID_PATTERN = re.compile(r"^[0-9]{11}$")


@dataclass
class RemoteSettings:
    announcement_title: str = ""
    announcement_body: str = ""
    shared_ics_url: str = ""
    force_theme: str = ""
    min_version: str = ""
    feature_flags: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_FEATURE_FLAGS))

    @classmethod
    def from_dict(cls, raw: dict | None) -> "RemoteSettings":
        if not isinstance(raw, dict):
            return cls()
        flags = dict(DEFAULT_FEATURE_FLAGS)
        raw_flags = raw.get("feature_flags")
        if isinstance(raw_flags, dict):
            for k in DEFAULT_FEATURE_FLAGS:
                if k in raw_flags:
                    flags[k] = bool(raw_flags[k])
        return cls(
            announcement_title=str(raw.get("announcement_title") or "").strip(),
            announcement_body=str(raw.get("announcement_body") or "").strip(),
            shared_ics_url=str(raw.get("shared_ics_url") or "").strip(),
            force_theme=str(raw.get("force_theme") or "").strip().lower(),
            min_version=str(raw.get("min_version") or "").strip(),
            feature_flags=flags,
        )

    def allows(self, flag_name: str, role: str) -> bool:
        if role in ("admin", "super_admin"):
            return True
        return bool(self.feature_flags.get(flag_name, True))


@dataclass
class AuthSession:
    user_id: str = ""
    email: str = ""
    db_role: str = "guest"
    admin_verified: bool = False
    is_active: bool = True
    access_token: str = ""
    refresh_token: str = ""

    @property
    def effective_role(self) -> str:
        if not self.access_token or not self.user_id or not self.is_active:
            return "guest"
        if self.admin_verified and self.db_role in ("super_admin", "admin"):
            return self.db_role
        return "user"

    @property
    def is_guest(self) -> bool:
        return self.effective_role == "guest"

    @property
    def is_admin(self) -> bool:
        return self.effective_role in ("admin", "super_admin")

    @property
    def is_super_admin(self) -> bool:
        return self.effective_role == "super_admin"

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "db_role": self.db_role,
            "admin_verified": self.admin_verified,
            "is_active": self.is_active,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }

    @classmethod
    def from_dict(cls, raw: dict | None) -> "AuthSession":
        if not isinstance(raw, dict):
            return cls()
        return cls(
            user_id=str(raw.get("user_id") or ""),
            email=str(raw.get("email") or ""),
            db_role=str(raw.get("db_role") or "guest"),
            admin_verified=bool(raw.get("admin_verified", False)),
            is_active=bool(raw.get("is_active", True)),
            access_token=str(raw.get("access_token") or ""),
            refresh_token=str(raw.get("refresh_token") or ""),
        )


@dataclass
class AuthResult:
    ok: bool
    message: str = ""
    data: Any = None
    session: AuthSession | None = None


def _protect_bytes(raw: bytes) -> bytes:
    """Encrypt bytes with Windows DPAPI tied to the current OS user when available."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class _DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            buf = ctypes.create_string_buffer(raw, len(raw))
            in_blob = _DATA_BLOB(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
            out_blob = _DATA_BLOB()
            if crypt32.CryptProtectData(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)):
                try:
                    encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                    return json.dumps({"dpapi": base64.b64encode(encrypted).decode("ascii")}).encode("utf-8")
                finally:
                    kernel32.LocalFree(out_blob.pbData)
        except Exception:
            pass
    return raw


def _unprotect_bytes(raw: bytes) -> bytes:
    """Decrypt DPAPI-protected payload on Windows, or return raw JSON bytes."""
    try:
        parsed = json.loads(raw.decode("utf-8"))
        if isinstance(parsed, dict) and "dpapi" in parsed and sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class _DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

            crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            enc = base64.b64decode(str(parsed["dpapi"]))
            buf = ctypes.create_string_buffer(enc, len(enc))
            in_blob = _DATA_BLOB(len(enc), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
            out_blob = _DATA_BLOB()
            if crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 0x01, ctypes.byref(out_blob)):
                try:
                    return ctypes.string_at(out_blob.pbData, out_blob.cbData)
                finally:
                    kernel32.LocalFree(out_blob.pbData)
            return b""
    except Exception:
        pass
    return raw


class AuthClient:
    """Client for Supabase Auth & 3-tier RBAC RPCs with DPAPI/0600 session caching."""

    def __init__(
        self,
        session_path: str,
        supabase_url: str = SUPABASE_URL,
        supabase_anon_key: str = SUPABASE_ANON_KEY,
        timeout: int = 10,
    ) -> None:
        self.session_path = session_path
        self.supabase_url = (supabase_url or "").strip().rstrip("/")
        self.supabase_anon_key = (supabase_anon_key or "").strip()
        self.timeout = timeout
        self.session: AuthSession = self._load_session()
        self.remote_settings: RemoteSettings = RemoteSettings()

    def configure(self, supabase_url: str, supabase_anon_key: str) -> None:
        self.supabase_url = (supabase_url or "").strip().rstrip("/")
        self.supabase_anon_key = (supabase_anon_key or "").strip()

    def is_configured(self) -> bool:
        return bool(self.supabase_url.startswith(("https://", "http://")) and self.supabase_anon_key)

    def _headers(self, token: str = "") -> dict[str, str]:
        h = {
            "apikey": self.supabase_anon_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    def _save_session(self) -> None:
        try:
            parent = os.path.dirname(os.path.abspath(self.session_path))
            if parent:
                os.makedirs(parent, exist_ok=True)
            payload = json.dumps(self.session.to_dict(), ensure_ascii=False).encode("utf-8")
            wrapped = _protect_bytes(payload)
            with open(self.session_path, "wb") as fh:
                fh.write(wrapped)
            if sys.platform != "win32":
                os.chmod(self.session_path, 0o600)
        except Exception:
            pass

    def _load_session(self) -> AuthSession:
        if not self.session_path or not os.path.exists(self.session_path):
            return AuthSession()
        try:
            with open(self.session_path, "rb") as fh:
                raw = _unprotect_bytes(fh.read())
            if not raw:
                return AuthSession()
            data = json.loads(raw.decode("utf-8"))
            return AuthSession.from_dict(data)
        except Exception:
            return AuthSession()

    def _clear_session(self) -> None:
        self.session = AuthSession()
        self.remote_settings = RemoteSettings()
        try:
            if os.path.exists(self.session_path):
                os.remove(self.session_path)
        except Exception:
            pass

    def _extract_error(self, resp: requests.Response) -> str:
        try:
            body = resp.json()
            if isinstance(body, dict):
                return str(body.get("msg") or body.get("error_description") or body.get("message") or body.get("error") or resp.text)
        except Exception:
            pass
        return resp.text or f"HTTP {resp.status_code}"

    def _rpc(self, fn_name: str, payload: dict[str, Any] | None = None, token: str = "") -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "Supabase chưa được cấu hình (URL & Anon Key trống).")
        tok = token or self.session.access_token
        if not tok:
            return AuthResult(False, "Bạn chưa đăng nhập.")
        try:
            resp = requests.post(
                f"{self.supabase_url}/rest/v1/rpc/{fn_name}",
                headers=self._headers(tok),
                json=payload or {},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                return AuthResult(False, self._extract_error(resp))
            data = resp.json() if resp.text.strip() else {}
            return AuthResult(True, "", data=data)
        except Exception as exc:
            return AuthResult(False, str(exc))

    def _sync_state(self, token: str, keep_admin_verified: bool) -> AuthResult:
        res = self._rpc("get_my_session_state", {}, token=token)
        if not res.ok:
            return res
        info = res.data if isinstance(res.data, dict) else {}
        if not info.get("ok"):
            return AuthResult(False, str(info.get("error") or "Không thể xác thực phiên làm việc."))

        is_active = bool(info.get("is_active", True))
        db_role = str(info.get("db_role") or "user")
        if not is_active:
            self._clear_session()
            return AuthResult(False, "Tài khoản này đã bị quản trị viên khóa.")

        self.session.user_id = str(info.get("id") or self.session.user_id)
        self.session.email = str(info.get("email") or self.session.email)
        self.session.db_role = db_role
        self.session.is_active = is_active
        self.session.admin_verified = bool(keep_admin_verified and db_role in ("admin", "super_admin"))
        self.remote_settings = RemoteSettings.from_dict(info.get("remote_settings"))
        self._save_session()
        return AuthResult(True, "OK", data=info, session=self.session)

    def sign_up(self, email: str, password: str) -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "Supabase chưa được cấu hình.")
        clean_email = (email or "").strip().lower()
        if not clean_email or "@" not in clean_email:
            return AuthResult(False, "Email không hợp lệ.")
        if len(password or "") < 6:
            return AuthResult(False, "Mật khẩu phải có ít nhất 6 ký tự.")
        try:
            resp = requests.post(
                f"{self.supabase_url}/auth/v1/signup",
                headers=self._headers(),
                json={"email": clean_email, "password": password},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                return AuthResult(False, self._extract_error(resp))
            body = resp.json() if resp.text.strip() else {}
            access_token = str(body.get("access_token") or "")
            refresh_token = str(body.get("refresh_token") or "")
            if access_token:
                self.session = AuthSession(
                    email=clean_email,
                    access_token=access_token,
                    refresh_token=refresh_token,
                    admin_verified=False,
                )
                return self._sync_state(access_token, keep_admin_verified=False)
            return AuthResult(
                True,
                "Đăng ký thành công! Nếu dự án Supabase bật xác nhận email, hãy kiểm tra hộp thư trước khi đăng nhập.",
                data=body,
            )
        except Exception as exc:
            return AuthResult(False, str(exc))

    def sign_in_user(self, email: str, password: str) -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "Supabase chưa được cấu hình.")
        clean_email = (email or "").strip().lower()
        if not clean_email or not password:
            return AuthResult(False, "Vui lòng nhập đầy đủ Email và Mật khẩu.")
        try:
            resp = requests.post(
                f"{self.supabase_url}/auth/v1/token?grant_type=password",
                headers=self._headers(),
                json={"email": clean_email, "password": password},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                return AuthResult(False, self._extract_error(resp))
            body = resp.json()
            access_token = str(body.get("access_token") or "")
            refresh_token = str(body.get("refresh_token") or "")
            user_obj = body.get("user") or {}
            if not access_token:
                return AuthResult(False, "Không nhận được token đăng nhập.")
            self.session = AuthSession(
                user_id=str(user_obj.get("id") or ""),
                email=clean_email,
                access_token=access_token,
                refresh_token=refresh_token,
                admin_verified=False,
            )
            return self._sync_state(access_token, keep_admin_verified=False)
        except Exception as exc:
            return AuthResult(False, str(exc))

    def activate_admin_with_id(self, admin_id: str) -> AuthResult:
        clean_id = (admin_id or "").strip()
        if not clean_id:
            return AuthResult(False, "Vui lòng nhập Admin ID.")
        if not self.session.access_token:
            return AuthResult(False, "Bạn cần đăng nhập Email + Mật khẩu trước.")

        v_res = self._rpc("verify_admin_access", {"input_admin_id": clean_id})
        if not v_res.ok:
            return v_res
        payload = v_res.data if isinstance(v_res.data, dict) else {}
        if not payload.get("ok"):
            err = str(payload.get("error") or "")
            if err == "locked":
                return AuthResult(False, "Nhập sai Admin ID quá 5 lần. Tài khoản tạm khóa kiểm tra ID trong 15 phút.")
            if err == "invalid_admin_id":
                left = payload.get("attempts_left", "")
                return AuthResult(False, f"Admin ID không chính xác (còn {left} lần thử).")
            if err == "not_an_admin":
                return AuthResult(False, "Tài khoản này không có quyền Admin hoặc Co-Admin.")
            if err == "account_disabled":
                self._clear_session()
                return AuthResult(False, "Tài khoản đã bị khóa.")
            return AuthResult(False, err or "Không thể xác thực Admin ID.")

        return self._sync_state(self.session.access_token, keep_admin_verified=True)

    def sign_in_admin(self, email: str, password: str, admin_id: str) -> AuthResult:
        clean_id = (admin_id or "").strip()
        if not clean_id:
            return AuthResult(False, "Vui lòng nhập Admin ID.")
        login_res = self.sign_in_user(email, password)
        if not login_res.ok:
            return login_res
        act_res = self.activate_admin_with_id(clean_id)
        if not act_res.ok:
            self._clear_session()
            return act_res
        return act_res

    def refresh_session(self) -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "not_configured")
        if not self.session.refresh_token:
            if self.session.access_token:
                return self._sync_state(self.session.access_token, keep_admin_verified=self.session.admin_verified)
            return AuthResult(False, "no_session")
        try:
            resp = requests.post(
                f"{self.supabase_url}/auth/v1/token?grant_type=refresh_token",
                headers=self._headers(),
                json={"refresh_token": self.session.refresh_token},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                self._clear_session()
                return AuthResult(False, self._extract_error(resp))
            body = resp.json()
            access_token = str(body.get("access_token") or "")
            refresh_token = str(body.get("refresh_token") or self.session.refresh_token)
            if not access_token:
                self._clear_session()
                return AuthResult(False, "Phiên đăng nhập đã hết hạn.")
            self.session.access_token = access_token
            self.session.refresh_token = refresh_token
            return self._sync_state(access_token, keep_admin_verified=self.session.admin_verified)
        except Exception as exc:
            return AuthResult(False, str(exc))

    def send_password_recovery(self, email: str) -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "Supabase chưa được cấu hình.")
        clean_email = (email or "").strip().lower()
        if not clean_email or "@" not in clean_email:
            return AuthResult(False, "Email không hợp lệ.")
        try:
            resp = requests.post(
                f"{self.supabase_url}/auth/v1/recover",
                headers=self._headers(),
                json={"email": clean_email},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                return AuthResult(False, self._extract_error(resp))
            return AuthResult(True, "Đã gửi mã khôi phục mật khẩu tới email của bạn.")
        except Exception as exc:
            return AuthResult(False, str(exc))

    def verify_recovery_and_set_password(self, email: str, otp_or_url: str, new_password: str) -> AuthResult:
        if not self.is_configured():
            return AuthResult(False, "Supabase chưa được cấu hình.")
        clean_email = (email or "").strip().lower()
        raw_input = (otp_or_url or "").strip()
        if not raw_input:
            return AuthResult(False, "Vui lòng nhập Mã OTP hoặc dán đường dẫn khôi phục từ Email.")
        if len(new_password or "") < 6:
            return AuthResult(False, "Mật khẩu mới phải có ít nhất 6 ký tự.")

        rec_token = ""
        token_hash = ""
        clean_otp = ""
        if "access_token=" in raw_input or "token_hash=" in raw_input or raw_input.startswith(("http://", "https://", "#")):
            parsed = urlparse(raw_input if "://" in raw_input else f"http://localhost/{raw_input}")
            frag_qs = parse_qs(parsed.fragment)
            query_qs = parse_qs(parsed.query)
            rec_token = str((frag_qs.get("access_token") or query_qs.get("access_token") or [""])[0]).strip()
            token_hash = str((query_qs.get("token_hash") or frag_qs.get("token_hash") or [""])[0]).strip()
        else:
            clean_otp = raw_input

        try:
            if not rec_token:
                if token_hash:
                    verify_payload: dict[str, Any] = {"type": "recovery", "token_hash": token_hash}
                else:
                    if not clean_email:
                        return AuthResult(False, "Vui lòng nhập Email khi dùng mã OTP.")
                    verify_payload = {"type": "recovery", "email": clean_email, "token": clean_otp}
                v_resp = requests.post(
                    f"{self.supabase_url}/auth/v1/verify",
                    headers=self._headers(),
                    json=verify_payload,
                    timeout=self.timeout,
                    verify=True,
                )
                if v_resp.status_code >= 400:
                    return AuthResult(False, self._extract_error(v_resp))
                body = v_resp.json()
                rec_token = str(body.get("access_token") or "")
                if not rec_token:
                    return AuthResult(False, "Không nhận được token khôi phục hợp lệ.")

            u_resp = requests.put(
                f"{self.supabase_url}/auth/v1/user",
                headers=self._headers(rec_token),
                json={"password": new_password},
                timeout=self.timeout,
                verify=True,
            )
            if u_resp.status_code >= 400:
                return AuthResult(False, self._extract_error(u_resp))
            return AuthResult(True, "Đổi mật khẩu thành công! Bạn có thể đăng nhập lại ngay.")
        except Exception as exc:
            return AuthResult(False, str(exc))

    def change_password(self, new_password: str) -> AuthResult:
        if not self.session.access_token:
            return AuthResult(False, "Bạn chưa đăng nhập.")
        if len(new_password or "") < 6:
            return AuthResult(False, "Mật khẩu mới phải có ít nhất 6 ký tự.")
        try:
            resp = requests.put(
                f"{self.supabase_url}/auth/v1/user",
                headers=self._headers(self.session.access_token),
                json={"password": new_password},
                timeout=self.timeout,
                verify=True,
            )
            if resp.status_code >= 400:
                return AuthResult(False, self._extract_error(resp))
            return AuthResult(True, "Đã cập nhật mật khẩu thành công.")
        except Exception as exc:
            return AuthResult(False, str(exc))

    def sign_out(self) -> None:
        tok = self.session.access_token
        if tok and self.is_configured():
            try:
                requests.post(
                    f"{self.supabase_url}/auth/v1/logout",
                    headers=self._headers(tok),
                    timeout=5,
                    verify=True,
                )
            except Exception:
                pass
        self._clear_session()

    # --- Admin & Super Admin RPC calls ---

    def list_profiles(self) -> AuthResult:
        if not self.session.is_admin:
            return AuthResult(False, "Yêu cầu quyền Admin hoặc Super Admin.")
        return self._rpc("admin_list_profiles", {})

    def grant_coadmin_id(self, target_email: str) -> AuthResult:
        if not self.session.is_super_admin:
            return AuthResult(False, "Chỉ tài khoản Super Admin mới có quyền tạo hoặc cấp lại Co-Admin ID.")
        clean_email = (target_email or "").strip().lower()
        if not clean_email or "@" not in clean_email:
            return AuthResult(False, "Email Co-Admin không hợp lệ.")
        return self._rpc("super_admin_grant_coadmin", {"target_email": clean_email})

    def revoke_coadmin(self, target_user_id: str) -> AuthResult:
        if not self.session.is_super_admin:
            return AuthResult(False, "Chỉ tài khoản Super Admin mới có quyền thu hồi Co-Admin.")
        return self._rpc("super_admin_revoke_coadmin", {"target_user_id": target_user_id})

    def set_user_active(self, target_user_id: str, new_active: bool) -> AuthResult:
        if not self.session.is_admin:
            return AuthResult(False, "Yêu cầu quyền Admin hoặc Super Admin.")
        return self._rpc(
            "admin_set_user_active",
            {"target_user_id": target_user_id, "new_active": bool(new_active)},
        )

    def delete_user(self, target_user_id: str) -> AuthResult:
        if not self.session.is_super_admin:
            return AuthResult(False, "Chỉ tài khoản Super Admin mới có quyền xóa tài khoản.")
        return self._rpc("super_admin_delete_user", {"target_user_id": target_user_id})

    def update_remote_settings(self, settings: RemoteSettings) -> AuthResult:
        if not self.session.is_admin:
            return AuthResult(False, "Yêu cầu quyền Admin hoặc Super Admin.")
        res = self._rpc(
            "admin_update_remote_settings",
            {
                "p_announcement_title": settings.announcement_title,
                "p_announcement_body": settings.announcement_body,
                "p_shared_ics_url": settings.shared_ics_url,
                "p_force_theme": settings.force_theme,
                "p_min_version": settings.min_version,
                "p_feature_flags": settings.feature_flags,
            },
        )
        if res.ok:
            self.remote_settings = settings
        return res


def start_recovery_callback_listener(on_url: Callable[[str], None], port: int = 3000) -> HTTPServer | None:
    """Listen briefly on 127.0.0.1:3000 so clicking Supabase's reset link auto-fills the desktop app."""

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/capture":
                qs = parse_qs(parsed.query)
                frag = str((qs.get("frag") or [""])[0])
                full = f"http://localhost:{port}/#{frag}" if frag else f"http://localhost:{port}{self.path}"
                on_url(full)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h3>OK!</h3>".encode("utf-8"))
                return

            if "token_hash=" in self.path or "access_token=" in self.path:
                on_url(f"http://localhost:{port}{self.path}")

            html = (
                "<!doctype html><html><meta charset='utf-8'>"
                "<body style='font-family:sans-serif;padding:24px;'>"
                "<h3>Đã nhận liên kết khôi phục cho desk-widget!</h3>"
                "<p>Bạn có thể đóng tab này và quay lại ứng dụng <b>desk-widget</b> để nhập mật khẩu mới.</p>"
                "<script>"
                "if (location.hash && location.hash.length > 1) {"
                "  fetch('/capture?frag=' + encodeURIComponent(location.hash.slice(1)));"
                "}"
                "</script></body></html>"
            )
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode("utf-8"))

    try:
        srv = HTTPServer(("127.0.0.1", port), _Handler)
    except OSError:
        return None

    def _serve() -> None:
        try:
            srv.serve_forever()
        except Exception:
            pass

    threading.Thread(target=_serve, daemon=True).start()
    return srv
