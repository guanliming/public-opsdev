from typing import Optional

from pydantic import BaseModel
from datetime import datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: str
    captcha_code: str


class CaptchaResponse(BaseModel):
    captcha_token: str
    image: str
    expires_in: int


class LoginAttemptStatus(BaseModel):
    username: str
    failed_count: int
    locked: bool
    locked_until: Optional[datetime] = None
    remaining_seconds: int = 0


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


class VirtualMachinePublicResponse(BaseModel):
    id: int
    name: str
    host: str
    port: int
    icon: str
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class VirtualMachineAdminResponse(VirtualMachinePublicResponse):
    username: str


class VirtualMachineResponse(VirtualMachinePublicResponse):
    username: str
    password: str


class DataSourceCreate(BaseModel):
    name: str
    db_type: str = "mysql"
    host: str
    port: int = 3306
    username: str
    password: str
    database: str = ""
    charset: str = "utf8mb4"
    description: str = ""


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    charset: Optional[str] = None
    description: Optional[str] = None


class DataSourceResponse(BaseModel):
    id: int
    name: str
    db_type: str
    host: str
    port: int
    username: str
    database: str
    charset: str
    description: str
    has_password: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DataSourceTestRequest(BaseModel):
    name: Optional[str] = None
    db_type: str = "mysql"
    host: str
    port: int = 3306
    username: str
    password: Optional[str] = None
    database: str = ""
    charset: str = "utf8mb4"


class DataSourceTestResponse(BaseModel):
    ok: bool
    version: Optional[str] = None
    error: Optional[str] = None


class SqlColumnInfo(BaseModel):
    name: str
    type: str


class SqlStatementResult(BaseModel):
    sql: str
    kind: str
    affected_rows: int = 0
    rows: Optional[list[dict]] = None
    columns: Optional[list[SqlColumnInfo]] = None
    execution_time_ms: float = 0
    truncated: bool = False
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


class SqlExecuteRequest(BaseModel):
    sql: str
    database: Optional[str] = None
    max_rows: int = 1000
    confirm_large_change: bool = False


class SqlExecuteResponse(BaseModel):
    datasource_id: int
    is_admin: bool
    statements: list[SqlStatementResult]
    total_affected_rows: int
    total_execution_time_ms: float


class SqlDatabaseInfo(BaseModel):
    name: str


class SqlTableInfo(BaseModel):
    name: str
    rows: Optional[int] = None
    size_mb: Optional[float] = None
