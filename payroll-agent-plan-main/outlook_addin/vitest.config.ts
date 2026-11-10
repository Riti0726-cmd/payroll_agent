import { defineConfig } from "vitest/config";

export default defineConfig({
  define: {
    __ADDIN_ENV__: JSON.stringify({
      VITE_AUTH_DISABLED: "true",
      VITE_API_BASE_URL: "/api",
      VITE_DEV_SPECIALIST_ID: "specialist@example.com",
    }),
  },
  esbuild: { jsx: "transform", jsxFactory: "React.createElement", jsxFragment: "React.Fragment" },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
