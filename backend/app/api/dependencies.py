from fastapi import Header, HTTPException

from app.core.config import settings
from app.core.tokens import verify_token


async def current_owner_id(
    authorization: str | None = Header(default=None),
    x_demo_user: str | None = Header(default=None),
) -> str:
    if authorization and authorization.startswith("Bearer ") and settings.auth_signing_secret:
        payload = verify_token(authorization[7:], settings.auth_signing_secret, expected_type="family")
        owner_id = payload.get("owner_id")
        if isinstance(owner_id, str) and owner_id:
            return owner_id
    if settings.allow_demo_identity:
        return x_demo_user or "internal-demo-family"
    raise HTTPException(status_code=401, detail="请重新进入小程序完成登录")


async def current_data_admin(x_data_admin_key: str | None = Header(default=None)) -> str:
    if not settings.data_admin_key:
        raise HTTPException(status_code=503, detail="数据运营接口尚未配置管理员访问密钥")
    if x_data_admin_key != settings.data_admin_key:
        raise HTTPException(status_code=403, detail="无权执行数据运营操作")
    return "data-admin"
