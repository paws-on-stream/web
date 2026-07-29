import esbuild from "esbuild";
import * as sass from "sass";
import fs from "fs-extra";
import path from "path";

const ROOT = process.cwd();

const SRC_SCSS = path.join(ROOT, "frontend_src/scss/app.scss");
const SRC_JS = path.join(ROOT, "frontend_src/js/main.js");

const OUT_CSS = path.join(ROOT, "paws_on_stream_web/static/css/app.css");
const OUT_JS = path.join(ROOT, "paws_on_stream_web/static/js/app.js");

// ensure dirs
fs.ensureDirSync(path.dirname(OUT_CSS));
fs.ensureDirSync(path.dirname(OUT_JS));

console.log("🔨 Building SCSS...");

const result = sass.compile(SRC_SCSS, {
  style: "compressed",
  loadPaths: ["node_modules"],
  quietDeps: true,
  sourceMap: true
});

fs.writeFileSync(OUT_CSS, result.css);
fs.writeFileSync(OUT_CSS + ".map", JSON.stringify(result.sourceMap));

console.log("⚡ Bundling JS...");

await esbuild.build({
  entryPoints: [SRC_JS],
  bundle: true,
  minify: true,
  outfile: OUT_JS,
  format: "iife",
  sourcemap: true
});

const ICONS_SRC = path.join(
  ROOT,
  "node_modules/bootstrap-icons/font/fonts"
);

const ICONS_DEST = path.join(
  ROOT,
  "paws_on_stream_web/static/fonts/bootstrap-icons"
);

console.log("📦 Copying Bootstrap Icons fonts...");

fs.copySync(ICONS_SRC, ICONS_DEST);

const CODEMIRROR_SRC = path.join(ROOT, "node_modules/codemirror");
const CODEMIRROR_DEST = path.join(
  ROOT,
  "paws_on_stream_web/static/vendor/codemirror"
);

console.log("📦 Copying CodeMirror editor assets...");
fs.copySync(path.join(CODEMIRROR_SRC, "lib"), path.join(CODEMIRROR_DEST, "lib"));
fs.copySync(path.join(CODEMIRROR_SRC, "mode/javascript"), path.join(CODEMIRROR_DEST, "mode/javascript"));

console.log("✅ Build complete");
