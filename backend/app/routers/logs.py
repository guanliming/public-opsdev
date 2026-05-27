import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SECRET_KEY, ALGORITHM
from app.database import get_db, async_session
from app.models import User, Project
from app.auth import get_current_user

router = APIRouter(tags=["logs"])


@router.get("/api/app-logs/tail")
async def tail_logs(
    project_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not project.log_path:
        raise HTTPException(status_code=400, detail="日志路径未配置")

    log_path = project.log_path
    if not os.path.isfile(log_path):
        raise HTTPException(status_code=400, detail=f"日志文件不存在: {log_path}")

    proc = await asyncio.create_subprocess_shell(
        f"tail -n 500 '{log_path}'",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return {"data": stdout.decode("utf-8", errors="replace")}


@router.get("/api/app-logs/search")
async def search_logs(
    project_id: int = Query(...),
    keyword: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not project.log_path:
        raise HTTPException(status_code=400, detail="日志路径未配置")

    log_path = project.log_path
    if not os.path.isfile(log_path):
        raise HTTPException(status_code=400, detail=f"日志文件不存在: {log_path}")

    safe_keyword = keyword.replace("'", "'\\''")
    proc = await asyncio.create_subprocess_shell(
        f"grep --color=never -n '{safe_keyword}' '{log_path}' | tail -n 500",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return {"data": stdout.decode("utf-8", errors="replace"), "keyword": keyword}


@router.get("/api/app-logs/stream")
async def stream_logs(
    project_id: int = Query(...),
    token: str = Query(...),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if not project.log_path:
        raise HTTPException(status_code=400, detail="日志路径未配置")

    log_path = project.log_path
    if not os.path.isfile(log_path):
        raise HTTPException(status_code=400, detail=f"日志文件不存在: {log_path}")

    async def event_generator():
        process = await asyncio.create_subprocess_shell(
            f"tail -f -n 0 '{log_path}'",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                data = line.decode("utf-8", errors="replace").rstrip("\n")
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            process.kill()
            await process.wait()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
