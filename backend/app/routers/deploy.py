import asyncio
import os
import glob as glob_mod
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import SECRET_KEY, ALGORITHM
from app.database import get_db, async_session
from app.models import User, Project, DeployLog
from app.schemas import DeployLogResponse, DeployLogPageResponse
from app.auth import get_current_user

router = APIRouter(tags=["deploy"])

deploy_logs_cache: dict[int, list[str]] = {}


async def run_command(cmd: str, cwd: str, log_lines: list[str], deploy_log_id: int):
    log_lines.append(f"$ {cmd}\n")
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        start_new_session=True,
    )

    # Concurrently wait for process exit and read stdout.
    # After the shell exits, grandchild daemons (e.g. Java app started with nohup/&)
    # may keep the pipe open. We stop reading shortly after the process exits.
    process_exited = asyncio.Event()

    async def wait_for_exit():
        await process.wait()
        process_exited.set()

    exit_task = asyncio.ensure_future(wait_for_exit())

    while True:
        read_coro = process.stdout.readline()
        if process_exited.is_set():
            try:
                line = await asyncio.wait_for(read_coro, timeout=3)
            except asyncio.TimeoutError:
                break
        else:
            # Wait for either a line of output or process exit
            read_task = asyncio.ensure_future(read_coro)
            done, _ = await asyncio.wait(
                [read_task, exit_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if read_task in done:
                line = read_task.result()
            else:
                # Process exited while we were waiting for output; drain briefly
                try:
                    line = await asyncio.wait_for(read_task, timeout=3)
                except asyncio.TimeoutError:
                    break

        if not line:
            break
        decoded = line.decode("utf-8", errors="replace")
        log_lines.append(decoded)

    if not exit_task.done():
        await exit_task
    return process.returncode


async def do_deploy(project: Project, deployer: str, deploy_log_id: int):
    log_lines = deploy_logs_cache.setdefault(deploy_log_id, [])
    root_dir = project.root_dir
    ssh_url = project.ssh_url
    branch = project.branch
    deploy_script = project.deploy_script

    try:
        log_lines.append(f"=== 开始部署项目: {project.name} ===\n")
        log_lines.append(f"部署分支: {branch}\n")
        log_lines.append(f"项目根目录: {root_dir}\n\n")

        # Step 1: Check if code exists
        is_git_repo = False
        if os.path.isdir(root_dir):
            check_proc = await asyncio.create_subprocess_shell(
                "git rev-parse --is-inside-work-tree",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=root_dir,
            )
            await check_proc.wait()
            is_git_repo = check_proc.returncode == 0

        if not is_git_repo:
            log_lines.append("--- 未检测到代码，开始 clone ---\n")
            os.makedirs(root_dir, exist_ok=True)
            rc = await run_command(f"git clone {ssh_url} .", root_dir, log_lines, deploy_log_id)
            if rc != 0:
                raise Exception(f"git clone 失败，退出码: {rc}")
            rc = await run_command(f"git checkout {branch}", root_dir, log_lines, deploy_log_id)
            if rc != 0:
                raise Exception(f"git checkout 失败，退出码: {rc}")
        else:
            log_lines.append("--- 检测到已有代码，切换分支并拉取最新 ---\n")
            rc = await run_command("git fetch --all", root_dir, log_lines, deploy_log_id)
            if rc != 0:
                raise Exception(f"git fetch 失败，退出码: {rc}")
            rc = await run_command(f"git checkout {branch}", root_dir, log_lines, deploy_log_id)
            if rc != 0:
                raise Exception(f"git checkout {branch} 失败，退出码: {rc}")
            rc = await run_command(f"git pull origin {branch}", root_dir, log_lines, deploy_log_id)
            if rc != 0:
                raise Exception(f"git pull 失败，退出码: {rc}")

        # Step 2: Maven package
        log_lines.append("\n--- 开始打包 ---\n")
        rc = await run_command("mvn clean package -Dmaven.test.skip=true", root_dir, log_lines, deploy_log_id)
        if rc != 0:
            raise Exception(f"mvn package 失败，退出码: {rc}")

        # Step 3: Find and move artifact to deploy_script directory
        log_lines.append("\n--- 移动打包文件 ---\n")
        artifacts = glob_mod.glob(os.path.join(root_dir, "**/target/*.jar"), recursive=True) + \
                    glob_mod.glob(os.path.join(root_dir, "**/target/*.war"), recursive=True)
        artifacts = [a for a in artifacts if not a.endswith("-sources.jar")
                     and not a.endswith("-javadoc.jar")
                     and not a.endswith("-tests.jar")
                     and "original-" not in os.path.basename(a)]
        if not artifacts:
            raise Exception("未找到打包产物 (*.jar / *.war)")

        # Multi-module: prefer artifact whose name contains the project name
        project_name_lower = project.name.lower()
        matched = [a for a in artifacts if project_name_lower in os.path.basename(a).lower()]
        artifact = matched[0] if matched else artifacts[0]
        if len(artifacts) > 1:
            log_lines.append(f"检测到多个打包产物，根据项目名称 [{project.name}] 匹配: {os.path.basename(artifact)}\n")
        artifact_name = os.path.basename(artifact)

        # deploy_script directory
        if os.path.isabs(deploy_script):
            dest_dir = os.path.dirname(deploy_script)
        else:
            dest_dir = os.path.dirname(os.path.join(root_dir, deploy_script))
        if not dest_dir:
            dest_dir = root_dir

        dest_path = os.path.join(dest_dir, artifact_name)
        log_lines.append(f"移动 {artifact} -> {dest_path}\n")
        os.makedirs(dest_dir, exist_ok=True)
        shutil.move(artifact, dest_path)

        # Step 4: Execute deploy script
        log_lines.append("\n--- 执行部署脚本 ---\n")
        if os.path.isabs(deploy_script):
            script_cmd = deploy_script
            script_cwd = os.path.dirname(deploy_script)
        else:
            script_cmd = deploy_script
            script_cwd = root_dir

        rc = await run_command(script_cmd, script_cwd, log_lines, deploy_log_id)
        if rc != 0:
            raise Exception(f"部署脚本执行失败，退出码: {rc}")

        log_lines.append("\n=== 部署成功 ===\n")
        final_status = "success"

    except Exception as e:
        log_lines.append(f"\n=== 部署失败: {str(e)} ===\n")
        final_status = "failed"

    # Update deploy log in database
    async with async_session() as db:
        result = await db.execute(select(DeployLog).where(DeployLog.id == deploy_log_id))
        record = result.scalar_one()
        record.status = final_status
        record.log = "".join(log_lines)
        record.finished_at = datetime.now(timezone.utc)
        await db.commit()


@router.post("/api/projects/{project_id}/deploy", response_model=DeployLogResponse)
async def trigger_deploy(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    deploy_log = DeployLog(
        project_id=project.id,
        project_name=project.name,
        deployer=current_user.username,
        status="running",
        log="",
    )
    db.add(deploy_log)
    await db.commit()
    await db.refresh(deploy_log)

    deploy_logs_cache[deploy_log.id] = []

    asyncio.create_task(do_deploy(project, current_user.username, deploy_log.id))

    return deploy_log


@router.get("/api/deploy-logs", response_model=DeployLogPageResponse)
async def list_deploy_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    total_result = await db.execute(select(func.count()).select_from(DeployLog))
    total = total_result.scalar()
    result = await db.execute(
        select(DeployLog)
        .order_by(DeployLog.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/api/deploy-logs/{log_id}", response_model=DeployLogResponse)
async def get_deploy_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(DeployLog).where(DeployLog.id == log_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部署日志不存在")
    return record


@router.delete("/api/deploy-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deploy_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(DeployLog).where(DeployLog.id == log_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部署日志不存在")
    await db.delete(record)
    await db.commit()


@router.get("/api/deploy-logs/{log_id}/stream")
async def stream_deploy_log(
    log_id: int,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Verify token from query parameter (EventSource doesn't support custom headers)
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(DeployLog).where(DeployLog.id == log_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部署日志不存在")

    async def event_generator():
        sent_index = 0
        while True:
            lines = deploy_logs_cache.get(log_id, [])
            if sent_index < len(lines):
                for i in range(sent_index, len(lines)):
                    data = lines[i].rstrip("\n").replace("\n", "\\n")
                    yield f"data: {data}\n\n"
                sent_index = len(lines)

            async with async_session() as check_db:
                res = await check_db.execute(select(DeployLog.status).where(DeployLog.id == log_id))
                current_status = res.scalar_one()
            if current_status != "running":
                # Send remaining lines
                lines = deploy_logs_cache.get(log_id, [])
                if sent_index < len(lines):
                    for i in range(sent_index, len(lines)):
                        data = lines[i].rstrip("\n").replace("\n", "\\n")
                        yield f"data: {data}\n\n"
                yield f"event: done\ndata: {current_status}\n\n"
                deploy_logs_cache.pop(log_id, None)
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Application Logs Endpoints ---

@router.get("/api/logs/tail")
async def tail_app_logs(
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


@router.get("/api/logs/search")
async def search_app_logs(
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


@router.get("/api/logs/stream")
async def stream_app_logs(
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
