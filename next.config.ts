import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // On Vercel, api/analyze.py is its own function. Locally, `npm run dev:api` serves it on :8000.
  async rewrites() {
    if (process.env.NODE_ENV !== "development") return [];
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8000/api/:path*" }];
  },
};

export default nextConfig;
