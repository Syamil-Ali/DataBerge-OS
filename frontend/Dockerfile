FROM node:22.17.0-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
# Production traffic stays same-origin and is forwarded by the Nginx /api proxy.
# This keeps HttpOnly session cookies first-party and avoids cross-site auth failures.
ENV VITE_API_BASE_URL=/api
RUN npm run build

FROM nginx:1.27.5-alpine
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
ENV BACKEND_ORIGIN=http://backend:8000 \
    NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1 \
    NGINX_ENVSUBST_FILTER="BACKEND_ORIGIN|NGINX_LOCAL_RESOLVERS"
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
