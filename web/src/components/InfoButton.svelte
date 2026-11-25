<script lang="ts">
  type Props = {
    open: boolean;
    onToggle: () => void;
    label: string;
    controlsId?: string;
    compact?: boolean;
  };

  let { open, onToggle, label, controlsId, compact = false }: Props = $props();
</script>

<button
  type="button"
  class="info-btn"
  class:open
  class:compact
  aria-expanded={open}
  aria-controls={controlsId}
  aria-label={label}
  title={open ? 'Hide stats details' : label}
  onclick={onToggle}
>
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
    <circle cx="7" cy="4" r="0.95" fill="currentColor" />
    <path d="M7 6.5V10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
  </svg>
</button>

<style>
  .info-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    padding: 0;
    border-radius: 999px;
    border: 1px solid var(--border-strong);
    background: var(--surface-subtle);
    color: var(--ink-muted);
    flex-shrink: 0;
    transition: background-color 0.12s ease, border-color 0.12s ease, color 0.12s ease;
  }

  .info-btn.compact {
    width: 20px;
    height: 20px;
  }

  .info-btn:hover {
    background: var(--accent-soft);
    border-color: var(--accent);
    color: var(--accent);
  }

  .info-btn.open {
    background: var(--accent);
    border-color: var(--accent);
    color: #ffffff;
  }

  .info-btn.open:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
    color: #ffffff;
  }
</style>
