import type { NextConfig } from "next";

// In dev the browser talks only to the Next.js origin; /api/* is proxied to the
// FastAPI backend so the session cookie stays first-party (no CORS). In
// production, point API_PROXY_TARGET at the API or terminate both behind one
// domain at the edge.
const apiTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiTarget}/:path*` }];
  },
};

export default nextConfig;
