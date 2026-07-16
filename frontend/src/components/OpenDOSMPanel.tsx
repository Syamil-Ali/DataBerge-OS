import { useEffect, useRef, useState } from 'react';
import { AlertCircle, ArrowRight, CheckCircle2, Database, Download, Loader, X } from 'lucide-react';
import {
  connectOpenDOSMDataset,
  getOpenDOSMTaskStatus,
  listOpenDOSMDatasets,
  OpenDOSMDataset,
} from '../services/api';

type Props = {
  projectId?: string | null;
  onConnected: (schemaId: string) => void;
};

const POLL_INTERVAL_MS = 3000;
type DownloadState = 'starting' | 'downloading' | 'completed' | 'failed';
type DownloadNotice = { datasetName: string; state: DownloadState; message: string };

export function OpenDOSMPanel({ projectId, onConnected }: Props) {
  const [datasets, setDatasets] = useState<OpenDOSMDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [downloadNotice, setDownloadNotice] = useState<DownloadNotice | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const completionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pollErrorsRef = useRef(0);

  useEffect(() => {
    listOpenDOSMDatasets()
      .then(setDatasets)
      .catch(() => setError('Failed to load datasets'))
      .finally(() => setLoading(false));
  }, []);

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (completionTimerRef.current) clearTimeout(completionTimerRef.current);
    };
  }, []);

  const startPolling = (taskId: string, datasetName: string) => {
    setStatusMsg('Downloading dataset...');
    pollErrorsRef.current = 0;
    setDownloadNotice({ datasetName, state: 'downloading', message: 'Downloading and preparing the dataset...' });
    timerRef.current = setInterval(async () => {
      try {
        const result = await getOpenDOSMTaskStatus(taskId);
        pollErrorsRef.current = 0;

        if (result.status === 'completed') {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setConnecting(null);
          setStatusMsg(null);
          setDownloadNotice({ datasetName, state: 'completed', message: result.message || 'Download complete.' });
          const connectedId = result.schema?.id || result.dataset?.id;
          if (connectedId) {
            completionTimerRef.current = setTimeout(() => onConnected(connectedId), 1200);
          }
        } else if (result.status === 'failed') {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setConnecting(null);
          setStatusMsg(null);
          const message = result.message || 'Download failed';
          setError(message);
          setDownloadNotice({ datasetName, state: 'failed', message });
        } else {
          const message = result.message || 'Downloading...';
          setStatusMsg(message);
          setDownloadNotice({
            datasetName,
            state: result.status === 'pending' ? 'starting' : 'downloading',
            message,
          });
        }
      } catch {
        pollErrorsRef.current += 1;
        if (pollErrorsRef.current >= 5) {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setConnecting(null);
          setStatusMsg(null);
          const message = 'Could not retrieve the download status. Please try again.';
          setError(message);
          setDownloadNotice({ datasetName, state: 'failed', message });
        }
      }
    }, POLL_INTERVAL_MS);
  };

  const handleConnect = async (dsId: string) => {
    const datasetName = datasets.find((dataset) => dataset.id === dsId)?.name || dsId;
    setConnecting(dsId);
    setError(null);
    setStatusMsg('Starting...');
    setDownloadNotice({ datasetName, state: 'starting', message: 'Starting OpenDOSM download...' });
    try {
      const { task_id } = await connectOpenDOSMDataset(dsId, projectId);
      startPolling(task_id, datasetName);
    } catch (err) {
      setConnecting(null);
      setStatusMsg(null);
      const message = err instanceof Error ? err.message : 'Connection failed';
      setError(message);
      setDownloadNotice({ datasetName, state: 'failed', message });
    }
  };

  if (loading) {
    return (
      <div className="opendosm-panel">
        <div className="opendosm-loading">
          <Loader className="spinner" size={18} />
          <span>Loading OpenDOSM catalogue...</span>
        </div>
      </div>
    );
  }

  const grouped = datasets.reduce<Record<string, OpenDOSMDataset[]>>((acc, ds) => {
    (acc[ds.category] ??= []).push(ds);
    return acc;
  }, {});
  const categoryEntries = Object.entries(grouped).sort(([left], [right]) => left.localeCompare(right));

  return (
    <div className="opendosm-panel">
      {downloadNotice && (
        <OpenDOSMDownloadNotice
          notice={downloadNotice}
          onClose={() => setDownloadNotice(null)}
        />
      )}
      <div className="opendosm-panel-head">
        <span className="opendosm-mark">
          <Database size={18} />
        </span>
        <div>
          <strong>OpenDOSM</strong>
          <span>Malaysia Official Open Data</span>
        </div>
        <em>{datasets.length} datasets</em>
      </div>

      {error && <div className="opendosm-error">{error}</div>}

      {statusMsg && (
        <div className="opendosm-status">
          <Loader className="spinner" size={14} />
          <span>{statusMsg}</span>
        </div>
      )}

      <div className="opendosm-categories">
        {categoryEntries.map(([category, items]) => (
          <div key={category} className="opendosm-category">
            <div className="opendosm-category-head">
              <h4>{category}</h4>
              <span>{items.length}</span>
            </div>
            <div className="opendosm-dataset-list">
              {items.map((ds) => (
                <button
                  key={ds.id}
                  className="opendosm-dataset-btn"
                  onClick={() => handleConnect(ds.id)}
                  disabled={connecting !== null}
                >
                  {connecting === ds.id ? (
                    <span className="opendosm-connect-state">
                      <Loader className="spinner" size={14} />
                      <span>{statusMsg || 'Connecting...'}</span>
                    </span>
                  ) : (
                    <>
                      <span className="opendosm-ds-info">
                        <span className="opendosm-ds-name">{ds.name}</span>
                        {ds.desc && <span className="opendosm-ds-desc">{ds.desc}</span>}
                      </span>
                      <span className="opendosm-ds-action">
                        <ArrowRight size={14} />
                      </span>
                    </>
                  )}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpenDOSMDownloadNotice({ notice, onClose }: { notice: DownloadNotice; onClose: () => void }) {
  const running = notice.state === 'starting' || notice.state === 'downloading';
  const Icon = notice.state === 'completed' ? CheckCircle2 : notice.state === 'failed' ? AlertCircle : Download;
  const label = notice.state === 'starting'
    ? 'Preparing download'
    : notice.state === 'downloading'
      ? 'Downloading'
      : notice.state === 'completed'
        ? 'Download complete'
        : 'Download failed';

  return (
    <aside
      className={`opendosm-download-popup ${notice.state}`}
      role={notice.state === 'failed' ? 'alert' : 'status'}
      aria-live={notice.state === 'failed' ? 'assertive' : 'polite'}
    >
      <div className="opendosm-download-head">
        <span className="opendosm-download-icon"><Icon size={16} /></span>
        <div>
          <strong>{label}</strong>
          <span>{notice.datasetName}</span>
        </div>
        {!running && (
          <button type="button" onClick={onClose} title="Close" aria-label="Close download status">
            <X size={15} />
          </button>
        )}
      </div>
      <div className="opendosm-download-track" aria-hidden="true"><span /></div>
      <p>{notice.message}</p>
    </aside>
  );
}
