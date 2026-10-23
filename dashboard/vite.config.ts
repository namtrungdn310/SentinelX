import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "SENTINELX_");
  const controllerTarget =
    env.SENTINELX_CONTROLLER_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5174,
      host: true,
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
      proxy: {
        "/api": {
          target: controllerTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
