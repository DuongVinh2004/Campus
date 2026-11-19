import type { NextConfig } from "next";

// An isolated build destination allows verification without touching another runtime.
const destination = process.env.CAMPUS_NEXT_DIST_DIR;
if (destination && !/^\.next-stitch-[a-z0-9-]+$/.test(destination)) {
  throw new Error("CAMPUS_NEXT_DIST_DIR must name a local .next-stitch-* directory");
}
const backend = process.env.CAMPUS_BACKEND_URL || "http://127.0.0.1:8006";
const backendUrl = new URL(backend);
if (backendUrl.pathname !== "/" || backendUrl.search || backendUrl.hash || backendUrl.username || backendUrl.password) {
  throw new Error("CAMPUS_BACKEND_URL must be an origin without credentials or a path");
}
const config: NextConfig = {
  ...(destination ? { distDir: destination } : {}),
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    return {
      beforeFiles: ["/v1/:path*", "/api/v1/:path*", "/health/:path*"].map(source => ({
        source,
        destination: `${backendUrl.origin}${source}`,
      })),
      afterFiles: [],
      fallback: [],
    };
  },
};
export default config;
