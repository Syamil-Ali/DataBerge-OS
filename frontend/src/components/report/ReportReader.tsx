import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  BarChart3,
  ChevronRight,
  ExternalLink,
  FileText,
  Layers3,
  MessageSquare,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react';

import type { Artifact } from '../../types/domain';
import { formatText } from '../../utils/format';
import { getReportOutline, openReportDocument, ReportDocument } from './ReportDocument';
import { TEMPLATE_LABELS } from './reportConfig';

export type ReportProgress = {
  status?: string;
  message?: string;
  percent?: number;
  current_step?: string;
  sections?: { key: string; label: string; status: string }[];
};

export function getReportProgress(report: Artifact): ReportProgress | null {
  const progress = report.payload?.report_progress;
  return progress && typeof progress === 'object' ? progress as ReportProgress : null;
}

export function isReportGenerating(report: Artifact) {
  const progress = getReportProgress(report);
  return report.status === 'generating' || progress?.status === 'queued' || progress?.status === 'running';
}

export function formatReportDate(value?: string) {
  if (!value) return 'Date unavailable';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  }).format(date);
}

export function reportTypeLabel(report: Artifact) {
  const explicit = String(report.payload?.report_type || '').trim();
  if (explicit) return explicit;
  const template = String(report.payload?.template || '').trim();
  return TEMPLATE_LABELS[template] || 'Report';
}

function reportSectionStats(report: Artifact) {
  const outline = getReportOutline(report.payload as any);
  const supplied = report.payload?.document?.sections || report.payload?.sections || [];
  const chartCount = Array.isArray(supplied)
    ? supplied.reduce((count: number, section: any) => {
      const kind = section?.presentation?.kind || section?.kind;
      if (kind !== 'chart') return count;
      return count + (Array.isArray(section?.content) ? section.content.length : section?.content ? 1 : 0);
    }, 0)
    : Array.isArray(report.payload?.charts) ? report.payload.charts.length : 0;
  return { sectionCount: outline.length, chartCount };
}

export function ReportLibraryRow({
  report,
  actionBusy,
  onOpen,
  onDelete,
  onSendToChat,
  sendBusy,
}: {
  report: Artifact;
  actionBusy: boolean;
  onOpen: () => void;
  onDelete: () => void;
  onSendToChat?: () => void;
  sendBusy: boolean;
}) {
  const progress = getReportProgress(report);
  const generating = isReportGenerating(report);
  const failed = report.status === 'failed' || progress?.status === 'failed';
  const percent = Math.min(100, Math.max(0, Number(progress?.percent ?? (generating ? 5 : 100))));
  const governance = report.payload?.governance;
  const { sectionCount, chartCount } = reportSectionStats(report);

  const open = () => {
    if (!generating && !failed) onOpen();
  };

  return (
    <article
      className={`report-library-row ${generating ? 'generating' : ''} ${failed ? 'failed' : ''}`}
      role="button"
      tabIndex={generating || failed ? -1 : 0}
      onClick={open}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          open();
        }
      }}
    >
      <span className="report-library-row-icon"><FileText size={17} /></span>
      <div className="report-library-row-body">
        <div className="report-library-row-topline">
          <span>{reportTypeLabel(report)}</span>
          <span>{formatReportDate(report.updated_at || report.created_at)}</span>
        </div>
        <h4>{formatText(report.title)}</h4>
        {generating && progress ? (
          <>
            <p>{formatText(progress.message || 'Generating report')}</p>
            <ReportProgressBar progress={progress} percent={percent} />
          </>
        ) : failed && progress ? (
          <p className="report-progress-error">{formatText(progress.message || 'Report generation failed.')}</p>
        ) : (
          <div className="report-library-row-facts">
            <span><Layers3 size={12} />{sectionCount} sections</span>
            {chartCount > 0 && <span><BarChart3 size={12} />{chartCount} chart{chartCount === 1 ? '' : 's'}</span>}
            {governance && (
              <span className="governance"><ShieldCheck size={12} />{governance.passed}/{governance.total} checks</span>
            )}
          </div>
        )}
      </div>
      {!generating && !failed && (
        <div className="report-library-row-actions">
          {onSendToChat && (
            <button
              type="button"
              className="report-icon-btn neutral"
              title="Send report to Chat"
              aria-label={`Send ${report.title} to Chat`}
              disabled={sendBusy}
              onClick={(event) => { event.stopPropagation(); onSendToChat(); }}
            >
              <MessageSquare size={15} />
            </button>
          )}
          <button
            type="button"
            className="report-icon-btn reject"
            title="Delete report"
            aria-label={`Delete ${report.title}`}
            disabled={actionBusy}
            onClick={(event) => { event.stopPropagation(); onDelete(); }}
          >
            <Trash2 size={15} />
          </button>
          <ChevronRight className="report-row-chevron" size={17} />
        </div>
      )}
    </article>
  );
}

