// Same-origin proxy to FastAPI.
//
// The browser bundle must not contain this host's address: a public env var gets inlined
// at build time, so every other machine on the LAN would resolve it against its own
// localhost and the app would break for anyone but the host. A Next rewrite is not enough
// because a rewrite to a different origin is answered with a redirect, which puts the
// backend URL back into the browser and reintroduces the exact problem.
//
// This handler forwards the request server-side instead, so the browser only ever talks to
// the origin it loaded the page from. Production does the same job with nginx forwarding
// /api/* to FastAPI, which is why /api is the only path this owns.
import { NextRequest } from 'next/server';

// Server-side only, never NEXT_PUBLIC_*. Defaults to the same host's backend.
const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8001';

// Next.js route handlers are static by default; this must run per request.
export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// The backend's own timeout is generous for retrieval, but a hung request must not pin a
// Next worker forever, so the edge of the request is bounded here too.
const UPSTREAM_TIMEOUT_MS = 120_000;

// Never forwarded upstream. The hop-by-hop set describes the browser's connection rather
// than the API's, and Host in particular breaks virtual hosting and any request signing.
// `expect` and `accept-encoding` are here for undici: fetch refuses to send Expect at all
// (it throws "expect header not supported", which surfaced as a bare 502), and it only
// decompresses a response when it negotiated the encoding itself. Passing either through
// makes undici hand back bytes that are still compressed under a header we then strip.
const NOT_FORWARDED = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
  'host',
  'content-length',
  'expect',
  'accept-encoding',
]);

function forwardableHeaders(headers: Headers): Headers {
  const out = new Headers();
  headers.forEach((value, key) => {
    if (!NOT_FORWARDED.has(key.toLowerCase())) out.set(key, value);
  });
  return out;
}

// Response headers that describe the transport rather than the payload. content-encoding is
// removed because undici has already decoded the body by this point.
const STRIPPED_RESPONSE_HEADERS = new Set([
  ...NOT_FORWARDED,
]);

// The upstream path is taken from the raw request URL rather than the catch-all params,
// which drop a trailing slash. FastAPI's routes are registered with trailing slashes and
// answer a slash-less request with a redirect to the backend's own origin, so the slash the
// client sent has to survive the hop.
function upstreamPath(request: NextRequest): string | null {
  const { pathname } = new URL(request.url);
  if (!pathname.startsWith('/api/') && pathname !== '/api') return null;
  const rest = pathname.slice('/api'.length) || '/';
  // A proxy must not let a caller walk out of the backend with dot segments.
  if (rest.split('/').some((segment) => segment === '..' || segment === '.')) return null;
  return rest;
}

async function proxy(request: NextRequest): Promise<Response> {
  const forwarded = upstreamPath(request);
  if (forwarded === null) {
    return Response.json({ detail: 'Not found' }, { status: 404 });
  }

  const search = request.nextUrl.search;
  const target = `${BACKEND_URL}${forwarded}${search}`;

  const hasBody = !['GET', 'HEAD'].includes(request.method);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: forwardableHeaders(request.headers),
      body: hasBody ? await request.arrayBuffer() : undefined,
      // Required so Next does not cache a per-user API response in a shared cache.
      cache: 'no-store',
      signal: controller.signal,
      redirect: 'manual',
    });

    const headers = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!STRIPPED_RESPONSE_HEADERS.has(key.toLowerCase())) headers.set(key, value);
    });

    // Streamed rather than buffered so server-sent events stay incremental.
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers,
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === 'AbortError';
    // The real cause goes to the server log; the client gets a stable, non-leaking message.
    // undici reports every transport problem as a bare "fetch failed" and hides the actual
    // errno in `cause`, so the cause has to be unwrapped to be diagnosable.
    const cause = err instanceof Error ? (err as { cause?: unknown }).cause : undefined;
    console.error(
      `[api-proxy] ${request.method} ${target} failed:`,
      err instanceof Error ? `${err.name}: ${err.message}` : err,
      cause ? `| cause: ${cause instanceof Error ? `${cause.name}: ${cause.message}` : String(cause)}` : '',
    );
    return Response.json(
      {
        detail: aborted
          ? `Upstream API did not respond within ${UPSTREAM_TIMEOUT_MS / 1000}s.`
          : 'Upstream API is unreachable. Is the Genesis backend running on port 8001?',
      },
      { status: aborted ? 504 : 502 },
    );
  } finally {
    clearTimeout(timer);
  }
}

export async function GET(request: NextRequest): Promise<Response> {
  return proxy(request);
}

export async function POST(request: NextRequest): Promise<Response> {
  return proxy(request);
}

export async function PUT(request: NextRequest): Promise<Response> {
  return proxy(request);
}

export async function PATCH(request: NextRequest): Promise<Response> {
  return proxy(request);
}

export async function DELETE(request: NextRequest): Promise<Response> {
  return proxy(request);
}
