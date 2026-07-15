import { Artifact, ChatAttachment, ChatResponse, CustomReportType, Dataset, ModelTransformation, Overview, Project, RelationalSchema, RelationalRelationship, ReportSectionKind, ReportSectionPresentation, ReportTypeSection } from '../types/domain';

const API_BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = localStorage.getItem('db_token');
  const headers: Record<string, string> = { ...(init?.headers as Record<string, string>) };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(text || `Request failed (${response.status})`);
  }
  return text ? (JSON.parse(text) as T) : ({} as T);
}

export async function getProjects(): Promise<Project[]> {
  return request<Project[]>('/projects');
}

export async function getOverview(projectId: string): Promise<Overview> {
  return request<Overview>(`/projects/${projectId}/overview`);
}

export async function uploadDataset(projectId: string, file: File): Promise<Dataset> {
  const formData = new FormData();
  formData.append('file', file);
  return request<Dataset>(`/projects/${projectId}/datasets`, {
    method: 'POST',
    body: formData,
  });
}

export async function deleteDataset(projectId: string, datasetId: string): Promise<{ deleted: boolean; dataset_id: string }> {
  return request<{ deleted: boolean; dataset_id: string }>(`/projects/${projectId}/datasets/${datasetId}`, {
    method: 'DELETE',
  });
}

