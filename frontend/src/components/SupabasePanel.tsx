import { FormEvent, useEffect, useState } from 'react';
import { CheckCircle2, Cloud, Database, Loader, Table2 } from 'lucide-react';
import {
  createDataConnection,
  createFederatedDataset,
  deleteDataConnection,
  listRemoteSchemas,
  listRemoteTables,
  RemoteSchema,
  RemoteTable,
  testDataConnection,
} from '../services/api';

type Props = {
  projectId: string;
  onConnected: (datasetId: string) => void;
};

type FormState = {
  name: string;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
};

const initialForm: FormState = {
  name: 'My Supabase',
  host: '',
  port: '5432',
  database: 'postgres',
  username: 'postgres',
  password: '',
};

function errorMessage(error: unknown): string {
  if (!(error instanceof Error)) return 'The Supabase operation failed.';
  try {
    const parsed = JSON.parse(error.message);
    return parsed.detail || error.message;
  } catch {
    return error.message;
  }
}

export function SupabasePanel({ projectId, onConnected }: Props) {
  const [form, setForm] = useState<FormState>(initialForm);
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [schemas, setSchemas] = useState<RemoteSchema[]>([]);
  const [tables, setTables] = useState<RemoteTable[]>([]);
  const [schema, setSchema] = useState('public');
  const [table, setTable] = useState('');
  const [busy, setBusy] = useState(false);
  const [loadingTables, setLoadingTables] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!connectionId || !schema) return;
    setLoadingTables(true);
    setTable('');
    listRemoteTables(projectId, connectionId, schema)
      .then((items) => {
        setTables(items);
        setTable(items[0]?.name || '');
      })
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoadingTables(false));
  }, [connectionId, projectId, schema]);

  const connect = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    let createdConnectionId: string | null = null;
    try {
      const connection = await createDataConnection(projectId, {
        name: form.name,
        provider: 'supabase',
        host: form.host.trim(),
        port: Number(form.port),
        database: form.database.trim(),
        username: form.username.trim(),
        password: form.password,
        sslmode: 'require',
      });
      createdConnectionId = connection.id;
      await testDataConnection(projectId, connection.id);
      const discovered = await listRemoteSchemas(projectId, connection.id);
      const preferred = discovered.some((item) => item.name === 'public') ? 'public' : discovered[0]?.name || '';
      setConnectionId(connection.id);
      setSchemas(discovered);
      setSchema(preferred);
      setForm((current) => ({ ...current, password: '' }));
    } catch (err) {
      if (createdConnectionId) {
        await deleteDataConnection(projectId, createdConnectionId).catch(() => undefined);
      }
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const register = async () => {
    if (!connectionId || !schema || !table) return;
    setBusy(true);
    setError(null);
    try {
      const dataset = await createFederatedDataset(projectId, {
        connection_id: connectionId,
        schema_name: schema,
        table_name: table,
      });
      onConnected(dataset.id);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (connectionId) {
    return (
      <section className="supabase-panel">
        <div className="supabase-panel-head">
          <span className="supabase-mark"><CheckCircle2 size={19} /></span>
          <div><strong>Supabase connected</strong><span>Select one accessible table to register as a live dataset.</span></div>
        </div>

        {error && <div className="opendosm-error">{error}</div>}

        <div className="supabase-resource-grid">
          <label>
            <span>Schema</span>
            <select value={schema} onChange={(event) => setSchema(event.target.value)} disabled={busy}>
              {schemas.map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}
            </select>
          </label>
          <label>
            <span>Table or view</span>
            <select value={table} onChange={(event) => setTable(event.target.value)} disabled={busy || loadingTables}>
              {tables.map((item) => (
                <option key={item.name} value={item.name}>
                  {item.name} · {item.kind}{item.estimated_rows ? ` · ~${item.estimated_rows.toLocaleString()} rows` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="supabase-note">
          <Cloud size={16} />
          Data stays in Supabase. Data-Berge stores schema metadata and queries bounded results on demand.
        </div>

        <button className="supabase-primary" type="button" onClick={register} disabled={busy || loadingTables || !table}>
          {busy ? <Loader className="spinner" size={14} /> : <Table2 size={14} />}
          {busy ? 'Profiling...' : 'Use table'}
        </button>
      </section>
    );
  }

  return (
    <form className="supabase-panel" onSubmit={connect}>
      <div className="supabase-panel-head">
        <span className="supabase-mark"><Database size={19} /></span>
        <div><strong>Supabase database</strong><span>Use a dedicated read-only PostgreSQL user.</span></div>
      </div>

      {error && <div className="opendosm-error">{error}</div>}

      <div className="supabase-form-grid">
        <label className="wide"><span>Connection name</span><input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required /></label>
        <label className="wide"><span>Database host</span><input value={form.host} onChange={(event) => setForm({ ...form, host: event.target.value })} placeholder="db.your-project.supabase.co" autoComplete="off" required /></label>
        <label><span>Port</span><input type="number" min="1" max="65535" value={form.port} onChange={(event) => setForm({ ...form, port: event.target.value })} required /></label>
        <label><span>Database</span><input value={form.database} onChange={(event) => setForm({ ...form, database: event.target.value })} required /></label>
        <label><span>Username</span><input value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} autoComplete="username" required /></label>
        <label><span>Password</span><input type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} autoComplete="new-password" required /></label>
      </div>

      <div className="supabase-note"><Cloud size={16} />SSL is required. Credentials are encrypted before being stored.</div>
      <button className="supabase-primary" type="submit" disabled={busy}>
        {busy ? <Loader className="spinner" size={14} /> : <Database size={14} />}
        {busy ? 'Testing...' : 'Test connection'}
      </button>
    </form>
  );
}
