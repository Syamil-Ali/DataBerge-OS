export type Project = {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
};

export type ProfileColumn = {
  name: string;
  dtype: string;
  semantic_type: 'numeric' | 'categorical' | 'text' | 'datetime';
  description?: string | null;
  description_source?: 'human' | 'inferred';
  engineering_role?: string;
  missing_count: number;
  missing_pct: number;
  unique_count: number;
  sample_values: unknown[];
  null_like_markers?: string[];
  datetime_candidate_pct?: number;
  quality_notes?: string[];
  suggested_actions?: string[];
  stats?: Record<string, number | null>;
  histogram?: { bins: number[]; counts: number[] };
  top_values?: { label: string; count: number }[];
  word_frequencies?: { word: string; count: number }[];
};

export type BivariateAnalysis = {
  numeric_numeric: {
    left: string;
    right: string;
    test: string;
    correlation?: number | null;
    p_value?: number | null;
    interpretation: string;
  }[];
  categorical_categorical: {
    left: string;
    right: string;
    test: string;
    chi2?: number | null;
    p_value?: number | null;
    interpretation: string;
  }[];
  numeric_categorical: {
    numeric: string;
    categorical: string;
    test: string;
    anova_F?: number | null;
    p_value?: number | null;
    interpretation: string;
  }[];
};

/** Per-table profile — the standard profile shape produced by profile_dataframe(). */
export type TableProfile = {
  row_count: number;
  column_count: number;
  columns: ProfileColumn[];
  metadata: {
    numeric_columns: string[];
    categorical_columns: string[];
    text_columns: string[];
    described_columns?: number;
    description_coverage_pct?: number;
    duplicate_rows: number;
    missing_cells: number;
  };
  correlations: { left: string; right: string; correlation: number }[];
  bivariate_analysis?: BivariateAnalysis;
  quality_flags: string[];
  source?: {
    source_type: string;
    file_type?: string;
    original_name?: string;
    source_path?: string;
    working_path?: string;
    lineage?: {
      read_path?: string;
      working_path?: string;
      mode?: string;
      refreshable?: boolean;
    };
    warnings?: string[];
  };
  data_engineering?: {
    readiness_score: number;
    summary: string;
    warnings: string[];
    recommended_actions: string[];
    semantic_roles: Record<string, string[]>;
    working_dataset_policy: {
      mutates_source_data: boolean;
      approval_required_for_cleaning: boolean;
      lineage: string;
      source_type?: string;
      refreshable?: boolean;
    };
  };
};

export type Dataset = {
  id: string;
  project_id: string;
  name: string;
  original_filename: string;
  file_type: string;
  row_count: number;
  column_count: number;
  status: string;
  created_at: string;
  /** Unified format: tables dict keyed by table name. */
  profile: {
    tables: Record<string, TableProfile>;
    relationships: RelationalRelationship[];
    description_map: Record<string, Record<string, string>>;
  };
};

export type RelationalTable = {
  name: string;
  columns: {
    name: string;
    clean_name?: string;
    key_type?: 'PK' | 'FK' | null;
    duckdb_type: string;
    dtype?: string;
    semantic_type: ProfileColumn['semantic_type'] | string;
    description_source?: 'human' | 'inferred' | 'dictionary';
    engineering_role?: string;
    null_like_markers?: string[];
    datetime_candidate_pct?: number;
    quality_notes?: string[];
    suggested_actions?: string[];
    unique_count: number;
    missing_count: number;
    missing_pct: number;
    sample_values: string[];
    description?: string;
    stats?: Record<string, number | null>;
    histogram?: { bins: number[]; counts: number[] };
    top_values?: { label: string; count: number }[];
    word_frequencies?: { word: string; count: number }[];
  }[];
  row_count: number;
  column_count: number;
  quality_flags?: string[];
  metadata?: {
    numeric_columns: string[];
    categorical_columns: string[];
    text_columns: string[];
    described_columns?: number;
    description_coverage_pct?: number;
    duplicate_rows: number;
    missing_cells: number;
  };
  correlations?: { left: string; right: string; correlation: number }[];
  bivariate_analysis?: BivariateAnalysis;
  source?: TableProfile['source'];
  data_engineering?: TableProfile['data_engineering'];
};

