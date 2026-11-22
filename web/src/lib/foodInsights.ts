import { MAX_SCORE, MIN_SCORE } from './normalize';
import type { RestaurantScore, Strategy, UserRatings } from './types';

export type FoodTierId = 'skip' | 'okay' | 'good' | 'all_time';

export type FoodTier = {
  id: FoodTierId;
  min: number;
  max: number;
  label: string;
  shortLabel: string;
  rangeLabel: string;
  color: string;
  softBg: string;
  border: string;
  bandBg: string;
};

export const FOOD_TIERS: FoodTier[] = [
  {
    id: 'skip',
    min: 1.0,
    max: 4.0,
    label: 'Skip',
    shortLabel: 'Skip',
    rangeLabel: '1.0–4.0',
    color: '#C04545',
    softBg: '#FCECEC',
    border: '#F2C6C6',
    bandBg: 'rgba(192, 69, 69, 0.045)',
  },
  {
    id: 'okay',
    min: 4.0,
    max: 6.5,
    label: "It's Okay",
    shortLabel: 'Okay',
    rangeLabel: '4.0–6.5',
    color: '#A87514',
    softBg: '#FBF4DF',
    border: '#EBD8A0',
    bandBg: 'rgba(184, 134, 11, 0.045)',
  },
  {
    id: 'good',
    min: 6.5,
    max: 8.5,
    label: 'Really Good',
    shortLabel: 'Good',
    rangeLabel: '6.5–8.5',
    color: '#C8611B',
    softBg: '#FDF0E4',
    border: '#F2CBA8',
    bandBg: 'rgba(208, 106, 34, 0.045)',
  },
  {
    id: 'all_time',
    min: 8.5,
    max: 10.0,
    label: 'All-Time',
    shortLabel: 'All-Time',
    rangeLabel: '8.5–10',
    color: '#1D7A52',
    softBg: '#E6F5EE',
    border: '#B1DEC8',
    bandBg: 'rgba(29, 122, 82, 0.05)',
  },
];

export const FOOD_TIERS_DESCENDING: FoodTier[] = [...FOOD_TIERS].reverse();

export const getTierForScore = (score: number): FoodTier => {
  if (score < 4.0) return FOOD_TIERS[0];
  if (score < 6.5) return FOOD_TIERS[1];
  if (score < 8.5) return FOOD_TIERS[2];
  return FOOD_TIERS[3];
};

export type StrategyMeta = {
  id: Strategy;
  title: string;
  code: Strategy;
  shortTag: string;
  summary: string;
  detail: string;
};

export const STRATEGY_LIST: StrategyMeta[] = [
  {
    id: 'quantile_map',
    title: 'Even Spread',
    code: 'quantile_map',
    shortTag: 'Uniform 1–10',
    summary: 'Spaces every restaurant evenly from 1 to 10 by rank percentile.',
    detail:
      'Every score band gets an equal share of spots. Great when you want maximum separation everywhere.',
  },
  {
    id: 'zscore_sigmoid',
    title: 'Bell Balance',
    code: 'zscore_sigmoid',
    shortTag: 'Centered at 5.5',
    summary: 'Centers typical restaurants near 5.5 and reserves 9+ for true standouts.',
    detail:
      'Preserves relative gaps near your average while compressing extreme outliers cleanly into a bell-like curve.',
  },
  {
    id: 'piecewise_bucket',
    title: 'Bucket Stretch',
    code: 'piecewise_bucket',
    shortTag: 'Density-weighted',
    summary: 'Widens crowded rating bands proportionally while respecting bucket boundaries.',
    detail:
      'Divides 1–10 into fixed raw buckets and gives crowded buckets a larger slice of the output scale.',
  },
];

export const STRATEGY_META: Record<Strategy, StrategyMeta> = {
  quantile_map: STRATEGY_LIST[0],
  zscore_sigmoid: STRATEGY_LIST[1],
  piecewise_bucket: STRATEGY_LIST[2],
};

