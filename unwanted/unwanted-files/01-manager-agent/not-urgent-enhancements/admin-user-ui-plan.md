# Admin User UI Plan - Global Registry Management

**Date:** 2026-07-09
**Source:** Architecture discussion on IoT vs Normal user separation
**Status:** Not urgent - future implementation (after current implementation stage)

---

## Overview

The EDAS system has two distinct user types that need different experiences:

1. **IoT User** — Manages the `global_registry` table (the single source of truth for all production lines, datasets, and schemas)
2. **Normal User** — Uses the Manager Agent for analysis, research, and task execution

Currently, the system is hardcoded with a single `user_id = "98765"` and no authentication. The `global_registry` is managed only through offline seed scripts. This plan describes the future implementation of role-based access control (RBAC) and an Admin UI for IoT users.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                EDAS App                      │
├──────────────┬──────────────────────────────┤
│  IoT User    │  Normal User                 │
│  (role=iot)  │  (role=normal)               │
├──────────────┼──────────────────────────────┤
│  Admin Page  │  Dashboard Page              │
│  - CRUD      │  - Manager Agent chat        │
│  - global_   │  - Analysis tasks            │
│    registry  │  - Research / Executor       │
│  management  │  - Results viewing           │
├──────────────┴──────────────────────────────┤
│  Same backend, same global_registry table   │
│  Role check on write endpoints only         │
└─────────────────────────────────────────────┘
```

**Key design decisions:**
- **Same table, no replicas** — Both user types read from the same `global_registry`. IoT users get write access via role-gated API endpoints. No separate table duplication or sync issues.
- **Immediate edits, no draft/publish** — IoT user changes go live instantly. No staging workflow.
- **JWT with role claim** — User role (`"iot"` or `"normal"`) is embedded in the JWT token, so authorization checks don't require extra DB lookups per request.

---

## Database Schema Changes

### New Migration: `009_add_user_role.sql`

```sql
ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'normal';

-- Valid values: 'iot', 'normal'
-- 'iot'    = can read + write global_registry (admin UI)
-- 'normal' = can only read global_registry (manager agent flow)
```

### User Model Update

```python
# edas/backend/db/models.py — User class
role: Mapped[str] = mapped_column(Text, nullable=False, default="normal")
```

---

## Backend Changes

### 1. Auth Updates (`edas/backend/api/auth.py`)

| Change | Detail |
|--------|--------|
| `register_user()` | Accept `role` parameter, store on User row |
| `create_access_token()` | Include `role` in JWT payload: `{"sub": user_id, "role": role, "exp": expire}` |
| New: `get_current_user_role()` | Decode JWT, return role string |
| New: `require_iot_role()` | FastAPI dependency — raises 403 if role != `"iot"` |

### 2. Auth Route Update (`edas/backend/api/routes/auth.py`)

- `/auth/register` — Accept `role` in request body (default: `"normal"`)
- `/auth/login` — Return `role` in the `Token` response

```python
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = "normal"  # "iot" or "normal"

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str
```

### 3. New CRUD Route (`edas/backend/api/routes/registry.py`)

| Endpoint | Method | Access | Description |
|----------|--------|--------|-------------|
| `/registry` | GET | All users | List all global_registry rows |
| `/registry/{id}` | GET | All users | Get single registry row |
| `/registry` | POST | IoT only | Create new registry row |
| `/registry/{id}` | PUT | IoT only | Update existing registry row |
| `/registry/{id}` | DELETE | IoT only | Delete registry row |

All endpoints use `Depends(get_current_user)` for authentication.
Write endpoints (POST/PUT/DELETE) additionally use `Depends(require_iot_role)`.

### 4. Register Router (`edas/backend/api/server.py`)

```python
from api.routes import auth, registry

app.include_router(auth.router)
app.include_router(registry.router)
```

---

## Frontend Changes

### 1. Auth Store (`edas/frontend/src/stores/authStore.ts`)

New Zustand store managing authentication state:

```typescript
interface AuthState {
  token: string | null;
  userId: string | null;
  role: string | null;        // "iot" | "normal"
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, role: string) => Promise<void>;
  logout: () => void;
}
```

- Persists `token`, `userId`, `role` to `localStorage`
- `login()` calls `/auth/login`, stores result
- `register()` calls `/auth/register`, stores result
- `logout()` clears state and localStorage

### 2. API Client Update (`edas/frontend/src/api/client.ts`)

Attach JWT token to all requests:

```typescript
client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});
```

### 3. Login Page (`edas/frontend/src/pages/LoginPage.tsx`)

- Email + password form
- Calls `/auth/login`
- Stores token, userId, role in authStore
- Redirects to `/` on success
- Link to register page

### 4. Register Page (`edas/frontend/src/pages/RegisterPage.tsx`)

- Email + password + role selector (IoT / Normal radio buttons)
- Calls `/auth/register`
- Stores token, userId, role in authStore
- Redirects to `/` on success
- Link to login page

### 5. Admin Page (`edas/frontend/src/pages/AdminPage.tsx`)

Only visible when `role === "iot"`.

**Table View:**
- Displays all `global_registry` rows in a table
- Columns: line_name, dataset_name, source_type, status, verified, maintained_by, global_version
- Search/filter by line_name or dataset_name
- Click row to view/edit details

**Create/Edit Form:**
- Modal or side panel form for creating/editing registry rows
- Fields: line_name, dataset_name, synonyms, description, source_type, source_config, column_definitions, role, join_hints, suggested_aims, verified, status
- JSON editor for JSONB fields (synonyms, source_config, column_definitions, join_hints, suggested_aims)
- Validation before submit

**Delete:**
- Confirmation dialog before deletion
- Calls `DELETE /registry/{id}`

**Data Flow:**
```
AdminPage → GET /registry → display table
AdminPage → POST /registry → create row → refresh table
AdminPage → PUT /registry/{id} → update row → refresh table
AdminPage → DELETE /registry/{id} → delete row → refresh table
```

### 6. Route Guard (`edas/frontend/src/components/ProtectedRoute.tsx`)

```typescript
interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;  // e.g., "iot"
}

