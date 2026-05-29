import asyncio
import logging
from typing import Optional

import asyncssh
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.database import async_session
from app.models import VirtualMachine, User
from app.auth import decode_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ssh"])


async def get_ws_user(token: str) -> Optional[User]:
    username = decode_token(token)
    if not username:
        return None
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


@router.websocket("/api/ssh/{vm_id}")
async def ssh_terminal(websocket: WebSocket, vm_id: int, token: str = Query(...)):
    user = await get_ws_user(token)
    if not user:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await websocket.accept()

    async with async_session() as db:
        result = await db.execute(select(VirtualMachine).where(VirtualMachine.id == vm_id))
        vm = result.scalar_one_or_none()

    if not vm:
        await websocket.send_text("\r\n虚拟机不存在\r\n")
        await websocket.close()
        return

    try:
        logger.info(f"SSH connecting to {vm.host}:{vm.port} as {vm.username}")
        conn = await asyncssh.connect(
            vm.host, port=vm.port,
            username=vm.username, password=vm.password,
            known_hosts=None,
        )
    except Exception as e:
        logger.error(f"SSH connect failed: {e}")
        await websocket.send_text(f"\r\n连接失败: {e}\r\n")
        await websocket.close()
        return

    try:
        process = await conn.create_process(
            term_type="xterm-256color", term_size=(120, 40),
            encoding=None,
        )
        logger.info("SSH session created successfully")

        async def read_from_ssh():
            try:
                while True:
                    data = await process.stdout.read(4096)
                    if not data:
                        break
                    await websocket.send_bytes(data)
            except (WebSocketDisconnect, asyncssh.misc.DisconnectError):
                pass
            except Exception as e:
                logger.error(f"read_from_ssh error: {e}")

        async def read_from_ws():
            try:
                while True:
                    msg = await websocket.receive()
                    if msg.get("type") == "websocket.disconnect":
                        break
                    data = msg.get("text") or (msg.get("bytes") or b"").decode()
                    if not data:
                        continue
                    if data.startswith("\x1b[resize:"):
                        parts = data[9:-1].split(",")
                        if len(parts) == 2:
                            cols, rows = int(parts[0]), int(parts[1])
                            process.channel.change_terminal_size(cols, rows)
                    else:
                        process.stdin.write(data.encode())
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"read_from_ws error: {e}")

        await asyncio.gather(read_from_ssh(), read_from_ws())
    except Exception as e:
        logger.error(f"SSH session error: {e}")
        try:
            await websocket.send_text(f"\r\n会话错误: {e}\r\n")
        except Exception:
            pass
    finally:
        conn.close()
        try:
            await websocket.close()
        except Exception:
            pass
