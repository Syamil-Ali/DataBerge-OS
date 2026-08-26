import { ChangeEvent, DragEvent, useEffect, useRef, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  FileSpreadsheet,
  Link2,
  Table2,
  UploadCloud,
  Database,
} from 'lucide-react';
import { OpenDOSMPanel } from './OpenDOSMPanel';
import { SupabasePanel } from './SupabasePanel';
import SampleLandingPage from './SampleLandingPage';

export type LandingStep = 'landing' | 'setup' | 'file-upload' | 'dosm-connect' | 'supabase-connect';

function SetupHeader({ onHome, onBack, backLabel }: { onHome: () => void; onBack: () => void; backLabel: string }) {
  return (
    <header className="landing-nav setup-nav">
      <button className="setup-brand" type="button" onClick={onHome} aria-label="Return to Data-Berge homepage">
        <img src="/favicon.svg" alt="" />
        <strong>Data-Berge</strong>
      </button>
      <button className="landing-nav-back" type="button" onClick={onBack}>
        <ArrowLeft size={15} />
        {backLabel}
      </button>
    </header>
  );
}

function SetupJourney() {
  return (
    <div className="setup-journey" aria-label="Data setup progress">
      <span className="active"><b>1</b>Add data</span>
      <ArrowRight size={13} aria-hidden="true" />
      <span><b>2</b>Review model</span>
      <ArrowRight size={13} aria-hidden="true" />
      <span><b>3</b>Workspace</span>
    </div>
  );
}

type LandingPageProps = {
  busy: boolean;
  onUpload: (file: File) => Promise<void>;
  projectId?: string | null;
  onOpenDOSMConnected?: (schemaId: string) => void;
  onFederatedDatasetConnected?: (datasetId: string) => void;
  initialStep?: LandingStep;
  onBackHome?: () => void;
  onGetStarted?: () => void;
  onLogin?: () => void;
  onSignUp?: () => void;
};

export function LandingPage({
  busy,
  onUpload,
  projectId,
  onOpenDOSMConnected,
  onFederatedDatasetConnected,
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
        <SetupHeader onHome={goHome} onBack={goHome} backLabel="Back to landing" />

        <main className="data-setup-page">
          <section className="data-setup-head">
            <span className="setup-eyebrow">Data setup</span>
            <h1>Connect your data</h1>
            <p>Choose how you want to bring data into Data-Berge before profiling, modeling, and analysis starts.</p>
            <SetupJourney />
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

            <button className="data-source-card" onClick={() => setStep('supabase-connect')}>
              <span className="data-source-icon violet">
                <Database size={25} />
              </span>
              <span className="data-source-copy">
                <strong>Connect Supabase</strong>
                <span>Query PostgreSQL tables where they live without downloading the full database.</span>
              </span>
              <span className="data-source-tags">
                <em>Supabase</em>
                <em>PostgreSQL</em>
                <em>Live query</em>
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
        <SetupHeader onHome={goHome} onBack={() => setStep('setup')} backLabel="Choose another source" />

        <main className="file-upload-page">
          <section className="data-setup-head">
            <span className="setup-eyebrow">File connector</span>
            <h1>Upload your dataset</h1>
            <p>Drop in a CSV or Excel workbook. Data-Berge will profile the file and open the data model review before the workspace.</p>
            <SetupJourney />
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
              onKeyDown={(event) => {
                if (!busy && (event.key === 'Enter' || event.key === ' ')) {
                  event.preventDefault();
                  inputRef.current?.click();
                }
              }}
              role="button"
              tabIndex={busy ? -1 : 0}
              aria-disabled={busy}
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
        <SetupHeader onHome={goHome} onBack={() => setStep('setup')} backLabel="Choose another source" />

        <main className="dosm-connect-page">
          <section className="data-setup-head">
            <span className="setup-eyebrow">Open data connector</span>
            <h1>Connect DOSM data</h1>
            <p>Pick a public Malaysian dataset from OpenDOSM. Data-Berge will download it, profile it, and open the workspace.</p>
            <SetupJourney />
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

  if (step === 'supabase-connect') {
    return (
      <div className="landing-shell setup">
        <SetupHeader onHome={goHome} onBack={() => setStep('setup')} backLabel="Choose another source" />
        <main className="dosm-connect-page">
          <section className="data-setup-head">
            <span className="setup-eyebrow">Federated database connector</span>
            <h1>Connect Supabase</h1>
            <p>Register a remote table for governed, on-demand queries. The complete table stays in Supabase.</p>
            <SetupJourney />
          </section>
          <section className="dosm-connect-stage">
            {projectId && onFederatedDatasetConnected ? (
              <SupabasePanel projectId={projectId} onConnected={onFederatedDatasetConnected} />
            ) : (
              <div className="setup-empty-source">Supabase connector is not available in this build.</div>
            )}
          </section>
        </main>
      </div>
    );
  }

  return (
    <SampleLandingPage
      onGetStarted={openSetup}
      onLogin={openLogin}
      onSignUp={openSignUp}
    />
  );

}
