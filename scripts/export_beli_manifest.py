#!/usr/bin/env python3
"""Export all Beli ranking data and associated metadata into a local JSON manifest.

Implements the reverse-engineered Beli API OpenAPI 3.1 contract documented in
https://github.com/ProjectBarks/beli-api using only the Python standard library
(Python 3.10+), so it can run standalone with zero third-party dependencies.

Why pure stdlib against the ProjectBarks/beli-api contract:
  * Supports BOTH email and phone_no (E.164) login as well as 7-day refresh tokens.
  * Handles every Beli response envelope (paginated, results-wrapped, bare lists,
    category-keyed dicts, scalars) without dropping unknown/extra fields.
  * Enforces mandatory Origin/User-Agent headers, multi-host routing (ONBOARD,
    API, RECS), polite >=350ms request spacing, and retry/backoff on 429/5xx.
  * Preserves 100% lossless raw payloads alongside a clean, merged `rankings`
    array directly compatible with `ranknorm.redistribute(...)`.

Examples:
  # Interactive login (prompts for email/phone & password, saves 7-day session)
  python3 scripts/export_beli_manifest.py

  # Fast bulk-only snapshot (~10s, skips per-business visit/tag lookups)
  python3 scripts/export_beli_manifest.py --detail fast --output data/beli-manifest.json

  # Maximum metadata (includes per-business community histograms, dishes, friends)
  python3 scripts/export_beli_manifest.py --detail max --resume

  # Non-interactive via environment variables (or a local .env file)
  BELI_EMAIL="you@example.com" BELI_PASSWORD="..." python3 scripts/export_beli_manifest.py
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------
# ProjectBarks/beli-api constants (from openapi/beli.yaml & sdkgen/python/beli.py)
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "1.0.0"
API_REFERENCE_URL = "https://github.com/ProjectBarks/beli-api"

HOST_ONBOARD = "https://backoffice-service-onboarding-t57o3dxfca-nn.a.run.app"
HOST_API = "https://backoffice-service-t57o3dxfca-nn.a.run.app"
HOST_RECS = "https://backoffice-service-recs-t57o3dxfca-nn.a.run.app"

DEFAULT_ORIGIN = "capacitor://localhost"
DEFAULT_REFERER: str | None = None
DEFAULT_MIN_INTERVAL_MS = 350
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_OUTPUT_PATH = Path("data/beli-manifest.json")
DEFAULT_SESSION_PATH = Path(".beli-session.json")
DEFAULT_KEYCHAIN_SERVICE = "beli-api-password"

# Known Beli category codes (union with dynamically discovered categories from user-scores)
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "RES",
    "BAR",
    "DES",
    "BAK",
    "CAF",
    "COF",
    "COFFEE",
    "BAKERY",
    "DESSERT",
    "ICE",
    "OTHER",
)

USER_AGENTS: tuple[str, ...] = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 16; SM-S928U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.7827.91 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
)

PII_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "phone_no",
        "phone_number",
        "sessions",
        "referrer",
        "referral_link",
        "qr_code",
        "fcm_token",
        "live_activity_token",
    }
)

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


# ---------------------------------------------------------------------------
# JWT, environment, and filesystem helpers
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
    data = json.loads(decoded.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JWT payload is not a JSON object")
    return data


def is_token_expired(
    token: str | None,
    *,
    skew_seconds: int = 60,
    now: float | None = None,
) -> bool:
    if not token:
        return True
    try:
        claims = decode_jwt_claims(token)
        exp = float(claims["exp"])
    except Exception:
        return True
    current = time.time() if now is None else now
    return exp - skew_seconds <= current


def load_dotenv_file(path: Path) -> dict[str, str]:
    """Minimal .env parser (no external dependencies)."""
    loaded: dict[str, str] = {}
    if not path.is_file():
        return loaded
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            loaded[key] = value
    return loaded


def atomic_write_json(path: Path, payload: Any, *, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    serialized = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
    tmp_path.write_text(serialized, encoding="utf-8")
    if mode is not None:
        os.chmod(tmp_path, mode)
    os.replace(tmp_path, path)
    if mode is not None:
        os.chmod(path, mode)


# ---------------------------------------------------------------------------
# HTTP transport and Beli API client
# ---------------------------------------------------------------------------


@dataclass
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str] = field(default_factory=dict)

    def json(self) -> Any:
        if not self.body:
            return None
        return json.loads(self.body.decode("utf-8"))


class BeliApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def _default_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
    timeout: float,
) -> HttpResponse:
    req = urllib.request.Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            return HttpResponse(status=resp.status, body=resp.read(), headers=resp_headers)
    except urllib.error.HTTPError as exc:
        resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
        return HttpResponse(status=exc.code, body=exc.read(), headers=resp_headers)


@dataclass
class Tokens:
    access: str = ""
    refresh: str = ""


class BeliClient:
    """Self-contained Beli API client implementing ProjectBarks/beli-api conventions."""

    def __init__(
        self,
        *,
        email: str | None = None,
        phone_no: str | None = None,
        password: str | None = None,
        access_token: str = "",
        refresh_token: str = "",
        user_agent: str | None = None,
        origin: str = DEFAULT_ORIGIN,
        referer: str | None = DEFAULT_REFERER,
        min_interval_ms: int = DEFAULT_MIN_INTERVAL_MS,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 3,
        session_path: Path | None = None,
        transport: Callable[[str, str, dict[str, str], bytes | None, float], HttpResponse]
        | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ) -> None:
        self.email = email
        self.phone_no = phone_no
        self.password = password
        self.tokens = Tokens(access=access_token, refresh=refresh_token)
        self.user_agent = user_agent or USER_AGENTS[0]
        self.origin = origin
        self.referer = referer
        self.min_interval_s = max(0.0, min_interval_ms / 1000.0)
        self.timeout = timeout
        self.max_retries = max(0, max_retries)
        self.session_path = session_path
        self._transport = transport or _default_transport
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._last_request_at: float | None = None
        self.request_count = 0

        if self.session_path and not (self.tokens.access or self.tokens.refresh):
            self._load_session_file()

    def _load_session_file(self) -> None:
        if not self.session_path or not self.session_path.is_file():
            return
        try:
            data = json.loads(self.session_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if isinstance(data, dict):
            self.tokens.access = str(data.get("access") or "")
            self.tokens.refresh = str(data.get("refresh") or "")

    def save_session_file(self) -> None:
        if not self.session_path:
            return
        if not (self.tokens.access or self.tokens.refresh):
            return
        payload = {
            "saved_at": utc_now_iso(),
            "user_id": self.try_user_id(),
            "access": self.tokens.access,
            "refresh": self.tokens.refresh,
        }
        atomic_write_json(self.session_path, payload, mode=stat.S_IRUSR | stat.S_IWUSR)

    def try_user_id(self) -> str | None:
        for tok in (self.tokens.access, self.tokens.refresh):
            if not tok:
                continue
            try:
                uid = decode_jwt_claims(tok).get("user_id")
                if uid:
                    return str(uid)
            except Exception:
                continue
        return None

    @property
    def user_id(self) -> str:
        token = self.ensure_fresh_token()
        uid = decode_jwt_claims(token).get("user_id")
        if not uid:
            raise BeliApiError("Access token JWT does not contain user_id claim")
        return str(uid)

    def _base_headers(self, *, authenticated: bool) -> dict[str, str]:
        headers = {
            "User-Agent": self.user_agent,
            "Origin": self.origin,
            "Accept": "application/json",
        }
        if self.referer:
            headers["Referer"] = self.referer
        if authenticated:
            headers["Authorization"] = f"Bearer {self.tokens.access}"
        return headers

    def _pace(self) -> None:
        if self.min_interval_s <= 0:
            return
        now = self._monotonic()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self.min_interval_s - elapsed
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()

    def _send_raw(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        json_body: Any = None,
    ) -> HttpResponse:
        body_bytes: bytes | None = None
        req_headers = dict(headers)
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._pace()
            self.request_count += 1
            try:
                resp = self._transport(method, url, req_headers, body_bytes, self.timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise BeliApiError(f"Network error calling {url}: {exc}") from exc
                backoff = min(8.0, (2**attempt) * 0.5)
                self._sleep(backoff)
                continue

            if resp.status in RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                retry_after = resp.headers.get("retry-after")
                if retry_after and retry_after.isdigit():
                    delay = min(15.0, float(retry_after))
                else:
                    delay = min(10.0, (2**attempt) * 0.75)
                self._sleep(delay)
                continue
            return resp

        raise BeliApiError(f"Request failed after retries for {url}: {last_exc}")

    def ensure_fresh_token(self, *, force_refresh: bool = False) -> str:
        if not force_refresh and not is_token_expired(self.tokens.access):
            return self.tokens.access

        if not is_token_expired(self.tokens.refresh):
            resp = self._send_raw(
                "POST",
                f"{HOST_ONBOARD}/api/token/refresh/",
                headers=self._base_headers(authenticated=False),
                json_body={"refresh": self.tokens.refresh},
            )
            if resp.status == 200:
                data = resp.json()
                if isinstance(data, dict) and data.get("access"):
                    self.tokens.access = str(data["access"])
                    self.save_session_file()
                    return self.tokens.access

        if (self.email or self.phone_no) and self.password:
            login_body: dict[str, str] = {"password": self.password}
            if self.email:
                login_body["email"] = self.email
            else:
                login_body["phone_no"] = self.phone_no or ""
            resp = self._send_raw(
                "POST",
                f"{HOST_ONBOARD}/api/token/",
                headers=self._base_headers(authenticated=False),
                json_body=login_body,
            )
            payload = _safe_parse_json(resp)
            if resp.status != 200 or not isinstance(payload, dict) or not payload.get("access"):
                raise BeliApiError(
                    f"Beli login failed (HTTP {resp.status}): {payload}",
                    status=resp.status,
                    payload=payload,
                )
            self.tokens = Tokens(
                access=str(payload["access"]),
                refresh=str(payload.get("refresh") or ""),
            )
            self.save_session_file()
            return self.tokens.access

        raise BeliApiError(
            "No usable Beli credentials or live token. Provide email/phone + password, "
            "a live access token, or a refresh token issued within the last 7 days."
        )

    def request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        host: str = HOST_API,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        follow_pagination: bool = True,
        max_pages: int = 100,
    ) -> tuple[int, Any]:
        """Make an authenticated request, refreshing once on 401 and optionally following DRF `next`."""
        url = _build_url(host, path_or_url, params)
        status, data = self._request_once(method, url, json_body=json_body)
        if not follow_pagination or status != 200 or not isinstance(data, dict):
            return status, data

        next_url = data.get("next")
        if not isinstance(next_url, str) or not next_url or not isinstance(data.get("results"), list):
            return status, data

        # Follow DRF pagination links if the server returns a non-null `next` URL.
        combined = dict(data)
        all_results = list(data["results"])
        seen_urls = {url}
        pages = 1
        while isinstance(next_url, str) and next_url and next_url not in seen_urls and pages < max_pages:
            seen_urls.add(next_url)
            resolved_next = urllib.parse.urljoin(url, next_url)
            p_status, p_data = self._request_once(method, resolved_next)
            if p_status != 200 or not isinstance(p_data, dict):
                break
            page_results = p_data.get("results")
            if isinstance(page_results, list):
                all_results.extend(page_results)
            next_url = p_data.get("next")
            pages += 1

        combined["results"] = all_results
        combined["next"] = next_url
        combined["_pages_fetched"] = pages
        return status, combined

    def _request_once(
        self,
        method: str,
        url: str,
        *,
        json_body: Any = None,
    ) -> tuple[int, Any]:
        self.ensure_fresh_token()
        resp = self._send_raw(
            method,
            url,
            headers=self._base_headers(authenticated=True),
            json_body=json_body,
        )
        if resp.status == 401:
            self.ensure_fresh_token(force_refresh=True)
            resp = self._send_raw(
                method,
                url,
                headers=self._base_headers(authenticated=True),
                json_body=json_body,
            )
        return resp.status, _safe_parse_json(resp)


def _safe_parse_json(resp: HttpResponse) -> Any:
    if not resp.body:
        return None
    try:
        return resp.json()
    except Exception:
        return {"_raw_text": resp.body.decode("utf-8", errors="replace")}


def _build_url(host: str, path_or_url: str, params: dict[str, Any] | None) -> str:
    if path_or_url.startswith(("http://", "https://")):
        base = path_or_url
    else:
        base = f"{host.rstrip('/')}/{path_or_url.lstrip('/')}"
    if not params:
        return base
    clean = {k: str(v) for k, v in params.items() if v is not None}
    if not clean:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urllib.parse.urlencode(clean)}"


# ---------------------------------------------------------------------------
# Envelope normalization & ID/score extractors
# ---------------------------------------------------------------------------


def extract_items(payload: Any) -> list[Any]:
    """Unwrap DRF `{count, results}`, `{results}`, bare list, or single dict into a list."""
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return payload["results"]
        if isinstance(payload.get("results"), dict):
            return [payload["results"]]
    return []


def extract_business_id(record: Any) -> int | None:
    if not isinstance(record, dict):
        return None
    for key in ("business_id", "business"):
        val = record.get(key)
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
        if isinstance(val, dict):
            nested = val.get("id")
            if isinstance(nested, int) and not isinstance(nested, bool):
                return nested
            if isinstance(nested, str) and nested.isdigit():
                return int(nested)
    return None


def extract_business_dict(record: Any) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        return None
    for key in ("business", "business_full"):
        val = record.get(key)
        if isinstance(val, dict) and (val.get("id") is not None or val.get("name")):
            return dict(val)
    return None


def extract_user_id_from_record(record: Any) -> str | None:
    if not isinstance(record, dict):
        return None
    for key in ("user_id", "user", "user1"):
        val = record.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict) and isinstance(val.get("id"), str):
            return val["id"]
    return None


def coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _filter_to_user_if_tagged(records: list[Any], user_id: str) -> list[Any]:
    """If records carry a user/user_id field, keep only the target user's rows."""
    if not records:
        return []
    any_user_field = any(extract_user_id_from_record(r) is not None for r in records)
    if not any_user_field:
        return records
    return [
        r
        for r in records
        if (uid := extract_user_id_from_record(r)) is None or uid.lower() == user_id.lower()
    ]


