import { FormEvent, useEffect, useMemo, useState } from 'react';
import {
  ChevronDown,
  Copy,
  FilePlus2,
  FileText,
  Library,
  LoaderCircle,
  MoveDown,
  MoveUp,
  Plus,
  Save,
  Settings2,
  Trash2,
  X,
} from 'lucide-react';

import {
  createCustomReportType,
  createReport,
  deleteArtifact,
  deleteCustomReportType,
  listCustomReportTypes,
  updateCustomReportType,
} from '../services/api';
import { Artifact, CustomReportType, Dataset, Project, ReportPlan, ReportSectionKind, ReportTypeSection } from '../types/domain';
import {
  draftFromPlan,
  draftFromType,
  newReportSection,
  SECTION_KINDS,
  TEMPLATE_BLOCKS,
  TEMPLATE_LABELS,
  type ReportTypeDraft,
} from './report/reportConfig';
import { FullReportModal, isReportGenerating, ReportLibraryRow } from './report/ReportReader';
import { ConfirmDialog } from './ConfirmDialog';

type DeleteTarget =
  | { kind: 'report'; artifact: Artifact }
  | { kind: 'report_type'; reportType: CustomReportType };

type ReportBuilderProps = {
  project: Project | null;
  dataset: Dataset | null;
  reports: Artifact[];
  onChanged: () => void;
  onSendToChat?: (artifact: Artifact) => void | Promise<void>;
  initialPlan?: ReportPlan | null;
  onInitialPlanConsumed?: () => void;
  initialReport?: Artifact | null;
  onInitialReportConsumed?: () => void;
  onInitialReportClosed?: () => void;
};

