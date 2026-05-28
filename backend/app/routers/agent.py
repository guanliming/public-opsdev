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

router = APIRouter(prefix="/api/agent", tags=["agent"])


class AnalyzeRequest(BaseModel):
    project_id: Optional[int] = None
    error_log: str
    extra_context: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None


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

    if req.project_id:
        result = await db.execute(select(Project).where(Project.id == req.project_id))
        project = result.scalar_one_or_none()
        if project:
            payload["project_name"] = project.name
            payload["repo_url"] = project.ssh_url
            payload["local_path"] = project.root_dir
            if project.env_info:
                payload["extra_context"] = (payload.get("extra_context") or "") + f"\n环境信息: {project.env_info}"

    if req.extra_context:
        payload["extra_context"] = req.extra_context
    if req.language:
        payload["language"] = req.language
    if req.framework:
        payload["framework"] = req.framework

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
    }
