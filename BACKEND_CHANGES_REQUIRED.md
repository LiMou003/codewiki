# Backend Changes Required for Full Authentication Support

## Overview

The current frontend redesign introduces a complete user authentication layer with login, registration, and user center pages. However, the current implementation uses **localStorage-only simulation** — no actual backend authentication is performed. The following changes are required in the Python FastAPI backend (`api/`) to fully support the new frontend features.

---

## 1. User Account System

### 1.1 Database

Add a user database (or use an existing persistent store). Recommended options:
- **SQLite** (simple, file-based, good for single-node deployments): add `sqlalchemy` + `aiosqlite`
- **PostgreSQL** (production-grade): add `asyncpg` + `sqlalchemy[asyncio]`

#### Users Table Schema
```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    VARCHAR(64) UNIQUE NOT NULL,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 1.2 Password Hashing

Install `passlib[bcrypt]` or `argon2-cffi`:
```toml
# pyproject.toml
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
```

---

## 2. New API Endpoints

### 2.1 User Registration

**POST `/auth/register`**

```python
class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict  # {id, username, email}

@app.post("/auth/register", response_model=AuthResponse)
async def register(body: RegisterRequest):
    # 1. Check username/email uniqueness
    # 2. Hash password
    # 3. Insert user into DB
    # 4. Return JWT access token
```

### 2.2 User Login

**POST `/auth/login`**

```python
class LoginRequest(BaseModel):
    username: str   # or email
    password: str

@app.post("/auth/login", response_model=AuthResponse)
async def login(body: LoginRequest):
    # 1. Lookup user by username or email
    # 2. Verify password hash
    # 3. Return JWT access token
```

### 2.3 Get Current User (Token Validation)

**GET `/auth/me`**

```python
@app.get("/auth/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    # 1. Decode JWT
    # 2. Return user info: {id, username, email, created_at}
```

### 2.4 Logout / Token Invalidation (Optional)

If using stateful tokens (e.g., with a token blocklist):

**POST `/auth/logout`**

```python
@app.post("/auth/logout")
async def logout(token: str = Depends(oauth2_scheme)):
    # Add token to blocklist (Redis or in-memory set)
```

### 2.5 Password Change

**PUT `/auth/password`**

```python
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

@app.put("/auth/password")
async def change_password(body: PasswordChangeRequest, user=Depends(get_current_user)):
    # 1. Verify current password
    # 2. Hash new password
    # 3. Update DB
```

---

## 3. JWT Authentication

Install `python-jose`:
```toml
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
```

### JWT Configuration
```python
# config.py additions
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
```

### Token Generation
```python
from jose import JWTError, jwt
from datetime import datetime, timedelta

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
```

### Token Dependency
```python
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await get_user_from_db(username)
    return user
```

---

## 4. Protect Existing Endpoints (Optional)

Once users are established, you may want to associate wiki generations with users. Add the `get_current_user` dependency to relevant endpoints:

```python
# Example: Associate wiki generation with a user
@app.post("/api/wiki_cache")
async def store_wiki_cache(body: WikiCacheBody, user=Depends(get_current_user_optional)):
    if user:
        body.user_id = user.id
    # ... rest of handler
```

Use `get_current_user_optional` (non-raising version) to maintain backwards compatibility with unauthenticated usage.

---

## 5. User Projects History

Add a user projects table to store per-user generated wikis:

```sql
CREATE TABLE user_projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE CASCADE,
    owner       VARCHAR(255) NOT NULL,
    repo        VARCHAR(255) NOT NULL,
    repo_url    VARCHAR(500),
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);
```

**GET `/api/user/projects`** — Returns list of projects for the authenticated user.

---

## 6. CORS Updates

The existing CORS config in `app.py` allows all origins. For production with auth:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-domain.com"],  # Be specific
    allow_credentials=True,  # Required for cookies/auth headers
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 7. Environment Variables to Add

```env
# .env additions
JWT_SECRET_KEY=your-very-long-random-secret-key-here
DATABASE_URL=sqlite:///./codewiki.db   # or postgresql://...
```

---

## 8. Frontend Integration Changes

Once the backend endpoints are ready, update the frontend `AuthContext.tsx`:

```typescript
// Replace localStorage simulation with real API calls
const login = async (username: string, password: string): Promise<boolean> => {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) return false;
  const { access_token, user } = await res.json();
  localStorage.setItem('cw_token', access_token);
  setUser(user);
  return true;
};

const register = async (username: string, email: string, password: string): Promise<boolean> => {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) return false;
  const { access_token, user } = await res.json();
  localStorage.setItem('cw_token', access_token);
  setUser(user);
  return true;
};
```

The Next.js API proxy routes in `src/app/api/auth/` will also need updating to forward to the actual backend endpoints.

---

## 9. Summary of Work Estimate

| Task | Complexity | Estimated Effort |
|------|-----------|-----------------|
| Database setup (SQLite) | Low | 2-4 hours |
| User model + CRUD | Low | 2-3 hours |
| Register/Login endpoints | Medium | 3-4 hours |
| JWT implementation | Medium | 2-3 hours |
| Password hashing | Low | 1 hour |
| `/auth/me` endpoint | Low | 1 hour |
| Frontend API integration | Medium | 2-3 hours |
| Testing | Medium | 3-4 hours |
| **Total** | | **~16-22 hours** |

---

## 10. Recommended Libraries

```toml
# Add to api/pyproject.toml
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
aiosqlite = "^0.20"          # For SQLite async
passlib = {extras = ["bcrypt"], version = "^1.7.4"}
python-jose = {extras = ["cryptography"], version = "^3.3.0"}
email-validator = "^2.0"      # For email validation
```

---

*This report was generated as part of the frontend redesign. The frontend currently uses a localStorage-based simulation for authentication that can be replaced with real backend calls once the above changes are implemented.*
