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
- 微信身份：配置 `WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`AUTH_SIGNING_SECRET`，然后设置 `ALLOW_DEMO_IDENTITY=false`。首次切换会把当前设备的内部测试档案迁移到微信身份。
- 报告访问：必须配置 `REPORT_SIGNING_SECRET`；小程序先取得短期签名地址，HTML 报告链接默认 10 分钟失效。
- 对外地址：如域名变化，通过 `PUBLIC_API_BASE_URL` 调整报告签名链接，不要使用 IP 直连 HTTPS。

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

生产环境的 systemd 配置位于 `deploy/nextpath-data-scheduler.service`。

## 历史参考数据

中考前预测只能读取 `production/forecast/usable_for_prediction=true` 的已审核版本。将旧系统中 2025 年及以前的数据发布为历史参考版本：

```bash
cd backend
.venv/bin/python scripts/import_historical_reference_data.py --source /path/to/schools-data.js
```

该脚本排除 2026 年出分后的一分一段表、控制线和预测数据，可重复执行且不会重复创建同名版本。

数据库结构由 Alembic 管理。部署前执行 `alembic upgrade head`；需要回退本次结构时，应先停止 API 和 worker，再执行 `alembic downgrade -1`。
