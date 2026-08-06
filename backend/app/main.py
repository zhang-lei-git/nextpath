from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.database import engine
from app.domain.models import Base


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        # MVP development migration. Production schema changes move to Alembic before public release.
        if settings.database_url.startswith("sqlite"):
            profile_columns = (await connection.exec_driver_sql("PRAGMA table_info(student_profiles)")).fetchall()
            if "grade" not in {column[1] for column in profile_columns}:
                await connection.exec_driver_sql(
                    "ALTER TABLE student_profiles ADD COLUMN grade VARCHAR(16) NOT NULL DEFAULT '初三'"
                )
            exam_columns = (await connection.exec_driver_sql("PRAGMA table_info(exams)")).fetchall()
            if "grade_size" not in {column[1] for column in exam_columns}:
                await connection.exec_driver_sql("ALTER TABLE exams ADD COLUMN grade_size INTEGER")
            if "total_full_mark" not in {column[1] for column in exam_columns}:
                await connection.exec_driver_sql("ALTER TABLE exams ADD COLUMN total_full_mark FLOAT")
            if "physical_score" not in {column[1] for column in exam_columns}:
                await connection.exec_driver_sql("ALTER TABLE exams ADD COLUMN physical_score FLOAT")
            if "physical_estimate" not in {column[1] for column in exam_columns}:
                await connection.exec_driver_sql("ALTER TABLE exams ADD COLUMN physical_estimate FLOAT")
            calibration_columns = (await connection.exec_driver_sql("PRAGMA table_info(position_calibration_samples)")).fetchall()
            if "final_candidate_count" not in {column[1] for column in calibration_columns}:
                await connection.exec_driver_sql(
                    "ALTER TABLE position_calibration_samples ADD COLUMN final_candidate_count INTEGER"
                )
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.allowed_origins if origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-Demo-User"],
)
app.include_router(health_router, prefix="/api")
app.include_router(api_router, prefix=settings.api_prefix)
