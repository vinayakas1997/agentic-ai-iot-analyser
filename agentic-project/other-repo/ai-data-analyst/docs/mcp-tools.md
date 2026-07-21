# MCP Tools Specification

This document describes the Model Context Protocol (MCP) tools used by the AI Data Analyst platform.

The project includes two tool servers:

1. **MCP Database Tool**
2. **MCP Email Tool**

Each tool exposes safe, structured capabilities that can be accessed by the agent through the backend orchestrator.

---

# 1. MCP Database Tool

## Purpose
The Database MCP Tool allows the agent to:

- Inspect database schema
- Validate SQL before execution
- Run safe, read-only SQL queries
- Return structured rows/columns metadata

The agent **never receives raw DB credentials** — all requests flow through this MCP tool.

---

## Capabilities

### **getSchema**
Returns:

- Tables  
- Columns  
- Data types  
- Column nullability  
- Optional row counts  

Used by the agent to generate SQL with schema context.

---

### **executeQuery**
**Parameters:**

- `sql: string`  
- `limit?: number` (default: 200)  
- `params?: object`  

**Returns:**

- `columns: string[]`  
- `rows: Array<Record<string, any>>`  
- `rowCount: number`  

---

## Security Rules

To protect the database:

- Only **SELECT** queries allowed  
- Forbidden keywords (blocked automatically):
  - `DROP`
  - `DELETE`
  - `UPDATE`
  - `INSERT`
  - `ALTER`
  - `TRUNCATE`
- Row limit enforced
- No transactions
- No multiple statements

---

## Implementation Notes

- Implement as a Node.js service
- Runs independently inside `apps/mcp-db/`
- Uses a Prisma + Postgres connection pool
- MCP server framework suggestions:
  - `mcp-js`
  - `@modelcontextprotocol/sdk` (official)

---

# 2. MCP Email Tool

## Purpose
Used for automated reporting and scheduled insights.

Workers send structured requests to this MCP tool instead of managing SMTP directly.

---

## Capabilities

### **sendEmail**
**Parameters:**

- `to: string`
- `subject: string`
- `html?: string`
- `text?: string`
- `attachments?: Array<{
    filename: string,
    content: string (base64 or buffer),
    type: string
  }>`  

**Supports:**

- Inline images  
- Chart attachments  
- PDF report attachments  
- Text-only fallback  

---

## Implementation Notes

Backend options:

- Resend (recommended for MVP)
- SendGrid
- AWS SES
- SMTP (Nodemailer)

Keep credentials outside the agent — only MCP has them.

---

# 3. Directory Structure

Each MCP tool runs as its own small Node.js service inside the monorepo.

```text
apps/
  mcp-db/        # Database MCP tool server
  mcp-email/     # Email MCP tool server
```

## MCP DB Tool — Interaction Summary

- Agent → MCP DB Tool → PostgreSQL  
- Validates schema, executes safe SQL, returns JSON results

## MCP Email Tool — Interaction Summary

- Worker → MCP Email Tool → Email Provider  
- Sends automated summaries and attachments


