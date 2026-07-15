import {
  BarChart3,
  CheckCircle2,
  FileText,
  ListChecks,
  RotateCcw,
  Table2,
  Target,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useState } from 'react';

import type { ReportPlan, ReportSectionKind } from '../types/domain';

type ReportPlanCardProps = {
  plan: ReportPlan;
  onConfirm?: () => void;
  onRevise?: (instruction: string) => void;
  busy?: boolean;
  closed?: boolean;
};

const kindIcon: Partial<Record<ReportSectionKind, LucideIcon>> = {
  actions: ListChecks,
  chart: BarChart3,
  comparison: Target,
  findings: Target,
  metrics: BarChart3,
  table: Table2,
};

export function ReportPlanCard({ plan, onConfirm, onRevise, busy, closed }: ReportPlanCardProps) {
  const [revision, setRevision] = useState('');

  const submitRevision = () => {
    const instruction = revision.trim();
    if (!instruction || busy || !onRevise) return;
    onRevise(instruction);
    setRevision('');
  };

  const scope = plan.dataset_scope;
  const isInteractive = Boolean(onConfirm || onRevise) && !closed;

  return (
    <section className="report-plan-card" aria-label="Proposed report plan">
      <header className="report-plan-header">
        <div className="report-plan-heading">
          <span className="report-plan-badge">Report Plan</span>
          <span className="report-plan-version">v{plan.version}</span>
        </div>
        <h3>{plan.title}</h3>
        <div className="report-plan-meta">
          <span><strong>Audience</strong>{plan.audience}</span>
          <span><strong>Report</strong>{plan.report_type}</span>
          <span><strong>Horizon</strong>{plan.horizon}</span>
        </div>
        <p className="report-plan-goal">{plan.goal}</p>
        {scope?.is_connector_sample && (
          <div className="report-plan-scope">
            <FileText size={15} aria-hidden="true" />
            <span>{scope.interpretation}</span>
          </div>
        )}
      </header>

      <ol className="report-plan-sections">
        {plan.sections.map((section, index) => {
          const Icon = kindIcon[section.kind] || FileText;
          return (
            <li className="report-plan-section" key={section.key}>
              <span className="report-plan-index">{String(index + 1).padStart(2, '0')}</span>
              <div className="report-plan-section-body">
                <div className="report-plan-section-title">
                  <Icon size={16} aria-hidden="true" />
                  <h4>{section.label}</h4>
                  <span className="report-plan-kind">{section.kind.replace('_', ' ')}</span>
                </div>
                <p>{section.purpose}</p>
                {section.data_fields.length > 0 && (
                  <div className="report-plan-fields" aria-label="Planned data fields">
                    {section.data_fields.map((field) => <span key={field}>{field}</span>)}
                  </div>
                )}
                {section.chart_intent && (
                  <div className="report-plan-chart-intent">
                    <BarChart3 size={14} aria-hidden="true" />
                    <span>{section.chart_intent}</span>
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {isInteractive ? (
        <footer className="report-plan-footer">
          {onRevise && (
            <div className="report-plan-revise">
              <input
                value={revision}
                onChange={(event) => setRevision(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    submitRevision();
                  }
                }}
                placeholder="Rename, remove, add, or reorder sections"
                disabled={busy}
              />
              <button
                type="button"
                className="report-plan-revise-button"
                onClick={submitRevision}
                disabled={busy || !revision.trim()}
              >
                <RotateCcw size={15} />
                Revise Plan
              </button>
            </div>
          )}
          {onConfirm && (
            <button
              type="button"
              className="report-plan-confirm"
              onClick={onConfirm}
              disabled={busy}
            >
              <CheckCircle2 size={17} />
              {busy ? 'Starting Generation' : 'Confirm & Generate'}
            </button>
          )}
        </footer>
      ) : (
        <div className="report-plan-closed">
          <CheckCircle2 size={15} aria-hidden="true" />
          <span>{closed ? 'Confirmed for generation' : 'Superseded by a newer plan'}</span>
        </div>
      )}
    </section>
  );
}