export function ReportBuilder({ project, dataset, reports, onChanged, onSendToChat, initialPlan, onInitialPlanConsumed, initialReport, onInitialReportConsumed, onInitialReportClosed }: ReportBuilderProps) {
  const [audience, setAudience] = useState('Leadership team');
  const [goal, setGoal] = useState('Identify risks, opportunities, and next actions');
  const [busy, setBusy] = useState(false);
  const [openReport, setOpenReport] = useState<Artifact | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [customTypes, setCustomTypes] = useState<CustomReportType[]>([]);
  const [selectedType, setSelectedType] = useState('executive');
  const [typeEditorOpen, setTypeEditorOpen] = useState(false);
  const [editingType, setEditingType] = useState<CustomReportType | null>(null);
  const [editorSourceType, setEditorSourceType] = useState<CustomReportType | null>(null);
  const [editorDraftOverride, setEditorDraftOverride] = useState<ReportTypeDraft | null>(null);
  const [editorFromChat, setEditorFromChat] = useState(false);
  const [typeBusy, setTypeBusy] = useState(false);
  const [typeError, setTypeError] = useState<string | null>(null);
  const [sendBusy, setSendBusy] = useState<string | null>(null);
  const [returnToChatOnClose, setReturnToChatOnClose] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DeleteTarget | null>(null);

  const hasGeneratingReports = reports.some(isReportGenerating);
  const activeCustomType = customTypes.find((reportType) => selectedType === `custom:${reportType.id}`) || null;
  const activeBlocks = activeCustomType
    ? activeCustomType.payload.sections.map((section) => section.key)
    : (TEMPLATE_BLOCKS[selectedType] || TEMPLATE_BLOCKS.executive).map((block) => block.key);
  const orderedReports = useMemo(
    () => [...reports].sort((left, right) => (
      new Date(right.updated_at || right.created_at).getTime()
      - new Date(left.updated_at || left.created_at).getTime()
    )),
    [reports],
  );

  useEffect(() => {
    if (!project || !hasGeneratingReports) return;
    const interval = window.setInterval(onChanged, 60_000);
    return () => window.clearInterval(interval);
  }, [hasGeneratingReports, onChanged, project]);

  useEffect(() => {
    let cancelled = false;
    if (!project || !dataset) {
      setCustomTypes([]);
      setSelectedType('executive');
      return () => { cancelled = true; };
    }
    listCustomReportTypes(project.id, dataset.id)
      .then((types) => {
        if (cancelled) return;
        setCustomTypes(types);
        const defaultType = types.find((type) => type.is_default);
        setSelectedType(defaultType ? `custom:${defaultType.id}` : 'executive');
        if (defaultType) {
          setAudience(defaultType.payload.audience);
          setGoal(defaultType.payload.goal);
        }
      })
      .catch(() => {
        if (!cancelled) setCustomTypes([]);
      });
    return () => { cancelled = true; };
  }, [dataset?.id, project?.id]);

  useEffect(() => {
    if (!initialPlan || !dataset) return;
    setEditingType(null);
    setEditorSourceType(null);
    setEditorDraftOverride(draftFromPlan(initialPlan));
    setEditorFromChat(true);
    setTypeError(null);
    setTypeEditorOpen(true);
    onInitialPlanConsumed?.();
  }, [dataset?.id, initialPlan?.plan_id]);

  useEffect(() => {
    if (!initialReport) return;
    setReturnToChatOnClose(true);
    setOpenReport(initialReport);
    onInitialReportConsumed?.();
  }, [initialReport?.id]);

  const handleTemplateChange = (template: string) => {
    if (template === '__create_custom__') {
      setEditingType(null);
      setEditorSourceType(null);
      setEditorDraftOverride(null);
      setEditorFromChat(false);
      setTypeError(null);
      setTypeEditorOpen(true);
      return;
    }
    setSelectedType(template);
    const nextType = customTypes.find((reportType) => template === `custom:${reportType.id}`);
    if (nextType) {
      setAudience(nextType.payload.audience);
      setGoal(nextType.payload.goal);
    }
  };

  const openTypeEditor = (reportType: CustomReportType | null, sourceType = reportType) => {
    setEditingType(reportType);
    setEditorSourceType(sourceType);
    setEditorDraftOverride(null);
    setEditorFromChat(false);
    setTypeError(null);
    setTypeEditorOpen(true);
  };

  const saveReportType = async (draft: ReportTypeDraft) => {
    if (!project || !dataset) return;
    setTypeBusy(true);
    setTypeError(null);
    const payload = {
      name: draft.name.trim(),
      description: draft.description.trim(),
      audience: draft.audience.trim(),
      goal: draft.goal.trim(),
      horizon: draft.horizon.trim(),
      tone: draft.tone,
      focus_areas: draft.focus_areas.split(',').map((item) => item.trim()).filter(Boolean),
      sections: draft.sections.map((section) => ({
        ...section,
        label: section.label.trim(),
        description: section.description?.trim() || '',
        data_fields: section.data_fields.map((field) => field.trim()).filter(Boolean),
        chart_intent: section.chart_intent?.trim() || '',
      })),
      visual_style: draft.visual_style,
      is_default: draft.is_default,
    };
    if (!payload.name || !payload.sections.length || payload.sections.some((section) => !section.label)) {
      setTypeError('Add a name and at least one named section before saving.');
      setTypeBusy(false);
      return;
    }
    try {
      const saved = editingType
        ? await updateCustomReportType(project.id, editingType.id, payload)
        : await createCustomReportType(project.id, { dataset_id: dataset.id, ...payload });
      setCustomTypes((current) => editingType
        ? current.map((item) => item.id === saved.id ? saved : (saved.is_default ? { ...item, is_default: false } : item))
        : [saved, ...(saved.is_default ? current.map((item) => ({ ...item, is_default: false })) : current)]);
      setSelectedType(`custom:${saved.id}`);
      setAudience(saved.payload.audience);
      setGoal(saved.payload.goal);
      setEditorDraftOverride(null);
      setEditorFromChat(false);
      setTypeEditorOpen(false);
    } catch (error) {
      setTypeError(error instanceof Error ? error.message : 'Could not save report type.');
    } finally {
      setTypeBusy(false);
    }
  };

  const removeReportType = async (reportType: CustomReportType) => {
    if (!project) return;
    setTypeBusy(true);
    try {
      await deleteCustomReportType(project.id, reportType.id);
      setCustomTypes((current) => current.filter((item) => item.id !== reportType.id));
      setSelectedType('executive');
      setEditorDraftOverride(null);
      setEditorFromChat(false);
      setTypeEditorOpen(false);
    } catch (error) {
      setTypeError(error instanceof Error ? error.message : 'Could not delete report type.');
    } finally {
      setTypeBusy(false);
    }
  };

  const generateDraft = async () => {
    if (busy) return;
    if (!project) {
      setFormError('No active project is loaded.');
      return;
    }
    if (!dataset) {
      setFormError('Select a dataset or data model first.');
      return;
    }
    setBusy(true);
    setFormError(null);
    try {
      await createReport(project.id, {
        dataset_id: dataset.id,
        audience,
        goal,
        horizon: activeCustomType?.payload.horizon || 'Next quarter',
        tone: activeCustomType?.payload.tone || 'Strategic',
        focus_areas: activeCustomType?.payload.focus_areas || ['growth', 'risk', 'quality'],
        template: activeCustomType ? 'custom' : selectedType,
        report_type: activeCustomType ? activeCustomType.name : TEMPLATE_LABELS[selectedType],
        blocks: activeBlocks,
        custom_blocks: activeCustomType?.payload.sections || null,
      });
      onChanged();
    } catch (error) {
      setFormError(error instanceof Error ? error.message : 'Report generation failed.');
    } finally {
      setBusy(false);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    await generateDraft();
  };

  const deleteReport = async (artifact: Artifact) => {
    if (!project || actionBusy) return;
    setActionBusy(artifact.id);
    try {
      await deleteArtifact(project.id, artifact.id);
      if (openReport?.id === artifact.id) closeOpenReport();
      await onChanged();
    } catch {
      setFormError('Report could not be deleted.');
    } finally {
      setActionBusy(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const target = deleteTarget;
    if (target.kind === 'report') {
      await deleteReport(target.artifact);
    } else {
      await removeReportType(target.reportType);
    }
    setDeleteTarget(null);
  };

  const closeOpenReport = () => {
    const shouldReturnToChat = returnToChatOnClose;
    setOpenReport(null);
    setReturnToChatOnClose(false);
    if (shouldReturnToChat) onInitialReportClosed?.();
  };

  const sendReportToChat = async (artifact: Artifact) => {
    if (!onSendToChat || sendBusy) return;
    setSendBusy(artifact.id);
    try {
      await onSendToChat(artifact);
      setOpenReport(null);
    } finally {
      setSendBusy(null);
    }
  };

  return (
    <section className="report-panel report-workspace-page">
      <div className="section-title tab-header">
        <div>
          <h2>Executive Report</h2>
          <p className="section-subcopy">
            Engineer validates readiness, Analyst establishes evidence, and Reporter composes the final document.
          </p>
        </div>
      </div>
      <div className="section-divider" />

      <div className="report-workspace-layout">
        <aside className="report-compose-panel">
          <div className="report-compose-head">
            <span className="report-compose-icon"><FilePlus2 size={17} /></span>
            <div>
              <h3>Create report</h3>
              <p>{activeCustomType?.name || TEMPLATE_LABELS[selectedType]}</p>
            </div>
          </div>

          <form onSubmit={submit} className="report-generate-form">
            <label className="report-field">
              <span>Audience</span>
              <input value={audience} onChange={(event) => setAudience(event.target.value)} />
            </label>
            <label className="report-field">
              <span>Decision goal</span>
              <textarea
                value={goal}
                rows={3}
                onChange={(event) => setGoal(event.target.value)}
              />
            </label>
            <label className="report-field">
              <span>Report type</span>
              <select
                value={selectedType}
                onChange={(event) => handleTemplateChange(event.target.value)}
                className="report-template-select"
              >
                <option value="executive">Executive Report</option>
                <option value="research">Research Report</option>
                <option value="technical">Technical Report</option>
                <option value="quick_brief">Quick Brief</option>
                {customTypes.length > 0 && <optgroup label="Saved custom types">
                  {customTypes.map((reportType) => (
                    <option key={reportType.id} value={`custom:${reportType.id}`}>{reportType.name}</option>
                  ))}
                </optgroup>}
                <option value="__create_custom__">Create custom report type...</option>
              </select>
            </label>

            <div className="report-type-actions">
              <button type="button" className="report-secondary-btn" onClick={() => openTypeEditor(activeCustomType)}>
                <Settings2 size={14} />{activeCustomType ? 'Edit type' : 'Customize'}
              </button>
              {activeCustomType && <button
                type="button"
                className="report-icon-btn neutral"
                title="Duplicate custom report type"
                aria-label="Duplicate custom report type"
                onClick={() => openTypeEditor(null, activeCustomType)}
              >
                <Copy size={14} />
              </button>}
            </div>

            {formError && <div className="report-form-error">{formError}</div>}
            <button
              type="submit"
              className="report-primary-btn report-generate-submit"
              disabled={busy || !dataset || !project}
              title={!dataset ? 'Select a dataset or data model first.' : 'Generate report'}
            >
              {busy ? <LoaderCircle className="report-spinner" size={15} /> : <FilePlus2 size={15} />}
              {busy ? 'Queueing' : 'Generate report'}
            </button>
          </form>
        </aside>

        <section className="report-library-panel">
          <header className="report-library-head">
            <div>
              <span className="report-library-icon"><Library size={16} /></span>
              <div>
                <h3>Report library</h3>
                <p>{reports.length} reports</p>
              </div>
            </div>
          </header>

          <div className={`report-library-list ${orderedReports.length === 0 ? 'empty' : ''}`}>
            {orderedReports.length ? orderedReports.map((report) => (
              <ReportLibraryRow
                key={report.id}
                report={report}
                actionBusy={actionBusy === report.id}
                onOpen={() => {
                  setReturnToChatOnClose(false);
                  setOpenReport(report);
                }}
                onDelete={() => setDeleteTarget({ kind: 'report', artifact: report })}
                onSendToChat={onSendToChat ? () => sendReportToChat(report) : undefined}
                sendBusy={sendBusy === report.id}
              />
            )) : (
              <div className="report-empty-state">
                <FileText size={26} />
                <h3>No reports yet</h3>
                <p>Create the first report for this dataset.</p>
              </div>
            )}
          </div>
        </section>
      </div>

      {openReport && (
        <FullReportModal
          report={openReport}
          onClose={closeOpenReport}
          onDelete={() => setDeleteTarget({ kind: 'report', artifact: openReport })}
          onSendToChat={onSendToChat ? () => sendReportToChat(openReport) : undefined}
          sendBusy={sendBusy === openReport.id}
        />
      )}

      {typeEditorOpen && (
        <ReportTypeEditor
          dataset={dataset}
          initial={editorDraftOverride || draftFromType(editorSourceType, selectedType.startsWith('custom:') ? 'executive' : selectedType, audience, goal)}
          editingType={editingType}
          fromChat={editorFromChat}
          busy={typeBusy}
          error={typeError}
          onClose={() => setTypeEditorOpen(false)}
          onSave={saveReportType}
          onDelete={editingType ? () => setDeleteTarget({ kind: 'report_type', reportType: editingType }) : undefined}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          eyebrow="Confirm delete"
          title={deleteTarget.kind === 'report' ? deleteTarget.artifact.title : deleteTarget.reportType.name}
          message={deleteTarget.kind === 'report'
            ? 'This report will be permanently removed. This action cannot be undone.'
            : 'This custom report type will be permanently removed. Existing generated reports will not be deleted.'}
          busy={deleteTarget.kind === 'report' ? actionBusy === deleteTarget.artifact.id : typeBusy}
          busyLabel="Deleting..."
          onCancel={() => setDeleteTarget(null)}
          onConfirm={confirmDelete}
        />
      )}
    </section>
  );
}

function ReportTypeEditor({
  dataset,
  initial,
  editingType,
  fromChat,
  busy,
  error,
  onClose,
  onSave,
  onDelete,
}: {
  dataset: Dataset | null;
  initial: ReportTypeDraft;
  editingType: CustomReportType | null;
  fromChat: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onSave: (draft: ReportTypeDraft) => void;
  onDelete?: () => void;
}) {
  const [draft, setDraft] = useState<ReportTypeDraft>(() => initial);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    () => new Set(initial.sections.slice(0, 1).map((section) => section.key)),
  );
  const availableFields = useMemo(() => Object.values(dataset?.profile.tables || {})
    .flatMap((table) => table.columns.map((column) => column.name)), [dataset]);

  const updateDraft = <K extends keyof ReportTypeDraft>(key: K, value: ReportTypeDraft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
  };

  const updateSection = (index: number, patch: Partial<ReportTypeSection>) => {
    setDraft((current) => ({
      ...current,
      sections: current.sections.map((section, sectionIndex) => sectionIndex === index ? { ...section, ...patch } : section),
    }));
  };

  const moveSection = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= draft.sections.length) return;
    setDraft((current) => {
      const sections = [...current.sections];
      [sections[index], sections[target]] = [sections[target], sections[index]];
      return { ...current, sections };
    });
  };

  const removeSection = (index: number) => {
    if (draft.sections.length <= 1) return;
    setDraft((current) => ({ ...current, sections: current.sections.filter((_, sectionIndex) => sectionIndex !== index) }));
  };

  const addSection = () => {
    const section = newReportSection(draft.sections.length);
    setDraft((current) => ({ ...current, sections: [...current.sections, section] }));
    setExpandedSections((current) => new Set(current).add(section.key));
  };

  const toggleSection = (key: string) => {
    setExpandedSections((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  return (
    <div className="report-type-editor-shell" role="dialog" aria-modal="true" aria-label="Custom report type editor">
      <div className="report-reader-backdrop" onClick={onClose} />
      <div className="report-type-editor">
        <header className="report-type-editor-head">
          <div>
            <span className="report-kicker">{fromChat ? 'From Chat' : 'Report type builder'}</span>
            <h3>{fromChat ? 'Review customized report structure' : editingType ? 'Edit custom report type' : 'Create custom report type'}</h3>
            <p>{fromChat ? 'Your conversation has prefilled this report structure for review before generation.' : 'Define the sections, evidence, and content the Reporter must produce.'}</p>
          </div>
          <button type="button" className="report-icon-btn neutral" title="Close editor" aria-label="Close editor" onClick={onClose}>
            <X size={17} />
          </button>
        </header>

        <div className="report-type-editor-body">
          <div className="report-type-editor-global">
            <label className="report-field">
              <span>Name</span>
              <input value={draft.name} onChange={(event) => updateDraft('name', event.target.value)} placeholder="e.g. Board Risk Brief" />
            </label>
            <label className="report-field">
              <span>Description</span>
              <input value={draft.description} onChange={(event) => updateDraft('description', event.target.value)} placeholder="When should this report type be used?" />
            </label>
            <label className="report-field">
              <span>Audience</span>
              <input value={draft.audience} onChange={(event) => updateDraft('audience', event.target.value)} />
            </label>
            <label className="report-field report-type-editor-wide">
              <span>Decision goal</span>
              <textarea rows={2} value={draft.goal} onChange={(event) => updateDraft('goal', event.target.value)} />
            </label>
            <label className="report-field">
              <span>Horizon</span>
              <input value={draft.horizon} onChange={(event) => updateDraft('horizon', event.target.value)} />
            </label>
            <label className="report-field">
              <span>Tone</span>
              <select value={draft.tone} onChange={(event) => updateDraft('tone', event.target.value as ReportTypeDraft['tone'])}>
                <option>Board-ready</option>
                <option>Strategic</option>
                <option>Operational</option>
                <option>Technical</option>
              </select>
            </label>
            <label className="report-field report-type-editor-wide">
              <span>Focus areas</span>
              <input value={draft.focus_areas} onChange={(event) => updateDraft('focus_areas', event.target.value)} placeholder="growth, risk, quality" />
            </label>
            <label className="report-field">
              <span>Density</span>
              <select value={draft.visual_style.density} onChange={(event) => updateDraft('visual_style', { ...draft.visual_style, density: event.target.value as ReportTypeDraft['visual_style']['density'] })}>
                <option value="comfortable">Comfortable</option>
                <option value="compact">Compact</option>
              </select>
            </label>
            <label className="report-field">
              <span>Emphasis</span>
              <select value={draft.visual_style.emphasis} onChange={(event) => updateDraft('visual_style', { ...draft.visual_style, emphasis: event.target.value as ReportTypeDraft['visual_style']['emphasis'] })}>
                <option value="balanced">Balanced</option>
                <option value="evidence">Evidence-led</option>
                <option value="decision">Decision-led</option>
              </select>
            </label>
            <label className="report-type-default-toggle">
              <input type="checkbox" checked={draft.is_default} onChange={(event) => updateDraft('is_default', event.target.checked)} />
              <span><strong>Use as default</strong><small>Apply this type when the dataset opens.</small></span>
            </label>
          </div>

          <div className="report-type-sections-head">
            <div>
              <span className="report-kicker">Report structure</span>
              <h4>{draft.sections.length} section{draft.sections.length === 1 ? '' : 's'}</h4>
            </div>
            <button type="button" className="report-secondary-btn" onClick={addSection}>
              <Plus size={14} /> Add section
            </button>
          </div>

          <div className="report-type-sections-list">
            {draft.sections.map((section, index) => (
              <article className={`report-type-section-editor ${expandedSections.has(section.key) ? 'expanded' : 'collapsed'}`} key={section.key}>
                <header>
                  <button type="button" className="report-type-section-toggle" aria-expanded={expandedSections.has(section.key)} onClick={() => toggleSection(section.key)}>
                    <span>{String(index + 1).padStart(2, '0')}</span>
                    <strong>{section.label || 'Untitled section'}</strong>
                    <ChevronDown size={15} aria-hidden="true" />
                  </button>
                  <div className="report-type-section-actions">
                    <button type="button" className="report-icon-btn neutral" title="Move section up" aria-label="Move section up" disabled={index === 0} onClick={() => moveSection(index, -1)}><MoveUp size={14} /></button>
                    <button type="button" className="report-icon-btn neutral" title="Move section down" aria-label="Move section down" disabled={index === draft.sections.length - 1} onClick={() => moveSection(index, 1)}><MoveDown size={14} /></button>
                    <button type="button" className="report-icon-btn reject" title="Remove section" aria-label="Remove section" disabled={draft.sections.length <= 1} onClick={() => removeSection(index)}><Trash2 size={14} /></button>
                  </div>
                </header>
                {expandedSections.has(section.key) && <div className="report-type-section-grid">
                  <label className="report-field">
                    <span>Section name</span>
                    <input value={section.label} onChange={(event) => updateSection(index, { label: event.target.value })} />
                  </label>
                  <label className="report-field">
                    <span>Content type</span>
                    <select value={section.kind} onChange={(event) => updateSection(index, { kind: event.target.value as ReportSectionKind, presentation: { ...section.presentation, kind: event.target.value as ReportSectionKind } })}>
                      {SECTION_KINDS.map((kind) => <option key={kind.value} value={kind.value}>{kind.label}</option>)}
                    </select>
                  </label>
                  <label className="report-field">
                    <span>Section layout</span>
                    <select value={section.presentation?.variant || 'standard'} onChange={(event) => updateSection(index, { presentation: { ...section.presentation, variant: event.target.value as 'hero' | 'feature' | 'standard' | 'compact' } })}>
                      <option value="hero">Hero</option>
                      <option value="feature">Feature</option>
                      <option value="standard">Standard</option>
                      <option value="compact">Compact</option>
                    </select>
                  </label>
                  <label className="report-field">
                    <span>Width</span>
                    <select value={section.presentation?.width || 'full'} onChange={(event) => updateSection(index, { presentation: { ...section.presentation, width: event.target.value as 'full' | 'half' | 'third' } })}>
                      <option value="full">Full width</option>
                      <option value="half">Half width</option>
                      <option value="third">Third width</option>
                    </select>
                  </label>
                  <label className="report-field">
                    <span>Emphasis</span>
                    <select value={section.presentation?.emphasis || 'supporting'} onChange={(event) => updateSection(index, { presentation: { ...section.presentation, emphasis: event.target.value as 'primary' | 'supporting' | 'context' } })}>
                      <option value="primary">Primary</option>
                      <option value="supporting">Supporting</option>
                      <option value="context">Context</option>
                    </select>
                  </label>
                  <label className="report-field report-type-editor-wide">
                    <span>Requirement</span>
                    <textarea rows={2} value={section.description || ''} onChange={(event) => updateSection(index, { description: event.target.value })} placeholder="What must this section explain or show?" />
                  </label>
                  <label className="report-field report-type-editor-wide">
                    <span>Data fields</span>
                    <input value={(section.data_fields || []).join(', ')} onChange={(event) => updateSection(index, { data_fields: event.target.value.split(',').map((field) => field.trim()).filter(Boolean) })} placeholder="date, population, state" />
                    {availableFields.length > 0 && <small className="report-field-hint">Available: {availableFields.join(', ')}</small>}
                  </label>
                  <label className="report-field report-type-editor-wide">
                    <span>Chart or visual instruction</span>
                    <input value={section.chart_intent || ''} onChange={(event) => updateSection(index, { chart_intent: event.target.value })} placeholder="e.g. Show a line chart of the year-over-year trend" />
                  </label>
                  <label className="report-type-required-toggle">
                    <input type="checkbox" checked={section.required} onChange={(event) => updateSection(index, { required: event.target.checked })} />
                    <span>Required section</span>
                  </label>
                  <label className="report-type-required-toggle">
                    <input type="checkbox" checked={Boolean(section.presentation?.page_break_before)} onChange={(event) => updateSection(index, { presentation: { ...section.presentation, page_break_before: event.target.checked } })} />
                    <span>Start on a new page</span>
                  </label>
                </div>}
              </article>
            ))}
          </div>
        </div>

        <footer className="report-type-editor-foot">
          {error ? <div className="report-form-error">{error}</div> : <span>Changes apply to future reports only.</span>}
          <div>
            {onDelete && <button type="button" className="report-danger-btn" onClick={onDelete} disabled={busy}><Trash2 size={14} /> Delete</button>}
            <button type="button" className="report-secondary-btn" onClick={onClose} disabled={busy}>Cancel</button>
            <button type="button" className="report-primary-btn" onClick={() => onSave(draft)} disabled={busy}><Save size={14} />{busy ? 'Saving' : 'Save report type'}</button>
          </div>
        </footer>
      </div>
    </div>
  );
}
