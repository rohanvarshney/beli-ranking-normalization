<script lang="ts">
  import { lerp } from '../lib/animation';
  import {
    computeBeeswarmOffsets,
    computeDensityCurve,
    computeDistributionSummary,
    computePiecewiseBuckets,
    FOOD_TIERS,
    getTierForScore,
    selectDisplayIndices,
    type DatasetId,
    type DatasetOption,
    type DensityPoint,
    type RankedRestaurantBase,
  } from '../lib/foodInsights';
  import type { Strategy } from '../lib/types';
  import InfoBanner from './InfoBanner.svelte';
  import InfoButton from './InfoButton.svelte';

  type Props = {
    ranked: RankedRestaurantBase[];
    beforeScores: number[];
    currentScores: number[];
    afterScores: number[];
    strategy: Strategy;
    bucketCount: number;
    progress: number;
    playing: boolean;
    speedMs: number;
    datasetId: DatasetId;
    datasetOptions: DatasetOption[];
    seed: number;
    hoveredId: string | null;
    selectedId: string | null;
    onPlayPause: () => void;
    onScrub: (t: number) => void;
    onSpeedChange: (ms: number) => void;
    onDatasetChange: (id: DatasetId) => void;
    onSeedChange: (seed: number) => void;
    onShuffleSeed: () => void;
    onHover: (id: string | null) => void;
    onSelect: (id: string | null) => void;
  };

  let {
    ranked,
    beforeScores,
    currentScores,
    afterScores,
    strategy,
    bucketCount,
    progress,
    playing,
    speedMs,
    datasetId,
    datasetOptions,
    seed,
    hoveredId,
    selectedId,
    onPlayPause,
    onScrub,
    onSpeedChange,
    onDatasetChange,
    onSeedChange,
    onShuffleSeed,
    onHover,
    onSelect,
  }: Props = $props();

  let showChartInfo = $state(false);

  const width = 1040;
  const height = 432;
  const padL = 102;
  const padR = 24;
  const plotW = width - padL - padR; // 914

  const topBaseY = 152;
  const flowTopY = 156;
  const flowBotY = 258;
  const botBaseY = 262;
  const ridgeH = 82;

  const scoreToX = (score: number): number => {
    const clamped = Math.max(1.0, Math.min(10.0, score));
    return padL + ((clamped - 1.0) / 9.0) * plotW;
  };

  const tierGradientStops = FOOD_TIERS.map((tier) => {
    const startPct = (((scoreToX(tier.min) - padL) / plotW) * 100).toFixed(2);
    const endPct = (((scoreToX(tier.max) - padL) / plotW) * 100).toFixed(2);
    const fillOpacity = tier.id === 'okay' ? 0.28 : tier.id === 'like' ? 0.24 : 0.22;
    return {
      id: tier.id,
      color: tier.color,
      startPct: `${startPct}%`,
      endPct: `${endPct}%`,
      fillOpacity,
    };
  });

  const tierBoundaries = FOOD_TIERS.slice(0, -1).map((tier) => tier.max);

  const clampCenter = (cx: number, halfWidth: number): number =>
    Math.max(padL + halfWidth, Math.min(padL + plotW - halfWidth, cx));

  const dinerOptions = $derived(datasetOptions.filter((o) => o.group === 'diners'));
  const aggregateOptions = $derived(datasetOptions.filter((o) => o.group === 'aggregate'));

  // Density curves & summaries computed across ALL N items
  const beforeCurve = $derived(computeDensityCurve(beforeScores, 90, 0.36));
  const afterCurve = $derived(computeDensityCurve(afterScores, 90, 0.36));
  const currentCurve = $derived(computeDensityCurve(currentScores, 90, 0.36));

  const sharedPeak = $derived.by(() => {
    let peak = 0.01;
    for (const pt of beforeCurve) if (pt.density > peak) peak = pt.density;
    for (const pt of afterCurve) if (pt.density > peak) peak = pt.density;
    for (const pt of currentCurve) if (pt.density > peak) peak = pt.density;
    return peak;
  });

  const beforeSummary = $derived(computeDistributionSummary(beforeScores));
  const currentSummary = $derived(computeDistributionSummary(currentScores));

  const buildRidgePaths = (
    curve: DensityPoint[],
    baseY: number,
    direction: -1 | 1,
    peak: number,
  ): { area: string; stroke: string } => {
    if (curve.length === 0) return { area: '', stroke: '' };
    const pts = curve.map((pt) => {
      const px = scoreToX(pt.score);
      const py = baseY + direction * ((pt.density / peak) * ridgeH);
      return `${px.toFixed(2)} ${py.toFixed(2)}`;
    });
    const stroke = `M ${pts.join(' L ')}`;
    const xStart = scoreToX(curve[0].score).toFixed(2);
    const xEnd = scoreToX(curve[curve.length - 1].score).toFixed(2);
    const area = `M ${xStart} ${baseY} L ${pts.join(' L ')} L ${xEnd} ${baseY} Z`;
    return { area, stroke };
  };

  const topRidge = $derived(buildRidgePaths(beforeCurve, topBaseY, -1, sharedPeak));
  const botRidge = $derived(buildRidgePaths(currentCurve, botBaseY, 1, sharedPeak));

  // Sample <= 120 dots evenly by rank for crisp non-cluttered ribbons and beeswarm packing
  const displayIndices = $derived(selectDisplayIndices(ranked, 120));
  const displayItems = $derived(displayIndices.map((pos) => ranked[pos]));

  const beforeOffsets = $derived(
    computeBeeswarmOffsets(
      displayItems.map((item) => scoreToX(item.beforeScore)),
      4.1,
      58,
    ),
  );

  const afterOffsets = $derived(
    computeBeeswarmOffsets(
      displayItems.map((item) => scoreToX(item.afterScores[strategy])),
      4.1,
      58,
    ),
  );

  const displayRankSet = $derived(new Set(displayItems.map((item) => item.id)));

  // Piecewise bucket funnel bands
  const bucketBands = $derived(
    strategy === 'piecewise_bucket' ? computePiecewiseBuckets(beforeScores, bucketCount) : [],
  );

  // Anchor landmarks (#1, median, #N)
  const anchorIds = $derived.by(() => {
    if (ranked.length === 0) return new Set<string>();
    const ids = new Set<string>();
    ids.add(ranked[0].id);
    ids.add(ranked[Math.floor(ranked.length / 2)].id);
    ids.add(ranked[ranked.length - 1].id);
    return ids;
  });

  // Active item spotlight (hovered takes precedence over selected)
  const activeId = $derived(hoveredId ?? selectedId);
  const activeItem = $derived(
    activeId ? (ranked.find((r) => r.id === activeId) ?? null) : null,
  );

  const activeOffset = $derived.by(() => {
    if (!activeItem) return { top: 0, bot: 0 };
    const idx = displayItems.findIndex((item) => item.id === activeItem.id);
    if (idx === -1) return { top: 0, bot: 0 };
    return {
      top: beforeOffsets[idx],
      bot: lerp(beforeOffsets[idx], afterOffsets[idx], progress),
    };
  });

  const activeCallout = $derived.by(() => {
    if (!activeItem) return null;
    const currScore = currentScores[activeItem.index] ?? activeItem.beforeScore;
    const delta = currScore - activeItem.beforeScore;
    const deltaStr = `${delta >= 0 ? '+' : ''}${delta.toFixed(2)}`;
    const text = `#${activeItem.rank} ${activeItem.displayName} · ${activeItem.beforeScore.toFixed(2)} → ${currScore.toFixed(2)} (${deltaStr})`;
    const boxW = Math.min(390, Math.max(210, text.length * 6.9 + 28));
    const xRaw = scoreToX(activeItem.beforeScore);
    const xCurr = scoreToX(currScore);
    const cx = clampCenter((xRaw + xCurr) / 2, boxW / 2 + 6);
    const tier = getTierForScore(currScore);
    return {
      item: activeItem,
      currScore,
      xRaw,
      xCurr,
      cx,
      boxW,
      text,
      color: tier.color,
    };
  });

  const topIqrGeom = $derived.by(() => {
    const x1 = scoreToX(beforeSummary.p25);
    const x2 = scoreToX(beforeSummary.p75);
    const span = beforeSummary.iqr;
    const label = `Middle 50%: ${beforeSummary.p25.toFixed(1)}–${beforeSummary.p75.toFixed(1)} (${span.toFixed(1)} ${Math.abs(span - 1) < 0.05 ? 'pt' : 'pts'})`;
    const pillW = Math.max(176, label.length * 6.4 + 20);
    const cx = clampCenter((x1 + x2) / 2, pillW / 2 + 4);
    return { x1, x2, label, pillW, cx };
  });

  const botIqrGeom = $derived.by(() => {
    const x1 = scoreToX(currentSummary.p25);
    const x2 = scoreToX(currentSummary.p75);
    const span = currentSummary.iqr;
    const label = `Middle 50%: ${currentSummary.p25.toFixed(1)}–${currentSummary.p75.toFixed(1)} (${span.toFixed(1)} ${Math.abs(span - 1) < 0.05 ? 'pt' : 'pts'})`;
    const pillW = Math.max(176, label.length * 6.4 + 20);
    const cx = clampCenter((x1 + x2) / 2, pillW / 2 + 4);
    return { x1, x2, label, pillW, cx };
  });

  const handleDotKey = (e: KeyboardEvent, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect(selectedId === id ? null : id);
    }
  };

  const formatSpeedActive = (targetMs: number) => Math.abs(speedMs - targetMs) < 100;
