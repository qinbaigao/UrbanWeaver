import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  base: "/",
  build: {
    outDir: resolve(import.meta.dirname, "../src/cityg/viewer_static"),
    emptyOutDir: true,
    sourcemap: false,
  },
});
