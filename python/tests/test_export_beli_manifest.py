from __future__ import annotations

import base64
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import time
from typing import Any
import urllib.parse

from ranknorm import redistribute

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "export_beli_manifest.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("export_beli_manifest", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_beli_manifest"] = module
    spec.loader.exec_module(module)
    return module


mod = _load_script_module()

TEST_USER_ID = "11111111-2222-3333-4444-555555555555"


def _make_jwt(claims: dict[str, Any]) -> str:
    header = (
        base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(json.dumps(claims).encode("utf-8"))
        .decode()
        .rstrip("=")
    )
    return f"{header}.{payload}.sig"


def _live_access_token(user_id: str = TEST_USER_ID, ttl: int = 1200) -> str:
    return _make_jwt(
        {"token_type": "access", "user_id": user_id, "exp": int(time.time()) + ttl}
    )


def _expired_access_token(user_id: str = TEST_USER_ID) -> str:
    return _make_jwt(
        {"token_type": "access", "user_id": user_id, "exp": int(time.time()) - 300}
    )


def _live_refresh_token(user_id: str = TEST_USER_ID, ttl: int = 604800) -> str:
    return _make_jwt(
        {"token_type": "refresh", "user_id": user_id, "exp": int(time.time()) + ttl}
    )


class FakeBeliServer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []
        self.fail_once_paths: dict[str, int] = {}
        self.require_fresh_token: str | None = None
        self.access_token = _live_access_token()
        self.refresh_token = _live_refresh_token()

    def __call__(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        timeout: float,
    ):
        parsed_body = json.loads(body.decode("utf-8")) if body else None
        self.calls.append((method, url, dict(headers), parsed_body))

        # Verify mandatory Beli headers from ProjectBarks/beli-api
        assert headers.get("Origin"), "Origin header must be present"
        assert headers.get("User-Agent"), "User-Agent header must be present"

        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path in self.fail_once_paths:
            status = self.fail_once_paths.pop(path)
            return mod.HttpResponse(
                status=status,
                body=json.dumps({"detail": "temporary error"}).encode("utf-8"),
                headers={"retry-after": "0"},
            )

        if path == "/api/token/":
            assert parsed_body and parsed_body.get("password") == "secret"
            assert parsed_body.get("email") or parsed_body.get("phone_no")
            return mod.HttpResponse(
                status=200,
                body=json.dumps(
                    {"access": self.access_token, "refresh": self.refresh_token}
                ).encode("utf-8"),
            )

        if path == "/api/token/refresh/":
            assert parsed_body and parsed_body.get("refresh") == self.refresh_token
            self.access_token = _live_access_token()
            self.require_fresh_token = self.access_token
            return mod.HttpResponse(
                status=200,
                body=json.dumps({"access": self.access_token}).encode("utf-8"),
            )

        auth = headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return mod.HttpResponse(status=401, body=b'{"detail":"no auth"}')
        if self.require_fresh_token and auth != f"Bearer {self.require_fresh_token}":
            return mod.HttpResponse(status=401, body=b'{"detail":"token expired"}')

        return self._route_authenticated(path, qs)

    def _json(self, data: Any, status: int = 200):
        return mod.HttpResponse(status=status, body=json.dumps(data).encode("utf-8"))

    def _route_authenticated(self, path: str, qs: dict[str, list[str]]):
        uid = TEST_USER_ID

        if path == "/api/user/logged-in/":
            return self._json(
                {
                    "count": 1,
                    "results": [
                        {
                            "id": uid,
                            "username": "foodie42",
                            "full_name": "Test Diner",
                            "email": "diner@example.com",
                            "phone_no": "+15551234567",
                            "home_city": "New York, NY",
                            "sessions": [{"id": "sess-1"}],
                            "referrer": "friend-uuid",
                        }
                    ],
                }
            )
        if path == "/api/user/member/":
            return self._json({"results": [{"id": uid, "tier": "vip"}]})
        if path == "/api/user/bio/":
            return self._json({"bio": "Always hungry"})
        if path == "/api/user/streak/":
            return self._json({"streak": 7})
        if path == f"/api/app-rank/{uid}/":
            return self._json({"rank": 120})
        if path == f"/api/count-ranked-this-year/{uid}/":
            return self._json({"count": 3})
        if path == f"/api/score-average/{uid}/ALL/":
            return self._json({"average": 8.6})
        if path == f"/api/user-field-count/{uid}/RANK/":
            return self._json({"count": 3})
        if path == f"/api/user-field-count/{uid}/BOOKMARKED/":
            return self._json({"count": 1})
        if path == f"/api/taste-profile-config/{uid}/":
            return self._json({"enabled": True})

        # Bare list envelope test (no `results` wrapper)
        if path == f"/api/user-scores/{uid}/":
            return self._json(
                [
                    {
                        "user_id": uid,
                        "business_id": 101,
                        "value": 9.3,
                        "category": "RES",
                        "num_visits": 3,
                        "notification_id": 9001,
                        "sent_dt": "2026-06-01T12:00:00Z",
                    },
                    {
                        "user_id": uid,
                        "business_id": 102,
                        "value": 8.4,
                        "category": "RES",
                        "num_visits": 1,
                        "notification_id": 9002,
                        "sent_dt": "2026-06-05T12:00:00Z",
                    },
                    {
                        "user_id": uid,
                        "business_id": 201,
                        "value": 8.9,
                        "category": "CUSTOMCAT",
                        "num_visits": 2,
                        "notification_id": 9003,
                        "sent_dt": "2026-06-10T12:00:00Z",
                    },
                ]
            )

        if path == f"/api/user-scores-cached/{uid}/":
            return self._json(
                {
                    "results": [
                        {
                            "user_id": uid,
                            "business_id": 101,
                            "value": 9.3,
                            "category": "RES",
                            "labels": ["Date Night"],
                        },
                        {
                            "user_id": uid,
                            "business_id": 201,
                            "value": 8.9,
                            "category": "CUSTOMCAT",
                            "labels": ["Late Night"],
                        },
                    ]
                }
            )

        if path == "/api/get-ranking/":
            cat = (qs.get("category") or [""])[0]
            page = (qs.get("page") or ["1"])[0]
            if cat == "RES" and page == "1":
                next_page_url = (
                    f"{mod.HOST_API}/api/get-ranking/?user={uid}&category=RES&page=2"
                )
                return self._json(
                    {
                        "count": 2,
                        "next": next_page_url,
                        "previous": None,
                        "results": [
                            {
                                "id": 5001,
                                "user": uid,
                                "category": "RES",
                                "score": 9.3,
                                "value": 9.3,
                                "visit_dates": ["2026-05-01"],
                                "created_dt": "2026-05-02T01:00:00Z",
                                "extra_beli_flag": "kept-in-raw",
                                "business": {
                                    "id": 101,
                                    "place_id": "ChIJ101",
                                    "name": "Golden Noodle",
                                    "city": "New York",
                                    "neighborhood": "West Village",
                                    "lat": 40.7336,
                                    "lng": -74.0027,
                                    "cuisines": ["Ramen"],
                                    "price_key": "$$",
                                },
                            }
                        ],
                    }
                )
            if cat == "RES" and page == "2":
                return self._json(
                    {
                        "count": 2,
                        "next": None,
                        "previous": "prev",
                        "results": [
                            {
                                "id": 5002,
                                "user": uid,
                                "category": "RES",
                                "score": 8.4,
                                "value": 8.4,
                                "visit_dates": ["2026-06-05"],
                                "created_dt": "2026-06-05T14:00:00Z",
                                "business": {
                                    "id": 102,
                                    "name": "Sunny Bistro",
                                },
                            }
                        ],
                    }
                )
            return self._json({"results": []})

        if path == "/api/user-business-photos/":
            return self._json(
                {
                    "results": [
                        {
                            "id": 701,
                            "user": uid,
                            "business": 101,
                            "image": "https://photos2.beliapp.cloud/101.jpg",
                            "favorite_dish": "Spicy Miso Ramen",
                            "description": "Broth was unreal",
                        }
                    ]
                }
            )

        if path == "/api/datauserbusinesstext-sparse/":
            return self._json(
                {
                    "results": [
                        {
                            "user": uid,
                            "business": 101,
                            "field": {"id": 11, "name": "NOTES"},
                            "value": "Sit at the counter.",
                        }
                    ]
                }
            )

        if path == "/api/closedatauserbusinessboolean/":
            return self._json(
                {
                    "results": [
                        {
                            "user": uid,
                            "business": 101,
                            "field_name": "REVISIT",
                            "value": True,
                        }
                    ]
                }
            )

        if path == "/api/tagged-users/":
            return self._json(
                {
                    "tags": [{"tagged": "friend-1", "notification__business": 101}],
                    "users": [{"id": "friend-1", "username": "alex"}],
                }
            )

        if path == "/api/business-labels/":
            return self._json(
                {"results": [{"id": 55, "name": "MICHELIN", "display": "Michelin Bib"}]}
            )

        if path == "/api/user-business-labels/":
            return self._json(
                {"results": [{"user": uid, "business": 101, "label": 55}]}
            )

        if path == f"/api/profile-newsfeed-data/{uid}/":
            return self._json(
                {
                    "results": [
                        {
                            "id": 9001,
                            "event_type": "ADD",
                            "business": 101,
                            "score": 9.3,
                            "body": "Ranked Golden Noodle",
                        }
                    ]
                }
            )

        if path == f"/api/newsfeed-user/{uid}/":
            return self._json({"results": []})

        if path == "/api/user-guide/":
            return self._json({"results": [{"id": 300, "title": "NYC Favorites"}]})

        if path == "/api/user-guide-items/":
            return self._json({"results": [{"id": 301, "guide": 300, "business": 101}]})

        if path == f"/api/published-list/{uid}/":
            return self._json({"results": []})

        if path == f"/api/short-list/{uid}/":
            return self._json({"results": []})

        if path == "/api/get-bookmark/":
            cat = (qs.get("category") or [""])[0]
            if cat == "RES":
                return self._json(
                    {
                        "Restaurants": [
                            {
                                "id": 801,
                                "user": uid,
                                "business": {"id": 999, "name": "Try Me"},
                            }
                        ]
                    }
                )
            return self._json({})

        if path == "/api/business/":
            bid = int((qs.get("id") or ["0"])[0])
            return self._json(
                {
                    "count": 1,
                    "results": [
                        {
                            "id": bid,
                            "place_id": f"ChIJ{bid}",
                            "name": f"Hydrated Place {bid}",
                            "city": "New York",
                            "lat": 40.71,
                            "lng": -74.0,
                            "cuisines": ["Bistro"],
                        }
                    ],
                }
            )

        if path.startswith(f"/api/visit-dates-on-business/{uid}/"):
            bid = int(path.rstrip("/").split("/")[-1])
            return self._json({"results": [f"2026-07-0{bid % 9}"]})

        if path.startswith(f"/api/tagged-users-on-business/{uid}/"):
            return self._json({"results": [{"id": "friend-1", "username": "alex"}]})

        if path.startswith(f"/api/scores/{uid}/"):
            return self._json(
                [
                    {
                        "user_id": "friend-1",
                        "business_id": 101,
                        "value": 9.0,
                        "category": "RES",
                    }
                ]
            )

        if path == f"/api/recs/{uid}/":
            return self._json([{"business_id": 101, "expected_percentile": 0.96}])

        if path.startswith("/api/business-count-rated/"):
            return self._json({"count": 420})
        if path.startswith("/api/business-histogram-data/"):
            return self._json({"buckets": [1, 5, 20, 80]})
        if path.startswith("/api/countuserbusinessoccasion/"):
            return self._json({"date_night": 14})
        if path == "/api/dish-rec/":
            return self._json({"results": ["Spicy Miso Ramen"]})
        if path.startswith(f"/api/business-friend-text/{uid}/"):
            return self._json({"text": "3 friends loved this"})
        if path.startswith(f"/api/friends-bookmarked/{uid}/"):
            return self._json({"results": [{"id": "friend-2", "username": "sam"}]})

        return self._json({"detail": f"Unhandled path {path}"}, status=404)


