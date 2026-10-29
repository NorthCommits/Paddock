import type { NextConfig } from "next";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const config: NextConfig = {
  async headers() {
    // The consent page must never be framed, or a hostile site could click Allow for the person.
    return [
      {
        source: "/oauth/:path*",
        headers: [
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
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
