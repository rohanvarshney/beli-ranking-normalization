<script lang="ts">
  import { STRATEGY_LIST } from '../lib/foodInsights';
  import type { Strategy } from '../lib/types';

  type Props = {
    strategy: Strategy;
    bucketCount: number;
    onSelectStrategy: (next: Strategy) => void;
    onBucketCountChange: (count: number) => void;
  };

  let { strategy, bucketCount, onSelectStrategy, onBucketCountChange }: Props = $props();
</script>

<section class="strategy-section" aria-label="Scoring style selector">
  <div class="strategy-grid">
    {#each STRATEGY_LIST as item (item.id)}
      {@const active = strategy === item.id}
      <div class="strategy-card card" class:active>
        <div class="card-top">
          <div class="title-group">
            <button
              type="button"
              class="card-select-btn"
              aria-pressed={active}
              onclick={() => onSelectStrategy(item.id)}
            >
              <span class="strategy-title">{item.title}</span>
            </button>
          </div>

          <svg
            class="shape-thumb"
            width="56"
            height="26"
            viewBox="0 0 56 26"
            aria-hidden="true"
          >
            <line x1="2" y1="23" x2="54" y2="23" class="thumb-axis" />
            {#if item.id === 'quantile_map'}
              <rect x="4" y="9" width="48" height="13" rx="2" class="thumb-fill" />
              <line x1="4" y1="9" x2="52" y2="9" class="thumb-stroke" />
            {:else if item.id === 'zscore_sigmoid'}
              <path
                d="M 4 22 C 13 22, 18 5, 28 5 C 38 5, 43 22, 52 22 Z"
                class="thumb-fill"
              />
              <path
                d="M 4 22 C 13 22, 18 5, 28 5 C 38 5, 43 22, 52 22"
                class="thumb-stroke"
              />
            {:else}
              <rect x="4" y="16" width="8" height="6" rx="1.5" class="thumb-fill" />
              <rect x="14" y="11" width="11" height="11" rx="1.5" class="thumb-fill" />
              <rect x="27" y="6" width="16" height="16" rx="1.5" class="thumb-fill" />
              <rect x="45" y="13" width="7" height="9" rx="1.5" class="thumb-fill" />
              <path
                d="M 4 16 H 12 M 14 11 H 25 M 27 6 H 43 M 45 13 H 52"
                class="thumb-stroke"
              />
            {/if}
          </svg>
        </div>

        <p class="strategy-summary">{item.summary}</p>
        <div class="card-foot">
          <span class="tag">{item.bestFor}</span>
          {#if active}
            <span class="active-indicator">Active</span>
          {/if}
        </div>
      </div>
    {/each}
  </div>

  {#if strategy === 'piecewise_bucket'}
    <div class="bucket-bar card">
      <div class="bucket-row">
        <div class="bucket-copy">
          <span class="bucket-label">Score Zones</span>
          <span class="bucket-hint">
            Splits 1–10 into {bucketCount} zones and gives busier zones more room.
          </span>
        </div>
        <div class="bucket-control">
          <input
            type="range"
            min="2"
            max="12"
            step="1"
            value={bucketCount}
            aria-label="Score zones count"
            oninput={(e) => onBucketCountChange(Number((e.currentTarget as HTMLInputElement).value))}
          />
          <span class="bucket-pill num">{bucketCount} zones</span>
        </div>
      </div>
    </div>
  {/if}
</section>

<style>
  .strategy-section {
    display: grid;
    gap: 12px;
  }

  .strategy-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    align-items: start;
  }

  .strategy-card {
    position: relative;
    text-align: left;
    padding: 15px 16px 14px;
    display: grid;
    gap: 8px;
    align-content: start;
    transition: border-color 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease;
  }

  .strategy-card:hover {
    border-color: var(--border-strong);
    background: var(--surface-hover);
  }

  .strategy-card.active {
    border-color: var(--accent);
    background: #fffcf8;
    box-shadow:
      0 0 0 1px var(--accent),
      0 6px 20px rgba(200, 90, 23, 0.08);
  }

  .card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 10px;
  }

  .title-group {
    display: grid;
    gap: 3px;
  }

  .card-select-btn {
    border: none;
    background: transparent;
    padding: 0;
    text-align: left;
    color: inherit;
  }

  .card-select-btn::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    cursor: pointer;
    z-index: 1;
  }

  .card-select-btn:focus-visible {
    outline: none;
  }

  .card-select-btn:focus-visible::after {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }

  .strategy-title {
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--ink);
    letter-spacing: -0.01em;
  }

  .shape-thumb {
    flex-shrink: 0;
  }

  .thumb-axis {
    stroke: var(--border-strong);
    stroke-width: 1;
  }

  .thumb-fill {
    fill: #e7ddd0;
    transition: fill 0.15s ease;
  }

  .thumb-stroke {
    fill: none;
    stroke: #9c8f80;
    stroke-width: 1.6;
    stroke-linecap: round;
    transition: stroke 0.15s ease;
  }

  .strategy-card.active .thumb-fill {
    fill: rgba(200, 90, 23, 0.18);
  }

  .strategy-card.active .thumb-stroke {
    stroke: var(--accent);
  }

  .strategy-summary {
    margin: 0;
    font-size: 0.85rem;
    line-height: 1.42;
    color: var(--ink-muted);
  }

  .card-foot {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 2px;
    gap: 8px;
  }

  .tag {
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--ink-muted);
    background: var(--surface-subtle);
    padding: 2px 8px;
    border-radius: 999px;
  }

  .strategy-card.active .tag {
    background: var(--accent-soft);
    color: var(--accent);
  }

  .active-indicator {
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .bucket-bar {
    padding: 12px 16px;
    display: grid;
    gap: 10px;
    background: #fffcf8;
    border-color: #ebd6c4;
  }

  .bucket-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 14px;
  }

  .bucket-copy {
    display: grid;
    gap: 2px;
  }

  .bucket-label {
    font-size: 0.84rem;
    font-weight: 700;
    color: var(--ink);
  }

  .bucket-hint {
    font-size: 0.8rem;
    color: var(--ink-muted);
  }

  .bucket-control {
    display: flex;
    align-items: center;
    gap: 12px;
    min-width: 240px;
  }

  .bucket-control input[type='range'] {
    flex: 1;
  }

  .bucket-pill {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--accent);
    background: var(--accent-soft);
    border: 1px solid #f2cba8;
    padding: 3px 10px;
    border-radius: 999px;
    white-space: nowrap;
  }

  @media (max-width: 820px) {
    .strategy-grid {
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
    }
  }
</style>
