import React from 'react';
import { motion } from 'motion/react';
import { UploadCloud, Link as LinkIcon, Database, FileSpreadsheet, ArrowLeft, ArrowRight } from 'lucide-react';

interface DataSetupProps {
  onBack: () => void;
  onComplete: () => void;
}

export function DataSetup({ onBack, onComplete }: DataSetupProps) {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans relative overflow-hidden">
      <div className="absolute inset-0 z-0 bg-[radial-gradient(#e2e8f0_1px,transparent_1px)] [background-size:24px_24px] opacity-40 pointer-events-none"></div>

      <header className="relative z-10 p-6 flex items-center max-w-[1400px] w-full mx-auto">
        <motion.button 
          onClick={onBack} 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="flex items-center gap-2 text-sm font-bold text-slate-600 hover:text-[#0f172a] bg-white border border-slate-200 px-4 py-2 rounded-full shadow-sm transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" /> Back to Home
        </motion.button>
      </header>
      
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center p-6 max-w-5xl mx-auto w-full">
        <div className="text-center mb-12">
          <motion.h2 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-4xl md:text-5xl font-extrabold text-[#0f172a] tracking-tight mb-4"
          >
            Connect your data
          </motion.h2>
          <motion.p 
            initial={{ opacity: 0, y: 15 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="text-base md:text-lg text-slate-500 font-medium"
          >
            Choose how you want to bring your data into Data-Berge.
          </motion.p>
        </div>
        
        <div className="grid md:grid-cols-2 gap-6 w-full max-w-4xl">
          {/* Option 1: Upload */}
          <motion.div 
            onClick={onComplete}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", stiffness: 150, damping: 20, delay: 0.15 }}
            whileHover={{ y: -6, scale: 1.01, boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.05), 0 8px 10px -6px rgb(0 0 0 / 0.05)" }}
            whileTap={{ scale: 0.98 }}
            className="bg-white rounded-[24px] p-8 border border-slate-200 shadow-sm hover:border-[#08b5cf]/40 transition-colors group flex flex-col h-full cursor-pointer"
          >
            <div className="w-16 h-16 rounded-full bg-cyan-50 flex items-center justify-center mb-6 group-hover:bg-[#08b5cf]/10 transition-colors">
              <UploadCloud className="w-8 h-8 text-[#08b5cf] group-hover:scale-110 transition-transform duration-300" />
            </div>
            <h3 className="text-2xl font-extrabold text-[#0f172a] mb-3">Upload Dataset</h3>
            <p className="text-slate-500 font-medium mb-8 flex-1 leading-relaxed">
              Upload your static files directly. Perfect for one-off analysis, ad-hoc reports, and quick insights.
            </p>
            <div className="flex flex-wrap items-center gap-3 mb-8">
              <span className="flex items-center gap-1.5 text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">
                <FileSpreadsheet className="w-3.5 h-3.5 text-slate-500"/> CSV File
              </span>
              <span className="flex items-center gap-1.5 text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">
                <Database className="w-3.5 h-3.5 text-slate-500"/> JSON File
              </span>
              <span className="flex items-center gap-1.5 text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">
                Excel Sheet
              </span>
            </div>
            <button className="w-full bg-slate-50 text-[#0f172a] border border-slate-200 font-bold py-3.5 rounded-full group-hover:bg-[#08b5cf] group-hover:text-white group-hover:border-[#08b5cf] transition-all cursor-pointer flex items-center justify-center gap-2">
              Select Files <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
            </button>
          </motion.div>

          {/* Option 2: API/DB Connect */}
          <motion.div 
            onClick={onComplete}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ type: "spring", stiffness: 150, damping: 20, delay: 0.2 }}
            whileHover={{ y: -6, scale: 1.01, boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.05), 0 8px 10px -6px rgb(0 0 0 / 0.05)" }}
            whileTap={{ scale: 0.98 }}
            className="bg-white rounded-[24px] p-8 border border-slate-200 shadow-sm hover:border-indigo-500/40 transition-colors group flex flex-col h-full cursor-pointer"
          >
            <div className="w-16 h-16 rounded-full bg-indigo-50 flex items-center justify-center mb-6 group-hover:bg-indigo-100 transition-colors">
              <LinkIcon className="w-7 h-7 text-indigo-600 group-hover:scale-110 transition-transform duration-300" />
            </div>
            <h3 className="text-2xl font-extrabold text-[#0f172a] mb-3">Connect via API</h3>
            <p className="text-slate-500 font-medium mb-8 flex-1 leading-relaxed">
              Link your live databases or SaaS tools for real-time synchronization and continuous AI analysis.
            </p>
            <div className="flex flex-wrap items-center gap-3 mb-8">
              <span className="text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">PostgreSQL</span>
              <span className="text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">Stripe Payments</span>
              <span className="text-xs font-bold bg-slate-100 text-slate-600 px-3 py-1.5 rounded-full">Mixpanel</span>
            </div>
            <button className="w-full bg-slate-50 text-[#0f172a] border border-slate-200 font-bold py-3.5 rounded-full group-hover:bg-indigo-600 group-hover:text-white group-hover:border-indigo-600 transition-all cursor-pointer flex items-center justify-center gap-2">
              Configure Live Sync <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
            </button>
          </motion.div>
        </div>
      </main>
    </div>
  );
}
