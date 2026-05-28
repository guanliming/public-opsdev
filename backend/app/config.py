import os

SECRET_KEY = os.getenv("SECRET_KEY", "opsdev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72

DATABASE_URL = "sqlite+aiosqlite:///./opsdev.db"

AGENT_URL = os.getenv("AGENT_URL", "http://localhost:3001")
