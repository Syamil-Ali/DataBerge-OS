export type TopValue = { label: string; count: number };

export function normalizeTopValues(value: unknown): TopValue[] {
  let values: TopValue[];
  if (Array.isArray(value)) {
    values = value
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === 'object')
      .map((item) => ({
        label: String(item.label ?? ''),
        count: Number(item.count ?? 0),
      }));
  } else if (value && typeof value === 'object') {
    values = Object.entries(value).map(([label, count]) => ({
      label,
      count: Number(count ?? 0),
    }));
  } else {
    return [];
  }

  return orderOrdinalRanges(values);
}

export function orderCategoryRows<T extends Record<string, any>>(rows: T[], key: string): T[] {
  const ordered = orderOrdinalRanges(rows.map((row) => ({ label: String(row[key] ?? ''), count: 0 })));
  if (ordered.length === rows.length && ordered.every((item, index) => item.label === String(rows[index]?.[key] ?? ''))) {
    return rows;
  }
  const byLabel = new Map(rows.map((row) => [String(row[key] ?? ''), row]));
  return ordered.map((item) => byLabel.get(item.label)).filter((row): row is T => Boolean(row));
}

function orderOrdinalRanges(values: TopValue[]): TopValue[] {
  const parsed = values.map((item) => ({ item, range: parseRange(item.label) }));
  const bounded = parsed.filter((entry) => entry.range?.upper !== null);
  const hasOpenEnded = parsed.some((entry) => entry.range?.upper === null);
  if (bounded.length < 2 || !hasOpenEnded) return values;

  const maxUpper = Math.max(...bounded.map((entry) => entry.range!.upper!));
  return parsed
    .filter((entry) => {
      if (!entry.range) return false;
      return entry.range.upper !== null || entry.range.lower > maxUpper;
    })
    .sort((a, b) => a.range!.lower - b.range!.lower)
    .map((entry) => entry.item);
}

function parseRange(label: string): { lower: number; upper: number | null } | null {
  const bounded = label.trim().match(/^(\d+)\s*-\s*(\d+)$/);
  if (bounded) return { lower: Number(bounded[1]), upper: Number(bounded[2]) };
  const open = label.trim().match(/^(\d+)\s*\+$/);
  if (open) return { lower: Number(open[1]), upper: null };
  return null;
}
