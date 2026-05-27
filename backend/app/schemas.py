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


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    name: str
    ssh_url: str
    branch: str = "main"
    root_dir: str = "/repo/"
    deploy_script: str = "./deploy.sh"
    log_path: str = "/var/log/"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    ssh_url: Optional[str] = None
    branch: Optional[str] = None
    root_dir: Optional[str] = None
    deploy_script: Optional[str] = None
    log_path: Optional[str] = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    ssh_url: str
    branch: str
    root_dir: str
    deploy_script: str
    log_path: str
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