</script>

<section class="hero card" aria-label="Beli ranking normalization flow chart">
  <div class="toolbar">
    <div class="toolbar-group">
      <label class="inline-field">
        <span class="field-label">List</span>
        <select
          value={datasetId}
          aria-label="Select diner or rating style preset"
          onchange={(e) => onDatasetChange((e.currentTarget as HTMLSelectElement).value as DatasetId)}
        >
          <optgroup label="Sample Beli Diners & Rating Habits">
            {#each dinerOptions as opt (opt.id)}
              <option value={opt.id}>{opt.label}</option>
            {/each}
          </optgroup>
          <optgroup label="Everyone Combined">
            {#each aggregateOptions as opt (opt.id)}
              <option value={opt.id}>{opt.label}</option>
            {/each}
          </optgroup>
        </select>
      </label>

      <button type="button" class="btn-subtle" onclick={onShuffleSeed} title="Generate a new sample list">
        ↻ New Sample
      </button>

      <InfoButton
        open={showChartInfo}
        onToggle={() => (showChartInfo = !showChartInfo)}
        label="Chart statistics and sample seed"
        controlsId="chart-info-banner"
      />
    </div>

    <div class="toolbar-group">
      <div class="speed-pills" role="group" aria-label="Animation speed">
        <button
          type="button"
          class="speed-btn"
          class:active={formatSpeedActive(7200)}
          onclick={() => onSpeedChange(7200)}
        >
          0.5×
        </button>
        <button
          type="button"
          class="speed-btn"
          class:active={formatSpeedActive(4000)}
          onclick={() => onSpeedChange(4000)}
        >
          1×
        </button>
        <button
          type="button"
          class="speed-btn"
          class:active={formatSpeedActive(1800)}
          onclick={() => onSpeedChange(1800)}
        >
          2×
        </button>
      </div>

      <button type="button" class="btn-primary" onclick={onPlayPause}>
        {#if playing}
          ❚❚ Pause
        {:else if progress >= 0.995}
          ↻ Replay
        {:else}
          ▶ Animate
        {/if}
      </button>
    </div>
  </div>

  <div class="scrubber-strip">
    <button
      type="button"
      class="endpoint-btn"
      class:active={progress <= 0.01}
      onclick={() => onScrub(0)}
    >
      Original (0%)
    </button>

    <input
      type="range"
      min="0"
      max="1"
      step="0.005"
      value={progress}
      aria-label="Morph progress between original and adjusted scores"
      oninput={(e) => onScrub(Number((e.currentTarget as HTMLInputElement).value))}
    />

    <span class="progress-badge num">{Math.round(progress * 100)}%</span>

    <button
      type="button"
      class="endpoint-btn"
      class:active={progress >= 0.99}
      onclick={() => onScrub(1)}
    >
      Adjusted (100%)
    </button>
  </div>

  {#if showChartInfo}
    <InfoBanner
      id="chart-info-banner"
      title="Chart stats & sample seed"
      onClose={() => (showChartInfo = false)}
    >
      <ul class="info-list">
        <li>
          <code class="tech-term">KDE</code> Smooth curves: Kernel Density Estimate showing where scores cluster.
        </li>
        <li class="num">
          <code class="tech-term">IQR (p25–p75)</code> Middle 50%: Interquartile range ({beforeSummary.p25.toFixed(2)}–{beforeSummary.p75.toFixed(2)} before → {currentSummary.p25.toFixed(2)}–{currentSummary.p75.toFixed(2)} now).
        </li>
        <li class="num">
          <code class="tech-term">Median (p50)</code> mid pill: 50th percentile score ({beforeSummary.median.toFixed(2)} → {currentSummary.median.toFixed(2)}).
        </li>
        <li class="num">
          <code class="tech-term">Monotonicity</code> Flow lines: Non-crossing Bezier curves confirming rank order is preserved across all {ranked.length.toLocaleString()} spots.
        </li>
      </ul>

      <div class="seed-row">
        <span class="seed-hint">Sample lists are generated deterministically from a PRNG seed.</span>
        <label class="inline-field seed-field">
          <span class="field-label">Seed</span>
          <input
            type="number"
            min="1"
            step="1"
            value={seed}
            aria-label="Dataset seed"
            onchange={(e) => {
              const parsed = Number.parseInt((e.currentTarget as HTMLInputElement).value, 10);
              if (Number.isFinite(parsed) && parsed >= 1) onSeedChange(parsed);
            }}
          />
        </label>
      </div>
    </InfoBanner>
  {/if}

  <div class="mobile-scroll-hint">Swipe chart horizontally to explore details →</div>
  <div class="svg-wrap">
    <svg
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Mirrored food rating flow chart comparing raw scores on top to normalized scores on bottom"
    >
      <defs>
        <linearGradient
          id="tier-fill-grad"
          gradientUnits="userSpaceOnUse"
          x1={padL}
          y1="0"
          x2={padL + plotW}
          y2="0"
        >
          {#each tierGradientStops as stop (stop.id)}
            <stop offset={stop.startPct} stop-color={stop.color} stop-opacity={stop.fillOpacity} />
            <stop offset={stop.endPct} stop-color={stop.color} stop-opacity={stop.fillOpacity} />
          {/each}
        </linearGradient>

        <linearGradient
          id="tier-stroke-grad"
          gradientUnits="userSpaceOnUse"
          x1={padL}
          y1="0"
          x2={padL + plotW}
          y2="0"
        >
          {#each tierGradientStops as stop (stop.id)}
            <stop offset={stop.startPct} stop-color={stop.color} />
            <stop offset={stop.endPct} stop-color={stop.color} />
          {/each}
        </linearGradient>

        <filter id="pill-shadow" x="-10%" y="-20%" width="120%" height="160%">
          <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#1F1B16" flood-opacity="0.12" />
        </filter>
      </defs>

      <!-- Food tier header pills -->
      {#each FOOD_TIERS as tier (tier.id)}
        {@const xStart = scoreToX(tier.min)}
        {@const xEnd = scoreToX(tier.max)}
        {@const bandW = xEnd - xStart}
        {@const midX = (xStart + xEnd) / 2}
        {@const pillLabel =
          bandW < 175 ? `${tier.shortLabel} · ${tier.rangeLabel}` : `${tier.label} · ${tier.rangeLabel}`}
        {@const pillW = Math.min(bandW - 10, Math.max(138, pillLabel.length * 6.8 + 24))}

        <rect
          x={xStart}
          y="38"
          width={bandW}
          height="336"
          fill={tier.bandBg}
        />

        <g transform={`translate(${midX}, 20)`}>
          <rect
            x={-pillW / 2}
            y="-12"
            width={pillW}
            height="23"
            rx="11.5"
            fill={tier.softBg}
            stroke={tier.border}
            stroke-width="1"
          />
          <text
            x="0"
            y="3.5"
            text-anchor="middle"
            class="tier-pill-text"
            fill={tier.textColor}
          >
            {pillLabel}
          </text>
        </g>
      {/each}

      <!-- Integer grid hairlines and tier boundary dividers -->
      {#each [2, 3, 4, 5, 6, 7, 8, 9] as tick}
        <line
          x1={scoreToX(tick)}
          y1="38"
          x2={scoreToX(tick)}
          y2="374"
          stroke="rgba(142, 131, 119, 0.14)"
          stroke-width="1"
        />
      {/each}

      {#each tierBoundaries as boundary}
        <line
          x1={scoreToX(boundary)}
          y1="38"
          x2={scoreToX(boundary)}
          y2="374"
          stroke="#D6CBB9"
          stroke-width="1.2"
          stroke-dasharray="3 4"
        />
      {/each}

      <!-- Chart outer frame subtle top & bottom hairlines -->
      <line x1={padL} y1="38" x2={padL + plotW} y2="38" stroke="#EAE2D6" stroke-width="1" />
      <line x1={padL} y1={topBaseY} x2={padL + plotW} y2={topBaseY} stroke="#DFD5C7" stroke-width="1.2" />
      <line x1={padL} y1={botBaseY} x2={padL + plotW} y2={botBaseY} stroke="#DFD5C7" stroke-width="1.2" />

      <!-- Left margin lane annotations -->
      <g class="lane-labels">
        <text x="10" y="96" class="lane-eyebrow">BEFORE</text>
        <text x="10" y="112" class="lane-sub">Original</text>
        <rect x="10" y="121" width="66" height="20" rx="6" fill="#F4EFE6" stroke="#E5DDD0" />
        <text x="43" y="135" text-anchor="middle" class="lane-med num">
          mid {beforeSummary.median.toFixed(1)}
        </text>

        <rect x="10" y="189" width="70" height="36" rx="8" fill="#FBF8F3" stroke="#E8E0D4" />
        <text x="45" y="204" text-anchor="middle" class="order-title">RANKS</text>
        <text x="45" y="217" text-anchor="middle" class="order-sub">100% locked</text>

        <text x="10" y="290" class="lane-eyebrow active-eyebrow">
          {progress <= 0.01 ? 'BEFORE' : progress >= 0.995 ? 'AFTER' : 'MOVING'}
        </text>
        <text x="10" y="306" class="lane-sub num">{Math.round(progress * 100)}% applied</text>
        <rect x="10" y="315" width="66" height="20" rx="6" fill="#FDF0E4" stroke="#F2CBA8" />
        <text x="43" y="329" text-anchor="middle" class="lane-med num" fill="#A94910">
          mid {currentSummary.median.toFixed(1)}
        </text>
      </g>

      <!-- Piecewise bucket funnel corridors (behind ribbons when active) -->
      {#if strategy === 'piecewise_bucket'}
        {#each bucketBands as band, bi (band.bucketIndex)}
          {#if band.count > 0}
            {@const xTopL = scoreToX(band.rawMin)}
            {@const xTopR = scoreToX(band.rawMax)}
            {@const currOutMin = lerp(band.rawMin, band.outMin, progress)}
            {@const currOutMax = lerp(band.rawMax, band.outMax, progress)}
            {@const xBotL = scoreToX(currOutMin)}
            {@const xBotR = scoreToX(currOutMax)}
            {@const midY = (flowTopY + flowBotY) / 2}
            <path
              d={`M ${xTopL} ${flowTopY} L ${xTopR} ${flowTopY} C ${xTopR} ${midY}, ${xBotR} ${midY}, ${xBotR} ${flowBotY} L ${xBotL} ${flowBotY} C ${xBotL} ${midY}, ${xTopL} ${midY}, ${xTopL} ${flowTopY} Z`}
              fill={bi % 2 === 0 ? 'rgba(200, 90, 23, 0.09)' : 'rgba(120, 108, 94, 0.07)'}
              stroke="rgba(200, 90, 23, 0.22)"
              stroke-width="1"
            />
            {#if xTopR - xTopL > 34}
              <text
                x={(xTopL + xTopR) / 2}
                y={flowTopY + 14}
                text-anchor="middle"
                class="bucket-tag num"
              >
                G{band.bucketIndex + 1} ({band.count})
              </text>
            {/if}
          {/if}
        {/each}
      {/if}

      <!-- Top & Bottom mirrored KDE distributions -->
      <path d={topRidge.area} fill="url(#tier-fill-grad)" />
      <path d={topRidge.stroke} fill="none" stroke="url(#tier-stroke-grad)" stroke-width="2" />

      <path d={botRidge.area} fill="url(#tier-fill-grad)" />
      <path d={botRidge.stroke} fill="none" stroke="url(#tier-stroke-grad)" stroke-width="2" />

      <!-- Top Middle 50% (IQR) bracket & pill -->
      {#if beforeSummary.count > 1}
        <g class="iqr-callout">
          <line x1={topIqrGeom.x1} y1="58" x2={topIqrGeom.x2} y2="58" stroke="#685F55" stroke-width="1.4" />
          <line x1={topIqrGeom.x1} y1="58" x2={topIqrGeom.x1} y2="63" stroke="#685F55" stroke-width="1.4" />
          <line x1={topIqrGeom.x2} y1="58" x2={topIqrGeom.x2} y2="63" stroke="#685F55" stroke-width="1.4" />
          <rect
            x={topIqrGeom.cx - topIqrGeom.pillW / 2}
            y="41"
            width={topIqrGeom.pillW}
            height="16"
            rx="8"
            fill="#FFFFFF"
            stroke="#DED5C8"
          />
          <text x={topIqrGeom.cx} y="52.5" text-anchor="middle" class="iqr-text num">
            {topIqrGeom.label}
          </text>
        </g>
      {/if}

      <!-- Bottom Middle 50% (IQR) bracket & pill -->
      {#if currentSummary.count > 1}
        <g class="iqr-callout">
          <line x1={botIqrGeom.x1} y1="351" x2={botIqrGeom.x2} y2="351" stroke="#685F55" stroke-width="1.4" />
          <line x1={botIqrGeom.x1} y1="346" x2={botIqrGeom.x1} y2="351" stroke="#685F55" stroke-width="1.4" />
          <line x1={botIqrGeom.x2} y1="346" x2={botIqrGeom.x2} y2="351" stroke="#685F55" stroke-width="1.4" />
          <rect
            x={botIqrGeom.cx - botIqrGeom.pillW / 2}
            y="354"
            width={botIqrGeom.pillW}
            height="16"
            rx="8"
            fill="#FFFFFF"
            stroke="#DED5C8"
          />
          <text x={botIqrGeom.cx} y="365.5" text-anchor="middle" class="iqr-text num">
            {botIqrGeom.label}
          </text>
        </g>
      {/if}

      <!-- Non-crossing order-preserving Bezier flow ribbons -->
      {#each displayItems as item (item.id)}
        {@const currScore = currentScores[item.index] ?? item.beforeScore}
        {@const xRaw = scoreToX(item.beforeScore)}
        {@const xCurr = scoreToX(currScore)}
        {@const tier = getTierForScore(currScore)}
        {@const isAnchor = !activeId && anchorIds.has(item.id)}
        <path
          d={`M ${xRaw} ${flowTopY} C ${xRaw} 207, ${xCurr} 207, ${xCurr} ${flowBotY}`}
          fill="none"
          stroke={tier.color}
          stroke-width={isAnchor ? 1.85 : 1.2}
          stroke-opacity={activeId ? 0.14 : isAnchor ? 0.62 : 0.28}
        />
      {/each}

      <!-- Top & Bottom interactive beeswarm dots -->
      {#each displayItems as item, k (item.id)}
        {@const currScore = currentScores[item.index] ?? item.beforeScore}
        {@const xRaw = scoreToX(item.beforeScore)}
        {@const yRaw = topBaseY - beforeOffsets[k]}
        {@const xCurr = scoreToX(currScore)}
        {@const yCurr = botBaseY + lerp(beforeOffsets[k], afterOffsets[k], progress)}
        {@const rawTier = getTierForScore(item.beforeScore)}
        {@const currTier = getTierForScore(currScore)}
        {@const isDimmed = activeId !== null && activeId !== item.id}

        <circle
          cx={xRaw}
          cy={yRaw}
          r="3.9"
          fill={rawTier.color}
          fill-opacity={isDimmed ? 0.28 : 0.85}
          stroke="#FFFFFF"
          stroke-width="0.9"
          class="dot-interactive"
          role="button"
          tabindex="0"
          aria-label={`#${item.rank} ${item.displayName}, raw score ${item.beforeScore.toFixed(2)}`}
          onmouseenter={() => onHover(item.id)}
          onmouseleave={() => onHover(null)}
          onclick={() => onSelect(selectedId === item.id ? null : item.id)}
          onkeydown={(e) => handleDotKey(e, item.id)}
        >
          <title>#{item.rank} {item.displayName}: {item.beforeScore.toFixed(2)} → {currScore.toFixed(2)}</title>
        </circle>

        <circle
          cx={xCurr}
          cy={yCurr}
          r="4.1"
          fill={currTier.color}
          fill-opacity={isDimmed ? 0.28 : 0.9}
          stroke="#FFFFFF"
          stroke-width="0.95"
          class="dot-interactive"
          role="button"
          tabindex="0"
          aria-label={`#${item.rank} ${item.displayName}, current score ${currScore.toFixed(2)}`}
          onmouseenter={() => onHover(item.id)}
          onmouseleave={() => onHover(null)}
          onclick={() => onSelect(selectedId === item.id ? null : item.id)}
          onkeydown={(e) => handleDotKey(e, item.id)}
        >
          <title>#{item.rank} {item.displayName}: {item.beforeScore.toFixed(2)} → {currScore.toFixed(2)}</title>
        </circle>
      {/each}

      <!-- Subtle anchor landmark labels when idle -->
      {#if !activeId && ranked.length >= 3}
        {@const topSpot = ranked[0]}
        {@const midSpot = ranked[Math.floor(ranked.length / 2)]}
        {@const botSpot = ranked[ranked.length - 1]}
        {#each [
          { tag: '#1 Best', item: topSpot },
          { tag: `#${midSpot.rank} Middle`, item: midSpot },
          { tag: `#${botSpot.rank}`, item: botSpot },
        ] as anchor (anchor.item.id)}
          {@const curr = currentScores[anchor.item.index] ?? anchor.item.beforeScore}
          {@const lx = clampCenter(scoreToX(curr), 36)}
          <text x={lx} y={flowBotY - 6} text-anchor="middle" class="anchor-label num">
            {anchor.tag}
          </text>
        {/each}
      {/if}

      <!-- Active Hovered / Selected Highlight Overlay -->
      {#if activeCallout}
        {@const yTopDot = displayRankSet.has(activeCallout.item.id) ? topBaseY - activeOffset.top : topBaseY}
        {@const yBotDot = displayRankSet.has(activeCallout.item.id) ? botBaseY + activeOffset.bot : botBaseY}

        <!-- White halo under highlighted Bezier curve -->
        <path
          d={`M ${activeCallout.xRaw} ${flowTopY} C ${activeCallout.xRaw} 207, ${activeCallout.xCurr} 207, ${activeCallout.xCurr} ${flowBotY}`}
          fill="none"
          stroke="#FFFFFF"
          stroke-width="6"
          stroke-opacity="0.92"
        />
        <path
          d={`M ${activeCallout.xRaw} ${flowTopY} C ${activeCallout.xRaw} 207, ${activeCallout.xCurr} 207, ${activeCallout.xCurr} ${flowBotY}`}
          fill="none"
          stroke={activeCallout.color}
          stroke-width="2.8"
        />

        <!-- Enlarged endpoint rings -->
        <circle
          cx={activeCallout.xRaw}
          cy={yTopDot}
          r="6.5"
          fill={getTierForScore(activeCallout.item.beforeScore).color}
          stroke="#FFFFFF"
          stroke-width="2.2"
          pointer-events="none"
        />
        <circle
          cx={activeCallout.xCurr}
          cy={yBotDot}
          r="6.8"
          fill={activeCallout.color}
          stroke="#FFFFFF"
          stroke-width="2.2"
          pointer-events="none"
        />

        <!-- Floating callout pill in flow channel -->
        <g transform={`translate(${activeCallout.cx}, 207)`} filter="url(#pill-shadow)" pointer-events="none">
          <rect
            x={-activeCallout.boxW / 2}
            y="-15"
            width={activeCallout.boxW}
            height="30"
            rx="15"
            fill="#FFFFFF"
            stroke={activeCallout.color}
            stroke-width="1.6"
          />
          <text x="0" y="4.5" text-anchor="middle" class="callout-text num">
            {activeCallout.text}
          </text>
        </g>
      {/if}

      <!-- Bottom Food Rating Ruler (1.0 to 10.0) -->
      <g class="ruler">
        <line x1={scoreToX(1)} y1="382" x2={scoreToX(10)} y2="382" stroke="#CFC4B4" stroke-width="1.4" />
        {#each [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] as tick}
          <line
            x1={scoreToX(tick)}
            y1="382"
            x2={scoreToX(tick)}
            y2="388"
            stroke="#AFA393"
            stroke-width="1.2"
          />
          <text x={scoreToX(tick)} y="403" text-anchor="middle" class="ruler-tick num">
            {tick}
          </text>
        {/each}
        <text x={padL + plotW / 2} y="423" text-anchor="middle" class="ruler-caption">
          Food Rating Scale (1.0 – 10.0)
        </text>
        {#if ranked.length > 120}
          <text x={padL + plotW} y="423" text-anchor="end" class="sample-note num">
            Stats use all {ranked.length.toLocaleString()} spots · showing 120 sample dots
          </text>
        {/if}
      </g>
    </svg>
  </div>
</section>

<style>
  .hero {
    padding: 16px 18px 14px;
    display: grid;
    gap: 12px;
  }

  .toolbar {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .toolbar-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
  }

  .inline-field {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 4px 10px;
  }

  .field-label {
    font-size: 0.76rem;
    font-weight: 700;
    color: var(--ink-muted);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .inline-field select,
  .inline-field input {
    border: none;
    background: transparent;
    font-size: 0.86rem;
    font-weight: 600;
    color: var(--ink);
    padding: 2px 0;
  }

  .seed-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding-top: 6px;
    border-top: 1px dashed #e2ccb5;
  }

  .seed-hint {
    color: var(--ink-muted);
  }

  .seed-field input {
    width: 64px;
  }

  .btn-subtle {
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--ink);
    border-radius: 10px;
    padding: 7px 12px;
    font-size: 0.84rem;
    font-weight: 600;
    transition: background-color 0.12s ease, border-color 0.12s ease;
  }

  .btn-subtle:hover {
    background: var(--surface-subtle);
    border-color: var(--border-strong);
  }

  .speed-pills {
    display: inline-flex;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 2px;
  }

  .speed-btn {
    border: none;
    background: transparent;
    color: var(--ink-muted);
    border-radius: 7px;
    padding: 4px 9px;
    font-size: 0.8rem;
    font-weight: 600;
  }

  .speed-btn.active {
    background: var(--surface);
    color: var(--ink);
    box-shadow: 0 1px 2px rgba(31, 27, 22, 0.08);
  }

  .btn-primary {
    border: 1px solid var(--accent);
    background: var(--accent);
    color: #ffffff;
    border-radius: 10px;
    padding: 7px 15px;
    font-size: 0.86rem;
    font-weight: 700;
    transition: background-color 0.12s ease;
  }

  .btn-primary:hover {
    background: var(--accent-hover);
  }

  .scrubber-strip {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 6px 10px;
  }

  .scrubber-strip input[type='range'] {
    flex: 1;
    min-width: 100px;
  }

  .endpoint-btn {
    border: 1px solid transparent;
    background: transparent;
    color: var(--ink-muted);
    border-radius: 8px;
    padding: 4px 10px;
    font-size: 0.78rem;
    font-weight: 600;
    white-space: nowrap;
  }

  .endpoint-btn:hover {
    background: rgba(255, 255, 255, 0.7);
    color: var(--ink);
  }

  .endpoint-btn.active {
    background: var(--surface);
    border-color: var(--border-strong);
    color: var(--ink);
    box-shadow: 0 1px 2px rgba(31, 27, 22, 0.06);
  }

  .progress-badge {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--accent);
    min-width: 40px;
    text-align: center;
  }

  .mobile-scroll-hint {
    display: none;
    font-size: 0.74rem;
    font-weight: 600;
    color: var(--ink-soft);
    text-align: right;
  }

  .svg-wrap {
    width: 100%;
    overflow: hidden;
  }

  svg {
    display: block;
    width: 100%;
    height: auto;
  }

  .tier-pill-text {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.01em;
  }

  .lane-eyebrow {
    font-size: 10px;
    font-weight: 800;
    fill: #544b42;
    letter-spacing: 0.05em;
  }

  .active-eyebrow {
    fill: #b84c0e;
  }

  .lane-sub {
    font-size: 10.5px;
    fill: #7d7266;
    font-weight: 500;
  }

  .lane-med {
    font-size: 10px;
    font-weight: 700;
    fill: #4f463d;
  }

  .order-title {
    font-size: 9.5px;
    font-weight: 800;
    fill: #6c6256;
    letter-spacing: 0.07em;
  }

  .order-sub {
    font-size: 9.5px;
    font-weight: 600;
    fill: #8c8174;
  }

  .iqr-text {
    font-size: 10px;
    font-weight: 700;
    fill: #4a423a;
  }

  .bucket-tag {
    font-size: 9.5px;
    font-weight: 700;
    fill: #9b4715;
  }

  .anchor-label {
    font-size: 9.5px;
    font-weight: 700;
    fill: #6e6357;
  }

  .callout-text {
    font-size: 11.5px;
    font-weight: 700;
    fill: #1f1b16;
  }

  .ruler-tick {
    font-size: 11px;
    font-weight: 600;
    fill: #685f55;
  }

  .ruler-caption {
    font-size: 11px;
    font-weight: 600;
    fill: #857a6d;
  }

  .sample-note {
    font-size: 10px;
    fill: #9a8f82;
  }

  .dot-interactive {
    cursor: pointer;
    transition: fill-opacity 0.12s ease;
  }

  @media (max-width: 680px) {
    .hero {
      padding: 12px;
    }
    .scrubber-strip {
      flex-wrap: wrap;
    }
    .scrubber-strip input[type='range'] {
      order: -1;
      width: 100%;
      flex: 1 0 100%;
    }
    .mobile-scroll-hint {
      display: block;
    }
    .svg-wrap {
      overflow-x: auto;
      -webkit-overflow-scrolling: touch;
      padding-bottom: 4px;
    }
    svg {
      min-width: 720px;
    }
  }
</style>
