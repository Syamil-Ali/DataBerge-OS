import { Component, ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardList,
  FileText,
  Flag,
  Gauge,
  ListChecks,
  Printer,
  Shield,
  Sparkles,
  Table2,
  Target,
  XCircle,
} from 'lucide-react';

import type {
  Artifact,
  ReportDraft,
  ReportSection,
  ReportSectionKind,
  ReportSectionPresentation,
} from '../../types/domain';
import { formatText, formatValue } from '../../utils/format';
import { ChartBlock } from '../ChartBlock';
import { ActionPlan } from './ActionPlan';
import { ExecutiveSummary } from './ExecutiveSummary';
import { FindingCards } from './FindingCards';
import { References } from './References';

type ReportPayload = ReportDraft & Record<string, any>;

type ResolvedSection = ReportSection & {
  label: string;
  presentation: ReportSectionPresentation;
};

type ReportDocumentProps = {
  payload: ReportPayload;
  title?: string;
  compact?: boolean;
  showHeader?: boolean;
  showGovernance?: boolean;
  sectionIdPrefix?: string;
};

export type ReportOutlineItem = {
  key: string;
  label: string;
  kind: ReportSectionKind;
};

const SECTION_ORDER = [
  'central_theme',
  'summary',
  'overview',
  'executive_summary',
  'problem_statement',
  'key_metrics',
  'data_quality_assessment',
  'schema_analysis',
  'findings',
  'top_findings',
  'key_findings',
  'business_implications',
  'data_story',
  'methodology',
  'charts',
  'recommendations',
  'action_plan',
  'next_steps',
  'prognosis',
  'conclusions',
  'systems_detail',
  'references',
];

const KIND_BY_KEY: Record<string, ReportSectionKind> = {
  central_theme: 'callout',
  executive_summary: 'summary',
  key_metrics: 'metrics',
  findings: 'findings',
  top_findings: 'findings',
  key_findings: 'findings',
  charts: 'chart',
  action_plan: 'actions',
  recommendations: 'actions',
  next_steps: 'actions',
  prognosis: 'comparison',
  references: 'references',
  data_quality_assessment: 'key_value',
  schema_analysis: 'key_value',
  systems_detail: 'key_value',
  business_implications: 'bullets',
  data_story: 'narrative',
  summary: 'narrative',
  overview: 'narrative',
  problem_statement: 'narrative',
  methodology: 'narrative',
  conclusions: 'narrative',
};

const KIND_ICON: Record<ReportSectionKind, typeof FileText> = {
  summary: ClipboardList,
  narrative: FileText,
  metrics: Gauge,
  findings: Flag,
  chart: BarChart3,
  actions: ListChecks,
  comparison: Sparkles,
  table: Table2,
  key_value: ClipboardList,
  bullets: ListChecks,
  references: FileText,
  callout: Target,
};

const KINDS = new Set<ReportSectionKind>([
  'summary', 'narrative', 'metrics', 'findings', 'chart', 'actions',
  'comparison', 'table', 'key_value', 'bullets', 'references', 'callout',
]);
const VARIANTS = new Set<ReportSectionPresentation['variant']>(['hero', 'feature', 'standard', 'compact']);
const WIDTHS = new Set<ReportSectionPresentation['width']>(['full', 'half', 'third']);
const EMPHASES = new Set<ReportSectionPresentation['emphasis']>(['primary', 'supporting', 'context']);

