# DevOps 错误分析集成指南

## Overview

本文档描述如何将 Error Analyzer 错误分析服务集成到你的 DevOps 系统中。

DevOps 系统的 Python 后台通过 HTTP REST API 调用 Error Analyzer 服务，传入错误日志和项目信息，获得结构化的错误分析结果（根因分析、修复建议、关联文件等）。

### Architecture

```
┌──────────────────────────────────────┐
│  DevOps 系统                          │
│                                      │
│  ┌───────────────────────────────┐   │
│  │  Python Backend               │   │
│  │                               │   │
│  │  analyze_error(               │   │
│  │    project_name="my-service", │   │
│  │    error_log="panic: ...",    │   │
│  │    local_path="/data/code/",  │   │
│  │    ...                        │   │
│  │  ) → Result                   │   │
│  └──────────┬────────────────────┘   │
│             │ HTTP POST               │
│             │ /api/analyze-error      │
└─────────────┼────────────────────────┘
              │
              ▼
┌──────────────────────────────────────┐
│  Error Analyzer (独立二进制 ~8 MB)     │
│                                      │
│  ┌───────────────────────────────┐   │
│  │  /api/analyze-error           │   │
│  │    → 解析错误日志               │   │
│  │    → 提取堆栈中的文件引用        │   │
│  │    → 读取源代码上下文           │   │
│  │    → WorkerAgent ReAct 循环    │   │
│  │    → 调用大模型进行分析          │   │
│  │    → 支持工具调用 (数据库等)     │   │
│  │    → 返回结构化 JSON           │   │
│  └──────────┬────────────────────┘   │
│             │                         │
│  ┌──────────▼────────────────────┐   │
│  │  LLM (Bailian DashScope)      │   │
│  │  模型: qwen3.6-35b-a3b        │   │
│  └───────────────────────────────┘   │
└──────────────────────────────────────┘
```

Error Analyzer 和 DevOps 部署在同一台服务器上（或内网互通），可以直接访问 DevOps 部署时已经 clone 到本地的项目源代码。

### 和完整 Agent 的关系

这是从完整 MyAgent 项目中独立出来的轻量级二进制，**基于 WorkerAgent 的 ReAct 循环实现**：

- ✅ 纯 Go 编译，**单个二进制文件，不依赖 Go 运行时**
- ✅ 支持 Linux / Windows / macOS
- ✅ 无 Windows 特有依赖（Win32 API 等）
- ✅ 二进制体积约 8 MB
- ✅ 支持 **ReAct 工具调用循环**，可自动使用数据库工具（db_connect, db_query 等）
- ✅ 支持数据库查询来辅助错误分析
- ❌ 不含桌面自动化、窗口控制、Vision 等 GUI 工具

---

## 快速开始（3 步）

### 第 1 步：在开发机上交叉编译 Linux 二进制

```bash
# 在 MyAgent 项目根目录下执行
cd /home/dawn/code/assistant_agent

# 编译 Linux amd64 版本
GOOS=linux GOARCH=amd64 go build -o error-analyzer ./cmd/error-analyzer/

# 编译后得到一个二进制文件
ls -lh error-analyzer
# → -rwxr-xr-x 1 dawn dawn 8.2M May 28 10:00 error-analyzer
```

> 开发机可以是 Windows / macOS / 任何有 Go 环境的机器。
> `GOOS=linux GOARCH=amd64` 表示目标 Linux 系统是 x86_64 架构。

### 第 2 步：把二进制传到目标 Linux 机器

```bash
# scp 到 DevOps 服务器
scp error-analyzer user@devops-server:/opt/agent/

# 如果 DevOps 服务器有 HTTP 文件服务，也可以 wget
```

### 第 3 步：启动服务

在目标机器上：

```bash
# 创建 .env 文件（和二进制放同一目录）
cat > /opt/agent/.env << 'EOF'
BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BAILIAN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen3.6-35b-a3b
EOF

# 加执行权限 & 启动
chmod +x /opt/agent/error-analyzer
/opt/agent/error-analyzer --port 3001
```

输出：
```
[error-analyzer] loaded 3 vars from /opt/agent/.env
[error-analyzer] model=qwen3.6-35b-a3b context=128000 port=3001
[error-analyzer] listening on http://0.0.0.0:3001
```

---

## 前提条件（完整版）

