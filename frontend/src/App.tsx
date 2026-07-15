import { Component, ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Database, EllipsisVertical, FileText, Link2, Loader, LogOut, MessageSquare, RefreshCw, Trash2, UserRound } from 'lucide-react';

import { ChatExplorer } from './components/ChatExplorer';
import { LandingPage, type LandingStep } from './components/LandingPage';
import { ProfileView } from './components/ProfileView';
import { RelationshipEditor } from './components/RelationshipEditor';
import { ReportBuilder } from './components/ReportBuilder';
import { deleteDataset, deleteRelationalSchema, getOverview, getProjects, getRelationalSchema, listRelationalSchemas, uploadDataset, uploadRelationalSchema } from './services/api';
import { Artifact, ChatAttachment, Dataset, Overview, Project, RelationalSchema, ReportPlan } from './types/domain';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { LoginPage } from './components/LoginPage';
import {
  addChatAttachment,
  reportAttachment,
  resolveWorkspaceSelection,
  schemaAsDataset,
  type WorkspaceKind,
} from './utils/workspace';

type Tab = 'profile' | 'chat' | 'report' | 'datamodel';
type AppRoute = 'main' | 'login' | 'signup' | 'upload' | 'workspace';

const routePath = (route: AppRoute) => (route === 'main' ? '/main' : `/${route}`);

const normalizeRoute = (pathname: string): AppRoute => {
  const clean = pathname.replace(/\/+$/, '') || '/';
  if (clean === '/' || clean === '/main') return 'main';
  if (clean === '/login') return 'login';
  if (clean === '/signup') return 'signup';
  if (clean === '/upload') return 'upload';
  if (clean === '/workspace') return 'workspace';
  return 'main';
};

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => normalizeRoute(window.location.pathname));

  const navigate = useCallback((nextRoute: AppRoute, options?: { replace?: boolean }) => {
    const nextPath = routePath(nextRoute);
    if (window.location.pathname !== nextPath) {
      if (options?.replace) {
        window.history.replaceState(null, '', nextPath);
      } else {
        window.history.pushState(null, '', nextPath);
      }
    }
    setRoute(nextRoute);
  }, []);

  useEffect(() => {
    const handlePopState = () => setRoute(normalizeRoute(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    const clean = window.location.pathname.replace(/\/+$/, '') || '/';
    const canonicalPath = routePath(route);
    if (clean !== canonicalPath) {
      window.history.replaceState(null, '', canonicalPath);
    }
  }, [route]);

  return (
    <AuthProvider>
      <AppErrorBoundary>
        <AppShell route={route} navigate={navigate} />
      </AppErrorBoundary>
    </AuthProvider>
  );
}

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error('Data-Berge render error', error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="empty-app" style={{ display: 'grid', placeItems: 'center', minHeight: '100vh', padding: 24 }}>
          <div className="error-banner" style={{ maxWidth: 720 }}>
            Something on this page could not render: {this.state.error.message || 'Unexpected UI payload.'}
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

function AppShell({ route, navigate }: { route: AppRoute; navigate: (route: AppRoute, options?: { replace?: boolean }) => void }) {
  const { user, loading, logout } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (!user && route !== 'main' && route !== 'login' && route !== 'signup') {
      navigate('login', { replace: true });
      return;
    }
    if (user && (route === 'login' || route === 'signup')) {
      navigate('workspace', { replace: true });
    }
  }, [loading, navigate, route, user]);

  if (loading) return <div className="empty-app" style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}><Loader className="spinner" /></div>;
  if (route === 'main') {
    return (
      <LandingPage
        busy={false}
        onUpload={async () => navigate(user ? 'upload' : 'login')}
        onGetStarted={() => navigate(user ? 'upload' : 'login')}
        onLogin={() => navigate('login')}
        onSignUp={() => navigate('signup')}
      />
    );
  }
  if (!user) {
    return (
      <LoginPage
        initialMode={route === 'signup' ? 'register' : 'login'}
        onModeChange={(mode) => navigate(mode === 'register' ? 'signup' : 'login')}
        onBackHome={() => navigate('main')}
      />
    );
  }
  return (
    <AuthenticatedApp
      route={route === 'login' || route === 'signup' ? 'workspace' : route}
      navigate={navigate}
      onLogout={() => {
        logout();
        navigate('login', { replace: true });
      }}
      userName={user.name}
    />
  );
}

