# Project Roadmap

This roadmap is designed for a **2–3 week MVP**, showcasing full AI + MCP + automation features.

---

# Foundation

## 1–2: Monorepo + Project Setup
- Initialize Turborepo  
- Create `apps/web` (Next.js)  
- Create `apps/api` (NestJS)  
- Create `apps/mcp-db` and `apps/mcp-email`  
- Setup shared types package  

## 3: Database Setup
- PostgreSQL setup  
- Prisma schema  
- Tables:
  - users  
  - datasets  
  - dataset_tables  
  - dashboards  
  - automations  
  - query_logs  

## 4: Dataset Upload Pipeline
- CSV upload to API  
- Parsing + validation  
- Store rows to Postgres  
- Extract metadata  

## 5: SQL Generation Pipeline (Agent)
- Build agent orchestration  
- Prompt design for SQL generation  
- Connect MCP DB Tool  
- Test sample queries  

---

# Dashboards + Automation

## 6–7: Chart Builder
- API for chart generation  
- UI components  
- Use ECharts or Recharts  

## 8: Dashboard Save/Load
- Persist queries + charts  
- Dashboard viewer UI  

## 9: Automation Worker
- BullMQ setup  
- Cron jobs  
- Connect email tool  
- Weekly summary email  

## 10: Anomaly Detection (Optional)
- Agent that analyses trends  
- Notifies user when anomalies appear  

---

# Polish + Documentation

## 11–12: UI Polish
- Sidebar  
- Dataset pages  
- Insight cards  

## 13: Authentication
- JWT or Clerk/Auth.js  

## 14: Final Documentation
- README polish  
- Architecture diagram  
- MCP tool docs  
- Deployment instructions  

---

# Stretch Goals (Future)
- Support external DB connectors  
- Multi-user organizations  
- Notebook mode  
- PDF report export  
- Real-time dashboards  
