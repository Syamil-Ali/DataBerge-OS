import { useEffect, useRef, useState } from 'react';
import { ArrowRight, Database, Loader } from 'lucide-react';
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

export function OpenDOSMPanel({ projectId, onConnected }: Props) {
  const [datasets, setDatasets] = useState<OpenDOSMDataset[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

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
    };
  }, []);

  const startPolling = (taskId: string) => {
    setStatusMsg('Downloading dataset...');
    timerRef.current = setInterval(async () => {
      try {
        const result = await getOpenDOSMTaskStatus(taskId);

        if (result.status === 'completed') {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setConnecting(null);
          setStatusMsg(null);
          if (result.schema) {
            onConnected(result.schema.id);
          } else if (result.dataset) {
            onConnected(result.dataset.id);
          }
        } else if (result.status === 'failed') {
          if (timerRef.current) clearInterval(timerRef.current);
          timerRef.current = null;
          setConnecting(null);
          setStatusMsg(null);
          setError(result.message || 'Download failed');
        } else {
          setStatusMsg(result.message || 'Downloading...');
        }
      } catch {
        // poll error, keep trying
      }
    }, POLL_INTERVAL_MS);
  };

  const handleConnect = async (dsId: string) => {
    setConnecting(dsId);
    setError(null);
    setStatusMsg('Starting...');
    try {
      const { task_id } = await connectOpenDOSMDataset(dsId, projectId);
      startPolling(task_id);
    } catch (err) {
      setConnecting(null);
      setStatusMsg(null);
      setError(err instanceof Error ? err.message : 'Connection failed');
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
