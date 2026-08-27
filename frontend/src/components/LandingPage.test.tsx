import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LandingPage } from './LandingPage';

describe('authenticated data setup navigation', () => {
  it('uses the configured session exit action instead of returning to the public landing page', () => {
    const onSetupExit = vi.fn();

    render(
      <LandingPage
        busy={false}
        initialStep="setup"
        onUpload={vi.fn()}
        onSetupExit={onSetupExit}
        setupExitLabel="Log out"
        setupExitKind="logout"
      />,
    );

    expect(screen.queryByRole('button', { name: 'Back to landing' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
    expect(onSetupExit).toHaveBeenCalledOnce();
  });
});
