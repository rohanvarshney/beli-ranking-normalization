<script lang="ts">
  import signatureImg from '../assets/freehand-signature-3.png';

  export type PitchChapterId = 'problem' | 'proposal' | 'demo' | 'impact' | 'ship';

  type Props = {
    activeSection: PitchChapterId;
  };

  let { activeSection }: Props = $props();

  const CHAPTERS: { id: PitchChapterId; label: string; href: string }[] = [
    { id: 'problem', label: 'Problem', href: '#problem' },
    { id: 'proposal', label: 'Proposal', href: '#proposal' },
    { id: 'demo', label: 'Live Demo', href: '#demo' },
    { id: 'impact', label: 'Impact', href: '#impact' },
    { id: 'ship', label: 'Ship It', href: '#ship' },
  ];
</script>

<nav class="pitch-nav" aria-label="Pitch deck chapters">
  <div class="nav-inner">
    <a
      class="brand-home-link"
      href="https://rohanvarshney.github.io"
      title="Rohan Varshney's Personal Website"
      aria-label="Back to rohanvarshney.github.io"
    >
      <img src={signatureImg} alt="Rohan Varshney" class="brand-signature" />
    </a>

    <div class="chapter-pills">
      {#each CHAPTERS as ch (ch.id)}
        <a
          class="chapter-pill"
          class:active={activeSection === ch.id}
          href={ch.href}
          aria-current={activeSection === ch.id ? 'location' : undefined}
        >
          {ch.label}
        </a>
      {/each}
    </div>

    <a
      class="github-link"
      href="https://github.com/rohanvarshney/beli-ranking-normalization"
      target="_blank"
      rel="noopener noreferrer"
    >
      GitHub ↗
    </a>
  </div>
</nav>

<style>
  .pitch-nav {
    position: sticky;
    top: 0;
    z-index: 30;
    margin: 0 -20px;
    padding: 10px 20px;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    background: rgba(250, 248, 244, 0.9);
    border-bottom: 1px solid var(--border);
  }

  .nav-inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .brand-home-link {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    border-radius: 8px;
    transition: opacity 0.15s ease;
    flex-shrink: 0;
  }

  .brand-home-link:hover {
    opacity: 0.72;
  }

  .brand-signature {
    display: block;
    height: 32px;
    width: auto;
    object-fit: contain;
    mix-blend-mode: multiply;
  }

  .chapter-pills {
    display: flex;
    align-items: center;
    gap: 4px;
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 3px;
    overflow-x: auto;
    scrollbar-width: none;
  }

  .chapter-pills::-webkit-scrollbar {
    display: none;
  }

  .chapter-pill {
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--ink-muted);
    padding: 5px 12px;
    border-radius: 999px;
    white-space: nowrap;
    transition: background-color 0.15s ease, color 0.15s ease;
  }

  .chapter-pill:hover {
    color: var(--ink);
    background: rgba(255, 255, 255, 0.7);
  }

  .chapter-pill.active {
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 700;
  }

  .github-link {
    text-decoration: none;
    font-size: 0.82rem;
    font-weight: 600;
    color: var(--ink);
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 6px 13px;
    box-shadow: 0 1px 2px rgba(31, 27, 22, 0.04);
    transition: background-color 0.12s ease, border-color 0.12s ease;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .github-link:hover {
    background: var(--surface-subtle);
    border-color: var(--border-strong);
  }

  @media (max-width: 760px) {
    .pitch-nav {
      margin: 0 -12px;
      padding: 8px 12px;
    }

    .nav-inner {
      flex-wrap: wrap;
      row-gap: 8px;
    }

    .chapter-pills {
      order: 3;
      width: 100%;
      justify-content: space-between;
    }

    .chapter-pill {
      padding: 4px 9px;
      font-size: 0.76rem;
    }
  }
</style>
