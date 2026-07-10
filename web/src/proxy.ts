import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// In dev the browser talks only to the Next.js origin; /api/* is proxied to
// the FastAPI backend so the session cookie stays first-party (no CORS). In
// production this also attaches a shared secret so the API can reject any
// /admin or /auth request that didn't come through this proxy.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export function proxy(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const upstreamPath = pathname.replace(/^\/api/, "");
  const destination = new URL(`${apiTarget}${upstreamPath}${search}`);

  const headers = new Headers(request.headers);
  const secret = process.env.PROXY_SHARED_SECRET;
  if (secret) headers.set("X-Undocking-Proxy-Secret", secret);

  return NextResponse.rewrite(destination, { request: { headers } });
}

export const config = {
  matcher: ["/api/:path*"],
};
