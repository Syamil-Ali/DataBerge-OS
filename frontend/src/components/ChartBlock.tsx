import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { ChartSpec } from '../types/domain';
import { formatValue } from '../utils/format';

const CHART_COLORS = ['#0891b2', '#f97316', '#16a34a', '#7c3aed', '#dc2626', '#0f766e'];

type ChartBlockProps = {
  title: string;
  chart: ChartSpec & { data?: Record<string, any>[] };
  data?: Record<string, any>[];
};

export function ChartBlock({ title, chart, data }: ChartBlockProps) {
  if (!chart || typeof chart !== 'object') return null;
  const rows = data ?? chart.data ?? [];
  const yKeys = chart.y ?? [];
  if (!rows.length) return null;

  if (chart.type === 'table') {
    const columns = chart.columns?.length ? chart.columns : Object.keys(rows[0] ?? {});
    return (
      <div className="chart-block">
        <h4>{title}</h4>
        <div className="chart-table-wrap">
          <table className="chart-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column}>{column}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 25).map((row, index) => (
                <tr key={index}>
                  {columns.map((column) => (
                    <td key={column}>{formatCell(row[column])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (!chart.x || !yKeys.length) return null;
  const firstY = yKeys[0];

  return (
    <div className="chart-block">
      <h4>{title}</h4>
      <div className="chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === 'donut' ? (
            <PieChart>
              <Tooltip />
              <Legend verticalAlign="bottom" height={28} />
              <Pie
                data={rows}
                dataKey={firstY}
                nameKey={chart.x}
                innerRadius="48%"
                outerRadius="72%"
                paddingAngle={2}
              >
                {rows.map((_, index) => (
                  <Cell key={index} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                ))}
              </Pie>
            </PieChart>
          ) : chart.type === 'scatter' ? (
            <ScatterChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={chart.x} name={chart.x} tick={{ fontSize: 11 }} type="number" tickFormatter={formatNumber} />
              <YAxis dataKey={firstY} name={firstY} tick={{ fontSize: 11 }} type="number" tickFormatter={formatNumber} />
              <Tooltip cursor={{ strokeDasharray: '3 3' }} formatter={formatNumber} />
              <Scatter data={rows} fill="#0891b2" />
            </ScatterChart>
          ) : chart.type === 'line' ? (
            <LineChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={chart.x} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip formatter={formatNumber} cursor={false} />
              {yKeys.map((key) => (
                <Line
                  key={key}
                  dataKey={key}
                  stroke="#0891b2"
                  strokeWidth={2.5}
                  activeDot={{ r: 6, strokeWidth: 2, stroke: '#0891b2', fill: '#fff' }}
                  dot={false}
                />
              ))}
            </LineChart>
          ) : (
            <BarChart data={rows}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey={chart.x} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={formatNumber} />
              <Tooltip formatter={formatNumber} cursor={false} />
              {yKeys.map((key) => (
                <Bar
                  key={key}
                  dataKey={key}
                  fill="#0891b2"
                  radius={[4, 4, 0, 0]}
                  activeBar={{ fill: '#06b6d4', stroke: '#0891b2', strokeWidth: 2 }}
                />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function formatNumber(value: unknown): string {
  if (value === null || value === undefined) return '';
  return formatValue(value);
}

function formatCell(value: unknown): string {
  return formatNumber(value);
}
