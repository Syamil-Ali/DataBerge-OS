import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Database,
  FileSpreadsheet,
  GitBranch,
  Link2,
  MessageSquareText,
  Table2,
  UploadCloud,
} from 'lucide-react';
import { OpenDOSMPanel } from './OpenDOSMPanel';

export type LandingStep = 'landing' | 'setup' | 'file-upload' | 'dosm-connect';

type LandingPageProps = {
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
  projectId?: string | null;
  onOpenDOSMConnected?: (schemaId: string) => void;
  initialStep?: LandingStep;
  onBackHome?: () => void;
  onGetStarted?: () => void;
  onLogin?: () => void;
  onSignUp?: () => void;
};

const partnerLabels = ['Excel', 'CSV', 'OpenDOSM', 'DuckDB'];

const featureCards = [
  {
    icon: FileSpreadsheet,
    title: 'Workbook profiling',
    copy: 'Read CSV and Excel files, detect tables, infer types, and surface column coverage.',
  },
  {
    icon: GitBranch,
    title: 'Relationship modeling',
    copy: 'Confirm joins, keys, and table relationships before the workspace starts answering.',
  },
  {
    icon: MessageSquareText,
    title: 'Analyst context',
    copy: 'Carry profile metadata, descriptions, and model context into Explorer and reports.',
  },
];

const workflowSteps = [
  {
    title: 'Upload or connect',
    copy: 'Bring in Excel, CSV, or OpenDOSM data from the setup page.',
  },
  {
    title: 'Review the model',
    copy: 'Preview rows, correct datatypes, and confirm table relationships.',
  },
  {
    title: 'Analyze with context',
    copy: 'Use Data Pulse, Explorer, and Executive Report from the confirmed profile.',
  },
];

