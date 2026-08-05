"""Authenticated PC workbench for NextPath data operations.

The browser talks only to this service. It keeps the data-operation key on the
server and forwards approved operator requests to the private NextPath API.
"""

import os
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
security = HTTPBasic()
app = FastAPI(title="NextPath 数据运营台", docs_url=None, redoc_url=None)
app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")


def require_operator(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    username = os.getenv("NEXT_PATH_ADMIN_USERNAME")
    password = os.getenv("NEXT_PATH_ADMIN_PASSWORD")
    valid = bool(username and password) and secrets.compare_digest(credentials.username, username) and secrets.compare_digest(
        credentials.password, password
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要运营台账号",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@app.get("/", response_class=FileResponse)
async def index(_: str = Depends(require_operator)) -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.api_route("/api/data/{path:path}", methods=["GET", "POST"])
async def proxy_data(path: str, request: Request, _: str = Depends(require_operator)) -> JSONResponse:
    api_base = os.getenv("NEXT_PATH_API_BASE", "http://127.0.0.1:8000/api/v1/data").rstrip("/")
    data_key = os.getenv("DATA_ADMIN_KEY")
    if not data_key:
        raise HTTPException(status_code=503, detail="运营台尚未配置数据管理员密钥")

    headers = {"X-Data-Admin-Key": data_key}
    content = await request.body()
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.request(
                request.method,
                f"{api_base}/{path}",
                params=request.query_params,
                content=content or None,
                headers={**headers, "Content-Type": request.headers.get("Content-Type", "application/json")},
            )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail=f"无法连接数据服务：{error}") from error

    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": "数据服务返回了无法识别的内容"}
    return JSONResponse(status_code=response.status_code, content=payload)
