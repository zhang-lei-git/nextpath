import argparse
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.database import SessionLocal
from app.services.data_service import DataService


async def run_due_jobs() -> int:
    executed = 0
    async with SessionLocal() as session:
        service = DataService(session)
        jobs = await service.repository.list_collection_jobs()
        now = datetime.now(timezone.utc)
        for job in jobs:
            if not job.is_active:
                continue
            last_run_at = job.last_run_at
            if last_run_at and last_run_at.tzinfo is None:
                last_run_at = last_run_at.replace(tzinfo=timezone.utc)
            if last_run_at and last_run_at + timedelta(minutes=job.interval_minutes) > now:
                continue
            try:
                await service.run_collection_job(job.id, "data-scheduler", trigger_type="scheduled")
            except HTTPException:
                pass
            executed += 1
    return executed


async def serve(poll_seconds: int) -> None:
    while True:
        await run_due_jobs()
        await asyncio.sleep(poll_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NextPath scheduled data collection jobs")
    parser.add_argument("--once", action="store_true", help="Run due jobs once and exit")
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.once:
        asyncio.run(run_due_jobs())
        return
    asyncio.run(serve(max(15, args.poll_seconds)))


if __name__ == "__main__":
    main()
