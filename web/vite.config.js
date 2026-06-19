import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Relative base so the build works under any path (GitHub Pages project site,
// Cloudflare Pages root, local preview) without reconfiguration.
export default defineConfig({
  base: "./",
  plugins: [react()],
  build: { outDir: "dist", chunkSizeWarningLimit: 4000 },
});
