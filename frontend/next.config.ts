import type { NextConfig } from "next";

// /api/* is proxied to FastAPI by app/api/[...path]/route.ts rather than by a rewrite here.
// A rewrite to a different origin is answered with a redirect, which puts the backend
// address back into the browser and breaks for any client that is not the host.
const nextConfig: NextConfig = {
	output: "standalone",
	// FastAPI registers its routes with trailing slashes (/auth/me/), and redirect_slashes
	// answers a slash-less request with a 307 to the slashed one. That redirect would send
	// the browser straight to the backend's origin, so /api paths are passed through exactly
	// as the client wrote them instead of being normalised on the way in.
	skipTrailingSlashRedirect: true,
};

export default nextConfig;
