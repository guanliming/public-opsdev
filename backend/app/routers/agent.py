import json
import logging
import sys

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import AGENT_URL
from app.database import get_db
from app.models import User, Project
from app.auth import get_current_user

logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AnalyzeRequest(BaseModel):
    project_id: Optional[int] = None
    error_log: str
    extra_context: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    session_id: Optional[str] = None


class ChatRequest(BaseModel):
    project_id: Optional[int] = None
    question: str
    database: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/analyze")
async def analyze_error(
    req: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    payload = {
        "project_name": "unknown",
        "error_log": req.error_log,
    }

    if req.extra_context:
        payload["extra_context"] = req.extra_context

    if req.project_id:
        result = await db.execute(select(Project).where(Project.id == req.project_id))
        project = result.scalar_one_or_none()
        if project:
            payload["project_name"] = project.name
            payload["repo_url"] = project.ssh_url
            payload["local_path"] = project.root_dir
            if project.env_info:
                extra = payload.get("extra_context") or ""
                payload["extra_context"] = (extra + "\n环境信息: " + project.env_info).strip()

    if req.language:
        payload["language"] = req.language
    if req.framework:
        payload["framework"] = req.framework
    if req.session_id:
        payload["session_id"] = req.session_id

    logger.info("→ POST /api/analyze-error payload:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{AGENT_URL}/api/analyze-error", json=payload)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接 Agent 服务，请检查配置")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Agent 服务响应超时")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()

    return {
        "analysis_id": data.get("analysis_id", ""),
        "root_cause": data.get("root_cause", ""),
        "severity": data.get("severity", "unknown"),
        "error_type": data.get("error_type", ""),
        "confidence": data.get("confidence", ""),
        "fix_suggestions": data.get("fix_suggestions", []),
        "related_files": data.get("related_files", []),
        "token_usage": data.get("token_usage"),
        "session_id": data.get("session_id", req.session_id or ""),
    }


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    question = req.question

    if req.project_id:
        result = await db.execute(select(Project).where(Project.id == req.project_id))
        project = result.scalar_one_or_none()
        if project:
            payload_local_path = project.root_dir
            if project.env_info:
                question = f"项目环境信息:\n{project.env_info}\n\n---\n\n{question}"
    else:
        payload_local_path = None

    payload: dict[str, str] = {
        "question": question,
    }

    if payload_local_path:
        payload["local_path"] = payload_local_path

    if req.database:
        payload["database"] = req.database
    if req.session_id:
        payload["session_id"] = req.session_id

    logger.info("→ POST /api/chat payload:\n%s", json.dumps(payload, ensure_ascii=False, indent=2))

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{AGENT_URL}/api/chat", json=payload)
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="无法连接 Agent 服务，请检查配置")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Agent 服务响应超时")

    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)

    data = resp.json()

    return {
        "answer": data.get("answer", ""),
        "question": data.get("question", req.question),
        "session_id": data.get("session_id", req.session_id or ""),
    }
