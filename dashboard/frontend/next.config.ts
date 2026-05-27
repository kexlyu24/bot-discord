import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        // Proxy all API requests to the FastAPI backend.
        // This ensures cookies set by the backend are scoped to
        // localhost:3000 (the frontend origin), solving cross-port
        // cookie issues during local development.
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
      },
    ];
  },
};

export default nextConfig;
