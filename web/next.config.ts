import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Fallback proxy: used only when NEXT_PUBLIC_API_URL is empty.
  // NOTE: not suitable for large uploads (the Next.js proxy buffers the body) —
  // that's why the frontend calls the API directly via NEXT_PUBLIC_API_URL.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

export default nextConfig;
