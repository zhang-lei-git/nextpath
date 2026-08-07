# NextPath MVP

NextPath 是面向家长的中考升学决策助手。此仓库包含原生微信小程序、FastAPI 后端与产品设计规范。

## 本地启动

后端需要 Python 3.12+：

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000
```

接口文档：`http://127.0.0.1:8000/docs`。小程序使用微信开发者工具导入 `miniprogram/`，在 `miniprogram/utils/config.js` 切换本地或生产接口。

## 部署约定

- 小程序 API：`https://nextpath.top/api/v1/`
- 健康检查：`https://nextpath.top/api/health`
- 生产数据库：设置 `DATABASE_URL=postgresql+asyncpg://...`
- 演示身份仅用于内部测试；生产环境须接入微信 `code2Session` 并签发用户令牌。

详细设计见 [docs/design-system.md](docs/design-system.md) 和 [docs/architecture.md](docs/architecture.md)。

## 数据采集进程

执行一次到期采集任务：

```bash
cd backend
.venv/bin/python -m app.workers.scheduler --once
```

持续运行调度器：

```bash
.venv/bin/python -m app.workers.scheduler --poll-seconds 60
```

数据库结构由 Alembic 管理。部署前执行 `alembic upgrade head`；需要回退本次结构时，应先停止 API 和 worker，再执行 `alembic downgrade -1`。
