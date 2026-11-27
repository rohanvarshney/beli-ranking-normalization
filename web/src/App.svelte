<script lang="ts">
  import FoodFlowChart from './components/FoodFlowChart.svelte';
  import ImpactPitchSection from './components/ImpactPitchSection.svelte';
  import ImpactSummary from './components/ImpactSummary.svelte';
  import PitchHero from './components/PitchHero.svelte';
  import PitchNav, { type PitchChapterId } from './components/PitchNav.svelte';
  import ProblemSection from './components/ProblemSection.svelte';
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

  const initialUsers = generateMockUsers(1337);
  const initialDatasetId: DatasetId =
    initialUsers.length > 6 ? 'diner:6' : getDefaultDatasetId(initialUsers);

  let seed = $state(1337);
  const users = $derived(generateMockUsers(seed));
  const datasetOptions = $derived(buildDatasetOptions(users));

  let datasetId = $state<DatasetId>(initialDatasetId);
  let strategy = $state<Strategy>('quantile_map');
  let bucketCount = $state(4);
  let speedMs = $state(4000);
  let progress = $state(1);
  let playing = $state(false);
  let hoveredId = $state<string | null>(null);
  let selectedId = $state<string | null>(null);
  let activeSection = $state<PitchChapterId>('problem');

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

  $effect(() => {
    const ids: PitchChapterId[] = ['problem', 'proposal', 'demo', 'impact', 'ship'];
    const elements = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (elements.length === 0 || typeof IntersectionObserver === 'undefined') return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const id = entry.target.id as PitchChapterId;
            if (ids.includes(id)) {
              activeSection = id;
            }
          }
        }
      },
      { rootMargin: '-25% 0px -60% 0px', threshold: 0.01 },
    );

    for (const el of elements) observer.observe(el);
    return () => observer.disconnect();
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

  const handleTryInDemo = (nextId: DatasetId) => {
    stopPlayback();
    hoveredId = null;
    selectedId = null;
    datasetId = nextId;
    progress = 0;
    startPlaybackFrom(0, speedMs);
    document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' });
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

<PitchNav {activeSection} />

<main>
  <PitchHero />

  <ProblemSection {users} {seed} onTryInDemo={handleTryInDemo} />

  <section id="proposal" class="pitch-section">
    <div class="section-head">
      <span class="section-eyebrow">02 · The Proposal</span>
      <h2 class="section-title">Stretch the scores, never the ranks</h2>
      <p class="section-lead">
        Keep Beli's head-to-head ranking UX 100% unchanged. Add a lightweight calibration step that
        spreads a user's scores across the full 1–10 scale, and pick the curve style that best fits
        Beli's product voice.
      </p>
    </div>

    <div class="steps-strip" aria-label="How score calibration works in three steps">
      <div class="step-card card">
        <span class="step-num num">1</span>
        <div>
          <strong>Rank as usual</strong>
          <p>Diners still tap <em>I liked it!</em>, <em>It was fine</em>, or <em>I didn't like it</em> and compare spots head-to-head.</p>
        </div>
      </div>

      <div class="step-card card">
        <span class="step-num num">2</span>
        <div>
          <strong>Calibrate the spread</strong>
          <p>A deterministic layer stretches crowded clusters across 1–10 while locking every single rank in place.</p>
        </div>
      </div>

      <div class="step-card card">
        <span class="step-num num">3</span>
        <div>
          <strong>Unlock clearer scores</strong>
          <p>Personal lists, Friend Scores, and Rec Scores all speak the same 1–10 language.</p>
        </div>
      </div>
    </div>

    <StrategySelector
      {strategy}
      {bucketCount}
      onSelectStrategy={handleSelectStrategy}
      onBucketCountChange={handleBucketCountChange}
    />
  </section>

  <section id="demo" class="pitch-section">
    <div class="section-head">
      <span class="section-eyebrow">03 · Live Demo</span>
      <h2 class="section-title">Watch a crowded Beli list open up</h2>
      <p class="section-lead">
        Pick a diner preset below, hit <strong>Animate</strong> (or drag the slider), and click any
        restaurant dot or row to follow how its score moves without changing its rank.
      </p>
    </div>

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
  </section>

  <ImpactPitchSection />
</main>

<style>
  .steps-strip {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
  }

  .step-card {
    padding: 15px 16px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    background: var(--surface);
  }

  .step-num {
    width: 26px;
    height: 26px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.82rem;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }

  .step-card strong {
    display: block;
    font-size: 0.92rem;
    color: var(--ink);
    margin-bottom: 3px;
  }

  .step-card p {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--ink-muted);
  }

  @media (max-width: 820px) {
    .steps-strip {
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
    }
  }
</style>
