# syntax=docker/dockerfile:1
# Use BuildKit for cache mounts: DOCKER_BUILDKIT=1 (default in Docker 23+)
FROM node:20-alpine AS base
WORKDIR /app

FROM base AS deps
COPY apps/web/package.json apps/web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web/ .
RUN mkdir -p /app/public
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
RUN --mount=type=cache,target=/app/.next/cache \
    npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 8080
ENV PORT=8080
ENV HOSTNAME="0.0.0.0"
CMD ["node", "server.js"]
