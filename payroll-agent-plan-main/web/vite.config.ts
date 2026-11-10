import path from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        main: path.resolve(rootDir, "index.html"),
        // MSAL Browser v5 redirect bridge (must not load the React app)
        redirect: path.resolve(rootDir, "redirect.html"),
      },
    },
  },
  server: {
    proxy: {
      // Avoid browser CORS when calling local ResponsesHostServer
      "/api/foundry": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/foundry/, "/responses"),
      },
      "/api/qa": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/qa/, "/qa"),
      },
      "/api/queue": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/queue/, "/queue"),
      },
      "/api/history": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/history/, "/history"),
      },
      "/api/settings": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/settings/, "/settings"),
      },
      "/api/drafts": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/drafts/, "/drafts"),
      },
      "/api/changelists": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/changelists/, "/changelists"),
      },
      "/api/triage": {
        target: "http://127.0.0.1:8088",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/triage/, "/triage"),
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    passWithNoTests: true,
  },
});
