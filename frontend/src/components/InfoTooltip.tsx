import { Info } from 'lucide-react';

export function InfoTooltip({ text }: { text: string }) {
  return (
    <span className="info-tooltip">
      <button type="button" className="info-tooltip-trigger" aria-label={text}>
        <Info size={15} />
      </button>
      <span className="info-tooltip-content" role="tooltip">{text}</span>
    </span>
  );
}
