<script lang="ts">
  import { getTierForScore, type RankedRestaurantBase } from '../lib/foodInsights';
  import type { Strategy } from '../lib/types';

  type FilterTab = 'all' | 'top10' | 'middle' | 'bottom10' | 'shifts';

  type Props = {
    ranked: RankedRestaurantBase[];
    currentScores: number[];
    strategy: Strategy;
    hoveredId: string | null;
    selectedId: string | null;
    onHover: (id: string | null) => void;
    onSelect: (id: string | null) => void;
  };

  let { ranked, currentScores, strategy, hoveredId, selectedId, onHover, onSelect }: Props = $props();

  let activeTab = $state<FilterTab>('all');
  let searchQuery = $state('');
  let visibleLimit = $state(80);

  $effect(() => {
    // Reset pagination cap when filter or dataset changes
    void activeTab;
    void searchQuery;
    void ranked;
    visibleLimit = 80;
  });

  const spotlightItem = $derived.by(() => {
    if (ranked.length === 0) return null;
    const targetId = hoveredId ?? selectedId;
    if (targetId) {
      const found = ranked.find((r) => r.id === targetId);
      if (found) return found;
    }
    return ranked[Math.floor(ranked.length / 2)];
  });

  const spotlightContext = $derived.by(() => {
    if (!spotlightItem) return null;
    const pos = spotlightItem.rank - 1;
    const currScore = currentScores[spotlightItem.index] ?? spotlightItem.beforeScore;
    const delta = currScore - spotlightItem.beforeScore;
    const rawTier = getTierForScore(spotlightItem.beforeScore);
    const currTier = getTierForScore(currScore);

    const prevItem = pos > 0 ? ranked[pos - 1] : null;
    const nextItem = pos < ranked.length - 1 ? ranked[pos + 1] : null;

    const rawGaps: number[] = [];
    const currGaps: number[] = [];
    if (prevItem) {
      rawGaps.push(Math.abs(prevItem.beforeScore - spotlightItem.beforeScore));
      currGaps.push(
        Math.abs((currentScores[prevItem.index] ?? prevItem.beforeScore) - currScore),
      );
    }
    if (nextItem) {
      rawGaps.push(Math.abs(spotlightItem.beforeScore - nextItem.beforeScore));
      currGaps.push(
        Math.abs(currScore - (currentScores[nextItem.index] ?? nextItem.beforeScore)),
      );
    }

    const closestRawGap = rawGaps.length > 0 ? Math.min(...rawGaps) : null;
    const closestCurrGap = currGaps.length > 0 ? Math.min(...currGaps) : null;
    const isPinned = selectedId === spotlightItem.id;
    const isHovered = hoveredId === spotlightItem.id;

    return {
      item: spotlightItem,
      currScore,
      delta,
      rawTier,
      currTier,
      closestRawGap,
      closestCurrGap,
      isPinned,
      isHovered,
    };
  });

  const filteredRows = $derived.by(() => {
    const n = ranked.length;
    if (n === 0) return [];

    let subset = ranked;
    if (activeTab === 'top10') {
      subset = ranked.slice(0, 10);
    } else if (activeTab === 'bottom10') {
      subset = ranked.slice(Math.max(0, n - 10));
    } else if (activeTab === 'middle') {
      const mid = Math.floor(n / 2);
      const start = Math.max(0, mid - 5);
      const end = Math.min(n, start + 10);
      subset = ranked.slice(start, end);
    } else if (activeTab === 'shifts') {
      subset = [...ranked].sort((a, b) => {
        const shiftA = Math.abs(
          (currentScores[a.index] ?? a.afterScores[strategy]) - a.beforeScore,
        );
        const shiftB = Math.abs(
          (currentScores[b.index] ?? b.afterScores[strategy]) - b.beforeScore,
        );
        return shiftB - shiftA;
      });
    }

    const q = searchQuery.trim().toLowerCase();
    if (!q) return subset;
    return subset.filter(
      (row) =>
        row.displayName.toLowerCase().includes(q) ||
        row.cuisine.toLowerCase().includes(q) ||
        `#${row.rank}`.includes(q),
    );
  });

  const shownRows = $derived(filteredRows.slice(0, visibleLimit));
  const hasMore = $derived(filteredRows.length > visibleLimit);

  const trackPct = (score: number): number => {
    const clamped = Math.max(1.0, Math.min(10.0, score));
    return ((clamped - 1.0) / 9.0) * 100;
  };

  const formatGap = (gap: number): string => {
    if (gap <= 0) return '0.00';
    if (gap < 0.005) return gap.toFixed(4);
    if (gap < 0.05) return gap.toFixed(3);
    return gap.toFixed(2);
  };
