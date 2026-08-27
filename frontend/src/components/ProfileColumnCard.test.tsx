import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ProfileColumn, RelationalTable } from '../types/domain';
import { ProfileColumnCard } from './ProfileColumnCard';

describe('ProfileColumnCard', () => {
  it('renders a standard profile column through the shared card', () => {
    const column: ProfileColumn = {
      name: 'region',
      dtype: 'VARCHAR',
      semantic_type: 'text',
      missing_count: 0,
      missing_pct: 0,
      unique_count: 4,
      sample_values: ['Central'],
    };

    render(<ProfileColumnCard column={column} />);

    expect(screen.getByRole('heading', { name: 'region' })).toBeInTheDocument();
    expect(screen.getByText('VARCHAR')).toBeInTheDocument();
    expect(screen.getByText('Central')).toBeInTheDocument();
  });

  it('retains relational key and table context', () => {
    const column: RelationalTable['columns'][number] = {
      name: 'customer_id',
      duckdb_type: 'BIGINT',
      semantic_type: 'numeric',
      key_type: 'FK',
      missing_count: 0,
      missing_pct: 0,
      unique_count: 842,
      sample_values: ['1001'],
    };

    render(<ProfileColumnCard column={column} tableName="orders" />);

    expect(screen.getByText('BIGINT')).toBeInTheDocument();
    expect(screen.getByText('FK')).toBeInTheDocument();
  });
});
