import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// 백엔드(manual.py)는 loopback + same-origin 만 허용하므로
// 브라우저에서 직접 cross-origin 호출을 하지 않고, Vite dev 서버가
// /api/* 요청을 백엔드로 프록시한다. 브라우저에는 same-origin 으로 보인다.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_TARGET || "http://127.0.0.1:8765";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      strictPort: false,
      proxy: {
        "/api": {
          target,
          changeOrigin: true,
        },
      },
    },
  };
});
