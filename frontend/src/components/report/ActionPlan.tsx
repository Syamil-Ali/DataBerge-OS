import { AlertCircle, Calendar, Clock } from 'lucide-react';
import { formatText } from '../../utils/format';

type ActionPlanProps = {
  action_plan: {
    immediate?: string[];
    short_term?: string[];
    long_term?: string[];
  };
};

const PHASES = [
  { key: 'immediate', label: 'Immediate', sublabel: 'Within days', icon: AlertCircle, tone: 'urgent' },
  { key: 'short_term', label: 'Short-Term', sublabel: '1-3 months', icon: Calendar, tone: 'near' },
  { key: 'long_term', label: 'Long-Term', sublabel: '6+ months', icon: Clock, tone: 'later' },
] as const;

export function ActionPlan({ action_plan }: ActionPlanProps) {
  const plan = action_plan && typeof action_plan === 'object' && !Array.isArray(action_plan) ? action_plan : {};
  const hasContent = PHASES.some((phase) => asList(plan[phase.key as keyof typeof plan]).length > 0);

  if (!hasContent) {
    return <p className="report-muted-empty">No action plan available.</p>;
  }

  return (
    <div className="report-action-grid">
      {PHASES.map((phase) => {
        const items = asList(plan[phase.key as keyof typeof plan]);
        const Icon = phase.icon;

        return (
          <article key={phase.key} className={`report-action-card ${phase.tone}`}>
            <header>
              <Icon size={15} />
              <div>
                <strong>{phase.label}</strong>
                <small>{phase.sublabel}</small>
              </div>
            </header>
            <ul>
              {items.length ? (
                items.map((item, index) => <li key={index}>{formatText(item)}</li>)
              ) : (
                <li className="empty">No items</li>
              )}
            </ul>
          </article>
        );
      })}
    </div>
  );
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map((item) => formatText(item));
  if (value === null || value === undefined || value === '') return [];
  return [formatText(value)];
}
