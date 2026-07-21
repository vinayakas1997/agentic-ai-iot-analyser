# Setup Guide

This document explains how to install, configure, and run the AI Data Analyst monorepo on your local machine.

---

# 1. Prerequisites

Make sure the following are installed:

- Node.js (v18+)
- pnpm (recommended) or npm/yarn
- PostgreSQL (v14+)
- Git
- OpenAI API key
- Redis (for BullMQ worker)

Optional (recommended):

- Docker Desktop
- Prisma Studio (`pnpm dlx prisma studio`)

---

# 2. Install Dependencies

Clone the repo:

```bash
git clone https://github.com/mihirrawal1399/ai-data-analyst.git
cd ai-data-analyst
```

Install dependencies:

```bash
pnpm install
```

Turborepo will automatically install packages inside all apps.

---

# 3. Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Open the `.env` file and fill in the required fields:

- PostgreSQL connection
- Redis URL
- OpenAI API key
- Email provider keys
- Service ports

A full reference is provided inside `.env.example`.

---

# 4. Database Setup

Run Prisma migrations:

```bash
pnpm --filter api prisma migrate dev
```

Generate Prisma client:

```bash
pnpm --filter api prisma generate
```

(Optional) Open Prisma Studio:

```bash
pnpm --filter api studio
```

---

# 5. Running the Project

Start all apps together:

```bash
pnpm dev
```

This runs:

- `apps/web` — Next.js frontend
- `apps/api` — NestJS backend
- `apps/mcp-db` — MCP DB tool server
- `apps/mcp-email` — MCP Email tool server
- `apps/worker` — BullMQ worker

---

# 6. Running Individual Apps

### Web (Next.js)

```bash
pnpm --filter web dev
```

### API (NestJS)

```bash
pnpm --filter api de
