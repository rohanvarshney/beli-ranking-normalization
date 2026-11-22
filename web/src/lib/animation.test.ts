import { describe, expect, it } from 'vitest';

import { easeInOutCubic, lerp } from './animation';

describe('animation utilities', () => {
  it('lerp interpolates and clamps', () => {
    expect(lerp(2, 10, 0)).toBe(2);
    expect(lerp(2, 10, 0.5)).toBe(6);
    expect(lerp(2, 10, 1)).toBe(10);
    expect(lerp(2, 10, -10)).toBe(2);
    expect(lerp(2, 10, 3)).toBe(10);
  });

  it('easeInOutCubic clamps and eases smoothly at endpoints and midpoint', () => {
    expect(easeInOutCubic(-0.5)).toBe(0);
    expect(easeInOutCubic(0)).toBe(0);
    expect(easeInOutCubic(0.25)).toBeLessThan(0.25);
    expect(easeInOutCubic(0.5)).toBe(0.5);
    expect(easeInOutCubic(0.75)).toBeGreaterThan(0.75);
    expect(easeInOutCubic(1)).toBe(1);
    expect(easeInOutCubic(1.5)).toBe(1);
  });
});