export function ReportDocument({
  payload,
  title,
  compact = false,
  showHeader = true,
  showGovernance = true,
  sectionIdPrefix,
}: ReportDocumentProps) {
  const sections = normalizeSections(payload);
  const context = payload.context && typeof payload.context === 'object' ? payload.context : {};
  const readiness = payload.readiness && typeof payload.readiness === 'object' ? payload.readiness : {};
  const limitations = asList(readiness.limitations);
  const governance = payload.governance && typeof payload.governance === 'object' ? payload.governance : null;
  const reportTitle = title || payload.title || 'Report';
  const reportType = formatReportType(payload);

  return (
    <article className={`report-document ${compact ? 'report-document--compact' : ''}`}>
      {showHeader && (
        <header className="report-document-masthead">
          <div className="report-document-heading">
            <span className="report-document-kicker">{reportType}</span>
            <h1>{formatText(reportTitle)}</h1>
            {context.goal && <p>{formatText(context.goal)}</p>}
          </div>
          <dl className="report-document-meta">
            {context.audience && (
              <div>
                <dt>Audience</dt>
                <dd>{formatText(context.audience)}</dd>
              </div>
            )}
            {context.horizon && (
              <div>
                <dt>Horizon</dt>
                <dd>{formatText(context.horizon)}</dd>
              </div>
            )}
            {readiness.score !== null && readiness.score !== undefined && (
              <div>
                <dt>Readiness</dt>
                <dd>{formatText(readiness.score)}/10</dd>
              </div>
            )}
          </dl>
        </header>
      )}

      <div className="report-document-grid">
        {sections.map((section, index) => (
          <ReportDocumentSection
            key={section.key}
            section={section}
            index={index}
            compact={compact}
            readiness={readiness}
            sectionId={sectionIdPrefix ? `${sectionIdPrefix}-${section.key}` : undefined}
          />
        ))}
      </div>

      {!compact && limitations.length > 0 && (
        <section className="report-document-appendix report-document-limitations">
          <header>
            <AlertTriangle size={15} />
            <h2>Data Limitations</h2>
          </header>
          <BulletContent content={limitations} />
        </section>
      )}

      {!compact && showGovernance && governance && (
        <GovernanceReview governance={governance} />
      )}
    </article>
  );
}

function ReportDocumentSection({
  section,
  index,
  compact,
  readiness,
  sectionId,
}: {
  section: ResolvedSection;
  index: number;
  compact: boolean;
  readiness: Record<string, any>;
  sectionId?: string;
}) {
  const { presentation } = section;
  const Icon = KIND_ICON[presentation.kind] || FileText;
  const className = [
    'report-document-section',
    `kind-${presentation.kind}`,
    `variant-${presentation.variant}`,
    `width-${presentation.width}`,
    `emphasis-${presentation.emphasis}`,
    presentation.page_break_before ? 'page-break-before' : '',
  ].filter(Boolean).join(' ');

  if (presentation.kind === 'callout') {
    return (
      <section
        className={className}
        id={sectionId}
        data-report-section-key={section.key}
      >
        <div className="report-document-callout">
          <div>
            <Icon size={15} />
            <span>{formatText(section.label)}</span>
          </div>
          <p>{formatText(section.content)}</p>
        </div>
      </section>
    );
  }

  return (
    <section
      className={className}
      id={sectionId}
      data-report-section-key={section.key}
    >
      <header className="report-document-section-head">
        <span className="report-document-section-index">{String(index + 1).padStart(2, '0')}</span>
        <span className="report-document-section-icon"><Icon size={14} /></span>
        <h2>{formatText(section.label)}</h2>
      </header>
      <div className="report-document-section-body">
        <ReportRenderBoundary title={section.label}>
          <SectionContent section={section} compact={compact} readiness={readiness} />
        </ReportRenderBoundary>
      </div>
    </section>
  );
}

function SectionContent({
  section,
  compact,
  readiness,
}: {
  section: ResolvedSection;
  compact: boolean;
  readiness: Record<string, any>;
}) {
  const { content } = section;
  switch (section.presentation.kind) {
    case 'summary':
      if (content && typeof content === 'object' && !Array.isArray(content)) {
        return <ExecutiveSummary central_theme="" executive_summary={content} readiness={readiness} />;
      }
      return <NarrativeContent content={content} />;
    case 'metrics':
      return <MetricsContent content={content} />;
    case 'findings':
      return <FindingsContent content={content} defaultExpanded={!compact} />;
    case 'chart':
      return <ChartContent content={content} />;
    case 'actions':
      if (isActionPlan(content)) return <ActionPlan action_plan={content} />;
      return <ActionListContent content={content} />;
    case 'comparison':
      return <ComparisonContent content={content} />;
    case 'table':
      return <TableContent content={content} />;
    case 'key_value':
      return <KeyValueContent content={content} />;
    case 'bullets':
      return <BulletContent content={content} />;
    case 'references':
      return Array.isArray(content)
        ? <References references={content as any} />
        : <KeyValueContent content={content} />;
    case 'narrative':
    default:
      return <NarrativeContent content={content} />;
  }
}

