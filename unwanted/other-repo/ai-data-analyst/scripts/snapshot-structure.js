// Snapshot the monorepo folder/file structure and save to docs and storage
// Usage: node scripts/snapshot-structure.js

const fs = require("fs");
const path = require("path");
const storage = require("../packages/storage/index.js");

const EXCLUDES = new Set(["node_modules", ".git", ".turbo", "dist", "build", "coverage", "data"]);
const MAX_ENTRIES = 200; // cap to keep docs readable

function listDirTree(dir, depth = 0, maxDepth = 3, counters) {
  if (depth > maxDepth) return [];
  let entries = [];
  const dirents = fs.readdirSync(dir, { withFileTypes: true });
  // Filter excludes
  const filtered = dirents.filter((d) => !EXCLUDES.has(d.name));
  // Sort: dirs first, then files, alphabetically
  filtered.sort((a, b) => (a.isDirectory() === b.isDirectory() ? a.name.localeCompare(b.name) : a.isDirectory() ? -1 : 1));

  for (let i = 0; i < filtered.length; i++) {
    const d = filtered[i];
    const isLast = i === filtered.length - 1;
    const prefix = "" + "  ".repeat(depth) + (depth === 0 ? "" : "");
    const branch = depth === 0 ? "├──" : isLast ? "└──" : "├──";
    const displayName = d.isDirectory() ? `${d.name}/` : d.name;
    entries.push(`${prefix}${branch} ${displayName}`);
    counters.count++;
    if (counters.count >= MAX_ENTRIES) {
      entries.push("(limited to 200 entries)");
      return entries;
    }
    if (d.isDirectory()) {
      const childPath = path.join(dir, d.name);
      const childEntries = listDirTree(childPath, depth + 1, maxDepth, counters);
      // Indent children with vertical guide
      const indentedChildren = childEntries.map((line) => `${"  ".repeat(depth)}│   ${line}`);
      entries.push(...indentedChildren);
      if (counters.count >= MAX_ENTRIES) return entries;
    }
  }
  return entries;
}

function generateTree(rootDir) {
  const counters = { count: 0 };
  const lines = ["// Directory tree (3 levels, limited to 200 entries)"]; // header comment line
  const rootEntries = listDirTree(rootDir, 0, 3, counters);
  lines.push(...rootEntries);
  return lines.join("\n");
}

function main() {
  const repoRoot = path.resolve(__dirname, "..");
  const treeText = generateTree(repoRoot);

  // Save to docs
  const docsPath = path.join(repoRoot, "docs", "monorepo-structure.md");
  fs.mkdirSync(path.dirname(docsPath), { recursive: true });
  const md = `# Monorepo Folder Structure\n\nUpdated: ${new Date().toISOString()}\n\n\`\`\`text\n${treeText}\n\`\`\``;
  fs.writeFileSync(docsPath, md, "utf8");

  console.log("Saved:");
  console.log("- ", path.relative(repoRoot, docsPath));

}

main();