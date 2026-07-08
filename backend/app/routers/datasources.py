from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_admin_user, get_current_user
from app.crypto import encrypt_value
from app.database import get_db
from app.datasource_pool import data_source_manager, test_connection
from app.models import DataSource, User
from app.schemas import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceTestRequest,
    DataSourceTestResponse,
    DataSourceUpdate,
)


router = APIRouter(prefix="/api/datasources", tags=["datasources"])


def _to_response(ds: DataSource) -> DataSourceResponse:
    return DataSourceResponse(
        id=ds.id,
        name=ds.name,
        db_type=ds.db_type,
        host=ds.host,
        port=ds.port,
        username=ds.username,
        database=ds.database,
        charset=ds.charset,
        description=ds.description,
        has_password=bool(ds.password_encrypted),
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )


async def _build_test_ds(
    payload: DataSourceTestRequest, existing: Optional[DataSource] = None
) -> DataSource:
    if existing is not None and payload.password is None:
        encrypted = existing.password_encrypted
    else:
        encrypted = encrypt_value(payload.password or "")
    return DataSource(
        id=existing.id if existing else 0,
        name=payload.name or (existing.name if existing else "test"),
        db_type=payload.db_type,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password_encrypted=encrypted,
        database=payload.database,
        charset=payload.charset,
        description="",
    )


@router.get("", response_model=list[DataSourceResponse])
async def list_datasources(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DataSource).order_by(DataSource.id))
    return [_to_response(ds) for ds in result.scalars().all()]


@router.get("/{ds_id}", response_model=DataSourceResponse)
async def get_datasource(
    ds_id: int,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在"
        )
    return _to_response(ds)


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def create_datasource(
    req: DataSourceCreate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if req.db_type != "mysql":
        raise HTTPException(status_code=400, detail="仅支持 mysql 类型")
    if not (1 <= req.port <= 65535):
        raise HTTPException(status_code=400, detail="端口无效")
    exists = await db.execute(select(DataSource).where(DataSource.name == req.name))
    if exists.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="数据源名称已存在")
    ds = DataSource(
        name=req.name,
        db_type=req.db_type,
        host=req.host,
        port=req.port,
        username=req.username,
        password_encrypted=encrypt_value(req.password),
        database=req.database,
        charset=req.charset,
        description=req.description,
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return _to_response(ds)


@router.put("/{ds_id}", response_model=DataSourceResponse)
async def update_datasource(
    ds_id: int,
    req: DataSourceUpdate,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在"
        )
    if req.name is not None and req.name != ds.name:
        exists = await db.execute(select(DataSource).where(DataSource.name == req.name))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="数据源名称已存在")
        ds.name = req.name
    if req.db_type is not None:
        if req.db_type != "mysql":
            raise HTTPException(status_code=400, detail="仅支持 mysql 类型")
        ds.db_type = req.db_type
    if req.host is not None:
        ds.host = req.host
    if req.port is not None:
        if not (1 <= req.port <= 65535):
            raise HTTPException(status_code=400, detail="端口无效")
        ds.port = req.port
    if req.username is not None:
        ds.username = req.username
    if req.password:
        ds.password_encrypted = encrypt_value(req.password)
    if req.database is not None:
        ds.database = req.database
    if req.charset is not None:
        ds.charset = req.charset
    if req.description is not None:
        ds.description = req.description
    await db.commit()
    await db.refresh(ds)
    await data_source_manager.drop(ds_id)
    return _to_response(ds)


@router.delete("/{ds_id}")
async def delete_datasource(
    ds_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在"
        )
    await db.delete(ds)
    await db.commit()
    await data_source_manager.drop(ds_id)
    return {"message": "删除成功"}


@router.post("/test", response_model=DataSourceTestResponse)
async def test_datasource_connection(
    req: DataSourceTestRequest,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    existing: Optional[DataSource] = None
    if req.name:
        result = await db.execute(select(DataSource).where(DataSource.name == req.name))
        existing = result.scalar_one_or_none()
    if req.password is None and existing is None:
        return DataSourceTestResponse(ok=False, error="缺少密码")
    ds = await _build_test_ds(req, existing)
    return DataSourceTestResponse(**await test_connection(ds))


@router.post("/{ds_id}/test", response_model=DataSourceTestResponse)
async def test_existing_datasource(
    ds_id: int,
    _: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ds = await db.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="数据源不存在"
        )
    return DataSourceTestResponse(**await test_connection(ds))