const NOUN_META: Record<string, { display: string; cuisine: string }> = {
  Bistro: { display: 'Bistro', cuisine: 'Bistro' },
  Kitchen: { display: 'Kitchen', cuisine: 'Kitchen' },
  Tavern: { display: 'Tavern', cuisine: 'Tavern' },
  Grill: { display: 'Grill', cuisine: 'Grill' },
  Ramen: { display: 'Ramen', cuisine: 'Ramen' },
  Pizzeria: { display: 'Pizzeria', cuisine: 'Pizza' },
  CurryHouse: { display: 'Curry House', cuisine: 'Curry' },
  Cafe: { display: 'Cafe', cuisine: 'Cafe' },
  Diner: { display: 'Diner', cuisine: 'Diner' },
  Taqueria: { display: 'Taqueria', cuisine: 'Tacos' },
  Bakery: { display: 'Bakery', cuisine: 'Bakery' },
  SushiBar: { display: 'Sushi Bar', cuisine: 'Sushi' },
};

export type ParsedRestaurantMeta = {
  baseName: string;
  code: string;
  cuisine: string;
};

export const parseRestaurantMeta = (rawName: string): ParsedRestaurantMeta => {
  const match = rawName.trim().match(/^(.+?)\s+#(\d+)$/);
  const namePart = match ? match[1] : rawName.trim();
  const numPart = match ? `#${Number.parseInt(match[2], 10)}` : '';
  const words = namePart.split(/\s+/);
  const lastWord = words[words.length - 1] ?? '';
  const mapped = NOUN_META[lastWord];
  if (mapped) {
    words[words.length - 1] = mapped.display;
    return {
      baseName: words.join(' '),
      code: numPart,
      cuisine: mapped.cuisine,
    };
  }
  return {
    baseName: namePart,
    code: numPart,
    cuisine: lastWord || 'Spot',
  };
};

export const formatDatasetNames = (
  items: RestaurantScore[],
): { displayName: string; code: string; cuisine: string }[] => {
  const parsed = items.map((item) => parseRestaurantMeta(item.restaurantName));
  const counts = new Map<string, number>();
  for (const p of parsed) {
    counts.set(p.baseName, (counts.get(p.baseName) ?? 0) + 1);
  }
  return parsed.map((p) => {
    const hasDuplicates = (counts.get(p.baseName) ?? 0) > 1;
    const displayName = hasDuplicates && p.code ? `${p.baseName} · ${p.code}` : p.baseName;
    return {
      displayName,
      code: p.code,
      cuisine: p.cuisine,
    };
  });
};

export type DatasetId = `diner:${number}` | 'all' | 'preset:harsh' | 'preset:bimodal';

export type DatasetOption = {
  id: DatasetId;
  label: string;
  shortLabel: string;
  count: number;
  group: 'diners' | 'aggregate' | 'presets';
};

const PRESET_COUNT = 65;

const PRESET_ADJECTIVES = [
  'Golden',
  'Rusty',
  'Hidden',
  'Spicy',
  'Cozy',
  'Lucky',
  'Midnight',
  'Sunny',
  'Royal',
  'Humble',
  'Crispy',
  'Saffron',
];

const PRESET_NOUNS = [
  'Bistro',
  'Kitchen',
  'Tavern',
  'Grill',
  'Ramen',
  'Pizzeria',
  'CurryHouse',
  'Cafe',
  'Diner',
  'Taqueria',
  'Bakery',
  'SushiBar',
];

class LocalSeededRng {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0;
  }

  next(): number {
    this.state = (1664525 * this.state + 1013904223) >>> 0;
    return this.state / 0x100000000;
  }

  int(min: number, max: number): number {
    return Math.floor(this.next() * (max - min + 1)) + min;
  }

  normal(mean = 0, std = 1): number {
    const u1 = Math.max(this.next(), Number.MIN_VALUE);
    const u2 = this.next();
    const z0 = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    return mean + z0 * std;
  }
}

