# Monorepo Folder Structure

Updated: 2025-11-26T17:23:53.304Z

```text
// Directory tree (3 levels, limited to 200 entries)
├── apps/
│     ├── api/
│     │       ├── prisma/
│     │       │         ├── migrations/
│     │       │         └── schema.prisma
│     │       ├── src/
│     │       │         ├── db/
│     │       │         ├── modules/
│     │       │         ├── app.controller.spec.ts
│     │       │         ├── app.controller.ts
│     │       │         ├── app.module.ts
│     │       │         ├── app.service.ts
│     │       │         └── main.ts
│     │       ├── .gitignore
│     │       ├── .prettierrc
│     │       ├── eslint.config.mjs
│     │       ├── nest-cli.json
│     │       ├── package.json
│     │       ├── pnpm-lock.yaml
│     │       ├── prisma.config.ts
│     │       ├── README.md
│     │       ├── tsconfig.build.json
│     │       └── tsconfig.json
│     ├── mcp-db/
│     │       └── README.md
│     ├── mcp-email/
│     │       └── README.md
│     ├── web/
│     │       ├── public/
│     │       │         ├── file.svg
│     │       │         ├── globe.svg
│     │       │         ├── next.svg
│     │       │         ├── vercel.svg
│     │       │         └── window.svg
│     │       ├── src/
│     │       │         └── app/
│     │       ├── .gitignore
│     │       ├── eslint.config.mjs
│     │       ├── next.config.ts
│     │       ├── package.json
│     │       ├── pnpm-lock.yaml
│     │       ├── postcss.config.mjs
│     │       ├── README.md
│     │       └── tsconfig.json
│     └── worker/
│     │       └── README.md
├── docs/
│     ├── architecture.md
│     ├── commands.md
│     ├── mcp-tools.md
│     ├── monorepo-structure.md
│     ├── roadmap.md
│     ├── scripts.md
│     └── setup.md
├── packages/
│     ├── shared-types/
│     │       ├── index.ts
│     │       └── README.md
│     └── storage/
│     │       ├── index.js
│     │       └── README.md
├── scripts/
│     └── snapshot-structure.js
├── .env.example
├── .gitattributes
├── .gitignore
├── LICENSE
├── package.json
├── pnpm-lock.yaml
├── pnpm-workspace.yaml
├── README.md
├── turbo.json
```