def test_jwt_and_phone_login_and_session_cache(tmp_path: Path):
    server = FakeBeliServer()
    session_file = tmp_path / ".beli-session.json"

    client = mod.BeliClient(
        phone_no="+15551234567",
        password="secret",
        min_interval_ms=0,
        session_path=session_file,
        transport=server,
        sleep_fn=lambda _: None,
    )
    assert client.user_id == TEST_USER_ID
    assert session_file.is_file()
    mode = stat.S_IMODE(session_file.stat().st_mode)
    assert mode == 0o600

    # Verify phone_no was sent (not email)
    login_call = server.calls[0]
    assert login_call[1].endswith("/api/token/")
    assert login_call[3] == {"phone_no": "+15551234567", "password": "secret"}

    # Second client resumes from session file without password or login call
    before_calls = len(server.calls)
    resumed = mod.BeliClient(
        min_interval_ms=0,
        session_path=session_file,
        transport=server,
        sleep_fn=lambda _: None,
    )
    assert resumed.user_id == TEST_USER_ID
    assert len(server.calls) == before_calls


def test_token_refresh_on_expiry_and_retry_on_429_503():
    server = FakeBeliServer()
    server.fail_once_paths[f"/api/app-rank/{TEST_USER_ID}/"] = 503
    sleeps: list[float] = []

    client = mod.BeliClient(
        access_token=_expired_access_token(),
        refresh_token=server.refresh_token,
        min_interval_ms=0,
        transport=server,
        sleep_fn=sleeps.append,
    )

    status, data = client.request_json("GET", f"/api/app-rank/{TEST_USER_ID}/")
    assert status == 200
    assert data == {"rank": 120}
    assert any(call[1].endswith("/api/token/refresh/") for call in server.calls)
    assert not any(call[1].endswith("/api/token/") for call in server.calls)
    assert len(sleeps) >= 1


