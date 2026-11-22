export type AnimatorState = {
  progress: number;
  playing: boolean;
};

export const easeInOutCubic = (t: number): number => {
  const x = Math.max(0, Math.min(1, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
};

export const createProgressStepper = (
  durationMs: number,
  onUpdate: (t: number) => void,
  onDone?: () => void,
) => {
  let rafId = 0;
  let start = 0;
  let running = false;
  let startT = 0;
  let activeDuration = durationMs;

  const tick = (timestamp: number) => {
    if (!running) return;
    if (!start) start = timestamp;
    const elapsed = timestamp - start;
    const f = Math.max(0, Math.min(1, elapsed / activeDuration));
    const eased = easeInOutCubic(f);
    const t = f >= 1 ? 1 : startT + (1 - startT) * eased;
    onUpdate(t);
    if (f < 1) {
      rafId = requestAnimationFrame(tick);
    } else {
      running = false;
      onDone?.();
    }
  };

  return {
    play(fromT = 0) {
      if (running) return;
      const clamped = Math.max(0, Math.min(1, fromT));
      startT = clamped >= 0.999 ? 0 : clamped;
      activeDuration = Math.max(120, (1 - startT) * durationMs);
      running = true;
      start = 0;
      rafId = requestAnimationFrame(tick);
    },
    stop() {
      running = false;
      if (rafId) cancelAnimationFrame(rafId);
      rafId = 0;
    },
  };
};

export const lerp = (a: number, b: number, t: number): number => {
  const clampedT = Math.max(0, Math.min(1, t));
  return a + (b - a) * clampedT;
};