// If no token → redirect to /login
// If requiredRole specified and user role doesn't match → redirect to /
// Otherwise render children
```

### 7. App.tsx Updates

```tsx
// New routes
<Route path="/login" element={<LoginPage />} />
<Route path="/register" element={<RegisterPage />} />
<Route path="/admin" element={
  <ProtectedRoute requiredRole="iot">
    <AdminPage />
  </ProtectedRoute>
} />

// Navbar: show "Admin" link only when role === "iot"
```

---

## Files Summary

| File | Action | Purpose |
|------|--------|---------|
| `edas/backend/db/migrations/009_add_user_role.sql` | **New** | Add `role` column to users table |
| `edas/backend/db/models.py` | Edit | Add `role` field to User model |
| `edas/backend/api/auth.py` | Edit | Role in token, role helper functions |
| `edas/backend/api/routes/auth.py` | Edit | Accept role in register, return role in token |
| `edas/backend/api/routes/registry.py` | **New** | CRUD endpoints for global_registry |
| `edas/backend/api/server.py` | Edit | Register auth + registry routers |
| `edas/frontend/src/stores/authStore.ts` | **New** | Auth state management |
| `edas/frontend/src/api/client.ts` | Edit | Attach JWT token to requests |
| `edas/frontend/src/pages/LoginPage.tsx` | **New** | Login form |
| `edas/frontend/src/pages/RegisterPage.tsx` | **New** | Registration form with role selector |
| `edas/frontend/src/pages/AdminPage.tsx` | **New** | Global registry CRUD management |
| `edas/frontend/src/components/ProtectedRoute.tsx` | **New** | Route guard for role-based access |
| `edas/frontend/src/App.tsx` | Edit | Add routes + conditional nav links |

**Total: 7 new files, 6 edits**

---

## Implementation Phases

### Phase 1: Backend Auth + RBAC
1. Create migration `009_add_user_role.sql`
2. Update User model with `role` field
3. Update `auth.py` — role in token, role helpers
4. Update `routes/auth.py` — accept role in register
5. Create `routes/registry.py` — CRUD endpoints with role checks
6. Register new routers in `server.py`
7. Test: register IoT user, register normal user, verify 403 on write for normal user

### Phase 2: Frontend Auth
1. Create `authStore.ts`
2. Update `client.ts` with JWT interceptor
3. Create `LoginPage.tsx`
4. Create `RegisterPage.tsx`
5. Create `ProtectedRoute.tsx`
6. Update `App.tsx` with routes
7. Test: login, register, token persistence, logout

### Phase 3: Admin UI
1. Create `AdminPage.tsx` with table view
2. Add create/edit form (modal or side panel)
3. Add delete with confirmation
4. Add search/filter
5. Add JSON editor for JSONB fields
6. Test: full CRUD flow, validation, error handling

---

## Testing Checklist

### Backend
- [ ] Migration runs without errors
- [ ] User registration stores role correctly
- [ ] JWT token contains role claim
- [ ] `/auth/login` returns role in response
- [ ] `/registry` GET works for all authenticated users
- [ ] `/registry` POST returns 403 for normal users
- [ ] `/registry` POST works for IoT users
- [ ] `/registry/{id}` PUT returns 403 for normal users
- [ ] `/registry/{id}` PUT works for IoT users
- [ ] `/registry/{id}` DELETE returns 403 for normal users
- [ ] `/registry/{id}` DELETE works for IoT users
- [ ] Unauthenticated requests return 401

### Frontend
- [ ] Login page renders and submits correctly
- [ ] Register page renders with role selector
- [ ] Token + role stored in localStorage
- [ ] API client attaches Authorization header
- [ ] ProtectedRoute redirects to /login when no token
- [ ] ProtectedRoute redirects to / when wrong role
- [ ] Admin page visible only for IoT users
- [ ] Admin page hidden for normal users
- [ ] Navbar shows "Admin" link only for IoT users
- [ ] Logout clears state and redirects

### Admin CRUD
- [ ] Table loads all registry rows
- [ ] Search/filter works
- [ ] Create form opens, validates, submits
- [ ] Edit form pre-fills, validates, submits
- [ ] Delete confirmation works
- [ ] JSON fields editable with JSON editor
- [ ] Error messages displayed on validation failure
- [ ] Table refreshes after create/edit/delete

---

## Expected Impact

After implementing this plan:

1. **Clear role separation** — IoT users manage data, normal users consume it
2. **Secure by default** — Write operations require IoT role, enforced at API level
3. **No data duplication** — Single `global_registry` table, no sync issues
4. **Scalable** — Adding new roles (e.g., "admin", "viewer") is straightforward
5. **User-friendly Admin UI** — IoT users can manage registry without seed scripts or DB access
6. **JWT-based** — Stateless auth, no session DB lookups for authorization

---

**Status:** Planned — ready for implementation when current stage is complete
**Priority:** Not urgent (future enhancement)
**Estimated effort:** 1-2 days (backend auth + RBAC + admin UI + testing)
