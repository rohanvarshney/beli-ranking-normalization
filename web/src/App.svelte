<script lang="ts">
  import FoodFlowChart from './components/FoodFlowChart.svelte';
  import ImpactSummary from './components/ImpactSummary.svelte';
  import RankedFoodList from './components/RankedFoodList.svelte';
  import StrategySelector from './components/StrategySelector.svelte';
  import { createProgressStepper } from './lib/animation';
  import {
    buildDatasetOptions,
    buildRankedItems,
    getDatasetItems,
    getDefaultDatasetId,
    type DatasetId,
  } from './lib/foodInsights';
  import { generateMockUsers } from './lib/mockData';
  import { interpolateScores, normalizeScores } from './lib/normalize';
  import type { Strategy } from './lib/types';

  let seed = $state(1337);
  const users = $derived(generateMockUsers(seed));
  const datasetOptions = $derived(buildDatasetOptions(users));

  let datasetId = $state<DatasetId>(getDefaultDatasetId(generateMockUsers(1337)));
  let strategy = $state<Strategy>('quantile_map');
  let bucketCount = $state(4);
  let speedMs = $state(2000);
  let progress = $state(1);
  let playing = $state(false);
  let hoveredId = $state<string | null>(null);
  let selectedId = $state<string | null>(null);

  const items = $derived(getDatasetItems(users, datasetId, seed));
  const beforeScores = $derived(items.map((x) => x.score));

  const afterByStrategy = $derived({
    quantile_map: normalizeScores(beforeScores, 'quantile_map'),
    zscore_sigmoid: normalizeScores(beforeScores, 'zscore_sigmoid'),
    piecewise_bucket: normalizeScores(beforeScores, 'piecewise_bucket', { bucketCount }),
  });

  const afterScores = $derived(afterByStrategy[strategy]);
  const currentScores = $derived(interpolateScores(beforeScores, afterScores, progress));
  const ranked = $derived(buildRankedItems(items, beforeScores, afterByStrategy));

  let stepper: ReturnType<typeof createProgressStepper> | null = null;

  $effect(() => {
    return () => {
      stepper?.stop();
    };
  });

  const stopPlayback = () => {
    stepper?.stop();
    stepper = null;
    playing = false;
  };

  const startPlaybackFrom = (startT: number, duration: number) => {
    stepper?.stop();
    playing = true;
    stepper = createProgressStepper(
      duration,
      (t) => {
        progress = t;
      },
      () => {
        playing = false;
        stepper = null;
      },
    );
    stepper.play(startT);
  };

  const handlePlayPause = () => {
    if (playing) {
      stopPlayback();
      return;
    }
    const startT = progress >= 0.995 ? 0 : progress;
    if (startT === 0) progress = 0;
    startPlaybackFrom(startT, speedMs);
  };

  const handleScrub = (nextT: number) => {
    stopPlayback();
    progress = Math.max(0, Math.min(1, nextT));
  };

  const handleSpeedChange = (nextMs: number) => {
    speedMs = nextMs;
    if (playing) {
      startPlaybackFrom(progress, nextMs);
    }
  };

  const handleSelectStrategy = (next: Strategy) => {
    strategy = next;
    if (!playing && progress === 0) {
      progress = 1;
    }
  };

  const handleBucketCountChange = (nextCount: number) => {
    bucketCount = nextCount;
    if (!playing && progress === 0) {
      progress = 1;
    }
  };

  const handleDatasetChange = (nextId: DatasetId) => {
    stopPlayback();
    hoveredId = null;
    selectedId = null;
    datasetId = nextId;
    progress = 1;
  };

  const applyNewSeed = (nextSeed: number) => {
    stopPlayback();
    hoveredId = null;
    selectedId = null;
    seed = nextSeed;
    const nextUsers = generateMockUsers(nextSeed);
    if (datasetId.startsWith('diner:')) {
      const idx = Number.parseInt(datasetId.slice('diner:'.length), 10);
      if (!Number.isFinite(idx) || idx < 0 || idx >= nextUsers.length) {
        datasetId = getDefaultDatasetId(nextUsers);
      }
    }
    progress = 1;
  };

  const handleShuffleSeed = () => {
    const nextSeed = ((seed * 1664525 + 1013904223) >>> 0) % 9000 + 1000;
    applyNewSeed(nextSeed === seed ? nextSeed + 1 : nextSeed);
  };
</script>

<main>
  <header class="page-header">
    <div class="header-copy">
      <span class="eyebrow">Ranking Normalization SDK · Visual Explorer</span>
      <h1>How Score Normalization Reshapes a Food List</h1>
      <p class="lead">
        Most diners pack nearly every restaurant between 7.0 and 9.0. Pick a heuristic below to watch crowded
        ratings stretch cleanly across the 1–10 food scale while keeping every rank in exact order.
      </p>
    </div>

    <a
      class="github-link"
      href="https://github.com/rohanvarshney/barn_heuristic"
      target="_blank"
      rel="noopener noreferrer"
    >
      GitHub ↗
    </a>
  </header>

  <StrategySelector
    {strategy}
    {bucketCount}
    onSelectStrategy={handleSelectStrategy}
    onBucketCountChange={handleBucketCountChange}
  />

  <FoodFlowChart
    {ranked}
    {beforeScores}
    {currentScores}
    {afterScores}
    {strategy}
    {bucketCount}
    {progress}
    {playing}
    {speedMs}
    {datasetId}
    {datasetOptions}
    {seed}
    {hoveredId}
    {selectedId}
    onPlayPause={handlePlayPause}
    onScrub={handleScrub}
    onSpeedChange={handleSpeedChange}
    onDatasetChange={handleDatasetChange}
    onSeedChange={applyNewSeed}
    onShuffleSeed={handleShuffleSeed}
    onHover={(id) => (hoveredId = id)}
    onSelect={(id) => (selectedId = id)}
  />

  <div class="details-grid">
    <RankedFoodList
      {ranked}
      {currentScores}
      {strategy}
      {hoveredId}
      {selectedId}
      onHover={(id) => (hoveredId = id)}
      onSelect={(id) => (selectedId = id)}
    />

    <ImpactSummary
      {ranked}
      {beforeScores}
      {currentScores}
      {strategy}
      {progress}
      {hoveredId}
      {selectedId}
      onSelectStrategy={handleSelectStrategy}
    />
  </div>
</main>

<style>
  .page-header {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    padding: 4px 2px 2px;
  }

  .header-copy {
    max-width: 880px;
    display: grid;
    gap: 6px;
  }

  .eyebrow {
    font-size: 0.74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent);
  }

  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.5rem, 2.75vw, 2.15rem);
    line-height: 1.16;
    letter-spacing: -0.02em;
    color: var(--ink);
  }

  .lead {
    margin: 0;
    font-size: 0.96rem;
    line-height: 1.5;
    color: var(--ink-muted);
  }

  .github-link {
    text-decoration: none;
    font-size: 0.84rem;
    font-weight: 600;
    color: var(--ink);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 7px 14px;
    box-shadow: 0 1px 2px rgba(31, 27, 22, 0.04);
    transition: background-color 0.12s ease, border-color 0.12s ease;
    white-space: nowrap;
  }

  .github-link:hover {
    background: var(--surface-subtle);
    border-color: var(--border-strong);
  }
</style>
