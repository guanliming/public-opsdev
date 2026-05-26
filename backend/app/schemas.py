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


class ProjectUpdate(BaseModel):
    name: str | None = None
    ssh_url: str | None = None
    branch: str | None = None
    root_dir: str | None = None
    deploy_script: str | None = None


class ProjectResponse(BaseModel):
    id: int
    name: str
    ssh_url: str
    branch: str
    root_dir: str
    deploy_script: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
