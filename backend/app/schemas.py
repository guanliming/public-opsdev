from typing import Optional

from pydantic import BaseModel
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str
    password: str
    display_name: str = ""
    role: str = "user"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    ssh_url: str
    branch: str = "main"
    root_dir: str = "/repo/"
    deploy_script: str = "./deploy.sh"
    log_path: str = "/var/log/"
    env_info: str = ""
    build_type: str = "jar"
    build_script: str = ""


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    ssh_url: Optional[str] = None
    branch: Optional[str] = None
    root_dir: Optional[str] = None
    deploy_script: Optional[str] = None
    log_path: Optional[str] = None
    env_info: Optional[str] = None
    build_type: Optional[str] = None
    build_script: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    ssh_url: str
    branch: str
    root_dir: str
    deploy_script: str
    log_path: str
    env_info: str
    build_type: str
    build_script: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DeployLogResponse(BaseModel):
    id: int
    project_id: int
    project_name: str
    deployer: str
    status: str
    log: str
    started_at: datetime
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DeployLogPageResponse(BaseModel):
    items: list[DeployLogResponse]
    total: int
    page: int
    page_size: int


class MenuLinkCreate(BaseModel):
    name: str
    url: str
    icon: str = ""
    sort_order: int = 0


class MenuLinkUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None


class MenuLinkResponse(BaseModel):
    id: int
    name: str
    url: str
    icon: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VirtualMachineCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    password: str
    icon: str = ""
    sort_order: int = 0


class VirtualMachineUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    icon: Optional[str] = None
    sort_order: Optional[int] = None


class VirtualMachineResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    username: str
    password: str
    icon: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}
