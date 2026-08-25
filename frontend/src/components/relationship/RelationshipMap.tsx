import { useEffect, useState } from 'react';
import { ArrowRight, GitBranch, Link2, Link2Off, Plus, Table2, Trash2 } from 'lucide-react';

import { RelationalRelationship, RelationalTable } from '../../types/domain';

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

export function RelationshipMap({
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
        <div className="rel-model-flow-scroll">
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
        </div>
        {showAddForm ? (
          <AddRelationshipForm
            tables={tables}
            onAdd={onAddRelationship}
            onCancel={onCancelAdd}
          />
        ) : null}
        <button
          className="rel-btn-add rel-btn-add-inline"
          onClick={onShowAddForm}
          disabled={showAddForm || tableNames.length < 2}
        >
          <Plus size={13} /> Add relationship
        </button>
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
