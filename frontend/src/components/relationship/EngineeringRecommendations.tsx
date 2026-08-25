import { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, Check, GitBranch, Link2, Link2Off, Plus, Table2, Trash2, WandSparkles } from 'lucide-react';

import { ModelTransformation, RelationalRelationship, RelationalSchema, RelationalTable } from '../../types/domain';
import { formatText } from '../../utils/format';
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
} from '../../services/api';
export function EngineeringRecommendations({
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
  const readinessValue = averageReadiness ? Number(averageReadiness) : null;
  const readinessLabel = readinessValue === null
    ? null
    : readinessValue >= 8
      ? 'Ready'
      : readinessValue >= 6
        ? 'Review suggested'
        : 'Preparation needed';
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
          <span className="rel-editor-label">Data preparation check</span>
          <h4>{readinessLabel === 'Ready' ? 'Your data is ready to analyze' : 'Review suggested improvements'}</h4>
          <p>Data-Berge checked your tables for structural issues and possible improvements. Any suggested fixes appear below, and nothing changes without your approval.</p>
        </div>
        {averageReadiness && readinessLabel ? (
          <span className="rel-engineering-status">
            <strong>{readinessLabel}</strong>
          </span>
        ) : null}
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