function AuthenticatedApp({
  route,
  navigate,
  onLogout,
  userName,
}: {
  route: 'upload' | 'workspace';
  navigate: (route: AppRoute, options?: { replace?: boolean }) => void;
  onLogout: () => void;
  userName: string;
}) {
  const [project, setProject] = useState<Project | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('profile');
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [relationalSchemas, setRelationalSchemas] = useState<RelationalSchema[]>([]);
  const [activeSchemaId, setActiveSchemaId] = useState<string | null>(null);
  const [activeWorkspaceKind, setActiveWorkspaceKind] = useState<WorkspaceKind>('dataset');
  const [datasetMenuOpen, setDatasetMenuOpen] = useState(false);
  const [deleteDialog, setDeleteDialog] = useState<{
    kind: 'dataset' | 'schema';
    name: string;
  } | null>(null);
  const [previewMode, setPreviewMode] = useState(false);
  const [reviewReturnStep, setReviewReturnStep] = useState<LandingStep>('setup');
  const [pendingReportPlan, setPendingReportPlan] = useState<ReportPlan | null>(null);
  const [openChatSessionId, setOpenChatSessionId] = useState<string | null>(null);
  const [pendingReportArtifact, setPendingReportArtifact] = useState<Artifact | null>(null);
  const [chatAttachments, setChatAttachments] = useState<ChatAttachment[]>([]);
  const MAX_ATTACHMENTS = 3;
  const datasetMenuRef = useRef<HTMLDivElement | null>(null);

  const selectedDataset = useMemo<Dataset | null>(() => {
    if (!overview || !selectedDatasetId) return null;
    return overview.datasets.find((dataset) => dataset.id === selectedDatasetId) ?? null;
  }, [overview, selectedDatasetId]);

  useEffect(() => {
    const handlePointerDown = (event: MouseEvent) => {
      if (!datasetMenuRef.current?.contains(event.target as Node)) {
        setDatasetMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handlePointerDown);
    return () => document.removeEventListener('mousedown', handlePointerDown);
  }, []);

  const load = async (
    preferredDatasetId: string | null | undefined = undefined,
    preferredSchemaId: string | null | undefined = undefined,
    preferredWorkspaceKind?: WorkspaceKind,
  ) => {
    try {
      setError(null);
      const projects = await getProjects();
      const activeProject = projects[0];
      if (!activeProject) {
        setProject(null);
        setOverview(null);
        setRelationalSchemas([]);
        setSelectedDatasetId(null);
        setActiveSchemaId(null);
        return;
      }
      setProject(activeProject);
      const nextSchemas = await listRelationalSchemas(activeProject.id).catch(() => [] as RelationalSchema[]);
      const nextOverview = await getOverview(activeProject.id);
      const { datasetId: nextDatasetId, schemaId: nextSchemaId, workspaceKind: nextWorkspaceKind } = resolveWorkspaceSelection({
        preferredDatasetId,
        preferredSchemaId,
        preferredWorkspaceKind,
        activeSchemaId,
        selectedDatasetId,
        activeWorkspaceKind,
        schemas: nextSchemas,
        overview: nextOverview,
      });
      const hydratedSchemas =
        nextSchemaId
          ? await hydrateActiveSchema(activeProject.id, nextSchemas, nextSchemaId)
          : nextSchemas;
      setOverview(nextOverview);
      setRelationalSchemas(hydratedSchemas);
      setSelectedDatasetId(nextDatasetId);
      setActiveSchemaId(nextSchemaId);
      setActiveWorkspaceKind(nextWorkspaceKind);
      if (!nextDatasetId && !nextSchemaId) {
        setActiveTab('profile');
      } else if (!nextSchemaId && activeTab === 'datamodel') {
        setActiveTab('profile');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load workspace.');
    } finally {
      setLoaded(true);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const loadRelationalSchemas = async (projectId: string) => {
    try {
      const schemas = await listRelationalSchemas(projectId);
      setRelationalSchemas(schemas);
      if (schemas.length > 0 && !activeSchemaId) {
        setActiveSchemaId(schemas[0].id);
      }
    } catch {
      // Silently fail — relational schemas are optional
    }
  };

  const hydrateActiveSchema = async (
    projectId: string,
    schemas: RelationalSchema[],
    schemaId: string,
  ): Promise<RelationalSchema[]> => {
    try {
      const detail = await getRelationalSchema(projectId, schemaId);
      return schemas.map((schema) => (schema.id === schemaId ? detail : schema));
    } catch {
      return schemas;
    }
  };

  const handleUpload = async (file: File) => {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const lower = file.name.toLowerCase();
      const usesDataModel = lower.endsWith('.csv') || lower.endsWith('.xlsx') || lower.endsWith('.xls');
      if (usesDataModel) {
        const schema = await uploadRelationalSchema(project.id, file);
        setReviewReturnStep('file-upload');
        setPreviewMode(true);
        setRelationalSchemas((prev) => [schema, ...prev.filter((item) => item.id !== schema.id)]);
        setSelectedDatasetId(null);
        setActiveSchemaId(schema.id);
        setActiveWorkspaceKind('schema');
        setActiveTab('datamodel');
        await load(null, schema.id, 'schema');
        return;
      }
      const dataset = await uploadDataset(project.id, file);
      setPreviewMode(true);
      setSelectedDatasetId(dataset.id);
      setActiveWorkspaceKind('dataset');
      setActiveTab('profile');
      await load(dataset.id, activeSchemaId, 'dataset');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setBusy(false);
    }
  };

  const executeDeleteDataset = async () => {
    if (!project || !selectedDataset) return;
    const deletedDatasetId = selectedDataset.id;
    const deletedLinkedSchema = activeSchemaId === deletedDatasetId;
    setBusy(true);
    setError(null);
    try {
      await deleteDataset(project.id, deletedDatasetId);
      setSelectedDatasetId(null);
      if (deletedLinkedSchema) {
        setActiveSchemaId(null);
        setRelationalSchemas((prev) => prev.filter((schema) => schema.id !== deletedDatasetId));
      }
      setActiveWorkspaceKind('dataset');
      setActiveTab('profile');
      await load(undefined, undefined, 'dataset');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  };

  const executeDeleteSchema = async () => {
    if (!project || !activeSchema) return;
    setBusy(true);
    setError(null);
    try {
      await deleteRelationalSchema(project.id, activeSchema.id);
      const remaining = relationalSchemas.filter((schema) => schema.id !== activeSchema.id);
      setRelationalSchemas(remaining);
      setActiveSchemaId(remaining[0]?.id ?? null);
      if (remaining.length === 0) {
        setActiveWorkspaceKind('dataset');
        setActiveTab('profile');
      }
      await load(
        remaining.length > 0 ? null : undefined,
        remaining[0]?.id ?? null,
        remaining.length > 0 ? 'schema' : 'dataset',
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed.');
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteDataset = () => {
    if (!selectedDataset) return;
    setDeleteDialog({
      kind: 'dataset',
      name: selectedDataset.name,
    });
  };

  const handleDeleteSchema = () => {
    if (!activeSchema) return;
    setDeleteDialog({
      kind: 'schema',
      name: activeSchema.name,
    });
  };

  const confirmDelete = async () => {
    if (!deleteDialog) return;
    const kind = deleteDialog.kind;
    setDeleteDialog(null);
    if (kind === 'dataset') {
      await executeDeleteDataset();
      return;
    }
    await executeDeleteSchema();
  };

  const reports = (overview?.artifacts ?? []).filter((artifact) => artifact.kind === 'report');
  const activeSchema = activeSchemaId
    ? relationalSchemas.find((s) => s.id === activeSchemaId) ?? null
    : null;
  const schemaMode = Boolean(activeSchema && activeWorkspaceKind === 'schema');
  // Build a virtual dataset from schema so chat/report/profile can work for both single-table and multi-table.
  const activeDatasetForTools = selectedDataset ?? schemaAsDataset(activeSchema);
  const showingSchemaSummary = Boolean(activeSchema && (activeTab === 'datamodel' || schemaMode || !selectedDataset));
  const canShowDataPulse = Boolean(activeDatasetForTools || activeSchema);

  const sendReportToChat = async (artifact: Artifact) => {
    const attachment = reportAttachment(artifact);
    setChatAttachments((previous) => {
      return addChatAttachment(previous, attachment, MAX_ATTACHMENTS);
    });
    setActiveTab('chat');
  };

  const hasRelationalSchemas = relationalSchemas.length > 0;
  const openDataModel = () => {
    if (activeSchema && overview?.datasets.some((dataset) => dataset.id === activeSchema.id)) {
      setSelectedDatasetId(activeSchema.id);
    } else {
      setSelectedDatasetId(null);
    }
    setActiveWorkspaceKind('schema');
    setActiveTab('datamodel');
    setDatasetMenuOpen(false);
  };

  useEffect(() => {
    if (!loaded || route !== 'workspace') return;
    if (!selectedDataset && !hasRelationalSchemas) {
      navigate('upload', { replace: true });
    }
  }, [hasRelationalSchemas, loaded, navigate, route, selectedDataset]);

  if (!loaded) {
    return (
      <div className="empty-app" style={{ display: 'grid', placeItems: 'center', minHeight: '100vh' }}>
        <Loader className="spinner" />
      </div>
    );
  }

  if (route === 'upload' || (!selectedDataset && !hasRelationalSchemas)) {
    if (previewMode && activeSchema && project) {
      return (
        <div className="preview-page">
          <div className="preview-scroll">
            <div className="preview-card">
              <RelationshipEditor
                schema={activeSchema}
                projectId={project.id}
                showEnterWorkspaceAction
                onCancelReview={async () => {
                  if (!project || !activeSchema) return;
                  setBusy(true);
                  setError(null);
                  try {
                    await deleteRelationalSchema(project.id, activeSchema.id);
                    setRelationalSchemas((prev) => prev.filter((schema) => schema.id !== activeSchema.id));
                    setActiveSchemaId(null);
                    setSelectedDatasetId(null);
                    setActiveWorkspaceKind('dataset');
                    setActiveTab('profile');
                    setPreviewMode(false);
                    await load(null, null, 'dataset');
                    navigate('upload');
                  } catch (err) {
                    setError(err instanceof Error ? err.message : 'Cancel failed.');
                  } finally {
                    setBusy(false);
                  }
                }}
                onSchemaUpdated={(updated) => {
                  setRelationalSchemas((prev) =>
                    prev.map((s) => (s.id === updated.id ? updated : s)),
                  );
                }}
                onRelationshipsConfirmed={async (updated) => {
                  setRelationalSchemas((prev) =>
                    prev.map((s) => (s.id === updated.id ? updated : s)),
                  );
                  setActiveSchemaId(updated.id);
                  setActiveTab('profile');
                  const isSingleTableModel = Object.keys(updated.schema.tables).length === 1;
                  setSelectedDatasetId(updated.id);
                  if (isSingleTableModel) {
                    setActiveWorkspaceKind('dataset');
                    await load(updated.id, updated.id, 'dataset');
                  } else {
                    setActiveWorkspaceKind('schema');
                    await load(updated.id, updated.id, 'schema');
                  }
                  setPreviewMode(false);
                  navigate('workspace');
                }}
              />
            </div>
          </div>
        </div>
      );
    }

    return (
      <div className="app-shell empty-app">
        {error && (
          <div style={{ position: 'fixed', top: 16, left: '50%', transform: 'translateX(-50%)', zIndex: 100 }}>
            <div className="error-banner">{error}</div>
          </div>
        )}
        <LandingPage
          busy={busy}
          onUpload={handleUpload}
          projectId={project?.id}
          initialStep={reviewReturnStep}
          onBackHome={() => navigate('main')}
          onOpenDOSMConnected={async (schemaId) => {
            setReviewReturnStep('dosm-connect');
            setPreviewMode(true);
            setSelectedDatasetId(null);
            setActiveSchemaId(schemaId);
            setActiveWorkspaceKind('schema');
            setActiveTab('datamodel');
            await load(null, schemaId, 'schema');
          }}
        />
      </div>
    );
  }

  return (
    <div className="app-shell has-data">
      {deleteDialog && (
        <div className="app-modal-backdrop" onClick={() => setDeleteDialog(null)}>
          <div className="app-modal" onClick={(event) => event.stopPropagation()}>
            <div className="app-modal-copy">
              <span className="app-modal-eyebrow">Confirm delete</span>
              <h3>{deleteDialog.name}</h3>
              <p>
                {deleteDialog.kind === 'schema'
                  ? 'This will remove the active relationship model and its generated dataset artifacts.'
                  : 'This will remove the active dataset and its generated artifacts.'}
              </p>
            </div>
            <div className="app-modal-actions">
              <button className="app-modal-cancel" onClick={() => setDeleteDialog(null)} disabled={busy}>
                Cancel
              </button>
              <button className="app-modal-danger" onClick={confirmDelete} disabled={busy}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-brand">
            <div className="brand-mark" aria-hidden="true">
              <img src="/favicon.svg" alt="" />
            </div>
            <div className="brand-copy">
              <strong>Data-Berge</strong>
            </div>
          </div>

          <div className="sidebar-section">
            <span className="sidebar-section-label">Main</span>
            <nav className="sidebar-nav">
              <button
                className={activeTab === 'profile' ? 'active' : ''}
                onClick={() => setActiveTab('profile')}
                disabled={!canShowDataPulse}
                title={!canShowDataPulse ? 'Upload a dataset to enable' : undefined}
              >
                <Database size={18} />
                <span>Data Pulse</span>
              </button>
              <button
                className={activeTab === 'chat' ? 'active' : ''}
                onClick={() => setActiveTab('chat')}
                disabled={!activeDatasetForTools}
                title={!activeDatasetForTools ? 'Upload a dataset or schema to enable.' : undefined}
              >
                <MessageSquare size={18} />
                <span>Explorer</span>
              </button>
              <button
                className={activeTab === 'report' ? 'active' : ''}
                onClick={() => setActiveTab('report')}
                disabled={!activeDatasetForTools}
                title={!activeDatasetForTools ? 'Upload a dataset or schema to enable.' : undefined}
              >
                <FileText size={18} />
                <span>Executive Report</span>
              </button>
            </nav>
          </div>

          <div className="sidebar-divider" />

          <div className="sidebar-section sidebar-dataset-card">
            <span className="sidebar-section-label">Active Dataset</span>
            <div className="dataset-summary-card">
              <div className="dataset-summary">
                {showingSchemaSummary && activeSchema ? (
                  <>
                    <strong title={activeSchema.name}>{activeSchema.name}</strong>
                  </>
                ) : selectedDataset ? (
                  <>
                    <strong title={selectedDataset.name}>{selectedDataset.name}</strong>
                  </>
                ) : null}
              </div>
              <div className="dataset-menu-shell" ref={datasetMenuRef}>
                <button
                  className="dataset-inline-action"
                  onClick={() => setDatasetMenuOpen((open) => !open)}
                  title="Workspace actions"
                  aria-label="Workspace actions"
                >
                  <EllipsisVertical size={14} />
                </button>
                {datasetMenuOpen && (
                  <div className="dataset-action-menu">
                    {hasRelationalSchemas && (
                      <button className="dataset-action-item" onClick={openDataModel}>
                        <Link2 size={14} />
                        <span>Data Model</span>
                      </button>
                    )}
                    <button className="dataset-action-item" onClick={() => { setDatasetMenuOpen(false); load(); if (project) loadRelationalSchemas(project.id); }}>
                      <RefreshCw size={14} />
                      <span>Refresh</span>
                    </button>
                    {showingSchemaSummary && activeSchema ? (
                      <button
                        className="dataset-action-item danger"
                        onClick={() => { setDatasetMenuOpen(false); handleDeleteSchema(); }}
                        disabled={busy}
                      >
                        <Trash2 size={14} />
                        <span>Delete</span>
                      </button>
                    ) : selectedDataset && (
                      <button
                        className="dataset-action-item danger"
                        onClick={() => { setDatasetMenuOpen(false); handleDeleteDataset(); }}
                        disabled={busy}
                      >
                        <Trash2 size={14} />
                        <span>Delete</span>
                      </button>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="sidebar-bottom-user">
            <div className="sidebar-user-card">
              <div className="sidebar-user-avatar" aria-hidden="true">
                <UserRound size={14} />
              </div>
              <div className="sidebar-user-copy">
                <span className="sidebar-user-label">Profile</span>
                <strong title={userName}>{userName}</strong>
              </div>
            </div>
            <button className="sidebar-ghost-action" onClick={onLogout} title="Sign out">
              <LogOut size={14} />
            </button>
          </div>
        </aside>

        <main className="main-shell">
          {error && <div className="error-banner">{error}</div>}

            <div className="workspace-grid">
            <div className="primary-column">
              <div className="tab-panel" hidden={activeTab !== 'profile'}>
                <ProfileView dataset={activeDatasetForTools} schema={schemaMode ? activeSchema : null} onAskInChat={(label, context) => {
                  setChatAttachments((prev) => {
                    return addChatAttachment(prev, { label, context }, MAX_ATTACHMENTS);
                  });
                  setActiveTab('chat');
                }} />
              </div>
              <div className="tab-panel" hidden={activeTab !== 'chat'}>
                <ChatExplorer
                  project={project}
                  dataset={activeDatasetForTools}
                  onArtifactCreated={load}
                  onReportSaved={() => setActiveTab('report')}
                  onCustomizeReportPlan={(plan) => {
                    setPendingReportPlan(plan);
                    setActiveTab('report');
                  }}
                  onOpenReport={async (artifact) => {
                    await load();
                    setPendingReportArtifact(artifact);
                  }}
                  openSessionId={openChatSessionId}
                  onOpenSessionConsumed={() => setOpenChatSessionId(null)}
                  attachments={chatAttachments}
                  onAttachmentRemove={(idx) => setChatAttachments((prev) => prev.filter((_, i) => i !== idx))}
                  onAttachmentsClear={() => setChatAttachments([])}
                  maxAttachments={MAX_ATTACHMENTS}
                />
              </div>
              <div className="tab-panel" hidden={activeTab !== 'report'}>
                <ReportBuilder
                  project={project}
                  dataset={activeDatasetForTools}
                  reports={reports}
                  onChanged={load}
                  onSendToChat={sendReportToChat}
                  initialPlan={pendingReportPlan}
                  onInitialPlanConsumed={() => setPendingReportPlan(null)}
                  initialReport={pendingReportArtifact}
                  onInitialReportConsumed={() => setPendingReportArtifact(null)}
                  onInitialReportClosed={() => setActiveTab('chat')}
                />
              </div>
              {activeTab === 'datamodel' && activeSchema && project && (
                <RelationshipEditor
                  schema={activeSchema}
                  projectId={project.id}
                  onSchemaUpdated={(updated: RelationalSchema) => {
                    setRelationalSchemas((prev) =>
                      prev.map((s) => (s.id === updated.id ? updated : s)),
                    );
                  }}
                  onRelationshipsConfirmed={async (updated: RelationalSchema) => {
                    setRelationalSchemas((prev) =>
                      prev.map((s) => (s.id === updated.id ? updated : s)),
                    );
                    setActiveSchemaId(updated.id);
                    setActiveTab('profile');
                    const isSingleTableModel = Object.keys(updated.schema.tables).length === 1;
                    setSelectedDatasetId(updated.id);
                    if (isSingleTableModel) {
                      setActiveWorkspaceKind('dataset');
                      await load(updated.id, updated.id, 'dataset');
                    } else {
                      setActiveWorkspaceKind('schema');
                      await load(updated.id, updated.id, 'schema');
                    }
                  }}
                />
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
