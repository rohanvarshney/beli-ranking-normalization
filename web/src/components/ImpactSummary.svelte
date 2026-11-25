<script lang="ts">
  import {
    computeDistributionSummary,
    getTierForScore,
    STRATEGY_LIST,
    verifyRankOrderPreserved,
    type RankedRestaurantBase,
  } from '../lib/foodInsights';
  import type { Strategy } from '../lib/types';
  import InfoBanner from './InfoBanner.svelte';
  import InfoButton from './InfoButton.svelte';

  type Props = {
    ranked: RankedRestaurantBase[];
    beforeScores: number[];
    currentScores: number[];
    strategy: Strategy;
    progress: number;
    hoveredId: string | null;
    selectedId: string | null;
    onSelectStrategy: (next: Strategy) => void;
  };

  let {
    ranked,
    beforeScores,
    currentScores,
    strategy,
    progress,
    hoveredId,
    selectedId,
    onSelectStrategy,
  }: Props = $props();

  let showTierInfo = $state(false);
  let showSpreadInfo = $state(false);
  let showCompareInfo = $state(false);

  const beforeSummary = $derived(computeDistributionSummary(beforeScores));
  const currentSummary = $derived(computeDistributionSummary(currentScores));
  const orderPreserved = $derived(verifyRankOrderPreserved(beforeScores, currentScores));

  const iqrMultiplier = $derived.by(() => {
    if (beforeSummary.iqr <= 0.05) return null;
    const ratio = currentSummary.iqr / beforeSummary.iqr;
    if (Math.abs(ratio - 1) < 0.05) return 'Unchanged';
    return ratio > 1 ? `${ratio.toFixed(1)}× wider` : `${ratio.toFixed(1)}× narrower`;
  });

  const gapMultiplier = $derived.by(() => {
    if (beforeSummary.medianAdjacentGap <= 1e-4) return null;
    const ratio = currentSummary.medianAdjacentGap / beforeSummary.medianAdjacentGap;
    if (Math.abs(ratio - 1) < 0.08) return 'Same spacing';
    return ratio > 1 ? `${ratio.toFixed(1)}× clearer` : `${ratio.toFixed(1)}× tighter`;
  });

  const spotlightSpot = $derived.by(() => {
    if (ranked.length === 0) return null;
    const targetId = hoveredId ?? selectedId;
    if (targetId) {
      const found = ranked.find((r) => r.id === targetId);
      if (found) return found;
    }
    return ranked[Math.floor(ranked.length / 2)];
  });

  const anchors = $derived.by(() => {
    if (ranked.length === 0) return null;
    const best = ranked[0];
    const median = ranked[Math.floor(ranked.length / 2)];
    const lowest = ranked[ranked.length - 1];
    return {
      best: {
        rank: best.rank,
        raw: best.beforeScore,
        curr: currentScores[best.index] ?? best.beforeScore,
      },
      median: {
        rank: median.rank,
        raw: median.beforeScore,
        curr: currentScores[median.index] ?? median.beforeScore,
      },
      lowest: {
        rank: lowest.rank,
        raw: lowest.beforeScore,
        curr: currentScores[lowest.index] ?? lowest.beforeScore,
      },
    };
  });

  const scoreToPct = (score: number): number =>
    ((Math.max(1.0, Math.min(10.0, score)) - 1.0) / 9.0) * 100;

  const formatGap = (gap: number): string => {
    if (gap <= 0) return '0.00';
    if (gap < 0.005) return gap.toFixed(4);
    if (gap < 0.05) return gap.toFixed(3);
    return gap.toFixed(2);
  };
</script>

