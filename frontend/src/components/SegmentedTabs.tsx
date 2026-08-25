import { ReactNode } from 'react';

type SegmentedTab<T extends string> = {
  value: T;
  label: string;
  icon?: ReactNode;
  badge?: ReactNode;
};

type SegmentedTabsProps<T extends string> = {
  label: string;
  value: T;
  tabs: readonly SegmentedTab<T>[];
  onChange: (value: T) => void;
  className?: string;
};

export function SegmentedTabs<T extends string>({
  label,
  value,
  tabs,
  onChange,
  className = '',
}: SegmentedTabsProps<T>) {
  return (
    <div className={className} role="tablist" aria-label={label}>
      {tabs.map((tab) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={active}
            className={active ? 'active' : ''}
            onClick={() => onChange(tab.value)}
          >
            {tab.icon}
            {tab.label}
            {tab.badge !== undefined ? <span>{tab.badge}</span> : null}
          </button>
        );
      })}
    </div>
  );
}
