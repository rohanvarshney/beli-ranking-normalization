<script lang="ts">
  import { STRATEGY_LIST } from '../lib/foodInsights';
</script>

<!-- Slide 4: Product Impact -->
<section id="impact" class="pitch-section">
  <div class="section-head">
    <span class="section-eyebrow">04 · Product Impact</span>
    <h2 class="section-title">Four wins across the Beli app</h2>
    <p class="section-lead">
      Calibrating scores behind the scenes makes every existing Beli surface—personal lists,
      friend feeds, and personalized recommendations—sharper without changing how diners log a meal.
    </p>
  </div>

  <div class="impact-grid">
    <article class="impact-card card">
      <h3>Clearer "Been" Lists</h3>
      <p>
        Power users with 100–500+ spots stop seeing dozens of meals blurred together in the low 8s,
        ending the urge to manually re-rank old spots just to make a 9+ feel earned.
      </p>
    </article>

    <article class="impact-card card">
      <h3>Smarter Rec Scores</h3>
      <p>
        Feeding calibrated user scores into Beli's recommendation model removes individual
        rating-style bias and sharpens predictions for spots a diner hasn't tried yet.
      </p>
    </article>

    <article class="impact-card card">
      <h3>Trustworthy Friend &amp; Match Scores</h3>
      <p>
        Aligns generous raters and tough critics onto one shared 1–10 scale so a friend's score
        means the same thing at a glance across your feed.
      </p>
    </article>

    <article class="impact-card card">
      <h3>Zero-Risk Rollout Paths</h3>
      <p>
        Ship silently inside the Rec Score ranking layer first, test as an opt-in
        <em>"Balanced Scale"</em> profile toggle, or apply to city leaderboards.
      </p>
    </article>
  </div>
</section>

<!-- Slide 5: Ready to Ship -->
<section id="ship" class="pitch-section">
  <div class="section-head">
    <span class="section-eyebrow">05 · Ready to Ship</span>
    <h2 class="section-title">Built to drop in without touching Beli's core UX</h2>
    <p class="section-lead">
      No database migrations, no new prompts when logging a restaurant, and zero risk to
      head-to-head ranking order.
    </p>
  </div>

  <div class="readiness-grid">
    <div class="ready-card card">
      <div class="ready-title">Sub-millisecond speed</div>
      <p>
        <code>O(n log n)</code> runtime and <code>O(n)</code> memory—calibrates a 500-spot list
        instantaneously on the fly.
      </p>
    </div>

    <div class="ready-card card">
      <div class="ready-title">Non-destructive &amp; reversible</div>
      <p>
        Raw scores and head-to-head order remain untouched; calibration is purely deterministic and
        easy to A/B test.
      </p>
    </div>

    <div class="ready-card card">
      <div class="ready-title">Production SDKs included</div>
      <p>
        Cross-language Python &amp; Go packages with full order-preservation test suites ready to
        inspect today.
      </p>
    </div>
  </div>

  <details class="tech-appendix card">
    <summary>Technical Appendix: Algorithms &amp; Guarantees</summary>
    <div class="appendix-body">
      <p>
        <strong>Monotonicity guarantee:</strong> Every strategy maps input scores onto
        <code class="tech-term">(1.0, 10.0]</code> while guaranteeing
        <code class="tech-term">raw_a &lt; raw_b ⇒ new_a ≤ new_b</code> across all pairs, with
        deterministic tie handling.
      </p>
      <ul class="appendix-list">
        {#each STRATEGY_LIST as item (item.id)}
          <li>
            <code class="tech-term">{item.code}</code> (<strong>{item.title}</strong>):
            {item.techDetail}
          </li>
        {/each}
      </ul>
    </div>
  </details>

  <footer class="pitch-footer">
    <a class="footer-btn secondary" href="#demo">Back to Live Demo ↑</a>
    <a
      class="footer-btn primary"
      href="https://github.com/rohanvarshney/beli-ranking-normalization"
      target="_blank"
      rel="noopener noreferrer"
    >
      Explore Python &amp; Go SDK on GitHub ↗
    </a>
  </footer>
</section>

<style>
  .impact-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  .impact-card {
    padding: 20px 22px;
    display: grid;
    gap: 8px;
    align-content: start;
  }

  h3 {
    margin: 0;
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--ink);
  }

  .impact-card p,
  .ready-card p {
    margin: 0;
    font-size: 0.88rem;
    line-height: 1.52;
    color: var(--ink-muted);
  }

  .readiness-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 14px;
  }

  .ready-card {
    padding: 18px 20px;
    display: grid;
    gap: 6px;
    align-content: start;
    background: var(--surface-subtle);
  }

  .ready-title {
    font-size: 0.94rem;
    font-weight: 700;
    color: var(--ink);
  }

  .ready-card code {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    color: var(--ink);
  }

  .tech-appendix {
    padding: 14px 18px;
  }

  .tech-appendix summary {
    cursor: pointer;
    font-size: 0.86rem;
    font-weight: 700;
    color: var(--ink);
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .tech-appendix summary::-webkit-details-marker {
    display: none;
  }

  .tech-appendix summary::after {
    content: '+';
    font-size: 1.05rem;
    color: var(--ink-muted);
  }

  .tech-appendix[open] summary::after {
    content: '−';
  }

  .appendix-body {
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px dashed var(--border);
    display: grid;
    gap: 10px;
    font-size: 0.83rem;
    line-height: 1.5;
    color: var(--ink-muted);
  }

  .appendix-body p {
    margin: 0;
  }

  .appendix-list {
    margin: 0;
    padding-left: 18px;
    display: grid;
    gap: 6px;
  }

  .pitch-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding-top: 8px;
  }

  .footer-btn {
    display: inline-flex;
    align-items: center;
    text-decoration: none;
    font-size: 0.88rem;
    font-weight: 700;
    padding: 10px 18px;
    border-radius: 999px;
    transition: background-color 0.14s ease, border-color 0.14s ease;
  }

  .footer-btn.secondary {
    background: var(--surface);
    color: var(--ink);
    border: 1px solid var(--border-strong);
  }

  .footer-btn.secondary:hover {
    background: var(--surface-subtle);
  }

  .footer-btn.primary {
    background: var(--accent);
    color: #ffffff;
    border: 1px solid var(--accent);
  }

  .footer-btn.primary:hover {
    background: var(--accent-hover);
  }

  @media (max-width: 820px) {
    .impact-grid,
    .readiness-grid {
      grid-template-columns: minmax(0, 1fr);
    }
  }
</style>
