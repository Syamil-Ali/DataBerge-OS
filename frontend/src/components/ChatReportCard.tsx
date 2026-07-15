import { ArrowUpRight, BarChart3, FileText, Layers3, LoaderCircle, Trash2 } from 'lucide-react';

import type { Artifact } from '../types/domain';

type ChatReportCardProps = {
  artifact: Artifact;
  onOpen?: () => void;
  onRemove?: () => void;
};

function reportStats(artifact: Artifact) {
  const sections = artifact.payload?.document?.sections || artifact.payload?.sections;
  const sectionCount = Array.isArray(sections) ? sections.length : 0;
  const charts = Array.isArray(artifact.payload?.charts) ? artifact.payload.charts.length : Array.isArray(sections)
    ? sections.filter((section: any) => (section?.presentation?.kind || section?.kind) === 'chart').length
    : 0;
  return { sectionCount, charts };
}

export function ChatReportCard({ artifact, onOpen, onRemove }: ChatReportCardProps) {
  const { sectionCount, charts } = reportStats(artifact);
  const generating = artifact.status === 'generating';
  const failed = artifact.status === 'failed';

  return (
    <section className={`chat-report-card ${generating ? 'generating' : ''} ${failed ? 'failed' : ''}`} aria-label="Generated report">
      <div className="chat-report-card-icon">
        {generating ? <LoaderCircle className="report-spinner" size={17} /> : <FileText size={17} />}
      </div>
      <div className="chat-report-card-body">
        <div className="chat-report-card-meta">
          <span>Report artifact</span>
        </div>
        <h4>{artifact.title}</h4>
        <div className="chat-report-card-facts">
          {sectionCount > 0 && <span><Layers3 size={12} />{sectionCount} sections</span>}
          {charts > 0 && <span><BarChart3 size={12} />{charts} chart{charts === 1 ? '' : 's'}</span>}
          {failed && <span>Generation failed</span>}
        </div>
      </div>
      <div className="chat-report-card-actions">
        {onOpen && !failed && (
          <button type="button" className="chat-report-card-open" onClick={onOpen} disabled={generating}>
            <ArrowUpRight size={15} />
            <span>Open report</span>
          </button>
        )}
        {onRemove && (
          <button type="button" className="chat-report-card-remove" onClick={onRemove} title="Remove report from Chat" aria-label="Remove report from Chat">
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </section>
  );
}