function MetricsContent({ content }: { content: any }) {
  const metrics = Array.isArray(content) ? content.filter(Boolean) : [];
  if (!metrics.length) return <EmptyContent />;
  return (
    <div className="report-document-metrics">
      {metrics.map((metric: any, index: number) => {
        const numericScore = Number(metric?.score);
        const hasScore = Number.isFinite(numericScore);
        return (
          <article className={`report-document-metric ${metric?.health || 'info'}`} key={metric?.name || index}>
            <span>{formatText(metric?.name || `Metric ${index + 1}`)}</span>
            <strong>{formatText(metric?.value, '-')}</strong>
            {hasScore && (
              <div className="report-document-meter">
                <span style={{ width: `${Math.min(100, Math.max(0, numericScore))}%` }} />
              </div>
            )}
            {metric?.description && <p>{formatText(metric.description)}</p>}
          </article>
        );
      })}
    </div>
  );
}

function FindingsContent({ content, defaultExpanded }: { content: any; defaultExpanded: boolean }) {
  const findings = (Array.isArray(content) ? content : asList(content)).map((item: any, index) => {
    if (item && typeof item === 'object') {
      return {
        ...item,
        title: item.title || item.finding || item.summary || `Finding ${index + 1}`,
        severity: item.severity || 'info',
        confidence: item.confidence || 'medium',
        evidence: item.evidence || item.summary || item.finding || '',
      };
    }
    return {
      title: formatText(item || `Finding ${index + 1}`),
      severity: 'info',
      confidence: 'medium',
      evidence: '',
    };
  });
  return <FindingCards findings={findings} defaultExpanded={defaultExpanded} />;
}

function ChartContent({ content }: { content: any }) {
  const charts = Array.isArray(content) ? content : [content];
  const usable = charts.filter((chart) => chart && typeof chart === 'object');
  if (!usable.length) return <EmptyContent />;
  return (
    <div className="report-document-charts">
      {usable.slice(0, 5).map((chart: any, index) => (
        <ChartBlock
          key={`${chart.title || chart.type || 'chart'}-${index}`}
          title={chart.title || `Chart ${index + 1}`}
          chart={chart}
          data={Array.isArray(chart.data) ? chart.data : undefined}
        />
      ))}
    </div>
  );
}

function NarrativeContent({ content }: { content: any }) {
  const text = formatText(content);
  if (!text) return <EmptyContent />;
  const paragraphs = text.split(/\n{2,}/).map((item) => item.trim()).filter(Boolean);
  return (
    <div className="report-document-prose">
      {paragraphs.map((paragraph, index) => <p key={index}>{paragraph}</p>)}
    </div>
  );
}

function BulletContent({ content }: { content: any }) {
  const items = Array.isArray(content) ? content : asList(content);
  if (!items.length) return <EmptyContent />;
  return (
    <ul className="report-document-list">
      {items.map((item, index) => (
        <li key={index}>
          {item && typeof item === 'object' && !Array.isArray(item) ? (
            <>
              {(item.title || item.label || item.name) && <strong>{formatText(item.title || item.label || item.name)}</strong>}
              <span>{formatText(item.evidence || item.description || item.summary || item.value || item)}</span>
            </>
          ) : formatText(item)}
        </li>
      ))}
    </ul>
  );
}

function ActionListContent({ content }: { content: any }) {
  const items = Array.isArray(content) ? content : asList(content);
  if (!items.length) return <EmptyContent />;
  return (
    <ol className="report-document-actions">
      {items.map((item, index) => (
        <li key={index}>
          <span>{String(index + 1).padStart(2, '0')}</span>
          <p>{formatText(item)}</p>
        </li>
      ))}
    </ol>
  );
}

function ComparisonContent({ content }: { content: any }) {
  if (!content || typeof content !== 'object' || Array.isArray(content)) {
    return <NarrativeContent content={content} />;
  }
  const current = content.current_state ?? content.current ?? content.without_action;
  const recommended = content.with_recommendations ?? content.recommended ?? content.with_action;
  if (!current && !recommended) return <KeyValueContent content={content} />;
  return (
    <div className="report-document-comparison">
      <article className="current">
        <div><AlertTriangle size={15} /><strong>Without action</strong></div>
        <p>{formatText(current, 'No current-state projection available.')}</p>
      </article>
      <article className="recommended">
        <div><CheckCircle2 size={15} /><strong>With recommendations</strong></div>
        <p>{formatText(recommended, 'No recommended-state projection available.')}</p>
      </article>
    </div>
  );
}

