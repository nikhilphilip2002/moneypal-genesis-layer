# Dockerfile for Next.js Frontend
FROM node:20-alpine

WORKDIR /app

# Cap node heap during install AND build so npm itself does not OOM-die
# inside resource-constrained build hosts (manifests as the
# "Exit handler never called!" npm crash). 512M was too low for Next 16
# + React 19 + the radix-ui dep tree.
ENV NODE_OPTIONS="--max-old-space-size=2048"
ENV NPM_CONFIG_AUDIT=false
ENV NPM_CONFIG_FUND=false
ENV NPM_CONFIG_UPDATE_NOTIFIER=false

# Copy package files
COPY package*.json ./

# Prefer the deterministic lockfile install. Fall back to `npm install`
# only if no lockfile is present. Force --include=dev so build-time tools
# are present even if NODE_ENV=production is in the environment, and
# verify that the `next` binary symlink was created — earlier npm crashes
# left a half-installed node_modules in the build cache.
RUN if [ -f package-lock.json ]; then \
      npm ci --legacy-peer-deps --include=dev --prefer-offline --no-audit --no-fund; \
    else \
      npm install --legacy-peer-deps --include=dev --no-audit --no-fund; \
    fi && \
    test -x node_modules/.bin/next || (echo "next binary missing after install" && exit 1)

# Copy project files
COPY . .

# Build arguments
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

# Bind to all interfaces so other containers (nginx) can reach this server
ENV HOSTNAME="0.0.0.0"

# Build the application via the package.json `build` script. npm resolves
# the `next` binary through its own lookup chain, which is more robust
# than calling ./node_modules/.bin/next directly and avoids npx, which
# probes registry.npmjs.org and fails with ERR_SSL_WRONG_VERSION_NUMBER
# in this build environment.
RUN npm run build -- --webpack

# Expose port
EXPOSE 3000

# Start the application — bind explicitly to 0.0.0.0
CMD ["npm", "start"]
