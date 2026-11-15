import { copyFileSync, createReadStream, mkdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const require = createRequire(import.meta.url);
const projectRoot = dirname(fileURLToPath(import.meta.url));
const ocrFiles = {
  "worker.min.js": require.resolve("tesseract.js/dist/worker.min.js"),
  "tesseract-core-simd-lstm.wasm.js": require.resolve("tesseract.js-core/tesseract-core-simd-lstm.wasm.js"),
  "tesseract-core-simd-lstm.wasm": require.resolve("tesseract.js-core/tesseract-core-simd-lstm.wasm"),
  "chi_sim.traineddata.gz": require.resolve("@tesseract.js-data/chi_sim/4.0.0_best_int/chi_sim.traineddata.gz"),
};

function localOcrAssets(): Plugin {
  return {
    name: "copy-local-ocr-assets",
    configureServer(server) {
      server.middlewares.use("/ocr", (request, response, next) => {
        const name = decodeURIComponent(request.url?.split("?")[0] ?? "").replace(/^\/+/, "");
        const source = ocrFiles[name as keyof typeof ocrFiles];
        if (!source) {
          next();
          return;
        }
        response.setHeader("Content-Type", name.endsWith(".wasm") ? "application/wasm" : name.endsWith(".gz") ? "application/gzip" : "text/javascript");
        response.setHeader("Content-Length", statSync(source).size);
        createReadStream(source).on("error", next).pipe(response);
      });
    },
    writeBundle(outputOptions) {
      const outputDirectory = resolve(outputOptions.dir ?? resolve(projectRoot, "dist"), "ocr");
      mkdirSync(outputDirectory, { recursive: true });
      for (const [name, source] of Object.entries(ocrFiles)) copyFileSync(source, resolve(outputDirectory, name));
    },
  };
}

export default defineConfig({
  plugins: [react(), localOcrAssets()],
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
