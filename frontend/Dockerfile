# 1. Сборка сайта
FROM node:24-alpine AS build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# 2. Caddy: раздаёт сайт, проксирует API и фото на бэкенд, сам получает HTTPS
FROM caddy:2-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
