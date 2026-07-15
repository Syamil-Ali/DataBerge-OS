import {
  AlertTriangle,
  CheckCircle2,
  FileText,
  Info,
  Target,
} from 'lucide-react';
import { formatText } from '../../utils/format';

type ExecutiveSummaryProps = {
  central_theme: string;
  executive_summary: {
    situation?: string[];
    background?: string[];
    assessment?: string[];
    recommendation?: string[];
  };
  readiness?: {
    score?: number;
    label?: string;
    limitations?: string[];
  };
  key_metrics?: Array<{
    name: string;
    value: string;
    health: string;
    trend: string;
    score: number;
    description: string;
  }>;
};

const SBAR_SECTIONS = [
  { key: 'situation', label: 'Situation', sublabel: 'What the data shows', tone: 'info', icon: FileText },
  { key: 'background', label: 'Background', sublabel: 'Context about the dataset', tone: 'neutral', icon: Info },
  { key: 'assessment', label: 'Assessment', sublabel: 'What the patterns mean', tone: 'warning', icon: AlertTriangle },
  { key: 'recommendation', label: 'Recommendation', sublabel: 'Actions to take', tone: 'success', icon: CheckCircle2 },
] as const;

export function ExecutiveSummary({ central_theme, executive_summary = {}, key_metrics }: ExecutiveSummaryProps) {
  const metrics = (key_metrics || []).slice(0, 4);

  return (
    <div className="report-exec-stack">
      {central_theme && (
        <div className="report-exec-theme">
          <div className="report-exec-theme-label">
            <Target size={14} />
            <span>Central Theme</span>
          </div>
          <p>{formatText(central_theme)}</p>
        </div>
      )}

      {metrics.length > 0 && (
        <div className="report-exec-group">
          <h4>Key Metrics</h4>
          <div className="report-exec-metrics">
            {metrics.map((metric) => (
              <div key={metric.name} className={`report-exec-metric ${metric.health || 'info'}`}>
                <span className="report-exec-metric-label">{formatText(metric.name)}</span>
                <strong>{formatText(metric.value)}</strong>
                <div className="report-exec-meter">
                  <span style={{ width: `${Math.min(100, Math.max(0, metric.score))}%` }} />
                </div>
                <p>{formatText(metric.description)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="report-exec-group">
        <h4>Situation And Recommendation</h4>
        <div className="report-sbar-grid">
          {SBAR_SECTIONS.map(({ key, label, sublabel, tone, icon: Icon }) => {
            const items = executive_summary[key as keyof typeof executive_summary] || [];
            if (!items.length) return null;

            return (
              <article key={key} className={`report-sbar-card ${tone}`}>
                <header>
                  <span className="report-sbar-icon">
                    <Icon size={15} />
                  </span>
                  <div>
                    <strong>{label}</strong>
                    <small>{sublabel}</small>
                  </div>
                </header>
                <ul>
                  {items.map((item, index) => (
                    <li key={index}>{formatText(item)}</li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
