import asyncio
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError, jwt
from sqlalchemy import select

from app.config import SECRET_KEY, ALGORITHM
from app.database import async_session
from app.models import Project

router = APIRouter(tags=["logs"])


async def verify_ws_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/api/ws/logs")
async def ws_logs(websocket: WebSocket, token: str = Query(...), project_id: int = Query(...)):
    username = await verify_ws_token(token)
    if not username:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()

    if not project or not project.log_path:
        await websocket.accept()
        await websocket.send_json({"type": "error", "data": "项目不存在或日志路径未配置"})
        await websocket.close()
        return

    log_path = project.log_path
    if not os.path.isfile(log_path):
        await websocket.accept()
        await websocket.send_json({"type": "error", "data": f"日志文件不存在: {log_path}"})
        await websocket.close()
        return

    await websocket.accept()

    process = None
    stream_task = None

    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")

            if action == "tail":
                proc = await asyncio.create_subprocess_shell(
                    f"tail -n 500 '{log_path}'",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                stdout, _ = await proc.communicate()
                await websocket.send_json({
                    "type": "bulk",
                    "data": stdout.decode("utf-8", errors="replace")
                })

            elif action == "search":
                keyword = msg.get("keyword", "")
                if keyword:
                    safe_keyword = keyword.replace("'", "'\\''")
                    proc = await asyncio.create_subprocess_shell(
                        f"grep --color=never -n '{safe_keyword}' '{log_path}' | tail -n 500",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.STDOUT,
                    )
                    stdout, _ = await proc.communicate()
                    await websocket.send_json({
                        "type": "search_result",
                        "data": stdout.decode("utf-8", errors="replace"),
                        "keyword": keyword,
                    })

            elif action == "stream_start":
                if process and process.returncode is None:
                    process.kill()
                if stream_task and not stream_task.done():
                    stream_task.cancel()

                process = await asyncio.create_subprocess_shell(
                    f"tail -f -n 0 '{log_path}'",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )

                async def stream_lines(proc, ws):
                    try:
                        while True:
                            line = await proc.stdout.readline()
                            if not line:
                                break
                            await ws.send_json({
                                "type": "line",
                                "data": line.decode("utf-8", errors="replace"),
                            })
                    except (WebSocketDisconnect, Exception):
                        pass

                stream_task = asyncio.create_task(stream_lines(process, websocket))

            elif action == "stream_stop":
                if process and process.returncode is None:
                    process.kill()
                    process = None
                if stream_task and not stream_task.done():
                    stream_task.cancel()
                    stream_task = None

    except WebSocketDisconnect:
        pass
    finally:
        if process and process.returncode is None:
            process.kill()
        if stream_task and not stream_task.done():
            stream_task.cancel()