| 条件 | 说明 |
|------|------|
| 服务器 | Linux x86_64（建议 2C4G 以上） |
| 网络 | 与 DevOps 系统内网互通 |
| API Key | 已获取百炼（DashScope）API Key |
| 项目代码 | 已在服务器本地（DevOps 部署流程会 clone） |

---

## 部署步骤（完整版）

### 1. 编译二进制

```bash
cd /home/dawn/code/assistant_agent
GOOS=linux GOARCH=amd64 go build -o error-analyzer ./cmd/error-analyzer/
```

体积对比：

| 版本 | 体积 | 依赖 |
|------|------|------|
| `error-analyzer`（推荐） | ~8 MB | 仅 LLM + HTTP |
| `rpcserver`（完整版） | ~12 MB | 含 Win32 窗口控制等 |

### 2. 传输到目标服务器

```bash
scp error-analyzer your-user@devops-server:/opt/agent/
```

### 3. 配置环境变量

```bash
cat > /opt/agent/.env << 'EOF'
BAILIAN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BAILIAN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen3.6-35b-a3b
EOF

# 安全起见
chmod 600 /opt/agent/.env
```

### 4. 启动

```bash
chmod +x /opt/agent/error-analyzer
/opt/agent/error-analyzer --port 3001 &
```

### 5. 验证

```bash
curl http://localhost:3001/health
# → {"status":"ok","model":"qwen3.6-35b-a3b","time":"2026-05-28T10:00:00+08:00","service":"error-analyzer"}

curl -X POST http://localhost:3001/api/analyze-error \
  -H "Content-Type: application/json" \
  -d '{"project_name":"test","error_log":"test error"}'
# → {"analysis_id":"ea-...","root_cause":"...","severity":"low",...}
```

### 配置详解

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `BAILIAN_API_KEY` | 百炼 / OpenAI 兼容 API Key | **必填** |
| `BAILIAN_API_URL` | API 地址 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| `BAILIAN_MODEL` | 分析用模型 | `qwen3.6-35b-a3b` |

