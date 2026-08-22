import { beforeEach, describe, expect, it } from 'vitest';

import { csrfToken, setCsrfToken } from './api';

describe('CSRF token handling', () => {
  beforeEach(() => {
    setCsrfToken();
    document.cookie = 'db_csrf=; Max-Age=0; path=/';
  });

  it('keeps cross-origin CSRF state in memory', () => {
    setCsrfToken('server-token');
    expect(csrfToken()).toBe('server-token');
  });

  it('falls back to a same-origin CSRF cookie', () => {
    document.cookie = 'db_csrf=cookie-token; path=/';
    expect(csrfToken()).toBe('cookie-token');
  });
});
