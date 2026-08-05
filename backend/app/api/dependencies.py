from fastapi import Header, HTTPException

from app.core.config import settings


async def current_owner_id(x_demo_user: str | None = Header(default=None)) -> str:
    """Temporary internal-test identity. Replace with WeChat session validation before release."""
    return x_demo_user or "internal-demo-family"


async def current_data_admin(x_data_admin_key: str | None = Header(default=None)) -> str:
    if not settings.data_admin_key:
        raise HTTPException(status_code=503, detail="数据运营接口尚未配置管理员访问密钥")
    if x_data_admin_key != settings.data_admin_key:
        raise HTTPException(status_code=403, detail="无权执行数据运营操作")
    return "data-admin"
