# Beli Ranking Normalization

[![CI](https://github.com/rohanvarshney/beli-ranking-normalization/actions/workflows/ci.yml/badge.svg)](https://github.com/rohanvarshney/beli-ranking-normalization/actions/workflows/ci.yml)
[![Pages](https://github.com/rohanvarshney/beli-ranking-normalization/actions/workflows/pages.yml/badge.svg)](https://github.com/rohanvarshney/beli-ranking-normalization/actions/workflows/pages.yml)

Cross-language SDK (Python + Go) for redistributing crowded numeric ratings on the `(1.0, 10.0]` scale into a more even spread while preserving relative ordering.

## Why this exists

Many rating systems end up with heavy clustering in one band (for example, lots of values between `7.9` and `8.6`). That makes ranking less informative and reduces separation between items.

This SDK applies deterministic redistribution heuristics so downstream ranking, sorting, and recommendation systems can work with scores that are better spread across the available range.

## Strategies

- `quantile_map` (default): rank-order values and map by percentile to an evenly spaced output range.
- `zscore_sigmoid`: standardize scores, apply logistic transform, then rescale to `(1.0, 10.0]`.
- `piecewise_bucket`: bucketize the range and re-allocate span based on bucket density.

## Input/Output contract

- Input scores must be in `(1.0, 10.0]`.
- Output scores are clamped to `(1.0, 10.0]`.
- Item count and item identity are preserved.
- Ties are handled with stable ordering.

## Python usage

```python
from ranknorm import redistribute, Strategy

items = [
    {"name": "A", "score": 8.1},
    {"name": "B", "score": 8.2},
    {"name": "C", "score": 8.2},
]

# Default strategy: quantile_map
normalized = redistribute(items, score_getter=lambda x: x["score"])

# Explicit strategy with options
normalized_piecewise = redistribute(
    items,
    score_getter=lambda x: x["score"],
    strategy=Strategy.PIECEWISE_BUCKET,
    options={"bucket_count": 5},
)
```

## Go usage

```go
package main

import (
	"fmt"
	"github.com/rohanvarshney/beli-ranking-normalization/go/ranknorm"
)

type Item struct {
	Name  string
	Score float64
}

func main() {
	items := []Item{
		{Name: "A", Score: 8.1},
		{Name: "B", Score: 8.2},
		{Name: "C", Score: 8.2},
	}

	out, err := ranknorm.Redistribute(
		items,
		func(i Item) float64 { return i.Score },
		func(i *Item, v float64) { i.Score = v },
		ranknorm.StrategyQuantileMap, // default if empty string is passed
		nil,
	)
	if err != nil {
		panic(err)
	}
	fmt.Println(out)
}
```

## Web visualizer demo

- Live demo (GitHub Pages): `https://rohanvarshney.github.io/beli-ranking-normalization/`
- Implementation guide: `docs/web-ui-visualizer.md`
- Features:
  - mirrored food-tier flow chart (`RAW` → `ORDER 100% locked` Bezier ribbons → `NORMALIZED`) across Beli's three buckets (**I Don't Like**, **It's Okay**, and **I Like**)
  - interactive strategy cards (`quantile_map`, `zscore_sigmoid`, `piecewise_bucket`) with live morph scrubber and heuristic comparison
  - ranked food list spotlighting neighbor separation and tier shifts across deterministic diners and rating-style presets
  - playback speed (`0.5×`, `1×`, `2×`) and piecewise bucket controls (`2–12` buckets)

## Exporting your own Beli rankings

To snapshot all of your personal Beli rankings and associated metadata (business details, notes, photos, visit dates, tagged users, labels, bookmarks, lists, and raw API payloads) to a local gitignored JSON manifest (`data/beli-manifest.json`):

```bash
python3 scripts/export_beli_manifest.py
```

See [docs/beli-manifest-export.md](docs/beli-manifest-export.md) for authentication options (email, phone, 7-day refresh token caching), detail levels (`fast`, `full`, `max`), checkpoint/resume, and the manifest schema.

## Complexity

- Sorting-based strategies are `O(n log n)`.
- Memory usage is `O(n)`.

## Caveats

- Redistribution changes score calibration, so thresholds based on original scores may need retuning.
- If your system depends on absolute score semantics, apply normalization only in ranking layers.

## Development

- Python tests: `PYTHONPATH=python python -m pytest python/tests`
- Go tests: `cd go && go test ./...`
- Web app local dev: `cd web && npm install && npm run dev`
- Web app test/check/build: `cd web && npm run test && npm run check && npm run build`
- Install pre-commit: `python -m pip install pre-commit`
- Enable hooks: `pre-commit install`
- Run on all files: `pre-commit run --all-files`
