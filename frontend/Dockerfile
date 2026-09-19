ARG NODE_VERSION=24.21.0-slim

FROM node:${NODE_VERSION} AS dependencies

WORKDIR /app

# Copy package-related files
COPY package.json package-lock.json* ./

# Install dependencies
RUN --mount=type=cache,target=/root/.npm \
  npm ci --no-audit --no-fund

# Build Next.js application
FROM node:${NODE_VERSION} AS builder

WORKDIR /app

# Copy project dependencies from dependencies stage
COPY --from=dependencies /app/node_modules ./node_modules

# Copy application source code
COPY . .

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# NEXT_PUBLIC_* values are compiled into browser JavaScript at build time. Compose passes
# /api so every deployed browser uses the same nginx origin instead of a fixed host/IP.
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ARG NEXT_PUBLIC_WORKBENCH_QUERY_ATTRIBUTION=false
ENV NEXT_PUBLIC_WORKBENCH_QUERY_ATTRIBUTION=${NEXT_PUBLIC_WORKBENCH_QUERY_ATTRIBUTION}

RUN --mount=type=cache,target=/app/.next/cache \
  npm run build


# Run Next.js application
FROM node:${NODE_VERSION} AS runner

WORKDIR /app

# Set production environment variables
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Copy production assets
COPY --from=builder --chown=node:node /app/public ./public

# Set the correct permission for prerender cache
RUN mkdir .next
RUN chown node:node .next

COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static

# Next.js runtime does not require the build cache. The builder's cache is
# mounted only for the build and may not exist as an image path afterward.

# Switch to non-root user for security best practices
USER node

# Expose port 3000 to allow HTTP traffic
EXPOSE 3000

# Start Next.js standalone server
CMD ["node", "server.js"]
