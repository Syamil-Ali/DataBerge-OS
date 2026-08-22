import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight,
  Check,
  Columns3,
  GitBranch,
  Link2,
  Link2Off,
  Plus,
  Table2,
  Trash2,
  WandSparkles,
} from 'lucide-react';

import { ModelTransformation, RelationalRelationship, RelationalSchema, RelationalTable } from '../types/domain';
import { formatText } from '../utils/format';
import {
  applyDictionaryMapping,
  DictionaryCandidatesResponse,
  DictionaryMapping,
  DictionaryPreviewResponse,
  getDictionaryCandidates,
  getRelationalTablePreview,
  previewDictionaryMapping,
  RelationalTablePreview,
  updateRelationalSchema,
} from '../services/api';

type Props = {
  schema: RelationalSchema;
  projectId: string;
  onSchemaUpdated?: (schema: RelationalSchema) => void;
  onRelationshipsConfirmed?: (schema: RelationalSchema) => void | Promise<void>;
  showEnterWorkspaceAction?: boolean;
  onCancelReview?: () => void | Promise<void>;
};

type EditorTab = 'relationships' | 'preview' | 'dictionary' | 'engineering';

const relationshipKey = (rel: RelationalRelationship) =>
  rel.id ?? `${rel.from_table}.${rel.from_column}->${rel.to_table}.${rel.to_column}`;

