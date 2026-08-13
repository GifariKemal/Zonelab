import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

const nextConfig: NextConfig = {
  // Without this, Turbopack walks up past the repo and picks up the stray
  // package-lock.json in the Windows home directory as the workspace root.
  turbopack: { root: fileURLToPath(new URL(".", import.meta.url)) },

  // The dev server treats a request whose Origin is not its own host as
  // cross-origin and answers /_next/static/* with 403. Opening the app on
  // 127.0.0.1 while the server considers itself localhost therefore serves the
  // HTML but none of the JavaScript, which looks exactly like a broken app.
  // Both spellings of loopback are the same machine here.
  allowedDevOrigins: ["localhost", "127.0.0.1"],

  // The floating dev badge parks itself over the bottom-left toolbox controls.
  devIndicators: false,
};

export default nextConfig;
