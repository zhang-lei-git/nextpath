"""Authenticated PC workbench for NextPath data operations."""

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


ROOT = Path(__file__).resolve().parent
USER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
SESSION_COOKIE = "nextpath_ops_session"


def admin_db_path() -> Path:
    data_dir = Path(os.getenv("NEXT_PATH_ADMIN_DATA_DIR", "/var/lib/nextpath"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "admin-portal.db"


def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_value, digest_value = stored.split("$", 1)
        salt = base64.urlsafe_b64decode(salt_value.encode())
        expected = base64.urlsafe_b64decode(digest_value.encode())
    except (ValueError, UnicodeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return hmac.compare_digest(actual, expected)


def connection() -> sqlite3.Connection:
    db = sqlite3.connect(admin_db_path())
    db.row_factory = sqlite3.Row
    return db


def initialize_users() -> None:
    username = os.getenv("NEXT_PATH_ADMIN_USERNAME")
    password = os.getenv("NEXT_PATH_ADMIN_PASSWORD")
    if not username or not password:
        raise RuntimeError("必须设置 NEXT_PATH_ADMIN_USERNAME 和 NEXT_PATH_ADMIN_PASSWORD")
    if not USER_PATTERN.fullmatch(username):
        raise RuntimeError("初始管理员用户名只能使用字母、数字、下划线或连字符")
    with connection() as db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )"""
        )
        exists = db.execute("SELECT 1 FROM admin_users LIMIT 1").fetchone()
        if not exists:
            now = int(time.time())
            db.execute(
                "INSERT INTO admin_users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (username, password_hash(password), now, now),
            )


def session_secret() -> bytes:
    value = os.getenv("NEXT_PATH_ADMIN_SESSION_SECRET")
    if not value:
        raise RuntimeError("必须设置 NEXT_PATH_ADMIN_SESSION_SECRET")
    return value.encode("utf-8")


def issue_session(username: str) -> str:
    expires_at = int(time.time()) + 12 * 60 * 60
    payload = f"{username}.{expires_at}"
    signature = hmac.new(session_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def session_user(token: str | None) -> str | None:
    if not token:
        return None
    try:
        username, expires_at, signature = token.rsplit(".", 2)
        payload = f"{username}.{expires_at}"
        expected = hmac.new(session_secret(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected) or int(expires_at) < int(time.time()):
            return None
    except (ValueError, TypeError):
        return None
    with connection() as db:
        return username if db.execute("SELECT 1 FROM admin_users WHERE username = ?", (username,)).fetchone() else None


def current_user(request: Request) -> str:
    username = session_user(request.cookies.get(SESSION_COOKIE))
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    return username


class LoginPayload(BaseModel):
    username: str
    password: str


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_-]{3,32}$")
    password: str = Field(min_length=8, max_length=128)


class PasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=128)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_users()
    yield


app = FastAPI(title="NextPath 数据运营台", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=ROOT / "static"), name="assets")


@app.get("/")
async def index(request: Request):
    if not session_user(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/login", status_code=303)
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/login", response_class=FileResponse)
async def login_page(request: Request):
    if session_user(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    return FileResponse(ROOT / "static" / "login.html")


@app.post("/api/auth/login")
async def login(payload: LoginPayload) -> JSONResponse:
    with connection() as db:
        row = db.execute("SELECT password_hash FROM admin_users WHERE username = ?", (payload.username,)).fetchone()
    if not row or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    response = JSONResponse({"username": payload.username})
    response.set_cookie(SESSION_COOKIE, issue_session(payload.username), max_age=12 * 60 * 60, httponly=True, samesite="lax")
    return response


@app.post("/api/auth/logout")
async def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/api/auth/me")
async def me(username: str = Depends(current_user)) -> dict[str, str]:
    return {"username": username}


@app.get("/api/users")
async def list_users(_: str = Depends(current_user)) -> list[dict]:
    with connection() as db:
        rows = db.execute("SELECT id, username, created_at, updated_at FROM admin_users ORDER BY id").fetchall()
    return [dict(row) for row in rows]


@app.post("/api/users", status_code=201)
async def create_user(payload: UserCreate, _: str = Depends(current_user)) -> dict:
    try:
        with connection() as db:
            now = int(time.time())
            cursor = db.execute(
                "INSERT INTO admin_users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (payload.username, password_hash(payload.password), now, now),
            )
            return {"id": cursor.lastrowid, "username": payload.username, "created_at": now, "updated_at": now}
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="该用户名已存在") from error


@app.post("/api/users/{user_id}/password")
async def reset_password(user_id: int, payload: PasswordReset, _: str = Depends(current_user)) -> dict[str, bool]:
    with connection() as db:
        cursor = db.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash(payload.password), int(time.time()), user_id),
        )
        if not cursor.rowcount:
            raise HTTPException(status_code=404, detail="未找到用户")
    return {"ok": True}


@app.api_route("/api/data/{path:path}", methods=["GET", "POST", "PATCH"])
async def proxy_data(path: str, request: Request, _: str = Depends(current_user)) -> JSONResponse:
    return await proxy_to_nextpath(os.getenv("NEXT_PATH_API_BASE", "http://127.0.0.1:8000/api/v1/data"), path, request)


@app.api_route("/api/analysis/{path:path}", methods=["GET", "POST", "PUT"])
async def proxy_analysis(path: str, request: Request, _: str = Depends(current_user)) -> JSONResponse:
    return await proxy_to_nextpath(os.getenv("NEXT_PATH_ANALYSIS_API_BASE", "http://127.0.0.1:8000/api/v1/analysis"), path, request)


async def proxy_to_nextpath(api_base: str, path: str, request: Request) -> JSONResponse:
    api_base = api_base.rstrip("/")
    data_key = os.getenv("DATA_ADMIN_KEY")
    if not data_key:
        raise HTTPException(status_code=503, detail="运营台尚未配置数据管理员密钥")

    content = await request.body()
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.request(
                request.method,
                f"{api_base}/{path}",
                params=request.query_params,
                content=content or None,
                headers={"X-Data-Admin-Key": data_key, "Content-Type": request.headers.get("Content-Type", "application/json")},
            )
        except httpx.HTTPError as error:
            raise HTTPException(status_code=502, detail=f"无法连接数据服务：{error}") from error

    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": "数据服务返回了无法识别的内容"}
    return JSONResponse(status_code=response.status_code, content=payload)
