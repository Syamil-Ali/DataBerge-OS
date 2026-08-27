import { render, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import App from './App';

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./services/api')>();
  return {
    ...actual,
    getProjects: vi.fn().mockResolvedValue([]),
  };
});

describe('authenticated route handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.history.replaceState(null, '', '/');
  });

  it('returns an authenticated user from the public route to the data setup flow', async () => {
    window.history.replaceState(null, '', '/main');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        csrf_token: 'csrf-value',
        user: {
          id: 'u1',
          email: 'owner@example.com',
          name: 'Owner',
          storage_used: 0,
          created_at: '2026-08-27T00:00:00Z',
        },
      }),
    }));

    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/upload'));
  });
});
