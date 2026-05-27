from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import init_db, engine
from app.routers import auth, projects, deploy, logs


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Add log_path column if missing (for existing databases)
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE projects ADD COLUMN log_path VARCHAR(500) NOT NULL DEFAULT '/var/log/'"))
        except Exception:
            pass
    yield


app = FastAPI(title="OpsDevOps", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(deploy.router)
app.include_router(logs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
