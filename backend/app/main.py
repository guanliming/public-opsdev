import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text


from app.database import init_db, engine
from app.routers import auth, projects, deploy, portal, ssh, agent, datasources, sql


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with engine.begin() as conn:
        try:
            await conn.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN log_path VARCHAR(500) NOT NULL DEFAULT '/var/log/'"
                )
            )
        except Exception:
            pass
        try:
            await conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'"
                )
            )
        except Exception:
            pass
        await conn.execute(
            text(
                "UPDATE users SET role = 'admin' WHERE username = 'admin' AND role = 'user'"
            )
        )
        for sql in [
            "CREATE INDEX IF NOT EXISTS ix_deploy_logs_started_at ON deploy_logs(started_at)",
            "CREATE INDEX IF NOT EXISTS ix_deploy_logs_status ON deploy_logs(status)",
        ]:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass
    yield


app = FastAPI(title="DevOps", version="1.0.0", lifespan=lifespan)

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
app.include_router(portal.router)
app.include_router(ssh.router)
app.include_router(agent.router)
app.include_router(datasources.router)
app.include_router(sql.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(static_dir / "index.html")
