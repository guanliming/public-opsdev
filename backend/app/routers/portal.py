from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MenuLink, VirtualMachine, User
from app.schemas import (
    MenuLinkCreate, MenuLinkUpdate, MenuLinkResponse,
    VirtualMachineCreate, VirtualMachineUpdate, VirtualMachineResponse,
)
from app.auth import get_current_user, get_admin_user

router = APIRouter(prefix="/api/portal", tags=["portal"])


@router.get("/links", response_model=list[MenuLinkResponse])
async def list_links(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MenuLink).order_by(MenuLink.sort_order, MenuLink.id))
    return result.scalars().all()


@router.post("/links", response_model=MenuLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_link(req: MenuLinkCreate, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    link = MenuLink(name=req.name, url=req.url, icon=req.icon, sort_order=req.sort_order)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


@router.put("/links/{link_id}", response_model=MenuLinkResponse)
async def update_link(link_id: int, req: MenuLinkUpdate, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MenuLink).where(MenuLink.id == link_id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在")
    if req.name is not None:
        link.name = req.name
    if req.url is not None:
        link.url = req.url
    if req.icon is not None:
        link.icon = req.icon
    if req.sort_order is not None:
        link.sort_order = req.sort_order
    await db.commit()
    await db.refresh(link)
    return link


@router.delete("/links/{link_id}")
async def delete_link(link_id: int, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MenuLink).where(MenuLink.id == link_id))
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="链接不存在")
    await db.delete(link)
    await db.commit()
    return {"message": "删除成功"}


@router.get("/vms", response_model=list[VirtualMachineResponse])
async def list_vms(_: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VirtualMachine).order_by(VirtualMachine.sort_order, VirtualMachine.id))
    return result.scalars().all()


@router.post("/vms", response_model=VirtualMachineResponse, status_code=status.HTTP_201_CREATED)
async def create_vm(req: VirtualMachineCreate, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    vm = VirtualMachine(
        name=req.name, host=req.host, port=req.port,
        username=req.username, password=req.password,
        icon=req.icon, sort_order=req.sort_order,
    )
    db.add(vm)
    await db.commit()
    await db.refresh(vm)
    return vm


@router.put("/vms/{vm_id}", response_model=VirtualMachineResponse)
async def update_vm(vm_id: int, req: VirtualMachineUpdate, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VirtualMachine).where(VirtualMachine.id == vm_id))
    vm = result.scalar_one_or_none()
    if not vm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="虚拟机不存在")
    if req.name is not None:
        vm.name = req.name
    if req.host is not None:
        vm.host = req.host
    if req.port is not None:
        vm.port = req.port
    if req.username is not None:
        vm.username = req.username
    if req.password is not None:
        vm.password = req.password
    if req.icon is not None:
        vm.icon = req.icon
    if req.sort_order is not None:
        vm.sort_order = req.sort_order
    await db.commit()
    await db.refresh(vm)
    return vm


@router.delete("/vms/{vm_id}")
async def delete_vm(vm_id: int, _: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(VirtualMachine).where(VirtualMachine.id == vm_id))
    vm = result.scalar_one_or_none()
    if not vm:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="虚拟机不存在")
    await db.delete(vm)
    await db.commit()
    return {"message": "删除成功"}
