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

# Switch to non-root user for security best practices
USER node

# Expose port 3000 to allow HTTP traffic
EXPOSE 3000

# Start Next.js standalone server
CMD ["node", "server.js"]
