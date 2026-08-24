import { useState, useEffect, useRef } from "react";
import {
  ArrowRight, Database, GitBranch, FileText, ChevronDown,
  Menu, X, ExternalLink, TrendingUp, Search, Layers
} from "lucide-react";

// ─── Iceberg SVG ─────────────────────────────────────────────────────────────
function IcebergHero() {
  return (
    <div className="relative w-full h-full flex items-center justify-center">
      <svg
        viewBox="0 0 520 700"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full max-w-[480px] drop-shadow-2xl"
        aria-label="Iceberg data metaphor illustration"
      >
        <defs>
          <linearGradient id="skyBg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#172033" />
            <stop offset="100%" stopColor="#1C2E44" />
          </linearGradient>
          <linearGradient id="seaGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#08B5CF" stopOpacity="0.18" />
            <stop offset="30%" stopColor="#196067" stopOpacity="0.55" />
            <stop offset="70%" stopColor="#134B50" stopOpacity="0.82" />
            <stop offset="100%" stopColor="#0B2C2F" stopOpacity="0.98" />
          </linearGradient>
          <linearGradient id="iceTopGrad" x1="0.3" y1="0" x2="0.8" y2="1">
            <stop offset="0%" stopColor="#EEF5F6" />
            <stop offset="45%" stopColor="#C8DEDE" />
            <stop offset="100%" stopColor="#96BABE" />
          </linearGradient>
          <linearGradient id="iceDeepGrad" x1="0.1" y1="0" x2="0.9" y2="1">
            <stop offset="0%" stopColor="#49878D" stopOpacity="0.95" />
            <stop offset="30%" stopColor="#1B6971" stopOpacity="0.92" />
            <stop offset="65%" stopColor="#134B50" stopOpacity="0.88" />
            <stop offset="100%" stopColor="#0B2C2F" stopOpacity="0.96" />
          </linearGradient>
          <linearGradient id="glowLine" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#08B5CF" stopOpacity="0" />
            <stop offset="30%" stopColor="#08B5CF" stopOpacity="0.8" />
            <stop offset="70%" stopColor="#08B5CF" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#08B5CF" stopOpacity="0" />
          </linearGradient>
          <filter id="iceShadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="8" stdDeviation="16" floodColor="#08B5CF" floodOpacity="0.18" />
          </filter>
          <filter id="deepGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
          <clipPath id="belowWaterClip">
            <rect x="0" y="270" width="520" height="430" />
          </clipPath>
        </defs>

        {/* Ocean background */}
        <rect y="270" width="520" height="430" fill="url(#seaGrad)" />

        {/* ── Below-water iceberg mass ── */}
        <path
          d="M168,270 L352,270 L418,342 L462,430 L455,512 L408,580 L338,622 L260,634 L182,618 L122,570 L96,490 L100,405 L128,342 Z"
          fill="url(#iceDeepGrad)"
          filter="url(#iceShadow)"
        />

        {/* Internal facet structure below water */}
        <path d="M168,270 L200,360 L260,310 L310,360 L352,270" fill="white" fillOpacity="0.04" />
        <path d="M200,360 L260,310 L310,360 L290,440 L230,440 Z" fill="white" fillOpacity="0.03" />

        {/* Depth horizon lines */}
        <path d="M115,360 Q260,348 405,360" stroke="#08B5CF" strokeWidth="0.6" strokeDasharray="4 6" opacity="0.35" />
        <path d="M100,450 Q260,438 420,450" stroke="#08B5CF" strokeWidth="0.6" strokeDasharray="4 6" opacity="0.25" />
        <path d="M97,540 Q260,528 423,540" stroke="#08A9C2" strokeWidth="0.6" strokeDasharray="4 6" opacity="0.18" />

        {/* Depth labels */}
        <text x="260" y="334" textAnchor="middle" fill="#08B5CF" fontSize="8.5" fontFamily="'JetBrains Mono', monospace" opacity="0.75" letterSpacing="1.5">— SURFACE PATTERNS —</text>
        <text x="260" y="416" textAnchor="middle" fill="#49878D" fontSize="8.5" fontFamily="'JetBrains Mono', monospace" opacity="0.65" letterSpacing="1.5">— TABLE RELATIONSHIPS —</text>
        <text x="260" y="500" textAnchor="middle" fill="#1B6971" fontSize="8.5" fontFamily="'JetBrains Mono', monospace" opacity="0.55" letterSpacing="1.5">— HIDDEN CORRELATIONS —</text>
        <text x="260" y="580" textAnchor="middle" fill="#134B50" fontSize="8.5" fontFamily="'JetBrains Mono', monospace" opacity="0.45" letterSpacing="1.5">— PREDICTIVE INSIGHTS —</text>

        {/* Data-node dots + connector lines */}
        <circle cx="170" cy="352" r="3.5" fill="#08B5CF" opacity="0.85" />
        <circle cx="350" cy="352" r="3.5" fill="#08B5CF" opacity="0.85" />
        <circle cx="260" cy="400" r="5" fill="#08B5CF" opacity="0.7" />
        <line x1="170" y1="352" x2="260" y2="400" stroke="#08B5CF" strokeWidth="0.8" opacity="0.4" />
        <line x1="350" y1="352" x2="260" y2="400" stroke="#08B5CF" strokeWidth="0.8" opacity="0.4" />

        <circle cx="140" cy="455" r="2.5" fill="#49878D" opacity="0.7" />
        <circle cx="380" cy="455" r="2.5" fill="#49878D" opacity="0.7" />
        <circle cx="220" cy="472" r="2" fill="#49878D" opacity="0.6" />
        <circle cx="300" cy="478" r="2" fill="#49878D" opacity="0.6" />
        <line x1="140" y1="455" x2="220" y2="472" stroke="#49878D" strokeWidth="0.6" opacity="0.3" />
        <line x1="380" y1="455" x2="300" y2="478" stroke="#49878D" strokeWidth="0.6" opacity="0.3" />
        <line x1="220" y1="472" x2="300" y2="478" stroke="#49878D" strokeWidth="0.6" opacity="0.3" />

        <circle cx="180" cy="545" r="2" fill="#1B6971" opacity="0.5" />
        <circle cx="340" cy="545" r="2" fill="#1B6971" opacity="0.5" />
        <circle cx="260" cy="560" r="3" fill="#1B6971" opacity="0.4" />
        <line x1="180" y1="545" x2="260" y2="560" stroke="#1B6971" strokeWidth="0.5" opacity="0.25" />
        <line x1="340" y1="545" x2="260" y2="560" stroke="#1B6971" strokeWidth="0.5" opacity="0.25" />

        {/* ── Waterline ── */}
        <rect x="0" y="268" width="520" height="4" fill="url(#glowLine)" opacity="0.6" />
        <path
          d="M0,270 Q65,262 130,270 Q195,278 260,270 Q325,262 390,270 Q455,278 520,270"
          stroke="#08B5CF"
          strokeWidth="2"
          fill="none"
          opacity="0.9"
        />
        <path
          d="M0,275 Q80,269 160,275 Q240,281 320,275 Q400,269 480,275 Q500,273 520,275"
          stroke="#08B5CF"
          strokeWidth="0.8"
          fill="none"
          opacity="0.4"
        />

        {/* Waterline label */}
        <text x="28" y="262" fill="#08B5CF" fontSize="7.5" fontFamily="'JetBrains Mono', monospace" opacity="0.6" letterSpacing="1">WATERLINE</text>
        <line x1="28" y1="264" x2="90" y2="264" stroke="#08B5CF" strokeWidth="0.5" opacity="0.4" />

        {/* ── Above-water iceberg tip ── */}
        <path
          d="M260,62
             L312,132 L338,174 L342,216
             L330,252 L304,268
             L260,272
             L216,268 L190,252
             L178,216 L182,174
             L208,132 Z"
          fill="url(#iceTopGrad)"
          filter="url(#iceShadow)"
        />

        {/* Tip facets */}
        <path d="M260,62 L312,132 L278,178 Z" fill="white" fillOpacity="0.28" />
        <path d="M260,62 L208,132 L244,175 Z" fill="white" fillOpacity="0.15" />
        <path d="M278,178 L244,175 L260,220 Z" fill="white" fillOpacity="0.12" />
        <path d="M312,132 L338,174 L304,195 Z" fill="white" fillOpacity="0.1" />

        {/* Tip outline for crisp edge */}
        <path
          d="M260,62 L312,132 L338,174 L342,216 L330,252 L304,268 L260,272 L216,268 L190,252 L178,216 L182,174 L208,132 Z"
          stroke="#B8D1D3"
          strokeWidth="0.8"
          fill="none"
          opacity="0.5"
        />

        {/* Shimmer highlight on tip */}
        <ellipse cx="248" cy="120" rx="20" ry="38" fill="white" fillOpacity="0.12" transform="rotate(-15 248 120)" />
      </svg>

      {/* ── Floating Data Cards ── */}
      <div className="absolute top-[12%] left-[2%] bg-white rounded-2xl px-4 py-3.5 shadow-2xl shadow-black/25 border border-[#E2E8F0] w-44">
        <div className="text-[9px] font-semibold text-[#08B5CF] uppercase tracking-widest mb-1">Data Pulse</div>
        <div className="text-2xl font-bold text-[#172033]" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>5 fields</div>
        <div className="text-[11px] text-[#64748B] mt-0.5">Profile ready for exploration</div>
        <div className="mt-2.5 flex items-center gap-1.5">
          <div className="text-[9px] text-[#08B5CF] font-mono">ready-to-use</div>
          <div className="flex-1 h-px bg-gradient-to-r from-[#08B5CF]/50 to-transparent" />
        </div>
      </div>

      <div className="absolute bottom-[24%] right-[1%] bg-[#172033] rounded-2xl px-4 py-3.5 shadow-2xl border border-white/10 w-44">
        <div className="text-[9px] font-semibold text-[#08B5CF] uppercase tracking-widest mb-1">Model</div>
        <div className="text-2xl font-bold text-white" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>3 tables</div>
        <div className="text-[11px] text-white/50 mt-0.5">2 relationships discovered</div>
        <div className="mt-2 grid grid-cols-3 gap-1">
          {["Customer", "Order", "Product"].map(t => (
            <div key={t} className="h-1 rounded-full bg-[#08B5CF]/40" />
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Depth Meter ──────────────────────────────────────────────────────────────
function DepthMeter({ layers }: { layers: { label: string; pct: number; color: string }[] }) {
  return (
    <div className="flex flex-col gap-2.5">
      {layers.map(({ label, pct, color }) => (
        <div key={label}>
          <div className="flex justify-between items-center mb-1">
            <span className="text-[11px] font-mono text-white/50 uppercase tracking-wider">{label}</span>
            <span className="text-[11px] font-mono" style={{ color }}>{pct}%</span>
          </div>
          <div className="h-1 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-700"
              style={{ width: `${pct}%`, backgroundColor: color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeStep, setActiveStep] = useState<number | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 48);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className="min-h-screen overflow-x-hidden"
      style={{ fontFamily: "'DM Sans', sans-serif", backgroundColor: "#F8FAFC", color: "#172033" }}
    >
      {/* ── NAV ── */}
      <nav
        className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
          scrolled
            ? "bg-[#172033]/96 backdrop-blur-xl shadow-xl shadow-black/20 border-b border-white/5"
            : "bg-transparent"
        }`}
      >
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-[#08B5CF] flex items-center justify-center shadow-lg shadow-[#08B5CF]/30 group-hover:shadow-[#08B5CF]/50 transition-shadow">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                <path d="M10 2L16 8L13 11L16 14L10 20L4 14L7 11L4 8Z" fill="white" />
                <circle cx="10" cy="11" r="2" fill="white" fillOpacity="0.6" />
              </svg>
            </div>
            <span className="font-semibold text-white text-[17px] tracking-tight">
              Data<span className="text-[#08B5CF]">berge</span>
            </span>
          </a>

          {/* Desktop links */}
          <div className="hidden md:flex items-center gap-8">
            {["Product", "Sources", "Results"].map(item => (
              <a
                key={item}
                href="#"
                className="text-[13.5px] text-white/60 hover:text-white transition-colors duration-200"
              >
                {item}
              </a>
            ))}
          </div>

          <div className="hidden md:flex items-center gap-3">
            <a href="#" className="text-[13.5px] text-white/60 hover:text-white transition-colors">Log in</a>
            <button className="px-4 py-2 rounded-lg bg-[#08B5CF] hover:bg-[#08A9C2] text-white text-[13.5px] font-semibold transition-all hover:shadow-lg hover:shadow-[#08B5CF]/30">
              Create account
            </button>
          </div>

          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="md:hidden text-white p-1"
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden bg-[#172033]/98 border-t border-white/10 px-6 py-4 flex flex-col gap-4">
            {["Product", "Sources", "Results"].map(item => (
              <a key={item} href="#" className="text-white/70 hover:text-white transition-colors">
                {item}
              </a>
            ))}
            <div className="flex gap-3 pt-2">
              <a href="#" className="text-white/60 hover:text-white text-sm transition-colors">Log in</a>
              <button className="px-4 py-2 rounded-lg bg-[#08B5CF] text-white text-sm font-semibold">
                Create account
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* ── HERO ── */}
      <section className="relative min-h-screen bg-[#172033] flex items-center overflow-hidden pt-16">
        {/* Background texture */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute inset-0 bg-gradient-to-br from-[#172033] via-[#1C2D44] to-[#0F1E30]" />
          <div
            className="absolute inset-0 opacity-40"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.07) 1px, transparent 0)",
              backgroundSize: "36px 36px",
            }}
          />
          {/* Depth glow blobs */}
          <div className="absolute top-1/4 right-1/3 w-[500px] h-[500px] bg-[#08B5CF]/4 rounded-full blur-[120px]" />
          <div className="absolute bottom-1/3 left-1/4 w-[400px] h-[400px] bg-[#1B6971]/8 rounded-full blur-[100px]" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 xl:gap-20 items-center py-20 lg:py-28">
          {/* Left – text */}
          <div>
            {/* Badge */}
            <div className="inline-flex items-center gap-2.5 px-3.5 py-1.5 rounded-full border border-[#08B5CF]/25 bg-[#08B5CF]/8 mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-[#08B5CF] animate-pulse" />
              <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.14em]">
                Analysis Workspace · Real-World Data
              </span>
            </div>

            <h1
              className="text-[2.8rem] sm:text-[3.4rem] lg:text-[3.8rem] font-bold text-white leading-[1.05] mb-6 tracking-tight"
              style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
            >
              The tip is
              <br />
              <span
                className="relative inline-block"
                style={{
                  background: "linear-gradient(135deg, #08B5CF 0%, #49878D 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                  backgroundClip: "text",
                }}
              >
                just the
              </span>
              <br />
              beginning.
            </h1>

            <p className="text-[1.05rem] text-white/55 mb-10 leading-[1.75] max-w-[420px]">
              Like an iceberg, your data hides thousands of stories beneath the surface.
              Upload workbooks, map relationships, and let Databerge surface what you&apos;ve been missing.
            </p>

            <div className="flex flex-wrap gap-3.5 mb-12">
              <button className="group flex items-center gap-2 px-6 py-3 rounded-xl bg-[#08B5CF] hover:bg-[#08A9C2] text-white font-semibold text-[15px] transition-all duration-200 shadow-lg shadow-[#08B5CF]/20 hover:shadow-[#08B5CF]/40 hover:-translate-y-0.5">
                Dive Deeper
                <ArrowRight size={17} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
              <button className="flex items-center gap-2 px-6 py-3 rounded-xl border border-white/15 text-white/70 hover:border-white/30 hover:text-white text-[15px] transition-all duration-200">
                How It Works
                <ChevronDown size={17} />
              </button>
            </div>

            <div className="flex items-center gap-2.5 flex-wrap">
              <span className="text-white/35 text-sm font-mono">Compatible with</span>
              {["Excel", "CSV", "OpenDOSM", "DuckDB"].map(f => (
                <span
                  key={f}
                  className="px-2.5 py-1 rounded-md bg-white/5 border border-white/10 text-white/50 text-[11.5px] font-mono hover:border-[#08B5CF]/30 hover:text-white/70 transition-colors cursor-default"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>

          {/* Right – Iceberg */}
          <div className="hidden lg:block h-[580px]">
            <IcebergHero />
          </div>
        </div>

        {/* Wave break to next section */}
        <div className="absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 72" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
            <path
              d="M0,36 Q180,72 360,36 Q540,0 720,36 Q900,72 1080,36 Q1260,0 1440,36 L1440,72 L0,72 Z"
              fill="#F8FAFC"
            />
          </svg>
        </div>
      </section>

      {/* ── WORKFLOW FEATURES ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-16">
            <div>
              <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-3 block">
                Workflow
              </span>
              <h2
                className="text-[2.4rem] font-bold text-[#172033] leading-tight max-w-sm"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                Experience that grows with your data.
              </h2>
            </div>
            <p className="text-[#64748B] leading-relaxed max-w-sm text-[15.5px]">
              Every dataset is an iceberg. Databerge gives you the tools to map what&apos;s visible —
              and reveal everything that lies beneath.
            </p>
          </div>

          <div className="grid md:grid-cols-3 gap-5">
            {[
              {
                icon: FileText,
                label: "Workbook profiling",
                desc: "Read Excel and CSV files, detect tables, infer types, and surface full column coverage before analysis begins.",
                accent: "#08B5CF",
              },
              {
                icon: GitBranch,
                label: "Relationship modeling",
                desc: "Confirm joins, keys, and table relationships before the workspace starts answering your questions.",
                accent: "#1B6971",
              },
              {
                icon: Database,
                label: "Analyst context",
                desc: "Carry profile metadata, descriptions, and model context into Explorer and Executive Reports seamlessly.",
                accent: "#134B50",
              },
            ].map(({ icon: Icon, label, desc, accent }) => (
              <div
                key={label}
                className="group relative p-7 rounded-2xl bg-white border border-[#E2E8F0] hover:border-transparent hover:shadow-2xl hover:shadow-[#08B5CF]/8 transition-all duration-300 cursor-pointer overflow-hidden"
              >
                <div
                  className="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 rounded-2xl"
                  style={{
                    background: `linear-gradient(135deg, ${accent}08 0%, transparent 60%)`,
                  }}
                />
                <div
                  className="relative w-11 h-11 rounded-xl flex items-center justify-center mb-5 transition-colors duration-300"
                  style={{ backgroundColor: `${accent}15` }}
                >
                  <Icon size={19} style={{ color: accent }} />
                </div>
                <div className="relative font-semibold text-[#172033] text-[15.5px] mb-2.5">{label}</div>
                <div className="relative text-[#64748B] text-sm leading-relaxed">{desc}</div>
                <div
                  className="absolute bottom-0 left-0 right-0 h-0.5 scale-x-0 group-hover:scale-x-100 transition-transform duration-300 origin-left"
                  style={{ background: `linear-gradient(to right, ${accent}, transparent)` }}
                />
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DEPTH / STATS ── */}
      <section className="relative py-24 lg:py-32 bg-[#172033] overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.04) 1px, transparent 0)",
              backgroundSize: "28px 28px",
            }}
          />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[300px] bg-[#08B5CF]/4 rounded-full blur-[80px]" />
          <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-[#08B5CF]/20 to-transparent" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-16 items-center">
          {/* Left */}
          <div>
            <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
              Coverage
            </span>
            <div
              className="text-[5rem] font-bold leading-none mb-2"
              style={{
                fontFamily: "'Bricolage Grotesque', sans-serif",
                background: "linear-gradient(135deg, #08B5CF 0%, #49878D 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                backgroundClip: "text",
              }}
            >
              100%
            </div>
            <div className="text-sm font-semibold text-[#08B5CF] mb-7 tracking-wide">
              Description coverage target
            </div>

            <p className="text-white/55 leading-[1.8] mb-10 text-[15.5px] max-w-sm">
              Move from workbook to workspace without losing context. Every field, every relationship,
              every insight — preserved and ready.
            </p>

            <div className="flex items-center gap-4">
              <div className="w-11 h-11 rounded-xl bg-white/90 flex items-center justify-center shadow-lg">
                <FileText size={18} className="text-[#172033]" />
              </div>
              <div className="flex items-center gap-2 flex-1">
                <div className="h-px flex-1 bg-gradient-to-r from-white/20 to-[#08B5CF]/60" />
                <div className="w-2 h-2 rounded-full bg-[#08B5CF]" />
                <div className="h-px flex-1 bg-gradient-to-r from-[#08B5CF]/60 to-white/20" />
              </div>
              <div className="w-11 h-11 rounded-xl bg-[#08B5CF]/15 border border-[#08B5CF]/30 flex items-center justify-center">
                <Database size={18} className="text-[#08B5CF]" />
              </div>
            </div>
            <p className="text-center text-[11px] text-white/35 mt-2 font-mono tracking-wider uppercase">
              Workbook → Workspace
            </p>
          </div>

          {/* Right – depth bars + chart */}
          <div className="flex flex-col gap-6">
            {/* Profile coverage sparkline */}
            <div className="rounded-2xl bg-white/5 border border-white/8 p-6">
              <div className="flex justify-between items-center mb-4">
                <span className="text-xs text-[#08B5CF] font-mono uppercase tracking-widest">
                  Profile Coverage
                </span>
                <span className="text-xs text-[#08B5CF] font-mono">↑ 94%</span>
              </div>
              <svg viewBox="0 0 360 80" className="w-full" aria-label="Profile coverage chart">
                <defs>
                  <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#08B5CF" stopOpacity="0.25" />
                    <stop offset="100%" stopColor="#08B5CF" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="chartLine" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#08B5CF" stopOpacity="0.3" />
                    <stop offset="100%" stopColor="#08B5CF" />
                  </linearGradient>
                </defs>
                <path
                  d="M0,72 Q40,68 80,58 Q120,48 160,35 Q200,22 240,14 Q280,8 320,4 Q340,2 360,1"
                  stroke="url(#chartLine)"
                  strokeWidth="2.5"
                  fill="none"
                />
                <path
                  d="M0,72 Q40,68 80,58 Q120,48 160,35 Q200,22 240,14 Q280,8 320,4 Q340,2 360,1 L360,80 L0,80 Z"
                  fill="url(#chartFill)"
                />
                <circle cx="360" cy="1" r="4" fill="#08B5CF" />
                <circle cx="360" cy="1" r="8" fill="#08B5CF" fillOpacity="0.2" />
              </svg>
            </div>

            {/* Depth meter */}
            <div className="rounded-2xl bg-white/5 border border-white/8 p-6">
              <div className="text-xs text-[#08B5CF] font-mono uppercase tracking-widest mb-5">
                Data Depth Layers
              </div>
              <DepthMeter
                layers={[
                  { label: "Surface — Raw fields", pct: 100, color: "#08B5CF" },
                  { label: "Mid — Relationships", pct: 82, color: "#49878D" },
                  { label: "Deep — Correlations", pct: 64, color: "#1B6971" },
                  { label: "Core — Predictions", pct: 41, color: "#134B50" },
                ]}
              />
            </div>
          </div>
        </div>

        {/* Stats row */}
        <div className="relative max-w-7xl mx-auto px-6 mt-20 pt-12 border-t border-white/8">
          <div className="grid grid-cols-3 gap-8">
            {[
              { stat: "100%", label: "Description coverage target", color: "#08B5CF" },
              { stat: "180K", label: "Rows profiled in local workflows", color: "#49878D" },
              { stat: "10+", label: "Analysis surfaces planned", color: "#96BABE" },
            ].map(({ stat, label, color }) => (
              <div key={stat} className="text-center group">
                <div
                  className="text-[2.8rem] sm:text-[3.5rem] font-bold mb-1.5 transition-colors"
                  style={{
                    fontFamily: "'Bricolage Grotesque', sans-serif",
                    color,
                  }}
                >
                  {stat}
                </div>
                <div className="text-white/45 text-sm">{label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Divider wave */}
        <div className="absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
            <path
              d="M0,32 Q360,64 720,32 Q1080,0 1440,32 L1440,64 L0,64 Z"
              fill="#F8FAFC"
            />
          </svg>
        </div>
      </section>

      {/* ── DATA SOURCES ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <div className="max-w-7xl mx-auto px-6">
          <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
            Bring Data In
          </span>
          <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-8 mb-12">
            <h2
              className="text-[2.4rem] font-bold text-[#172033] leading-tight max-w-md"
              style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
            >
              Start with the data you have.
            </h2>
            <p className="text-[#64748B] max-w-sm text-[15px] leading-relaxed">
              Two paths in, one unified model out. Every source gets the same depth of profiling.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            {/* Upload */}
            <div className="group relative p-8 rounded-2xl bg-white border border-[#E2E8F0] hover:border-[#08B5CF]/25 hover:shadow-xl hover:shadow-[#08B5CF]/6 transition-all duration-300 cursor-pointer overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-[#E8F0F1]/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-2xl" />
              <div className="relative flex items-start justify-between mb-7">
                <div>
                  <div
                    className="text-2xl font-bold text-[#172033] mb-1"
                    style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
                  >
                    Upload Dataset
                  </div>
                  <div className="text-sm text-[#64748B]">Drop files and get a profile instantly</div>
                </div>
                <div className="w-10 h-10 rounded-xl bg-[#F8FAFC] border border-[#E2E8F0] flex items-center justify-center group-hover:bg-[#08B5CF] group-hover:border-[#08B5CF] transition-all duration-300">
                  <ArrowRight
                    size={16}
                    className="text-[#64748B] group-hover:text-white transition-colors duration-300"
                  />
                </div>
              </div>
              <div className="relative flex gap-2">
                {["CSV", "XLSX", "XLS"].map(f => (
                  <span
                    key={f}
                    className="px-3 py-1.5 rounded-lg bg-[#F8FAFC] border border-[#E2E8F0] text-[#64748B] text-xs font-mono group-hover:border-[#08B5CF]/20 transition-colors"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>

            {/* DOSM */}
            <div className="group relative p-8 rounded-2xl bg-[#08B5CF] hover:bg-[#08A9C2] transition-all duration-300 cursor-pointer overflow-hidden shadow-lg shadow-[#08B5CF]/20 hover:shadow-[#08B5CF]/35">
              <div className="absolute top-0 right-0 w-64 h-64 bg-white/8 rounded-full -translate-y-1/2 translate-x-1/2 group-hover:scale-110 transition-transform duration-500" />
              <div className="relative flex items-start justify-between mb-7">
                <div>
                  <div
                    className="text-2xl font-bold text-white mb-1"
                    style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
                  >
                    Connect DOSM
                  </div>
                  <div className="text-sm text-white/70">Open data catalogue</div>
                </div>
                <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center">
                  <ExternalLink size={16} className="text-white" />
                </div>
              </div>
              <div className="relative text-white/80 text-[14.5px] leading-relaxed max-w-xs">
                Access Malaysia&apos;s national statistics and open data platform — directly wired into your workspace.
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── MODEL-FIRST FLOW (dark) ── */}
      <section className="relative py-24 lg:py-32 bg-[#0F1E30] overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.035) 1px, transparent 0)",
              backgroundSize: "28px 28px",
            }}
          />
        </div>

        <div className="relative max-w-7xl mx-auto px-6">
          <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
            Model-First Flow
          </span>
          <h2
            className="text-[2.4rem] font-bold text-white mb-4 max-w-2xl leading-tight"
            style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
          >
            Move from raw files to useful answers — without guessing the dataset shape.
          </h2>
          <p className="text-white/45 mb-16 max-w-xl text-[15px] leading-relaxed">
            Three steps. The model is confirmed before any analysis begins — so every answer is grounded in reality.
          </p>

          <div className="grid md:grid-cols-3 gap-5">
            {[
              {
                num: "01",
                title: "Upload or connect",
                desc: "Bring in CSV and Excel files, or connect OpenDOSM data from the setup page.",
                icon: FileText,
              },
              {
                num: "02",
                title: "Review the model",
                desc: "Preview rows, correct datatypes, and confirm table relationships with a clear visual editor.",
                icon: Search,
              },
              {
                num: "03",
                title: "Analyze with context",
                desc: "Use Data Pulse, Explorer, and Executive Report — with the confirmed profile already in place.",
                icon: TrendingUp,
              },
            ].map(({ num, title, desc, icon: Icon }, i) => (
              <div
                key={num}
                className="group relative p-7 rounded-2xl border border-white/8 bg-white/4 hover:bg-white/7 hover:border-[#08B5CF]/25 transition-all duration-300 cursor-pointer"
                onMouseEnter={() => setActiveStep(i)}
                onMouseLeave={() => setActiveStep(null)}
              >
                <div
                  className="text-[4.5rem] font-bold leading-none mb-5 transition-colors duration-300"
                  style={{
                    fontFamily: "'Bricolage Grotesque', sans-serif",
                    color: activeStep === i ? "rgba(8,181,207,0.25)" : "rgba(255,255,255,0.06)",
                  }}
                >
                  {num}
                </div>
                <div className="w-9 h-9 rounded-lg bg-white/8 flex items-center justify-center mb-4 group-hover:bg-[#08B5CF]/15 transition-colors duration-300">
                  <Icon size={16} className="text-white/50 group-hover:text-[#08B5CF] transition-colors duration-300" />
                </div>
                <div className="font-semibold text-white text-[15.5px] mb-2">{title}</div>
                <div className="text-white/45 text-sm leading-relaxed">{desc}</div>
                <div className="mt-6 h-px bg-gradient-to-r from-[#08B5CF]/0 via-[#08B5CF]/35 to-[#08B5CF]/0 scale-x-0 group-hover:scale-x-100 transition-transform duration-500 origin-left" />
              </div>
            ))}
          </div>
        </div>

        <div className="absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-full">
            <path d="M0,32 Q360,0 720,32 Q1080,64 1440,32 L1440,64 L0,64 Z" fill="#F8FAFC" />
          </svg>
        </div>
      </section>

      {/* ── WHY IT MATTERS ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
            Why It Matters
          </span>
          <h2
            className="text-[2.4rem] font-bold text-[#172033] mb-5 max-w-2xl mx-auto leading-tight"
            style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
          >
            Built for messy business data,
            <br />
            not perfect demo tables.
          </h2>
          <p className="text-[#64748B] mb-16 max-w-xl mx-auto text-[15.5px] leading-relaxed">
            Databerge keeps table structure, descriptions, relationships, and analyst context
            visible before chat or reports start using the dataset.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-8 max-w-2xl mx-auto">
            {[
              { stat: "100%", label: "Description coverage target" },
              { stat: "180K", label: "Rows profiled in local workflows" },
              { stat: "10+", label: "Analysis surfaces planned" },
            ].map(({ stat, label }) => (
              <div
                key={stat}
                className="group p-6 rounded-2xl bg-white border border-[#E2E8F0] hover:border-[#08B5CF]/30 hover:shadow-lg hover:shadow-[#08B5CF]/5 transition-all"
              >
                <div
                  className="text-[2.8rem] font-bold text-[#172033] mb-1.5 group-hover:text-[#08B5CF] transition-colors duration-300"
                  style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
                >
                  {stat}
                </div>
                <div className="text-[#64748B] text-sm">{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ── */}
      <section className="relative py-24 lg:py-32 bg-[#172033] overflow-hidden">
        <div className="absolute inset-0 pointer-events-none">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.04) 1px, transparent 0)",
              backgroundSize: "32px 32px",
            }}
          />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[400px] bg-[#08B5CF]/5 rounded-full blur-[100px]" />
        </div>

        <div className="relative max-w-7xl mx-auto px-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-10">
          <div className="max-w-xl">
            <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
              Try It Now
            </span>
            <h2
              className="text-[2.6rem] font-bold text-white mb-4 leading-tight"
              style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
            >
              Ready to prepare your next dataset?
            </h2>
            <p className="text-white/50 text-[15.5px] leading-relaxed">
              Start with upload or DOSM, review the data model, then move into the workspace
              with context already prepared. Your iceberg awaits.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 shrink-0">
            <button className="px-7 py-3.5 rounded-xl bg-[#08B5CF] hover:bg-[#08A9C2] text-white font-semibold text-[15px] transition-all duration-200 shadow-lg shadow-[#08B5CF]/25 hover:shadow-[#08B5CF]/40 hover:-translate-y-0.5">
              Get Started Now
            </button>
            <button className="px-7 py-3.5 rounded-xl border border-white/15 text-white/70 hover:border-white/30 hover:text-white text-[15px] transition-all duration-200">
              Learn More
            </button>
          </div>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-[#0B1624] py-16 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-10 mb-12">
            <div>
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-7 h-7 rounded-lg bg-[#08B5CF] flex items-center justify-center">
                  <svg width="13" height="13" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                    <path d="M10 2L16 8L13 11L16 14L10 20L4 14L7 11L4 8Z" fill="white" />
                  </svg>
                </div>
                <span className="font-semibold text-white text-[16px]">
                  Data<span className="text-[#08B5CF]">berge</span>
                </span>
              </div>
              <p className="text-white/35 text-sm leading-relaxed">
                Surface the thousands of stories hidden in your data.
              </p>
            </div>

            {[
              { heading: "Solutions", links: ["Workbook profiling", "Relationship modeling", "Executive reports"] },
              { heading: "Product", links: ["Data Pulse", "Explorer", "Data Model"] },
              { heading: "Sources", links: ["Excel", "CSV", "OpenDOSM"] },
            ].map(({ heading, links }) => (
              <div key={heading}>
                <div className="font-semibold text-white text-sm mb-4 tracking-wide">{heading}</div>
                <div className="flex flex-col gap-3">
                  {links.map(link => (
                    <a
                      key={link}
                      href="#"
                      className="text-white/35 hover:text-white/70 transition-colors text-sm"
                    >
                      {link}
                    </a>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-white/8 pt-8 flex flex-col sm:flex-row items-center justify-between gap-3">
            <span className="text-white/25 text-sm">© 2024 Databerge OS. All rights reserved.</span>
            <span className="text-white/20 text-xs font-mono">
              Below the surface, data tells more stories.
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
