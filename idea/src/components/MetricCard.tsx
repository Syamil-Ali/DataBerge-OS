import React from 'react';

interface MetricCardProps {
  title: string;
  value: string;
  trend: string;
  trendUp: boolean;
  icon: React.ElementType;
  iconBg: string;
}

export function MetricCard({ title, value, trend, trendUp, icon: Icon, iconBg }: MetricCardProps) {
  return (
    <div className="bg-white rounded-2xl p-5 shadow-soft border border-slate-200 flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-slate-500 uppercase tracking-wide">{title}</span>
        <div className={`w-10 h-10 rounded-full flex items-center justify-center ${iconBg}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
      </div>
      <div className="flex items-end justify-between">
        <div className="flex flex-col">
          <span className="text-3xl font-black text-[#0f172a] tracking-tight">{value}</span>
        </div>
        <div className={`flex items-center gap-1 text-sm font-bold rounded-full px-2.5 py-1 ${trendUp ? 'bg-emerald-50 text-[#059669]' : 'bg-red-50 text-[#dc2626]'}`}>
          {trendUp ? '↑' : '↓'} {trend}
        </div>
      </div>
    </div>
  );
}
