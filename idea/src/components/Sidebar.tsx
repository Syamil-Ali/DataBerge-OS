import { Database, LayoutDashboard, LineChart, MessageSquare, Settings, Sparkles } from 'lucide-react';
import React from 'react';

const NAV_ITEMS = [
  { label: 'Overview', icon: LayoutDashboard, active: true },
  { label: 'Datasets', icon: Database },
  { label: 'Analysis', icon: LineChart },
  { label: 'AI Agents', icon: Sparkles },
  { label: 'Chat Log', icon: MessageSquare },
];

export function Sidebar() {
  return (
    <aside className="fixed inset-y-0 left-0 w-[260px] bg-white border-r border-slate-200 flex flex-col z-10">
      <div className="h-16 flex items-center px-6 border-b border-slate-200">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-brand-cyan flex items-center justify-center text-white font-bold">
            <Database className="w-5 h-5 text-white" />
          </div>
          <span className="font-extrabold text-[#0f172a] text-lg tracking-tight">Data-Berge</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-6 px-4 flex flex-col gap-1">
        <div className="px-2 pb-2">
          <p className="text-[10px] font-black uppercase tracking-wider text-slate-400">Main Menu</p>
        </div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.label}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-full transition-colors font-semibold text-sm w-full text-left
              ${item.active 
                ? 'bg-[#08b5cf]/10 text-[#08b5cf]' 
                : 'text-[#64748b] hover:bg-slate-50 hover:text-[#0f172a]'
              }`}
          >
            <item.icon className="w-5 h-5" />
            {item.label}
          </button>
        ))}
      </div>

      <div className="p-4 border-t border-slate-200">
        <button className="flex items-center gap-3 px-3 py-2.5 rounded-full transition-colors font-semibold text-sm text-[#64748b] hover:bg-slate-50 hover:text-[#0f172a] w-full text-left">
          <Settings className="w-5 h-5" />
          Settings
        </button>
        <div className="mt-4 flex items-center gap-3 px-3">
          <div className="w-8 h-8 rounded-full bg-slate-200 border border-slate-300"></div>
          <div className="flex flex-col">
            <span className="text-sm font-bold text-[#0f172a]">Admin User</span>
            <span className="text-xs text-[#64748b]">Ready</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
