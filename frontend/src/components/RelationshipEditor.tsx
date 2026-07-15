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

function RelationshipMap({
  tables,
  relationships,
  activeIndexes,
  showAddForm,
  onToggleRelationship,
  onDeleteRelationship,
  onCardinalityChange,
  onAddRelationship,
  onShowAddForm,
  onCancelAdd,
}: {
  tables: Record<string, RelationalTable>;
  relationships: RelationalRelationship[];
  activeIndexes: Set<number>;
  showAddForm: boolean;
  onToggleRelationship: (index: number) => void;
  onDeleteRelationship: (index: number) => void;
  onCardinalityChange: (index: number, cardinality: NonNullable<RelationalRelationship['cardinality']>) => void;
  onAddRelationship: (rel: RelationalRelationship) => void;
  onShowAddForm: () => void;
  onCancelAdd: () => void;
}) {
  const tableNames = Object.keys(tables);
  const [visibleCounts, setVisibleCounts] = useState<Record<string, number>>({});
  const [hoveredColumn, setHoveredColumn] = useState<string | null>(null);
  const [hoveredRelationship, setHoveredRelationship] = useState<string | null>(null);
  const [pinnedColumn, setPinnedColumn] = useState<string | null>(null);
  const [pinnedRelationship, setPinnedRelationship] = useState<string | null>(null);

  useEffect(() => {
    setVisibleCounts((prev) => {
      const next: Record<string, number> = {};
      for (const name of tableNames) {
        next[name] = Math.min(prev[name] ?? 10, tables[name].columns.length);
      }
      return next;
    });
  }, [tableNames.join('|'), tables]);

  const columnKey = (table: string, column: string) => `${table}.${column}`;
  const relationshipTouchesColumn = (rel: RelationalRelationship, table: string, column: string) =>
    (rel.from_table === table && rel.from_column === column) || (rel.to_table === table && rel.to_column === column);
  const relationshipKeysForColumn = (selectedColumn: string | null) => (
    selectedColumn
      ? relationships
        .filter((rel, index) => activeIndexes.has(index) && (
          columnKey(rel.from_table, rel.from_column) === selectedColumn
          || columnKey(rel.to_table, rel.to_column) === selectedColumn
        ))
        .map(relationshipKey)
      : []
  );
  const highlightedRelationshipKeys = new Set(
    [
      ...(pinnedRelationship ? [pinnedRelationship] : []),
      ...relationshipKeysForColumn(pinnedColumn),
      ...(hoveredRelationship ? [hoveredRelationship] : []),
      ...relationshipKeysForColumn(hoveredColumn),
    ],
  );
  const columnIsInHighlightedRelationship = (table: string, column: string) =>
    relationships.some((rel, index) => (
      activeIndexes.has(index)
      && highlightedRelationshipKeys.has(relationshipKey(rel))
      && relationshipTouchesColumn(rel, table, column)
    ));
  const columnHasAnyRelationship = (table: string, column: string) =>
    relationships.some((rel, index) => activeIndexes.has(index) && relationshipTouchesColumn(rel, table, column));

  return (
    <div className="rel-model-workspace">
      <aside className="rel-model-flow">
        <div className="rel-model-flow-head">
          <GitBranch size={14} />
          <span>Relationships</span>
        </div>
        {relationships.length === 0 ? (
          <div className="rel-model-flow-empty">No relationships yet.</div>
        ) : (
          relationships.map((rel, index) => {
            const key = relationshipKey(rel);
            const isHighlighted = highlightedRelationshipKeys.has(key);
            const enabled = activeIndexes.has(index);
            return (
              <div
                className={`rel-model-flow-item ${isHighlighted ? 'highlighted' : ''} ${enabled ? '' : 'disabled'}`}
                key={`${key}-${index}`}
                onMouseEnter={() => setHoveredRelationship(key)}
                onMouseLeave={() => setHoveredRelationship(null)}
                onClick={() => {
                  setPinnedColumn(null);
                  setPinnedRelationship((prev) => (prev === key ? null : key));
                }}
              >
                <div className="rel-flow-endpoints">
                  <span>{rel.from_table}.{rel.from_column}</span>
                  <ArrowRight size={13} />
                  <span>{rel.to_table}.{rel.to_column}</span>
                </div>
                <div className="rel-flow-meta">
                  <select
                    className="rel-cardinality-select"
                    value={rel.cardinality ?? 'many_to_one'}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => onCardinalityChange(index, event.target.value as NonNullable<RelationalRelationship['cardinality']>)}
                  >
                    <option value="many_to_one">Many-to-one</option>
                    <option value="one_to_many">One-to-many</option>
                    <option value="one_to_one">One-to-one</option>
                    <option value="many_to_many">Many-to-many</option>
                  </select>
                  <span>{methodLabel(rel.method)}</span>
                  <button
                    className="rel-toggle"
                    onClick={(event) => {
                      event.stopPropagation();
                      onToggleRelationship(index);
                    }}
                    title={enabled ? 'Disable relationship' : 'Enable relationship'}
                  >
                    {enabled ? <Link2 size={14} color="#059669" /> : <Link2Off size={14} color="#94a3b8" />}
                  </button>
                  <button
                    className="rel-delete"
                    onClick={(event) => {
                      event.stopPropagation();
                      onDeleteRelationship(index);
                    }}
                    title="Remove relationship"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            );
          })
        )}
        {showAddForm ? (
          <AddRelationshipForm
            tables={tables}
            onAdd={onAddRelationship}
            onCancel={onCancelAdd}
          />
        ) : (
          <button className="rel-btn-add rel-btn-add-inline" onClick={onShowAddForm} disabled={tableNames.length < 2}>
            <Plus size={13} /> Add relationship
          </button>
        )}
      </aside>

      <div className="rel-model-table-section">
        <div className="rel-model-table-section-head">
          <Table2 size={14} />
          <span>Tables and columns</span>
        </div>
        <div className="rel-model-tables">
          {tableNames.map((name) => {
            const table = tables[name];
            const visibleCount = visibleCounts[name] ?? Math.min(10, table.columns.length);
            const visibleColumns = table.columns.slice(0, visibleCount);
            const remaining = Math.max(table.columns.length - visibleCount, 0);

            return (
              <article className="rel-model-table" key={name}>
                <div className="rel-model-table-head">
                  <div>
                    <strong>{name}</strong>
                    <span>{table.row_count.toLocaleString()} rows / {table.column_count.toLocaleString()} columns</span>
                  </div>
                  <Table2 size={13} />
                </div>
                <div className="rel-model-columns">
                  {visibleColumns.map((column) => {
                    const key = columnKey(name, column.name);
                    const isHighlighted = (
                      hoveredColumn === key
                      || columnIsInHighlightedRelationship(name, column.name)
                    );

                    return (
                      <div
                        className={`rel-model-column ${isHighlighted ? 'highlighted' : ''} ${columnHasAnyRelationship(name, column.name) ? 'connected' : ''}`}
                        key={column.name}
                        onMouseEnter={() => setHoveredColumn(key)}
                        onMouseLeave={() => setHoveredColumn(null)}
                        onClick={() => {
                          setPinnedRelationship(null);
                          setPinnedColumn((prev) => (prev === key ? null : key));
                        }}
                      >
                        <span className={`rel-col-type ${column.semantic_type}`}>{column.semantic_type === 'numeric' ? '123' : 'ABC'}</span>
                        <span className="rel-model-column-name">{column.name}</span>
                        {column.key_type && <span className={`rel-key-badge ${column.key_type.toLowerCase()}`}>{column.key_type}</span>}
                      </div>
                    );
                  })}
                </div>
                {remaining > 0 && (
                  <div className="rel-model-column-actions">
                    <button
                      type="button"
                      onClick={() => setVisibleCounts((prev) => ({
                        ...prev,
                        [name]: Math.min((prev[name] ?? visibleCount) + 10, table.columns.length),
                      }))}
                    >
                      Show 10 more
                    </button>
                    <button
                      type="button"
                      onClick={() => setVisibleCounts((prev) => ({ ...prev, [name]: table.columns.length }))}
                    >
                      Show all
                    </button>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function AddRelationshipForm({
  tables,
  onAdd,
  onCancel,
}: {
  tables: Record<string, RelationalTable>;
  onAdd: (rel: RelationalRelationship) => void;
  onCancel: () => void;
}) {
  const tableNames = Object.keys(tables);
  const [fromTable, setFromTable] = useState(tableNames[0] || '');
  const [fromCol, setFromCol] = useState('');
  const [toTable, setToTable] = useState(tableNames.find((name) => name !== fromTable) || '');
  const [toCol, setToCol] = useState('');
  const [cardinality, setCardinality] = useState<NonNullable<RelationalRelationship['cardinality']>>('many_to_one');

  useEffect(() => {
    if (toTable === fromTable) {
      setToTable(tableNames.find((name) => name !== fromTable) || '');
      setToCol('');
    }
  }, [fromTable, tableNames, toTable]);

  const fromCols = tables[fromTable]?.columns ?? [];
  const toCols = tables[toTable]?.columns ?? [];
  const canAdd = fromTable && toTable && fromCol && toCol && fromTable !== toTable;

  return (
    <div className="rel-add-form">
      <div className="rel-add-row">
        <div className="rel-add-group">
          <label>From table</label>
          <select value={fromTable} onChange={(event) => { setFromTable(event.target.value); setFromCol(''); }}>
            {tableNames.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
          <select value={fromCol} onChange={(event) => setFromCol(event.target.value)}>
            <option value="">Select column</option>
            {fromCols.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
          </select>
        </div>
        <ArrowRight size={16} className="rel-add-arrow" />
        <div className="rel-add-group">
          <label>To table</label>
          <select value={toTable} onChange={(event) => { setToTable(event.target.value); setToCol(''); }}>
            {tableNames.filter((name) => name !== fromTable).map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
          <select value={toCol} onChange={(event) => setToCol(event.target.value)}>
            <option value="">Select column</option>
            {toCols.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
          </select>
        </div>
        <div className="rel-add-group rel-add-cardinality">
          <label>Kind</label>
          <select value={cardinality} onChange={(event) => setCardinality(event.target.value as NonNullable<RelationalRelationship['cardinality']>)}>
            <option value="many_to_one">Many-to-one</option>
            <option value="one_to_many">One-to-many</option>
            <option value="one_to_one">One-to-one</option>
            <option value="many_to_many">Many-to-many</option>
          </select>
        </div>
      </div>
      <div className="rel-add-actions">
        <button
          className="rel-btn-confirm"
          disabled={!canAdd}
          onClick={() => {
            if (!canAdd) return;
            onAdd({
              id: `${fromTable}.${fromCol}->${toTable}.${toCol}`,
              from_table: fromTable,
              from_column: fromCol,
              to_table: toTable,
              to_column: toCol,
              confidence: 1,
              method: 'manual',
              cardinality,
              active: true,
            });
          }}
        >
          <Plus size={13} /> Add
        </button>
        <button className="rel-btn-cancel" onClick={onCancel}>Cancel</button>
      </div>
    </div>
  );
}

function DataDictionaryMapper({
  schema,
  projectId,
  onSchemaUpdated,
}: {
  schema: RelationalSchema;
  projectId: string;
  onSchemaUpdated?: (schema: RelationalSchema) => void;
}) {
  const [candidates, setCandidates] = useState<DictionaryCandidatesResponse | null>(null);
  const [mapping, setMapping] = useState<DictionaryMapping | null>(null);
  const [preview, setPreview] = useState<DictionaryPreviewResponse | null>(null);
  const [manualTargets, setManualTargets] = useState<Record<string, { table: string; column: string }>>({});
  const [inspecting, setInspecting] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tableNames = Object.keys(schema.schema.tables);

  useEffect(() => {
    let cancelled = false;
    setInspecting(true);
    setError(null);
    setPreview(null);
    getDictionaryCandidates(projectId, schema.id)
      .then((result) => {
        if (cancelled) return;
        setCandidates(result);
        const preferred = result.sheets.find((sheet) => sheet.name === result.preferred_sheet) ?? result.sheets[0];
        if (preferred) {
          setMapping({
            sheet_name: preferred.name,
            table_column: preferred.guesses.table_column ?? null,
            column_column: preferred.guesses.column_column ?? preferred.columns[0] ?? '',
            description_column: preferred.guesses.description_column ?? preferred.columns[1] ?? '',
            default_table: tableNames.length === 1 ? tableNames[0] : null,
          });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to inspect workbook.');
      })
      .finally(() => {
        if (!cancelled) setInspecting(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, schema.id]);

  const selectedSheet = candidates?.sheets.find((sheet) => sheet.name === mapping?.sheet_name) ?? null;
  const canPreview = Boolean(mapping?.sheet_name && mapping.column_column && mapping.description_column);
  const targetOptionsByTable = useMemo(() => (
    tableNames.map((tableName) => ({
      tableName,
      options: schema.schema.tables[tableName].columns.map((column) => ({
        table: tableName,
        column: column.name,
        value: JSON.stringify({ table: tableName, column: column.name }),
      })),
    }))
  ), [schema.schema.tables, tableNames.join('|')]);
  const mappingWithTargets = mapping ? { ...mapping, manual_targets: manualTargets } : null;

  const updateMapping = (updates: Partial<DictionaryMapping>) => {
    setMapping((prev) => (prev ? { ...prev, ...updates } : null));
    setPreview(null);
    setManualTargets({});
    setError(null);
  };

  const handleSheetChange = (sheetName: string) => {
    const sheet = candidates?.sheets.find((item) => item.name === sheetName);
    if (!sheet) return;
    setMapping({
      sheet_name: sheet.name,
      table_column: sheet.guesses.table_column ?? null,
      column_column: sheet.guesses.column_column ?? sheet.columns[0] ?? '',
      description_column: sheet.guesses.description_column ?? sheet.columns[1] ?? '',
      default_table: tableNames.length === 1 ? tableNames[0] : null,
    });
    setPreview(null);
    setManualTargets({});
    setError(null);
  };

  const handlePreview = async () => {
    if (!mapping || !canPreview) return;
    setLoading(true);
    setError(null);
    try {
      const result = await previewDictionaryMapping(projectId, schema.id, mappingWithTargets ?? mapping);
      setPreview(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to preview dictionary mapping.');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!mapping || !canPreview) return;
    setSaving(true);
    setError(null);
    try {
      const result = await applyDictionaryMapping(projectId, schema.id, mappingWithTargets ?? mapping);
      setPreview(result.preview);
      onSchemaUpdated?.(result.schema);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply dictionary mapping.');
    } finally {
      setSaving(false);
    }
  };

  const getRowTarget = (row: { row_id: string; table?: string | null; column?: string | null }) => {
    const manual = manualTargets[row.row_id];
    if (manual) return JSON.stringify(manual);
    if (row.table && row.column) return JSON.stringify({ table: row.table, column: row.column });
    return '';
  };

  const handleTargetChange = (rowId: string, value: string) => {
    setManualTargets((prev) => {
      const next = { ...prev };
      if (!value) {
        delete next[rowId];
        return next;
      }
      next[rowId] = JSON.parse(value) as { table: string; column: string };
      return next;
    });
  };

  return (
    <section className="dict-panel">
      <div className="dict-panel-head">
        <div>
          <h4>Data Dictionary Mapping</h4>
          <p>{inspecting ? 'Inspecting workbook sheets...' : 'Choose which workbook columns define table names, field names, and descriptions.'}</p>
        </div>
        <div className="dict-actions">
          <button className="rel-btn-cancel" onClick={handlePreview} disabled={!canPreview || loading || inspecting}>
            {loading ? 'Previewing' : 'Preview'}
          </button>
          <button className="rel-btn-confirm" onClick={handleApply} disabled={!canPreview || saving || inspecting}>
            <Check size={13} />
            {saving ? 'Applying' : 'Apply descriptions'}
          </button>
        </div>
      </div>

      {error && <div className="rel-save-error">{error}</div>}
      {!inspecting && candidates && candidates.sheets.length === 0 ? (
        <div className="dict-empty">
          No data dictionary sheet was found in this upload.
        </div>
      ) : null}

      <div className="dict-grid">
        <label>
          <span>Dictionary sheet</span>
          <select value={mapping?.sheet_name ?? ''} onChange={(event) => handleSheetChange(event.target.value)} disabled={!candidates}>
            {(candidates?.sheets ?? []).map((sheet) => (
              <option key={sheet.name} value={sheet.name}>
                {sheet.name}{sheet.is_dictionary_like ? ' (detected)' : ''}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Table column</span>
          <select
            value={mapping?.table_column ?? ''}
            onChange={(event) => updateMapping({ table_column: event.target.value || null })}
            disabled={!selectedSheet}
          >
            <option value="">None / infer table</option>
            {selectedSheet?.columns.map((column) => <option key={column} value={column}>{column}</option>)}
          </select>
        </label>
        <label>
          <span>Field column</span>
          <select
            value={mapping?.column_column ?? ''}
            onChange={(event) => updateMapping({ column_column: event.target.value })}
            disabled={!selectedSheet}
          >
            {selectedSheet?.columns.map((column) => <option key={column} value={column}>{column}</option>)}
          </select>
        </label>
        <label>
          <span>Description column</span>
          <select
            value={mapping?.description_column ?? ''}
            onChange={(event) => updateMapping({ description_column: event.target.value })}
            disabled={!selectedSheet}
          >
            {selectedSheet?.columns.map((column) => <option key={column} value={column}>{column}</option>)}
          </select>
        </label>
        {tableNames.length > 1 && !mapping?.table_column && (
          <label>
            <span>Default table</span>
            <select
              value={mapping?.default_table ?? ''}
              onChange={(event) => updateMapping({ default_table: event.target.value || null })}
            >
              <option value="">Infer from unique column names</option>
              {tableNames.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
        )}
      </div>

      {selectedSheet && (
        <div className="dict-sample">
          <div className="dict-section-title">Sheet preview</div>
          <div className="dict-sample-table">
            <table>
              <thead>
                <tr>
                  {selectedSheet.columns.map((column) => <th key={column}>{column}</th>)}
                </tr>
              </thead>
              <tbody>
                {selectedSheet.sample_rows.slice(0, 4).map((row, index) => (
                  <tr key={index}>
                    {selectedSheet.columns.map((column) => <td key={column}>{row[column] ?? ''}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {preview && (
        <div className="dict-preview">
          <div className="dict-preview-stats">
            <span><strong>{preview.counts.matched}</strong> matched</span>
            <span><strong>{preview.counts.ambiguous}</strong> ambiguous</span>
            <span><strong>{preview.counts.unmatched}</strong> unmatched</span>
            <span><strong>{preview.counts.skipped}</strong> skipped</span>
          </div>
          <div className="dict-sample-table">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Dictionary table</th>
                  <th>Dictionary column</th>
                  <th>Target column</th>
                  <th>Description</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {preview.rows.slice(0, 40).map((row, index) => (
                  <tr key={`${row.source_column}-${index}`}>
                    <td>
                      <span className={`dict-status ${manualTargets[row.row_id] ? 'matched' : row.status}`}>
                        {manualTargets[row.row_id] ? 'manual' : row.status}
                      </span>
                    </td>
                    <td>{row.source_table || ''}</td>
                    <td>{row.source_column}</td>
                    <td>
                      <select
                        className="dict-target-select"
                        value={getRowTarget(row)}
                        onChange={(event) => handleTargetChange(row.row_id, event.target.value)}
                      >
                        <option value="">No target selected</option>
                        {targetOptionsByTable.map((group) => (
                          <optgroup label={group.tableName} key={group.tableName}>
                            {group.options.map((option) => (
                              <option key={option.value} value={option.value}>{option.column}</option>
                            ))}
                          </optgroup>
                        ))}
                      </select>
                    </td>
                    <td>{formatText(row.description)}</td>
                    <td>{manualTargets[row.row_id] ? 'Manual target selected.' : formatText(row.reason)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function DataPreviewEditor({
  schema,
  projectId,
  onSchemaUpdated,
}: {
  schema: RelationalSchema;
  projectId: string;
  onSchemaUpdated?: (schema: RelationalSchema) => void;
}) {
  const tableNames = useMemo(() => Object.keys(schema.schema.tables), [schema.schema.tables]);
  const [selectedTable, setSelectedTable] = useState(tableNames[0] ?? '');
  const [preview, setPreview] = useState<RelationalTablePreview | null>(null);
  const [draftColumns, setDraftColumns] = useState<RelationalTable['columns']>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transformOperation, setTransformOperation] = useState<ModelTransformation['operation']>('trim_text');
  const [transformColumn, setTransformColumn] = useState('');
  const [findValue, setFindValue] = useState('');
  const [replacementValue, setReplacementValue] = useState('');
  const [transforming, setTransforming] = useState(false);
  const [transformMenuColumn, setTransformMenuColumn] = useState<string | null>(null);

  useEffect(() => {
    if (!tableNames.length) {
      setSelectedTable('');
      return;
    }
    if (!selectedTable || !schema.schema.tables[selectedTable]) {
      setSelectedTable(tableNames[0]);
    }
  }, [schema.id, schema.schema.tables, selectedTable, tableNames]);

  useEffect(() => {
    if (!selectedTable) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setSaved(false);
    getRelationalTablePreview(projectId, schema.id, selectedTable)
      .then((result) => {
        if (cancelled) return;
        setPreview(result);
        setDraftColumns(result.columns);
        setTransformColumn((current) => current && result.columns.some((column) => column.name === current) ? current : result.columns[0]?.name ?? '');
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load table preview.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, schema.id, schema.updated_at, schema.schema.transformations, selectedTable]);

  const updateColumnType = (columnName: string, semanticType: string) => {
    setDraftColumns((prev) => prev.map((column) => (
      column.name === columnName ? { ...column, semantic_type: semanticType } : column
    )));
    setSaved(false);
  };

  const handleSave = async () => {
    if (!selectedTable) return;
    setSaving(true);
    setError(null);
    try {
      const result = await updateRelationalSchema(projectId, schema.id, {
        tables: {
          [selectedTable]: {
            columns: draftColumns,
          },
        },
      });
      setPreview((prev) => prev ? { ...prev, columns: draftColumns } : prev);
      setDraftColumns(result.schema.tables[selectedTable]?.columns ?? draftColumns);
      setSaved(true);
      onSchemaUpdated?.(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save type changes.');
    } finally {
      setSaving(false);
    }
  };

  const handleApplyTransform = async () => {
    if (!selectedTable || !transformColumn || !transformOperation) return;
    if (transformOperation === 'replace_value' && !findValue) {
      setError('Enter the value to replace.');
      return;
    }
    if (transformOperation === 'fill_missing' && !replacementValue) {
      setError('Enter a replacement value for missing cells.');
      return;
    }
    const labels: Record<string, string> = {
      trim_text: 'Trim leading and trailing spaces',
      lowercase_text: 'Convert text to lowercase',
      replace_value: 'Replace an exact value',
      fill_missing: 'Fill missing values',
    };
    const step: ModelTransformation = {
      id: `${selectedTable}:${transformColumn}:${transformOperation}:${Date.now()}`,
      table: selectedTable,
      columns: [transformColumn],
      action: labels[transformOperation] ?? 'Manual data transformation',
      operation: transformOperation,
      params: transformOperation === 'replace_value'
        ? { find: findValue, replacement: replacementValue }
        : transformOperation === 'fill_missing' ? { value: replacementValue } : undefined,
      status: 'applied',
      created_at: new Date().toISOString(),
    };
    setTransforming(true);
    setError(null);
    try {
      const result = await updateRelationalSchema(projectId, schema.id, {
        transformations: [...(schema.schema.transformations ?? []), step],
      });
      onSchemaUpdated?.(result);
      setFindValue('');
      setReplacementValue('');
      setTransformMenuColumn(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to apply transformation.');
    } finally {
      setTransforming(false);
    }
  };

  const activePreview = preview;

  return (
    <section className="data-preview-view">
      <div className="data-preview-toolbar">
        <div>
          <h4>{selectedTable || 'Data Preview'}</h4>
          <p>{activePreview ? `${activePreview.row_count.toLocaleString()} rows` : loading ? 'Loading preview...' : 'Preview uploaded rows'}</p>
        </div>
        <div className="data-preview-actions">
          <label>
            <span>Table</span>
            <select value={selectedTable} onChange={(event) => setSelectedTable(event.target.value)}>
              {tableNames.map((name) => <option key={name} value={name}>{name}</option>)}
            </select>
          </label>
          <button className="rel-btn-confirm" onClick={handleSave} disabled={!selectedTable || saving || loading}>
            <Check size={13} />
            {saving ? 'Saving' : saved ? 'Saved' : 'Apply changes'}
          </button>
        </div>
      </div>

      <div className="data-preview-transform">
        <span>Transform</span>
        <select value={transformOperation ?? ''} onChange={(event) => setTransformOperation(event.target.value as ModelTransformation['operation'])}>
          <option value="trim_text">Trim text</option>
          <option value="lowercase_text">Lowercase text</option>
          <option value="replace_value">Replace value</option>
          <option value="fill_missing">Fill missing</option>
        </select>
        <select value={transformColumn} onChange={(event) => setTransformColumn(event.target.value)}>
          {draftColumns.map((column) => <option key={column.name} value={column.name}>{column.name}</option>)}
        </select>
        {transformOperation === 'replace_value' ? (
          <>
            <input value={findValue} onChange={(event) => setFindValue(event.target.value)} placeholder="Find exact value" />
            <input value={replacementValue} onChange={(event) => setReplacementValue(event.target.value)} placeholder="Replace with" />
          </>
        ) : transformOperation === 'fill_missing' ? (
          <input value={replacementValue} onChange={(event) => setReplacementValue(event.target.value)} placeholder="Value for missing cells" />
        ) : null}
        <button className="rel-btn-confirm" type="button" onClick={handleApplyTransform} disabled={transforming || loading || !transformColumn}>
          {transforming ? 'Applying…' : 'Apply transform'}
        </button>
      </div>

      {error && <div className="rel-save-error">{error}</div>}

      {loading ? (
        <div className="data-preview-empty">Loading table preview...</div>
      ) : activePreview ? (
        <div className="data-preview-table">
          <table>
            <thead>
              <tr>
                <th className="data-preview-row-index">#</th>
                {draftColumns.map((column) => (
                  <th key={column.name}>
                    <div className="data-preview-column-head">
                      <strong title={column.name}>{column.name}</strong>
                      <button
                        className={`data-preview-transform-trigger ${transformMenuColumn === column.name ? 'active' : ''}`}
                        type="button"
                        title={`Transform ${column.name}`}
                        aria-label={`Transform ${column.name}`}
                        onClick={() => {
                          setTransformColumn(column.name);
                          setTransformMenuColumn((current) => current === column.name ? null : column.name);
                        }}
                      >
                        <WandSparkles size={13} />
                      </button>
                      <select
                        value={String(column.semantic_type)}
                        onChange={(event) => updateColumnType(column.name, event.target.value)}
                        title={`Set type for ${column.name}`}
                      >
                        <option value="numeric">numeric</option>
                        <option value="categorical">categorical</option>
                        <option value="text">text</option>
                        <option value="datetime">datetime</option>
                      </select>
                      {transformMenuColumn === column.name ? (
                        <div className="data-preview-transform-menu" onClick={(event) => event.stopPropagation()}>
                          <strong>Transform {column.name}</strong>
                          <select value={transformOperation ?? ''} onChange={(event) => setTransformOperation(event.target.value as ModelTransformation['operation'])}>
                            <option value="trim_text">Trim text</option>
                            <option value="lowercase_text">Lowercase text</option>
                            <option value="replace_value">Replace value</option>
                            <option value="fill_missing">Fill missing</option>
                          </select>
                          {transformOperation === 'replace_value' ? (
                            <>
                              <input value={findValue} onChange={(event) => setFindValue(event.target.value)} placeholder="Find exact value" />
                              <input value={replacementValue} onChange={(event) => setReplacementValue(event.target.value)} placeholder="Replace with" />
                            </>
                          ) : transformOperation === 'fill_missing' ? (
                            <input value={replacementValue} onChange={(event) => setReplacementValue(event.target.value)} placeholder="Value for missing cells" />
                          ) : null}
                          <button className="rel-btn-confirm" type="button" onClick={handleApplyTransform} disabled={transforming || loading}>
                            {transforming ? 'Applying…' : 'Apply'}
                          </button>
                        </div>
                      ) : null}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activePreview.rows.map((row, index) => (
                <tr key={index}>
                  <td className="data-preview-row-index">{index + 1}</td>
                  {draftColumns.map((column) => <td key={column.name}>{String(row[column.name] ?? '')}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="data-preview-empty">No preview rows available.</div>
      )}
    </section>
  );
}

function EngineeringRecommendations({
  schema,
  projectId,
  onSchemaUpdated,
}: {
  schema: RelationalSchema;
  projectId: string;
  onSchemaUpdated?: (schema: RelationalSchema) => void;
}) {
  const tables = schema.schema.tables;
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const tableEntries = Object.entries(tables);
  const recommendations = tableEntries.flatMap(([tableName, table]) => {
    const contract = table.data_engineering;
    const tableActions = (contract?.recommended_actions ?? []).map((action) => ({
      tableName,
      action,
      columns: [] as string[],
    }));
    const columnActions = table.columns.flatMap((column) =>
      (column.suggested_actions ?? []).map((action) => ({ tableName, action, columns: [column.name] })),
    );
    return [...tableActions, ...columnActions];
  });
  const dedupedRecommendations = Array.from(
    recommendations.reduce((items, recommendation) => {
      const key = `${recommendation.tableName}:${recommendation.action}`;
      const existing = items.get(key);
      if (existing) {
        existing.columns.push(...recommendation.columns);
      } else {
        items.set(key, { ...recommendation });
      }
      return items;
    }, new Map<string, { tableName: string; action: string; columns: string[] }>()),
  ).map(([, recommendation]) => ({
    ...recommendation,
    columns: [...new Set(recommendation.columns)],
  }));
  const warnings = tableEntries.flatMap(([tableName, table]) =>
    (table.data_engineering?.warnings ?? []).map((warning) => ({ tableName, warning })),
  );
  const readiness = tableEntries.map(([, table]) => table.data_engineering?.readiness_score).filter((score): score is number => score !== undefined);
  const averageReadiness = readiness.length
    ? (readiness.reduce((total, score) => total + score, 0) / readiness.length).toFixed(1)
    : null;
  const operationForAction = (action: string): ModelTransformation['operation'] => {
    const normalized = action.toLowerCase();
    if (normalized.startsWith('normalize null-like')) return 'normalize_null_like';
    if (normalized.startsWith('cast to datetime')) return 'cast_datetime';
    return 'manual_review';
  };
  const decisions = new Map((schema.schema.transformations ?? []).map((step) => [step.id, step]));
  const updateDecision = async (
    recommendation: { tableName: string; action: string; columns: string[] },
    status: ModelTransformation['status'],
  ) => {
    const id = `${recommendation.tableName}:${recommendation.columns.join(',')}:${recommendation.action}`;
    setPendingId(id);
    setActionError(null);
    try {
      const nextStep: ModelTransformation = {
        id,
        table: recommendation.tableName,
        columns: recommendation.columns,
        action: recommendation.action,
        operation: operationForAction(recommendation.action),
        status,
        created_at: new Date().toISOString(),
      };
      const existing = (schema.schema.transformations ?? []).filter((step) => step.id !== id);
      const updated = await updateRelationalSchema(projectId, schema.id, { transformations: [...existing, nextStep] });
      onSchemaUpdated?.(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update the transformation pipeline.');
    } finally {
      setPendingId(null);
    }
  };
  const updatePipeline = async (nextPipeline: ModelTransformation[], pendingKey: string) => {
    setPendingId(pendingKey);
    setActionError(null);
    try {
      const updated = await updateRelationalSchema(projectId, schema.id, { transformations: nextPipeline });
      onSchemaUpdated?.(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Could not update the transformation pipeline.');
    } finally {
      setPendingId(null);
    }
  };
  const history = schema.schema.transformations ?? [];

  return (
    <div className="rel-engineering-panel">
      <div className="rel-engineering-hero">
        <div>
          <span className="rel-editor-label">Data Engineer agent</span>
          <h4>Transformation recommendations</h4>
          <p>Review suggestions generated from each table’s profile before changing the working dataset. Source files are never modified automatically.</p>
        </div>
        {averageReadiness ? <strong className="rel-engineering-score">{averageReadiness}<small>/10 readiness</small></strong> : null}
      </div>

      {actionError ? <div className="rel-save-error">{actionError}</div> : null}

      {dedupedRecommendations.length ? (
        <div className="rel-engineering-list">
          {dedupedRecommendations.map((recommendation, index) => {
            const id = `${recommendation.tableName}:${recommendation.columns.join(',')}:${recommendation.action}`;
            const decision = decisions.get(id);
            const automatic = operationForAction(recommendation.action) !== 'manual_review';
            return (
            <article className={`rel-engineering-item ${decision?.status ?? ''}`} key={`${recommendation.tableName}-${recommendation.action}-${index}`}>
              <WandSparkles size={16} />
              <div>
                <span>{recommendation.tableName}{recommendation.columns.length ? ` · ${recommendation.columns.join(', ')}` : ''}</span>
                <p>{recommendation.action}</p>
              </div>
              <div className="rel-engineering-actions">
                {decision ? (
                  <span className="rel-engineering-decision">{decision.status === 'applied' ? (automatic ? 'Applied' : 'Reviewed') : 'Ignored'}</span>
                ) : (
                  <>
                    <button type="button" onClick={() => updateDecision(recommendation, 'applied')} disabled={pendingId === id}>
                      {pendingId === id ? 'Saving…' : automatic ? 'Apply' : 'Mark reviewed'}
                    </button>
                    <button type="button" className="ignore" onClick={() => updateDecision(recommendation, 'ignored')} disabled={pendingId === id}>Ignore</button>
                  </>
                )}
              </div>
            </article>
            );
          })}
        </div>
      ) : (
        <div className="rel-engineering-empty">The Data Engineer agent has not found any transformations that need review.</div>
      )}

      {warnings.length ? (
        <div className="rel-engineering-warnings">
          <strong>Things to resolve before modelling</strong>
          {warnings.map(({ tableName, warning }, index) => <p key={`${tableName}-${warning}-${index}`}><b>{tableName}:</b> {warning}</p>)}
        </div>
      ) : null}

      <section className="rel-transform-history">
        <div className="rel-transform-history-head">
          <div>
            <span>Working model</span>
            <h4>Transformation history</h4>
          </div>
          <small>{history.length} step{history.length === 1 ? '' : 's'}</small>
        </div>
        {history.length ? (
          <div className="rel-transform-history-list">
            {history.map((step, index) => (
              <article className={`rel-transform-history-item ${step.status}`} key={step.id}>
                <div className="rel-transform-order">{index + 1}</div>
                <div>
                  <strong>{step.action}</strong>
                  <span>{step.table}{step.columns.length ? ` · ${step.columns.join(', ')}` : ''} · {step.status}</span>
                </div>
                <div className="rel-transform-history-actions">
                  <button type="button" disabled={index === 0 || pendingId === step.id} onClick={() => {
                    const next = [...history]; [next[index - 1], next[index]] = [next[index], next[index - 1]];
                    updatePipeline(next, step.id);
                  }}>↑</button>
                  <button type="button" disabled={index === history.length - 1 || pendingId === step.id} onClick={() => {
                    const next = [...history]; [next[index + 1], next[index]] = [next[index], next[index + 1]];
                    updatePipeline(next, step.id);
                  }}>↓</button>
                  <button type="button" disabled={pendingId === step.id} onClick={() => updatePipeline(history.map((item) => item.id === step.id ? { ...item, status: item.status === 'applied' ? 'disabled' : 'applied' } : item), step.id)}>
                    {step.status === 'applied' ? 'Disable' : 'Enable'}
                  </button>
                  <button type="button" className="danger" disabled={pendingId === step.id} onClick={() => updatePipeline(history.filter((item) => item.id !== step.id), step.id)}>Undo</button>
                </div>
              </article>
            ))}
          </div>
        ) : <div className="rel-engineering-empty">Applied transformations will appear here.</div>}
      </section>
    </div>
  );
}

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
    setActiveEditorTab(Object.keys(schema.schema.tables).length > 1 ? 'relationships' : 'preview');
    setSaved(false);
    setSaveError(null);
  }, [schema.id, schema.schema.relationships, schema.schema.tables]);

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
