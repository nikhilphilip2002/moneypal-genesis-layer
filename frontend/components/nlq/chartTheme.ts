// Chart theme for the NLQ layer.
//
// The categorical order is fixed and never cycled: slot N always belongs to the Nth series
// in the ChartSpec, so a filter that removes a series does not repaint the survivors.
// Validated with the dataviz palette validator (light mode, surface #fcfcfb):
//   lightness band PASS · chroma floor PASS · CVD separation PASS (worst adjacent ΔE 9.1)
//   normal-vision floor PASS (worst adjacent ΔE 19.6) · contrast WARN
// The contrast WARN obligates relief — every chart here ships a table view (ChartSpec.rows
// is always populated), which satisfies it.
//
// Dark values are the same hues re-stepped for the dark surface, not an automatic flip.

export const SERIES_LIGHT = [
  '#2a78d6', // blue
  '#eb6834', // orange
  '#1baf7a', // aqua
  '#eda100', // yellow
  '#e87ba4', // magenta
  '#008300', // green
  '#4a3aa7', // violet
  '#e34948', // red
] as const;

export const SERIES_DARK = [
  '#3987e5',
  '#d95926',
  '#199e70',
  '#c98500',
  '#d55181',
  '#008300',
  '#9085e9',
  '#e66767',
] as const;

// Past eight series, colour stops being an identity channel. The renderer folds the tail
// into "Other" rather than generating a ninth hue.
export const MAX_SERIES = 8;

// ─── Sequential (magnitude: heatmap cells, meter track) ───
// One hue, light→dark, five bins. Nine steps was the first attempt and failed the
// validator's adjacent-ΔL check at every pair (~0.047, floor 0.06): more steps than the
// eye can separate is not more information. Five bins is also the point past which
// adjacent heat classes start to blur.
//   node scripts/validate_palette.js "#86b6ef,#3987e5,#256abf,#184f95,#0d366b" \
//     --mode light --ordinal   → monotone PASS · ΔL PASS · light-end 2.06:1 PASS · hue spread 4° PASS
//   node scripts/validate_palette.js "#cde2fb,#9ec5f4,#6da7ec,#3987e5,#184f95" \
//     --mode dark  --ordinal   → monotone PASS · ΔL PASS · light-end 2.15:1 PASS · hue spread 4° PASS
export const SEQUENTIAL_LIGHT = ['#86b6ef', '#3987e5', '#256abf', '#184f95', '#0d366b'] as const;
export const SEQUENTIAL_DARK = ['#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5', '#184f95'] as const;
export const SEQUENTIAL_BINS = 5;

// ─── Diverging (polarity: variance, waterfall) ───
// Blue ↔ red: warm/cool, so the poles read as opposite and the midpoint reads as nothing.
// The midpoint is neutral grey, never a hue. Aqua was not considered for the negative arm
// precisely because blue↔aqua are both cool and the zero point stops meaning zero.
//   node scripts/validate_palette.js "#2a78d6,#e34948" --mode light → all PASS (CVD ΔE 21.6)
//   node scripts/validate_palette.js "#3987e5,#e66767" --mode dark  → all PASS (CVD ΔE 19.2)
export const DIVERGING = {
  light: { positive: '#2a78d6', negative: '#e34948', neutral: '#f0efec' },
  dark: { positive: '#3987e5', negative: '#e66767', neutral: '#383835' },
} as const;

export type Mode = 'light' | 'dark';

export function seriesColor(index: number, mode: Mode): string {
  const palette = mode === 'dark' ? SERIES_DARK : SERIES_LIGHT;
  return palette[index % palette.length];
}

/** Bin a value into the sequential ramp. `max` is the largest magnitude in the grid, so
 *  the ramp always spans the data actually shown rather than an absolute scale. */