命令行参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--port` | HTTP 监听端口 | `3001` |
| `--pool-size` | Agent 池大小（预创建实例数） | `5` |
| `--cache-ttl` | 缓存 TTL（相同错误指纹） | `5m` |

> 注意：
> - `local_path` 来自请求参数中的 `local_path` 字段，不同项目可能不同
> - 默认端口是 **3001**（不是 3000），避免和完整 rpcserver 冲突

---

## API 参考

### POST /api/analyze-error

主接口，提交错误日志进行分析。

**技术实现**：基于 WorkerAgent ReAct 循环，支持工具调用（大模型可以自动调用数据库工具进行查询辅助分析）。

#### Request

```json
{
  "project_name": "my-service",
  "repo_url": "https://github.com/org/my-service",
  "local_path": "/data/projects/my-service",
  "language": "go",
  "framework": "gin",
  "error_log": "2026-05-28 10:00:00 ERROR http: panic serving 10.0.0.1:54321\npanic: runtime error: invalid memory address or nil pointer dereference\n[signal SIGSEGV: segmentation violation code=0x1 addr=0x0 pc=0x123456]\n\ngoroutine 42 [running]:\nmain.(*Handler).GetUser(...)\n    /data/projects/my-service/handler.go:156 +0x2a1\nmain.(*Server).ServeHTTP(...)\n    /data/projects/my-service/server.go:88 +0x1b3",
  "db_connection": "postgres://app:password@db-host:5432/my_service?sslmode=disable",
  "extra_context": "This error occurs when the API receives a GET request with an invalid user ID"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `project_name` | string | 是 | 项目名称 |
| `error_log` | string | **是** | 完整的错误日志文本 |
| `local_path` | string | 否 | 项目本地代码路径。提供后可自动提取堆栈对应的源代码上下文 |
| `repo_url` | string | 否 | 仓库地址，供参考 |
| `language` | string | 否 | 编程语言（go / python / java / typescript 等） |
| `framework` | string | 否 | 项目框架（gin / spring / django / nest 等） |
| `db_connection` | string | 否 | 数据库连接信息。提供后有助于分析数据库相关错误，密码会自动脱敏 |
| `extra_context` | string | 否 | 额外的上下文信息，如触发条件、复现步骤等 |

#### Response

```json
{
  "analysis_id": "ea-4a2f1b8e3c70",
  "root_cause": "根因分析（中文，200-500 字）...",
  "severity": "critical",
  "error_type": "空指针",
  "confidence": "high",
  "fix_suggestions": [
    {
      "file": "handler.go",
      "line": 156,
      "description": "GetUser 函数中未检查 user 是否为 nil，当传入无效 ID 时直接访问 user.Name 触发 panic。应增加 nil 检查后返回 404。",
      "code_snippet": "func (h *Handler) GetUser(id string) (*User, error) {\n    user, err := h.userRepo.FindByID(id)\n    if err != nil {\n        return nil, fmt.Errorf(\"find user: %w\", err)\n    }\n    if user == nil {\n        return nil, ErrUserNotFound\n    }\n    return user, nil\n}"
    }
  ],
  "related_files": [
    {
      "path": "server.go",
      "reason": "ServeHTTP 中未对 GetUser 的返回值做错误处理，直接将结果传递给 HTTP 响应写入器"
    },
    {
      "path": "user_repo.go",
      "reason": "FindByID 在数据库查询无结果时返回 nil 而非错误，导致调用方未察觉"
    }
  ],
  "token_usage": {
    "prompt_tokens": 2340,
    "completion_tokens": 512,
    "total_tokens": 2852
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `analysis_id` | string | 唯一分析 ID，可用于日志关联 |
| `root_cause` | string | 根因分析（中文，详细说明错误原因和触发路径） |
| `severity` | string | 严重程度：`critical` / `high` / `medium` / `low` |
| `error_type` | string | 错误类型（空指针、类型错误、连接超时、SQL 错误等） |
| `confidence` | string | 模型置信度：`high` / `medium` / `low` |
| `fix_suggestions` | array | 修复建议列表，每项含文件、行号、说明和示例代码 |
| `related_files` | array | 相关文件列表 |
| `token_usage` | object | Token 消耗统计 |

**响应说明**：
- 如果大模型返回了符合格式的 JSON 响应，所有字段都会被正确解析
- 如果返回非结构化文本，`root_cause` 会包含完整分析文本，其他字段为默认值

#### Error Response

```json
{
  "error": "error_log is required",
  "details": "..."
}
```

HTTP 状态码：
- `200` — 分析完成（即使大模型返回格式异常也会返回 200，内容可能包含 `raw_response`）
- `400` — 请求参数错误（如缺少必填字段、JSON 格式错误）
- `405` — 请求方法错误（只接受 POST）
- `500` — 服务端错误（LLM 调用失败、内部异常等）

---

## Python 集成示例

### 安装依赖

```python
pip install requests
```

### 基础用法

```python
import requests
import json
from typing import Optional


class ErrorAnalyzer:
    """Error Analyzer 客户端"""

    def __init__(self, base_url: str = "http://localhost:3001"):
        self.base_url = base_url.rstrip("/")
        self.analyze_url = f"{self.base_url}/api/analyze-error"

    def analyze(
        self,
        project_name: str,
        error_log: str,
        local_path: Optional[str] = None,
        repo_url: Optional[str] = None,
        language: Optional[str] = None,
        framework: Optional[str] = None,
        db_connection: Optional[str] = None,
        extra_context: Optional[str] = None,
        timeout: int = 120,
    ) -> dict:
        """提交错误日志进行分析

        Args:
            project_name: 项目名称
            error_log: 完整错误日志
            local_path: 项目本地代码路径（提供后可自动提取源码上下文）
            repo_url: 仓库地址
            language: 编程语言
            framework: 框架
            db_connection: 数据库连接字符串
            extra_context: 额外上下文信息
            timeout: 超时时间（秒），默认 120

        Returns:
            结构化的分析结果字典

        Raises:
            requests.Timeout: 请求超时
            requests.RequestException: 网络或服务端错误
            ValueError: 服务端返回错误
        """
        payload = {
            "project_name": project_name,
            "error_log": error_log,
        }

        if local_path:
            payload["local_path"] = local_path
        if repo_url:
            payload["repo_url"] = repo_url
        if language:
            payload["language"] = language
        if framework:
            payload["framework"] = framework
        if db_connection:
            payload["db_connection"] = db_connection
        if extra_context:
            payload["extra_context"] = extra_context

        resp = requests.post(
            self.analyze_url,
            json=payload,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

        if resp.status_code != 200:
            try:
                err_data = resp.json()
                raise ValueError(
                    f"API error ({resp.status_code}): {err_data.get('error', 'unknown')}"
                )
            except (json.JSONDecodeError, ValueError):
                raise ValueError(f"API error ({resp.status_code}): {resp.text[:200]}")

        return resp.json()
```

### 在你的 DevOps 流程中集成

```python
# devops_error_handler.py
from error_analyzer import ErrorAnalyzer
from your_devops_sdk import get_project_info, get_error_logs

analyzer = ErrorAnalyzer("http://localhost:3001")

def on_deploy_failure(deploy_task_id: str):
    """部署失败时自动分析错误"""
    # 1. 获取项目配置和错误日志
    project = get_project_info(deploy_task_id)
    logs = get_error_logs(deploy_task_id, limit=100)

    # 2. 调用 Error Analyzer
    result = analyzer.analyze(
        project_name=project.name,
        error_log=logs.latest_error,
        local_path=project.local_path,
        language=project.language,
        framework=project.framework,
        db_connection=project.get_db_connection(),
        repo_url=project.repo_url,
        extra_context=f"Deploy task failed: {deploy_task_id}",
    )

    # 3. 处理分析结果
    if result["severity"] in ("critical", "high"):
        # 高严重错误：创建故障单并通知相关人员
        create_incident(
            title=f"[{result['severity'].upper()}] {project.name}: {result['error_type']}",
            description=result["root_cause"],
            suggestions=result["fix_suggestions"],
        )
        notify_oncall(project.name, result["severity"])
    else:
        # 低严重错误：记录到日志
        log_analysis(project.name, result)

    return result


def batch_analyze_recent_failures(project_name: str, hours: int = 24):
    """批量分析最近失败的构建/部署"""
    failures = get_recent_failures(project_name, hours)
    results = []
    for f in failures:
        try:
            r = analyzer.analyze(
                project_name=project_name,
                error_log=f.error_log,
                local_path=f.local_path,
                language=f.language,
            )
            results.append({"failure_id": f.id, "result": r})
        except Exception as e:
            print(f"Failed to analyze {f.id}: {e}")
    return results
```

### 处理超时和重试

```python
import time
from functools import wraps


def retry(max_retries=2, backoff=2.0):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.Timeout as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(backoff ** attempt)
                except requests.ConnectionError as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(backoff ** attempt)
            raise last_exception
        return wrapper
    return decorator


class ResilientAnalyzer(ErrorAnalyzer):
    @retry(max_retries=2, backoff=1.5)
    def analyze(self, *args, **kwargs):
        kwargs.setdefault("timeout", 120)
        return super().analyze(*args, **kwargs)
```

---

## 代码上下文提取机制

当你在请求中提供了 `local_path` 字段，Error Analyzer 会自动进行以下处理：

1. **解析堆栈跟踪**：正则匹配日志中的 `file.ext:line` 模式
2. **定位文件**：在 `local_path` 下查找匹配的源文件
3. **读取上下文**：读取错误行前后各 8 行的源代码（用 `→` 标记错误行）
4. **注入 Prompt**：将源代码上下文格式化后嵌入 LLM 提示词中

```
### /data/projects/my-service/handler.go (第 156 行是错误行)

    154: func (h *Handler) GetUser(id string) (*User, error) {
    155:     user, err := h.userRepo.FindByID(id)
→  156:     return user, nil
    157: }
    158:
```

### 支持的文件扩展名

| 语言 | 扩展名 |
|------|--------|
| Go | `.go` |
| Python | `.py` |
| Java / Kotlin / Scala | `.java` `.kt` `.scala` |
| TypeScript / JavaScript | `.ts` `.tsx` `.js` |
| Rust | `.rs` |
| Ruby | `.rb` |
| PHP | `.php` |
| C / C++ / C# | `.c` `.cpp` `.cs` |
| Swift | `.swift` |

### 如何最大化源码分析效果

1. **确保 `local_path` 路径正确**：验证文件是否存在、权限是否正确
2. **提供完整的堆栈跟踪**：不要截断
3. **项目代码在本地**：Error Analyzer 直接读取文件系统，不需要网络访问

---

## 服务器部署建议

### 资源需求

| 配置 | 最低 | 推荐 |
|------|------|------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 磁盘 | 1 GB | 10 GB（仅二进制 + .env） |
| 网络 | 内网互通 | 低延迟连接 DevOps 服务和 LLM API |

### 推荐部署拓扑：与 DevOps 服务同机部署

```
一台服务器就够了:
  ┌──────────────────────────────┐
  │  /data/                      │
  │    ├── devops/               │  ← DevOps 系统
  │    ├── projects/             │  ← clone 的各项目代码
  │    │    ├── service-a/       │
  │    │    ├── service-b/       │
  │    │    └── ...              │
  │    └── agent/                │  ← error-analyzer + .env
  │         ├── error-analyzer   │  ← 单个 8MB 文件
  │         └── .env             │
  └──────────────────────────────┘
```

因为 DevOps 部署时已经把所有项目代码 clone 到了这台机器，Error Analyzer 可以直接通过 `local_path` 读取，不需要额外网络挂载。

### 服务管理（systemd）

```ini
# /etc/systemd/system/error-analyzer.service
[Unit]
Description=Error Analyzer Service
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/agent
ExecStart=/opt/agent/error-analyzer --port 3001
Restart=always
RestartSec=5
User=agent
EnvironmentFile=/opt/agent/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable error-analyzer
sudo systemctl start error-analyzer
sudo systemctl status error-analyzer
```

---

## 安全注意事项

1. **API Key 保护**
   - `BAILIAN_API_KEY` 通过 `.env` 文件加载，不要硬编码在代码中
   - `.env` 文件权限设为 `600`（仅 owner 可读）
   - 定期轮换 API Key

2. **数据库连接信息**
   - 传入 `db_connection` 时，Error Analyzer 会自动脱敏密码部分（`postgres://user:****@host/db`）
   - 但明文经过内网 HTTP 传输，建议用 Nginx 反代加 TLS

3. **代码安全**
   - Error Analyzer **只读**源代码，不会写入或修改任何文件
   - 只读取堆栈指向的相关行（±8 行），不会扫描整个项目

4. **网络隔离**
   - 服务不应暴露到公网
   - 用防火墙限制只允许 DevOps 内网 IP 访问端口 3001
   ```bash
   sudo ufw allow from 10.0.0.0/8 to any port 3001
   ```

5. **日志**
   - Error Analyzer 控制台会打印分析请求的项目名和严重程度
   - 错误日志原文**不会**打印到控制台（只传给 LLM）

---

## 故障排查

### 常见问题

**Q: curl 测试返回 404**
```bash
curl http://localhost:3001/api/analyze-error
→ 404 page not found
```
A: 用 POST 方法，带 JSON body：
```bash
curl -X POST http://localhost:3001/api/analyze-error \
  -H "Content-Type: application/json" \
  -d '{"project_name":"test","error_log":"error occurred"}'
```

**Q: 分析特别慢（超过 30 秒）**
A: 首次调用需要加载模型。如果持续慢，检查：
- 服务器到 LLM API 的网络延迟（`ping dashscope.aliyuncs.com`）
- 错误日志是否太长（超过 8000 字符会自动截断）
- `local_path` 是否正确，文件读取是否耗时

**Q: 源码上下文没有出现在分析结果中**
A: 检查：
- `local_path` 路径是否存在、有读权限
- 堆栈格式是否包含带扩展名的文件路径（`handler.go:42`）
- 文件扩展名是否在支持列表中

**Q: 模型返回非结构化内容**
A: 换一个指令跟随能力更强的模型：
```
BAILIAN_MODEL=qwen-plus
```

**Q: 编译时提示 `build constraints exclude all Go files`**
A: 这是用 `GOOS=linux` 编译完整 `rpcserver` 时报的错。用 `./cmd/error-analyzer/` 代替：
```bash
GOOS=linux GOARCH=amd64 go build -o error-analyzer ./cmd/error-analyzer/
```

**Q: 无法连接服务**
```python
requests.exceptions.ConnectionError: HTTPConnectionPool(...)
```
A: 检查：
- 服务是否已启动（`ps aux | grep error-analyzer`、`ss -tlnp | grep 3001`）
- 端口是否正确（默认 3001）
- 防火墙是否放行

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.2 | 2026-05-28 | 新增：Agent 池化、结果缓存、Structured Output 优化 |
| v1.1 | 2026-05-28 | 新增：基于 WorkerAgent ReAct 循环，支持数据库工具自动调用 |
| v1.0 | 2026-05-28 | 初始版本，支持错误日志分析和源码上下文提取 |

---

## 附录：接口一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze-error` | **提交错误日志进行分析（主接口）** |
| GET | `/health` | 健康检查（含模型状态信息） |
