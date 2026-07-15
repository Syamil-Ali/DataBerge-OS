import { Fragment, useEffect, useState } from 'react';
import {
  AlertTriangle, Bot, ChevronLeft, ChevronRight, Columns3,
  Database, EllipsisVertical, FileCog, GitCompareArrows, Hash, LayoutGrid, MessageSquareText, Sigma, Type,
} from 'lucide-react';
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { BivariateAnalysis, RelationalSchema, RelationalTable } from '../types/domain';
import { formatPercent, formatRange, formatText, formatValue } from '../utils/format';
import { formatColumnChartContext } from '../utils/chartContext';
import { MetricCard } from './MetricCard';

const COLUMNS_PER_PAGE = 6;
type AskInChat = (label: string, context: string) => void;

function fv(v: number | null | undefined) {
  if (v === null || v === undefined) return '-';
  if (Math.abs(v) < 0.0001 && v !== 0) return v.toExponential(2);
  return formatValue(v);
}

function dv(v: unknown) {
  return formatValue(v);
}

function mini(c: RelationalTable['columns'][number]) {
  if (c.semantic_type === 'numeric' && c.histogram) {
    const { bins, counts } = c.histogram;
    return counts.map((ct, i) => ({ label: formatRange(bins[i], bins[i + 1]) || String(i + 1), count: ct }));
  }
  const tv = c.top_values;
  const items = Array.isArray(tv) ? tv : tv && typeof tv === 'object' ? Object.entries(tv).map(([l, ct]) => ({ label: l, count: Number(ct) })) : [];
  return items.slice(0, 8).map((it) => ({ label: String(it.label).slice(0, 12), count: it.count }));
}

