<script lang="ts">
  import {
    computeDistributionSummary,
    FOOD_TIERS,
    formatDatasetNames,
    getDatasetItems,
    type DatasetId,
  } from '../lib/foodInsights';
  import type { UserRatings } from '../lib/types';

  type Props = {
    users: UserRatings[];
    seed: number;
    onTryInDemo: (datasetId: DatasetId) => void;
  };

  let { users, seed, onTryInDemo }: Props = $props();

  const scoreToPct = (score: number): number =>
    ((Math.max(1.0, Math.min(10.0, score)) - 1.0) / 9.0) * 100;

  // Card 1: Tight 8.0-8.6 Pack (diner:0)
  const crowdedData = $derived.by(() => {
    const items = getDatasetItems(users, 'diner:0', seed);
    const scores = items.map((x) => x.score);
    const summary = computeDistributionSummary(scores);
    const formatted = formatDatasetNames(items);

    const sorted = items
      .map((item, idx) => ({
        name: formatted[idx].displayName,
        cuisine: formatted[idx].cuisine,
        score: item.score,
      }))
      .sort((a, b) => b.score - a.score);

    const n = sorted.length;
    const sampleRanks = [0, 14, 34, 54]
      .filter((i) => i < n)
      .map((i) => ({
        rank: i + 1,
        ...sorted[i],
      }));

    // Share inside the tight 7.5-9.0 band
    const inTightBand = scores.filter((s) => s >= 7.5 && s <= 9.0).length;
    const tightPct = n > 0 ? Math.round((inTightBand / n) * 100) : 0;

    return {
      count: n,
      summary,
      sampleRanks,
      tightPct,
      clusterLeft: scoreToPct(summary.p25),
      clusterWidth: Math.max(2, scoreToPct(summary.p75) - scoreToPct(summary.p25)),
    };
  });

  // Card 2: Generous Lover vs Tough Critic
  const scaleComparison = $derived.by(() => {
    const loverItems = getDatasetItems(users, 'preset:lover', seed);
    const harshItems = getDatasetItems(users, 'preset:harsh', seed);

    const loverScores = loverItems.map((x) => x.score);
    const harshScores = harshItems.map((x) => x.score);

    const loverSummary = computeDistributionSummary(loverScores);
    const harshSummary = computeDistributionSummary(harshScores);

    return {
      lover: {
        median: loverSummary.median,
        best: loverSummary.max,
        p25: loverSummary.p25,
        p75: loverSummary.p75,
      },
      harsh: {
        median: harshSummary.median,
        best: harshSummary.max,
        p25: harshSummary.p25,
        p75: harshSummary.p75,
      },
    };
  });
</script>

