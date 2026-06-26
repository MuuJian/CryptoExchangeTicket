import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const roots = [join(packageRoot, "static/js")];
const files = roots.flatMap(collectJavaScriptFiles);

for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status || 1);
  checkRelativeImports(file);
}

checkIndexEntry();
console.log(`Checked ${files.length} realtime dashboard static JS files.`);

function collectJavaScriptFiles(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap(entry => {
    const path = join(root, entry.name);
    if (entry.isDirectory()) return collectJavaScriptFiles(path);
    return entry.isFile() && path.endsWith(".js") ? [path] : [];
  });
}

function checkRelativeImports(file) {
  const source = readFileSync(file, "utf8");
  const importPattern = /import\s+(?:[^"']+\s+from\s+)?["'](\.[^"']+)["']/g;
  let match;

  while ((match = importPattern.exec(source))) {
    const target = resolve(dirname(file), match[1]);
    if (!existsSync(target)) {
      throw new Error(`Missing import target in ${file}: ${match[1]}`);
    }
  }
}

function checkIndexEntry() {
  const html = readFileSync(join(packageRoot, "index.html"), "utf8");
  if (!html.includes('<script type="module" src="/static/js/dashboard.js"></script>')) {
    throw new Error("realtime dashboard must load /static/js/dashboard.js as a module");
  }
}