export function LandingPage({
  busy,
  onUpload,
  projectId,
  onOpenDOSMConnected,
  initialStep = 'landing',
  onBackHome,
  onGetStarted,
  onLogin,
  onSignUp,
}: LandingPageProps) {
  const [step, setStep] = useState<LandingStep>(initialStep);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setStep(initialStep);
  }, [initialStep]);

  const openSetup = () => {
    if (onGetStarted) {
      onGetStarted();
      return;
    }
    setStep('setup');
  };

  const goHome = () => {
    if (onBackHome) {
      onBackHome();
      return;
    }
    setStep('landing');
  };

  const openLogin = () => {
    if (onLogin) {
      onLogin();
      return;
    }
    openSetup();
  };

  const openSignUp = () => {
    if (onSignUp) {
      onSignUp();
      return;
    }
    openSetup();
  };

  const handleFile = async (file: File) => {
    const lower = file.name.toLowerCase();
    if (!lower.endsWith('.csv') && !lower.endsWith('.xlsx') && !lower.endsWith('.xls')) {
      setError('Upload a CSV or Excel file.');
      return;
    }
    setError(null);
    await onUpload(file);
    if (inputRef.current) inputRef.current.value = '';
  };

  const handleChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) await handleFile(file);
  };

  const handleDrop = async (event: DragEvent) => {
    event.preventDefault();
    setDragOver(false);
    const file = event.dataTransfer.files[0];
    if (file) await handleFile(file);
  };

  if (step === 'setup') {
    return (
      <div className="landing-shell setup">
        <header className="landing-nav setup-nav">
          <button className="landing-nav-back" onClick={goHome}>
            <ArrowLeft size={15} />
            Back to Home
          </button>
        </header>

        <main className="data-setup-page">
          <section className="data-setup-head">
            <h1>Connect your data</h1>
            <p>Choose how you want to bring data into Data-Berge before profiling, modeling, and analysis starts.</p>
          </section>

          <section className="data-source-grid">
            <button className="data-source-card" onClick={() => setStep('file-upload')}>
              <span className="data-source-icon cyan">
                <UploadCloud size={26} />
              </span>
              <span className="data-source-copy">
                <strong>Upload Dataset</strong>
                <span>Use CSV or Excel files for one-off analysis, relationship modeling, and quick reports.</span>
              </span>
              <span className="data-source-tags">
                <em><FileSpreadsheet size={13} /> CSV</em>
                <em><Table2 size={13} /> XLSX</em>
                <em>XLS</em>
              </span>
            </button>

            <button className="data-source-card" onClick={() => setStep('dosm-connect')}>
              <span className="data-source-icon green">
                <Link2 size={25} />
              </span>
              <span className="data-source-copy">
                <strong>Connect DOSM</strong>
                <span>Pull public Malaysian datasets through the OpenDOSM connector and profile them in the workspace.</span>
              </span>
              <span className="data-source-tags">
                <em>OpenDOSM</em>
                <em>API</em>
                <em>Public data</em>
              </span>
            </button>
          </section>
        </main>
      </div>
    );
  }

  if (step === 'file-upload') {
    return (
      <div className="landing-shell setup">
        <header className="landing-nav setup-nav">
          <button className="landing-nav-back" onClick={() => setStep('setup')}>
            <ArrowLeft size={15} />
            Choose another source
          </button>
        </header>

        <main className="file-upload-page">
          <section className="data-setup-head">
            <h1>Upload your dataset</h1>
            <p>Drop in a CSV or Excel workbook. Data-Berge will profile the file and open the data model review before the workspace.</p>
          </section>

          <section className="file-upload-stage">
            <div
              className={`setup-dropzone ${dragOver ? 'drag-over' : ''} ${busy ? 'processing' : ''}`}
              onDragOver={(event) => {
                event.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => !busy && inputRef.current?.click()}
            >
              <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleChange} disabled={busy} />
              <div className="setup-dropzone-icon">
                {busy ? <div className="dropzone-spinner" /> : <UploadCloud size={30} />}
              </div>
              <div className="setup-dropzone-copy">
                <strong>{busy ? 'Analyzing your data...' : dragOver ? 'Drop your file here' : 'Drop a file here'}</strong>
                <span>{busy ? 'Profiling, detecting tables, and preparing the data model.' : 'or click to browse from your computer'}</span>
              </div>
              <div className="setup-dropzone-formats">
                <Table2 size={13} />
                CSV, XLSX, XLS
              </div>
              {error && <div className="upload-card-error">{error}</div>}
            </div>
          </section>
        </main>
      </div>
    );
  }

  if (step === 'dosm-connect') {
    return (
      <div className="landing-shell setup">
        <header className="landing-nav setup-nav">
          <button className="landing-nav-back" onClick={() => setStep('setup')}>
            <ArrowLeft size={15} />
            Choose another source
          </button>
        </header>

        <main className="dosm-connect-page">
          <section className="data-setup-head">
            <h1>Connect DOSM data</h1>
            <p>Pick a public Malaysian dataset from OpenDOSM. Data-Berge will download it, profile it, and open the workspace.</p>
          </section>

          <section className="dosm-connect-stage">
            {onOpenDOSMConnected ? (
              <OpenDOSMPanel projectId={projectId} onConnected={onOpenDOSMConnected} />
            ) : (
              <div className="setup-empty-source">OpenDOSM connector is not available in this build.</div>
            )}
          </section>
        </main>
      </div>
    );
  }

  return (
    <div className="landing-showcase">
      <header className="showcase-nav">
        <div className="showcase-nav-inner">
          <button className="showcase-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <span><img src="/favicon.svg" alt="" /></span>
            <strong>Data-Berge</strong>
          </button>
          <nav>
            <button onClick={() => document.getElementById('showcase-flow')?.scrollIntoView({ behavior: 'smooth' })}>Product</button>
            <button onClick={() => document.getElementById('showcase-sources')?.scrollIntoView({ behavior: 'smooth' })}>Sources</button>
            <button onClick={() => document.getElementById('showcase-proof')?.scrollIntoView({ behavior: 'smooth' })}>Results</button>
          </nav>
          <div className="showcase-auth-actions">
            <button className="showcase-login" onClick={openLogin}>Log in</button>
            <button className="showcase-signup" onClick={openSignUp}>Create account</button>
          </div>
        </div>
      </header>

      <main>
        <section className="showcase-hero">
          <div className="showcase-hero-copy">
            <span className="showcase-eyebrow"><Database size={13} /> Analysis workspace for real-world data</span>
            <h1>Get analysis-ready data models fast.</h1>
            <p>Upload workbooks, connect DOSM data, confirm relationships, and enter a workspace that already understands your tables.</p>
            <div className="showcase-start">
              <button onClick={openSetup}>
                Get Started
                <ArrowRight size={15} />
              </button>
              <span>{partnerLabels.join('  /  ')}</span>
            </div>
          </div>

          <div className="showcase-visual" aria-label="Data-Berge product preview">
            <div className="showcase-profile-card">
              <span>Data Pulse</span>
              <strong>5 fields</strong>
              <em>Profile ready for exploration</em>
            </div>
            <div className="showcase-window">
              <div className="window-bar">
                <i /><i /><i />
                <span>Data Model</span>
              </div>
              <div className="model-grid-preview">
                <article>
                  <strong>Customer</strong>
                  <span>CustomerID</span>
                  <span>Email</span>
                  <span>Status</span>
                </article>
                <div className="model-link-preview">
                  <em>many-to-one</em>
                </div>
                <article>
                  <strong>Order</strong>
                  <span>OrderID</span>
                  <span>CustomerID</span>
                  <span>TotalAmount</span>
                </article>
              </div>
            </div>

            <div className="showcase-floating-card">
              <span>Model</span>
              <strong>3 tables</strong>
              <em>2 relationships</em>
            </div>
          </div>
        </section>

        <section id="showcase-flow" className="showcase-feature-panel">
          <div>
            <span>Workflow</span>
            <h2>Experience that grows with your data.</h2>
          </div>
          <div className="showcase-feature-list">
            {featureCards.map((feature) => {
              const Icon = feature.icon;
              return (
                <article key={feature.title}>
                  <Icon size={22} />
                  <h3>{feature.title}</h3>
                  <p>{feature.copy}</p>
                </article>
              );
            })}
          </div>
        </section>

        <section id="showcase-proof" className="showcase-proof-grid">
          <article className="showcase-metric">
            <strong>100%</strong>
            <span>Description coverage target</span>
          </article>
          <article className="showcase-route-card">
            <h3>Workbook to workspace without losing context</h3>
            <div><FileSpreadsheet size={24} /><i /><Database size={24} /></div>
          </article>
          <article className="showcase-chart-card">
            <h3>Profile coverage</h3>
            <svg viewBox="0 0 360 150" aria-hidden="true">
              <path d="M20 120 C90 88 120 86 170 70 C225 52 268 62 340 26" />
              <polyline points="20,120 90,88 170,70 240,58 340,26" />
            </svg>
          </article>
        </section>

        <section id="showcase-sources" className="showcase-action-band">
          <div>
            <span>Choose source</span>
            <h2>Start with the data you have.</h2>
          </div>
          <div>
            <button onClick={openSetup}><strong>Upload</strong><em>CSV / Excel</em><ArrowUpRight size={16} /></button>
            <button onClick={openSetup}><strong>DOSM</strong><em>Open data connector</em><ArrowUpRight size={16} /></button>
          </div>
        </section>

        <section className="showcase-steps">
          <div>
            <span>Model-first flow</span>
            <h2>Move from raw files to useful answers without guessing the dataset shape.</h2>
          </div>
          <div className="showcase-step-grid">
            {workflowSteps.map((item, index) => (
              <article key={item.title}>
                <strong>{index + 1}</strong>
                <h3>{item.title}</h3>
                <p>{item.copy}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="showcase-stats">
          <span>Why it matters</span>
          <h2>Built for messy business data, not perfect demo tables.</h2>
          <p>Data-Berge keeps table structure, descriptions, relationships, and analyst context visible before chat or reports start using the dataset.</p>
          <div>
            <article><strong>100%</strong><span>Description coverage target</span></article>
            <article><strong>180K</strong><span>Rows profiled in local workflows</span></article>
            <article><strong>10+</strong><span>Analysis surfaces planned</span></article>
          </div>
        </section>

        <section className="showcase-source-cards">
          <span>Bring data in</span>
          <div>
            <button onClick={openSetup}>
              <strong>Upload Dataset</strong>
              <em>CSV, XLSX, XLS</em>
              <ArrowUpRight size={16} />
            </button>
            <button className="accent" onClick={openSetup}>
              <strong>Connect DOSM</strong>
              <em>Open data catalogue</em>
              <ArrowUpRight size={16} />
            </button>
          </div>
        </section>

        <section className="showcase-final-cta">
          <div>
            <span>Try it now</span>
            <h2>Ready to prepare your next dataset?</h2>
            <p>Start with upload or DOSM, review the data model, then move into the workspace with context already prepared.</p>
          </div>
          <div>
            <button onClick={openSetup}>Get Started Now</button>
            <button className="outline" onClick={() => document.getElementById('showcase-flow')?.scrollIntoView({ behavior: 'smooth' })}>Learn More</button>
          </div>
        </section>
      </main>

      <footer className="showcase-footer">
        <div className="showcase-footer-inner">
          <div className="showcase-brand">
            <span><img src="/favicon.svg" alt="" /></span>
            <strong>Data-Berge</strong>
          </div>
          <div>
            <strong>Solutions</strong>
            <span>Workbook profiling</span>
            <span>Relationship modeling</span>
            <span>Executive reports</span>
          </div>
          <div>
            <strong>Product</strong>
            <span>Data Pulse</span>
            <span>Explorer</span>
            <span>Data Model</span>
          </div>
          <div>
            <strong>Sources</strong>
            <span>Excel</span>
            <span>CSV</span>
            <span>OpenDOSM</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
