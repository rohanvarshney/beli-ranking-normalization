import { describe, expect, it } from 'vitest';

import {
  buildDatasetOptions,
  buildRankedItems,
  computeBeeswarmOffsets,
  computeDensityCurve,
  computeDistributionSummary,
  computePiecewiseBuckets,
  FOOD_TIERS,
  formatDatasetNames,
  getDatasetItems,
  getDefaultDatasetId,
  getTierForScore,
  parseRestaurantMeta,
  selectDisplayIndices,
  verifyRankOrderPreserved,
} from './foodInsights';
import { generateMockUsers } from './mockData';
import { MAX_SCORE, MIN_SCORE, normalizeScores } from './normalize';

describe('foodInsights', () => {
  it('maps boundary scores cleanly to contiguous food tiers', () => {
    expect(FOOD_TIERS).toHaveLength(3);
    expect(getTierForScore(0.1).id).toBe('dislike');
    expect(getTierForScore(1.0001).id).toBe('dislike');
    expect(getTierForScore(3.3).id).toBe('dislike');
    expect(getTierForScore(3.34).id).toBe('dislike');
    expect(getTierForScore(3.35).id).toBe('okay');
    expect(getTierForScore(3.4).id).toBe('okay');
    expect(getTierForScore(6.6).id).toBe('okay');
    expect(getTierForScore(6.64).id).toBe('okay');
    expect(getTierForScore(6.65).id).toBe('like');
    expect(getTierForScore(6.7).id).toBe('like');
    expect(getTierForScore(10.0).id).toBe('like');
  });

  it('parses and formats restaurant names and cuisines cleanly', () => {
    expect(parseRestaurantMeta('Golden SushiBar #014')).toEqual({
      baseName: 'Golden Sushi Bar',
      code: '#14',
      cuisine: 'Sushi',
    });
    expect(parseRestaurantMeta('Spicy CurryHouse #003')).toEqual({
      baseName: 'Spicy Curry House',
      code: '#3',
      cuisine: 'Curry',
    });
    expect(parseRestaurantMeta('Sunny Taqueria #042')).toEqual({
      baseName: 'Sunny Taqueria',
      code: '#42',
      cuisine: 'Tacos',
    });
    expect(parseRestaurantMeta('Rusty Pizzeria #108')).toEqual({
      baseName: 'Rusty Pizzeria',
      code: '#108',
      cuisine: 'Pizza',
    });
    expect(parseRestaurantMeta('Cozy Ramen #007')).toEqual({
      baseName: 'Cozy Ramen',
      code: '#7',
      cuisine: 'Ramen',
    });

    const formatted = formatDatasetNames([
      { id: '1', restaurantName: 'Golden SushiBar #014', score: 8.1 },
      { id: '2', restaurantName: 'Golden SushiBar #099', score: 7.4 },
      { id: '3', restaurantName: 'Sunny Taqueria #005', score: 9.0 },
    ]);
    expect(formatted.map((f) => f.displayName)).toEqual([
      'Golden Sushi Bar · #14',
      'Golden Sushi Bar · #99',
      'Sunny Taqueria',
    ]);
  });

  it('generates deterministic presets and distinctly profiled sample diners within (1.0, 10.0]', () => {
    const users = generateMockUsers(1337);
    const options = buildDatasetOptions(users);
    expect(options.length).toBe(18);
    expect(getDefaultDatasetId(users)).toMatch(/^diner:\d+$/);

    // Aggregate group includes All Diners + Negative / Neutral / Positive tier partitions
    const aggregateOptions = options.filter((o) => o.group === 'aggregate');
    expect(aggregateOptions.map((o) => o.id)).toEqual([
      'all',
      'all:negative',
      'all:neutral',
      'all:positive',
    ]);
    const allItems = getDatasetItems(users, 'all', 1337);
    const negItems = getDatasetItems(users, 'all:negative', 1337);
    const neuItems = getDatasetItems(users, 'all:neutral', 1337);
    const posItems = getDatasetItems(users, 'all:positive', 1337);
    expect(negItems.length).toBeGreaterThan(0);
    expect(neuItems.length).toBeGreaterThan(0);
    expect(posItems.length).toBeGreaterThan(0);
    expect(negItems.length + neuItems.length + posItems.length).toBe(allItems.length);
    expect(negItems.every((x) => getTierForScore(x.score).id === 'dislike')).toBe(true);
    expect(neuItems.every((x) => getTierForScore(x.score).id === 'okay')).toBe(true);
    expect(posItems.every((x) => getTierForScore(x.score).id === 'like')).toBe(true);

    // Every sample diner & rating habit has a distinct descriptive label and score distribution
    const dinerLabels = options.filter((o) => o.group === 'diners').map((o) => o.label);
    expect(new Set(dinerLabels).size).toBe(14);
    expect(dinerLabels[0]).toContain('Tight 8.0–8.6 Pack');
    expect(dinerLabels[9]).toContain('Tough Skeptic');
    expect(dinerLabels[10]).toContain('Lover');
    expect(dinerLabels[11]).toContain('Hater');

    const tightSummary = computeDistributionSummary(users[0].ratings.map((r) => r.score));
    const generousSummary = computeDistributionSummary(users[1].ratings.map((r) => r.score));
    const balancedSummary = computeDistributionSummary(users[5].ratings.map((r) => r.score));
    const skepticSummary = computeDistributionSummary(users[9].ratings.map((r) => r.score));

    expect(tightSummary.iqr).toBeLessThan(0.6);
    expect(generousSummary.median).toBeGreaterThan(8.2);
    expect(balancedSummary.iqr).toBeGreaterThan(2.0);
    expect(skepticSummary.median).toBeLessThan(4.8);

    // Diner #8 snaps to 0.5 increments so it produces many exact ties
    const tieHeavyScores = users[7].ratings.map((r) => r.score);
    expect(new Set(tieHeavyScores).size).toBeLessThan(tieHeavyScores.length / 2);

    const loverA = getDatasetItems(users, 'preset:lover', 1337);
    const loverB = getDatasetItems(users, 'preset:lover', 1337);
    const hater = getDatasetItems(users, 'preset:hater', 1337);
    const harshA = getDatasetItems(users, 'preset:harsh', 1337);
    const harshB = getDatasetItems(users, 'preset:harsh', 1337);
    const bimodal = getDatasetItems(users, 'preset:bimodal', 1337);

    expect(loverA).toEqual(loverB);
    expect(harshA).toEqual(harshB);
    expect(loverA).toHaveLength(65);
    expect(hater).toHaveLength(65);
    expect(harshA).toHaveLength(65);
    expect(bimodal).toHaveLength(65);

    for (const item of [...loverA, ...hater, ...harshA, ...bimodal]) {
      expect(item.score).toBeGreaterThan(1.0);
      expect(item.score).toBeLessThanOrEqual(10.0);
    }
    expect(Math.min(...loverA.map((x) => x.score))).toBeGreaterThanOrEqual(7.2);
    expect(loverA.every((x) => getTierForScore(x.score).id === 'like')).toBe(true);
    expect(Math.max(...hater.map((x) => x.score))).toBeLessThanOrEqual(3.34);
    expect(hater.every((x) => getTierForScore(x.score).id === 'dislike')).toBe(true);
    expect(Math.max(...harshA.map((x) => x.score))).toBeLessThanOrEqual(7.8);
  });

  it('builds descending ranked items with consistent non-increasing scores across all strategies', () => {
    const users = generateMockUsers(1337);
    const items = getDatasetItems(users, 'diner:6', 1337);
    const beforeScores = items.map((x) => x.score);
    const afterByStrategy = {
      quantile_map: normalizeScores(beforeScores, 'quantile_map'),
      zscore_sigmoid: normalizeScores(beforeScores, 'zscore_sigmoid'),
      piecewise_bucket: normalizeScores(beforeScores, 'piecewise_bucket', { bucketCount: 4 }),
    };

    const ranked = buildRankedItems(items, beforeScores, afterByStrategy);
    expect(ranked).toHaveLength(items.length);
    expect(ranked[0].rank).toBe(1);
    expect(ranked[ranked.length - 1].rank).toBe(items.length);

    for (let i = 0; i < ranked.length - 1; i += 1) {
      expect(ranked[i].beforeScore).toBeGreaterThanOrEqual(ranked[i + 1].beforeScore);
      expect(ranked[i].afterScores.quantile_map).toBeGreaterThanOrEqual(
        ranked[i + 1].afterScores.quantile_map,
      );
      expect(ranked[i].afterScores.zscore_sigmoid).toBeGreaterThanOrEqual(
        ranked[i + 1].afterScores.zscore_sigmoid,
      );
      expect(ranked[i].afterScores.piecewise_bucket).toBeGreaterThanOrEqual(
        ranked[i + 1].afterScores.piecewise_bucket,
      );
    }

    expect(verifyRankOrderPreserved(beforeScores, afterByStrategy.quantile_map)).toBe(true);
    expect(verifyRankOrderPreserved(beforeScores, afterByStrategy.zscore_sigmoid)).toBe(true);
    expect(verifyRankOrderPreserved(beforeScores, afterByStrategy.piecewise_bucket)).toBe(true);
  });

  it('reflects KDE cleanly at boundaries so uniform distributions stay flat', () => {
    const uniform = Array.from({ length: 180 }, (_, i) => 1.02 + (i / 179) * 8.96);
    const curve = computeDensityCurve(uniform, 90, 0.36);
    expect(curve).toHaveLength(91);

    const leftEdge = curve[0].density;
    const center = curve[45].density;
    const rightEdge = curve[90].density;

    expect(Math.abs(leftEdge - center) / center).toBeLessThan(0.15);
    expect(Math.abs(rightEdge - center) / center).toBeLessThan(0.15);
  });

  it('separates identical x coordinates in beeswarm packing without NaN', () => {
    const offsets = computeBeeswarmOffsets([200, 200, 200, 200, 450, 452], 4.2, 62);
    expect(offsets).toHaveLength(6);
    for (const y of offsets) {
      expect(Number.isFinite(y)).toBe(true);
      expect(y).toBeGreaterThanOrEqual(0);
    }
    const uniqueFirstFour = new Set(offsets.slice(0, 4).map((v) => v.toFixed(2)));
    expect(uniqueFirstFour.size).toBe(4);
  });

  it('computes piecewise bucket bands that account for all items and partition output range', () => {
    const scores = [2.1, 7.6, 7.8, 8.1, 8.2, 8.4, 9.2];
    const bands = computePiecewiseBuckets(scores, 4);
    expect(bands).toHaveLength(4);
    expect(bands.reduce((acc, b) => acc + b.count, 0)).toBe(scores.length);

    const nonEmpty = bands.filter((b) => b.count > 0);
    expect(nonEmpty[0].outMin).toBeCloseTo(1.0, 5);
    expect(nonEmpty[nonEmpty.length - 1].outMax).toBeCloseTo(MAX_SCORE, 5);
    for (let i = 0; i < nonEmpty.length - 1; i += 1) {
      expect(nonEmpty[i].outMax).toBeCloseTo(nonEmpty[i + 1].outMin, 6);
    }
    expect(MIN_SCORE).toBeGreaterThan(1.0);
  });

  it('samples display indices cleanly and computes distribution summary', () => {
    const users = generateMockUsers(1337);
    const allItems = getDatasetItems(users, 'all', 1337);
    const beforeScores = allItems.map((x) => x.score);
    const afterByStrategy = {
      quantile_map: normalizeScores(beforeScores, 'quantile_map'),
      zscore_sigmoid: normalizeScores(beforeScores, 'zscore_sigmoid'),
      piecewise_bucket: normalizeScores(beforeScores, 'piecewise_bucket', { bucketCount: 4 }),
    };
    const ranked = buildRankedItems(allItems, beforeScores, afterByStrategy);
    const sample = selectDisplayIndices(ranked, 120);
    expect(sample.length).toBeLessThanOrEqual(120);
    expect(sample[0]).toBe(0);
    expect(sample[sample.length - 1]).toBe(ranked.length - 1);

    const summary = computeDistributionSummary(beforeScores);
    expect(summary.count).toBe(allItems.length);
    expect(summary.iqr).toBeGreaterThan(0);
    expect(summary.tiers.reduce((acc, row) => acc + row.count, 0)).toBe(allItems.length);
  });
});