export type RelationalRelationship = {
  id?: string;
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  confidence: number;
  method: string;
  cardinality?: 'one_to_one' | 'one_to_many' | 'many_to_one' | 'many_to_many';
  coverage?: number;
  active?: boolean;
};

export type ModelTransformation = {
  id: string;
  table: string;
  columns: string[];
  action: string;
  operation?: 'normalize_null_like' | 'cast_datetime' | 'trim_text' | 'lowercase_text' | 'replace_value' | 'fill_missing' | 'manual_review';
  params?: Record<string, string>;
  status: 'applied' | 'ignored' | 'disabled';
  created_at: string;
};

export type RelationalSchema = {
  id: string;
  project_id: string;
  user_id?: string;
  name: string;
  original_filename: string;
  source_path: string;
  schema: {
    tables: Record<string, RelationalTable>;
    relationships: RelationalRelationship[];
    description_map: Record<string, Record<string, string>>;
    transformations?: ModelTransformation[];
  };
  status: 'draft' | 'confirmed' | 'active';
  created_at: string;
  updated_at: string;
};

export type Artifact = {
  id: string;
  project_id: string;
  dataset_id?: string;
  kind: 'dashboard' | 'chart' | 'report';
  title: string;
  status: 'generating' | 'draft' | 'failed';
  payload: Record<string, any>;
  created_at: string;
  updated_at: string;
};

export type ChartType = 'bar' | 'line' | 'donut' | 'scatter' | 'table';

export type ChartSpec = {
  type: ChartType;
  title: string;
  x?: string;
  y?: string[];
  columns?: string[];
};

export type ReportSectionKind =
  | 'summary'
  | 'narrative'
  | 'metrics'
  | 'findings'
  | 'chart'
  | 'actions'
  | 'comparison'
  | 'table'
  | 'key_value'
  | 'bullets'
  | 'references'
  | 'callout';

export type ReportSectionPresentation = {
  kind: ReportSectionKind;
  variant: 'hero' | 'feature' | 'standard' | 'compact';
  width: 'full' | 'half' | 'third';
  emphasis: 'primary' | 'supporting' | 'context';
  page_break_before?: boolean;
};

export type ReportTypeSection = {
  key: string;
  label: string;
  description?: string;
  required: boolean;
  kind: ReportSectionKind;
  data_fields: string[];
  chart_intent?: string;
  presentation?: Partial<ReportSectionPresentation>;
};

export type CustomReportType = {
  id: string;
  user_id: string;
  project_id: string;
  dataset_id: string;
  name: string;
  description: string;
  is_default: boolean;
  created_at: string;
  updated_at: string;
  payload: {
    audience: string;
    goal: string;
    horizon: string;
    tone: 'Board-ready' | 'Strategic' | 'Operational' | 'Technical';
    focus_areas: string[];
    sections: ReportTypeSection[];
    visual_style?: Record<string, string>;
  };
};

export type ReportSection = {
  key: string;
  label?: string;
  content: any;
  kind?: ReportSectionKind;
  presentation?: Partial<ReportSectionPresentation>;
};

export type ReportDocument = {
  version: 2;
  theme: 'executive' | 'research' | 'technical' | 'brief' | 'custom';
  density: 'comfortable' | 'compact';
  sections: ReportSection[];
};

