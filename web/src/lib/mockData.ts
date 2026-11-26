import type { RestaurantScore, UserRatings } from './types';
import { MAX_SCORE, MIN_SCORE } from './normalize';

class SeededRandom {
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

const ADJECTIVES = [
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
const NOUNS = [
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

const restaurantName = (rng: SeededRandom, idx: number): string => {
  const adj = ADJECTIVES[rng.int(0, ADJECTIVES.length - 1)];
  const noun = NOUNS[rng.int(0, NOUNS.length - 1)];
  return `${adj} ${noun} #${String(idx).padStart(3, '0')}`;
};

const clampScore = (raw: number, maxCap = MAX_SCORE): number => {
  if (raw <= 1.0) return MIN_SCORE;
  if (raw > maxCap) return maxCap;
  return raw;
};

type DinerArchetype = {
  label: string;
  description: string;
  sampleScore: (rng: SeededRandom) => number;
};

export const DINER_ARCHETYPES: readonly DinerArchetype[] = [
  {
    label: 'Tight 8.0–8.6 Pack',
    description: 'Packs almost every spot tightly between 8.0 and 8.6.',
    sampleScore: (rng) => clampScore(rng.normal(8.3, 0.25), 9.2),
  },
  {
    label: 'Generous Foodie (High 8–9.5)',
    description: 'Upbeat rater skewed heavily toward the top of I Like.',
    sampleScore: (rng) => clampScore(rng.normal(8.7, 0.58), MAX_SCORE),
  },
  {
    label: 'Cautious Mid-Rater (5–7.5)',
    description: 'Avoids extremes, clustering around the 5.5–7.5 middle band.',
    sampleScore: (rng) => clampScore(rng.normal(6.3, 0.72), 8.6),
  },
  {
    label: 'Picky + Rare Gems (Right Tail)',
    description: 'Mostly strict 5s with a long tail of rare 8.5+ favorites.',
    sampleScore: (rng) =>
      rng.next() < 0.16
        ? clampScore(rng.normal(8.6, 0.45), MAX_SCORE)
        : clampScore(rng.normal(5.5, 0.78), 7.6),
  },
  {
    label: 'Two-Tier Foodie (7.5s & 9.3s)',
    description: 'Splits between everyday 7.5 staples and 9.3 bucket-list gems.',
    sampleScore: (rng) =>
      rng.next() < 0.32
        ? clampScore(rng.normal(9.3, 0.28), MAX_SCORE)
        : clampScore(rng.normal(7.5, 0.42), 8.6),
  },
  {
    label: 'Balanced Full-Scale (2.5–9.5)',
    description: 'Already spreads ratings widely across all three Beli tiers.',
    sampleScore: (rng) => clampScore(rng.normal(6.0, 2.05), MAX_SCORE),
  },
  {
    label: 'Classic Beli Crowd (7–9)',
    description: 'Typical Beli bell curve crowded between 7.0 and 9.0.',
    sampleScore: (rng) => clampScore(rng.normal(8.0, 0.75), MAX_SCORE),
  },
  {
    label: 'Tie-Heavy Rater (0.5 Steps)',
    description: 'Snaps ratings to 0.5 increments, creating frequent exact ties.',
    sampleScore: (rng) => {
      const snapped = Math.round(rng.normal(7.5, 1.05) * 2) / 2;
      return clampScore(snapped, MAX_SCORE);
    },
  },
  {
    label: 'Outlier Chaser (7s + 2s & 10s)',
    description: 'Mostly 7s punctuated by extreme 2-star misses and 9.6+ hits.',
    sampleScore: (rng) => {
      const pick = rng.next();
      if (pick < 0.12) return clampScore(rng.normal(2.2, 0.45), 3.3);
      if (pick > 0.88) return clampScore(rng.normal(9.6, 0.25), MAX_SCORE);
      return clampScore(rng.normal(7.4, 0.45), 8.5);
    },
  },
  {
    label: 'Tough Skeptic (3–6)',
    description: 'Hard to please, keeping most spots in Okay or Don’t Like.',
    sampleScore: (rng) => clampScore(rng.normal(4.2, 1.0), 7.4),
  },
];

export const generateMockUsers = (
  seed = 1337,
  userCount = 10,
  minRestaurants = 50,
  maxRestaurants = 500,
): UserRatings[] => {
  const countRng = new SeededRandom(seed);
  const users: UserRatings[] = [];

  for (let u = 0; u < userCount; u += 1) {
    const archetype = DINER_ARCHETYPES[u % DINER_ARCHETYPES.length];
    const restaurantCount = countRng.int(minRestaurants, maxRestaurants);
    const userRng = new SeededRandom(((seed ^ Math.imul(u + 1, 0x9e3779b1)) >>> 0));
    const ratings: RestaurantScore[] = [];
    for (let i = 0; i < restaurantCount; i += 1) {
      ratings.push({
        id: `u${u + 1}-r${i + 1}`,
        restaurantName: restaurantName(userRng, i + 1),
        score: archetype.sampleScore(userRng),
      });
    }
    users.push({
      userId: `user_${String(u + 1).padStart(2, '0')}`,
      label: archetype.label,
      description: archetype.description,
      ratings,
    });
  }

  return users;
};

export const flattenUsers = (users: UserRatings[]): RestaurantScore[] => {
  return users.flatMap((u) => u.ratings.map((r) => ({ ...r, id: `${u.userId}-${r.id}` })));
};