const clampScoreRange = (value: number, maxCap = MAX_SCORE): number => {
  if (value <= 1.0) return MIN_SCORE;
  if (value > maxCap) return maxCap;
  return value;
};

const buildPresetRatings = (kind: 'harsh' | 'bimodal', seed: number): RestaurantScore[] => {
  const salt = kind === 'harsh' ? 0x9e3779b9 : 0x85ebca6b;
  const rng = new LocalSeededRng((seed ^ salt) >>> 0);
  const out: RestaurantScore[] = [];

  for (let i = 0; i < PRESET_COUNT; i += 1) {
    const adj = PRESET_ADJECTIVES[rng.int(0, PRESET_ADJECTIVES.length - 1)];
    const noun = PRESET_NOUNS[rng.int(0, PRESET_NOUNS.length - 1)];
    const name = `${adj} ${noun} #${String(i + 1).padStart(3, '0')}`;

    let score: number;
    if (kind === 'harsh') {
      score = clampScoreRange(rng.normal(4.6, 0.72), 7.8);
    } else {
      const isLoved = rng.next() >= 0.42;
      const raw = isLoved ? rng.normal(8.5, 0.55) : rng.normal(3.6, 0.65);
      score = clampScoreRange(raw, MAX_SCORE);
    }

    out.push({
      id: `preset-${kind}-${i + 1}`,
      restaurantName: name,
      score,
    });
  }

  return out;
};

export const buildDatasetOptions = (users: UserRatings[]): DatasetOption[] => {
  const totalCount = users.reduce((acc, u) => acc + u.ratings.length, 0);
  const dinerOptions: DatasetOption[] = users.map((u, idx) => ({
    id: `diner:${idx}` as DatasetId,
    label: `Diner #${idx + 1} · ${u.ratings.length} spots`,
    shortLabel: `Diner #${idx + 1}`,
    count: u.ratings.length,
    group: 'diners',
  }));

  return [
    ...dinerOptions,
    {
      id: 'all',
      label: `All ${users.length} Diners · ${totalCount.toLocaleString()} spots`,
      shortLabel: `All ${users.length} Diners`,
      count: totalCount,
      group: 'aggregate',
    },
    {
      id: 'preset:harsh',
      label: `Tough Critic (Clustered 4–6) · ${PRESET_COUNT} spots`,
      shortLabel: 'Tough Critic',
      count: PRESET_COUNT,
      group: 'presets',
    },
    {
      id: 'preset:bimodal',
      label: `Love-or-Skip Rater (Two Peaks) · ${PRESET_COUNT} spots`,
      shortLabel: 'Love-or-Skip',
      count: PRESET_COUNT,
      group: 'presets',
    },
  ];
};

export const getDefaultDatasetId = (users: UserRatings[]): DatasetId => {
  if (users.length === 0) return 'preset:harsh';
  let bestIdx = 0;
  let bestDist = Infinity;
  for (let i = 0; i < users.length; i += 1) {
    const dist = Math.abs(users[i].ratings.length - 75);
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = i;
    }
  }
  return `diner:${bestIdx}`;
};

export const getDatasetItems = (
  users: UserRatings[],
  datasetId: DatasetId,
  seed: number,
): RestaurantScore[] => {
  if (datasetId === 'preset:harsh') return buildPresetRatings('harsh', seed);
  if (datasetId === 'preset:bimodal') return buildPresetRatings('bimodal', seed);
  if (datasetId === 'all') {
    return users.flatMap((u) => u.ratings.map((r) => ({ ...r, id: `${u.userId}-${r.id}` })));
  }
  const idx = Number.parseInt(datasetId.slice('diner:'.length), 10);
  const safeIdx = Number.isFinite(idx) && idx >= 0 && idx < users.length ? idx : 0;
  return users[safeIdx]?.ratings ?? [];
};

export type RankedRestaurantBase = {
  index: number;
  id: string;
  displayName: string;
  code: string;
  cuisine: string;
  rank: number;
  percentile: number;
  beforeScore: number;
  afterScores: Record<Strategy, number>;
};

