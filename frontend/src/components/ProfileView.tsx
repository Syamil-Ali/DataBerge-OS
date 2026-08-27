import { Fragment, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  Bot,
  CheckCircle2,
  Columns3,
  Database,
  FileText,
  GitCompareArrows,
  Hash,
  LayoutGrid,
  Sigma,
  Type,
} from 'lucide-react';
import { BivariateAnalysis, Dataset, RelationalSchema, TableProfile } from '../types/domain';
import { formatPercent, formatPValue, formatText, formatValue } from '../utils/format';
import { MetricCard } from './MetricCard';
import { ProfileColumnCard } from './ProfileColumnCard';
import { SchemaProfileView } from './SchemaProfileView';
import { WorkspacePageHeader } from './WorkspacePageHeader';

type ProfileViewProps = {
  dataset: Dataset | null;
  schema?: RelationalSchema | null;
  onAskInChat?: (label: string, context: string) => void;
};

const INITIAL_COLUMNS = 10;
const COLUMN_STEP = 10;

function fmt(value: unknown) {
  return formatValue(value);
}

function pct(value: unknown) {
  return formatPercent(value);
}

function roleLabel(value: string) {
  return value.replace(/_/g, ' ');
}

function BivariateBlock({ bivariate }: { bivariate: BivariateAnalysis }) {
  return (
    <section className="profile-section-card bivariate-section">
      <div className="analysis-heading profile-section-heading">
        <div>
          <p>Relationships</p>
          <h2>Group differences and correlations</h2>
        </div>
        <span className="status-pill"><GitCompareArrows size={14} /> statistical tests</span>
      </div>

      <div className="analysis-table wide">
        <div className="analysis-title">
          <Sigma size={16} />
          <strong>Numerical vs Numerical</strong>
        </div>
        <div className="table-grid numeric-grid">
          <span>Variable pair</span>
          <span>Correlation</span>
          <span>P-value</span>
          <span>Interpretation</span>
          {bivariate.numeric_numeric.length ? bivariate.numeric_numeric.slice(0, 8).map((item) => (
            <Fragment key={`${item.left}-${item.right}`}>
              <strong>{item.left} vs {item.right}</strong>
              <span>{fmt(item.correlation)}</span>
              <span>{formatPValue(item.p_value)}</span>
              <span>{item.interpretation}</span>
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
            <span>Pair</span>
            <span>P-value</span>
            <span>Result</span>
            {bivariate.categorical_categorical.length ? bivariate.categorical_categorical.slice(0, 6).map((item) => (
              <Fragment key={`${item.left}-${item.right}`}>
                <strong>{item.left} vs {item.right}</strong>
                <span>{formatPValue(item.p_value)}</span>
                <span>{item.interpretation}</span>
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
            <span>Variables</span>
            <span>P-value</span>
            <span>Result</span>
            {bivariate.numeric_categorical.length ? bivariate.numeric_categorical.slice(0, 6).map((item) => (
              <Fragment key={`${item.numeric}-${item.categorical}`}>
                <strong>{item.numeric} by {item.categorical}</strong>
                <span>{formatPValue(item.p_value)}</span>
                <span>{item.interpretation}</span>
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

export function ProfileView({ dataset, schema, onAskInChat }: ProfileViewProps) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_COLUMNS);
  const rawProfile = dataset?.profile as any;
  const tables = rawProfile?.tables as Record<string, TableProfile> | undefined;
  const tableProfile = (tables ? Object.values(tables)[0] : rawProfile) as TableProfile | undefined;
  const columns = tableProfile?.columns ?? [];
  const meta = tableProfile?.metadata;
  const engineering = tableProfile?.data_engineering;
  const qualityFlags = (tableProfile?.quality_flags ?? [])
    .filter((flag) => !flag.includes('No obvious'))
    .filter((flag) => !flag.startsWith('No human column descriptions'));
  const topCorrelation = tableProfile?.correlations?.[0] ?? null;
  const visibleColumns = columns.slice(0, visibleCount);
  const describedColumns = meta?.described_columns ?? columns.filter((column) => Boolean(column.description)).length;
  const descriptionCoverage = meta?.description_coverage_pct ?? (columns.length ? (describedColumns / columns.length) * 100 : 0);
  const semanticRoles = (engineering?.semantic_roles ?? {}) as Record<string, string[]>;
  const roleEntries = Object.entries(semanticRoles).filter(([, roleColumns]) => roleColumns.length);

  const counts = useMemo(() => ({
    numeric: columns.filter((column) => column.semantic_type === 'numeric').length,
    categorical: columns.filter((column) => column.semantic_type === 'categorical').length,
    text: columns.filter((column) => column.semantic_type === 'text').length,
    datetime: columns.filter((column) => column.semantic_type === 'datetime').length,
  }), [columns]);

  // Keep hooks in the same order when the workspace switches between a dataset
  // and a relational schema. Returning before useMemo here previously caused
  // React to render fewer hooks on that transition.
  if (schema) {
    return <SchemaProfileView schema={schema} onAskInChat={onAskInChat} />;
  }

  if (!dataset || !tableProfile) {
    return (
      <section className="profile-view empty-state">
        <Database size={34} />
        <h2>No dataset selected</h2>
        <p>Upload a CSV or Excel file to generate the profile.</p>
      </section>
    );
  }

  return (
    <section className="profile-view data-pulse-view">
      <div className="data-pulse-sticky-header">
        <WorkspacePageHeader
          title="Data Pulse"
          description="Understand what is in this dataset, spot issues, and choose what to explore next."
          actions={onAskInChat ? (
              <button
                className="profile-export-btn"
                type="button"
                onClick={() => onAskInChat('Dataset profile', `Summarize the dataset profile for ${dataset.name}. Rows: ${dataset.row_count}. Columns: ${dataset.column_count}.`)}
              >
                <Bot size={14} />
                Ask in Explorer
              </button>
          ) : null}
        />
      </div>

      <div className="data-pulse-scroll-content">
      <div className="metric-grid profile-metric-grid">
        <MetricCard label="Rows" value={dataset.row_count.toLocaleString()} icon={Hash} tone="blue" />
        <MetricCard label="Variables" value={columns.length.toLocaleString()} icon={Columns3} tone="cyan" />
        <MetricCard label="Descriptions" value={`${describedColumns}/${columns.length}`} icon={FileText} tone="emerald" />
        <MetricCard label="Missing cells" value={(meta?.missing_cells ?? 0).toLocaleString()} icon={AlertTriangle} tone="amber" />
      </div>

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
              <strong>{describedColumns}/{columns.length}</strong>
              <small>{pct(descriptionCoverage)} coverage</small>
            </div>
            <div>
              <span>Duplicate rows</span>
              <strong>{(meta?.duplicate_rows ?? 0).toLocaleString()}</strong>
              <small>Structural duplicates</small>
            </div>
            <div>
              <span>Top relationship</span>
              <strong>{topCorrelation ? fmt(topCorrelation.correlation) : '-'}</strong>
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
                  {roleEntries.map(([role, roleColumns]) => (
                    <span key={role}>{roleLabel(role)}: {roleColumns.slice(0, 3).map((item) => formatText(item)).join(', ')}</span>
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
                  <strong>{counts.text}</strong>
                </div>
              </div>
            </>
          ) : (
            <p className="profile-summary-copy">Engineering checks are not available for this dataset yet.</p>
          )}
        </section>
      </div>

      <div className="profile-detail-grid">
        <section className="profile-panel">
          <div className="profile-panel-head">
            <div>
              <p>Column mix</p>
              <h3>Semantic types</h3>
            </div>
            <CheckCircle2 size={18} />
          </div>
          <div className="profile-list-stack">
            <div className="profile-list-item"><Sigma size={15} /> Numeric: {counts.numeric}</div>
            <div className="profile-list-item"><BarChart3 size={15} /> Categorical: {counts.categorical}</div>
            <div className="profile-list-item"><Type size={15} /> Text: {counts.text}</div>
            <div className="profile-list-item"><FileText size={15} /> Datetime: {counts.datetime}</div>
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
            {engineering?.recommended_actions?.length ? (
              engineering.recommended_actions.map((item, index) => <div className="profile-list-item" key={`${formatText(item)}-${index}`}>{formatText(item)}</div>)
            ) : (
              <div className="profile-list-item muted">No prep work is required before the next analyst pass.</div>
            )}
          </div>
        </section>
      </div>

      <section className="profile-section-card">
        <div className="analysis-heading profile-section-heading">
          <div>
            <p>Column explorer</p>
            <h2><LayoutGrid size={20} /> Univariate analysis</h2>
          </div>
          <span className="profile-summary-copy">{visibleColumns.length} of {columns.length} columns</span>
        </div>

        <div className="column-grid">
          {visibleColumns.map((column) => <ProfileColumnCard key={column.name} column={column} onAskInChat={onAskInChat} />)}
        </div>

        {visibleCount < columns.length ? (
          <div className="page-dots">
            <button type="button" onClick={() => setVisibleCount((count) => Math.min(columns.length, count + COLUMN_STEP))}>
              Show 10 more
            </button>
          </div>
        ) : null}
      </section>

      {tableProfile.bivariate_analysis ? (
        <BivariateBlock bivariate={tableProfile.bivariate_analysis} />
      ) : null}
      </div>
    </section>
  );
}
