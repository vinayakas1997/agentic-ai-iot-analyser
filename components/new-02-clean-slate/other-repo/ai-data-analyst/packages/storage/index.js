const fs = require("fs");
const path = require("path");

const STORAGE_ROOT = process.env.STORAGE_ROOT || path.resolve(process.cwd(), "data");

function ensureDir(dir) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function saveText(relativePath, content) {
  const fullPath = path.resolve(STORAGE_ROOT, relativePath);
  ensureDir(path.dirname(fullPath));
  fs.writeFileSync(fullPath, content, "utf8");
  return fullPath;
}

function saveJSON(relativePath, data) {
  const fullPath = path.resolve(STORAGE_ROOT, relativePath);
  ensureDir(path.dirname(fullPath));
  fs.writeFileSync(fullPath, JSON.stringify(data, null, 2), "utf8");
  return fullPath;
}

function readText(relativePath) {
  const fullPath = path.resolve(STORAGE_ROOT, relativePath);
  return fs.readFileSync(fullPath, "utf8");
}

function readJSON(relativePath) {
  const fullPath = path.resolve(STORAGE_ROOT, relativePath);
  return JSON.parse(fs.readFileSync(fullPath, "utf8"));
}

function getStorageRoot() {
  ensureDir(STORAGE_ROOT);
  return STORAGE_ROOT;
}

module.exports = {
  saveText,
  saveJSON,
  readText,
  readJSON,
  getStorageRoot,
};