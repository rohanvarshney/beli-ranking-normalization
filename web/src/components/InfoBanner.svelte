<script lang="ts">
  import type { Snippet } from 'svelte';
  import { slide } from 'svelte/transition';

  type Props = {
    id?: string;
    title?: string;
    onClose?: () => void;
    children: Snippet;
  };

  let { id, title = 'Under the hood', onClose, children }: Props = $props();
</script>

<div {id} class="info-banner" role="region" aria-label={title} transition:slide={{ duration: 160 }}>
  <div class="info-head">
    <span class="info-title-wrap">
      <span class="info-micro-badge" aria-hidden="true">i</span>
      <span class="info-title">{title}</span>
    </span>
    {#if onClose}
      <button type="button" class="info-close" aria-label="Close info banner" onclick={onClose}>
        ×
      </button>
    {/if}
  </div>
  <div class="info-body">
    {@render children()}
  </div>
</div>

<style>
  .info-banner {
    background: #faf5ee;
    border: 1px solid #ead8c5;
    border-left: 3px solid var(--accent);
    border-radius: 10px;
    padding: 9px 11px;
    display: grid;
    gap: 6px;
  }

  .info-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
  }

  .info-title-wrap {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .info-micro-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
    border-radius: 999px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: 0.65rem;
    font-weight: 800;
    line-height: 1;
  }

  .info-title {
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent);
  }

  .info-close {
    border: none;
    background: transparent;
    color: var(--ink-soft);
    font-size: 0.95rem;
    line-height: 1;
    padding: 0 3px;
    border-radius: 4px;
  }

  .info-close:hover {
    color: var(--ink);
    background: rgba(31, 27, 22, 0.06);
  }

  .info-body {
    font-size: 0.78rem;
    line-height: 1.48;
    color: var(--ink-muted);
    display: grid;
    gap: 6px;
  }

  .info-body :global(p) {
    margin: 0;
  }
</style>
