from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import CollectionJob, DataEvidence, DataFact, DataIngestion, DataRelease, DataReleaseItem, DataSource


class DataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_source(self, source: DataSource) -> DataSource:
        self.session.add(source)
        await self.session.flush()
        await self.session.refresh(source)
        return source

    async def get_source(self, source_id: str) -> DataSource | None:
        return await self.session.get(DataSource, source_id)

    async def list_sources(self) -> list[DataSource]:
        return list(await self.session.scalars(select(DataSource).order_by(desc(DataSource.created_at))))

    async def add_evidence(self, evidence: DataEvidence) -> DataEvidence:
        self.session.add(evidence)
        await self.session.flush()
        await self.session.refresh(evidence)
        return evidence

    async def list_evidence(self, source_id: str | None = None) -> list[DataEvidence]:
        statement = select(DataEvidence).order_by(desc(DataEvidence.captured_at))
        if source_id:
            statement = statement.where(DataEvidence.source_id == source_id)
        return list(await self.session.scalars(statement))

    async def add_fact(self, fact: DataFact) -> DataFact:
        self.session.add(fact)
        await self.session.flush()
        await self.session.refresh(fact)
        return fact

    async def get_fact(self, fact_id: str) -> DataFact | None:
        return await self.session.get(DataFact, fact_id)

    async def list_facts(self, status: str | None = None) -> list[DataFact]:
        statement = select(DataFact).order_by(desc(DataFact.created_at))
        if status:
            statement = statement.where(DataFact.status == status)
        return list(await self.session.scalars(statement))

    async def review_fact(self, fact: DataFact, decision: str, note: str | None, reviewer: str) -> DataFact:
        fact.status = decision
        fact.review_note = note
        fact.reviewed_by = reviewer
        fact.reviewed_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(fact)
        return fact

    async def get_evidence(self, evidence_ids: list[str]) -> list[DataEvidence]:
        if not evidence_ids:
            return []
        records = list(await self.session.scalars(select(DataEvidence).where(DataEvidence.id.in_(evidence_ids))))
        by_id = {record.id: record for record in records}
        return [by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in by_id]

    async def add_release(self, release: DataRelease, facts: list[DataFact]) -> DataRelease:
        self.session.add(release)
        await self.session.flush()
        self.session.add_all([DataReleaseItem(release_id=release.id, fact_id=fact.id) for fact in facts])
        await self.session.flush()
        await self.session.refresh(release)
        return release

    async def latest_release(self, region: str, reference_year: int) -> DataRelease | None:
        return await self.session.scalar(
            select(DataRelease)
            .where(DataRelease.region == region, DataRelease.reference_year == reference_year)
            .order_by(desc(DataRelease.published_at))
            .limit(1)
        )

    async def latest_release_before(self, region: str, before_year: int) -> DataRelease | None:
        return await self.session.scalar(
            select(DataRelease)
            .where(DataRelease.region == region, DataRelease.reference_year < before_year)
            .order_by(desc(DataRelease.reference_year), desc(DataRelease.published_at))
            .limit(1)
        )

    async def list_releases(self) -> list[DataRelease]:
        return list(await self.session.scalars(select(DataRelease).order_by(desc(DataRelease.published_at))))

    async def release_fact_count(self, release_id: str) -> int:
        return len(list(await self.session.scalars(
            select(DataReleaseItem.id).where(DataReleaseItem.release_id == release_id)
        )))

    async def facts_in_release(self, release_id: str, fact_type: str, entity_name: str | None = None) -> list[DataFact]:
        statement = (
            select(DataFact)
            .join(DataReleaseItem, DataReleaseItem.fact_id == DataFact.id)
            .where(DataReleaseItem.release_id == release_id, DataFact.fact_type == fact_type)
            .order_by(DataFact.entity_name, DataFact.field)
        )
        if entity_name:
            statement = statement.where(DataFact.entity_name == entity_name)
        return list(await self.session.scalars(statement))

    async def all_facts_in_release(self, release_id: str) -> list[DataFact]:
        statement = (
            select(DataFact)
            .join(DataReleaseItem, DataReleaseItem.fact_id == DataFact.id)
            .where(DataReleaseItem.release_id == release_id)
            .order_by(DataFact.fact_type, DataFact.entity_name, DataFact.field)
        )
        return list(await self.session.scalars(statement))

    async def source_for_evidence(self, evidence: DataEvidence) -> DataSource | None:
        return await self.session.get(DataSource, evidence.source_id) if evidence.source_id else None

    async def add_ingestion(self, ingestion: DataIngestion) -> DataIngestion:
        self.session.add(ingestion)
        await self.session.flush()
        await self.session.refresh(ingestion)
        return ingestion

    async def list_ingestions(self) -> list[DataIngestion]:
        return list(await self.session.scalars(select(DataIngestion).order_by(desc(DataIngestion.created_at))))

    async def add_collection_job(self, job: CollectionJob) -> CollectionJob:
        self.session.add(job)
        await self.session.flush()
        await self.session.refresh(job)
        return job

    async def get_collection_job(self, job_id: str) -> CollectionJob | None:
        return await self.session.get(CollectionJob, job_id)

    async def list_collection_jobs(self) -> list[CollectionJob]:
        return list(await self.session.scalars(select(CollectionJob).order_by(desc(CollectionJob.created_at))))
