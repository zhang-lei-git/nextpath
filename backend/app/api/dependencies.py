from fastapi import Header


async def current_owner_id(x_demo_user: str | None = Header(default=None)) -> str:
    """Temporary internal-test identity. Replace with WeChat session validation before release."""
    return x_demo_user or "internal-demo-family"