</script>

<section class="list-card card" aria-label="Ranked food list">
  <div class="list-header">
    <div>
      <h2>Sample "Been" List — Same Order, Clearer Scores</h2>
      <p class="subtitle">
        Every spot keeps its exact rank from #1 down to #{ranked.length.toLocaleString()}.
      </p>
    </div>
    <span class="count-pill num">{filteredRows.length.toLocaleString()} spots</span>
  </div>

  {#if spotlightContext}
    {@const sc = spotlightContext}
    <div class="spotlight">
      <div class="spotlight-top">
        <span class="spotlight-badge">
          {#if sc.isPinned}
            Pinned Spot
          {:else if sc.isHovered}
            Inspecting Spot
          {:else}
            Example · Middle Spot
          {/if}
        </span>

        {#if sc.isPinned}
          <button type="button" class="clear-pin" onclick={() => onSelect(null)}>
            Clear pin ×
          </button>
        {:else}
          <span class="spotlight-hint">Click any restaurant or dot to pin</span>
        {/if}
      </div>

      <div class="spotlight-main">
        <div class="spotlight-identity">
          <span class="spot-rank num">#{sc.item.rank} of {ranked.length.toLocaleString()}</span>
          <strong class="spot-name">{sc.item.displayName}</strong>
          <span class="cuisine-pill">{sc.item.cuisine}</span>
        </div>

        <div class="spotlight-scores num">
          <span class="raw-score">{sc.item.beforeScore.toFixed(2)}</span>
          <span class="arrow">→</span>
          <span class="new-score" style={`color: ${sc.currTier.textColor}`}>
            {sc.currScore.toFixed(2)}
          </span>
          <span class="delta-chip" class:up={sc.delta > 0.005} class:down={sc.delta < -0.005}>
            {sc.delta >= 0 ? '+' : ''}{sc.delta.toFixed(2)}
          </span>
        </div>
      </div>

      <div class="spotlight-meta">
        <span class="tier-shift">
          Tier:
          <strong style={`color: ${sc.rawTier.textColor}`}>{sc.rawTier.label}</strong>
          {#if sc.rawTier.id !== sc.currTier.id}
            <span class="arrow">→</span>
            <strong style={`color: ${sc.currTier.textColor}`}>{sc.currTier.label}</strong>
          {:else}
            <span class="same-tier">(unchanged)</span>
          {/if}
        </span>

        {#if sc.closestRawGap !== null && sc.closestCurrGap !== null}
          <span class="neighbor-gap num">
            Gap to neighbor:
            <strong>{formatGap(sc.closestRawGap)}</strong>
            →
            <strong>{formatGap(sc.closestCurrGap)} pts</strong>
          </span>
        {/if}
      </div>
    </div>
  {/if}

  <div class="filter-bar">
    <div class="tabs" role="tablist" aria-label="Filter ranked restaurants">
      {#each [
        { id: 'all', label: 'All' },
        { id: 'top10', label: 'Top 10' },
        { id: 'middle', label: 'Middle Pack' },
        { id: 'bottom10', label: 'Bottom 10' },
        { id: 'shifts', label: 'Biggest Shifts' },
      ] as tab (tab.id)}
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          class="tab-btn"
          class:active={activeTab === tab.id}
          onclick={() => (activeTab = tab.id as FilterTab)}
        >
          {tab.label}
        </button>
      {/each}
    </div>

    <input
      type="search"
      class="search-input"
      placeholder="Search spot or cuisine..."
      bind:value={searchQuery}
      aria-label="Search restaurants by name, cuisine, or rank"
    />
  </div>

  <div class="rows-scroll" role="list">
    {#if shownRows.length === 0}
      <div class="empty-state">No restaurants match "{searchQuery}".</div>
    {:else}
      {#each shownRows as row (row.id)}
        {@const currScore = currentScores[row.index] ?? row.beforeScore}
        {@const delta = currScore - row.beforeScore}
        {@const currTier = getTierForScore(currScore)}
        {@const rawPct = trackPct(row.beforeScore)}
        {@const currPct = trackPct(currScore)}
        {@const minPct = Math.min(rawPct, currPct)}
        {@const spanPct = Math.abs(currPct - rawPct)}
        {@const active = selectedId === row.id || hoveredId === row.id}

        <button
          type="button"
          class="food-row"
          class:selected={selectedId === row.id}
          class:hovered={hoveredId === row.id}
          class:active
          onmouseenter={() => onHover(row.id)}
          onmouseleave={() => onHover(null)}
          onclick={() => onSelect(selectedId === row.id ? null : row.id)}
        >
          <span class="rank-badge num" class:podium={row.rank <= 3}>#{row.rank}</span>

          <span class="name-col">
            <span class="spot-title">{row.displayName}</span>
            <span class="cuisine-tag">{row.cuisine}</span>
          </span>

          <span class="shift-track" aria-hidden="true">
            <span class="track-rail"></span>
            <span
              class="track-span"
              style={`left: ${minPct}%; width: ${spanPct}%; background: ${currTier.color};`}
            ></span>
            <span class="dot-raw" style={`left: ${rawPct}%;`}></span>
            <span
              class="dot-curr"
              style={`left: ${currPct}%; background: ${currTier.color};`}
            ></span>
          </span>

          <span class="score-col num">
            <span class="before-val">{row.beforeScore.toFixed(1)}</span>
            <span class="score-arrow">→</span>
            <span class="curr-val" style={`color: ${currTier.textColor}`}>
              {currScore.toFixed(1)}
            </span>
            <span class="delta-mini" class:up={delta > 0.05} class:down={delta < -0.05}>
              {delta >= 0 ? '+' : ''}{delta.toFixed(1)}
            </span>
          </span>
        </button>
      {/each}

      {#if hasMore}
        <button
          type="button"
          class="show-more"
          onclick={() => (visibleLimit += 100)}
        >
          Show 100 more ({(filteredRows.length - visibleLimit).toLocaleString()} remaining)
        </button>
      {/if}
    {/if}
  </div>
</section>

<style>
  .list-card {
    padding: 16px 18px;
    display: grid;
    gap: 12px;
  }

  .list-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
  }

  h2 {
    margin: 0;
    font-size: 1.05rem;
    font-weight: 700;
    color: var(--ink);
  }

  .subtitle {
    margin: 2px 0 0;
    font-size: 0.82rem;
    color: var(--ink-muted);
  }

  .count-pill {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--ink-muted);
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    padding: 3px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }

  .spotlight {
    background: #fcfaf6;
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 11px 13px;
    display: grid;
    gap: 7px;
  }

  .spotlight-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .spotlight-badge {
    font-size: 0.7rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--accent);
  }

  .spotlight-hint {
    font-size: 0.74rem;
    color: var(--ink-soft);
  }

  .clear-pin {
    border: 1px solid var(--border-strong);
    background: var(--surface);
    color: var(--ink-muted);
    font-size: 0.73rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 999px;
  }

  .clear-pin:hover {
    color: var(--ink);
    background: var(--surface-subtle);
  }

  .spotlight-main {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .spotlight-identity {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 7px;
  }

  .spot-rank {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--ink-muted);
    background: var(--surface-subtle);
    padding: 2px 7px;
    border-radius: 6px;
  }

  .spot-name {
    font-size: 0.96rem;
    color: var(--ink);
  }

  .cuisine-pill {
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--ink-muted);
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 1px 7px;
    border-radius: 999px;
  }

  .spotlight-scores {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.96rem;
    font-weight: 700;
  }

  .raw-score {
    color: var(--ink-soft);
  }

  .arrow {
    color: var(--ink-soft);
    font-weight: 400;
  }

  .new-score {
    font-weight: 800;
  }

  .delta-chip {
    font-size: 0.76rem;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 999px;
    background: var(--surface-subtle);
    color: var(--ink-muted);
  }

  .delta-chip.up {
    background: #e6f5ee;
    color: #1d7a52;
  }

  .delta-chip.down {
    background: #fdf0e4;
    color: #b45312;
  }

  .spotlight-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    gap: 8px;
    font-size: 0.78rem;
    color: var(--ink-muted);
    padding-top: 4px;
    border-top: 1px dashed var(--border);
  }

  .same-tier {
    color: var(--ink-soft);
  }

  .filter-bar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  .tab-btn {
    border: 1px solid transparent;
    background: transparent;
    color: var(--ink-muted);
    font-size: 0.78rem;
    font-weight: 600;
    padding: 5px 9px;
    border-radius: 8px;
  }

  .tab-btn:hover {
    background: var(--surface-subtle);
    color: var(--ink);
  }

  .tab-btn.active {
    background: var(--surface-subtle);
    border-color: var(--border-strong);
    color: var(--ink);
  }

  .search-input {
    border: 1px solid var(--border);
    background: var(--surface);
    border-radius: 9px;
    padding: 5px 10px;
    font-size: 0.82rem;
    min-width: 175px;
    flex: 1;
    max-width: 240px;
  }

  .rows-scroll {
    max-height: 420px;
    overflow-y: auto;
    display: grid;
    gap: 4px;
    padding-right: 4px;
  }

  .food-row {
    width: 100%;
    text-align: left;
    border: 1px solid transparent;
    background: transparent;
    border-radius: 10px;
    padding: 7px 9px;
    display: grid;
    grid-template-columns: 44px minmax(0, 1fr) 86px 124px;
    align-items: center;
    gap: 10px;
    transition: background-color 0.1s ease, border-color 0.1s ease;
  }

  .food-row:hover,
  .food-row.hovered {
    background: var(--surface-hover);
    border-color: var(--border);
  }

  .food-row.selected {
    background: #fff9f3;
    border-color: var(--accent);
  }

  .rank-badge {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--ink-muted);
    text-align: center;
    padding: 2px 5px;
    border-radius: 6px;
    background: var(--surface-subtle);
  }

  .rank-badge.podium {
    background: #fbf0d9;
    color: #96610c;
  }

  .name-col {
    display: flex;
    align-items: center;
    gap: 7px;
    min-width: 0;
  }

  .spot-title {
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cuisine-tag {
    font-size: 0.71rem;
    font-weight: 600;
    color: var(--ink-soft);
    background: var(--surface-subtle);
    padding: 1px 6px;
    border-radius: 999px;
    flex-shrink: 0;
  }

  .shift-track {
    position: relative;
    height: 16px;
    width: 86px;
  }

  .track-rail {
    position: absolute;
    left: 0;
    right: 0;
    top: 7px;
    height: 2px;
    border-radius: 999px;
    background: #e9e2d7;
  }

  .track-span {
    position: absolute;
    top: 7px;
    height: 2px;
    opacity: 0.55;
  }

  .dot-raw {
    position: absolute;
    top: 4px;
    width: 8px;
    height: 8px;
    margin-left: -4px;
    border-radius: 999px;
    background: #ffffff;
    border: 2px solid #9b8f82;
  }

  .dot-curr {
    position: absolute;
    top: 3.5px;
    width: 9px;
    height: 9px;
    margin-left: -4.5px;
    border-radius: 999px;
    border: 1.5px solid #ffffff;
    box-shadow: 0 1px 2px rgba(31, 27, 22, 0.2);
  }

  .score-col {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 4px;
    font-size: 0.82rem;
    white-space: nowrap;
  }

  .before-val {
    color: var(--ink-soft);
    font-weight: 500;
  }

  .score-arrow {
    color: var(--ink-soft);
    font-size: 0.76rem;
  }

  .curr-val {
    font-weight: 800;
    min-width: 24px;
    text-align: right;
  }

  .delta-mini {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--ink-soft);
    min-width: 34px;
    text-align: right;
  }

  .delta-mini.up {
    color: #1d7a52;
  }

  .delta-mini.down {
    color: #b45312;
  }

  .empty-state {
    padding: 24px 12px;
    text-align: center;
    font-size: 0.86rem;
    color: var(--ink-soft);
  }

  .show-more {
    margin-top: 6px;
    border: 1px solid var(--border);
    background: var(--surface-subtle);
    color: var(--ink);
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 0.82rem;
    font-weight: 600;
  }

  .show-more:hover {
    background: #ebe3d6;
  }

  @media (max-width: 640px) {
    .food-row {
      grid-template-columns: 38px minmax(0, 1fr) auto;
    }
    .shift-track {
      display: none;
    }
  }
</style>