function KeyValueContent({ content }: { content: any }) {
  if (!content || typeof content !== 'object' || Array.isArray(content)) {
    return <NarrativeContent content={content} />;
  }
  const entries = Object.entries(content).filter(([, value]) => value !== null && value !== undefined && value !== '');
  if (!entries.length) return <EmptyContent />;
  return (
    <dl className="report-document-details">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{formatText(key.replace(/_/g, ' '))}</dt>
          <dd>
            {Array.isArray(value) ? <BulletContent content={value} /> : (
              value && typeof value === 'object'
                ? <KeyValueContent content={value} />
                : formatText(value)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function TableContent({ content }: { content: any }) {
  const rows = Array.isArray(content) ? content.filter((item) => item && typeof item === 'object' && !Array.isArray(item)) : [];
  if (!rows.length) return <BulletContent content={content} />;
  const columns = Array.from(new Set(rows.slice(0, 20).flatMap((row) => Object.keys(row)))).slice(0, 10);
  return (
    <div className="report-document-table-wrap">
      <table className="report-document-table">
        <thead>
          <tr>{columns.map((column) => <th key={column}>{formatText(column.replace(/_/g, ' '))}</th>)}</tr>
        </thead>
        <tbody>
          {rows.slice(0, 25).map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => <td key={column}>{formatValue(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GovernanceReview({ governance }: { governance: Record<string, any> }) {
  const checks = Array.isArray(governance.checks) ? governance.checks : [];
  return (
    <section className="report-document-appendix report-document-governance">
      <header>
        <Shield size={15} />
        <h2>Governance Review</h2>
        {(governance.passed !== undefined || governance.total !== undefined) && (
          <span>{formatText(governance.passed, '0')}/{formatText(governance.total, '0')} checks</span>
        )}
      </header>
      {governance.summary && <p>{formatText(governance.summary)}</p>}
      {checks.length > 0 && (
        <div className="report-document-checks">
          {checks.map((check: any, index: number) => (
            <div className={check?.passed ? 'passed' : 'failed'} key={index}>
              {check?.passed ? <CheckCircle2 size={13} /> : <XCircle size={13} />}
              <span>{formatText(check?.check || `Check ${index + 1}`)}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyContent() {
  return <p className="report-document-empty">No content generated for this section.</p>;
}

class ReportRenderBoundary extends Component<
  { title: string; children: ReactNode },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error(`Could not render report section: ${this.props.title}`, error);
  }

  render() {
    if (this.state.error) {
      return <p className="report-document-empty">This section could not be rendered.</p>;
    }
    return this.props.children;
  }
}

export function openReportDocument(report: Artifact) {
  const reportWindow = window.open('', '_blank');
  if (!reportWindow) return;

  const styles = Array.from(document.head.querySelectorAll('link[rel="stylesheet"], style'))
    .map((node) => {
      const clone = node.cloneNode(true) as HTMLElement;
      if (node instanceof HTMLLinkElement && clone instanceof HTMLLinkElement) clone.href = node.href;
      return clone.outerHTML;
    })
    .join('\n');

  reportWindow.document.open();
  reportWindow.document.write(`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">${styles}</head><body><div id="report-window-root"></div></body></html>`);
  reportWindow.document.close();
  reportWindow.document.title = report.title;
  const rootElement = reportWindow.document.getElementById('report-window-root');
  if (!rootElement) return;

  createRoot(rootElement).render(
    <div className="report-standalone-shell">
      <div className="report-window-toolbar">
        <div>
          <span>Data-Berge OS</span>
          <strong>{formatText(report.title)}</strong>
        </div>
        <button type="button" onClick={() => reportWindow.print()}>
          <Printer size={15} />
          Print / PDF
        </button>
      </div>
      <main className="report-standalone-page">
        <ReportDocument
          payload={report.payload as ReportPayload}
          title={report.title}
          showHeader
          showGovernance
        />
      </main>
    </div>,
  );
}

export function getReportOutline(payload: ReportPayload): ReportOutlineItem[] {
  return normalizeSections(payload).map((section) => ({
    key: section.key,
    label: section.label,
    kind: section.presentation.kind,
  }));
}

function normalizeSections(payload: ReportPayload): ResolvedSection[] {
  const documentSections = payload.document && Array.isArray(payload.document.sections)
    ? payload.document.sections
    : null;
  const supplied = documentSections || (Array.isArray(payload.sections) ? payload.sections : null);
  const rawSections = supplied && supplied.length ? supplied : legacySections(payload);

  return rawSections
    .filter((section) => section && section.key)
    .map((section, index) => {
      const content = unwrapSchemaContent(section.content);
      const presentation = resolvePresentation(section, content, index);
      return {
        ...section,
        content,
        label: section.label || titleCase(section.key),
        presentation,
      };
    });
}

function legacySections(payload: ReportPayload): ReportSection[] {
  const order = Array.isArray(payload.block_order) && payload.block_order.length
    ? payload.block_order
    : SECTION_ORDER;
  return order
    .filter((key, index) => order.indexOf(key) === index && hasContent(payload[key]))
    .map((key) => ({
      key,
      label: payload.block_labels?.[key] || titleCase(key),
      content: payload[key],
    }));
}

function resolvePresentation(section: ReportSection, content: any, index: number): ReportSectionPresentation {
  const raw = section.presentation || {};
  const hintedKind = section.kind || raw.kind;
  const kind = hintedKind && KINDS.has(hintedKind) ? hintedKind : inferKind(section.key, content);
  let variant: ReportSectionPresentation['variant'] = kind === 'callout' ? 'hero' : kind === 'summary' ? 'feature' : 'standard';
  let width: ReportSectionPresentation['width'] = ['narrative', 'bullets', 'key_value'].includes(kind) && index > 0 && contentWeight(content) <= 420 ? 'half' : 'full';
  let emphasis: ReportSectionPresentation['emphasis'] = ['callout', 'summary', 'metrics', 'findings', 'actions'].includes(kind) ? 'primary' : 'supporting';

  if (raw.variant && VARIANTS.has(raw.variant)) variant = raw.variant;
  if (raw.width && WIDTHS.has(raw.width)) width = raw.width;
  if (raw.emphasis && EMPHASES.has(raw.emphasis)) emphasis = raw.emphasis;
  if (['summary', 'metrics', 'findings', 'chart', 'actions', 'comparison', 'table', 'references', 'callout'].includes(kind)) width = 'full';

  return { kind, variant, width, emphasis, page_break_before: Boolean(raw.page_break_before) };
}

function inferKind(key: string, content: any): ReportSectionKind {
  if (KIND_BY_KEY[key]) return KIND_BY_KEY[key];
  if (typeof content === 'string') return 'narrative';
  if (Array.isArray(content)) {
    if (!content.length || content.every((item) => typeof item === 'string')) return 'bullets';
    const rows = content.filter((item) => item && typeof item === 'object' && !Array.isArray(item));
    if (rows.length && rows.every((item) => 'name' in item && 'value' in item)) return 'metrics';
    if (rows.length && rows.every((item) => 'title' in item || 'finding' in item || 'evidence' in item)) return 'findings';
    return rows.length ? 'table' : 'bullets';
  }
  if (content && typeof content === 'object') {
    const keys = new Set(Object.keys(content));
    if (['situation', 'background', 'assessment', 'recommendation'].some((keyName) => keys.has(keyName))) return 'summary';
    if (['immediate', 'short_term', 'long_term'].some((keyName) => keys.has(keyName))) return 'actions';
    if (['current_state', 'with_recommendations'].some((keyName) => keys.has(keyName))) return 'comparison';
    return 'key_value';
  }
  return 'narrative';
}

function unwrapSchemaContent(content: any) {
  if (!content || typeof content !== 'object' || Array.isArray(content)) return content;
  if (!['array', 'string', 'object', 'number', 'boolean'].includes(content.type)) return content;
  if (Array.isArray(content.items)) return content.items;
  if ('value' in content) return content.value;
  if ('content' in content) return content.content;
  return content;
}

function isActionPlan(content: any): content is { immediate?: string[]; short_term?: string[]; long_term?: string[] } {
  return Boolean(content && typeof content === 'object' && !Array.isArray(content)
    && ('immediate' in content || 'short_term' in content || 'long_term' in content));
}

function formatReportType(payload: ReportPayload) {
  if (payload.report_type) return formatText(payload.report_type);
  const template = String(payload.template || 'custom').replace(/_/g, ' ');
  return `${titleCase(template)} Report`;
}

function titleCase(value: string) {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function asList(value: any): any[] {
  if (Array.isArray(value)) return value.filter((item) => item !== null && item !== undefined && item !== '');
  if (value === null || value === undefined || value === '') return [];
  return [value];
}

function hasContent(value: any) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'string') return Boolean(value.trim());
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
}

function contentWeight(value: any): number {
  if (typeof value === 'string') return value.length;
  if (Array.isArray(value)) return value.reduce((total, item) => total + contentWeight(item), 0);
  if (value && typeof value === 'object') return Object.entries(value).reduce((total, [key, item]) => total + key.length + contentWeight(item), 0);
  return String(value || '').length;
}
