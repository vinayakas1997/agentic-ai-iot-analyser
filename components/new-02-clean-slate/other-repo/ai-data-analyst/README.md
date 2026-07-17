# AI Data Analyst

A modern AI-powered data analysis platform that converts natural language into SQL queries, generates visual dashboards, and automates insights through scheduled reports.  
Built with agentic workflows, MCP tools, and a clean full-stack architecture.

## 🚀 Features

- Natural language → SQL generation
- Automated dashboards & charts
- Multi-agent reasoning system
- MCP Database Tool (safe SQL execution)
- MCP Email Tool (automated reports)
- Dataset ingestion & metadata extraction
- Scheduled insights (daily/weekly)
- Minimalistic, modern UI

## 🏗️ Tech Stack

**Frontend:** Next.js, TailwindCSS, ShadCN  
**Backend:** Node.js (NestJS), Prisma  
**AI:** OpenAI GPT-4.1 / o3  
**Database:** PostgreSQL + pgvector  
**Workers:** BullMQ  
**Tools:** MCP DB Tool, MCP Email Tool  
**Repo Layout:** Turborepo monorepo

## 📐 System Architecture

```mermaid
flowchart TD

    subgraph UI[Next.js Web App]
        A1[Chat Interface]
        A2[Dashboard Viewer]
        A3[Dataset Upload]
    end

    subgraph API[NestJS Backend]
        B1[Auth & Users]
        B2[Dataset Service]
        B3[SQL Generation]
        B4[Visualization Service]
        B5[Automation Scheduler]
    end

    subgraph WORKER[BullMQ Worker]
        W1[Scheduled Jobs]
        W2[Weekly Reports]
        W3[Anomaly Detection]
    end

    subgraph MCPDB[MCP DB Tool]
        M1[Schema Inspector]
        M2[Query Executor]
    end

    subgraph MCPEMAIL[MCP Email Tool]
        E1[Send Email]
        E2[Attach Reports]
    end

    subgraph DB[PostgreSQL]
        D1[(Tables + Vectors)]
    end


    A1 -->|Ask Question| API
    A2 --> API
    A3 -->|Upload| API

    API -->|Generate SQL| MCPDB
    API -->|Store results| DB
    
    WORKER --> API
    WORKER --> MCPEMAIL

    MCPDB --> DB