def test_full_export_merges_all_metadata_and_works_with_ranknorm(tmp_path: Path):
    server = FakeBeliServer()
    out_path = tmp_path / "beli-manifest.json"
    client = mod.BeliClient(
        email="diner@example.com",
        password="secret",
        min_interval_ms=0,
        transport=server,
        sleep_fn=lambda _: None,
    )

    exporter = mod.BeliManifestExporter(
        client,
        detail_level="full",
        output_path=out_path,
        checkpoint_every=2,
        progress_fn=lambda _: None,
    )
    manifest = exporter.export()

    assert out_path.is_file()
    saved = json.loads(out_path.read_text(encoding="utf-8"))
    assert manifest == saved
    assert saved["manifest_meta"]["complete"] is True
    assert saved["manifest_meta"]["counts"]["rankings_total"] == 3
    assert saved["manifest_meta"]["counts"]["api_reported_rank_count"] == 3
    assert saved["manifest_meta"]["counts"]["bookmarks_total"] == 1
    assert "CUSTOMCAT" in saved["manifest_meta"]["categories_queried"]

    by_biz = {r["business_id"]: r for r in saved["rankings"]}
    assert set(by_biz.keys()) == {101, 102, 201}

    # Place 101: merged from page 1 of get-ranking + scores + bulk metadata
    r101 = by_biz[101]
    assert r101["rank"] == 1
    assert r101["score"] == 9.3
    assert r101["name"] == "Golden Noodle"
    assert r101["notes"] == ["Sit at the counter."]
    assert r101["favorite_dishes"] == ["Spicy Miso Ramen"]
    assert "Date Night" in r101["labels"]
    assert "Michelin Bib" in r101["labels"]
    assert "2026-05-01" in r101["visit_dates"]
    assert r101["tagged_users"] == [{"id": "friend-1", "username": "alex"}]
    assert len(r101["photos"]) == 1
    assert len(r101["feed_items"]) == 1
    assert r101["community"]["rec_score"]["expected_percentile"] == 0.96
    assert r101["lists"][0]["guide_title"] == "NYC Favorites"
    assert r101["raw"]["ranking_record"]["extra_beli_flag"] == "kept-in-raw"
    assert r101["enrichment"]["status"] == "complete"

    # Place 102: came from DRF page 2 and lacked lat/lng so /api/business/ hydrated it
    r102 = by_biz[102]
    assert r102["rank"] == 2
    assert r102["name"] == "Sunny Bistro"
    assert r102["business"]["lat"] == 40.71

    # Place 201: orphan in user-scores (not in get-ranking), still preserved & hydrated
    r201 = by_biz[201]
    assert r201["category"] == "CUSTOMCAT"
    assert r201["score"] == 8.9
    assert r201["name"] == "Hydrated Place 201"
    assert "Late Night" in r201["labels"]

    # Directly compatible with ranknorm.redistribute
    normalized = redistribute(saved["rankings"], score_getter=lambda r: r["score"])
    assert len(normalized) == 3
    assert all(1.0 < item["score"] <= 10.0 for item in normalized)


