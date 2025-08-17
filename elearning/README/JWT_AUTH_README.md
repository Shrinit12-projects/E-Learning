# JWT Authentication – E-Learning Platform API

## 📌 Overview
This is the **JWT Authentication** implementation for the **E-Learning Platform Analytics API** built with **FastAPI**, **MongoDB**, and **Redis**.  
It follows the requirements from the project specification:

- JWT authentication with **role-based access control**
- Redis session management & **token blacklisting**
- Refresh token validation against Redis
- Swagger UI integration with **OAuth2 Password Flow**
- MongoDB for persistent user storage
- Secure password hashing with `passlib`

This README contains *all* context for how JWT works in the project so development can resume anytime without re-analyzing the code.

---

## 🗂 Folder Structure (Auth-Related)
```
.
├── auth/
│   ├── jwt.py                # Token creation, decoding, JTI extraction
│   └── dependencies.py       # get_current_user + role checks
├── routers/
│   └── auth.py               # /register, /login, /refresh, /logout endpoints
├── repos/
│   └── users.py              # User CRUD + password hashing
├── schemas/
│   └── auth_schemas.py       # Pydantic request/response models
├── deps.py                   # Mongo + Redis connection injection
├── config.py                 # Settings (Mongo URI, Redis URL, JWT secret, etc.)
└── .env                      # Secret keys + TTL values
```

---

## ⚙ Environment Variables (`.env`)
```env
MONGO_URI=mongodb://elearning-mongo:27017/elearning?replicaSet=rs0
REDIS_URL=redis://redis:6379/0
JWT_SECRET=change-this-in-prod
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
```

---

## 🛠 Dependencies
Required Python packages for JWT Auth:
```txt
fastapi
pymongo
redis
passlib[bcrypt]
pyjwt
pydantic
```

---

## 🔑 Token Types

### Access Token
- **Lifetime**: 15 minutes (configurable via `.env`)
- **Purpose**: Used for authenticating API calls
- **Claims**:
```json
{
  "sub": "<user_id>",
  "role": "<role>",
  "exp": "<expiry_timestamp>",
  "jti": "<unique_id>",
  "type": "access"
}
```

### Refresh Token
- **Lifetime**: 7 days (configurable via `.env`)
- **Purpose**: Used to get a new Access Token without re-login
- Stored in Redis for validation
- **Claims**:
```json
{
  "sub": "<user_id>",
  "role": "<role>",
  "exp": "<expiry_timestamp>",
  "jti": "<unique_id>",
  "type": "refresh"
}
```

---

## 🗄 Redis Key Patterns
| Key Pattern | Purpose | TTL |
|-------------|---------|-----|
| `user_session:{user_id}` | Cached session info (email, role) | 24h |
| `refresh_tokens:{user_id}` | Stored refresh token | 7d |
| `blacklisted_tokens:{jti}` | Revoked access token ID | Token lifetime |

---

## 📜 Endpoints

### 1. `POST /auth/register`
Registers a new user.
```json
{
  "email": "student@example.com",
  "password": "123456",
  "full_name": "John Doe",
  "role": "student"
}
```

---

### 2. `POST /auth/login`
OAuth2 Password Flow login (Swagger form):
- **username** → email
- **password** → password

**Response:**
```json
{
  "access_token": "<jwt_access_token>",
  "refresh_token": "<jwt_refresh_token>",
  "token_type": "bearer"
}
```

---

### 3. `POST /auth/refresh`
Gets a new access token using a refresh token.
```json
{
  "refresh_token": "<jwt_refresh_token>"
}
```

---

### 4. `DELETE /auth/logout`
Revokes both access & refresh tokens:
- Blacklists current access token in Redis
- Deletes `user_session` and `refresh_tokens` entries

---

## 📦 Auth Flow

1. **Register** → Create MongoDB user (hashed password)
2. **Login** → Verify password → Issue access + refresh tokens → Store in Redis
3. **Access API** → Send `Authorization: Bearer <access_token>` → Checked against Redis
4. **Refresh Token** → Get new access token without re-login
5. **Logout** → Blacklist access token JTI + delete Redis session

---

## 🔒 Role-Based Access
Implemented with:
```python
from auth.dependencies import require_role

@router.get("/admin-only")
async def admin_endpoint(user=Depends(require_role("admin"))):
    return {"message": "Welcome Admin"}
```
This checks the `"role"` claim in the JWT and ensures it matches the required roles.

---

## 🧠 Key Design Decisions
- **OAuth2PasswordBearer + OAuth2PasswordRequestForm**: Keeps Swagger login form & "Authorize" button functional.
- **Redis Blacklist**: Allows immediate token invalidation without waiting for expiry.
- **Session TTL**: Users are logged out automatically after 24h unless they refresh the token.
- **JTI Claim**: Each token has a unique ID for blacklisting.

---

## ▶ How to Run (Auth Only)
1. Start **MongoDB + Redis** via `docker-compose` in `/elearningdb`:
```bash
cd elearningdb
docker compose up -d
```
2. Start the API:
```bash
docker compose up --build
```
3. Open Swagger UI at:
```
http://localhost:8000/docs
```

---

If you give me back **this README** later:
- I’ll know how JWT auth works here
- I’ll know where Redis fits in
- I’ll know Mongo is used for user persistence
- I’ll know the endpoints, request/response formats, and token flow
- I’ll know your TTLs, claims, and key patterns
- I’ll know your role-based access dependency

