# Data-Berge OS frontend

React 19 and Vite frontend for the Data-Berge OS workspace.

## Local development

~~~powershell
npm ci
npm run dev
~~~

Vite proxies /api to http://localhost:8000 by default.

## Validation

~~~powershell
npm audit --audit-level=high
npm run test:run
npm run build
npm run test:e2e
~~~

## Production

The production container builds static assets and serves them through Nginx. Nginx applies browser security headers and proxies /api to BACKEND_ORIGIN, keeping HttpOnly session cookies same-origin.
