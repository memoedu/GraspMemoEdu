// SPDX-License-Identifier: AGPL-3.0-or-later
import {defineConfig} from "vite";
import solid from "vite-plugin-solid";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = fileURLToPath(new URL(".", import.meta.url));
export default defineConfig({
  root, base: "./", publicDir: false, plugins: [solid()],
  resolve: {alias: [{find: /^pdfjs-dist$/, replacement: path.resolve(root, "../node_modules/pdfjs-dist/legacy/build/pdf.mjs")}]},
  define: {__BUILD_TIME__: JSON.stringify("2026-11-24"), __GIT_COMMIT__: JSON.stringify("7469b642"), __TINE_COMMUNITY_REGISTRY__: "false"},
  build: {target: "esnext", outDir: process.env.GRASPMEMOEDU_TINE_OUT, emptyOutDir: false},
});