function ReportProgressBar({ progress, percent }: { progress: ReportProgress; percent: number }) {
  const sections = Array.isArray(progress.sections) ? progress.sections : [];
  return (
    <div className="report-progress-block" aria-label="Report generation progress">
      <div className="report-progress-track"><span style={{ width: `${percent}%` }} /></div>
      {sections.length > 0 && (
        <div className="report-progress-steps">
          {sections.map((section) => (
            <span key={section.key} className={section.status}>{formatText(section.label)}</span>
          ))}
        </div>
      )}
    </div>
  );
}

export function FullReportModal({
  report,
  onClose,
  onDelete,
  onSendToChat,
  sendBusy,
}: {
  report: Artifact;
  onClose: () => void;
  onDelete: () => void;
  onSendToChat?: () => void;
  sendBusy: boolean;
}) {
  const outline = useMemo(() => getReportOutline(report.payload as any), [report]);
  const readerRef = useRef<HTMLDivElement>(null);
  const [activeSection, setActiveSection] = useState(outline[0]?.key || '');
  const readiness = report.payload?.readiness;
  const governance = report.payload?.governance;
  const sectionPrefix = `report-reader-${report.id}`;

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', closeOnEscape);
    };
  }, [onClose]);

  useEffect(() => {
    const root = readerRef.current;
    if (!root || !outline.length) return;
    const elements = outline
      .map((item) => root.querySelector(`[data-report-section-key="${item.key}"]`))
      .filter((element): element is Element => Boolean(element));
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
      if (visible) setActiveSection(visible.target.getAttribute('data-report-section-key') || '');
    }, { root, rootMargin: '-12% 0px -68% 0px', threshold: [0, 0.15, 0.4] });
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [outline, report.id]);

  const scrollToSection = (key: string) => {
    setActiveSection(key);
    readerRef.current
      ?.querySelector(`[data-report-section-key="${key}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return createPortal(
    (
      <div className="report-reader-shell" role="dialog" aria-modal="true" aria-label={report.title}>
        <div className="report-reader-backdrop" onClick={onClose} />
        <div className="report-reader">
          <header className="report-reader-toolbar">
            <div className="report-reader-title">
              <div>
                <span>Executive Reports</span>
                <h3>{formatText(report.title)}</h3>
              </div>
            </div>
            <div className="report-reader-actions">
              <button type="button" className="report-text-btn" onClick={() => openReportDocument(report)}>
                <ExternalLink size={14} /> Open
              </button>
              {onSendToChat && (
                <button type="button" className="report-text-btn" onClick={onSendToChat} disabled={sendBusy}>
                  <MessageSquare size={14} /> {sendBusy ? 'Attaching' : 'Attach to Chat'}
                </button>
              )}
              <button type="button" className="report-icon-btn reject" title="Delete report" aria-label="Delete report" onClick={onDelete}>
                <Trash2 size={16} />
              </button>
              <button type="button" className="report-icon-btn neutral" title="Close" aria-label="Close report" onClick={onClose}>
                <X size={16} />
              </button>
            </div>
          </header>

          <div className="report-reader-layout">
            <aside className="report-reader-sidebar">
              <div className="report-reader-summary">
                <span>{reportTypeLabel(report)}</span>
                <dl>
                  <div><dt>Updated</dt><dd>{formatReportDate(report.updated_at || report.created_at)}</dd></div>
                  {readiness?.score !== undefined && <div><dt>Readiness</dt><dd>{formatText(readiness.score)}/10</dd></div>}
                  {governance && <div><dt>Governance</dt><dd>{governance.passed}/{governance.total}</dd></div>}
                </dl>
              </div>
              {outline.length > 0 && (
                <nav className="report-reader-nav" aria-label="Report sections">
                  <span>Contents</span>
                  {outline.map((item, index) => (
                    <button
                      type="button"
                      key={item.key}
                      className={activeSection === item.key ? 'active' : ''}
                      onClick={() => scrollToSection(item.key)}
                    >
                      <span>{String(index + 1).padStart(2, '0')}</span>
                      <strong>{formatText(item.label)}</strong>
                    </button>
                  ))}
                </nav>
              )}
            </aside>
            <div className="report-reader-canvas" ref={readerRef}>
              <ReportDocument
                payload={report.payload as any}
                title={report.title}
                sectionIdPrefix={sectionPrefix}
                showHeader
                showGovernance
              />
            </div>
          </div>
        </div>
      </div>
    ),
    document.body,
  );
}
