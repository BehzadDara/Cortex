import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { viteStaticCopy } from "vite-plugin-static-copy";

const VAD_ASSETS = [
  "node_modules/@ricky0123/vad-web/dist/vad.worklet.bundle.min.js",
  "node_modules/@ricky0123/vad-web/dist/silero_vad_v5.onnx",
  "node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.mjs",
  "node_modules/onnxruntime-web/dist/ort-wasm-simd-threaded.wasm",
];

export default defineConfig({
  plugins: [
    react(),
    viteStaticCopy({
      targets: VAD_ASSETS.map((src) => ({
        src,
        dest: "vad",
        rename: { stripBase: true },
      })),
    }),
  ],
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
