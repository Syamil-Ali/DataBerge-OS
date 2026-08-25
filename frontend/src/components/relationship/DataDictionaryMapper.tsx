import { useEffect, useMemo, useState } from 'react';
import { Check } from 'lucide-react';

import { RelationalSchema } from '../../types/domain';
import { formatText } from '../../utils/format';
import {
  applyDictionaryMapping,
  DictionaryCandidatesResponse,
  DictionaryMapping,
  DictionaryPreviewResponse,
  getDictionaryCandidates,
  previewDictionaryMapping,
} from '../../services/api';
export function DataDictionaryMapper({
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
