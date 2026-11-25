# Beli Ranking Manifest Export

`scripts/export_beli_manifest.py` is a standalone, zero-dependency Python 3.10+ script that fetches all of your Beli ranking data and associated metadata using the reverse-engineered Beli API documented in [ProjectBarks/beli-api](https://github.com/ProjectBarks/beli-api) and writes everything to a single local JSON manifest (`data/beli-manifest.json` by default).

Both `data/beli-manifest*.json` and `.beli-session*.json` are gitignored so your personal account data and auth tokens are never accidentally committed.

## Quickstart

```bash
# Interactive login (prompts for email or E.164 phone number + password)
python3 scripts/export_beli_manifest.py
```

On first run, the script exchanges your credentials via `POST /api/token/` and caches the 7-day refresh token in `.beli-session.json` (`chmod 600`), so subsequent runs reuse your session without re-entering your password.

You can also authenticate via environment variables (or a local `.env` file):

```bash
# Email login
BELI_EMAIL="you@example.com" BELI_PASSWORD="your-password" \
  python3 scripts/export_beli_manifest.py

# Phone login (E.164 format)
BELI_PHONE="+15551234567" BELI_PASSWORD="your-password" \
  python3 scripts/export_beli_manifest.py

# Reuse an existing refresh token directly
BELI_REFRESH_TOKEN="<jwt>" python3 scripts/export_beli_manifest.py
```

### Storing your password securely without a plaintext file (macOS Keychain / stdin)

Instead of putting a password in `.env` or a CLI argument (where it would appear in shell history or `ps`), store it encrypted in macOS Keychain once with a hidden prompt:

```bash
security add-generic-password -U -a "you@example.com" -s "beli-api-password" -w
```

Then run with `--keychain`:

```bash
python3 scripts/export_beli_manifest.py --email "you@example.com" --keychain
```

You can also pipe a password from any secret manager or pass a bash process substitution via `--password-stdin` or `--password-file`:

```bash
# Piped over stdin
security find-generic-password -a "you@example.com" -s "beli-api-password" -w \
  | python3 scripts/export_beli_manifest.py --email "you@example.com" --password-stdin

# Process substitution (ephemeral fd, no file on disk)
python3 scripts/export_beli_manifest.py \
  --email "you@example.com" \
  --password-file <(security find-generic-password -a "you@example.com" -s "beli-api-password" -w)
```

## Detail levels

| Flag | What it fetches | Typical runtime |
|---|---|---|
| `--detail fast` | Bulk endpoints only: account/profile stats, `user-scores`, `user-scores-cached`, `get-ranking` across all discovered + standard categories, photos, notes/EAV fields, labels, bookmarks, feed items, guides/lists. | ~10–15 seconds |
| `--detail full` *(default)* | Everything in `fast` **plus** per-ranked-business personal metadata: `/api/visit-dates-on-business/`, `/api/tagged-users-on-business/`, missing `/api/business/` details, and fallback per-business notes/photos if bulk returned empty. | ~1–3 min per 100 places |
| `--detail max` | Everything in `full` **plus** community & social metadata: one-shot friend network scores (`/api/scores/`) & personalized recs (`/api/recs/`), plus per-business rated counts, score histograms, occasion tags, dish recommendations, friend summaries, and friends who bookmarked. | ~3–6 min per 100 places |

Requests are automatically paced at `>=350ms` (`--min-interval-ms`) with automatic retry/backoff on `429`/`5xx` and automatic renewal of Beli's 20-minute access tokens.

## Checkpointing & resuming

In `full` and `max` modes, the script atomically checkpoints progress to `--output` every 25 businesses (configurable via `--checkpoint-every`) and on `Ctrl+C`. Re-run with `--resume` to pick up right where you left off:

```bash
python3 scripts/export_beli_manifest.py --detail max --resume
```

## Useful options

- `-o / --output <path>`: custom output path (default: `data/beli-manifest.json`).
- `--categories RES,BAR,DES`: restrict ranking queries to specific category codes (default auto-discovers every category present in your scores plus standard codes).
- `--redact-pii`: replaces `email`, `phone_no`, `sessions`, `referrer`, `referral_link`, and `qr_code` with `[REDACTED]`.
- `--omit-raw`: omits the top-level `raw_endpoints` section for a smaller manifest.
- `--skip-bookmarks`: skips fetching Want-to-Try bookmarks.
- `--no-save-session`: disables reading/writing `.beli-session.json`.

## Manifest structure

```json
{
  "manifest_meta": {
    "schema_version": "1.0.0",
    "exported_at": "2026-11-25T16:00:00Z",
    "complete": true,
    "detail_level": "full",
    "counts": {
      "rankings_total": 240,
      "rankings_by_category": { "RES": 190, "BAR": 35, "DES": 15 },
      "api_reported_rank_count": 240,
      "bookmarks_total": 85,
      "photos_total": 120,
      "notes_total": 64
    },
    "endpoints_status": {}
  },
  "account": {},
  "rankings": [
    {
      "ranking_id": 123456,
      "business_id": 7316,
      "place_id": "ChIJ...",
      "name": "Example Bistro",
      "category": "RES",
      "rank": 1,
      "score": 9.4,
      "raw_value": 9.4,
      "num_visits": 3,
      "created_dt": "...",
      "sent_dt": "...",
      "notification_id": 99999,
      "business": {},
      "notes": [],
      "favorite_dishes": [],
      "labels": [],
      "visit_dates": [],
      "tagged_users": [],
      "photos": [],
      "text_fields": [],
      "boolean_fields": [],
      "user_label_records": [],
      "feed_items": [],
      "lists": [],
      "community": {},
      "enrichment": { "status": "complete", "detail_level": "full", "enriched_at": "..." },
      "raw": { "ranking_record": {}, "score_record": {}, "cached_score_record": {} }
    }
  ],
  "rankings_by_category": { "RES": [7316] },
  "bookmarks": { "count": 85, "items": [], "by_category": {} },
  "lists": { "user_guides": [], "user_guide_items": [], "published_lists": [], "short_list": [] },
  "lookup_tables": { "business_labels": [] },
  "raw_endpoints": {}
}
```

## Using the manifest with `ranknorm`

Each entry in `manifest["rankings"]` includes `name` and numeric `score`, so you can pass it directly to `ranknorm`:

```python
import json
from ranknorm import redistribute

manifest = json.loads(open("data/beli-manifest.json").read())
restaurants = [r for r in manifest["rankings"] if r["category"] == "RES" and r["score"] is not None]
normalized = redistribute(restaurants, score_getter=lambda r: r["score"])
```
