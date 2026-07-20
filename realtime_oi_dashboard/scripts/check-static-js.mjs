import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const roots = [join(packageRoot, "static/js")];
const files = roots.flatMap(collectJavaScriptFiles);
const importsByFile = new Map();

for (const file of files) {
  const result = spawnSync(process.execPath, ["--check", file], { stdio: "inherit" });
  if (result.status !== 0) process.exit(result.status || 1);
  importsByFile.set(file, checkRelativeImports(file));
}

const htmlPath = join(packageRoot, "index.html");
const entryPath = join(packageRoot, "static/js/dashboard.js");
checkIndexEntry(htmlPath, '<script type="module" src="/static/js/dashboard.js"></script>');
checkReachableModules(entryPath, files, importsByFile);
checkDomIds(htmlPath, entryPath);
console.log(`Checked ${files.length} reachable dashboard JavaScript files.`);

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
  const targets = [];
  let match;

  while ((match = importPattern.exec(source))) {
    const target = resolve(dirname(file), match[1]);
    if (!existsSync(target)) {
      throw new Error(`Missing import target in ${file}: ${match[1]}`);
    }
    targets.push(target);
  }
  return targets;
}

function checkIndexEntry(htmlPath, expectedEntry) {
  const html = readFileSync(htmlPath, "utf8");
  if (!html.includes(expectedEntry)) {
    throw new Error(`${htmlPath} must load ${expectedEntry}`);
  }
}

function checkReachableModules(entryPath, files, importsByFile) {
  const knownFiles = new Set(files);
  const reachable = new Set();
  const pending = [entryPath];

  while (pending.length) {
    const file = pending.pop();
    if (reachable.has(file)) continue;
    if (!knownFiles.has(file)) throw new Error(`Missing dashboard entry: ${file}`);

    reachable.add(file);
    for (const target of importsByFile.get(file) || []) {
      if (knownFiles.has(target)) pending.push(target);
    }
  }

  const unused = files.filter(file => !reachable.has(file));
  if (unused.length) {
    throw new Error(
      `Unreachable dashboard modules: ${unused.map(file => relative(packageRoot, file)).join(", ")}`,
    );
  }
}

function checkDomIds(htmlPath, entryPath) {
  const html = readFileSync(htmlPath, "utf8");
  const source = readFileSync(entryPath, "utf8");
  const htmlIds = [...html.matchAll(/\bid=["']([^"']+)["']/g)].map(match => match[1]);
  const duplicateIds = htmlIds.filter((id, index) => htmlIds.indexOf(id) !== index);
  if (duplicateIds.length) {
    throw new Error(`Duplicate HTML ids: ${[...new Set(duplicateIds)].join(", ")}`);
  }

  const knownIds = new Set(htmlIds);
  const requiredIds = [
    ...source.matchAll(/getElementById\(["']([^"']+)["']\)/g),
  ].map(match => match[1]);
  const missingIds = requiredIds.filter(id => !knownIds.has(id));
  if (missingIds.length) {
    throw new Error(`Missing dashboard HTML ids: ${missingIds.join(", ")}`);
  }
}
