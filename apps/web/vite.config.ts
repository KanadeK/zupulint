import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    setupFiles: "./tests/setup.ts",
    css: true,
    globals: true,
    include: ["tests/**/*.test.{ts,tsx}"],
    exclude: ["tests/e2e/**"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/vite-env.d.ts", "src/types.ts"],
      reporter: ["text", "json-summary"],
      thresholds: { lines: 75, functions: 75, statements: 75, branches: 75 },
    },
  },
});
