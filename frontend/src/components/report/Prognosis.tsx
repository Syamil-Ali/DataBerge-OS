import { useState } from 'react';
import { Activity, TrendingDown, TrendingUp } from 'lucide-react';
import { formatText } from '../../utils/format';

type PrognosisProps = {
  prognosis: {
    current_state?: string;
    with_recommendations?: string;
  };
};

export function Prognosis({ prognosis }: PrognosisProps) {
  const [activeTab, setActiveTab] = useState<'current' | 'recommended'>('current');
  const hasContent = Boolean(prognosis?.current_state || prognosis?.with_recommendations);

  if (!hasContent) {
    return <p className="report-muted-empty">No prognosis available.</p>;
  }

  const content = activeTab === 'current'
    ? prognosis.current_state || 'No data available.'
    : prognosis.with_recommendations || 'No data available.';

  return (
    <div className="report-prognosis">
      <div className="report-segmented">
        <button
          className={activeTab === 'current' ? 'active danger' : ''}
          onClick={() => setActiveTab('current')}
        >
          <TrendingDown size={14} />
          Current State
        </button>
        <button
          className={activeTab === 'recommended' ? 'active success' : ''}
          onClick={() => setActiveTab('recommended')}
        >
          <TrendingUp size={14} />
          With Recommendations
        </button>
      </div>

      <div className={`report-prognosis-card ${activeTab}`}>
        <div className="report-card-title">
          <Activity size={14} />
          <h4>{activeTab === 'current' ? 'Without Action' : 'With Recommendations'}</h4>
        </div>
        <p>{formatText(content)}</p>
      </div>
    </div>
  );
}
