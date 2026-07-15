import { Bot, Send, User } from 'lucide-react';
import React from 'react';

const MESSAGES = [
  { role: 'ai', content: 'Hello! I am your Data-Berge agent. How can I help you analyze your data today?' },
  { role: 'user', content: 'Can you summarize the revenue growth over the last quarter?' },
  { role: 'ai', content: 'Based on the recent datasets, Q2 revenue grew by 14.2% compared to Q1, primarily driven by a 22% increase in new user acquisition in May.' },
];

export function AgentChat() {
  return (
    <div className="bg-white rounded-2xl shadow-soft border border-slate-200 flex flex-col h-[500px] overflow-hidden">
      <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-[#08b5cf] flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-[#0f172a]">Data Agent</h3>
            <div className="flex items-center gap-1.5 mt-0.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wide">Online</span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {MESSAGES.map((msg, i) => (
          <div key={i} className={`flex items-start gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center ${msg.role === 'ai' ? 'bg-[#08b5cf]' : 'bg-[#e2e8f0]'}`}>
              {msg.role === 'ai' ? <Bot className="w-4 h-4 text-white" /> : <User className="w-4 h-4 text-slate-500" />}
            </div>
            <div className={`max-w-[80%] rounded-2xl p-3.5 text-sm font-medium leading-relaxed
              ${msg.role === 'user' 
                ? 'bg-[#162033] text-white rounded-tr-none' 
                : 'bg-slate-50 text-[#0f172a] border border-slate-100 rounded-tl-none'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-slate-200">
        <div className="relative">
          <input 
            type="text" 
            placeholder="Ask about your data..." 
            className="w-full bg-slate-50 border border-slate-200 rounded-full py-3 pl-4 pr-12 text-sm font-medium text-[#0f172a] focus:outline-none focus:ring-2 focus:ring-[#08b5cf]/50 focus:border-[#08b5cf] transition-all placeholder:text-slate-400"
          />
          <button className="absolute right-1.5 top-1.5 w-9 h-9 rounded-full bg-[#08b5cf] flex items-center justify-center hover:bg-[#0787a0] transition-colors">
            <Send className="w-4 h-4 text-white -ml-0.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