export async function askQuestion(projectId: string, datasetId: string, message: string, sessionId: string, attachments: ChatAttachment[] = []): Promise<ChatResponse> {
  return request<ChatResponse>(`/projects/${projectId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, message, session_id: sessionId, attachments }),
  });
}

export async function getArtifact(projectId: string, artifactId: string): Promise<Artifact> {
  return request<Artifact>(`/projects/${projectId}/artifacts/${artifactId}`);
}

export async function deleteChatMessage(projectId: string, messageId: string): Promise<{ deleted: boolean; message_id: string }> {
  return request<{ deleted: boolean; message_id: string }>(`/projects/${projectId}/chat/messages/${messageId}`, {
    method: 'DELETE',
  });
}

export type ChatProfileContext = {
  project_id: string;
  dataset_id: string;
  context_source: string;
  explanation: string;
  observability_request_summary_shape: Record<string, any>;
  resolved_dataset: Dataset;
  resolved_profile: Record<string, any>;
  relational_schema?: RelationalSchema | null;
};

export async function getChatProfileContext(projectId: string, datasetId: string): Promise<ChatProfileContext> {
  return request<ChatProfileContext>(`/projects/${projectId}/chat/profile-context?dataset_id=${encodeURIComponent(datasetId)}`);
}

export async function createReport(
  projectId: string,
  payload: {
    dataset_id: string;
    audience: string;
    goal: string;
    horizon: string;
    tone: string;
    focus_areas: string[];
    template?: string;
    report_type?: string | null;
    blocks?: string[] | null;
    custom_blocks?: {
      key: string;
      label: string;
      description?: string;
      required?: boolean;
      kind?: ReportSectionKind;
      presentation?: Partial<ReportSectionPresentation>;
      data_fields?: string[];
      chart_intent?: string;
    }[] | null;
  },
): Promise<Artifact> {
  return request<Artifact>(`/projects/${projectId}/reports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export type ReportTypeInput = {
  dataset_id: string;
  name: string;
  description: string;
  audience: string;
  goal: string;
  horizon: string;
  tone: 'Board-ready' | 'Strategic' | 'Operational' | 'Technical';
  focus_areas: string[];
  sections: ReportTypeSection[];
  visual_style?: Record<string, string>;
  is_default: boolean;
};

export async function listCustomReportTypes(projectId: string, datasetId: string): Promise<CustomReportType[]> {
  return request<CustomReportType[]>(`/projects/${projectId}/reports/types?dataset_id=${encodeURIComponent(datasetId)}`);
}

export async function createCustomReportType(projectId: string, payload: ReportTypeInput): Promise<CustomReportType> {
  return request<CustomReportType>(`/projects/${projectId}/reports/types`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function updateCustomReportType(projectId: string, typeId: string, payload: Omit<ReportTypeInput, 'dataset_id'>): Promise<CustomReportType> {
  return request<CustomReportType>(`/projects/${projectId}/reports/types/${typeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function deleteCustomReportType(projectId: string, typeId: string): Promise<{ deleted: boolean; report_type_id: string }> {
  return request<{ deleted: boolean; report_type_id: string }>(`/projects/${projectId}/reports/types/${typeId}`, {
    method: 'DELETE',
  });
}

export async function deleteArtifact(projectId: string, artifactId: string): Promise<{ deleted: boolean; artifact_id: string }> {
  return request<{ deleted: boolean; artifact_id: string }>(`/projects/${projectId}/artifacts/${artifactId}`, {
    method: 'DELETE',
  });
}

// Chat Sessions

export type ChatSession = {
  id: string;
  project_id: string;
  dataset_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages?: ChatMessage[];
};

export type ChatMessage = {
  id: string;
  project_id: string;
  dataset_id: string;
  session_id: string;
  role: string;
  content: string;
  payload: Record<string, any>;
  created_at: string;
};

export async function listChatSessions(projectId: string, datasetId?: string): Promise<ChatSession[]> {
  const qs = datasetId ? `?dataset_id=${datasetId}` : '';
  return request<ChatSession[]>(`/projects/${projectId}/chat-sessions${qs}`);
}

export async function createChatSession(projectId: string, datasetId: string, title?: string): Promise<ChatSession> {
  return request<ChatSession>(`/projects/${projectId}/chat-sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, title: title || 'New Chat' }),
  });
}

export async function getChatSession(projectId: string, sessionId: string): Promise<ChatSession> {
  return request<ChatSession>(`/projects/${projectId}/chat-sessions/${sessionId}`);
}

export async function deleteChatSession(projectId: string, sessionId: string): Promise<{ deleted: boolean }> {
  return request<{ deleted: boolean }>(`/projects/${projectId}/chat-sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

// OpenDOSM

export type OpenDOSMDataset = {
  id: string;
  name: string;
  category: string;
  desc?: string;
};

export type OpenDOSMTaskStatus = {
  task_id: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed';
  message: string;
  dataset?: Dataset;
  schema?: RelationalSchema;
};

export async function listOpenDOSMDatasets(): Promise<OpenDOSMDataset[]> {
  return request<OpenDOSMDataset[]>('/opendosm/datasets');
}

/** Start a background connect. Returns immediately with a task_id. */
export async function connectOpenDOSMDataset(
  datasetId: string,
  projectId?: string | null,
  limit?: number,
): Promise<{ task_id: string; status: string }> {
  return request<{ task_id: string; status: string }>('/opendosm/connect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      dataset_id: datasetId,
      project_id: projectId ?? undefined,
      ...(limit == null ? {} : { limit }),
    }),
  });
}

/** Poll this endpoint to check whether the connect task is done. */
export async function getOpenDOSMTaskStatus(taskId: string): Promise<OpenDOSMTaskStatus> {
  return request<OpenDOSMTaskStatus>(`/opendosm/status/${taskId}`);
}

// Relational Schemas

export async function uploadRelationalSchema(projectId: string, file: File): Promise<RelationalSchema> {
  const formData = new FormData();
  formData.append('file', file);
  return request<RelationalSchema>(`/projects/${projectId}/relational-schemas`, {
    method: 'POST',
    body: formData,
  });
}

export async function listRelationalSchemas(projectId: string): Promise<RelationalSchema[]> {
  return request<RelationalSchema[]>(`/projects/${projectId}/relational-schemas`);
}

export async function getRelationalSchema(projectId: string, schemaId: string): Promise<RelationalSchema> {
  return request<RelationalSchema>(`/projects/${projectId}/relational-schemas/${schemaId}`);
}

export async function updateRelationalSchema(
  projectId: string,
  schemaId: string,
  body: {
    relationships?: RelationalRelationship[];
    status?: string;
    tables?: Record<string, Record<string, unknown>>;
    transformations?: ModelTransformation[];
  },
): Promise<RelationalSchema> {
  return request<RelationalSchema>(`/projects/${projectId}/relational-schemas/${schemaId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

export async function deleteRelationalSchema(projectId: string, schemaId: string): Promise<{ deleted: boolean; schema_id: string }> {
  return request<{ deleted: boolean; schema_id: string }>(`/projects/${projectId}/relational-schemas/${schemaId}`, {
    method: 'DELETE',
  });
}

export type RelationalTablePreview = {
  table_name: string;
  row_count: number;
  columns: RelationalSchema['schema']['tables'][string]['columns'];
  rows: Record<string, any>[];
};

export async function getRelationalTablePreview(
  projectId: string,
  schemaId: string,
  tableName: string,
): Promise<RelationalTablePreview> {
  return request<RelationalTablePreview>(
    `/projects/${projectId}/relational-schemas/${schemaId}/tables/${encodeURIComponent(tableName)}/preview`,
  );
}

export type DictionarySheetCandidate = {
  name: string;
  columns: string[];
  row_count: number;
  sample_rows: Record<string, string | null>[];
  guesses: {
    table_column?: string | null;
    column_column?: string | null;
    description_column?: string | null;
  };
  is_dictionary_like: boolean;
};

export type DictionaryCandidatesResponse = {
  sheets: DictionarySheetCandidate[];
  preferred_sheet?: string | null;
};

export type DictionaryMapping = {
  sheet_name: string;
  table_column?: string | null;
  column_column: string;
  description_column: string;
  default_table?: string | null;
  manual_targets?: Record<string, { table: string; column: string }>;
};

export type DictionaryPreviewRow = {
  row_id: string;
  source_table?: string | null;
  source_column: string;
  source_description?: string;
  table?: string | null;
  column?: string | null;
  description: string;
  status: 'matched' | 'ambiguous' | 'unmatched' | 'skipped';
  reason: string;
};

export type DictionaryPreviewResponse = {
  rows: DictionaryPreviewRow[];
  counts: Record<'matched' | 'ambiguous' | 'unmatched' | 'skipped', number>;
};

export async function getDictionaryCandidates(projectId: string, schemaId: string): Promise<DictionaryCandidatesResponse> {
  return request<DictionaryCandidatesResponse>(`/projects/${projectId}/relational-schemas/${schemaId}/dictionary-candidates`);
}

export async function previewDictionaryMapping(
  projectId: string,
  schemaId: string,
  mapping: DictionaryMapping,
): Promise<DictionaryPreviewResponse> {
  return request<DictionaryPreviewResponse>(`/projects/${projectId}/relational-schemas/${schemaId}/dictionary-preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mapping),
  });
}

export async function applyDictionaryMapping(
  projectId: string,
  schemaId: string,
  mapping: DictionaryMapping,
): Promise<{ schema: RelationalSchema; preview: DictionaryPreviewResponse }> {
  return request<{ schema: RelationalSchema; preview: DictionaryPreviewResponse }>(`/projects/${projectId}/relational-schemas/${schemaId}/dictionary-apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(mapping),
  });
}