export function heatColor(value: number, max: number, mode: Mode): string {
  const ramp = mode === 'dark' ? SEQUENTIAL_DARK : SEQUENTIAL_LIGHT;
  if (!Number.isFinite(value) || max <= 0) return ink(mode).grid;
  const share = Math.min(Math.max(value / max, 0), 1);
  return ramp[Math.min(Math.round(share * (SEQUENTIAL_BINS - 1)), SEQUENTIAL_BINS - 1)];
}

/** Cells go dark at the top of the ramp; label ink has to follow or it disappears. */
export function heatInk(value: number, max: number, mode: Mode): string {
  if (!Number.isFinite(value) || max <= 0) return ink(mode).muted;
  const share = Math.min(Math.max(value / max, 0), 1);
  const bin = Math.round(share * (SEQUENTIAL_BINS - 1));
  if (mode === 'dark') return bin >= 3 ? '#ffffff' : '#0b0b0b';
  return bin >= 2 ? '#ffffff' : '#0b0b0b';
}

export function divergingColor(value: number, mode: Mode): string {
  const pair = DIVERGING[mode];
  if (!Number.isFinite(value) || value === 0) return pair.neutral;
  return value > 0 ? pair.positive : pair.negative;
}

export const ink = (mode: Mode) => ({
  primary: mode === 'dark' ? '#ffffff' : '#0b0b0b',
  secondary: mode === 'dark' ? '#c3c2b7' : '#52514e',
  muted: mode === 'dark' ? '#8d8c85' : '#78766f',
  grid: mode === 'dark' ? '#33322f' : '#e8e7e3',
  surface: mode === 'dark' ? '#1a1a19' : '#fcfcfb',
});

// ─── Value formatting ───
// Units come from the catalog, never guessed from the value. Indian money conventions:
// crore and lakh, because this is a report for an Indian NBFC board.

const CRORE = 1e7;
const LAKH = 1e5;

export function formatValue(value: unknown, unit: string): string {
  if (value === null || value === undefined) return '—';
  // Identifiers often arrive from PostgreSQL as numbers even though the catalog declares
  // them as text. Formatting must follow catalog semantics: grouping an account number or
  // PIN changes its displayed identity.
  if (unit === 'text' || unit === 'date' || unit === 'datetime' || unit === 'boolean') {
    return String(value);
  }
  if (typeof value !== 'number') return String(value);

  switch (unit) {
    case 'inr': {
      const magnitude = Math.abs(value);
      if (magnitude >= CRORE) return `₹${(value / CRORE).toFixed(2)} Cr`;
      if (magnitude >= LAKH) return `₹${(value / LAKH).toFixed(2)} L`;
      return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
    }
    case 'percent':
      return Math.abs(value) < 1 ? `${value.toFixed(2)}%` : `${value.toFixed(1)}%`;
    case 'count':
    case 'days':
    case 'months':
    case 'years':
    case 'year':
      return value.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    default:
      return value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }
}

// Compact form for axis ticks, where a full ₹1,27,54,559 would collide with its neighbour.
export function formatTick(value: unknown, unit: string): string {
  if (unit === 'text' || unit === 'date' || unit === 'datetime' || unit === 'boolean') {
    return String(value ?? '');
  }
  if (typeof value !== 'number') return String(value ?? '');
  if (unit === 'inr') {
    const magnitude = Math.abs(value);
    if (magnitude >= CRORE) return `₹${(value / CRORE).toFixed(1)}Cr`;
    if (magnitude >= LAKH) return `₹${(value / LAKH).toFixed(1)}L`;
    if (magnitude >= 1000) return `₹${(value / 1000).toFixed(0)}k`;
    return `₹${value}`;
  }
  if (unit === 'percent') return `${value.toFixed(value < 10 ? 1 : 0)}%`;
  if (Math.abs(value) >= 1e5) return `${(value / 1e5).toFixed(1)}L`;
  if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(0)}k`;
  return String(value);
}

export function useChartMode(): Mode {
  if (typeof document === 'undefined') return 'light';
  const stamped = document.documentElement.getAttribute('data-theme');
  if (stamped === 'dark') return 'dark';
  if (stamped === 'light') return 'light';
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light';
}