def test_resume_skips_already_enriched_businesses(tmp_path: Path):
    server = FakeBeliServer()
    out_path = tmp_path / "beli-manifest.json"
    client = mod.BeliClient(
        email="diner@example.com",
        password="secret",
        min_interval_ms=0,
        transport=server,
        sleep_fn=lambda _: None,
    )

    first = mod.BeliManifestExporter(
        client,
        detail_level="full",
        output_path=out_path,
        progress_fn=lambda _: None,
    ).export()

    server.calls.clear()
    mod.BeliManifestExporter(
        client,
        detail_level="full",
        output_path=out_path,
        existing_manifest=first,
        progress_fn=lambda _: None,
    ).export()

    # None of the per-business visit/tag endpoints should have been re-called
    per_biz_calls = [
        url
        for _, url, _, _ in server.calls
        if "/api/visit-dates-on-business/" in url
        or "/api/tagged-users-on-business/" in url
    ]
    assert per_biz_calls == []


def test_max_detail_and_pii_redaction_and_fast_mode():
    server = FakeBeliServer()
    client = mod.BeliClient(
        email="diner@example.com",
        password="secret",
        min_interval_ms=0,
        transport=server,
        sleep_fn=lambda _: None,
    )

    max_manifest = mod.BeliManifestExporter(
        client,
        detail_level="max",
        redact_pii=True,
        include_raw=False,
        progress_fn=lambda _: None,
    ).export()

    assert "raw_endpoints" not in max_manifest
    profile = max_manifest["account"]["profile"]
    assert profile["email"] == "[REDACTED]"
    assert profile["phone_no"] == "[REDACTED]"
    assert profile["sessions"] == "[REDACTED]"
    assert profile["username"] == "foodie42"

    r101 = next(r for r in max_manifest["rankings"] if r["business_id"] == 101)
    assert r101["community"]["count_rated"] == {"count": 420}
    assert r101["community"]["histogram"] == {"buckets": [1, 5, 20, 80]}
    assert r101["community"]["friend_scores"][0]["user_id"] == "friend-1"
    assert r101["community"]["rec_score"]["expected_percentile"] == 0.96

    # Fast mode skips per-business enrichment
    server.calls.clear()
    fast_manifest = mod.BeliManifestExporter(
        client,
        detail_level="fast",
        progress_fn=lambda _: None,
    ).export()
    assert all(
        r["enrichment"]["status"] == "bulk_only" for r in fast_manifest["rankings"]
    )
    assert not any(
        "/api/visit-dates-on-business/" in url for _, url, _, _ in server.calls
    )


