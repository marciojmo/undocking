import type { NextConfig } from "next";

// The /api/* proxy to the FastAPI backend lives in middleware.ts (not here) —
// it needs to attach a shared-secret header to the proxied request, which
// next.config.ts rewrites can't do.
const nextConfig: NextConfig = {};

export default nextConfig;
