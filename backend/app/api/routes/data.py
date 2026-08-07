from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import current_data_admin
from app.core.database import get_session
from app.domain.schemas import (
    ConsumerDataResponse,
    DataFactCreate,
    DataFactRead,
    DataFactReview,
    DataReleaseCreate,
    DataReleaseRead,
    DataSourceCreate,
    DataSourceRead,
    EvidenceCreate,
    EvidenceRead,
    CollectionJobCreate,
    CollectionJobRead,
    CollectionJobUpdate,
    CollectionReprocessRequest,
    CollectionRunDetail,
    CollectionRunRead,
    DataIngestionRead,
)
from app.services.data_service import DataService

router = APIRouter(prefix="/data", tags=["data operations"])


@router.post("/sources", response_model=DataSourceRead, status_code=201)
async def create_source(
    payload: DataSourceCreate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataSourceRead:
    return await DataService(session).create_source(payload)


@router.get("/sources", response_model=list[DataSourceRead])
async def list_sources(
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DataSourceRead]:
    return await DataService(session).list_sources()


@router.post("/evidence", response_model=EvidenceRead, status_code=201)
async def create_evidence(
    payload: EvidenceCreate,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> EvidenceRead:
    return await DataService(session).create_evidence(payload, actor)


@router.get("/evidence", response_model=list[EvidenceRead])
async def list_evidence(
    source_id: str | None = Query(default=None),
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[EvidenceRead]:
    return await DataService(session).list_evidence(source_id)


@router.post("/ingestions/documents", response_model=DataIngestionRead, status_code=201)
async def ingest_document(
    title: str = Form(min_length=1, max_length=240),
    file: UploadFile = File(...),
    source_id: str | None = Form(default=None),
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataIngestionRead:
    return await DataService(session).ingest_document(source_id=source_id, title=title, file=file, actor=actor)


@router.get("/ingestions", response_model=list[DataIngestionRead])
async def list_ingestions(
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DataIngestionRead]:
    return await DataService(session).list_ingestions()


@router.post("/collection-jobs", response_model=CollectionJobRead, status_code=201)
async def create_collection_job(
    payload: CollectionJobCreate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> CollectionJobRead:
    return await DataService(session).create_collection_job(payload)


@router.get("/collection-jobs", response_model=list[CollectionJobRead])
async def list_collection_jobs(
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[CollectionJobRead]:
    return await DataService(session).list_collection_jobs()


@router.patch("/collection-jobs/{job_id}", response_model=CollectionJobRead)
async def update_collection_job(
    job_id: str,
    payload: CollectionJobUpdate,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> CollectionJobRead:
    return await DataService(session).update_collection_job(job_id, payload)


@router.post("/collection-jobs/{job_id}/run", response_model=DataIngestionRead)
async def run_collection_job(
    job_id: str,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataIngestionRead:
    return await DataService(session).run_collection_job(job_id, actor)


@router.get("/collection-runs", response_model=list[CollectionRunRead])
async def list_collection_runs(
    job_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[CollectionRunRead]:
    return await DataService(session).list_collection_runs(job_id=job_id, status=status)


@router.get("/collection-runs/{run_id}", response_model=CollectionRunDetail)
async def collection_run_detail(
    run_id: str,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> CollectionRunDetail:
    return await DataService(session).collection_run_detail(run_id)


@router.post("/collection-runs/{run_id}/retry", response_model=DataIngestionRead)
async def retry_collection_run(
    run_id: str,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataIngestionRead:
    return await DataService(session).retry_collection_run(run_id, actor)


@router.post("/collection-runs/{run_id}/reprocess", response_model=DataIngestionRead)
async def reprocess_collection_run(
    run_id: str,
    payload: CollectionReprocessRequest,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataIngestionRead:
    return await DataService(session).reprocess_collection_run(run_id, payload, actor)


@router.post("/facts", response_model=DataFactRead, status_code=201)
async def create_fact(
    payload: DataFactCreate,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataFactRead:
    return await DataService(session).create_fact(payload, actor)


@router.get("/facts", response_model=list[DataFactRead])
async def list_facts(
    status: str | None = Query(default=None, pattern="^(pending_review|approved|rejected)$"),
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DataFactRead]:
    return await DataService(session).list_facts(status)


@router.post("/facts/{fact_id}/review", response_model=DataFactRead)
async def review_fact(
    fact_id: str,
    payload: DataFactReview,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataFactRead:
    return await DataService(session).review_fact(fact_id, payload, actor)


@router.post("/releases", response_model=DataReleaseRead, status_code=201)
async def publish_release(
    payload: DataReleaseCreate,
    actor: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> DataReleaseRead:
    return await DataService(session).publish_release(payload, actor)


@router.get("/releases", response_model=list[DataReleaseRead])
async def list_releases(
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DataReleaseRead]:
    return await DataService(session).list_releases()


@router.get("/releases/{release_id}/facts", response_model=list[DataFactRead])
async def release_facts(
    release_id: str,
    _: str = Depends(current_data_admin),
    session: AsyncSession = Depends(get_session),
) -> list[DataFactRead]:
    return await DataService(session).release_facts(release_id)


@router.get("/consumer/school-search", response_model=ConsumerDataResponse)
async def search_schools(
    region: str,
    reference_year: int,
    query: str = Query(min_length=1, max_length=80),
    school_stage: str = Query(pattern="^(junior|senior)$"),
    session: AsyncSession = Depends(get_session),
) -> ConsumerDataResponse:
    return await DataService(session).search_schools(region, reference_year, query, school_stage)


@router.get("/consumer/schools/{school_name}", response_model=ConsumerDataResponse)
async def consume_school(
    school_name: str,
    region: str,
    reference_year: int,
    session: AsyncSession = Depends(get_session),
) -> ConsumerDataResponse:
    return await DataService(session).consume("school", region, reference_year, school_name)


@router.get("/consumer/admissions", response_model=ConsumerDataResponse)
async def consume_admissions(
    region: str,
    reference_year: int,
    session: AsyncSession = Depends(get_session),
) -> ConsumerDataResponse:
    return await DataService(session).consume("admission", region, reference_year)


@router.get("/consumer/policies", response_model=ConsumerDataResponse)
async def consume_policies(
    region: str,
    reference_year: int,
    session: AsyncSession = Depends(get_session),
) -> ConsumerDataResponse:
    return await DataService(session).consume("policy", region, reference_year)
