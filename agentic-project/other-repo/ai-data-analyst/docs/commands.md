pnpm install

node ./scripts/snapshot-structure.js

pnpm --filter api dev
pnpm --filter web dev

pnpm add dotenv --filter api
pnpm remove dotenv --filter api


# Delete all node_modules folders (local)
pnpm recursive exec -- rm -rf node_modules
rm -rf node_modules
# Delete the pnpm lockfile
# This forces a fresh dependency resolution
rm pnpm-lock.yaml
# 3. Prune the pnpm store cache
# This deletes unreferenced/old packages from the global content store
pnpm store prune
# (Optional, if prune fails) Force a full clean
# This command forces a full cleanup of the store directory.
# This should be a last resort, as it deletes ALL stored packages, 
# but it guarantees removal of the conflicting package.
# Find the store path: pnpm store path
# Then manually delete the directory (e.g., C:\Users\rawal\AppData\Local\pnpm\store\v3)

Get-ExecutionPolicy
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

#prisma commands
pnpm --filter api prisma migrate dev
or
apps/api/ pnpm prisma migrate dev --name init
pnpm prisma db pull
