import type { Artifact, ChatAttachment, Dataset, Overview, RelationalSchema } from '../types/domain';

export type WorkspaceKind = 'dataset' | 'schema';

export type WorkspaceSelection = {
  preferredDatasetId?: string | null;
  preferredSchemaId?: string | null;
  preferredWorkspaceKind?: WorkspaceKind;
  activeSchemaId: string | null;
  selectedDatasetId: string | null;
  activeWorkspaceKind: WorkspaceKind;
  schemas: RelationalSchema[];
  overview: Overview;
};

export type ResolvedWorkspaceSelection = {
  datasetId: string | null;
  schemaId: string | null;
  workspaceKind: WorkspaceKind;
};

export function resolveWorkspaceSelection({
  preferredDatasetId,
  preferredSchemaId,
  preferredWorkspaceKind,
  activeSchemaId,
  selectedDatasetId,
  activeWorkspaceKind,
  schemas,
  overview,
}: WorkspaceSelection): ResolvedWorkspaceSelection {
  const currentSchemaStillExists = Boolean(
    activeSchemaId && schemas.some((schema) => schema.id === activeSchemaId),
  );
  const schemaId =
    preferredSchemaId === null
      ? null
      : preferredSchemaId && schemas.some((schema) => schema.id === preferredSchemaId)
        ? preferredSchemaId
        : preferredSchemaId === undefined && currentSchemaStillExists
          ? activeSchemaId
          : schemas[0]?.id ?? null;
  const schema = schemaId ? schemas.find((item) => item.id === schemaId) ?? null : null;
  const schemaTableCount = Object.keys(schema?.schema?.tables ?? {}).length;
  const hasCurrentWorkspaceSelection = Boolean(activeSchemaId || selectedDatasetId);
  const effectiveWorkspaceKind =
    preferredWorkspaceKind
      ?? (preferredDatasetId !== undefined && preferredSchemaId === undefined
        ? 'dataset'
        : hasCurrentWorkspaceSelection
          ? activeWorkspaceKind
          : schemaTableCount > 1
            ? 'schema'
            : 'dataset');
  const currentDatasetStillExists = Boolean(
    selectedDatasetId && overview.datasets.some((dataset) => dataset.id === selectedDatasetId),
  );
  const schemaDatasetId =
    schemaId && overview.datasets.some((dataset) => dataset.id === schemaId)
      ? schemaId
      : null;
  const shouldPreferSchemaDataset = Boolean(
    schemaDatasetId
      && effectiveWorkspaceKind === 'dataset'
      && preferredDatasetId === undefined
      && !currentDatasetStillExists,
  );
  const datasetId =
    effectiveWorkspaceKind === 'schema'
      ? preferredDatasetId && overview.datasets.some((dataset) => dataset.id === preferredDatasetId)
        ? preferredDatasetId
        : schemaDatasetId
      : preferredDatasetId === null
        ? null
        : preferredDatasetId && overview.datasets.some((dataset) => dataset.id === preferredDatasetId)
          ? preferredDatasetId
          : preferredDatasetId === undefined && currentDatasetStillExists
            ? selectedDatasetId
            : shouldPreferSchemaDataset
              ? schemaDatasetId
              : overview.datasets[0]?.id ?? null;
  const workspaceKind = schemaId && (effectiveWorkspaceKind === 'schema' || !datasetId)
    ? 'schema'
    : 'dataset';

  return { datasetId, schemaId, workspaceKind };
}

export function schemaAsDataset(schema: RelationalSchema | null): Dataset | null {
  if (!schema) return null;
  const tables = schema.schema?.tables ?? {};
  return {
    id: schema.id,
    project_id: schema.project_id,
    name: schema.name,
    original_filename: schema.original_filename,
    file_type: 'xlsx',
    row_count: Object.values(tables).reduce((sum, table) => sum + (table.row_count ?? 0), 0),
    column_count: Object.values(tables).reduce((sum, table) => sum + (table.column_count ?? table.columns?.length ?? 0), 0),
    status: schema.status,
    created_at: schema.created_at,
    profile: {
      tables: tables as Record<string, any>,
      relationships: schema.schema?.relationships ?? [],
      description_map: schema.schema?.description_map ?? {},
    },
  };
}

type ReportSectionSummary = { title: string; content: string };

function summarizeReportSection(section: Record<string, any>): ReportSectionSummary {
  const content = section.content ?? section.body ?? section.text ?? section.summary ?? '';
  return {
    title: section.title || section.label || section.key || 'Section',
    content: typeof content === 'string'
      ? content.slice(0, 260)
      : Array.isArray(section.content)
        ? section.content
          .map((item: any) => typeof item === 'string' ? item.slice(0, 160) : item?.title || item?.evidence || item?.type || '')
          .filter(Boolean)
          .join('; ')
          .slice(0, 260)
        : section.content?.title || section.content?.evidence || section.content?.type || '',
  };
}

export function reportAttachment(artifact: Artifact): ChatAttachment {
  const payload = artifact.payload || {};
  const document = payload.document || payload;
  const sections = Array.isArray(document.sections)
    ? document.sections.map((section: Record<string, any>) => summarizeReportSection(section))
    : [];
  const context = [
    `Attached report: ${artifact.title}`,
    `Status: ${artifact.status}. Report type: ${payload.report_type || payload.template || 'Report'}.`,
    'Use the attached report as the primary context when answering the user question. Do not create a new report unless the user explicitly asks for one.',
    sections.length > 0 ? `Report sections:\n${sections.map((section: ReportSectionSummary) => `${section.title}: ${section.content}`).join('\n').slice(0, 950)}` : '',
  ].filter(Boolean).join('\n');
  return { label: `Report: ${artifact.title}`, context };
}

export function addChatAttachment(
  attachments: ChatAttachment[],
  attachment: ChatAttachment,
  maxAttachments: number,
): ChatAttachment[] {
  if (attachments.length >= maxAttachments || attachments.some((item) => item.label === attachment.label)) {
    return attachments;
  }
  return [...attachments, attachment];
}
