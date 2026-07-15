import { LucideIcon } from 'lucide-react';

type MetricCardProps = {
  label: string;
  value: string | number;
  icon: LucideIcon;
  tone?: 'cyan' | 'blue' | 'emerald' | 'amber';
};

export function MetricCard({ label, value, icon: Icon, tone = 'cyan' }: MetricCardProps) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}>
        <Icon size={18} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
      </div>
    </div>
  );
}