<aside class="summary-stack" aria-label="Normalization impact summary">
  <!-- 1. Food Tier Shift -->
  <section class="sub-card card">
    <div class="sub-head">
      <div class="sub-head-row">
        <h3>Where Your Restaurants Land</h3>
        <InfoButton
          open={showTierInfo}
          onToggle={() => (showTierInfo = !showTierInfo)}
          label="How Beli tier cutoffs work"
          controlsId="tier-info-banner"
          compact
        />
      </div>
      <span class="sub-tag">{beforeSummary.crowdedHeadline}</span>
    </div>

    {#if showTierInfo}
      <InfoBanner
        id="tier-info-banner"
        title="Tier thresholds"
        onClose={() => (showTierInfo = false)}
      >
        <p>
          Beli tiers use fixed score cutoffs:
          <code class="tech-term">0.1–3.34</code> I Don't Like,
          <code class="tech-term">3.35–6.64</code> It's Okay, and
          <code class="tech-term">6.65–10.0</code> I Like. Spreading out a positively skewed list
          moves some mid-ranked spots across thresholds without changing rank order.
        </p>
      </InfoBanner>
    {/if}

    <div class="stacked-bars">
      <div class="bar-row">
        <span class="bar-label">Before (Original)</span>
        <div class="stacked-track" role="img" aria-label="Before tier breakdown">
          {#each beforeSummary.tiers as row (row.tier.id)}
            {#if row.pct > 0}
              <div
                class="stack-seg"
                style={`width: ${row.pct}%; background: ${row.tier.color};`}
                title={`${row.tier.label}: ${row.count} spots (${row.pct.toFixed(0)}%)`}
              ></div>
            {/if}
          {/each}
        </div>
      </div>

      <div class="bar-row">
        <span class="bar-label num">Now ({Math.round(progress * 100)}%)</span>
        <div class="stacked-track" role="img" aria-label="Current normalized tier breakdown">
          {#each currentSummary.tiers as row (row.tier.id)}
            {#if row.pct > 0}
              <div
                class="stack-seg"
                style={`width: ${row.pct}%; background: ${row.tier.color};`}
                title={`${row.tier.label}: ${row.count} spots (${row.pct.toFixed(0)}%)`}
              ></div>
            {/if}
          {/each}
        </div>
      </div>
    </div>

    <div class="tier-table">
      {#each currentSummary.tiers as currRow, idx (currRow.tier.id)}
        {@const prevRow = beforeSummary.tiers[idx]}
        <div class="tier-line">
          <div class="tier-name-cell">
            <span class="tier-dot" style={`background: ${currRow.tier.color};`}></span>
            <span class="tier-label">{currRow.tier.label}</span>
            <span class="tier-range num">{currRow.tier.rangeLabel}</span>
          </div>
          <div class="tier-count-cell num">
            <span class="muted-count">{prevRow.count} ({Math.round(prevRow.pct)}%)</span>
            <span class="arrow">→</span>
            <strong style={`color: ${currRow.tier.textColor}`}>
              {currRow.count} ({Math.round(currRow.pct)}%)
            </strong>
          </div>
        </div>
      {/each}
    </div>
  </section>

  <!-- 2. Score Spread & Order -->
  <section class="sub-card card">
    <div class="sub-head">
      <div class="sub-head-row">
        <h3>Score Spread &amp; Order</h3>
        <InfoButton
          open={showSpreadInfo}
          onToggle={() => (showSpreadInfo = !showSpreadInfo)}
          label="Spread and order statistics"
          controlsId="spread-info-banner"
          compact
        />
      </div>
      <span class="order-pill" class:ok={orderPreserved}>
        {orderPreserved ? '✓ Every rank stays in order' : 'Order check warning'}
      </span>
    </div>

    {#if showSpreadInfo}
      <InfoBanner
        id="spread-info-banner"
        title="Spread & order statistics"
        onClose={() => (showSpreadInfo = false)}
      >
        <ul class="info-list">
          <li class="num">
            <code class="tech-term">IQR (p75 − p25)</code>: Interquartile range of the middle 50%
            ({beforeSummary.p25.toFixed(2)}–{beforeSummary.p75.toFixed(2)} before →
            {currentSummary.p25.toFixed(2)}–{currentSummary.p75.toFixed(2)} now).
          </li>
          <li>
            <code class="tech-term">Median adjacent gap</code>: Median score gap between
            consecutive ranked spots (<code class="tech-term">sorted[k+1] − sorted[k]</code>).
          </li>
          <li class="num">
            <code class="tech-term">Monotonicity check</code>: Verifies
            <code class="tech-term">before[i] &lt; before[j] ⇒ after[i] ≤ after[j]</code> across
            all {ranked.length.toLocaleString()} spots.
          </li>
        </ul>
      </InfoBanner>
    {/if}

    <div class="metric-blocks">
      <div class="metric-item">
        <div class="metric-top">
          <span class="metric-name">Score Spread</span>
          <div class="metric-vals num">
            <span class="muted-val">{beforeSummary.iqr.toFixed(1)} pts</span>
            <span class="arrow">→</span>
            <strong>{currentSummary.iqr.toFixed(1)} pts</strong>
            {#if iqrMultiplier}
              <span class="mult-badge">{iqrMultiplier}</span>
            {/if}
          </div>
        </div>
        <div class="iqr-bars">
          <div class="iqr-track">
            <div
              class="iqr-fill raw"
              style={`left: ${scoreToPct(beforeSummary.p25)}%; width: ${Math.max(1.5, scoreToPct(beforeSummary.p75) - scoreToPct(beforeSummary.p25))}%;`}
            ></div>
          </div>
          <div class="iqr-track">
            <div
              class="iqr-fill curr"
              style={`left: ${scoreToPct(currentSummary.p25)}%; width: ${Math.max(1.5, scoreToPct(currentSummary.p75) - scoreToPct(currentSummary.p25))}%;`}
            ></div>
          </div>
        </div>
      </div>

      <div class="metric-item">
        <div class="metric-top">
          <span class="metric-name">Space Between Spots</span>
          <div class="metric-vals num">
            <span class="muted-val">{formatGap(beforeSummary.medianAdjacentGap)} pts</span>
            <span class="arrow">→</span>
            <strong>{formatGap(currentSummary.medianAdjacentGap)} pts</strong>
            {#if gapMultiplier}
              <span class="mult-badge">{gapMultiplier}</span>
            {/if}
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- 3. Compare Styles on One Spot -->
  {#if spotlightSpot}
    {@const rawTier = getTierForScore(spotlightSpot.beforeScore)}
    <section class="sub-card card">
      <div class="sub-head">
        <div class="sub-head-row">
          <h3>Compare Styles on One Spot</h3>
          <InfoButton
            open={showCompareInfo}
            onToggle={() => (showCompareInfo = !showCompareInfo)}
            label="Algorithm and percentile details"
            controlsId="compare-info-banner"
            compact
          />
        </div>
        <span class="spot-chip num">
          #{spotlightSpot.rank} {spotlightSpot.displayName} · Originally
          <strong style={`color: ${rawTier.textColor}`}>
            {spotlightSpot.beforeScore.toFixed(2)}
          </strong>
        </span>
      </div>

      {#if showCompareInfo}
        <InfoBanner
          id="compare-info-banner"
          title="Algorithm & percentile details"
          onClose={() => (showCompareInfo = false)}
        >
          <ul class="info-list">
            <li class="num">
              Spotlight rank position:
              <code class="tech-term">{(spotlightSpot.percentile * 100).toFixed(1)}th percentile</code>.
            </li>
            <li>
              Styles: <code class="tech-term">quantile_map</code> (Even Spread),
              <code class="tech-term">zscore_sigmoid</code> (Bell Balance),
              <code class="tech-term">piecewise_bucket</code> (Bucket Stretch).
            </li>
            <li>
              Quick Check tracks the 3 distribution anchors:
              <code class="tech-term">max / #1</code>,
              <code class="tech-term">median / p50</code>, and
              <code class="tech-term">min / #N</code>.
            </li>
          </ul>
        </InfoBanner>
      {/if}

      <div class="compare-list">
        {#each STRATEGY_LIST as meta (meta.id)}
          {@const targetScore = spotlightSpot.afterScores[meta.id]}
          {@const targetTier = getTierForScore(targetScore)}
          {@const delta = targetScore - spotlightSpot.beforeScore}
          {@const active = strategy === meta.id}
          <button
            type="button"
            class="compare-row"
            class:active
            onclick={() => onSelectStrategy(meta.id)}
          >
            <div class="compare-left">
              <span class="compare-title">{meta.title}</span>
              <span class="compare-tag">{meta.shortTag}</span>
            </div>
            <div class="compare-right num">
              <strong style={`color: ${targetTier.textColor}`}>{targetScore.toFixed(2)}</strong>
              <span class="compare-delta">
                ({delta >= 0 ? '+' : ''}{delta.toFixed(2)})
              </span>
            </div>
          </button>
        {/each}
      </div>

      {#if anchors}
        <p class="anchor-summary num">
          <strong>Quick Check:</strong>
          Your #1 spot moves
          {anchors.best.raw.toFixed(1)} → {anchors.best.curr.toFixed(1)},
          your middle spot (#{anchors.median.rank}) moves
          {anchors.median.raw.toFixed(1)} → {anchors.median.curr.toFixed(1)},
          and your lowest (#{anchors.lowest.rank}) moves
          {anchors.lowest.raw.toFixed(1)} → {anchors.lowest.curr.toFixed(1)}.
        </p>
      {/if}
    </section>
  {/if}
</aside>

<style>
  .summary-stack {
    display: grid;
    gap: 16px;
  }

  .sub-card {
    padding: 15px 16px;
    display: grid;
    gap: 12px;
  }

  .sub-head {
    display: grid;
    gap: 4px;
  }

  .sub-head-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  h3 {
    margin: 0;
    font-size: 0.96rem;
    font-weight: 700;
    color: var(--ink);
  }

  .sub-tag {
    font-size: 0.8rem;
    color: var(--ink-muted);
  }

  .stacked-bars {
    display: grid;
    gap: 8px;
  }

  .bar-row {
    display: grid;
    gap: 4px;
  }

  .bar-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--ink-muted);
  }

  .stacked-track {
    height: 14px;
    border-radius: 999px;
    overflow: hidden;
    display: flex;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
  }

  .stack-seg {
    height: 100%;
    transition: width 0.1s linear;
  }

  .tier-table {
    display: grid;
    gap: 6px;
    padding-top: 4px;
    border-top: 1px dashed var(--border);
  }

  .tier-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    font-size: 0.81rem;
  }

  .tier-name-cell {
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .tier-dot {
    width: 9px;
    height: 9px;
    border-radius: 999px;
    flex-shrink: 0;
  }

  .tier-label {
    font-weight: 600;
    color: var(--ink);
  }

  .tier-range {
    font-size: 0.74rem;
    color: var(--ink-soft);
  }

  .tier-count-cell {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .muted-count,
  .muted-val,
  .arrow {
    color: var(--ink-soft);
  }

  .order-pill {
    justify-self: start;
    font-size: 0.76rem;
    font-weight: 700;
    padding: 3px 9px;
    border-radius: 999px;
    background: #fcecec;
    color: #c04545;
  }

  .order-pill.ok {
    background: #e6f5ee;
    color: #1d7a52;
  }

  .metric-blocks {
    display: grid;
    gap: 12px;
  }

  .metric-item {
    display: grid;
    gap: 6px;
  }

  .metric-top {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
  }

  .metric-name {
    font-weight: 600;
    color: var(--ink);
  }

  .metric-vals {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .mult-badge {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 1px 7px;
    border-radius: 999px;
  }

  .iqr-bars {
    display: grid;
    gap: 4px;
  }

  .iqr-track {
    position: relative;
    height: 7px;
    border-radius: 999px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
  }

  .iqr-fill {
    position: absolute;
    top: -1px;
    bottom: -1px;
    border-radius: 999px;
  }

  .iqr-fill.raw {
    background: #a5998c;
  }

  .iqr-fill.curr {
    background: var(--accent);
  }

  .spot-chip {
    font-size: 0.8rem;
    color: var(--ink-muted);
  }

  .compare-list {
    display: grid;
    gap: 6px;
  }

  .compare-row {
    width: 100%;
    text-align: left;
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: 10px;
    padding: 8px 11px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    transition: border-color 0.12s ease, background-color 0.12s ease;
  }

  .compare-row:hover {
    background: var(--surface-hover);
    border-color: var(--border-strong);
  }

  .compare-row.active {
    background: #fffcf8;
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }

  .compare-left {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .compare-title {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--ink);
  }

  .compare-tag {
    font-size: 0.72rem;
    color: var(--ink-soft);
    background: var(--surface-subtle);
    padding: 1px 7px;
    border-radius: 999px;
  }

  .compare-right {
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.88rem;
  }

  .compare-delta {
    font-size: 0.76rem;
    color: var(--ink-muted);
  }

  .anchor-summary {
    margin: 0;
    font-size: 0.79rem;
    line-height: 1.45;
    color: var(--ink-muted);
    background: var(--surface-subtle);
    border-radius: 9px;
    padding: 8px 10px;
  }
</style>
