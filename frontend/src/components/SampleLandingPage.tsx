import { useState, useEffect, useRef, type ReactNode } from "react";
import {
  ArrowRight, Database, GitBranch, FileText, ChevronDown,
  Menu, X, ExternalLink, TrendingUp, Search
} from "lucide-react";

// ─── Iceberg SVG ─────────────────────────────────────────────────────────────

// ─── Depth Meter ──────────────────────────────────────────────────────────────
function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting || entry.boundingClientRect.bottom < 0) {
          element.classList.add("is-visible");
          observer.unobserve(element);
        }
      },
      { threshold: 0.12, rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return <div ref={ref} className={`db-reveal ${className}`}>{children}</div>;
}

// ─── Main App ─────────────────────────────────────────────────────────────────
type SampleLandingPageProps = {
  onGetStarted: () => void;
  onLogin: () => void;
  onSignUp: () => void;
};

export default function SampleLandingPage({ onGetStarted, onLogin, onSignUp }: SampleLandingPageProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navFilled, setNavFilled] = useState(false);
  const heroRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;

    const observer = new IntersectionObserver(
      ([entry]) => setNavFilled(entry.intersectionRatio < 0.92),
      { threshold: [0.92] },
    );

    observer.observe(hero);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      className="min-h-screen overflow-x-hidden"
      style={{ fontFamily: "'DM Sans', sans-serif", backgroundColor: "#F8FAFC", color: "#172033" }}
    >
      {/* ── NAV ── */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-[background-color,backdrop-filter,border-color,box-shadow] duration-700 ease-out ${navFilled ? "bg-[#172033]/92 backdrop-blur-xl border-b border-white/5 shadow-lg shadow-[#08111d]/10" : "bg-transparent border-b border-transparent shadow-none"}`}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg overflow-hidden shadow-lg shadow-[#08B5CF]/30 group-hover:shadow-[#08B5CF]/50 transition-shadow">
              <img src="/favicon.svg" alt="" className="w-full h-full" />
            </div>
            <span className="font-semibold text-white text-[17px] tracking-tight">Data-Berge</span>
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
            <button onClick={onLogin} className="text-[13.5px] text-white/60 hover:text-white transition-colors">Log in</button>
            <button onClick={onSignUp} className="px-4 py-2 rounded-lg bg-[#08B5CF] hover:bg-[#08A9C2] text-white text-[13.5px] font-semibold transition-all hover:shadow-lg hover:shadow-[#08B5CF]/30">
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
              <button onClick={onLogin} className="text-white/60 hover:text-white text-sm transition-colors">Log in</button>
              <button onClick={onSignUp} className="px-4 py-2 rounded-lg bg-[#08B5CF] text-white text-sm font-semibold">
                Create account
              </button>
            </div>
          </div>
        )}
      </nav>

      {/* ── HERO ── */}
      <section ref={heroRef} className="relative min-h-[100dvh] bg-[#172033] overflow-hidden pt-16">
        <img
          src="/data-berge-hero-wide.webp"
          alt="Iceberg above and below the waterline"
          width="1672"
          height="939"
          fetchPriority="high"
          className="db-hero-image absolute inset-0 h-full w-full object-cover object-center"
        />
        <div className="absolute inset-0 bg-[#0B1624]/55" />
        <div className="absolute inset-0 bg-gradient-to-b from-[#172033]/45 via-[#0B1624]/65 to-[#0B1624]/45" />

        <div className="relative mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-4xl items-center justify-center px-6 pb-24 pt-8 text-center">
          <div className="db-hero-content flex flex-col items-center">
            <h1
              className="mb-6 text-[2.8rem] font-bold leading-[1.02] tracking-tight text-white sm:text-[3.5rem] lg:text-[4.2rem]"
              style={{ fontFamily: "'Bricolage Grotesque', sans-serif", textShadow: "0 3px 26px rgba(4, 13, 27, 0.6)" }}
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

            <p className="mb-8 max-w-xl text-[1.05rem] leading-[1.7] text-white/75" style={{ textShadow: "0 2px 18px rgba(4, 13, 27, 0.85)" }}>
              Like an iceberg, your data hides thousands of stories beneath the surface.
              Upload workbooks, map relationships, and let Databerge surface what you&apos;ve been missing.
            </p>

            <div className="mb-8 flex flex-wrap justify-center gap-3.5">
              <button onClick={onGetStarted} className="group flex items-center gap-2 px-6 py-3 rounded-xl bg-[#08B5CF] hover:bg-[#08A9C2] text-white font-semibold text-[15px] transition-all duration-200 shadow-lg shadow-[#08B5CF]/20 hover:shadow-[#08B5CF]/40 hover:-translate-y-0.5">
                Dive Deeper
                <ArrowRight size={17} className="group-hover:translate-x-0.5 transition-transform" />
              </button>
              <button className="flex items-center gap-2 px-6 py-3 rounded-xl border border-white/15 text-white/70 hover:border-white/30 hover:text-white text-[15px] transition-all duration-200">
                How It Works
                <ChevronDown size={17} />
              </button>
            </div>

            <div className="flex flex-wrap items-center justify-center gap-2.5">
              <span className="text-sm font-mono text-white/55">Compatible with</span>
              {["Excel", "CSV", "OpenDOSM", "DuckDB"].map(f => (
                <span
                  key={f}
                  className="cursor-default rounded-md border border-white/15 bg-[#0B1624]/45 px-2.5 py-1 font-mono text-[11.5px] text-white/70 backdrop-blur-sm transition-colors hover:border-[#08B5CF]/40 hover:text-white"
                >
                  {f}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Wave break to next section */}
        <div className="db-wave-break absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 72" fill="none" xmlns="http://www.w3.org/2000/svg" className="block w-full">
            <path
              d="M0,36 Q180,72 360,36 Q540,0 720,36 Q900,72 1080,36 Q1260,0 1440,36 L1440,72 L0,72 Z"
              fill="#F8FAFC"
            />
          </svg>
        </div>
      </section>

      {/* ── WORKFLOW FEATURES ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <Reveal className="max-w-7xl mx-auto px-6">
          <div className="mb-14 max-w-2xl">
            <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-3 block">
              Workflow
            </span>
            <h2
              className="text-[2.4rem] font-bold text-[#172033] leading-tight"
              style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
            >
              Experience that grows with your data.
            </h2>
            <p className="mt-5 text-[#64748B] leading-relaxed max-w-xl text-[15.5px]">
              Data-Berge maps what is visible and carries the structure needed to explore what lies beneath.
            </p>
          </div>

          <div>
            <div className="db-reveal-stagger grid md:grid-cols-[1.2fr_0.8fr] gap-5">
              <article className="db-motion-card group relative min-h-[500px] p-8 rounded-2xl border border-[#D8E4E8] bg-gradient-to-b from-white to-[#E8F5F6] overflow-hidden hover:shadow-2xl hover:shadow-[#08B5CF]/10 transition-all duration-300">
                <div className="absolute inset-x-0 top-0 h-48 bg-[radial-gradient(circle_at_70%_0%,rgba(8,181,207,0.18),transparent_64%)]" />
                <div className="relative h-full flex flex-col justify-end">
                  <div className="w-12 h-12 rounded-xl bg-[#08B5CF]/12 flex items-center justify-center mb-8">
                    <FileText size={21} className="text-[#08B5CF]" />
                  </div>
                  <h3 className="text-2xl font-semibold text-[#172033] mb-3">Workbook profiling</h3>
                  <p className="max-w-md text-[#64748B] text-sm leading-relaxed">
                    Read Excel and CSV files, detect tables, infer types, and surface full column coverage before analysis begins.
                  </p>
                </div>
              </article>

              <div className="grid gap-5">
                {[
                  {
                    icon: GitBranch,
                    label: "Relationship modeling",
                    desc: "Confirm joins, keys, and table relationships before the workspace starts answering your questions.",
                  },
                  {
                    icon: Database,
                    label: "Analyst context",
                    desc: "Carry profile metadata, descriptions, and model context into Explorer and Executive Reports.",
                  },
                ].map(({ icon: Icon, label, desc }) => (
                  <article key={label} className="db-motion-card group min-h-[240px] p-7 rounded-2xl bg-white border border-[#E2E8F0] hover:border-[#08B5CF]/30 hover:shadow-xl hover:shadow-[#08B5CF]/8 transition-all duration-300">
                    <div className="w-11 h-11 rounded-xl bg-[#08B5CF]/10 flex items-center justify-center mb-8">
                      <Icon size={19} className="text-[#087F91]" />
                    </div>
                    <h3 className="font-semibold text-[#172033] text-[17px] mb-2.5">{label}</h3>
                    <p className="text-[#64748B] text-sm leading-relaxed">{desc}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      {/* ── DEPTH / STATS ── */}
      <section className="relative py-24 lg:py-32 bg-[#172033] overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none opacity-70"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.04) 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />

        <Reveal className="relative max-w-7xl mx-auto px-6">
          <div className="max-w-2xl mb-14 lg:mb-16">
            <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">What Happens Next</span>
            <h2 className="text-[2.5rem] lg:text-[3.2rem] font-bold text-white leading-tight mb-6" style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}>
              From messy workbook to clear answers.
            </h2>
            <p className="text-white/55 leading-[1.8] text-[15.5px] max-w-xl">
              You do not need to clean everything first. Add your file, check what Data-Berge found, and start exploring.
            </p>
          </div>

          <div className="db-reveal-stagger relative grid lg:grid-cols-3 rounded-2xl border border-white/10 bg-white/[0.035] overflow-hidden">
            {[
              { step: "01", icon: FileText, title: "Add your file", desc: "Upload an Excel or CSV file exactly as it is. No special template is required." },
              { step: "02", icon: GitBranch, title: "Check what we found", desc: "See the detected tables, columns, and connections. Correct anything before moving on." },
              { step: "03", icon: Search, title: "Explore with confidence", desc: "Ask questions, build charts, and create reports from a structure you have already reviewed." },
            ].map(({ step, icon: Icon, title, desc }, index) => (
              <article key={step} className="relative p-7 lg:p-9 border-b last:border-b-0 lg:border-b-0 lg:border-r lg:last:border-r-0 border-white/10">
                <div className="mb-12 flex items-center justify-between">
                  <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#08B5CF]/12 border border-[#08B5CF]/20">
                    <Icon size={19} className="text-[#08B5CF]" />
                  </span>
                  <span className="font-mono text-xs text-white/25">{step}</span>
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{title}</h3>
                <p className="text-sm leading-relaxed text-white/50">{desc}</p>
                {index < 2 && <ArrowRight size={18} className="absolute right-[-9px] top-12 z-10 hidden text-[#08B5CF] lg:block" />}
              </article>
            ))}
          </div>

          <div className="mt-6 flex items-start gap-3 text-sm text-white/55">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#08B5CF]" />
            <p><span className="font-semibold text-white/80">You stay in control.</span> Data-Berge shows you the structure before any analysis begins.</p>
          </div>
        </Reveal>

        <div className="db-wave-break absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="block w-full">
            <path d="M0,32 Q360,64 720,32 Q1080,0 1440,32 L1440,64 L0,64 Z" fill="#F8FAFC" />
          </svg>
        </div>
      </section>

      {/* ── DATA SOURCES ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <Reveal className="max-w-7xl mx-auto px-6">
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

          <div className="db-reveal-stagger grid md:grid-cols-2 gap-5">
            {/* Upload */}
            <button type="button" onClick={onGetStarted} className="db-motion-card group relative p-8 rounded-2xl bg-white border border-[#E2E8F0] hover:border-[#08B5CF]/25 hover:shadow-xl hover:shadow-[#08B5CF]/6 transition-all duration-300 cursor-pointer overflow-hidden text-left">
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
            </button>

            {/* DOSM */}
            <button type="button" onClick={onGetStarted} className="db-motion-card group relative p-8 rounded-2xl bg-[#08B5CF] hover:bg-[#08A9C2] transition-all duration-300 cursor-pointer overflow-hidden shadow-lg shadow-[#08B5CF]/20 hover:shadow-[#08B5CF]/35 text-left">
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
                Access Malaysia&apos;s national statistics and open data platform, directly wired into your workspace.
              </div>
            </button>
          </div>
        </Reveal>
      </section>

      {/* ── MODEL-FIRST FLOW ── */}
      <section className="relative py-24 lg:py-32 bg-[#0F1E30] overflow-hidden">
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(8,181,207,0.035) 1px, transparent 0)",
            backgroundSize: "28px 28px",
          }}
        />

        <div className="relative max-w-7xl mx-auto px-6 grid lg:grid-cols-[0.8fr_1.2fr] gap-14 lg:gap-24">
          <Reveal>
            <div className="lg:sticky lg:top-28">
              <span className="text-[#08B5CF] text-[10.5px] font-semibold uppercase tracking-[0.16em] mb-4 block">
                Once Your Data Is Ready
              </span>
              <h2
                className="text-[2.4rem] font-bold text-white mb-5 max-w-xl leading-tight"
                style={{ fontFamily: "'Bricolage Grotesque', sans-serif" }}
              >
                Find the story, then share it.
              </h2>
              <p className="text-white/45 max-w-md text-[15px] leading-relaxed">
                Use the same prepared workspace to answer questions, investigate patterns, and communicate what matters.
              </p>
            </div>
          </Reveal>

          <Reveal>
            <div className="db-reveal-stagger grid gap-4">
              {[
                {
                  label: "Data Pulse",
                  title: "Ask a question",
                  desc: "Use everyday language to ask about your data and receive answers grounded in the workspace you reviewed.",
                  icon: Search,
                  action: "Question to answer",
                },
                {
                  label: "Explorer",
                  title: "Investigate a pattern",
                  desc: "Compare groups, filter results, and build charts when you need to understand what is driving a change.",
                  icon: TrendingUp,
                  action: "Pattern to evidence",
                },
                {
                  label: "Executive Reports",
                  title: "Share the finding",
                  desc: "Turn the important results into a focused report that decision-makers can read without opening the raw data.",
                  icon: FileText,
                  action: "Finding to report",
                },
              ].map(({ label, title, desc, icon: Icon, action }) => (
                <article key={label} className="group grid gap-5 rounded-2xl border border-white/10 bg-white/[0.035] p-6 transition-colors duration-300 hover:border-[#08B5CF]/30 hover:bg-white/[0.055] sm:grid-cols-[52px_1fr_auto] sm:items-center">
                  <span className="db-timeline-node flex h-12 w-12 items-center justify-center rounded-xl border border-[#08B5CF]/20 bg-[#13263A]">
                    <Icon size={17} className="text-[#08B5CF]" />
                  </span>
                  <div>
                    <span className="text-[11px] text-[#08B5CF]/70 font-mono uppercase tracking-wider">{label}</span>
                    <h3 className="text-xl font-semibold text-white mt-1.5 mb-2">{title}</h3>
                    <p className="text-white/45 text-sm leading-relaxed max-w-lg">{desc}</p>
                  </div>
                  <div className="flex items-center gap-2 text-xs font-mono text-white/30 transition-colors group-hover:text-[#08B5CF]">
                    <span>{action}</span>
                    <ArrowRight size={14} />
                  </div>
                </article>
              ))}
            </div>
          </Reveal>
        </div>

        <div className="db-wave-break absolute bottom-0 left-0 right-0 pointer-events-none">
          <svg viewBox="0 0 1440 64" fill="none" xmlns="http://www.w3.org/2000/svg" className="block w-full">
            <path d="M0,32 Q360,0 720,32 Q1080,64 1440,32 L1440,64 L0,64 Z" fill="#F8FAFC" />
          </svg>
        </div>
      </section>

      {/* ── WHY IT MATTERS ── */}
      <section className="py-24 lg:py-32 bg-[#F8FAFC]">
        <Reveal className="max-w-7xl mx-auto px-6 text-center">
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

          <div className="db-reveal-stagger grid grid-cols-1 sm:grid-cols-3 max-w-4xl mx-auto border-t border-[#D8E2E8]">
            {[
              { stat: "100%", label: "Description coverage target" },
              { stat: "180K", label: "Rows profiled in local workflows" },
              { stat: "10+", label: "Analysis surfaces planned" },
            ].map(({ stat, label }) => (
              <div key={stat} className="group px-6 py-9 sm:border-r sm:last:border-r-0 border-[#D8E2E8]">
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
        </Reveal>
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

        <Reveal className="relative max-w-7xl mx-auto px-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-10">
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
            <button onClick={onGetStarted} className="px-7 py-3.5 rounded-xl bg-[#08B5CF] hover:bg-[#08A9C2] text-white font-semibold text-[15px] transition-all duration-200 shadow-lg shadow-[#08B5CF]/25 hover:shadow-[#08B5CF]/40 hover:-translate-y-0.5">
              Get Started Now
            </button>
            <button className="px-7 py-3.5 rounded-xl border border-white/15 text-white/70 hover:border-white/30 hover:text-white text-[15px] transition-all duration-200">
              Learn More
            </button>
          </div>
        </Reveal>
      </section>

      {/* ── FOOTER ── */}
      <footer className="bg-[#0B1624] py-16 border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-10 mb-12">
            <div>
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-7 h-7 rounded-lg overflow-hidden">
                  <img src="/favicon.svg" alt="" className="w-full h-full" />
                </div>
                <span className="font-semibold text-white text-[16px]">Data-Berge</span>
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