def _extract_label_strings(item: Any, label_lookup: dict[int, dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    if isinstance(item, str) and item:
        return [item]
    if isinstance(item, int) and item in label_lookup:
        meta = label_lookup[item]
        name = meta.get("display") or meta.get("name") or meta.get("label") or str(item)
        return [str(name)]
    if isinstance(item, dict):
        for key in ("display", "label_name", "name", "title", "value"):
            val = item.get(key)
            if isinstance(val, str) and val:
                labels.append(val)
                return labels
        nested = item.get("label") or item.get("business_label")
        if isinstance(nested, dict):
            return _extract_label_strings(nested, label_lookup)
        if isinstance(nested, int):
            return _extract_label_strings(nested, label_lookup)
        if isinstance(nested, str) and nested:
            return [nested]
    return labels


def _is_note_field(record: dict[str, Any]) -> bool:
    field_name = record.get("field_name")
    if isinstance(field_name, str) and field_name.upper() in {"NOTES", "NOTE", "REVIEW"}:
        return True
    field_obj = record.get("field")
    if isinstance(field_obj, int) and field_obj == 11:
        return True
    if isinstance(field_obj, dict):
        if field_obj.get("id") == 11:
            return True
        name = field_obj.get("name")
        if isinstance(name, str) and name.upper() in {"NOTES", "NOTE", "REVIEW"}:
            return True
    return False


def _merge_dicts(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for k, v in incoming.items():
        if v is None and k in merged and merged[k] is not None:
            continue
        if isinstance(v, list) and not v and isinstance(merged.get(k), list) and merged[k]:
            continue
        if isinstance(v, dict) and not v and isinstance(merged.get(k), dict) and merged[k]:
            continue
        merged[k] = v
    return merged


def _dedupe_preserve_order(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for val in values:
        key = json.dumps(val, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            out.append(val)
    return out


def _redact_pii_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("[REDACTED]" if k in PII_FIELDS else _redact_pii_recursive(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_pii_recursive(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Manifest exporter
# ---------------------------------------------------------------------------


class BeliManifestExporter:
    """Orchestrates full extraction and assembly of a user's Beli ranking manifest."""

    def __init__(
        self,
        client: BeliClient,
        *,
        detail_level: str = "full",
        categories: list[str] | None = None,
        include_bookmarks: bool = True,
        include_raw: bool = True,
        redact_pii: bool = False,
        refresh_businesses: bool = False,
        checkpoint_every: int = 25,
        output_path: Path | None = None,
        existing_manifest: dict[str, Any] | None = None,
        progress_fn: Callable[[str], None] | None = None,
    ) -> None:
        if detail_level not in ("fast", "full", "max"):
            raise ValueError(f"Unsupported detail_level: {detail_level}")
        self.client = client
        self.detail_level = detail_level
        self.explicit_categories = [c.strip().upper() for c in categories] if categories else None
        self.include_bookmarks = include_bookmarks
        self.include_raw = include_raw
        self.redact_pii = redact_pii
        self.refresh_businesses = refresh_businesses
        self.checkpoint_every = max(1, checkpoint_every)
        self.output_path = output_path
        self.existing_manifest = existing_manifest
        self._log = progress_fn or (lambda msg: print(msg, file=sys.stderr, flush=True))
        self.endpoints_status: dict[str, dict[str, Any]] = {}
        self.raw_endpoints: dict[str, Any] = {}

    def _fetch(
        self,
        name: str,
        path: str,
        *,
        host: str = HOST_API,
        params: dict[str, Any] | None = None,
        fallback_without_params: bool = False,
        record_raw: bool = True,
    ) -> tuple[bool, Any]:
        started = time.monotonic()
        try:
            status, data = self.client.request_json("GET", path, host=host, params=params)
            if fallback_without_params and params and (status >= 400 or (status == 200 and not extract_items(data))):
                fb_status, fb_data = self.client.request_json("GET", path, host=host, params=None)
                if fb_status == 200 and (status >= 400 or extract_items(fb_data)):
                    status, data = fb_status, fb_data
            elapsed_ms = int((time.monotonic() - started) * 1000)
            ok = 200 <= status < 300
            self.endpoints_status[name] = {
                "ok": ok,
                "status": status,
                "elapsed_ms": elapsed_ms,
                "path": path,
            }
            if record_raw:
                self.raw_endpoints[name] = data
            return ok, data
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self.endpoints_status[name] = {
                "ok": False,
                "status": None,
                "elapsed_ms": elapsed_ms,
                "path": path,
                "error": str(exc),
            }
            return False, None

    def _previous_enriched_by_biz(self) -> dict[int, dict[str, Any]]:
        if not isinstance(self.existing_manifest, dict):
            return {}
        by_biz: dict[int, dict[str, Any]] = {}
        for entry in self.existing_manifest.get("rankings", []):
            if not isinstance(entry, dict):
                continue
            biz_id = coerce_int(entry.get("business_id"))
            enrichment = entry.get("enrichment")
            if biz_id is not None and isinstance(enrichment, dict) and enrichment.get("status") == "complete":
                prev_level = enrichment.get("detail_level")
                if prev_level == self.detail_level or (prev_level == "max" and self.detail_level == "full"):
                    by_biz[biz_id] = entry
        return by_biz

    def export(self) -> dict[str, Any]:
        user_id = self.client.user_id
        self._log(f"[beli] Authenticated as user_id={user_id} (detail={self.detail_level})")

        # ------------------------------------------------------------------
        # Phase 1: Account profile & ranking summary metrics
        # ------------------------------------------------------------------
        self._log("[beli] Phase 1/4: Fetching account profile & summary metrics...")
        _, logged_in_raw = self._fetch("logged_in", "/api/user/logged-in/", host=HOST_ONBOARD)
        logged_in_items = extract_items(logged_in_raw)
        logged_in_profile = logged_in_items[0] if logged_in_items else (logged_in_raw if isinstance(logged_in_raw, dict) else None)

        _, member_raw = self._fetch("user_member", "/api/user/member/", params={"id": user_id}, fallback_without_params=True)
        _, bio_raw = self._fetch("user_bio", "/api/user/bio/", params={"id": user_id}, fallback_without_params=True)
        _, streak_raw = self._fetch("user_streak", "/api/user/streak/", params={"user": user_id}, fallback_without_params=True)
        _, app_rank_raw = self._fetch("app_rank", f"/api/app-rank/{user_id}/")
        _, count_year_raw = self._fetch("count_ranked_this_year", f"/api/count-ranked-this-year/{user_id}/")
        _, score_avg_raw = self._fetch("score_average", f"/api/score-average/{user_id}/ALL/")
        _, rank_count_raw = self._fetch("field_count_rank", f"/api/user-field-count/{user_id}/RANK/")
        _, bookmark_count_raw = self._fetch("field_count_bookmarked", f"/api/user-field-count/{user_id}/BOOKMARKED/")
        _, taste_config_raw = self._fetch("taste_profile_config", f"/api/taste-profile-config/{user_id}/")

        account = {
            "user_id": user_id,
            "profile": logged_in_profile,
            "member": member_raw,
            "bio": bio_raw,
            "streak": streak_raw,
            "app_rank": app_rank_raw,
            "count_ranked_this_year": count_year_raw,
            "score_average": score_avg_raw,
            "field_count_rank": rank_count_raw,
            "field_count_bookmarked": bookmark_count_raw,
            "taste_profile_config": taste_config_raw,
        }

        # ------------------------------------------------------------------
        # Phase 2: Core scores & all category rankings
        # ------------------------------------------------------------------
        self._log("[beli] Phase 2/4: Fetching user scores & category ranking lists...")
        _, user_scores_raw = self._fetch("user_scores", f"/api/user-scores/{user_id}/")
        _, user_scores_cached_raw = self._fetch("user_scores_cached", f"/api/user-scores-cached/{user_id}/")

        user_scores = extract_items(user_scores_raw)
        user_scores_cached = extract_items(user_scores_cached_raw)

        discovered_categories: list[str] = []
        for item in user_scores + user_scores_cached:
            if isinstance(item, dict) and isinstance(item.get("category"), str) and item["category"].strip():
                cat = item["category"].strip().upper()
                if cat not in discovered_categories:
                    discovered_categories.append(cat)

        if self.explicit_categories:
            categories_to_query = list(dict.fromkeys(self.explicit_categories))
        else:
            categories_to_query = list(dict.fromkeys([*discovered_categories, *DEFAULT_CATEGORIES]))

        rankings_raw_by_category: dict[str, list[Any]] = {}
        for cat in categories_to_query:
            ok, payload = self._fetch(
                f"get_ranking_{cat}",
                "/api/get-ranking/",
                params={"user": user_id, "category": cat},
            )
            items = extract_items(payload) if ok else []
            if items:
                rankings_raw_by_category[cat] = items
                self._log(f"  - category {cat}: {len(items)} ranked places")

        # ------------------------------------------------------------------
        # Phase 3: Associated bulk metadata (photos, notes, labels, bookmarks, feed, lists)
        # ------------------------------------------------------------------
        self._log("[beli] Phase 3/4: Fetching photos, notes/EAV fields, labels, feed & lists...")
        ok_photos, photos_raw = self._fetch(
            "user_business_photos",
            "/api/user-business-photos/",
            params={"user": user_id},
            fallback_without_params=True,
        )
        ok_notes, notes_raw = self._fetch(
            "datauserbusinesstext_sparse",
            "/api/datauserbusinesstext-sparse/",
            params={"user": user_id},
            fallback_without_params=True,
        )
        ok_tagged, tagged_raw = self._fetch(
            "tagged_users",
            "/api/tagged-users/",
            params={"user": user_id},
        )
        _, user_labels_raw = self._fetch(
            "user_business_labels",
            "/api/user-business-labels/",
            params={"user": user_id},
            fallback_without_params=True,
        )
        _, biz_labels_raw = self._fetch("business_labels", "/api/business-labels/")
        _, profile_feed_raw = self._fetch("profile_newsfeed_data", f"/api/profile-newsfeed-data/{user_id}/")
        _, user_feed_raw = self._fetch("newsfeed_user", f"/api/newsfeed-user/{user_id}/")

        _, user_guide_raw = self._fetch(
            "user_guide",
            "/api/user-guide/",
            params={"user_id": user_id},
        )
        _, user_guide_items_raw = self._fetch(
            "user_guide_items",
            "/api/user-guide-items/",
            params={"user_id": user_id},
        )
        _, published_lists_raw = self._fetch("published_lists", f"/api/published-list/{user_id}/")
        _, short_list_raw = self._fetch("short_list", f"/api/short-list/{user_id}/")

        bookmarks_by_category: dict[str, Any] = {}
        bookmarks_flat: list[Any] = []
        if self.include_bookmarks:
            bm_categories = list(dict.fromkeys([*rankings_raw_by_category.keys(), "RES", "BAR", "DES", "BAK"]))
            for cat in bm_categories:
                ok_bm, bm_payload = self._fetch(
                    f"get_bookmark_{cat}",
                    "/api/get-bookmark/",
                    params={"user": user_id, "category": cat},
                )
                if ok_bm and bm_payload:
                    bookmarks_by_category[cat] = bm_payload
                    if isinstance(bm_payload, dict) and "results" not in bm_payload:
                        for v in bm_payload.values():
                            if isinstance(v, list):
                                bookmarks_flat.extend(v)
                    else:
                        bookmarks_flat.extend(extract_items(bm_payload))
            bookmarks_flat = _dedupe_preserve_order(bookmarks_flat)

        # Build lookup indexes from bulk data
        label_lookup: dict[int, dict[str, Any]] = {}
        for lbl in extract_items(biz_labels_raw):
            if isinstance(lbl, dict) and coerce_int(lbl.get("id")) is not None:
                label_lookup[int(lbl["id"])] = lbl

        photos_by_biz: dict[int, list[dict[str, Any]]] = {}
        for photo in _filter_to_user_if_tagged(extract_items(photos_raw), user_id):
            biz_id = extract_business_id(photo)
            if biz_id is not None and isinstance(photo, dict):
                photos_by_biz.setdefault(biz_id, []).append(photo)

        text_eav_by_biz: dict[int, list[dict[str, Any]]] = {}
        for row in _filter_to_user_if_tagged(extract_items(notes_raw), user_id):
            biz_id = extract_business_id(row)
            if biz_id is not None and isinstance(row, dict):
                text_eav_by_biz.setdefault(biz_id, []).append(row)

        bool_eav_by_biz: dict[int, list[dict[str, Any]]] = {}

        tagged_users_by_biz: dict[int, list[dict[str, Any]]] = {}
        if ok_tagged and isinstance(tagged_raw, dict):
            user_by_id: dict[str, dict[str, Any]] = {}
            for u in tagged_raw.get("users") or []:
                if isinstance(u, dict) and u.get("id"):
                    user_by_id[str(u["id"])] = u
            for tag in tagged_raw.get("tags") or []:
                if not isinstance(tag, dict):
                    continue
                biz_id = coerce_int(tag.get("notification__business") or tag.get("business") or tag.get("business_id"))
                tagged_uid = tag.get("tagged") or tag.get("user") or tag.get("user_id")
                if biz_id is None:
                    continue
                if isinstance(tagged_uid, str) and tagged_uid in user_by_id:
                    tagged_users_by_biz.setdefault(biz_id, []).append(user_by_id[tagged_uid])
                else:
                    tagged_users_by_biz.setdefault(biz_id, []).append(tag)

        user_labels_by_biz: dict[int, list[dict[str, Any]]] = {}
        for row in _filter_to_user_if_tagged(extract_items(user_labels_raw), user_id):
            biz_id = extract_business_id(row)
            if biz_id is not None and isinstance(row, dict):
                user_labels_by_biz.setdefault(biz_id, []).append(row)

        feed_by_biz: dict[int, list[dict[str, Any]]] = {}
        feed_by_notif: dict[int, dict[str, Any]] = {}
        for feed_item in _dedupe_preserve_order(
            extract_items(profile_feed_raw) + extract_items(user_feed_raw)
        ):
            if not isinstance(feed_item, dict):
                continue
            biz_id = extract_business_id(feed_item)
            if biz_id is not None:
                feed_by_biz.setdefault(biz_id, []).append(feed_item)
            fid = coerce_int(feed_item.get("id"))
            if fid is not None:
                feed_by_notif[fid] = feed_item

        guide_titles: dict[int, str] = {}
        for g in extract_items(user_guide_raw):
            if isinstance(g, dict) and coerce_int(g.get("id")) is not None:
                guide_titles[int(g["id"])] = str(g.get("title") or g.get("name") or "")

        lists_by_biz: dict[int, list[dict[str, Any]]] = {}
        for item in extract_items(user_guide_items_raw):
            if not isinstance(item, dict):
                continue
            biz_id = extract_business_id(item)
            if biz_id is None:
                continue
            guide_ref = item.get("guide") or item.get("user_guide") or item.get("list")
            guide_id = coerce_int(guide_ref.get("id") if isinstance(guide_ref, dict) else guide_ref)
            lists_by_biz.setdefault(biz_id, []).append(
                {
                    "guide_id": guide_id,
                    "guide_title": guide_titles.get(guide_id) if guide_id is not None else None,
                    "raw": item,
                }
            )

        # Assemble canonical merged ranking records before Phase 4 enrichment
        rankings = self._merge_rankings(
            rankings_raw_by_category=rankings_raw_by_category,
            user_scores=user_scores,
            user_scores_cached=user_scores_cached,
            photos_by_biz=photos_by_biz,
            text_eav_by_biz=text_eav_by_biz,
            bool_eav_by_biz=bool_eav_by_biz,
            tagged_users_by_biz=tagged_users_by_biz,
            user_labels_by_biz=user_labels_by_biz,
            label_lookup=label_lookup,
            feed_by_biz=feed_by_biz,
            feed_by_notif=feed_by_notif,
            lists_by_biz=lists_by_biz,
        )

        # ------------------------------------------------------------------
        # Phase 4: Per-ranked-business enrichment (full / max)
        # ------------------------------------------------------------------
        prev_enriched = self._previous_enriched_by_biz()
        unique_biz_ids = list(dict.fromkeys(r["business_id"] for r in rankings if r.get("business_id") is not None))

        # Apply resumed enrichment data up front
        if prev_enriched:
            for r in rankings:
                prev = prev_enriched.get(r["business_id"])
                if prev:
                    self._apply_cached_enrichment(r, prev)

        recs_by_biz: dict[int, dict[str, Any]] = {}
        if self.detail_level in ("full", "max") and unique_biz_ids:
            self._log(f"[beli] Phase 4/4 ({self.detail_level}): Fetching personalized rec percentiles...")
            ok_recs, recs_raw = self._fetch(
                "user_recs",
                f"/api/recs/{user_id}/",
                host=HOST_RECS,
                record_raw=False,
            )
            if ok_recs:
                for rec in extract_items(recs_raw):
                    bid = extract_business_id(rec)
                    if bid is not None and isinstance(rec, dict):
                        recs_by_biz[bid] = rec

        if self.detail_level in ("full", "max") and unique_biz_ids:
            to_enrich = [bid for bid in unique_biz_ids if bid not in prev_enriched]
            skipped_count = len(unique_biz_ids) - len(to_enrich)
            need_per_biz_notes = not (ok_notes and bool(text_eav_by_biz))
            need_per_biz_photos = not (ok_photos and bool(photos_by_biz))
            need_per_biz_tagged = not ok_tagged

            entries_by_biz: dict[int, list[dict[str, Any]]] = {}
            for r in rankings:
                if r.get("business_id") is not None:
                    entries_by_biz.setdefault(r["business_id"], []).append(r)

            if self.detail_level == "full":
                per_biz_needed = [
                    bid
                    for bid in to_enrich
                    if self._needs_full_per_biz_calls(
                        entries_by_biz.get(bid, []),
                        need_per_biz_notes=need_per_biz_notes,
                        need_per_biz_photos=need_per_biz_photos,
                        need_per_biz_tagged=need_per_biz_tagged,
                    )
                ]
                self._log(
                    f"[beli] Phase 4/4 (full): {len(to_enrich) - len(per_biz_needed)} businesses already complete from bulk endpoints; "
                    f"fetching per-business detail for {len(per_biz_needed)} remaining (resumed={skipped_count})..."
                )
            else:
                self._log(
                    f"[beli] Phase 4/4 (max): Enriching {len(to_enrich)} ranked businesses with community metadata "
                    f"(resumed={skipped_count})..."
                )

            interrupted = False
            per_biz_processed = 0
            try:
                for idx, biz_id in enumerate(to_enrich, start=1):
                    biz_entries = entries_by_biz.get(biz_id, [])
                    made_calls = self.detail_level == "max" or self._needs_full_per_biz_calls(
                        biz_entries,
                        need_per_biz_notes=need_per_biz_notes,
                        need_per_biz_photos=need_per_biz_photos,
                        need_per_biz_tagged=need_per_biz_tagged,
                    )
                    self._enrich_business(
                        user_id=user_id,
                        biz_id=biz_id,
                        biz_entries=biz_entries,
                        need_per_biz_notes=need_per_biz_notes,
                        need_per_biz_photos=need_per_biz_photos,
                        need_per_biz_tagged=need_per_biz_tagged,
                        rec_item=recs_by_biz.get(biz_id),
                    )
                    if made_calls:
                        per_biz_processed += 1
                    if made_calls and (per_biz_processed % self.checkpoint_every == 0):
                        self._log(f"  - enriched {per_biz_processed} businesses ({idx}/{len(to_enrich)} total)")
                        if self.output_path:
                            manifest_ckpt = self._build_manifest(
                                user_id=user_id,
                                account=account,
                                rankings=rankings,
                                categories_queried=categories_to_query,
                                bookmarks_by_category=bookmarks_by_category,
                                bookmarks_flat=bookmarks_flat,
                                lists_section={
                                    "user_guides": extract_items(user_guide_raw),
                                    "user_guide_items": extract_items(user_guide_items_raw),
                                    "published_lists": extract_items(published_lists_raw),
                                    "short_list": extract_items(short_list_raw),
                                },
                                business_labels=extract_items(biz_labels_raw),
                                complete=False,
                            )
                            atomic_write_json(self.output_path, manifest_ckpt)
            except KeyboardInterrupt:
                interrupted = True
                self._log("\n[beli] Interrupted! Saving partial checkpoint manifest (re-run with --resume)...")

            manifest = self._build_manifest(
                user_id=user_id,
                account=account,
                rankings=rankings,
                categories_queried=categories_to_query,
                bookmarks_by_category=bookmarks_by_category,
                bookmarks_flat=bookmarks_flat,
                lists_section={
                    "user_guides": extract_items(user_guide_raw),
                    "user_guide_items": extract_items(user_guide_items_raw),
                    "published_lists": extract_items(published_lists_raw),
                    "short_list": extract_items(short_list_raw),
                },
                business_labels=extract_items(biz_labels_raw),
                complete=not interrupted,
            )
            if self.output_path:
                atomic_write_json(self.output_path, manifest)
            if interrupted:
                raise KeyboardInterrupt
            return manifest

        manifest = self._build_manifest(
            user_id=user_id,
            account=account,
            rankings=rankings,
            categories_queried=categories_to_query,
            bookmarks_by_category=bookmarks_by_category,
            bookmarks_flat=bookmarks_flat,
            lists_section={
                "user_guides": extract_items(user_guide_raw),
                "user_guide_items": extract_items(user_guide_items_raw),
                "published_lists": extract_items(published_lists_raw),
                "short_list": extract_items(short_list_raw),
            },
            business_labels=extract_items(biz_labels_raw),
            complete=True,
        )
        if self.output_path:
            atomic_write_json(self.output_path, manifest)
        return manifest

    def _merge_rankings(
        self,
        *,
        rankings_raw_by_category: dict[str, list[Any]],
        user_scores: list[Any],
        user_scores_cached: list[Any],
        photos_by_biz: dict[int, list[dict[str, Any]]],
        text_eav_by_biz: dict[int, list[dict[str, Any]]],
        bool_eav_by_biz: dict[int, list[dict[str, Any]]],
        tagged_users_by_biz: dict[int, list[dict[str, Any]]],
        user_labels_by_biz: dict[int, list[dict[str, Any]]],
        label_lookup: dict[int, dict[str, Any]],
        feed_by_biz: dict[int, list[dict[str, Any]]],
        feed_by_notif: dict[int, dict[str, Any]],
        lists_by_biz: dict[int, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        score_by_key: dict[tuple[int, str], dict[str, Any]] = {}
        score_by_biz: dict[int, dict[str, Any]] = {}
        for s in user_scores:
            if not isinstance(s, dict):
                continue
            bid = extract_business_id(s)
            if bid is None:
                continue
            cat = str(s.get("category") or "RES").strip().upper()
            score_by_key[(bid, cat)] = s
            score_by_biz.setdefault(bid, s)

        cached_by_key: dict[tuple[int, str], dict[str, Any]] = {}
        cached_by_biz: dict[int, dict[str, Any]] = {}
        for c in user_scores_cached:
            if not isinstance(c, dict):
                continue
            bid = extract_business_id(c)
            if bid is None:
                continue
            cat = str(c.get("category") or "RES").strip().upper()
            cached_by_key[(bid, cat)] = c
            cached_by_biz.setdefault(bid, c)

        merged_records: list[dict[str, Any]] = []
        seen_keys: set[tuple[int, str]] = set()

        # 1. Start from ordered `/api/get-ranking/` lists (preserves Beli's exact rank order)
        for cat, items in rankings_raw_by_category.items():
            for rank_pos, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                bid = extract_business_id(item)
                if bid is None:
                    continue
                item_cat = str(item.get("category") or cat).strip().upper()
                key = (bid, item_cat)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                score_rec = score_by_key.get(key) or score_by_biz.get(bid)
                cached_rec = cached_by_key.get(key) or cached_by_biz.get(bid)
                merged_records.append(
                    self._build_ranking_entry(
                        biz_id=bid,
                        category=item_cat,
                        rank_position=rank_pos,
                        ranking_rec=item,
                        score_rec=score_rec,
                        cached_rec=cached_rec,
                        photos_by_biz=photos_by_biz,
                        text_eav_by_biz=text_eav_by_biz,
                        bool_eav_by_biz=bool_eav_by_biz,
                        tagged_users_by_biz=tagged_users_by_biz,
                        user_labels_by_biz=user_labels_by_biz,
                        label_lookup=label_lookup,
                        feed_by_biz=feed_by_biz,
                        feed_by_notif=feed_by_notif,
                        lists_by_biz=lists_by_biz,
                    )
                )

        # 2. Include any entries present in user-scores / user-scores-cached missed by get-ranking
        orphan_keys: list[tuple[int, str]] = []
        for k in list(score_by_key.keys()) + list(cached_by_key.keys()):
            if k not in seen_keys and k not in orphan_keys:
                orphan_keys.append(k)

        for bid, cat in orphan_keys:
            seen_keys.add((bid, cat))
            score_rec = score_by_key.get((bid, cat))
            cached_rec = cached_by_key.get((bid, cat))
            merged_records.append(
                self._build_ranking_entry(
                    biz_id=bid,
                    category=cat,
                    rank_position=None,
                    ranking_rec=None,
                    score_rec=score_rec,
                    cached_rec=cached_rec,
                    photos_by_biz=photos_by_biz,
                    text_eav_by_biz=text_eav_by_biz,
                    bool_eav_by_biz=bool_eav_by_biz,
                    tagged_users_by_biz=tagged_users_by_biz,
                    user_labels_by_biz=user_labels_by_biz,
                    label_lookup=label_lookup,
                    feed_by_biz=feed_by_biz,
                    feed_by_notif=feed_by_notif,
                    lists_by_biz=lists_by_biz,
                )
            )

        return merged_records

    def _build_ranking_entry(
        self,
        *,
        biz_id: int,
        category: str,
        rank_position: int | None,
        ranking_rec: dict[str, Any] | None,
        score_rec: dict[str, Any] | None,
        cached_rec: dict[str, Any] | None,
        photos_by_biz: dict[int, list[dict[str, Any]]],
        text_eav_by_biz: dict[int, list[dict[str, Any]]],
        bool_eav_by_biz: dict[int, list[dict[str, Any]]],
        tagged_users_by_biz: dict[int, list[dict[str, Any]]],
        user_labels_by_biz: dict[int, list[dict[str, Any]]],
        label_lookup: dict[int, dict[str, Any]],
        feed_by_biz: dict[int, list[dict[str, Any]]],
        feed_by_notif: dict[int, dict[str, Any]],
        lists_by_biz: dict[int, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        business: dict[str, Any] = {}
        if ranking_rec:
            extracted = extract_business_dict(ranking_rec)
            if extracted:
                business = _merge_dicts(business, extracted)

        # Hydrate business from feed_item.business_full if not present yet
        matching_feeds = list(feed_by_biz.get(biz_id, []))
        notif_id = coerce_int(
            (score_rec or {}).get("notification_id")
            or (ranking_rec or {}).get("notification_id")
        )
        if notif_id is not None and notif_id in feed_by_notif:
            matching_feeds = _dedupe_preserve_order([feed_by_notif[notif_id], *matching_feeds])
        for fi in matching_feeds:
            fb = extract_business_dict(fi)
            if fb:
                business = _merge_dicts(business, fb)

        # Resolve display score (0-10 scale) with clear precedence
        score = (
            coerce_float((ranking_rec or {}).get("score"))
            if (ranking_rec or {}).get("score") is not None
            else coerce_float((score_rec or {}).get("value"))
        )
        if score is None:
            score = coerce_float((cached_rec or {}).get("value"))
        if score is None:
            score = coerce_float((ranking_rec or {}).get("value"))

        raw_value = (ranking_rec or {}).get("value")
        if raw_value is None and score_rec is not None:
            raw_value = score_rec.get("value")

        num_visits = coerce_int(
            (score_rec or {}).get("num_visits")
            or (ranking_rec or {}).get("num_visits")
        )

        # Merge visit dates
        visit_dates: list[str] = []
        if ranking_rec and isinstance(ranking_rec.get("visit_dates"), list):
            visit_dates.extend(str(d) for d in ranking_rec["visit_dates"] if d)

        # Merge labels
        labels: list[str] = []
        if cached_rec and isinstance(cached_rec.get("labels"), list):
            for lbl in cached_rec["labels"]:
                labels.extend(_extract_label_strings(lbl, label_lookup))
        for u_lbl in user_labels_by_biz.get(biz_id, []):
            labels.extend(_extract_label_strings(u_lbl, label_lookup))
        labels = list(dict.fromkeys(labels))

        # Extract notes & EAV text fields
        text_fields = list(text_eav_by_biz.get(biz_id, []))
        notes: list[str] = []
        for row in text_fields:
            val = row.get("value")
            if isinstance(val, str) and val.strip() and _is_note_field(row):
                notes.append(val)
        if ranking_rec and isinstance(ranking_rec.get("notes"), str) and ranking_rec["notes"].strip():
            notes.append(ranking_rec["notes"])
        notes = list(dict.fromkeys(notes))

        photos = list(photos_by_biz.get(biz_id, []))
        favorite_dishes = list(
            dict.fromkeys(
                str(p["favorite_dish"]).strip()
                for p in photos
                if isinstance(p.get("favorite_dish"), str) and p["favorite_dish"].strip()
            )
        )

        return {
            "ranking_id": coerce_int((ranking_rec or {}).get("id")),
            "business_id": biz_id,
            "place_id": business.get("place_id"),
            "name": business.get("name"),
            "category": category,
            "rank": rank_position,
            "score": score,
            "raw_value": raw_value,
            "num_visits": num_visits,
            "created_dt": (ranking_rec or {}).get("created_dt"),
            "latest_visit_date": (ranking_rec or {}).get("latest_visit_date"),
            "sent_dt": (score_rec or {}).get("sent_dt") or (ranking_rec or {}).get("sent_dt"),
            "notification_id": notif_id,
            "business": business,
            "notes": notes,
            "favorite_dishes": favorite_dishes,
            "labels": labels,
            "visit_dates": list(dict.fromkeys(visit_dates)),
            "tagged_users": _dedupe_preserve_order(list(tagged_users_by_biz.get(biz_id, []))),
            "photos": photos,
            "text_fields": text_fields,
            "boolean_fields": list(bool_eav_by_biz.get(biz_id, [])),
            "user_label_records": list(user_labels_by_biz.get(biz_id, [])),
            "feed_items": matching_feeds,
            "lists": list(lists_by_biz.get(biz_id, [])),
            "community": {},
            "enrichment": {
                "status": "bulk_only" if self.detail_level == "fast" else "pending",
                "detail_level": "fast" if self.detail_level == "fast" else None,
                "enriched_at": None,
            },
            "raw": {
                "ranking_record": ranking_rec,
                "score_record": score_rec,
                "cached_score_record": cached_rec,
            },
        }

    def _apply_cached_enrichment(self, entry: dict[str, Any], cached: dict[str, Any]) -> None:
        if isinstance(cached.get("business"), dict):
            entry["business"] = _merge_dicts(entry.get("business") or {}, cached["business"])
            if not entry.get("name"):
                entry["name"] = entry["business"].get("name")
            if not entry.get("place_id"):
                entry["place_id"] = entry["business"].get("place_id")
        if isinstance(cached.get("visit_dates"), list):
            entry["visit_dates"] = list(dict.fromkeys([*entry.get("visit_dates", []), *cached["visit_dates"]]))
        if isinstance(cached.get("tagged_users"), list):
            entry["tagged_users"] = _dedupe_preserve_order([*entry.get("tagged_users", []), *cached["tagged_users"]])
        if isinstance(cached.get("photos"), list) and not entry.get("photos"):
            entry["photos"] = cached["photos"]
        if isinstance(cached.get("notes"), list):
            entry["notes"] = list(dict.fromkeys([*entry.get("notes", []), *cached["notes"]]))
        if isinstance(cached.get("text_fields"), list) and not entry.get("text_fields"):
            entry["text_fields"] = cached["text_fields"]
        if isinstance(cached.get("community"), dict):
            entry["community"] = _merge_dicts(entry.get("community") or {}, cached["community"])
        entry["enrichment"] = dict(cached.get("enrichment") or {})

    def _needs_full_per_biz_calls(
        self,
        biz_entries: list[dict[str, Any]],
        *,
        need_per_biz_notes: bool,
        need_per_biz_photos: bool,
        need_per_biz_tagged: bool,
    ) -> bool:
        current_biz = biz_entries[0].get("business") if biz_entries else {}
        needs_biz_fetch = (
            self.refresh_businesses
            or not current_biz
            or not current_biz.get("name")
            or current_biz.get("lat") is None
        )
        return needs_biz_fetch or need_per_biz_notes or need_per_biz_photos or need_per_biz_tagged

    def _enrich_business(
        self,
        *,
        user_id: str,
        biz_id: int,
        biz_entries: list[dict[str, Any]],
        need_per_biz_notes: bool,
        need_per_biz_photos: bool,
        need_per_biz_tagged: bool,
        rec_item: dict[str, Any] | None,
    ) -> None:
        # 1. Business detail if missing/minimal, or refresh requested, or max mode
        current_biz = biz_entries[0].get("business") if biz_entries else {}
        needs_biz_fetch = (
            self.refresh_businesses
            or not current_biz
            or not current_biz.get("name")
            or current_biz.get("lat") is None
        )
        fetched_biz: dict[str, Any] | None = None
        if needs_biz_fetch:
            status, payload = self.client.request_json(
                "GET",
                "/api/business/",
                params={"id": biz_id, "from_business_page": "true"},
            )
            if status == 200:
                items = extract_items(payload)
                if items and isinstance(items[0], dict):
                    fetched_biz = items[0]
                elif isinstance(payload, dict) and payload.get("id") is not None:
                    fetched_biz = payload

        # 2. Visit dates on business (only needed when ranking record wasn't present or in max mode)
        visit_dates_extra: list[Any] = []
        has_ranking_rec = any((e.get("raw") or {}).get("ranking_record") for e in biz_entries)
        if not has_ranking_rec or self.detail_level == "max":
            v_status, v_payload = self.client.request_json(
                "GET", f"/api/visit-dates-on-business/{user_id}/{biz_id}/"
            )
            if v_status == 200:
                if isinstance(v_payload, dict) and isinstance(v_payload.get("visit_dates"), list):
                    visit_dates_extra = v_payload["visit_dates"]
                else:
                    visit_dates_extra = extract_items(v_payload)

        # 3. Tagged users on business (fallback only when bulk /api/tagged-users/ did not succeed)
        tagged_users: list[Any] = []
        if need_per_biz_tagged:
            t_status, t_payload = self.client.request_json(
                "GET", f"/api/tagged-users-on-business/{user_id}/{biz_id}/"
            )
            if t_status == 200:
                tagged_users = extract_items(t_payload)

        # 4. Fallback per-business notes/photos if bulk returned empty
        extra_text_fields: list[dict[str, Any]] = []
        if need_per_biz_notes:
            n_status, n_payload = self.client.request_json(
                "GET",
                "/api/datauserbusinesstext-sparse/",
                params={"user": user_id, "business": biz_id},
            )
            if n_status == 200:
                extra_text_fields = [r for r in extract_items(n_payload) if isinstance(r, dict)]

        extra_photos: list[dict[str, Any]] = []
        if need_per_biz_photos:
            p_status, p_payload = self.client.request_json(
                "GET",
                "/api/user-business-photo/",
                params={"user": user_id, "business": biz_id},
            )
            if p_status == 200:
                extra_photos = [r for r in extract_items(p_payload) if isinstance(r, dict)]

        # 5. Community / restaurant-level metadata
        community: dict[str, Any] = {}
        if rec_item is not None:
            community["rec_score"] = rec_item
        if self.detail_level == "max":
            for key, path, params in (
                ("count_rated", f"/api/business-count-rated/{biz_id}/", None),
                ("histogram", f"/api/business-histogram-data/{biz_id}/", None),
                ("occasion_counts", f"/api/countuserbusinessoccasion/{biz_id}/", None),
                ("dish_recs", "/api/dish-rec/", {"business": biz_id}),
                ("friend_text", f"/api/business-friend-text/{user_id}/{biz_id}/", None),
                ("friends_bookmarked", f"/api/friends-bookmarked/{user_id}/{biz_id}/", None),
                ("friend_scores", f"/api/scores/{user_id}/{biz_id}/", None),
            ):
                c_status, c_payload = self.client.request_json("GET", path, params=params)
                if c_status == 200:
                    community[key] = c_payload

        enriched_at = utc_now_iso()
        for entry in biz_entries:
            if fetched_biz:
                entry["business"] = _merge_dicts(entry.get("business") or {}, fetched_biz)
                if not entry.get("name"):
                    entry["name"] = entry["business"].get("name")
                if not entry.get("place_id"):
                    entry["place_id"] = entry["business"].get("place_id")
            if visit_dates_extra:
                entry["visit_dates"] = _dedupe_preserve_order(
                    [*entry.get("visit_dates", []), *visit_dates_extra]
                )
            if tagged_users:
                entry["tagged_users"] = _dedupe_preserve_order(
                    [*entry.get("tagged_users", []), *tagged_users]
                )
            if extra_text_fields:
                entry["text_fields"] = _dedupe_preserve_order(
                    [*entry.get("text_fields", []), *extra_text_fields]
                )
                extra_notes = [
                    r["value"]
                    for r in extra_text_fields
                    if isinstance(r.get("value"), str) and r["value"].strip() and _is_note_field(r)
                ]
                entry["notes"] = list(dict.fromkeys([*entry.get("notes", []), *extra_notes]))
            if extra_photos:
                entry["photos"] = _dedupe_preserve_order([*entry.get("photos", []), *extra_photos])
                extra_dishes = [
                    str(p["favorite_dish"]).strip()
                    for p in extra_photos
                    if isinstance(p.get("favorite_dish"), str) and p["favorite_dish"].strip()
                ]
                entry["favorite_dishes"] = list(
                    dict.fromkeys([*entry.get("favorite_dishes", []), *extra_dishes])
                )
            if community:
                entry["community"] = _merge_dicts(entry.get("community") or {}, community)
            entry["enrichment"] = {
                "status": "complete",
                "detail_level": self.detail_level,
                "enriched_at": enriched_at,
            }

    def _build_manifest(
        self,
        *,
        user_id: str,
        account: dict[str, Any],
        rankings: list[dict[str, Any]],
        categories_queried: list[str],
        bookmarks_by_category: dict[str, Any],
        bookmarks_flat: list[Any],
        lists_section: dict[str, Any],
        business_labels: list[Any],
        complete: bool,
    ) -> dict[str, Any]:
        rankings_by_category: dict[str, list[int]] = {}
        for r in rankings:
            cat = r.get("category") or "UNKNOWN"
            rankings_by_category.setdefault(cat, []).append(r["business_id"])

        username = None
        if isinstance(account.get("profile"), dict):
            username = account["profile"].get("username")

        api_rank_count = None
        fc = account.get("field_count_rank")
        if isinstance(fc, int):
            api_rank_count = fc
        elif isinstance(fc, dict):
            for k in ("count", "results", "value"):
                if coerce_int(fc.get(k)) is not None:
                    api_rank_count = coerce_int(fc.get(k))
                    break

        enriched_biz = len(
            {
                r["business_id"]
                for r in rankings
                if isinstance(r.get("enrichment"), dict) and r["enrichment"].get("status") == "complete"
            }
        )

        account_out = _redact_pii_recursive(account) if self.redact_pii else account
        raw_out = self.raw_endpoints
        if self.redact_pii and "logged_in" in raw_out:
            raw_out = dict(raw_out)
            raw_out["logged_in"] = _redact_pii_recursive(raw_out["logged_in"])

        manifest: dict[str, Any] = {
            "manifest_meta": {
                "schema_version": SCHEMA_VERSION,
                "exported_at": utc_now_iso(),
                "complete": complete,
                "detail_level": self.detail_level,
                "api_reference": API_REFERENCE_URL,
                "user_id": user_id,
                "username": username,
                "pii_redacted": self.redact_pii,
                "requests_made": self.client.request_count,
                "categories_queried": categories_queried,
                "categories_with_rankings": list(rankings_by_category.keys()),
                "counts": {
                    "rankings_total": len(rankings),
                    "rankings_by_category": {k: len(v) for k, v in rankings_by_category.items()},
                    "api_reported_rank_count": api_rank_count,
                    "unique_businesses_ranked": len({r["business_id"] for r in rankings}),
                    "enriched_businesses": enriched_biz,
                    "bookmarks_total": len(bookmarks_flat),
                    "photos_total": sum(len(r.get("photos", [])) for r in rankings),
                    "notes_total": sum(len(r.get("notes", [])) for r in rankings),
                },
                "endpoints_status": self.endpoints_status,
            },
            "account": account_out,
            "rankings": rankings,
            "rankings_by_category": rankings_by_category,
            "bookmarks": {
                "count": len(bookmarks_flat),
                "items": bookmarks_flat,
                "by_category": bookmarks_by_category,
            },
            "lists": lists_section,
            "lookup_tables": {
                "business_labels": business_labels,
            },
        }
        if self.include_raw:
            manifest["raw_endpoints"] = raw_out
        return manifest


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Export all Beli ranking data and associated metadata into a local JSON manifest "
            "(based on https://github.com/ProjectBarks/beli-api)."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output manifest JSON path (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--detail",
        choices=("fast", "full", "max"),
        default="full",
        help=(
            "Metadata depth: 'fast' (bulk endpoints only, ~10s), "
            "'full' (default: bulk + per-business visit dates, tagged users, full business details), "
            "'max' (full + community histograms, rated counts, dish recs, friend scores, rec percentiles)."
        ),
    )
    parser.add_argument(
        "--categories",
        type=str,
        default=None,
        help="Comma-separated category codes to fetch (default: auto-discover from scores + standard codes).",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from an existing manifest at --output, skipping already-enriched businesses.",
    )
    parser.add_argument(
        "--refresh-businesses",
        action="store_true",
        help="Always call /api/business/ for each ranked place in full mode even if embedded data exists.",
    )
    parser.add_argument(
        "--skip-bookmarks",
        action="store_true",
        help="Skip fetching Want-to-Try bookmarks.",
    )
    parser.add_argument(
        "--omit-raw",
        action="store_true",
        help="Omit top-level `raw_endpoints` blob to produce a smaller manifest file.",
    )
    parser.add_argument(
        "--redact-pii",
        action="store_true",
        help="Redact email, phone_no, sessions, and referral fields from the saved manifest.",
    )
    parser.add_argument(
        "--min-interval-ms",
        type=int,
        default=DEFAULT_MIN_INTERVAL_MS,
        help=f"Minimum delay between API requests in milliseconds (default: {DEFAULT_MIN_INTERVAL_MS}).",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=25,
        help="Save progress to --output every N enriched businesses (default: 25).",
    )

    auth_group = parser.add_argument_group("Authentication")
    auth_group.add_argument("--email", default=None, help="Beli account email (or BELI_EMAIL env var).")
    auth_group.add_argument(
        "--phone",
        default=None,
        help="Beli account phone number in E.164 format, e.g. +15551234567 (or BELI_PHONE env var).",
    )
    auth_group.add_argument(
        "--password",
        default=None,
        help="Beli password (prefer --keychain, --password-stdin, --password-file, or interactive prompt).",
    )
    auth_group.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read Beli password from stdin (avoids storing passwords in files or shell history).",
    )
    auth_group.add_argument(
        "--password-file",
        type=Path,
        default=None,
        help="Read Beli password from a file or bash process substitution, e.g. <(security find-generic-password ...).",
    )
    auth_group.add_argument(
        "--keychain",
        action="store_true",
        help=(
            f"Read Beli password from macOS Keychain via `security find-generic-password` "
            f"(service: {DEFAULT_KEYCHAIN_SERVICE}, account: --email or --phone)."
        ),
    )
    auth_group.add_argument(
        "--keychain-service",
        default=DEFAULT_KEYCHAIN_SERVICE,
        help=f"macOS Keychain service name used with --keychain (default: {DEFAULT_KEYCHAIN_SERVICE}).",
    )
    auth_group.add_argument(
        "--refresh-token",
        default=None,
        help="Existing 7-day refresh token (or BELI_REFRESH_TOKEN env var).",
    )
    auth_group.add_argument(
        "--access-token",
        default=None,
        help="Existing 20-minute access token (or BELI_ACCESS_TOKEN env var).",
    )
    auth_group.add_argument(
        "--session-file",
        type=Path,
        default=DEFAULT_SESSION_PATH,
        help=f"Local file (chmod 600) to cache refresh/access tokens for 7 days (default: {DEFAULT_SESSION_PATH}).",
    )
    auth_group.add_argument(
        "--no-save-session",
        action="store_true",
        help="Do not read or write the local session token cache file.",
    )
    auth_group.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional .env file to load BELI_* variables from (default: .env).",
    )
    auth_group.add_argument(
        "--user-agent",
        default=None,
        help="Custom browser User-Agent header (default: random realistic browser UA).",
    )
    auth_group.add_argument(
        "--origin",
        default=DEFAULT_ORIGIN,
        help=f"Mandatory Origin header (default: {DEFAULT_ORIGIN}).",
    )
    return parser


def read_password_from_keychain(account: str, service: str = DEFAULT_KEYCHAIN_SERVICE) -> str:
    """Read a password stored encrypted in the macOS Keychain."""
    try:
        proc = subprocess.run(
            ["security", "find-generic-password", "-a", account, "-s", service, "-w"],
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise BeliApiError("macOS `security` CLI not found; --keychain is supported on macOS.") from exc
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        raise BeliApiError(
            f"Could not read password from macOS Keychain for account={account!r}, service={service!r}. "
            f"Store it first with: security add-generic-password -U -a {account!r} -s {service!r} -w"
            + (f" ({err})" if err else "")
        )
    return proc.stdout.rstrip("\r\n")


def resolve_credentials(args: argparse.Namespace) -> dict[str, str | None]:
    dotenv = load_dotenv_file(args.env_file) if args.env_file else {}

    def pick(cli_val: str | None, env_key: str) -> str | None:
        return cli_val or os.environ.get(env_key) or dotenv.get(env_key)

    email = pick(args.email, "BELI_EMAIL")
    phone = pick(args.phone, "BELI_PHONE") or pick(None, "BELI_PHONE_NO")
    password = pick(args.password, "BELI_PASSWORD")
    refresh_token = pick(args.refresh_token, "BELI_REFRESH_TOKEN")
    access_token = pick(args.access_token, "BELI_ACCESS_TOKEN")

    if not password and getattr(args, "password_stdin", False):
        password = sys.stdin.read().rstrip("\r\n") or None
    if not password and getattr(args, "password_file", None):
        password = Path(args.password_file).read_text(encoding="utf-8").rstrip("\r\n") or None

    session_file: Path | None = None if args.no_save_session else args.session_file
    has_cached_token = False
    if session_file and session_file.is_file():
        try:
            cached = json.loads(session_file.read_text(encoding="utf-8"))
            if isinstance(cached, dict) and (
                not is_token_expired(cached.get("access"))
                or not is_token_expired(cached.get("refresh"))
            ):
                has_cached_token = True
        except Exception:
            pass

    has_live_token = (
        not is_token_expired(access_token)
        or not is_token_expired(refresh_token)
        or has_cached_token
    )

    if not has_live_token and not password and getattr(args, "keychain", False):
        account = email or phone
        if not account:
            raise BeliApiError("--keychain requires --email or --phone (or BELI_EMAIL/BELI_PHONE).")
        service = getattr(args, "keychain_service", DEFAULT_KEYCHAIN_SERVICE)
        password = read_password_from_keychain(account, service)

    if not has_live_token and not ((email or phone) and password):
        if sys.stdin.isatty():
            print("No active Beli session token found. Log in to your Beli account:", file=sys.stderr)
            if not (email or phone):
                ident = input("Beli email or phone (+1...): ").strip()
                if "@" in ident:
                    email = ident
                elif ident:
                    phone = ident
            if not password:
                password = getpass.getpass("Beli password: ")

    return {
        "email": email,
        "phone_no": phone,
        "password": password,
        "refresh_token": refresh_token or "",
        "access_token": access_token or "",
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    try:
        creds = resolve_credentials(args)
    except BeliApiError as exc:
        print(f"[beli] Error: {exc}", file=sys.stderr)
        return 1
    session_path = None if args.no_save_session else args.session_file

    existing_manifest: dict[str, Any] | None = None
    if args.resume and args.output.is_file():
        try:
            loaded = json.loads(args.output.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing_manifest = loaded
                print(f"[beli] Loaded existing manifest for resume: {args.output}", file=sys.stderr)
        except Exception as exc:
            print(f"[beli] Warning: could not parse existing manifest for --resume ({exc}); starting fresh.", file=sys.stderr)

    client = BeliClient(
        email=creds["email"],
        phone_no=creds["phone_no"],
        password=creds["password"],
        access_token=creds["access_token"] or "",
        refresh_token=creds["refresh_token"] or "",
        user_agent=args.user_agent or os.environ.get("BELI_USER_AGENT"),
        origin=args.origin,
        min_interval_ms=args.min_interval_ms,
        session_path=session_path,
    )

    categories = [c for c in args.categories.split(",") if c.strip()] if args.categories else None
    exporter = BeliManifestExporter(
        client,
        detail_level=args.detail,
        categories=categories,
        include_bookmarks=not args.skip_bookmarks,
        include_raw=not args.omit_raw,
        redact_pii=args.redact_pii,
        refresh_businesses=args.refresh_businesses,
        checkpoint_every=args.checkpoint_every,
        output_path=args.output,
        existing_manifest=existing_manifest,
    )

    try:
        manifest = exporter.export()
    except KeyboardInterrupt:
        print(f"[beli] Saved partial manifest to {args.output}. Re-run with --resume to continue.", file=sys.stderr)
        return 130
    except BeliApiError as exc:
        print(f"[beli] Error: {exc}", file=sys.stderr)
        return 1

    counts = manifest["manifest_meta"]["counts"]
    print(
        f"[beli] Done! Saved {counts['rankings_total']} rankings "
        f"({counts['rankings_by_category']}) + {counts['bookmarks_total']} bookmarks, "
        f"{counts['photos_total']} photos, {counts['notes_total']} notes to {args.output}",
        file=sys.stderr,
    )
    if (
        counts["api_reported_rank_count"] is not None
        and counts["api_reported_rank_count"] != counts["rankings_total"]
    ):
        print(
            f"[beli] Note: API reported RANK count={counts['api_reported_rank_count']}, "
            f"manifest captured={counts['rankings_total']} "
            "(check `manifest_meta.endpoints_status` if a category was skipped).",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
