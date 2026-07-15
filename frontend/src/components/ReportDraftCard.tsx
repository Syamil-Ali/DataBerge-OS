import { Play, RotateCcw } from 'lucide-react';
import { useState } from 'react';

import type { ReportDraft } from '../types/domain';
import { formatText } from '../utils/format';
import { ReportDocument } from './report/ReportDocument';

type ReportDraftCardProps = {
  draft: ReportDraft;
  onExecute: () => void;
  onRevise?: (instruction: string) => void;
  busy?: boolean;
};

export function ReportDraftCard({ draft, onExecute, onRevise, busy }: ReportDraftCardProps) {
  const [reviseInput, setReviseInput] = useState('');

  const submitRevision = () => {
    const instruction = reviseInput.trim();
    if (!instruction || busy || !onRevise) return;
    onRevise(instruction);
    setReviseInput('');
  };

  return (
    <div className="report-draft-card">
      <div className="draft-header">
        <h3 className="draft-title">{formatText(draft.title)}</h3>
      </div>

      <ReportDocument
        payload={draft}
        title={draft.title}
        compact
        showHeader={false}
        showGovernance={false}
      />

      <div className="draft-footer">
        {onRevise && (
          <div className="draft-revise-row">
            <input
              className="draft-revise-input"
              placeholder="Focus more on risk, add charts..."
              value={reviseInput}
              onChange={(event) => setReviseInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  submitRevision();
                }
              }}
            />
            <button
              type="button"
              className="draft-revise-btn"
              disabled={!reviseInput.trim() || busy}
              onClick={submitRevision}
            >
              <RotateCcw size={14} />
              Revise
            </button>
          </div>
        )}
        <button type="button" className="draft-execute-btn" onClick={onExecute} disabled={busy}>
          <Play size={15} />
          {busy ? 'Saving...' : 'Execute'}
        </button>
      </div>
    </div>
  );
}
