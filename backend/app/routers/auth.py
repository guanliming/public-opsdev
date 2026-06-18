import base64
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.captcha_service import captcha_service
from app.captcha_store import captcha_store, CAPTCHA_TTL_SECONDS, is_debug_bypass
from app.database import get_db
from app.login_protection import (
    MAX_FAILED_ATTEMPTS,
    FAIL_WINDOW_MINUTES,
    LOCK_DURATION_MINUTES,
    clear_attempts,
    get_lock_status,
    register_failure,
    reset_attempts,
    user_exists,
)
from app.models import User
from app.schemas import (
    CaptchaResponse,
    LoginAttemptStatus,
    LoginRequest,
    PasswordChange,
    Token,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.auth import (
    create_access_token,
    get_admin_user,
    get_current_user,
    hash_password,
    verify_password,
)


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _lock_payload(status_obj):
    return {
        "locked": status_obj.locked,
        "failed_count": status_obj.failed_count,
        "remaining_seconds": status_obj.remaining_seconds,
        "locked_until": _iso(status_obj.locked_until),
        "max_attempts": MAX_FAILED_ATTEMPTS,
        "lock_minutes": LOCK_DURATION_MINUTES,
        "window_minutes": FAIL_WINDOW_MINUTES,
    }


def _make_captcha_response() -> CaptchaResponse:
    token, text, image_bytes = captcha_service.generate()
    captcha_store.put(token, text)
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return CaptchaResponse(
        captcha_token=token,
        image=f"data:image/png;base64,{encoded}",
        expires_in=CAPTCHA_TTL_SECONDS,
    )


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    return _make_captcha_response()


@router.get("/_debug_captcha/{token}")
async def debug_captcha(token: str):
    if not is_debug_bypass():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    code = captcha_store.peek(token)
    if code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return code


@router.post("/login", response_model=Token)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    username = (req.username or "").strip()
    if not username or not req.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码不能为空")

    if not req.captcha_token or not req.captcha_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入图形验证码")
    if not captcha_store.consume(req.captcha_token, captcha_service.normalize(req.captcha_code)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误或已过期")

    lock_status = await get_lock_status(db, username)
    if lock_status.locked:
        body = {
            "detail": f"登录失败次数过多,账号已锁定 {lock_status.remaining_seconds // 60 + 1} 分钟",
        }
        body.update({"lock": _lock_payload(lock_status)})
        return JSONResponse(status_code=status.HTTP_423_LOCKED, content=body)

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    password_ok = bool(user) and verify_password(req.password, user.hashed_password)
    user_exists_flag = bool(user) or await user_exists(db, username)

    if not password_ok:
        if user_exists_flag:
            new_status = await register_failure(db, username)
            if new_status.locked:
                body = {
                    "detail": f"登录失败 {MAX_FAILED_ATTEMPTS} 次,账号已锁定 {LOCK_DURATION_MINUTES} 分钟",
                }
                body.update({"lock": _lock_payload(new_status)})
                return JSONResponse(status_code=status.HTTP_423_LOCKED, content=body)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"用户名或密码错误,还有 {MAX_FAILED_ATTEMPTS - new_status.failed_count} 次尝试机会",
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

    await clear_attempts(db, username)
    token = create_access_token(data={"sub": user.username})
    return Token(access_token=token)


@router.get("/login-attempts/{username}", response_model=LoginAttemptStatus)
async def get_login_attempt_status(
    username: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role != "admin" and current_user.username != username:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权查看")
    lock_status = await get_lock_status(db, username)
    return LoginAttemptStatus(
        username=username,
        failed_count=lock_status.failed_count,
        locked=lock_status.locked,
        locked_until=lock_status.locked_until,
        remaining_seconds=lock_status.remaining_seconds,
    )


@router.post("/login-attempts/{username}/reset")
async def reset_login_attempts(
    username: str,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    existed = await reset_attempts(db, username)
    if not existed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="该用户没有失败记录")
    return {"message": f"已重置用户 {username} 的登录失败记录"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/password")
async def change_password(
    req: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(req.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    current_user.hashed_password = hash_password(req.new_password)
    await db.commit()
    return {"message": "密码修改成功"}


@router.get("/users", response_model=list[UserResponse])
async def list_users(_: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: UserCreate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.username,
        role=req.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    req: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if req.display_name is not None:
        user.display_name = req.display_name
    if req.password:
        user.hashed_password = hash_password(req.password)
    if req.role is not None:
        user.role = req.role
    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    await db.delete(user)
    await db.commit()
    return {"message": "删除成功"}
