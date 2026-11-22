# Beli Ranking Normalization — Web UI Visualizer Guide

## Purpose

The web UI is a Svelte-based interactive explorer that visualizes how **Beli Ranking Normalization** transforms crowded restaurant ratings on `(1.0, 10.0]` into a clearer, spread-out food rating distribution while preserving 100% of rank order.

## Where the logic lives

- App orchestration: `web/src/App.svelte`
- Strategy engine: `web/src/lib/normalize.ts`
- Deterministic mock data: `web/src/lib/mockData.ts`
- Animation utilities: `web/src/lib/animation.ts`
- Food-ranking & visualization math: `web/src/lib/foodInsights.ts`
- Strategy cards & bucket controls: `web/src/components/StrategySelector.svelte`
- Mirrored food rating flow chart: `web/src/components/FoodFlowChart.svelte`
- Ranked restaurant list & spotlight: `web/src/components/RankedFoodList.svelte`
- Tier shift, spacing & heuristic comparison: `web/src/components/ImpactSummary.svelte`

## How the UI works

1. The app generates deterministic mock restaurant ratings across 10 diners (`generateMockUsers(seed)`) and defaults to an individual diner list sized for clear visual inspection (`getDefaultDatasetId`).
2. Users can switch between any of the 10 individual diners, **All 10 Diners** combined, or deterministic rating-style presets (**Tough Critic** clustered around `4–6` and **Love-or-Skip Rater** with two peaks).
3. It computes:
   - `beforeScores` (raw ratings)
   - `afterByStrategy` (normalized scores across `quantile_map`, `zscore_sigmoid`, and `piecewise_bucket`)
4. Using the morph scrubber (`0%` to `100%`) or Play/Replay controls (`0.5×`, `1×`, `2×`), it interpolates live score values:
   - `currentScores = interpolateScores(beforeScores, afterScores, progress)`
5. All panels read from the same `ranked` and `currentScores` state so hovering or pinning a restaurant highlights it simultaneously across the flow chart, ranked list, and heuristic comparison card.

## Visual panels

### 1) Strategy Selector (`StrategySelector.svelte`)

Three visual strategy cards with mini distribution shape thumbnails and plain-English descriptions:
- **Even Spread** (`quantile_map`)
- **Bell Balance** (`zscore_sigmoid`)
- **Bucket Stretch** (`piecewise_bucket`, displaying an inline `2–12` raw bucket count slider when active)

### 2) Mirrored Food Rating Flow Chart (`FoodFlowChart.svelte`)

A unified three-lane SVG across the `(1.0, 10.0]` food scale divided into four intuitive food tiers (**Skip** `1.0–4.0`, **It's Okay** `4.0–6.5`, **Really Good** `6.5–8.5`, **All-Time** `8.5–10`):
- **Top Lane (`RAW / Before`)**: Reflected Gaussian KDE ridge + beeswarm restaurant dots + Middle 50% (IQR) callout bracket.
- **Middle Lane (`ORDER · 100% locked`)**: Non-crossing cubic Bezier flow ribbons tracking each restaurant from its raw position to its live normalized position (plus density-proportional bucket funnel corridors when `piecewise_bucket` is active).
- **Bottom Lane (`NORMALIZED / Live Morph`)**: Mirrored KDE ridge on the same Y-scale + animated beeswarm dots + updated Middle 50% (IQR) bracket.

### 3) Ranked Food List (`RankedFoodList.svelte`)

Displays restaurants in exact descending rank order (`#1` to `#N`) with filter tabs (`All`, `Top 10`, `Middle Pack`, `Bottom 10`, `Biggest Shifts`), search by name/cuisine/rank, inline `1–10` shift tracks, and a spotlight card showing tier transitions and closest-neighbor gap widening.

### 4) Impact Summary (`ImpactSummary.svelte`)

Summarizes:
- **Where Your Restaurants Land**: Before vs. Now stacked tier distribution bars and counts across the 4 food tiers.
- **Separation & Order Guarantee**: Live verification that rank order is 100% intact, alongside Middle 50% spread and typical neighbor gap changes.
- **Compare Heuristics on One Spot**: Side-by-side output scores across all 3 heuristics for the spotlighted spot plus a 3-anchor (`#1`, median, `#N`) snapshot.

## Determinism model

Determinism is guaranteed by the seeded pseudo-random generators in `mockData.ts` and `foodInsights.ts`:

- Same seed -> same diners, same restaurants, same scores
- Different seed -> different dataset, still reproducible for that seed

## Local run

```bash
cd web
npm install
npm run dev
```

## Validation commands

```bash
cd web
npm run test
npm run check
npm run build
```
