import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Fallback proxy: używane tylko gdy NEXT_PUBLIC_API_URL jest puste.
  // UWAGA: nie nadaje się do dużych uploadów (proxy Next.js buforuje body) —
  // dlatego front woła API bezpośrednio przez NEXT_PUBLIC_API_URL.
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
