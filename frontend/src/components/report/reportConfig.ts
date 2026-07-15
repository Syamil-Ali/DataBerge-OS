import type { CustomReportType, ReportPlan, ReportSectionKind, ReportTypeSection } from '../../types/domain';

export const TEMPLATE_BLOCKS: Record<string, { key: string; label: string; required: boolean }[]> = {
  executive: [
    { key: 'central_theme', label: 'Central Theme', required: true },
    { key: 'executive_summary', label: 'Executive Summary (SBAR)', required: true },
    { key: 'key_metrics', label: 'Key Metrics', required: true },
    { key: 'findings', label: 'Findings', required: true },
    { key: 'data_story', label: 'Data Story', required: false },
    { key: 'action_plan', label: 'Action Plan', required: false },
    { key: 'prognosis', label: 'Prognosis', required: false },
    { key: 'charts', label: 'Charts', required: false },
  ],
  research: [
    { key: 'summary', label: 'Summary', required: true },
    { key: 'problem_statement', label: 'Problem Statement', required: true },
    { key: 'methodology', label: 'Methodology', required: true },
    { key: 'findings', label: 'Findings', required: true },
    { key: 'data_story', label: 'Data Story', required: false },
    { key: 'conclusions', label: 'Conclusions', required: true },
    { key: 'references', label: 'References', required: false },
  ],
  technical: [
    { key: 'overview', label: 'Overview', required: true },
    { key: 'data_quality_assessment', label: 'Data Quality Assessment', required: true },
    { key: 'schema_analysis', label: 'Schema Analysis', required: true },
    { key: 'key_metrics', label: 'Key Metrics', required: true },
    { key: 'findings', label: 'Findings', required: true },
    { key: 'recommendations', label: 'Recommendations', required: true },
  ],
  quick_brief: [
    { key: 'central_theme', label: 'Central Theme', required: true },
    { key: 'key_metrics', label: 'Key Metrics', required: true },
    { key: 'top_findings', label: 'Top Findings', required: true },
    { key: 'charts', label: 'Charts', required: false },
  ],
};

export const TEMPLATE_LABELS: Record<string, string> = {
  executive: 'Executive Report',
  research: 'Research Report',
  technical: 'Technical Report',
  quick_brief: 'Quick Brief',
  custom: 'Custom Report',
};

export const SECTION_KINDS: { value: ReportSectionKind; label: string }[] = [
  { value: 'narrative', label: 'Narrative' },
  { value: 'summary', label: 'Summary' },
  { value: 'metrics', label: 'Key metrics' },
  { value: 'findings', label: 'Findings' },
  { value: 'chart', label: 'Chart' },
  { value: 'table', label: 'Table' },
  { value: 'comparison', label: 'Comparison' },
  { value: 'bullets', label: 'Bullets' },
  { value: 'actions', label: 'Actions' },
  { value: 'callout', label: 'Callout' },
  { value: 'key_value', label: 'Key-value' },
  { value: 'references', label: 'References' },
];

export type ReportTypeDraft = {
  name: string;
  description: string;
  audience: string;
  goal: string;
  horizon: string;
  tone: 'Board-ready' | 'Strategic' | 'Operational' | 'Technical';
  focus_areas: string;
  sections: ReportTypeSection[];
  visual_style: {
    density: 'comfortable' | 'compact';
    emphasis: 'balanced' | 'evidence' | 'decision';
  };
  is_default: boolean;
};

export function sectionKindForKey(key: string): ReportSectionKind {
  if (key === 'charts') return 'chart';
  if (key === 'key_metrics') return 'metrics';
  if (key === 'findings' || key === 'top_findings') return 'findings';
  if (key === 'action_plan' || key === 'recommendations' || key === 'next_steps') return 'actions';
  if (key === 'executive_summary' || key === 'summary' || key === 'central_theme') return 'summary';
  return 'narrative';
}

export function sectionsFromTemplate(template: string): ReportTypeSection[] {
  return (TEMPLATE_BLOCKS[template] || TEMPLATE_BLOCKS.executive).map((block) => ({
    key: block.key,
    label: block.label,
    description: '',
    required: block.required,
    kind: sectionKindForKey(block.key),
    data_fields: [],
    chart_intent: '',
    presentation: {
      kind: sectionKindForKey(block.key),
      variant: block.required ? 'feature' : 'standard',
      width: 'full',
      emphasis: block.required ? 'primary' : 'supporting',
    },
  }));
}

export function draftFromType(reportType: CustomReportType | null, template: string, audience: string, goal: string): ReportTypeDraft {
  if (reportType) {
    return {
      name: reportType.name,
      description: reportType.description,
      audience: reportType.payload.audience,
      goal: reportType.payload.goal,
      horizon: reportType.payload.horizon,
      tone: reportType.payload.tone,
      focus_areas: reportType.payload.focus_areas.join(', '),
      sections: reportType.payload.sections.map((section) => ({
        ...section,
        data_fields: [...(section.data_fields || [])],
        presentation: { ...(section.presentation || {}) },
      })),
      visual_style: {
        density: reportType.payload.visual_style?.density === 'compact' ? 'compact' : 'comfortable',
        emphasis: reportType.payload.visual_style?.emphasis === 'evidence' || reportType.payload.visual_style?.emphasis === 'decision'
          ? reportType.payload.visual_style.emphasis
          : 'balanced',
      },
      is_default: reportType.is_default,
    };
  }
  return {
    name: `${TEMPLATE_LABELS[template] || 'Custom Report'} Copy`,
    description: 'A reusable custom report type for this dataset.',
    audience,
    goal,
    horizon: 'Next quarter',
    tone: 'Strategic',
    focus_areas: 'growth, risk, quality',
    sections: sectionsFromTemplate(template),
    visual_style: { density: 'comfortable', emphasis: 'balanced' },
    is_default: false,
  };
}

export function draftFromPlan(plan: ReportPlan): ReportTypeDraft {
  return {
    name: (plan.report_type && plan.report_type !== 'Custom Report' ? plan.report_type : plan.title).slice(0, 120),
    description: plan.goal,
    audience: plan.audience,
    goal: plan.goal,
    horizon: plan.horizon,
    tone: plan.tone,
    focus_areas: plan.focus_areas.join(', '),
    sections: plan.sections.map((section) => ({
      key: section.key,
      label: section.label,
      description: section.purpose,
      required: section.required,
      kind: section.kind,
      data_fields: [...section.data_fields],
      chart_intent: section.chart_intent || '',
      presentation: section.presentation || {
        kind: section.kind,
        variant: 'standard',
        width: 'full',
        emphasis: section.required ? 'primary' : 'supporting',
      },
    })),
    visual_style: { density: 'comfortable', emphasis: 'decision' },
    is_default: false,
  };
}

export function newReportSection(index: number): ReportTypeSection {
  return {
    key: `custom_section_${Date.now()}_${index}`,
    label: 'New section',
    description: '',
    required: false,
    kind: 'narrative',
    data_fields: [],
    chart_intent: '',
    presentation: { kind: 'narrative', variant: 'standard', width: 'full', emphasis: 'supporting' },
  };
}
