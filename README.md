# OpsDevOps

公司定制化 DevOps 系统，减少开发人员直接登录服务器操作。

## 技术栈

- 前端：Vue 3 + Vite + Element Plus
- 后端：FastAPI + SQLite
- 认证：JWT（72小时有效期）

## 快速启动

### 后端

```bash
cd backend
pip install -r requirements.txt

# 初始化管理员账号（默认 admin / admin123）
python init_user.py

# 启动服务
ss -lntp | grep 8000
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:3000 即可使用，默认账号 `admin` / `admin123`。

## 功能

- [x] 用户登录（JWT 72小时有效期）
- [x] 项目配置管理（SSH地址、部署分支、项目根目录、部署脚本）
- [ ] 一键部署
- [ ] 实时日志查看（WebSocket + Xterm.js） 
