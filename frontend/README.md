# Frontend

Next.js React application for the Company Intelligence Agent.

## Structure

```
frontend/
├── app/              # Next.js App Router pages
│   ├── page.tsx      # Dashboard
│   ├── layout.tsx    # Root layout
│   ├── companies/    # Company list page
│   ├── knowledge-base/  # RAG chat page
│   └── usage/        # Usage stats page
├── lib/              # Utilities
│   └── api.ts        # API client
├── package.json      # Dependencies
├── Dockerfile        # Docker image
└── config files      # Next.js, Tailwind, TypeScript
```

## Setup

### Local Development

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Open http://localhost:3000

## Build

```bash
npm run build
```

## Environment Variables

- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000/api)

Authentication is driven by the Django API's `/api/auth/oidc/config/` endpoint.
For local development, configure the backend with:

- `KEYCLOAK_SERVER_URL=http://localhost:8080`
- `KEYCLOAK_REALM=workspace-hub`
- `KEYCLOAK_CLIENT_ID=company-intelligence`
- `FRONTEND_URL=http://localhost:3000`

The Keycloak client must allow `http://localhost:3000/callback` as a redirect URI,
`http://localhost:3000/login` as a post-logout redirect URI, and
`http://localhost:3000` as a web origin.

## Features

- **Dashboard**: Overview statistics
- **Companies**: List, sync, and trigger scraping
- **Knowledge Base**: RAG chat interface
- **Usage**: API usage statistics
