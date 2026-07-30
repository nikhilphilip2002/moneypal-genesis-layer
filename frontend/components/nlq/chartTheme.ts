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

export type Mode = 'light' | 'dark';

export function seriesColor(index: number, mode: Mode): string {
  const palette = mode === 'dark' ? SERIES_DARK : SERIES_LIGHT;
  return palette[index % palette.length];
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
      return value.toLocaleString('en-IN', { maximumFractionDigits: 0 });
    default:
      return value.toLocaleString('en-IN', { maximumFractionDigits: 2 });
  }
}

// Compact form for axis ticks, where a full ₹1,27,54,559 would collide with its neighbour.
export function formatTick(value: unknown, unit: string): string {
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
