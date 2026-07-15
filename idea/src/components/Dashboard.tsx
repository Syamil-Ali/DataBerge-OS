import React from 'react';
import { Sidebar } from './Sidebar';
import { MetricCard } from './MetricCard';
import { DataChart } from './DataChart';
import { AgentChat } from './AgentChat';
import { Activity, Users, DollarSign, Target, Database } from 'lucide-react';

export function Dashboard() {
  return (
    <div className="min-h-screen flex bg-slate-50">
      <Sidebar />
      
      <main className="flex-1 ml-[260px] p-8 max-w-[1400px]">
        <header className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-[#0f172a] tracking-tight">Make your data talk.</h1>
            <p className="text-sm font-medium text-slate-500 mt-1">Overview of your connected data sources</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-2 bg-white border border-slate-200 rounded-full px-4 py-2 text-sm font-bold text-slate-600 shadow-sm">
              <div className="w-2 h-2 rounded-full bg-emerald-500"></div>
              System Systems Normal
            </span>
            <button className="bg-brand-navy text-white rounded-full px-5 py-2 text-sm font-bold shadow-soft hover:bg-[#172033] transition-colors">
              New Query
            </button>
          </div>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <MetricCard 
            title="Total Users" 
            value="124.5K" 
            trend="12.5%" 
            trendUp={true} 
            icon={Users} 
            iconBg="bg-blue-600" 
          />
          <MetricCard 
            title="Revenue" 
            value="$842.2K" 
            trend="8.2%" 
            trendUp={true} 
            icon={DollarSign} 
            iconBg="bg-emerald-500" 
          />
          <MetricCard 
            title="Active Sessions" 
            value="1,492" 
            trend="2.4%" 
            trendUp={false} 
            icon={Activity} 
            iconBg="bg-amber-500" 
          />
          <MetricCard 
            title="Goal Completion" 
            value="68.2%" 
            trend="4.1%" 
            trendUp={true} 
            icon={Target} 
            iconBg="bg-cyan-500" 
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 flex flex-col gap-6">
            <DataChart />
            
            <div className="bg-white rounded-2xl shadow-soft border border-slate-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[#0f172a]">Recent Datasets</h3>
                <button className="text-sm font-bold text-brand-cyan hover:text-brand-cyan-dark transition-colors">View All</button>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-100">
                      <th className="py-3 px-4 text-xs font-black text-slate-400 uppercase tracking-wider">Name</th>
                      <th className="py-3 px-4 text-xs font-black text-slate-400 uppercase tracking-wider">Source</th>
                      <th className="py-3 px-4 text-xs font-black text-slate-400 uppercase tracking-wider">Records</th>
                      <th className="py-3 px-4 text-xs font-black text-slate-400 uppercase tracking-wider">Status</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm font-medium text-[#0f172a]">
                    <tr className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4 flex items-center gap-2">
                        <Database className="w-4 h-4 text-brand-cyan" /> Q2_Financials.csv
                      </td>
                      <td className="py-3 px-4 text-slate-500">Stripe Export</td>
                      <td className="py-3 px-4"><span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full text-xs font-bold">12,492</span></td>
                      <td className="py-3 px-4"><span className="bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full text-xs font-bold">Synced</span></td>
                    </tr>
                    <tr className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4 flex items-center gap-2">
                        <Database className="w-4 h-4 text-brand-cyan" /> User_Events_May.json
                      </td>
                      <td className="py-3 px-4 text-slate-500">Mixpanel</td>
                      <td className="py-3 px-4"><span className="bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full text-xs font-bold">842,105</span></td>
                      <td className="py-3 px-4"><span className="bg-emerald-50 text-emerald-600 px-2 py-0.5 rounded-full text-xs font-bold">Synced</span></td>
                    </tr>
                    <tr className="hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4 flex items-center gap-2">
                        <Database className="w-4 h-4 text-slate-400" /> Marketing_Campaigns.xlsx
                      </td>
                      <td className="py-3 px-4 text-slate-500">Google Ads</td>
                      <td className="py-3 px-4"><span className="bg-slate-100 text-slate-500 px-2 py-0.5 rounded-full text-xs font-bold">4,120</span></td>
                      <td className="py-3 px-4"><span className="bg-amber-50 text-amber-600 px-2 py-0.5 rounded-full text-xs font-bold">Syncing</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          
          <div className="lg:col-span-1">
            <AgentChat />
          </div>
        </div>
      </main>
    </div>
  );
}
