<section id="pitch" class="hero-cover card">
  <div class="hero-content">
    <span class="section-eyebrow">Product Proposal for Beli</span>
    <h1>Make Every Point on Beli Mean Something Again</h1>
    <p class="hero-lead">
      Beli replaced the industry's anonymous 5-star reviews with head-to-head rankings on your
      <strong>Been</strong> list. But as lists grow, most diners rate restaurants around the same
      score, causing score overcrowding that blurs standouts and average spots together. Automatic
      score calibration unlocks the full 1–10 scale without changing a single rank.
    </p>

    <div class="hero-actions">
      <a class="cta-primary" href="#demo">Try the Live Demo ↓</a>
      <a class="cta-secondary" href="#problem">Start the 2-Minute Pitch ↓</a>
    </div>
  </div>

  <div class="pillar-grid">
    <div class="pillar-card">
      <div class="pillar-title">100% Order Locked</div>
      <p class="pillar-copy">
        Every head-to-head comparison stays untouched from #1 down to #N.
      </p>
    </div>

    <div class="pillar-card">
      <div class="pillar-title">Fairer Friend &amp; Rec Scores</div>
      <p class="pillar-copy">
        Generous raters and tough critics speak the same 1–10 language.
      </p>
    </div>

    <div class="pillar-card">
      <div class="pillar-title">Zero Manual Re-Ranking</div>
      <p class="pillar-copy">
        Runs automatically in milliseconds, with zero UX friction for diners.
      </p>
    </div>
  </div>
</section>

<style>
  .hero-cover {
    padding: 32px 30px 28px;
    display: grid;
    gap: 24px;
    background: linear-gradient(180deg, #ffffff 0%, #fcf9f4 100%);
  }

  .hero-content {
    display: grid;
    gap: 12px;
    max-width: 780px;
  }

  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: clamp(1.75rem, 3.4vw, 2.55rem);
    line-height: 1.12;
    letter-spacing: -0.025em;
    color: var(--ink);
  }

  .hero-lead {
    margin: 0;
    font-size: 1.03rem;
    line-height: 1.58;
    color: var(--ink-muted);
  }

  .hero-lead strong {
    color: var(--ink);
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 12px;
    margin-top: 4px;
  }

  .cta-primary {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    background: var(--accent);
    color: #ffffff;
    font-size: 0.9rem;
    font-weight: 700;
    padding: 10px 18px;
    border-radius: 999px;
    transition: background-color 0.14s ease, transform 0.14s ease;
  }

  .cta-primary:hover {
    background: var(--accent-hover);
    transform: translateY(-1px);
  }

  .cta-secondary {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--border-strong);
    font-size: 0.88rem;
    font-weight: 600;
    padding: 9px 16px;
    border-radius: 999px;
    transition: background-color 0.14s ease, border-color 0.14s ease;
  }

  .cta-secondary:hover {
    background: var(--surface-subtle);
  }

  .pillar-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
    padding-top: 18px;
    border-top: 1px dashed var(--border);
  }

  .pillar-card {
    background: var(--surface-subtle);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 13px 15px;
    display: grid;
    gap: 4px;
  }

  .pillar-title {
    font-size: 0.9rem;
    font-weight: 700;
    color: var(--ink);
  }

  .pillar-copy {
    margin: 0;
    font-size: 0.82rem;
    line-height: 1.45;
    color: var(--ink-muted);
  }

  @media (max-width: 820px) {
    .hero-cover {
      padding: 22px 18px 20px;
      gap: 18px;
    }

    .pillar-grid {
      grid-template-columns: minmax(0, 1fr);
      gap: 10px;
    }
  }
</style>
