FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.28-alpine
ENV FRONTEND_PORT=8080 \
    BACKEND_UPSTREAM=http://backend:8000 \
    NGINX_ENVSUBST_FILTER="^(FRONTEND_PORT|BACKEND_UPSTREAM)$"
COPY nginx/security-headers.conf /etc/nginx/security-headers.conf
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null "http://127.0.0.1:${FRONTEND_PORT}/healthz" || exit 1
