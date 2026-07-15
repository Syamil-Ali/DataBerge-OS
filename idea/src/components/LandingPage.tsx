import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { 
  ArrowRight, 
  Database, 
  User, 
  Shield, 
  ArrowUpRight, 
  Globe, 
  BarChart3, 
  Activity, 
  Heart, 
  Sparkles, 
  HelpCircle,
  CheckCircle2,
  RefreshCw,
  Lock,
  ChevronDown
} from 'lucide-react';

interface LandingPageProps {
  onGetStarted: () => void;
}

export function LandingPage({ onGetStarted }: LandingPageProps) {
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('Home');
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  
  // Interactive Scan Simulation State
  const [scanStatus, setScanStatus] = useState<'idle' | 'scanning' | 'complete'>('idle');
  const [scanProgress, setScanProgress] = useState(0);
  const [scanResults, setScanResults] = useState<{
    integrity: number;
    anomalies: number;
    threatsBlocked: number;
  } | null>(null);

  // FAQ Accordion State
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  const startIntegrityScan = () => {
    if (scanStatus === 'scanning') return;
    setScanStatus('scanning');
    setScanProgress(0);
    
    const interval = setInterval(() => {
      setScanProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setScanStatus('complete');
          setScanResults({
            integrity: 99.8,
            anomalies: 0,
            threatsBlocked: 14,
          });
          return 100;
        }
        return prev + 4;
      });
    }, 60);
  };

  const resetScan = () => {
    setScanStatus('idle');
    setScanProgress(0);
    setScanResults(null);
  };

  // Sample interactive charts data
  const chartsData = {
    M1: 19,
    M2: 32,
    M3: 46,
    M4: 12,
    M5: 28,
  };

  const handleTabClick = (tabName: string) => {
    setActiveTab(tabName);
    if (tabName === 'Features') {
      const el = document.getElementById('features');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    } else if (tabName === 'FAQ') {
      const el = document.getElementById('faq');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    } else if (tabName === 'Home') {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } else {
      // Data App, Assets, Pricing go straight to app flow for better conversions
      onGetStarted();
    }
  };

  const faqs = [
    {
      question: "What data sources can I connect?",
      answer: "You can directly upload CSV, JSON, and Excel files, or instantly link Postgres databases, Stripe billing data, Google Analytics, and Mixpanel exports via our pre-built high-security OAuth pipelines."
    },
    {
      question: "Is my sensitive information private?",
      answer: "Absolutely. Data-Berge operates with zero-trust storage standards. Your datasets are fully isolated at the sandboxed container level and are never shared or used to train public models."
    },
    {
      question: "How does the sovereign defense algorithm work?",
      answer: "We analyze integrity metrics, check for data corruption, anomalies, and schema drifts in real-time, instantly notifying and shielding your production pipelines from toxic data ingestion."
    }
  ];

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans overflow-x-hidden selection:bg-white/20 pb-16">
      {/* Navbar */}
      <nav id="nav-header" className="fixed top-0 inset-x-0 z-50 py-6">
        <div className="max-w-[1400px] mx-auto px-6 flex items-center justify-between">
          <motion.div 
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => handleTabClick('Home')}
            className="flex items-center gap-2 cursor-pointer"
          >
            <div className="w-9 h-9 rounded-full bg-gradient-to-tr from-[#08b5cf] to-[#10b981] flex items-center justify-center text-white font-bold shadow-lg shadow-[#08b5cf]/20">
              <Database className="w-5 h-5 text-black" />
            </div>
            <span className="font-extrabold text-white text-lg tracking-tight hidden sm:inline">Data-Berge</span>
          </motion.div>
          
          {/* Enhanced Navigation Links */}
          <div className="flex items-center gap-1 bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-full p-1.5 text-xs font-semibold text-zinc-400">
            {['Home', 'Data App', 'Assets', 'Features', 'Pricing', 'FAQ'].map((tab) => (
              <button
                key={tab}
                onClick={() => handleTabClick(tab)}
                className={`relative px-4 py-2 rounded-full transition-all duration-300 ${
                  activeTab === tab 
                    ? 'text-white font-bold bg-white/5 shadow-inner' 
                    : 'hover:text-white hover:bg-white/[0.02]'
                }`}
              >
                {tab}
              </button>
            ))}
            <div className="w-[1px] h-4 bg-white/10 mx-1"></div>
            <button 
              onClick={onGetStarted}
              className="flex items-center gap-1.5 px-4 py-2 rounded-full text-zinc-400 hover:text-white hover:bg-white/[0.02] transition-all"
            >
              Protection <Shield className="w-3.5 h-3.5 text-emerald-400" />
            </button>
          </div>

          <button 
            id="btn-create-account"
            onClick={onGetStarted}
            className="group flex items-center gap-2 text-xs font-bold bg-white text-black px-5 py-2.5 rounded-full hover:bg-zinc-200 active:scale-95 transition-all shadow-lg"
          >
            <User className="w-4 h-4" /> Create Account
          </button>
        </div>
      </nav>

      {/* Hero Section */}
      <section id="hero-section" className="relative pt-36 pb-20 min-h-screen flex flex-col items-center justify-center overflow-hidden">
        {/* Background Gradients & Mesh Grid */}
        <div className="absolute inset-0 z-0 bg-[radial-gradient(#ffffff06_1px,transparent_1px)] [background-size:24px_24px] opacity-80 pointer-events-none"></div>
        
        <div className="absolute inset-0 z-0 flex items-center justify-center pointer-events-none">
          <motion.div 
            animate={{ 
              opacity: [0.2, 0.35, 0.2], 
              scale: [1, 1.1, 1],
            }}
            transition={{ duration: 10, repeat: Infinity, ease: "easeInOut" }}
            className="w-[850px] h-[500px] bg-gradient-to-tr from-[#08b5cf]/15 via-[#10b981]/8 to-transparent rounded-full blur-[120px] will-change-transform"
          />
          <motion.div 
            animate={{ 
              opacity: [0.1, 0.25, 0.1], 
              scale: [1, 1.05, 1],
            }}
            transition={{ duration: 12, repeat: Infinity, ease: "easeInOut", delay: 1 }}
            className="absolute top-1/4 right-1/4 w-[650px] h-[400px] bg-gradient-to-bl from-purple-500/8 to-transparent rounded-full blur-[100px] will-change-transform"
          />
        </div>

        {/* Floating Interactive Nodes */}
        <div className="absolute inset-0 z-10 pointer-events-none max-w-[1400px] mx-auto hidden lg:block">
          {/* Top Left: Cortex */}
          <motion.div 
            animate={{ y: [0, -10, 0] }}
            transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut" }}
            className="absolute top-[26%] left-[6%] flex items-center gap-3 cursor-pointer pointer-events-auto select-none group/node"
            onMouseEnter={() => setHoveredNode('cortex')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ willChange: 'transform' }}
          >
            <div className="w-3.5 h-3.5 rounded-full bg-white flex items-center justify-center relative transition-transform duration-300 group-hover/node:scale-110">
              <span className="absolute -inset-1 rounded-full border border-cyan-400/30 animate-ping"></span>
              <div className="w-1.5 h-1.5 rounded-full bg-cyan-400"></div>
            </div>
            <div 
              className={`flex flex-col bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-xl border transition-all duration-300 ${
                hoveredNode === 'cortex' 
                  ? 'opacity-100 translate-x-1 border-cyan-500/40 shadow-[0_0_15px_rgba(8,181,207,0.2)]' 
                  : 'opacity-60 translate-x-0 border-white/5'
              }`}
            >
              <span className="text-[10px] font-bold tracking-wider text-white flex items-center gap-1.5">
                <Activity className="w-3 h-3 text-[#08b5cf] animate-pulse"/> CORTEX AI
              </span>
              <span className="text-[9px] text-zinc-500 font-mono">Shielding active</span>
            </div>
          </motion.div>

          {/* Bottom Left: Aelf */}
          <motion.div 
            animate={{ y: [0, 10, 0] }}
            transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 0.5 }}
            className="absolute bottom-[26%] left-[10%] flex items-center gap-3 cursor-pointer pointer-events-auto select-none group/node"
            onMouseEnter={() => setHoveredNode('aelf')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ willChange: 'transform' }}
          >
            <div className="w-3.5 h-3.5 rounded-full bg-white/20 flex items-center justify-center relative transition-transform duration-300 group-hover/node:scale-110">
              <div className="w-1.5 h-1.5 rounded-full bg-[#10b981]"></div>
            </div>
            <div 
              className={`flex flex-col bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-xl border transition-all duration-300 ${
                hoveredNode === 'aelf' 
                  ? 'opacity-100 translate-x-1 border-[#10b981]/40 shadow-[0_0_15px_rgba(16,185,129,0.2)]' 
                  : 'opacity-60 translate-x-0 border-white/5'
              }`}
            >
              <span className="text-[10px] font-bold tracking-wider text-white flex items-center gap-1.5">
                <Database className="w-3 h-3 text-[#10b981]"/> METRIC VAULT
              </span>
              <span className="text-[9px] text-zinc-500 font-mono">19.346 ms latency</span>
            </div>
          </motion.div>

          {/* Top Right: Quant */}
          <motion.div 
            animate={{ y: [0, -12, 0] }}
            transition={{ duration: 6, repeat: Infinity, ease: "easeInOut", delay: 0.2 }}
            className="absolute top-[20%] right-[10%] flex items-center gap-3 cursor-pointer pointer-events-auto select-none group/node"
            onMouseEnter={() => setHoveredNode('quant')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ willChange: 'transform' }}
          >
            <div 
              className={`flex flex-col items-end bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-xl border transition-all duration-300 ${
                hoveredNode === 'quant' 
                  ? 'opacity-100 -translate-x-1 border-purple-500/40 shadow-[0_0_15px_rgba(168,85,247,0.2)]' 
                  : 'opacity-60 translate-x-0 border-white/5'
              }`}
            >
              <span className="text-[10px] font-bold tracking-wider text-white flex items-center gap-1.5">
                QUANT DEVIATION <BarChart3 className="w-3 h-3 text-purple-400"/>
              </span>
              <span className="text-[9px] text-zinc-500 font-mono">Clean schema</span>
            </div>
            <div className="w-3.5 h-3.5 rounded-full bg-white flex items-center justify-center relative transition-transform duration-300 group-hover/node:scale-110">
              <div className="w-1.5 h-1.5 rounded-full bg-purple-400"></div>
            </div>
          </motion.div>

          {/* Bottom Right: Meeton */}
          <motion.div 
            animate={{ y: [0, 12, 0] }}
            transition={{ duration: 5.2, repeat: Infinity, ease: "easeInOut", delay: 0.8 }}
            className="absolute bottom-[30%] right-[6%] flex items-center gap-3 cursor-pointer pointer-events-auto select-none group/node"
            onMouseEnter={() => setHoveredNode('meeton')}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ willChange: 'transform' }}
          >
            <div 
              className={`flex flex-col items-end bg-black/80 backdrop-blur-md px-3 py-1.5 rounded-xl border transition-all duration-300 ${
                hoveredNode === 'meeton' 
                  ? 'opacity-100 -translate-x-1 border-blue-500/40 shadow-[0_0_15px_rgba(59,130,246,0.2)]' 
                  : 'opacity-60 translate-x-0 border-white/5'
              }`}
            >
              <span className="text-[10px] font-bold tracking-wider text-white flex items-center gap-1.5">
                INTEGRATION NODE <Globe className="w-3 h-3 text-blue-400"/>
              </span>
              <span className="text-[9px] text-zinc-500 font-mono">440 edge networks</span>
            </div>
            <div className="w-3.5 h-3.5 rounded-full bg-white/20 flex items-center justify-center relative transition-transform duration-300 group-hover/node:scale-110">
              <div className="w-1.5 h-1.5 rounded-full bg-blue-400"></div>
            </div>
          </motion.div>

          {/* Elegant SVG constellation network */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            <line x1="8%" y1="28%" x2="88%" y2="22%" stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" />
            <line x1="12%" y1="72%" x2="92%" y2="68%" stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" />
            <line x1="8%" y1="28%" x2="12%" y2="72%" stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" />
            <line x1="88%" y1="22%" x2="92%" y2="68%" stroke="rgba(255, 255, 255, 0.02)" strokeWidth="1" />
            <line x1="8%" y1="28%" x2="92%" y2="68%" stroke="rgba(255, 255, 255, 0.01)" strokeWidth="1" strokeDasharray="4 4" />
            <line x1="12%" y1="72%" x2="88%" y2="22%" stroke="rgba(255, 255, 255, 0.01)" strokeWidth="1" strokeDasharray="4 4" />

            {/* Glowing active animated lines with hardware-accelerated transitions */}
            <line 
              x1="8%" y1="28%" x2="88%" y2="22%" 
              stroke="#08b5cf" 
              strokeWidth={hoveredNode ? "1.5" : "0"} 
              className="transition-all duration-500 ease-out"
              style={{
                opacity: (hoveredNode === 'cortex' || hoveredNode === 'quant') ? 0.3 : 0,
                strokeDasharray: "6 3",
              }}
            />
            <line 
              x1="12%" y1="72%" x2="92%" y2="68%" 
              stroke="#10b981" 
              strokeWidth={hoveredNode ? "1.5" : "0"} 
              className="transition-all duration-500 ease-out"
              style={{
                opacity: (hoveredNode === 'aelf' || hoveredNode === 'meeton') ? 0.3 : 0,
                strokeDasharray: "6 3",
              }}
            />
            <line 
              x1="8%" y1="28%" x2="12%" y2="72%" 
              stroke="#08b5cf" 
              strokeWidth={hoveredNode ? "1.5" : "0"} 
              className="transition-all duration-500 ease-out"
              style={{
                opacity: (hoveredNode === 'cortex' || hoveredNode === 'aelf') ? 0.3 : 0,
                strokeDasharray: "3 3",
              }}
            />
            <line 
              x1="88%" y1="22%" x2="92%" y2="68%" 
              stroke="#c084fc" 
              strokeWidth={hoveredNode ? "1.5" : "0"} 
              className="transition-all duration-500 ease-out"
              style={{
                opacity: (hoveredNode === 'quant' || hoveredNode === 'meeton') ? 0.3 : 0,
                strokeDasharray: "3 3",
              }}
            />
          </svg>
        </div>

        {/* Main Hero Center Content Group */}
        <div className="relative z-20 flex flex-col items-center justify-center flex-1 w-full max-w-4xl px-6 py-12 text-center">
          <div className="relative z-20 text-center flex flex-col items-center">


            <h1 className="text-4xl sm:text-6xl md:text-[5.5rem] font-bold text-white tracking-tight leading-[1.08] mb-6">
              One-click for <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-white/90 to-zinc-500">Data Defense</span>
            </h1>
            
            <p className="text-sm md:text-base font-medium text-zinc-400 mb-12 max-w-2xl leading-relaxed">
              Instantly scan, validate, and guard your business files against drift, schema corruption, and malicious injections. Your sovereign analytical sanctuary.
            </p>
            
            {/* Main Action CTAs */}
            <div className="flex flex-col sm:flex-row items-center gap-4 justify-center">
              <motion.button 
                id="btn-open-app-hero"
                onClick={onGetStarted}
                whileHover={{ scale: 1.03, boxShadow: "0 20px 40px -15px rgba(8, 181, 207, 0.4)" }}
                whileTap={{ scale: 0.98 }}
                className="group flex items-center gap-2 bg-gradient-to-r from-zinc-900 to-black border border-white/10 text-white px-8 py-4 rounded-full text-sm font-semibold transition-all backdrop-blur-md cursor-pointer"
              >
                Open Analytics Suite
                <ArrowUpRight className="w-4 h-4 text-zinc-400 group-hover:text-white group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </motion.button>
              <button 
                id="btn-discover-hero"
                onClick={() => handleTabClick('Features')}
                className="bg-white text-black px-8 py-4 rounded-full text-sm font-bold shadow-soft hover:bg-zinc-100 transition-all cursor-pointer active:scale-95"
              >
                Discover Features
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* NEW: Interactive Data Health Scanner Section for Elite UX */}
      <section id="interactive-diagnostic" className="py-16 relative z-30 bg-[#070707] border-y border-white/5">
        <div className="max-w-[1000px] mx-auto px-6">
          <div className="bg-[#0b0b0b]/80 border border-white/10 rounded-3xl p-6 md:p-10 backdrop-blur-md relative overflow-hidden">
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-[#08b5cf]/5 rounded-full blur-[90px] pointer-events-none"></div>
            
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-8 mb-8 relative z-10">
              <div>
                <div className="inline-flex items-center gap-1.5 text-[10px] font-bold text-emerald-400 uppercase tracking-widest mb-3">
                  <Shield className="w-3.5 h-3.5" /> Sandbox Engine Preview
                </div>
                <h3 className="text-2xl md:text-3xl font-black text-white tracking-tight">Try Live Integrity Check</h3>
                <p className="text-zinc-400 text-xs mt-1.5 max-w-md">Simulate an instant integrity analysis of a mock corporate financial dataset to see our defense model in action.</p>
              </div>

              {scanStatus === 'idle' && (
                <button
                  id="btn-trigger-scan"
                  onClick={startIntegrityScan}
                  className="flex items-center gap-2 bg-white text-black px-6 py-3 rounded-full text-xs font-black tracking-wider hover:bg-zinc-200 transition-all shadow-xl active:scale-95 cursor-pointer"
                >
                  <RefreshCw className="w-4 h-4" /> RUN INTEGRITY SCAN
                </button>
              )}

              {scanStatus === 'scanning' && (
                <div className="flex items-center gap-3 bg-white/5 border border-white/10 px-5 py-3 rounded-full text-xs font-bold text-zinc-400">
                  <RefreshCw className="w-4 h-4 text-cyan-400 animate-spin" />
                  ANALYZING SCHEMAS {scanProgress}%
                </div>
              )}

              {scanStatus === 'complete' && (
                <button
                  id="btn-reset-scan"
                  onClick={resetScan}
                  className="flex items-center gap-2 bg-white/5 border border-white/10 text-white px-5 py-3 rounded-full text-xs font-semibold hover:bg-white/10 transition-all cursor-pointer"
                >
                  Reset Sandbox
                </button>
              )}
            </div>

            {/* Scan Display Console */}
            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 font-mono text-xs relative overflow-hidden">
              {scanStatus === 'idle' && (
                <div className="py-10 text-center text-zinc-500 flex flex-col items-center justify-center gap-3">
                  <Database className="w-8 h-8 text-zinc-600 animate-pulse" />
                  <span>Interactive Engine ready. Click button to ingest dataset.</span>
                </div>
              )}

              {scanStatus === 'scanning' && (
                <div className="space-y-2.5">
                  <div className="flex justify-between text-[#08b5cf] animate-pulse">
                    <span>[BOOT] Ingesting mock_corporate_ledger.xlsx</span>
                    <span>OK</span>
                  </div>
                  <div className="text-zinc-400">
                    &gt; Scanning columns and computing anomaly hashes...
                  </div>
                  <div className="w-full bg-white/5 rounded-full h-1.5 mt-4 overflow-hidden">
                    <motion.div 
                      className="bg-[#08b5cf] h-full" 
                      style={{ width: `${scanProgress}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-zinc-600">Verification keys deployed: cortex-402b-verify</p>
                </div>
              )}

              {scanStatus === 'complete' && scanResults && (
                <div className="grid sm:grid-cols-3 gap-6 text-center py-4">
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                    <div className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider mb-1">Integrity Rating</div>
                    <div className="text-3xl font-extrabold text-emerald-400 flex items-center justify-center gap-1.5">
                      <CheckCircle2 className="w-5 h-5" /> {scanResults.integrity}%
                    </div>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                    <div className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider mb-1">Drift Anomalies</div>
                    <div className="text-3xl font-extrabold text-white">
                      {scanResults.anomalies}
                    </div>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                    <div className="text-zinc-500 text-[10px] uppercase font-bold tracking-wider mb-1">Injections Blocked</div>
                    <div className="text-3xl font-extrabold text-[#08b5cf] flex items-center justify-center gap-1.5">
                      <Lock className="w-4 h-4" /> {scanResults.threatsBlocked}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {scanStatus === 'complete' && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-6 text-center"
              >
                <button
                  id="btn-sandbox-cta"
                  onClick={onGetStarted}
                  className="inline-flex items-center gap-2 text-xs font-black text-[#10b981] bg-[#10b981]/10 px-5 py-2.5 rounded-full border border-[#10b981]/20 hover:bg-[#10b981]/20 transition-all cursor-pointer"
                >
                  Deploy Real Shields For Your Data <ArrowRight className="w-4 h-4" />
                </button>
              </motion.div>
            )}
          </div>
        </div>
      </section>

      {/* Marvellous Insights / System Capabilities Section */}
      <section id="features" className="py-28 bg-[#050505] relative z-20">
        <div className="max-w-[1200px] mx-auto px-6">
          <div className="text-center mb-16">
            <motion.div 
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true }}
              className="inline-flex items-center gap-1.5 text-xs font-black text-[#08b5cf] tracking-widest uppercase mb-4"
            >
              <Sparkles className="w-3.5 h-3.5" /> SYSTEM CAPABILITIES
            </motion.div>
            <h2 className="text-4xl md:text-5xl font-extrabold text-white mb-4 tracking-tight">Meet Marvellous Insights</h2>
            <p className="text-zinc-400 text-sm max-w-xl mx-auto">Skip manual verification. Let our live analytics dashboard automatically flag, secure, and optimize dataset distribution.</p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            {/* Top Left Card: Success Transactions (Globe) */}
            <motion.div 
              onMouseEnter={() => setHoveredCard('success')}
              onMouseLeave={() => setHoveredCard(null)}
              whileHover={{ y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`bg-[#0a0a0a] border ${hoveredCard === 'success' ? 'border-[#08b5cf]/40 shadow-[0_0_20px_rgba(8,181,207,0.08)]' : 'border-white/5'} rounded-3xl p-8 relative overflow-hidden group cursor-pointer transition-all duration-300`}
            >
              <div className="absolute top-0 right-0 w-64 h-64 bg-cyan-500/5 rounded-full blur-[70px] opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              
              <h3 className="text-5xl font-light text-white mb-2 flex items-center gap-1.5">
                98.2% 
                <span className="text-lg text-emerald-400 font-bold">↗</span>
              </h3>
              <p className="text-xs font-bold text-zinc-500 tracking-widest uppercase mb-12">Spots . WorldWide</p>
              
              {/* Fake Globe Visual */}
              <div className="absolute top-8 right-8 w-44 h-44 border border-white/5 rounded-full flex items-center justify-center overflow-hidden">
                <motion.div 
                  animate={{ rotate: 360 }}
                  transition={{ duration: 30, repeat: Infinity, ease: "linear" }}
                  className="w-32 h-32 border border-dashed border-zinc-800 rounded-full relative"
                >
                  <div className="absolute w-2 h-2 bg-[#08b5cf] rounded-full top-4 left-10 blur-[0.5px]"></div>
                  <div className="absolute w-1.5 h-1.5 bg-[#10b981] rounded-full bottom-10 right-10 blur-[0.5px]"></div>
                </motion.div>
                <span className="absolute top-1 left-4 text-[7px] font-mono text-zinc-600">Spot 2 (Active)</span>
                <span className="absolute bottom-6 right-2 text-[7px] font-mono text-[#08b5cf]">Spot 3 (Connected)</span>
              </div>

              <div className="flex flex-wrap gap-2 text-[9px] text-zinc-400 mt-20">
                <span className="bg-white/5 border border-white/10 px-2.5 py-1 rounded-full font-mono uppercase">^K Opens Spots API Dev</span>
                <span className="bg-white/5 border border-white/10 px-2.5 py-1 rounded-full font-mono uppercase">I Assign issue to experts</span>
              </div>

              <div className="mt-8 border-t border-white/5 pt-6">
                <h4 className="text-sm font-semibold text-white mb-1.5">Success Transactions</h4>
                <p className="text-xs text-zinc-500 max-w-sm">Innovative AI models process financial flows and trigger live alerts to streamline operational efficiency.</p>
              </div>
            </motion.div>

            {/* Top Right Card: Liquidity Labyrinth (3D Interactive Cylinder Bars) */}
            <motion.div 
              onMouseEnter={() => setHoveredCard('labyrinth')}
              onMouseLeave={() => setHoveredCard(null)}
              whileHover={{ y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`bg-[#0a0a0a] border ${hoveredCard === 'labyrinth' ? 'border-[#10b981]/40 shadow-[0_0_20px_rgba(16,185,129,0.08)]' : 'border-white/5'} rounded-3xl p-8 relative overflow-hidden group cursor-pointer transition-all duration-300`}
            >
              <div className="absolute bottom-0 right-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-[70px] opacity-0 group-hover:opacity-100 transition-opacity duration-500"></div>
              
              <div className="h-[210px] flex items-end justify-center gap-3.5 mb-8">
                {[40, 75, 55, 95, 65, 35].map((h, i) => (
                  <div key={i} className="w-7 relative group" style={{ height: `${h}%` }}>
                    <motion.div 
                      initial={{ height: "40%" }}
                      animate={{ height: hoveredCard === 'labyrinth' ? `${h}%` : "50%" }}
                      transition={{ type: "spring", stiffness: 180, damping: 15, delay: i * 0.04 }}
                      className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-zinc-900 via-zinc-850 to-zinc-700/60 border border-white/10 rounded-t-lg shadow-lg"
                    >
                      {/* Top Cap */}
                      <div className="absolute -top-1 left-0 w-full h-2 bg-gradient-to-r from-zinc-600 to-zinc-500 rounded-full scale-y-50 shadow-inner"></div>
                      {/* Active indicator dot */}
                      {i === 3 && (
                        <div className="absolute top-2 left-1/2 -translate-x-1/2 w-1.5 h-1.5 bg-[#10b981] rounded-full shadow-lg animate-pulse"></div>
                      )}
                    </motion.div>
                  </div>
                ))}
              </div>
              
              <div className="text-center mt-auto">
                <h4 className="text-sm font-semibold text-white mb-1.5 flex items-center justify-center gap-1.5">
                  Liquidity Labyrinth <span className="w-2 h-2 rounded-full bg-[#10b981]"></span>
                </h4>
                <p className="text-xs text-zinc-500 max-w-sm mx-auto">Explore high-dimension cluster datasets mapped instantly into interactive, touchable structures.</p>
              </div>
            </motion.div>

            {/* Bottom Left Card: Dual Financial Growth Trackers */}
            <motion.div 
              onMouseEnter={() => setHoveredCard('palette')}
              onMouseLeave={() => setHoveredCard(null)}
              whileHover={{ y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`bg-[#0a0a0a] border ${hoveredCard === 'palette' ? 'border-[#08b5cf]/30 shadow-[0_0_20px_rgba(8,181,207,0.05)]' : 'border-white/5'} rounded-3xl p-8 flex flex-col justify-between group cursor-pointer transition-all duration-300`}
            >
              <div className="flex justify-between items-start mb-12">
                <div className="bg-black/40 border border-white/5 rounded-2xl p-4 flex-1 mr-4 hover:border-cyan-500/20 transition-all duration-300">
                  <div className="flex items-center gap-2 text-xs font-bold text-zinc-500 mb-2 uppercase tracking-wider">
                    <span className="w-1.5 h-3 bg-cyan-400 rounded-full"></span>
                    Internal Grow
                  </div>
                  <p className="text-[10px] font-black text-zinc-400 mb-1">METRIC GROWTH</p>
                  <h4 className="text-4xl font-extrabold text-white mb-1 tracking-tight">19.2<span className="text-sm text-cyan-400 ml-1">%</span></h4>
                  <p className="text-[10px] font-mono text-zinc-500">$2.7m ARR</p>
                </div>

                <div className="bg-black/40 border border-white/5 rounded-2xl p-4 flex-1 hover:border-emerald-500/20 transition-all duration-300">
                  <div className="flex items-center gap-2 text-xs font-bold text-zinc-500 mb-2 uppercase tracking-wider">
                    <span className="w-1.5 h-3 bg-emerald-400 rounded-full"></span>
                    SaaS Engine
                  </div>
                  <p className="text-[10px] font-black text-zinc-400 mb-1">EXTERNAL GROWTH</p>
                  <h4 className="text-4xl font-extrabold text-white mb-1 tracking-tight">24.5<span className="text-sm text-emerald-400 ml-1">%</span></h4>
                  <p className="text-[10px] font-mono text-zinc-500">$3.2m ARR</p>
                </div>
              </div>
              
              <div className="mt-4">
                <h4 className="text-sm font-semibold text-white mb-1.5">Your Palette Financial Opportunities</h4>
                <p className="text-xs text-zinc-500 leading-relaxed">Watch your integrated data pipelines automatically identify margin gaps and trigger proactive business suggestions.</p>
              </div>
            </motion.div>

            {/* Bottom Right Card: Opportunities Histogram */}
            <motion.div 
              onMouseEnter={() => setHoveredCard('space')}
              onMouseLeave={() => setHoveredCard(null)}
              whileHover={{ y: -4 }}
              transition={{ type: "spring", stiffness: 300, damping: 25 }}
              className={`bg-[#0a0a0a] border ${hoveredCard === 'space' ? 'border-purple-500/30 shadow-[0_0_20px_rgba(168,85,247,0.05)]' : 'border-white/5'} rounded-3xl p-8 group cursor-pointer transition-all duration-300`}
            >
               <div className="text-center mb-8">
                 <h4 className="text-sm font-semibold text-white mb-1.5">Data Space . Opportunities</h4>
                 <p className="text-xs text-zinc-500">Every color represents a chance to optimize your cluster distribution.</p>
               </div>
               
               <div className="h-32 flex items-end justify-between px-2">
                 {(Object.keys(chartsData) as Array<keyof typeof chartsData>).map((key, i) => {
                   const val = chartsData[key];
                   return (
                     <div key={key} className="flex flex-col items-center gap-2 flex-1">
                       <span className="text-[9px] font-mono text-zinc-500">{val}</span>
                       <div className="w-full max-w-[28px] bg-zinc-900 border border-white/5 rounded-t-sm relative h-20 flex items-end">
                         <motion.div 
                           initial={{ height: "20%" }}
                           animate={{ height: hoveredCard === 'space' ? `${val * 2}%` : `${val * 1.3}%` }}
                           transition={{ type: "spring", stiffness: 150, damping: 12, delay: i * 0.03 }}
                           className="w-full bg-gradient-to-t from-purple-500/20 to-purple-400/80 rounded-t-sm"
                         />
                       </div>
                       <span className="text-[8px] font-mono text-zinc-600 uppercase">{key}</span>
                     </div>
                   );
                 })}
               </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Helpful FAQ Section for Richness */}
      <section id="faq" className="py-24 border-t border-white/5 relative z-20">
        <div className="max-w-[800px] mx-auto px-6">
          <div className="text-center mb-16">
            <HelpCircle className="w-8 h-8 text-[#08b5cf] mx-auto mb-3" />
            <h3 className="text-3xl font-black text-white tracking-tight">Frequently Asked Questions</h3>
            <p className="text-xs text-zinc-500 mt-1">Get precise answers to our security and algorithm mechanisms</p>
          </div>

          <div className="space-y-3">
            {faqs.map((faq, index) => {
              const isOpen = openFaq === index;
              return (
                <div 
                  key={index}
                  onClick={() => setOpenFaq(isOpen ? null : index)}
                  className="bg-[#0a0a0a] border border-white/5 rounded-2xl p-5 hover:border-white/10 transition-all duration-300 cursor-pointer select-none"
                >
                  <div className="flex items-center justify-between gap-4">
                    <h4 className="text-sm font-semibold text-white">{faq.question}</h4>
                    <motion.div
                      animate={{ rotate: isOpen ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                      className="text-zinc-500 hover:text-white"
                    >
                      <ChevronDown className="w-4 h-4" />
                    </motion.div>
                  </div>
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0, marginTop: 0 }}
                        animate={{ height: "auto", opacity: 1, marginTop: 12 }}
                        exit={{ height: 0, opacity: 0, marginTop: 0 }}
                        transition={{ duration: 0.25, ease: "easeInOut" }}
                        className="overflow-hidden"
                      >
                        <p className="text-xs text-zinc-400 leading-relaxed border-t border-white/5 pt-3">
                          {faq.answer}
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      </section>
      
      {/* Footer */}
      <footer id="footer-section" className="border-t border-white/10 py-12 px-6 relative z-20 bg-[#050505]">
        <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
           <div className="flex gap-6 text-xs font-semibold text-zinc-500">
             <a href="#" className="hover:text-white transition-colors">Support Portal</a>
             <a href="#" className="hover:text-white transition-colors">System Register</a>
             <a href="#" className="hover:text-white transition-colors">Privacy Shield</a>
           </div>
           
           <p className="text-xs text-zinc-600 flex items-center gap-1 font-mono">
             Made with <Heart className="w-3 h-3 text-red-500 fill-red-500" /> by Data-Berge Operating Systems . SOC2 Certified
           </p>
           
           <div className="flex gap-2">
             <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-xs text-zinc-400 hover:text-white hover:bg-white/10 cursor-pointer transition-colors font-mono">X</div>
             <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-xs text-zinc-400 hover:text-white hover:bg-white/10 cursor-pointer transition-colors font-mono font-bold">in</div>
           </div>
        </div>
      </footer>
    </div>
  );
}
