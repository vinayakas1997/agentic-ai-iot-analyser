# Project Scripts

This document describes useful scripts available in the repository.

## Snapshot Monorepo Structure

Generate a snapshot of the repository's folder/file tree and save it to both the docs and a storage location.

- Script: `node scripts/snapshot-structure.js`
- Location: <mcfile name="snapshot-structure.js" path="c:\Users\rawal\OneDrive\Documents\GitHub\ai-data-analyst\scripts\snapshot-structure.js"></mcfile>
- Outputs:
  - Markdown in docs: <mcfile name="monorepo-structure.md" path="c:\Users\rawal\OneDrive\Documents\GitHub\ai-data-analyst\docs\monorepo-structure.md"></mcfile>
  - Text snapshot in storage: `STORAGE_ROOT/monorepo/structure.txt`
- Storage helper: <mcfile name="index.js" path="c:\Users\rawal\OneDrive\Documents\GitHub\ai-data-analyst\packages\storage\index.js"></mcfile>

### Why a storage root?
By default, the storage helper uses a `data/` folder at the repository root (`process.cwd()`), so locally generated artifacts are easy to find and can be selectively gitignored. Override with the `STORAGE_ROOT` environment variable if you prefer a different location.

### Usage

1. Ensure your environment file is set:
   - Copy `.env.example` to `.env`.
   - Optionally set `STORAGE_ROOT` (defaults to `./data`).
2. Run the script from the repository root:
   ```bash
   node scripts/snapshot-structure.js
   ```
3. Check outputs:
   - `docs/monorepo-structure.md` (formatted tree for documentation)
   - `${STORAGE_ROOT}/monorepo/structure.txt` (plain text tree)

### Behavior
- Depth: 3 levels (to keep docs readable)
- Entry cap: 200 entries (prevents overly long docs)
- Excludes: `node_modules`, `.git`, `.turbo`, `dist`, `build`, `coverage`, `data`
- Sorting: Directories first, then files, all alphabetically

### Tips
- Consider adding `data/` to `.gitignore` to avoid committing local snapshots.
- Re-run the script whenever the folder structure changes to update docs.