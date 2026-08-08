import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_session
from app.core.tokens import issue_token
from app.domain.models import StudentProfile


router = APIRouter(prefix="/auth", tags=["authentication"])


class WeChatLoginRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)
    legacy_owner_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^internal-[A-Za-z0-9.-]+$")


class LoginResponse(BaseModel):
    access_token: str
    expires_in: int


@router.post("/wechat", response_model=LoginResponse)
async def wechat_login(
    payload: WeChatLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> LoginResponse:
    if not settings.wechat_app_id or not settings.wechat_app_secret or not settings.auth_signing_secret:
        raise HTTPException(status_code=503, detail="微信登录尚未完成服务端配置")
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={
                "appid": settings.wechat_app_id,
                "secret": settings.wechat_app_secret,
                "js_code": payload.code,
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="微信登录服务暂时不可用")
    result = response.json()
    openid = result.get("openid")
    if not openid:
        raise HTTPException(status_code=401, detail="微信登录失败，请重新进入小程序")
    owner_id = f"wx:{openid}"
    if payload.legacy_owner_id:
        current = await session.scalar(select(StudentProfile).where(StudentProfile.owner_id == owner_id))
        legacy = await session.scalar(select(StudentProfile).where(StudentProfile.owner_id == payload.legacy_owner_id))
        if legacy and not current:
            legacy.owner_id = owner_id
            await session.commit()
    token = issue_token(
        {"type": "family", "owner_id": owner_id},
        settings.auth_signing_secret,
        settings.auth_token_ttl_seconds,
    )
    return LoginResponse(access_token=token, expires_in=settings.auth_token_ttl_seconds)
