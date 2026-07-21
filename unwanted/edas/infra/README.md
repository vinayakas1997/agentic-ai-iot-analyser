# EDAS remote infrastructure

Deploy on **edgexpert** (`192.168.1.101`) — not on the dev machine.

## PostgreSQL

```bash
docker compose -f postgres-docker-compose.yml up -d
```

Apply schema once from a machine that can reach the DB:

```bash
psql "postgresql://edas:edas@192.168.1.101:9001/edas" -f ../backend/db/migrations/001_initial.sql
```

- Host port: **9001** → container **5432**
- Allow inbound TCP **9001** from dev machines on the LAN.

## Atlas LLM

```bash
docker compose -f llm_model.yml up -d
```

- Serves model **`atlas-35b`** on port **8009** (host network)
- Underlying weights: `Sehyo/Qwen3.5-35B-A3B-NVFP4`
- Set in `edas/backend/.env`: `VLLM_BASE_URL=http://192.168.1.101:8009/v1`, `MANAGER_MODEL=atlas-35b`, `RESEARCH_MODEL=atlas-35b`

Verify from dev machine:

```powershell
curl.exe http://192.168.1.101:8009/v1/models
```
