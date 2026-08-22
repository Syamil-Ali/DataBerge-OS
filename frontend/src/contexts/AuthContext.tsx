import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

import { API_BASE, csrfToken, setCsrfToken } from '../services/api';

type User = {
  id: string;
  email: string;
  name: string;
  storage_used: number;
  created_at: string;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // The access token is an HttpOnly cookie and is never exposed to JavaScript.
  useEffect(() => {
    localStorage.removeItem('db_token');
    fetch(`${API_BASE}/auth/me`, {
      credentials: 'include',
    })
      .then((r) => {
        if (!r.ok) throw new Error('Invalid');
        return r.json();
      })
      .then((data) => {
        setCsrfToken(data.csrf_token);
        setUser(data.user);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed');
    }
    const data = await res.json();
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  };

  const register = async (email: string, name: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ email, name, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed');
    }
    const data = await res.json();
    setCsrfToken(data.csrf_token);
    setUser(data.user);
  };

  const logout = async () => {
    const csrf = csrfToken();
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: csrf ? { 'X-CSRF-Token': csrf } : {},
    }).catch(() => undefined);
    setCsrfToken();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