export type ReportDraft = {
  title: string;
  template?: string;
  report_type?: string;
  block_order?: string[];
  block_labels?: Record<string, string>;
  sections?: ReportSection[];
  document?: ReportDocument;
  design?: Pick<ReportDocument, 'version' | 'theme' | 'density'>;
  central_theme?: string;
  executive_summary?: string | {
    situation?: string[];
    background?: string[];
    assessment?: string[];
    recommendation?: string[];
  };
  key_metrics?: {
    name: string;
    value: string;
    health?: string;
    trend?: string;
    score?: number;
    description?: string;
  }[];
  top_findings?: {
    title: string;
    severity?: string;
    evidence?: string;
  }[];
  key_findings?: string[];
  business_implications?: string[];
  findings?: {
    title: string;
    severity: 'critical' | 'concerning' | 'good' | 'info';
    confidence: string;
    evidence: string;
    sql?: string;
    columns_used?: string[];
  }[];
  data_story?: string;
  action_plan?: {
    immediate?: string[];
    short_term?: string[];
    long_term?: string[];
  };
  prognosis?: {
    current_state?: string;
    with_recommendations?: string;
  };
  recommendations?: string[];
  next_steps?: string[];
  charts?: ChartSpec[];
  context?: Record<string, any>;
  readiness?: {
    score?: number;
    label?: string;
    limitations?: string[];
  };
};

export type ReportPlanSection = {
  key: string;
  label: string;
  purpose: string;
  kind: ReportSectionKind;
  data_fields: string[];
  chart_intent?: string | null;
  required: boolean;
  presentation?: Partial<ReportSectionPresentation> | null;
};

export type ReportPlan = {
  version: number;
  plan_id: string;
  status: 'proposed' | 'approved' | 'failed';
  title: string;
  template: 'custom';
  report_type: string;
  audience: string;
  goal: string;
  horizon: string;
  tone: 'Board-ready' | 'Strategic' | 'Operational' | 'Technical';
  focus_areas: string[];
  dataset_scope?: {
    name?: string;
    row_count?: number;
    column_count?: number;
    loaded_rows?: number;
    is_connector_sample?: boolean;
    sample_limit?: number | string | null;
    interpretation?: string;
  };
  sections: ReportPlanSection[];
  revision_instruction?: string | null;
  generation_source: 'llm' | 'failed';
  generation_warning?: string;
};

export type AgentRole = 'team_manager' | 'data_analyst' | 'data_engineer' | 'report_agent';

export type ChatAttachment = {
  kind?: string;
  label: string;
  context: string;
  artifact_id?: string;
};

export type ChatResponse = {
  answer: string;
  chat_message_id?: string;
  evidence: string[];
  sql?: string | null;
  data: Record<string, any>[];
  chart?: ChartSpec | null;
  confidence: number;
  mode?: string;
  active_skill?: 'intake' | 'profiling' | 'query' | 'visualization' | 'reporting' | 'engineering' | 'sequential' | 'parallel';
  handled_by?: AgentRole;
  lead_agent?: AgentRole;
  artifact?: Artifact;
  session_id?: string;
  report_plan?: ReportPlan | null;
  report_draft?: ReportDraft | null;
  action?: 'plan' | 'plan_revised' | 'plan_failed' | 'plan_revision_failed' | 'draft' | 'execute_requested' | 'saved' | 'queued';
  handoff?: {
    from: AgentRole;
    to: AgentRole;
    reason: string;
  };
  shared_state?: {
    active_lead: AgentRole;
    previous_lead?: AgentRole | null;
    handoff_reason?: string | null;
    user_intent: string;
    conversation_focus: string;
  };
  sequential_results?: {
    index: number;
    question: string;
    agent: AgentRole;
    answer: string;
    confidence: number;
    mode?: string;
    active_skill?: string;
    sql?: string | null;
    status: 'done' | 'failed';
  }[];
  sequential_groups?: {
    agent: AgentRole;
    label: 'Analyst' | 'Engineer' | string;
    items: {
      index: number;
      question: string;
      agent: AgentRole;
      answer: string;
      confidence: number;
      mode?: string;
      active_skill?: string;
      sql?: string | null;
      status: 'done' | 'failed';
    }[];
  }[];
};

export type Overview = {
  project: Project;
  datasets: Dataset[];
  artifacts: Artifact[];
};
