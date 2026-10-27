import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  async rewrites() {
    // Only our own API goes to the backend. /api/auth is handled by Neon Auth's route handler.
    return [
      { source: "/api/v1/:path*", destination: `${backend}/v1/:path*` },
      // Wakes the sleeping servers (see lib/warm.ts).
      { source: "/api/warm", destination: `${backend}/warmz` },
    ];
  },
};

export default config;