export const buildRankedItems = (
  items: RestaurantScore[],
  beforeScores: number[],
  afterByStrategy: Record<Strategy, number[]>,
): RankedRestaurantBase[] => {
  const n = items.length;
  if (n === 0) return [];

  const formatted = formatDatasetNames(items);
  const indices = Array.from({ length: n }, (_, i) => i);
  // Descending rank order (#1 = best), breaking ties by higher original index first
  // so that normalize.ts ascending tie-break (a - b) remains non-increasing down the rank list.
  indices.sort((a, b) =>
    beforeScores[b] !== beforeScores[a] ? beforeScores[b] - beforeScores[a] : b - a,
  );

  return indices.map((origIdx, pos) => {
    const rank = pos + 1;
    const meta = formatted[origIdx];
    return {
      index: origIdx,
      id: items[origIdx].id,
      displayName: meta.displayName,
      code: meta.code,
      cuisine: meta.cuisine,
      rank,
      percentile: n > 1 ? (n - rank) / (n - 1) : 1,
      beforeScore: beforeScores[origIdx],
      afterScores: {
        quantile_map: afterByStrategy.quantile_map[origIdx],
        zscore_sigmoid: afterByStrategy.zscore_sigmoid[origIdx],
        piecewise_bucket: afterByStrategy.piecewise_bucket[origIdx],
      },
    };
  });
};

export const verifyRankOrderPreserved = (
  beforeScores: number[],
  afterScores: number[],
): boolean => {
  const n = beforeScores.length;
  if (n !== afterScores.length) return false;
  if (n <= 1) return true;

  const indices = Array.from({ length: n }, (_, i) => i);
  indices.sort((a, b) =>
    beforeScores[a] !== beforeScores[b] ? beforeScores[a] - beforeScores[b] : a - b,
  );

  for (let k = 0; k < n - 1; k += 1) {
    if (afterScores[indices[k]] > afterScores[indices[k + 1]] + 1e-12) {
      return false;
    }
  }
  return true;
};

export type DensityPoint = {
  score: number;
  density: number;
};

export const computeDensityCurve = (
  scores: number[],
  steps = 90,
  bandwidth = 0.36,
): DensityPoint[] => {
  const safeSteps = Math.max(10, steps);
  const dx = 9.0 / safeSteps;
  const n = scores.length;

  if (n === 0) {
    return Array.from({ length: safeSteps + 1 }, (_, i) => ({
      score: 1.0 + i * dx,
      density: 0,
    }));
  }

  // Bin into `safeSteps` equal-width histogram buckets on [1.0, 10.0]
  const bins = new Float64Array(safeSteps);
  for (let i = 0; i < n; i += 1) {
    const raw = Math.floor(((scores[i] - 1.0) / 9.0) * safeSteps);
    const binIdx = Math.max(0, Math.min(safeSteps - 1, raw));
    bins[binIdx] += 1;
  }

  const radius = Math.ceil((3.2 * bandwidth) / dx);
  const normConst = 1 / (Math.sqrt(2 * Math.PI) * bandwidth * n);
  const twoBwSq = 2 * bandwidth * bandwidth;

  const mirrorBin = (b: number): number => {
    let m = b;
    while (m < 0 || m >= safeSteps) {
      if (m < 0) {
        m = -m - 1;
      } else {
        m = 2 * safeSteps - 1 - m;
      }
    }
    return m;
  };

  const out: DensityPoint[] = new Array(safeSteps + 1);
  for (let i = 0; i <= safeSteps; i += 1) {
    let sum = 0;
    const minB = i - radius;
    const maxB = i + radius - 1;
    for (let b = minB; b <= maxB; b += 1) {
      const dist = (b + 0.5 - i) * dx;
      const weight = Math.exp(-(dist * dist) / twoBwSq);
      sum += bins[mirrorBin(b)] * weight;
    }
    out[i] = {
      score: 1.0 + i * dx,
      density: sum * normConst,
    };
  }
  return out;
};

