import { useCallback, useEffect, useState } from 'react';

export type AppRoute = 'main' | 'login' | 'signup' | 'upload' | 'workspace';
export type Navigate = (route: AppRoute, options?: { replace?: boolean }) => void;

const routePath = (route: AppRoute) => (route === 'main' ? '/main' : `/${route}`);

const normalizeRoute = (pathname: string): AppRoute => {
  const clean = pathname.replace(/\/+$/, '') || '/';
  if (clean === '/' || clean === '/main') return 'main';
  if (clean === '/login') return 'login';
  if (clean === '/signup') return 'signup';
  if (clean === '/upload') return 'upload';
  if (clean === '/workspace') return 'workspace';
  return 'main';
};

export function useAppRoute(): [AppRoute, Navigate] {
  const [route, setRoute] = useState<AppRoute>(() => normalizeRoute(window.location.pathname));

  const navigate = useCallback<Navigate>((nextRoute, options) => {
    const nextPath = routePath(nextRoute);
    if (window.location.pathname !== nextPath) {
      if (options?.replace) window.history.replaceState(null, '', nextPath);
      else window.history.pushState(null, '', nextPath);
    }
    setRoute(nextRoute);
  }, []);

  useEffect(() => {
    const handlePopState = () => setRoute(normalizeRoute(window.location.pathname));
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    const clean = window.location.pathname.replace(/\/+$/, '') || '/';
    const canonicalPath = routePath(route);
    if (clean !== canonicalPath) window.history.replaceState(null, '', canonicalPath);
  }, [route]);

  return [route, navigate];
}