function ColumnCard({
  column,
  tableName,
  onAskInChat,
}: {
  column: RelationalTable['columns'][number];
  tableName: string;
  onAskInChat?: AskInChat;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const isNum = column.semantic_type === 'numeric';
  const isTxt = column.semantic_type === 'text';
  const cd = mini(column);
  const canAttachChart = Boolean(onAskInChat && cd.length);
  const attachChart = () => {
    if (!onAskInChat) return;
    setMenuOpen(false);
    onAskInChat(`Chart: ${tableName}.${column.name}`, formatColumnChartContext(column, cd, { tableName }));
  };
  return (
    <article className="column-card">
      <div className="column-card-head">
        <div><h3>{column.name}</h3><p>{column.duckdb_type}</p></div>
        <div className="column-card-actions">
          <span className={`column-type-badge ${isNum ? 'numeric' : isTxt ? 'text' : 'categorical'}`}>{column.semantic_type}</span>
          {column.key_type && <span className="rel-key-badge" style={{ fontSize: '10px' }}>{column.key_type}</span>}
          {canAttachChart ? (
            <div className="column-menu-wrapper">
              <button
                className="column-menu-btn"
                type="button"
                onClick={() => setMenuOpen((open) => !open)}
                title="Chart actions"
                aria-label={`Chart actions for ${tableName}.${column.name}`}
              >
                <EllipsisVertical size={15} />
              </button>
              {menuOpen ? (
                <div className="column-menu-dropdown">
                  <button type="button" onClick={attachChart}>
                    <MessageSquareText size={14} />
                    Add as attachment
                  </button>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
      {column.description && <p className="column-description">{formatText(column.description)}</p>}
      <div className="column-stats"><span>Unique: {dv(column.unique_count)}</span><span>Missing: {formatPercent(column.missing_pct)}</span></div>
      {cd.length > 0 && (
        <Fragment>
          <div className={`mini-chart ${isNum ? 'numeric-mini-chart' : ''}`}>
            <ResponsiveContainer width="100%" height={126}>
              <BarChart data={cd} layout={isNum ? 'horizontal' : 'vertical'}>
                {isNum
                  ? <><XAxis dataKey="label" hide /><YAxis hide /><Bar dataKey="count" fill="#22c7da" radius={[4,4,0,0]} activeBar={{fill:'#06b6d4',stroke:'#22c7da',strokeWidth:2}} /></>
                  : <><XAxis type="number" hide /><YAxis dataKey="label" type="category" width={70} tick={{fontSize:10,fill:'#64748b'}} /><Bar dataKey="count" fill="#34d399" radius={[0,4,4,0]} activeBar={{fill:'#10b981',stroke:'#34d399',strokeWidth:2}} /></>}
                <Tooltip cursor={false} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {isNum && column.stats ? (
            <div className="chart-range-labels">
              <span>Min {dv(column.stats.min)}</span>
              <span>Max {dv(column.stats.max)}</span>
            </div>
          ) : null}
        </Fragment>
      )}
      {column.stats && (
        <div className="numeric-stat-boxes">
          <div>
            <span>Mean</span>
            <strong>{dv(column.stats.mean)}</strong>
          </div>
          <div>
            <span>Median</span>
            <strong>{dv(column.stats.median)}</strong>
          </div>
          <div>
            <span>Std</span>
            <strong>{dv(column.stats.std)}</strong>
          </div>
        </div>
      )}
      {!isNum && (
        <div className="column-footer">
          <span>{isTxt ? 'Text sample' : 'Top values'}</span>
          <strong>{dv(column.sample_values?.[0] ?? column.top_values?.[0]?.label)}</strong>
        </div>
      )}
    </article>
  );
}

function TableReadinessPanels({
  table,
  qualityFlags,
  topCorrelation,
}: {
  table: RelationalTable;
  qualityFlags: string[];
  topCorrelation?: { left: string; right: string; correlation: number } | null;
}) {
  const meta = table.metadata ?? null;
  const engineering = table.data_engineering ?? null;
  const describedColumns = meta?.described_columns ?? table.columns.filter((column) => Boolean(column.description)).length;
  const descriptionCoverage = meta?.description_coverage_pct ?? (table.column_count ? Math.round((describedColumns / table.column_count) * 10000) / 100 : 0);
  const roleEntries = engineering
    ? Object.entries(engineering.semantic_roles ?? {}).filter(([, columns]) => columns.length)
    : [];

  return (
    <div className="profile-overview-grid">
      <section className="profile-panel">
        <div className="profile-panel-head">
          <div>
            <p>Dataset context</p>
            <h3>Coverage and quality</h3>
          </div>
          <span className={`profile-chip ${qualityFlags.length ? 'warn' : 'ok'}`}>
            {qualityFlags.length ? `${qualityFlags.length} notes` : 'Healthy'}
          </span>
        </div>

        <div className="profile-kpi-list">
          <div>
            <span>Descriptions</span>
            <strong>{describedColumns}/{table.column_count}</strong>
            <small>{formatPercent(descriptionCoverage)} coverage</small>
          </div>
          <div>
            <span>Duplicate rows</span>
            <strong>{(meta?.duplicate_rows ?? 0).toLocaleString()}</strong>
            <small>Structural duplicates</small>
          </div>
          <div>
            <span>Top relationship</span>
            <strong>{topCorrelation ? fv(topCorrelation.correlation) : '-'}</strong>
            <small>{topCorrelation ? `${topCorrelation.left} vs ${topCorrelation.right}` : 'No numeric pair'}</small>
          </div>
        </div>

        {qualityFlags.length ? (
          <div className="quality-list">
            {qualityFlags.map((flag) => <div className="quality-row" key={flag}>{flag}</div>)}
          </div>
        ) : (
          <div className="profile-inline-note">No structural data quality warnings are currently flagged.</div>
        )}
      </section>

      <section className="profile-panel">
        <div className="profile-panel-head">
          <div>
            <p>Analyst readiness</p>
            <h3>Engineering summary</h3>
          </div>
          {engineering ? <span className="profile-readiness-badge">{engineering.readiness_score}/10</span> : null}
        </div>

        {engineering ? (
          <>
            <p className="profile-summary-copy">{formatText(engineering.summary)}</p>
            {roleEntries.length ? (
              <div className="role-strip">
                {roleEntries.map(([role, columns]) => (
                  <span key={role}>{role.replace('_', ' ')}: {columns.slice(0, 3).map((item) => formatText(item)).join(', ')}</span>
                ))}
              </div>
            ) : null}
            <div className="profile-mini-grid">
              <div className="profile-mini-card">
                <span>Warnings</span>
                <strong>{engineering.warnings.length}</strong>
              </div>
              <div className="profile-mini-card">
                <span>Actions</span>
                <strong>{engineering.recommended_actions.length}</strong>
              </div>
              <div className="profile-mini-card">
                <span>Text fields</span>
                <strong>{(meta?.text_columns ?? []).length}</strong>
              </div>
            </div>
          </>
        ) : (
          <p className="profile-summary-copy">Engineering checks are not available for this table yet.</p>
        )}
      </section>
    </div>
  );
}

function TableActionsPanels({ table }: { table: RelationalTable }) {
  const engineering = table.data_engineering;
  if (!engineering) return null;

  return (
    <div className="profile-detail-grid">
      <section className="profile-panel">
        <div className="profile-panel-head">
          <div>
            <p>Risk review</p>
            <h3>Warnings</h3>
          </div>
        </div>
        <div className="profile-list-stack">
          {engineering.warnings.length ? (
            engineering.warnings.map((item, index) => <div className="profile-list-item" key={`${formatText(item)}-${index}`}>{formatText(item)}</div>)
          ) : (
            <div className="profile-list-item muted">No warnings flagged in the current engineering pass.</div>
          )}
        </div>
      </section>

      <section className="profile-panel">
        <div className="profile-panel-head">
          <div>
            <p>Next steps</p>
            <h3>Recommended actions</h3>
          </div>
        </div>
        <div className="profile-list-stack">
          {engineering.recommended_actions.length ? (
            engineering.recommended_actions.map((item, index) => <div className="profile-list-item" key={`${formatText(item)}-${index}`}>{formatText(item)}</div>)
          ) : (
            <div className="profile-list-item muted">No prep work is required before the next analyst pass.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function BivariateBlock({ b }: { b: BivariateAnalysis }) {
  return (
    <section className="profile-section-card bivariate-section">
      <div className="analysis-heading profile-section-heading">
        <div><p>Relationships</p><h2>Group differences and correlations</h2></div>
        <span className="status-pill"><GitCompareArrows size={14} /> statistical tests</span>
      </div>
      <div className="analysis-table wide">
        <div className="analysis-title">
          <Sigma size={16} />
          <strong>Numerical vs Numerical</strong>
        </div>
        <div className="table-grid numeric-grid">
          <span>Variable pair</span><span>Correlation</span><span>P-value</span><span>Interpretation</span>
          {b.numeric_numeric.length ? b.numeric_numeric.slice(0, 8).map((it) => (
            <Fragment key={`${it.left}-${it.right}`}>
              <strong>{it.left} vs {it.right}</strong>
              <span>{fv(it.correlation)}</span>
              <span>{fv(it.p_value)}</span>
              <span>{it.interpretation}</span>
            </Fragment>
          )) : (
            <Fragment>
              <strong>No numeric pair available</strong>
              <span>-</span>
              <span>-</span>
              <span>This table does not have enough paired numeric fields for correlation analysis.</span>
            </Fragment>
          )}
        </div>
      </div>
      <div className="analysis-split">
        <div className="analysis-table">
          <div className="analysis-title">
            <GitCompareArrows size={16} />
            <strong>Categorical vs Categorical</strong>
          </div>
          <div className="table-grid cat-grid">
            <span>Pair</span><span>P-value</span><span>Result</span>
            {b.categorical_categorical.length ? b.categorical_categorical.slice(0, 6).map((it) => (
              <Fragment key={`${it.left}-${it.right}`}>
                <strong>{it.left} vs {it.right}</strong>
                <span>{fv(it.p_value)}</span>
                <span>{it.interpretation}</span>
              </Fragment>
            )) : (
              <Fragment>
                <strong>No categorical pair available</strong>
                <span>-</span>
                <span>This table does not have enough paired categorical fields for association analysis.</span>
              </Fragment>
            )}
          </div>
        </div>
        <div className="analysis-table">
          <div className="analysis-title">
            <GitCompareArrows size={16} />
            <strong>Numerical vs Categorical</strong>
          </div>
          <div className="table-grid mixed-grid">
            <span>Variables</span><span>P-value</span><span>Result</span>
            {b.numeric_categorical.length ? b.numeric_categorical.slice(0, 6).map((it) => (
              <Fragment key={`${it.numeric}-${it.categorical}`}>
                <strong>{it.numeric} by {it.categorical}</strong>
                <span>{fv(it.p_value)}</span>
                <span>{it.interpretation}</span>
              </Fragment>
            )) : (
              <Fragment>
                <strong>No mixed pair available</strong>
                <span>-</span>
                <span>This table does not have enough numeric and categorical fields for group-difference tests.</span>
              </Fragment>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export function SchemaProfileView({ schema, onAskInChat }: { schema: RelationalSchema; onAskInChat?: AskInChat }) {
  const [selTable, setSelTable] = useState(() => Object.keys(schema.schema.tables)[0] ?? '');
  const [page, setPage] = useState(1);
  const tables = schema.schema.tables;
  const entries = Object.entries(tables);
  const totalCols = entries.reduce((s, [, t]) => s + (t.column_count ?? t.columns?.length ?? 0), 0);
  const descCols = entries.reduce((s, [, t]) => s + t.columns.filter((c) => Boolean(c.description)).length, 0);
  const curTable = tables[selTable] ?? null;
  const cols = curTable?.columns ?? [];
  const totalPages = Math.max(1, Math.ceil(cols.length / COLUMNS_PER_PAGE));
  const start = (page - 1) * COLUMNS_PER_PAGE;
  const visible = cols.slice(start, start + COLUMNS_PER_PAGE);
  const goTo = (p: number) => setPage(Math.min(totalPages, Math.max(1, p)));
  const qFlags = (curTable?.quality_flags ?? [])
    .filter((f) => !f.includes('No obvious'))
    .filter((f) => !f.startsWith('No human column descriptions'));
  const corrs = curTable?.correlations ?? [];
  const topCorr = corrs[0];
  const meta = curTable?.metadata;
  const bivar = curTable?.bivariate_analysis ?? null;
  const hasProf = cols.some((c) => c.histogram || c.top_values || c.stats);
  useEffect(() => {
    const tableNames = Object.keys(schema.schema.tables ?? {});
    if (!tableNames.length) {
      setSelTable('');
      return;
    }
    if (!selTable || !schema.schema.tables[selTable]) {
      setSelTable(tableNames[0]);
    }
  }, [schema.id, schema.schema.tables, selTable]);
  useEffect(() => { setPage(1); }, [selTable]);
  return (
    <section className="profile-view data-pulse-view">
      <div className="data-pulse-sticky-header">
        <div className="section-title tab-header">
          <div>
            <h2>Data Pulse</h2>
            <p className="section-subcopy">{hasProf ? 'Per-table data profiling, distributions, readiness signals, and quality checks.' : 'Relational model context, table structure, keys, and relationship coverage.'}</p>
          </div>
          {onAskInChat ? (
            <div className="header-actions">
              <button
                className="profile-export-btn"
                type="button"
                onClick={() => onAskInChat('Relational data model profile', `Summarize the relational data model ${schema.name}. Tables: ${entries.length}. Columns: ${totalCols}.`)}
              >
                <Bot size={14} />
                Ask in chat
              </button>
            </div>
          ) : null}
        </div>
        <div className="section-divider" />
      </div>
      <div className="data-pulse-scroll-content">
      {entries.length > 1 && (<div className="metric-grid profile-metric-grid">
        <MetricCard label="Tables" value={entries.length} icon={Database} tone="cyan" />
        <MetricCard label="Columns" value={totalCols} icon={Columns3} tone="emerald" />
        <MetricCard label="Descriptions" value={`${descCols}/${totalCols}`} icon={FileCog} tone="amber" />
      </div>)}
      {entries.length > 1 && (
        <div className="rel-editor-tabs" style={{marginBottom:16}}>
          {entries.map(([name, t]) => (
            <button key={name} className={selTable === name ? 'active' : ''} onClick={() => setSelTable(name)}>
              <Database size={14} /> {name} <small style={{marginLeft:4,opacity:0.6}}>{(t.row_count ?? 0).toLocaleString()} rows</small>
            </button>
          ))}
        </div>
      )}
      {curTable && (<>
        <div className="metric-grid profile-metric-grid">
          <MetricCard label="Variables" value={curTable.column_count} icon={Columns3} tone="cyan" />
          <MetricCard label="Rows" value={(curTable.row_count ?? 0).toLocaleString()} icon={Hash} tone="blue" />
          <MetricCard label="Missing cells" value={(meta?.missing_cells ?? 0).toLocaleString()} icon={AlertTriangle} tone="amber" />
          <MetricCard label="Duplicates" value={(meta?.duplicate_rows ?? 0).toLocaleString()} icon={Type} tone="emerald" />
        </div>
        <TableReadinessPanels table={curTable} qualityFlags={qFlags} topCorrelation={topCorr} />
        <TableActionsPanels table={curTable} />
        <section className="profile-section-card">
          <div className="analysis-heading profile-section-heading">
            <div><p>Column explorer &mdash; {selTable}</p><h2><LayoutGrid size={20} /> Univariate analysis</h2></div>
            {totalPages > 1 && (
              <div className="pager">
                <span>Page {page} of {totalPages}</span>
                <div className="pager-controls">
                  <button onClick={() => goTo(page-1)} disabled={page===1}><ChevronLeft size={16} /></button>
                  <button onClick={() => goTo(page+1)} disabled={page===totalPages}><ChevronRight size={16} /></button>
                </div>
              </div>
            )}
          </div>
          <div className="column-grid">
            {visible.map((col) => (
              <ColumnCard key={col.name} column={col} tableName={selTable} onAskInChat={onAskInChat} />
            ))}
          </div>
          {totalPages > 1 && (
            <div className="page-dots">{Array.from({length:totalPages},(_,i) => (
              <button className={page===i+1?'active':''} key={i+1} onClick={() => goTo(i+1)}>{i+1}</button>
            ))}</div>
          )}
        </section>
        {bivar && <BivariateBlock b={bivar} />}
      </>)}
      </div>
    </section>
  );
}