export const selectDisplayIndices = (
  ranked: RankedRestaurantBase[],
  maxDots = 120,
): number[] => {
  const n = ranked.length;
  if (n === 0) return [];
  if (n <= maxDots) {
    return Array.from({ length: n }, (_, i) => i);
  }

  const chosen = new Set<number>();
  const target = Math.max(3, maxDots);
  const mid = Math.floor(n / 2);
  const leftSteps = Math.max(1, Math.floor((target - 1) / 2));
  const rightSteps = Math.max(1, target - 1 - leftSteps);

  for (let k = 0; k <= leftSteps; k += 1) {
    chosen.add(Math.round((k / leftSteps) * mid));
  }
  for (let k = 0; k <= rightSteps; k += 1) {
    chosen.add(mid + Math.round((k / rightSteps) * (n - 1 - mid)));
  }

  return Array.from(chosen).sort((a, b) => a - b);
};

export const computeBeeswarmOffsets = (
  xCoords: number[],
  radius = 4.2,
  maxHeight = 62,
): number[] => {
  const n = xCoords.length;
  if (n === 0) return [];

  const minDist = radius * 2 + 1.1;
  const minDistSq = minDist * minDist;
  const order = Array.from({ length: n }, (_, i) => i);
  order.sort((a, b) => (xCoords[a] !== xCoords[b] ? xCoords[a] - xCoords[b] : a - b));

  const offsets = new Array<number>(n).fill(0);
  const placed: { x: number; y: number }[] = [];

  for (let k = 0; k < n; k += 1) {
    const idx = order[k];
    const cx = xCoords[idx];
    const intervals: { start: number; end: number }[] = [];

    for (let j = placed.length - 1; j >= 0; j -= 1) {
      const dx = cx - placed[j].x;
      if (dx >= minDist) break;
      const dy = Math.sqrt(Math.max(0, minDistSq - dx * dx));
      intervals.push({
        start: placed[j].y - dy,
        end: placed[j].y + dy,
      });
    }

    intervals.sort((a, b) => a.start - b.start);
    let candidateY = 0;
    for (let i = 0; i < intervals.length; i += 1) {
      const iv = intervals[i];
      if (candidateY < iv.start - 1e-6) break;
      if (candidateY < iv.end) {
        candidateY = iv.end;
      }
    }

    const clampedY = Math.max(0, Math.min(maxHeight, candidateY));
    offsets[idx] = clampedY;
    placed.push({ x: cx, y: clampedY });
  }

  return offsets;
};

export type PiecewiseBucketBand = {
  bucketIndex: number;
  rawMin: number;
  rawMax: number;
  outMin: number;
  outMax: number;
  count: number;
};

export const computePiecewiseBuckets = (
  beforeScores: number[],
  bucketCount = 4,
): PiecewiseBucketBand[] => {
  const buckets = Math.max(2, bucketCount);
  const width = (MAX_SCORE - MIN_SCORE) / buckets;
  const counts = new Array<number>(buckets).fill(0);
  const n = beforeScores.length;

  for (let i = 0; i < n; i += 1) {
    const raw = width > 0 ? Math.floor((beforeScores[i] - MIN_SCORE) / width) : 0;
    const bucketIdx = Math.max(0, Math.min(buckets - 1, raw));
    counts[bucketIdx] += 1;
  }

  let writeStart = MIN_SCORE;
  const out: PiecewiseBucketBand[] = [];
  for (let b = 0; b < buckets; b += 1) {
    const count = counts[b];
    const rawMin = b === 0 ? 1.0 : MIN_SCORE + b * width;
    const rawMax = b === buckets - 1 ? MAX_SCORE : MIN_SCORE + (b + 1) * width;
    const span = n > 0 ? (count / n) * (MAX_SCORE - MIN_SCORE) : 0;
    const writeEnd = count > 0 ? Math.min(MAX_SCORE, writeStart + span) : writeStart;

    out.push({
      bucketIndex: b,
      rawMin,
      rawMax,
      outMin: b === 0 && count > 0 ? 1.0 : writeStart,
      outMax: writeEnd,
      count,
    });

    if (count > 0) {
      writeStart = writeEnd;
    }
  }
  return out;
};

