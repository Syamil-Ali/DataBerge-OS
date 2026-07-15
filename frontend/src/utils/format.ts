export function formatNumber(value: number, maximumFractionDigits = 2) {
  return value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits,
  });
}

export function formatValue(value: unknown, maximumFractionDigits = 2) {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'number') return formatNumber(value, maximumFractionDigits);
  if (typeof value === 'string' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value);
}

export function formatText(value: unknown, fallback = ''): string {
  if (value === null || value === undefined || value === '') return fallback;
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => formatText(item)).filter(Boolean).join(', ');
  if (typeof value === 'object') {
    const record = value as Record<string, unknown>;
    if (record.description !== undefined) return formatText(record.description, fallback);
    if (record.summary !== undefined) return formatText(record.summary, fallback);
    if (record.value !== undefined) return formatText(record.value, fallback);
    if (record.label !== undefined) return formatText(record.label, fallback);
    return Object.entries(record)
      .map(([key, item]) => `${key}: ${formatText(item, '-')}`)
      .join('; ');
  }
  return String(value);
}

export function formatPercent(value: unknown, maximumFractionDigits = 1) {
  const numeric = typeof value === 'number' ? value : Number(value ?? 0);
  if (!Number.isFinite(numeric)) return '0%';
  return `${formatNumber(numeric, maximumFractionDigits)}%`;
}

export function formatRange(start: unknown, end: unknown, maximumFractionDigits = 2) {
  if (typeof start !== 'number' || typeof end !== 'number') return '-';
  if (!Number.isFinite(start) || !Number.isFinite(end)) return '-';
  if (start === end) return formatNumber(start, maximumFractionDigits);
  return `${formatNumber(start, maximumFractionDigits)} - ${formatNumber(end, maximumFractionDigits)}`;
}
