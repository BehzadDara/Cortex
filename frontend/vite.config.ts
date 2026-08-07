import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5100,
    proxy: {
      "/api": {
        target: "http://localhost:8100",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
