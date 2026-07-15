import { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Code2,
  Eye,
  Info,
} from 'lucide-react';
import { ChartBlock } from '../ChartBlock';
import { formatText, formatValue } from '../../utils/format';

type Finding = {
  title: string;
  severity: string;
  confidence: string;
  evidence: string;
  sql?: string;
  data_preview?: Record<string, any>[];
  chart?: any;
  columns_used?: string[];
};

type FindingCardsProps = {
  findings: Finding[];
  defaultExpanded?: boolean;
};

const SEVERITY_ICON: Record<string, typeof AlertTriangle> = {
  critical: AlertTriangle,
  concerning: AlertTriangle,
  good: CheckCircle2,
  info: Info,
};

export function FindingCards({ findings, defaultExpanded = false }: FindingCardsProps) {
  const [expanded, setExpanded] = useState<Set<number>>(
    () => defaultExpanded ? new Set(findings.map((_, index) => index)) : new Set(),
  );

  const toggle = (index: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  if (!findings.length) {
    return <p className="report-muted-empty">No findings to display.</p>;
  }

  return (
    <div className="report-finding-list">
      {findings.filter(Boolean).map((finding, index) => {
        const severity = finding.severity || 'info';
        const SeverityIcon = SEVERITY_ICON[severity] || Info;
        const isExpanded = expanded.has(index);
        const title = formatText(finding.title || (finding as any).finding || (finding as any).summary || `Finding ${index + 1}`);
        const previewRows = Array.isArray(finding.data_preview) ? finding.data_preview.filter(Boolean) : [];
        const columnsUsed = Array.isArray(finding.columns_used) ? finding.columns_used : [];

        return (
          <article key={index} className={`report-finding-card ${severity}`}>
            <button className="report-finding-head" onClick={() => toggle(index)}>
              <span className="report-finding-icon">
                <SeverityIcon size={15} />
              </span>
              <span className="report-finding-title">{title}</span>
              <span className={`report-pill severity ${severity}`}>{formatText(severity)}</span>
              <span className={`report-pill confidence ${finding.confidence || 'medium'}`}>
                {formatText(finding.confidence || 'medium')}
              </span>
              {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>

            {isExpanded && (
              <div className="report-finding-body">
                {finding.evidence && (
                  <div className="report-detail-block">
                    <h5>Evidence</h5>
                    <p>{formatText(finding.evidence)}</p>
                  </div>
                )}

                {columnsUsed.length > 0 && (
                  <div className="report-detail-block">
                    <h5>Columns</h5>
                    <div className="report-token-row">
                      {columnsUsed.map((column, columnIndex) => (
                        <span key={`${formatText(column)}-${columnIndex}`}>{formatText(column)}</span>
                      ))}
                    </div>
                  </div>
                )}

                {finding.sql && (
                  <details className="report-disclosure">
                    <summary>
                      <Code2 size={12} />
                      <span>View SQL</span>
                    </summary>
                    <pre><code>{finding.sql}</code></pre>
                  </details>
                )}

                {previewRows.length > 0 && (
                  <details className="report-disclosure">
                    <summary>
                      <Eye size={12} />
                      <span>Data Preview ({previewRows.length} rows)</span>
                    </summary>
                    <div className="report-mini-table-wrap">
                      <table className="report-mini-table">
                        <thead>
                          <tr>
                            {Object.keys(previewRows[0]).map((column) => (
                              <th key={column}>{column}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {previewRows.slice(0, 5).map((row, rowIndex) => (
                            <tr key={rowIndex}>
                              {Object.values(row).map((value, valueIndex) => (
                                <td key={valueIndex}>{formatValue(value)}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                )}

                {finding.chart && <ChartBlock title={title} chart={finding.chart} />}
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
