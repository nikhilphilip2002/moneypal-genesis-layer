export function formatIndianNumber(
  value: number,
  options: Intl.NumberFormatOptions = {},
): string {
  return value.toLocaleString('en-IN', options);
}

export function formatINR(
  value?: number,
  options: Intl.NumberFormatOptions = {},
): string {
  return `₹${formatIndianNumber(Number(value || 0), options)}`;
}

type CompactINROptions = {
  croreDigits?: number;
  lakhDigits?: number;
  thousandDigits?: number;
};

export function formatCompactINR(
  raw?: number,
  {
    croreDigits = 2,
    lakhDigits = 2,
    thousandDigits = 1,
  }: CompactINROptions = {},
): string {
  const value = Number(raw || 0);
  const magnitude = Math.abs(value);
  if (magnitude >= 10_000_000) {
    return `₹${(value / 10_000_000).toFixed(croreDigits)} Cr`;
  }
  if (magnitude >= 100_000) {
    return `₹${(value / 100_000).toFixed(lakhDigits)} L`;
  }
  if (magnitude >= 1_000) {
    return `₹${(value / 1_000).toFixed(thousandDigits)} K`;
  }
  return formatINR(value, { maximumFractionDigits: 0 });
}
