import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ProxyOptions } from "vite";

// 백엔드(python -m apps.web)는 loopback + same-origin 만 허용하므로
// 브라우저에서 직접 cross-origin 호출을 하지 않고, Vite dev 서버가
// /api/* 요청을 백엔드로 프록시한다. 브라우저에는 same-origin 으로 보인다.
export default defineConfig(({ mode }) => {
  const root = path.dirname(fileURLToPath(import.meta.url));
  const env = loadEnv(mode, root, "");
  const target = env.API_TARGET || env.VITE_API_TARGET || "http://127.0.0.1:8765";
  const backendOrigin = new URL(target).origin;
  const apiProxy: ProxyOptions = {
    target,
    changeOrigin: true,
    configure(proxy) {
      proxy.on("proxyReq", (proxyReq, request) => {
        // changeOrigin rewrites Host, but leaves the browser's Origin intact.
        // Rewrite only a request from this frontend; foreign origins stay
        // unchanged so the backend can reject them.
        if (request.headers.origin === `http://${request.headers.host}`) {
          proxyReq.setHeader("Origin", backendOrigin);
        }
      });
    },
  };

  return {
    root,
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(root, "src"),
      },
    },
    build: {
      rollupOptions: {
        input: {
          landing: path.resolve(root, "index.html"),
          demo: path.resolve(root, "demo/index.html"),
          legacyDemo: path.resolve(root, "legacy-demo/index.html"),
        },
      },
    },
    server: {
      host: "127.0.0.1",
      port: 5173,
      strictPort: true,
      proxy: { "/api": apiProxy },
    },
    preview: {
      host: "127.0.0.1",
      port: 4173,
      strictPort: true,
      proxy: { "/api": apiProxy },
    },
  };
});
