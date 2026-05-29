from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime, timezone, timedelta

_beijing = timezone(timedelta(hours=8))

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), default="")
    role = Column(String(20), nullable=False, default="user")
    created_at = Column(DateTime, default=lambda: datetime.now(_beijing))


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    ssh_url = Column(String(500), nullable=False)
    branch = Column(String(100), nullable=False, default="main")
    root_dir = Column(String(500), nullable=False, default="/repo/")
    deploy_script = Column(String(500), nullable=False, default="./deploy.sh")
    log_path = Column(String(500), nullable=False, default="/var/log/")
    env_info = Column(String(2000), nullable=False, default="")
    build_type = Column(String(20), nullable=False, default="jar")
    build_script = Column(String(500), nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(_beijing))
    updated_at = Column(DateTime, default=lambda: datetime.now(_beijing), onupdate=lambda: datetime.now(_beijing))


class DeployLog(Base):
    __tablename__ = "deploy_logs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, nullable=False, index=True)
    project_name = Column(String(100), nullable=False)
    deployer = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="running")
    log = Column(Text, nullable=False, default="")
    started_at = Column(DateTime, default=lambda: datetime.now(_beijing))
    finished_at = Column(DateTime, nullable=True)


class MenuLink(Base):
    __tablename__ = "menu_links"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(500), nullable=False)
    icon = Column(String(100), nullable=True, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(_beijing))


class VirtualMachine(Base):
    __tablename__ = "virtual_machines"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=22)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    icon = Column(String(100), nullable=True, default="")
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(_beijing))
