import type { NextConfig } from "next";

// Backend origin, reachable from the Next.js server (not the browser).
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8010";

const nextConfig: NextConfig = {
  // Same-origin proxy: the browser calls /api/* on this app (port 3010) and
  // Next forwards to the FastAPI backend. No CORS, works from remote browsers.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
