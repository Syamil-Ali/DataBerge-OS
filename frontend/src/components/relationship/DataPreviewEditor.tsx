import { useEffect, useMemo, useState } from 'react';
import { Check, WandSparkles } from 'lucide-react';

import { ModelTransformation, RelationalSchema, RelationalTable } from '../../types/domain';
import {
  getRelationalTablePreview,
  RelationalTablePreview,
  updateRelationalSchema,
} from '../../services/api';
export function DataPreviewEditor({
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
  const [draftColumnsByTable, setDraftColumnsByTable] = useState<Record<string, RelationalTable['columns']>>({});
  const [dirtyTables, setDirtyTables] = useState<Set<string>>(() => new Set());
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
  const draftColumns = draftColumnsByTable[selectedTable] ?? preview?.columns ?? [];

  useEffect(() => {
    setDraftColumnsByTable({});
    setDirtyTables(new Set());
    setPreview(null);
    setSaved(false);
  }, [schema.id]);

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
        setDraftColumnsByTable((current) => (
          current[selectedTable]
            ? current
            : { ...current, [selectedTable]: result.columns }
        ));
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
    if (!selectedTable) return;
    setDraftColumnsByTable((current) => ({
      ...current,
      [selectedTable]: (current[selectedTable] ?? preview?.columns ?? []).map((column) => (
        column.name === columnName ? { ...column, semantic_type: semanticType } : column
      )),
    }));
    setDirtyTables((current) => new Set(current).add(selectedTable));
    setSaved(false);
  };

  const handleSave = async () => {
    if (!selectedTable || dirtyTables.size === 0) return;
    setSaving(true);
    setError(null);
    try {
      const tableUpdates = Object.fromEntries(
        [...dirtyTables]
          .filter((tableName) => draftColumnsByTable[tableName])
          .map((tableName) => [tableName, { columns: draftColumnsByTable[tableName] }]),
      );
      const result = await updateRelationalSchema(projectId, schema.id, {
        tables: tableUpdates,
      });
      setDraftColumnsByTable((current) => {
        const next = { ...current };
        for (const tableName of dirtyTables) {
          next[tableName] = result.schema.tables[tableName]?.columns ?? current[tableName];
        }
        return next;
      });
      setPreview((current) => current
        ? { ...current, columns: result.schema.tables[selectedTable]?.columns ?? current.columns }
        : current);
      setDirtyTables(new Set());
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
          <button className="rel-btn-confirm" onClick={handleSave} disabled={!selectedTable || dirtyTables.size === 0 || saving || loading}>
            <Check size={13} />
            {saving
              ? 'Saving'
              : saved
                ? 'Saved'
                : dirtyTables.size > 1
                  ? `Apply changes (${dirtyTables.size} tables)`
                  : 'Apply changes'}
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
