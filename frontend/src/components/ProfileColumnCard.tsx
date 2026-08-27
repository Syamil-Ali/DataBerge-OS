import { Fragment } from 'react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';

import { ProfileColumn, RelationalTable } from '../types/domain';
import { formatColumnChartContext } from '../utils/chartContext';
import { formatPercent, formatRange, formatText, formatValue } from '../utils/format';
import { normalizeTopValues } from '../utils/profile';
import { ChartActionMenu } from './ChartActionMenu';

type ColumnData = ProfileColumn | RelationalTable['columns'][number];
type AskInChat = (label: string, context: string) => void;

type ProfileColumnCardProps = {
  column: ColumnData;
  tableName?: string;
  onAskInChat?: AskInChat;
};

function chartDataFor(column: ColumnData) {
  if (column.semantic_type === 'numeric' && column.histogram) {
    const { bins, counts } = column.histogram;
    return counts.map((count, index) => ({
      label: formatRange(bins[index], bins[index + 1]) || String(index + 1),
      count,
    }));
  }
  return normalizeTopValues(column.top_values)
    .slice(0, 8)
    .map((item) => ({ label: String(item.label).slice(0, 14), count: item.count }));
}

export function ProfileColumnCard({ column, tableName, onAskInChat }: ProfileColumnCardProps) {
  const isNumeric = column.semantic_type === 'numeric';
  const isText = column.semantic_type === 'text';
  const chartData = chartDataFor(column);
  const firstTopValue = normalizeTopValues(column.top_values)[0];
  const typeLabel = 'duckdb_type' in column ? column.duckdb_type : column.dtype;
  const keyType = 'key_type' in column ? column.key_type : null;
  const qualifiedName = tableName ? `${tableName}.${column.name}` : column.name;
  const canAttachChart = Boolean(onAskInChat && chartData.length);

  const attachChart = () => {
    if (!onAskInChat) return;
    onAskInChat(
      `Chart: ${qualifiedName}`,
      formatColumnChartContext(column, chartData, tableName ? { tableName } : undefined),
    );
  };

  return (
    <article className="column-card">
      <div className="column-card-head">
        <div><h3>{column.name}</h3><p>{typeLabel}</p></div>
        <div className="column-card-actions">
          <span className={`column-type-badge ${isNumeric ? 'numeric' : isText ? 'text' : 'categorical'}`}>
            {column.semantic_type}
          </span>
          {keyType ? <span className="rel-key-badge" style={{ fontSize: '10px' }}>{keyType}</span> : null}
          {canAttachChart ? <ChartActionMenu label={qualifiedName} onAttach={attachChart} /> : null}
        </div>
      </div>

      {column.description ? <p className="column-description">{formatText(column.description)}</p> : null}

      <div className="column-stats">
        <span>Unique: {formatValue(column.unique_count)}</span>
        <span>Missing: {formatPercent(column.missing_pct)}</span>
      </div>

      {chartData.length ? (
        <Fragment>
          <div className={`mini-chart ${isNumeric ? 'numeric-mini-chart' : ''}`}>
            <ResponsiveContainer width="100%" height={126}>
              <BarChart data={chartData} layout={isNumeric ? 'horizontal' : 'vertical'}>
                {isNumeric ? (
                  <>
                    <XAxis dataKey="label" hide />
                    <YAxis hide />
                    <Bar dataKey="count" fill="#22c7da" radius={[4, 4, 0, 0]} activeBar={{ fill: '#06b6d4', stroke: '#22c7da', strokeWidth: 2 }} />
                  </>
                ) : (
                  <>
                    <XAxis type="number" hide />
                    <YAxis dataKey="label" type="category" width={78} tick={{ fontSize: 10, fill: '#64748b' }} />
                    <Bar dataKey="count" fill="#34d399" radius={[0, 4, 4, 0]} activeBar={{ fill: '#10b981', stroke: '#34d399', strokeWidth: 2 }} />
                  </>
                )}
                <Tooltip cursor={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {isNumeric && column.stats ? (
            <div className="chart-range-labels">
              <span>Min {formatValue(column.stats.min)}</span>
              <span>Max {formatValue(column.stats.max)}</span>
            </div>
          ) : null}
        </Fragment>
      ) : null}

      {column.stats ? (
        <div className="numeric-stat-boxes">
          <div><span>Mean</span><strong>{formatValue(column.stats.mean)}</strong></div>
          <div><span>Median</span><strong>{formatValue(column.stats.median)}</strong></div>
          <div><span>Std</span><strong>{formatValue(column.stats.std)}</strong></div>
        </div>
      ) : null}

      {!isNumeric ? (
        <div className="column-footer">
          <span>{isText ? 'Text sample' : 'Top value'}</span>
          <strong>{formatValue(column.sample_values?.[0] ?? firstTopValue?.label)}</strong>
        </div>
      ) : null}
    </article>
  );
}
