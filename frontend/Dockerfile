
# ==========================================
# Dependencies
# ==========================================
FROM node:22-alpine AS deps

WORKDIR /app

ARG APP_ENV=production

COPY package.json package-lock.json ./

RUN --mount=type=secret,id=corporate_ca,target=/run/secrets/corporate-ca.pem,required=false \
    if [ "$APP_ENV" = "development" ]; then \
        test -s /run/secrets/corporate-ca.pem || \
            (echo "ERROR: Corporate CA certificate was not provided." && exit 1); \
        NODE_EXTRA_CA_CERTS=/run/secrets/corporate-ca.pem \
            npm ci --no-audit --no-fund || \
            (echo "===== NPM DEBUG LOG =====" && \
             cat /root/.npm/_logs/*-debug-0.log && exit 1); \
    else \
        npm ci --no-audit --no-fund; \
    fi


# ==========================================
# Build
# ==========================================
FROM node:22-alpine AS builder

WORKDIR /app

ARG APP_ENV=production
ARG NEXT_PUBLIC_API_BASE_URL

ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_TELEMETRY_DISABLED=1

COPY --from=deps /app/node_modules ./node_modules
COPY . .

RUN --mount=type=secret,id=corporate_ca,target=/run/secrets/corporate-ca.pem,required=false \
    if [ "$APP_ENV" = "development" ]; then \
        test -s /run/secrets/corporate-ca.pem || \
            (echo "ERROR: Corporate CA certificate was not provided." && exit 1); \
        NODE_EXTRA_CA_CERTS=/run/secrets/corporate-ca.pem npm run build; \
    else \
        npm run build; \
    fi


# ==========================================
# Production runtime
# ==========================================
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

COPY --from=builder --chown=nextjs:nodejs /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