const methodLabel = (method: string) => {
  if (method.includes('explicit')) return 'PK/FK label';
  if (method.includes('table_name')) return 'Table-name match';
  if (method.includes('value')) return 'Value coverage';
  if (method.includes('name_match_id')) return 'ID name match';
  if (method.includes('manual')) return 'Manual';
  return 'Name match';
};
import { RelationshipMap } from './relationship/RelationshipMap';
import { DataDictionaryMapper } from './relationship/DataDictionaryMapper';
import { DataPreviewEditor } from './relationship/DataPreviewEditor';
import { EngineeringRecommendations } from './relationship/EngineeringRecommendations';
export function RelationshipEditor({
  schema,
  projectId,
  onSchemaUpdated,
  onRelationshipsConfirmed,
  showEnterWorkspaceAction = false,
  onCancelReview,
}: Props) {
  const initialRelationships = useMemo(() => schema.schema.relationships ?? [], [schema]);
  const [relationships, setRelationships] = useState<RelationalRelationship[]>(initialRelationships);
  const [enabledSet, setEnabledSet] = useState<Set<number>>(
    () => new Set(initialRelationships.map((rel, index) => (rel.active === false ? -1 : index)).filter((index) => index >= 0)),
  );
  const [showAddForm, setShowAddForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const initialEditorTab = Object.keys(schema.schema.tables).length > 1 ? 'relationships' : 'preview';
  const [activeEditorTab, setActiveEditorTab] = useState<EditorTab>(initialEditorTab);

  useEffect(() => {
    const nextRelationships = schema.schema.relationships ?? [];
    setRelationships(nextRelationships);
    setEnabledSet(new Set(nextRelationships.map((rel, index) => (rel.active === false ? -1 : index)).filter((index) => index >= 0)));
    setSaved(false);
    setSaveError(null);
  }, [schema.id, schema.schema.relationships]);

  useEffect(() => {
    setActiveEditorTab(Object.keys(schema.schema.tables).length > 1 ? 'relationships' : 'preview');
  }, [schema.id]);

  const tables = schema.schema.tables;
  const tableNames = Object.keys(tables);
  const hasRelationshipTab = tableNames.length > 1;

  useEffect(() => {
    if (!hasRelationshipTab && activeEditorTab === 'relationships') {
      setActiveEditorTab('preview');
    }
  }, [activeEditorTab, hasRelationshipTab]);

  const toggleRelationship = useCallback((idx: number) => {
    setEnabledSet((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
    setSaved(false);
  }, []);

  const updateRelationship = useCallback((idx: number, update: Partial<RelationalRelationship>) => {
    setRelationships((prev) => prev.map((rel, index) => (index === idx ? { ...rel, ...update } : rel)));
    setSaved(false);
  }, []);

  const deleteRelationship = useCallback((idx: number) => {
    setRelationships((prev) => prev.filter((_, index) => index !== idx));
    setEnabledSet((prev) => {
      const next = new Set<number>();
      for (const index of prev) {
        if (index < idx) next.add(index);
        else if (index > idx) next.add(index - 1);
      }
      return next;
    });
    setSaved(false);
  }, []);

  const addRelationship = useCallback((rel: RelationalRelationship) => {
    setRelationships((prev) => [...prev, rel]);
    setEnabledSet((prev) => new Set([...prev, relationships.length]));
    setShowAddForm(false);
    setSaved(false);
  }, [relationships.length]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const relationshipsToSave = relationships.map((rel, index) => ({
        ...rel,
        id: relationshipKey(rel),
        active: enabledSet.has(index),
      }));
      const result = await updateRelationalSchema(projectId, schema.id, {
        relationships: relationshipsToSave,
        status: 'confirmed',
      });
      setSaved(true);
      onSchemaUpdated?.(result);
      await onRelationshipsConfirmed?.(result);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save relationships.');
    } finally {
      setSaving(false);
    }
  }, [relationships, enabledSet, projectId, schema.id, onSchemaUpdated, onRelationshipsConfirmed]);

  const activeCount = relationships.filter((_, index) => enabledSet.has(index)).length;

  return (
    <section className={`rel-editor ${activeEditorTab === 'relationships' ? 'relationship-mode' : activeEditorTab === 'preview' ? 'preview-mode' : ''}`}>
      <div className="rel-editor-head">
        <div>
          <div className="rel-editor-label">Data Model</div>
          <h3 className="rel-editor-title">{schema.name}</h3>
          <p className="rel-editor-sub">
            Review the inferred table links, fix the relationship kind, or add a missing connection.
          </p>
        </div>
        {showEnterWorkspaceAction || onCancelReview ? (
          <div className="rel-editor-actions">
            {showEnterWorkspaceAction ? (
              <button className="rel-btn-enter" onClick={handleSave} disabled={saving} type="button">
                {saving ? 'Saving' : 'Enter workspace'}
              </button>
            ) : null}
            {onCancelReview ? (
              <button className="rel-btn-cancel" onClick={onCancelReview} disabled={saving} type="button">
                Cancel
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {saveError && <div className="rel-save-error">{saveError}</div>}

      <div className="rel-editor-tabs">
        {hasRelationshipTab ? (
          <button
            className={activeEditorTab === 'relationships' ? 'active' : ''}
            onClick={() => setActiveEditorTab('relationships')}
          >
            <GitBranch size={14} />
            Relationships
          </button>
        ) : null}
        <button
          className={activeEditorTab === 'preview' ? 'active' : ''}
          onClick={() => setActiveEditorTab('preview')}
        >
          <Table2 size={14} />
          Preview
        </button>
        <button
          className={activeEditorTab === 'dictionary' ? 'active' : ''}
          onClick={() => setActiveEditorTab('dictionary')}
        >
          <Columns3 size={14} />
          Data Dictionary
        </button>
        <button
          className={activeEditorTab === 'engineering' ? 'active' : ''}
          onClick={() => setActiveEditorTab('engineering')}
        >
          <WandSparkles size={14} />
          Transformations
        </button>
      </div>

      {hasRelationshipTab && activeEditorTab === 'relationships' ? (
        <div className="rel-relationship-content">
          <div className="rel-relationship-toolbar">
            <span className="rel-status-pill">{activeCount} active / {relationships.length} total</span>
            <div className="rel-relationship-actions">
              <button className="rel-btn-confirm" onClick={handleSave} disabled={saving}>
                <Check size={13} />
                {saving ? 'Saving' : saved ? 'Saved' : 'Confirm relationships'}
              </button>
            </div>
          </div>

          <div className="rel-model-summary">
            <div>
              <span>Tables</span>
              <strong>{tableNames.length}</strong>
            </div>
            <div>
              <span>Total columns</span>
              <strong>{tableNames.reduce((sum, name) => sum + tables[name].column_count, 0)}</strong>
            </div>
          </div>

          <RelationshipMap
            tables={tables}
            relationships={relationships}
            activeIndexes={enabledSet}
            showAddForm={showAddForm}
            onToggleRelationship={toggleRelationship}
            onDeleteRelationship={deleteRelationship}
            onCardinalityChange={(idx, cardinality) => updateRelationship(idx, {
              cardinality,
              method: relationships[idx]?.method === 'manual' ? 'manual' : `${relationships[idx]?.method ?? 'manual'}_edited`,
            })}
            onAddRelationship={addRelationship}
            onShowAddForm={() => setShowAddForm(true)}
            onCancelAdd={() => setShowAddForm(false)}
          />
        </div>
      ) : activeEditorTab === 'preview' ? (
        <DataPreviewEditor schema={schema} projectId={projectId} onSchemaUpdated={onSchemaUpdated} />
      ) : activeEditorTab === 'dictionary' ? (
        <DataDictionaryMapper schema={schema} projectId={projectId} onSchemaUpdated={onSchemaUpdated} />
      ) : (
        <EngineeringRecommendations schema={schema} projectId={projectId} onSchemaUpdated={onSchemaUpdated} />
      )}
    </section>
  );
}