export type TierSummaryRow = {
  tier: FoodTier;
  count: number;
  pct: number;
};

export type DistributionSummary = {
  count: number;
  min: number;
  max: number;
  p25: number;
  median: number;
  p75: number;
  iqr: number;
  medianAdjacentGap: number;
  tiers: TierSummaryRow[];
  crowdedHeadline: string;
};

const quantileSorted = (sorted: number[], q: number): number => {
  if (sorted.length === 0) return 0;
  if (sorted.length === 1) return sorted[0];
  const pos = q * (sorted.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  if (lo === hi) return sorted[lo];
  const frac = pos - lo;
  return sorted[lo] + (sorted[hi] - sorted[lo]) * frac;
};

export const computeDistributionSummary = (scores: number[]): DistributionSummary => {
  const n = scores.length;
  const tierCounts = new Map<FoodTierId, number>([
    ['all_time', 0],
    ['good', 0],
    ['okay', 0],
    ['skip', 0],
  ]);

  if (n === 0) {
    return {
      count: 0,
      min: 0,
      max: 0,
      p25: 0,
      median: 0,
      p75: 0,
      iqr: 0,
      medianAdjacentGap: 0,
      tiers: FOOD_TIERS_DESCENDING.map((tier) => ({ tier, count: 0, pct: 0 })),
      crowdedHeadline: 'No scores available',
    };
  }

  for (let i = 0; i < n; i += 1) {
    const t = getTierForScore(scores[i]);
    tierCounts.set(t.id, (tierCounts.get(t.id) ?? 0) + 1);
  }

  const sorted = [...scores].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[n - 1];
  const p25 = quantileSorted(sorted, 0.25);
  const median = quantileSorted(sorted, 0.5);
  const p75 = quantileSorted(sorted, 0.75);
  const iqr = p75 - p25;

  let medianAdjacentGap = 0;
  if (n > 1) {
    const gaps: number[] = new Array(n - 1);
    for (let i = 0; i < n - 1; i += 1) {
      gaps[i] = sorted[i + 1] - sorted[i];
    }
    gaps.sort((a, b) => a - b);
    medianAdjacentGap = quantileSorted(gaps, 0.5);
  }

  // Find densest 2.0-point band in 0.5 increments to summarize crowding intuitively
  let bestCount = 0;
  let bestLo = 7.0;
  let bestHi = 9.0;
  let bestCenterDist = Infinity;

  for (let lo = 1.0; lo <= 8.0 + 1e-9; lo += 0.5) {
    const hi = Math.min(10.0, lo + 2.0);
    let inside = 0;
    for (let i = 0; i < n; i += 1) {
      if (sorted[i] >= lo && sorted[i] <= hi) inside += 1;
    }
    const centerDist = Math.abs((lo + hi) / 2 - median);
    if (inside > bestCount || (inside === bestCount && centerDist < bestCenterDist)) {
      bestCount = inside;
      bestLo = lo;
      bestHi = hi;
      bestCenterDist = centerDist;
    }
  }

  const peakPct = Math.round((bestCount / n) * 100);
  const crowdedHeadline =
    peakPct >= 45
      ? `${peakPct}% of scores sit between ${bestLo.toFixed(1)} and ${bestHi.toFixed(1)}`
      : `Middle 50% spans ${p25.toFixed(1)} to ${p75.toFixed(1)}`;

  return {
    count: n,
    min,
    max,
    p25,
    median,
    p75,
    iqr,
    medianAdjacentGap,
    tiers: FOOD_TIERS_DESCENDING.map((tier) => {
      const count = tierCounts.get(tier.id) ?? 0;
      return {
        tier,
        count,
        pct: (count / n) * 100,
      };
    }),
    crowdedHeadline,
  };
};
