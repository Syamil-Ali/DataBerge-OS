import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { ChartActionMenu } from './ChartActionMenu';

describe('ChartActionMenu', () => {
  it('closes when the user presses outside the menu', () => {
    render(<ChartActionMenu label="revenue" onAttach={vi.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Chart actions for revenue' }));
    expect(screen.getByRole('menu')).toBeInTheDocument();

    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