def test_secure_password_sources_file_stdin_and_keychain(tmp_path: Path, monkeypatch):
    pw_file = tmp_path / "pw.txt"
    pw_file.write_text("from-file\n", encoding="utf-8")

    parser = mod.build_arg_parser()

    # --password-file
    args_file = parser.parse_args(
        [
            "--email",
            "diner@example.com",
            "--password-file",
            str(pw_file),
            "--no-save-session",
            "--env-file",
            str(tmp_path / "missing.env"),
        ]
    )
    creds_file = mod.resolve_credentials(args_file)
    assert creds_file["password"] == "from-file"

    # --password-stdin
    monkeypatch.setattr(sys, "stdin", io.StringIO("from-stdin\n"))
    args_stdin = parser.parse_args(
        [
            "--email",
            "diner@example.com",
            "--password-stdin",
            "--no-save-session",
            "--env-file",
            str(tmp_path / "missing.env"),
        ]
    )
    creds_stdin = mod.resolve_credentials(args_stdin)
    assert creds_stdin["password"] == "from-stdin"

    # --keychain
    class _FakeProc:
        returncode = 0
        stdout = "from-keychain\n"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: _FakeProc())
    args_kc = parser.parse_args(
        [
            "--email",
            "diner@example.com",
            "--keychain",
            "--no-save-session",
            "--env-file",
            str(tmp_path / "missing.env"),
        ]
    )
    creds_kc = mod.resolve_credentials(args_kc)
    assert creds_kc["password"] == "from-keychain"
