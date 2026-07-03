'use client';

import { auth, clearLocalAuthState, type OidcConfig } from '@/lib/api';

const CODE_VERIFIER_KEY = 'keycloak_pkce_verifier';
const OIDC_STATE_KEY = 'keycloak_oidc_state';

function browserRedirectUri(): string {
  // Always derived from the actual browser origin so Keycloak redirects back
  // to the same host, keeping sessionStorage accessible on the callback page.
  return `${window.location.origin}/callback`;
}

function browserAuthorizationEndpoint(config: OidcConfig): string {
  // Replace the Keycloak hostname with the browser's current hostname so the
  // SSO cookie is set for the same domain on every host (localhost, Tailscale
  // IP, etc.). The port and path stay as configured in the backend.
  const url = new URL(config.authorization_endpoint);
  url.hostname = window.location.hostname;
  return url.toString();
}

export async function startKeycloakLogin(): Promise<void> {
  const config = await auth.oidcConfig();
  const codeVerifier = randomBase64Url(64);
  const codeChallenge = await sha256Base64Url(codeVerifier);
  const state = randomBase64Url(32);

  sessionStorage.setItem(CODE_VERIFIER_KEY, codeVerifier);
  sessionStorage.setItem(OIDC_STATE_KEY, state);
  clearLocalAuthState();

  const params = new URLSearchParams({
    client_id: config.client_id,
    redirect_uri: browserRedirectUri(),
    response_type: 'code',
    scope: 'openid profile email',
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
    state,
  });

  window.location.href = `${browserAuthorizationEndpoint(config)}?${params.toString()}`;
}

export function readStoredPkceState(): { codeVerifier: string | null; state: string | null } {
  return {
    codeVerifier: sessionStorage.getItem(CODE_VERIFIER_KEY),
    state: sessionStorage.getItem(OIDC_STATE_KEY),
  };
}

export function clearStoredPkceState(): void {
  sessionStorage.removeItem(CODE_VERIFIER_KEY);
  sessionStorage.removeItem(OIDC_STATE_KEY);
}

export function callbackRedirectUri(_config: OidcConfig): string {
  return browserRedirectUri();
}

function randomBase64Url(byteLength: number): string {
  const bytes = new Uint8Array(byteLength);
  crypto.getRandomValues(bytes);
  return base64Url(bytes);
}

async function sha256Base64Url(value: string): Promise<string> {
  const data = new TextEncoder().encode(value);
  if (crypto?.subtle) {
    const digest = await crypto.subtle.digest('SHA-256', data);
    return base64Url(new Uint8Array(digest));
  }
  return base64Url(sha256Sync(data));
}

function rotr32(x: number, n: number): number {
  return (x >>> n) | (x << (32 - n));
}

function sha256Sync(message: Uint8Array): Uint8Array {
  const K = new Uint32Array([
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ]);
  const msgLen = message.length;
  const padLen = msgLen % 64 < 56 ? 56 - (msgLen % 64) : 120 - (msgLen % 64);
  const padded = new Uint8Array(msgLen + padLen + 8);
  padded.set(message);
  padded[msgLen] = 0x80;
  const dv = new DataView(padded.buffer);
  const bitLen = msgLen * 8;
  dv.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000), false);
  dv.setUint32(padded.length - 4, bitLen >>> 0, false);
  let h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a;
  let h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
  const W = new Uint32Array(64);
  for (let i = 0; i < padded.length; i += 64) {
    for (let j = 0; j < 16; j++) W[j] = dv.getUint32(i + j * 4, false);
    for (let j = 16; j < 64; j++) {
      const s0 = rotr32(W[j - 15], 7) ^ rotr32(W[j - 15], 18) ^ (W[j - 15] >>> 3);
      const s1 = rotr32(W[j - 2], 17) ^ rotr32(W[j - 2], 19) ^ (W[j - 2] >>> 10);
      W[j] = (W[j - 16] + s0 + W[j - 7] + s1) >>> 0;
    }
    let a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
    for (let j = 0; j < 64; j++) {
      const S1 = rotr32(e, 6) ^ rotr32(e, 11) ^ rotr32(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + S1 + ch + K[j] + W[j]) >>> 0;
      const S0 = rotr32(a, 2) ^ rotr32(a, 13) ^ rotr32(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0;
      d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    h0 = (h0 + a) >>> 0; h1 = (h1 + b) >>> 0; h2 = (h2 + c) >>> 0; h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0; h5 = (h5 + f) >>> 0; h6 = (h6 + g) >>> 0; h7 = (h7 + h) >>> 0;
  }
  const out = new Uint8Array(32);
  const ov = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((v, i) => ov.setUint32(i * 4, v, false));
  return out;
}

function base64Url(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
