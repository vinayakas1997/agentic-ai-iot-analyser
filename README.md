# Data Analysis Project

Event-driven analysis system (**EDAS**) plus shared docs and Cursor agent config.

## EDAS quick start

```bash
cd edas
cp backend/.env.example backend/.env
docker compose up --build
```

- Dashboard: http://localhost:7008
- API: http://localhost:7009/health

See [edas/README.md](edas/README.md), [edas/backend/README.md](edas/backend/README.md), [edas/frontend/README.md](edas/frontend/README.md), and [docs/configuration.md](docs/configuration.md).

## Project structure

```
data_analysis_project/
├── edas/
│   ├── backend/           # Python API, agents, bus, db (port 7009)
│   └── frontend/          # React dashboard (port 7008)
├── data/                  # Local CSV datasets (gitignored)
├── docs/                  # Living project documentation
└── project_related_docs/  # Design references (DATABASE_DEFINITION, etc.)
```

## Documentation

| Doc | Description |
|-----|-------------|
| [File structure](docs/file-structure.md) | Repo layout and module summaries |
| [Development plan](docs/development-plan.md) | Phases and plan decisions |
| [Architecture](docs/architecture.md) | Deployment and modules |
| [Architecture diagrams](docs/architecture-diagrams.md) | Mermaid flows |
| [Implementation status](docs/implementation-status.md) | Done vs planned |
| [Configuration](docs/configuration.md) | Env vars |
| [Manager CLI](docs/usage/manager.md) | `python -m agents.manager` |
| [Changelog](docs/changelog.md) | Notable changes |

Say **project management** and pick an action, or type **init** / **update** directly (personal **project-management** skill: `~/.cursor/skills/project-management/`).
