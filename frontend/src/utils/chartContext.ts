import { formatPercent, formatText, formatValue } from './format';

export type ChartContextColumn = {
  name: string;
  dtype?: unknown;
  duckdb_type?: unknown;
  semantic_type?: unknown;
  missing_count?: unknown;
  missing_pct?: unknown;
  unique_count?: unknown;
  stats?: Record<string, unknown> | null;
  description?: string | null;
  quality_notes?: string[] | null;
  key_type?: string | null;
};

export function formatColumnChartContext(
  column: ChartContextColumn,
  chartData: { label: string; count: number }[],
  options: { tableName?: string } = {},
) {
  const chartKind = column.semantic_type === 'numeric' ? 'Distribution chart' : 'Top values chart';
  const stats = column.stats
    ? [
        `Min: ${formatValue(column.stats.min)}`,
        `Max: ${formatValue(column.stats.max)}`,
        `Mean: ${formatValue(column.stats.mean)}`,
        `Median: ${formatValue(column.stats.median)}`,
        `Std: ${formatValue(column.stats.std)}`,
      ]
    : [];
  const chartRows = chartData
    .slice(0, 12)
    .map((item) => `${item.label}: ${formatValue(item.count)}`);
  const columnLabel = options.tableName ? `${options.tableName}.${column.name}` : column.name;

  return [
    `${chartKind}: ${columnLabel}`,
    ...(options.tableName ? [`Table: ${options.tableName}`, `Column: ${column.name}`] : []),
    `Data type: ${formatValue(column.dtype ?? column.duckdb_type)}`,
    `Semantic type: ${formatValue(column.semantic_type)}`,
    `Missing: ${formatValue(column.missing_count)} (${formatPercent(column.missing_pct)})`,
    `Unique values: ${formatValue(column.unique_count)}`,
    ...stats,
    chartRows.length ? `Chart values:\n${chartRows.join('\n')}` : '',
    column.description ? `Description: ${formatText(column.description)}` : '',
    column.quality_notes?.length ? `Quality notes: ${column.quality_notes.join('; ')}` : '',
    column.key_type ? `Key type: ${column.key_type}` : '',
  ].filter(Boolean).join('\n');
}
