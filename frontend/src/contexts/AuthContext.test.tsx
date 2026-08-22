import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AuthProvider, useAuth } from './AuthContext';

function CurrentUser() {
  const { user, loading } = useAuth();
  if (loading) return <span>Loading</span>;
  return <span>{user?.name || 'Signed out'}</span>;
}

describe('AuthProvider', () => {
  afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
  });

  it('restores an HttpOnly session and removes a legacy bearer token', async () => {
    localStorage.setItem('db_token', 'legacy-token');
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        user: { id: 'u1', email: 'owner@example.com', name: 'Owner' },
        csrf_token: 'csrf-value',
      }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AuthProvider><CurrentUser /></AuthProvider>);

    expect(await screen.findByText('Owner')).toBeInTheDocument();
    expect(localStorage.getItem('db_token')).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/auth/me'),
      expect.objectContaining({ credentials: 'include' }),
    );
  });
});