<section id="problem" class="pitch-section">
  <div class="section-head">
    <span class="section-eyebrow">01 · The Problem</span>
    <h2 class="section-title">The 8.2 Traffic Jam</h2>
    <p class="section-lead">
      Diners naturally visit restaurants they expect to enjoy. Once a <strong>Been</strong> list
      reaches 50–500+ spots, almost everything piles into <em>I liked it!</em> That squeezes
      all-time favorites and average weeknight spots into the same tiny band.
    </p>
  </div>

  <div class="problem-grid">
    <!-- Card 1: One Diner's Crowded Been List -->
    <article class="problem-card card">
      <div class="card-head">
        <h3>One Diner's Crowded Been List</h3>
        <span class="card-badge num">{crowdedData.tightPct}% of spots in 7.5–9.0</span>
      </div>

      <p class="card-copy">
        On a typical crowded list ({crowdedData.count} spots), half of all restaurants sit inside a
        <strong>{crowdedData.summary.iqr.toFixed(1)}-point</strong> sliver ({crowdedData.summary.p25.toFixed(1)}–{crowdedData.summary.p75.toFixed(1)}).
      </p>

      <div class="mini-ruler-wrap" aria-label="Score crowding on the 1 to 10 Beli scale">
        <div class="tier-strip">
          {#each FOOD_TIERS as tier (tier.id)}
            <div
              class="tier-zone"
              style={`width: ${((tier.max - tier.min) / 9.0) * 100}%; background: ${tier.softBg}; color: ${tier.textColor};`}
            >
              <span>{tier.shortLabel}</span>
            </div>
          {/each}
        </div>

        <div class="cluster-track">
          <div
            class="cluster-pill"
            style={`left: ${crowdedData.clusterLeft}%; width: ${crowdedData.clusterWidth}%;`}
            title={`Middle 50%: ${crowdedData.summary.p25.toFixed(1)}–${crowdedData.summary.p75.toFixed(1)}`}
          ></div>
        </div>

        <div class="ruler-nums num">
          <span>1</span>
          <span>3.3</span>
          <span>6.6</span>
          <span>10</span>
        </div>
      </div>

      <div class="sample-ranks">
        {#each crowdedData.sampleRanks as row (row.rank)}
          <div class="sample-row">
            <span class="sample-rank num">#{row.rank}</span>
            <span class="sample-name">{row.name}</span>
            <span class="sample-score num">{row.score.toFixed(1)}</span>
          </div>
        {/each}
      </div>

      <button type="button" class="demo-jump-btn" onclick={() => onTryInDemo('diner:0')}>
        See this list open up in the demo →
      </button>
    </article>

    <!-- Card 2: Two Friends, Same Taste, Different Scales -->
    <article class="problem-card card">
      <div class="card-head">
        <h3>Two Friends, Same Taste, Different Scales</h3>
        <span class="card-badge">Friend &amp; Rec Score Bias</span>
      </div>

      <p class="card-copy">
        Because every user's list drifts into their own habit, raw numbers stop meaning the same
        thing from person to person.
      </p>

      <div class="friend-meters">
        <div class="friend-row">
          <div class="friend-meta">
            <strong>Generous Friend</strong>
            <span class="num">
              Typical: {scaleComparison.lover.median.toFixed(1)} · #1 Spot: {scaleComparison.lover.best.toFixed(1)}
            </span>
          </div>
          <div class="meter-track">
            <div
              class="meter-range lover"
              style={`left: ${scoreToPct(scaleComparison.lover.p25)}%; width: ${Math.max(3, scoreToPct(scaleComparison.lover.p75) - scoreToPct(scaleComparison.lover.p25))}%;`}
            ></div>
            <div
              class="meter-dot lover"
              style={`left: ${scoreToPct(scaleComparison.lover.best)}%;`}
              title={`#1 spot: ${scaleComparison.lover.best.toFixed(1)}`}
            ></div>
          </div>
        </div>

        <div class="friend-row">
          <div class="friend-meta">
            <strong>Picky Critic</strong>
            <span class="num">
              Typical: {scaleComparison.harsh.median.toFixed(1)} · #1 Spot: {scaleComparison.harsh.best.toFixed(1)}
            </span>
          </div>
          <div class="meter-track">
            <div
              class="meter-range harsh"
              style={`left: ${scoreToPct(scaleComparison.harsh.p25)}%; width: ${Math.max(3, scoreToPct(scaleComparison.harsh.p75) - scoreToPct(scaleComparison.harsh.p25))}%;`}
            ></div>
            <div
              class="meter-dot harsh"
              style={`left: ${scoreToPct(scaleComparison.harsh.best)}%;`}
              title={`#1 spot: ${scaleComparison.harsh.best.toFixed(1)}`}
            ></div>
          </div>
        </div>
      </div>

      <p class="punchline">
        The picky friend's <strong>#1 spot of the year</strong> ({scaleComparison.harsh.best.toFixed(1)})
        looks worse on paper than the generous friend's average Tuesday takeout ({scaleComparison.lover.median.toFixed(1)}), blurring
        <strong>Friend Scores</strong> and <strong>Rec Scores</strong>.
      </p>

      <button type="button" class="demo-jump-btn" onclick={() => onTryInDemo('preset:harsh')}>
        Compare Tough Critic in the demo →
      </button>
    </article>
  </div>
</section>

<style>
  .problem-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
    align-items: stretch;
  }

  .problem-card {
    padding: 20px 22px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  .card-head {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  h3 {
    margin: 0;
    font-size: 1.04rem;
    font-weight: 700;
    color: var(--ink);
  }

  .card-badge {
    font-size: 0.74rem;
    font-weight: 700;
    color: var(--accent);
    background: var(--accent-soft);
    padding: 3px 9px;
    border-radius: 999px;
  }

  .card-copy {
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.5;
    color: var(--ink-muted);
  }

  .mini-ruler-wrap {
    display: grid;
    gap: 6px;
  }

  .tier-strip {
    display: flex;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--border);
  }

  .tier-zone {
    font-size: 0.7rem;
    font-weight: 700;
    text-align: center;
    padding: 4px 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cluster-track {
    position: relative;
    height: 10px;
    background: var(--surface-subtle);
    border-radius: 999px;
    border: 1px solid var(--border);
  }

  .cluster-pill {
    position: absolute;
    top: -1px;
    bottom: -1px;
    background: var(--accent);
    border-radius: 999px;
  }

  .ruler-nums {
    display: flex;
    justify-content: space-between;
    font-size: 0.72rem;
    color: var(--ink-soft);
  }

  .sample-ranks {
    display: grid;
    gap: 5px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 10px 12px;
  }

  .sample-row {
    display: grid;
    grid-template-columns: 36px minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
  }

  .sample-rank {
    font-weight: 700;
    color: var(--ink-muted);
  }

  .sample-name {
    font-weight: 600;
    color: var(--ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sample-score {
    font-weight: 800;
    color: var(--tier-like);
  }

  .friend-meters {
    display: grid;
    gap: 12px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 14px;
  }

  .friend-row {
    display: grid;
    gap: 5px;
  }

  .friend-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 6px;
    font-size: 0.82rem;
  }

  .friend-meta span {
    color: var(--ink-muted);
    font-size: 0.78rem;
  }

  .meter-track {
    position: relative;
    height: 10px;
    border-radius: 999px;
    background: var(--surface);
    border: 1px solid var(--border);
  }

  .meter-range {
    position: absolute;
    top: -1px;
    bottom: -1px;
    border-radius: 999px;
    opacity: 0.38;
  }

  .meter-range.lover {
    background: var(--tier-like);
  }

  .meter-range.harsh {
    background: var(--tier-okay);
  }

  .meter-dot {
    position: absolute;
    top: 50%;
    width: 11px;
    height: 11px;
    transform: translate(-50%, -50%);
    border-radius: 999px;
    border: 2px solid #ffffff;
    box-shadow: 0 1px 3px rgba(31, 27, 22, 0.25);
  }

  .meter-dot.lover {
    background: var(--tier-like);
  }

  .meter-dot.harsh {
    background: var(--accent);
  }

  .punchline {
    margin: 0;
    font-size: 0.86rem;
    line-height: 1.5;
    color: var(--ink-muted);
    background: #fcfaf6;
    border-left: 3px solid var(--accent);
    padding: 9px 12px;
    border-radius: 0 8px 8px 0;
  }

  .demo-jump-btn {
    margin-top: auto;
    align-self: flex-start;
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--ink);
    font-size: 0.83rem;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 999px;
    transition: background-color 0.12s ease, border-color 0.12s ease;
  }

  .demo-jump-btn:hover {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }

  @media (max-width: 860px) {
    .problem-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
