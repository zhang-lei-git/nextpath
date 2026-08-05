from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import DataEvidence, DataFact, DataRelease, DataSource
from app.domain.schemas import (
    ConsumerDataResponse,
    ConsumerFact,
    DataFactCreate,
    DataFactRead,
    DataFactReview,
    DataReleaseCreate,
    DataReleaseRead,
    DataSourceCreate,
    DataSourceRead,
    EvidenceCreate,
    EvidenceRead,
)
from app.repositories.data_repository import DataRepository


class DataService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DataRepository(session)

    async def create_source(self, payload: DataSourceCreate) -> DataSourceRead:
        source = await self.repository.add_source(DataSource(**payload.model_dump()))
        await self.session.commit()
        return DataSourceRead.model_validate(source)

    async def list_sources(self) -> list[DataSourceRead]:
        return [DataSourceRead.model_validate(source) for source in await self.repository.list_sources()]

    async def create_evidence(self, payload: EvidenceCreate, actor: str) -> EvidenceRead:
        if payload.source_id and not await self.repository.get_source(payload.source_id):
            raise HTTPException(status_code=404, detail="未找到数据来源")
        evidence = await self.repository.add_evidence(DataEvidence(**payload.model_dump(), created_by=actor))
        await self.session.commit()
        return await self._evidence_read(evidence)

    async def list_evidence(self, source_id: str | None = None) -> list[EvidenceRead]:
        evidence = await self.repository.list_evidence(source_id)
        return [await self._evidence_read(record) for record in evidence]

    async def create_fact(self, payload: DataFactCreate, actor: str) -> DataFactRead:
        evidence = await self.repository.get_evidence(payload.evidence_ids)
        if len(evidence) != len(set(payload.evidence_ids)):
            raise HTTPException(status_code=422, detail="存在未登记的证据，不能创建候选事实")
        fact = await self.repository.add_fact(DataFact(**payload.model_dump(), created_by=actor))
        await self.session.commit()
        return DataFactRead.model_validate(fact)

    async def list_facts(self, status: str | None = None) -> list[DataFactRead]:
        return [DataFactRead.model_validate(fact) for fact in await self.repository.list_facts(status)]

    async def review_fact(self, fact_id: str, payload: DataFactReview, actor: str) -> DataFactRead:
        fact = await self.repository.get_fact(fact_id)
        if not fact:
            raise HTTPException(status_code=404, detail="未找到候选事实")
        reviewed = await self.repository.review_fact(fact, payload.decision, payload.note, actor)
        await self.session.commit()
        return DataFactRead.model_validate(reviewed)

    async def publish_release(self, payload: DataReleaseCreate, actor: str) -> DataReleaseRead:
        requested_ids = list(dict.fromkeys(payload.fact_ids))
        facts = []
        for fact_id in requested_ids:
            fact = await self.repository.get_fact(fact_id)
            if not fact:
                raise HTTPException(status_code=404, detail=f"未找到候选事实：{fact_id}")
            facts.append(fact)

        invalid_facts = [fact for fact in facts if fact.status != "approved"]
        if invalid_facts:
            raise HTTPException(status_code=422, detail="只能发布已审核通过的事实")
        mismatched_facts = [
            fact for fact in facts if fact.region != payload.region or fact.reference_year != payload.reference_year
        ]
        if mismatched_facts:
            raise HTTPException(status_code=422, detail="发布版本的地区和年度必须与事实一致")

        release = await self.repository.add_release(
            DataRelease(
                name=payload.name,
                region=payload.region,
                reference_year=payload.reference_year,
                notes=payload.notes,
                published_by=actor,
            ),
            facts,
        )
        await self.session.commit()
        return self._release_read(release, len(facts))

    async def list_releases(self) -> list[DataReleaseRead]:
        releases = await self.repository.list_releases()
        return [self._release_read(release, await self.repository.release_fact_count(release.id)) for release in releases]

    async def release_facts(self, release_id: str) -> list[DataFactRead]:
        release = await self.session.get(DataRelease, release_id)
        if not release:
            raise HTTPException(status_code=404, detail="未找到发布版本")
        return [DataFactRead.model_validate(fact) for fact in await self.repository.all_facts_in_release(release_id)]

    async def consume(
        self,
        fact_type: str,
        region: str,
        reference_year: int,
        entity_name: str | None = None,
    ) -> ConsumerDataResponse:
        release = await self.repository.latest_release(region, reference_year)
        if not release:
            return ConsumerDataResponse(release=None, facts=[])
        facts = await self.repository.facts_in_release(release.id, fact_type, entity_name)
        consumer_facts = [await self._consumer_fact(fact) for fact in facts]
        return ConsumerDataResponse(
            release=self._release_read(release, len(facts)),
            facts=consumer_facts,
        )

    async def search_schools(
        self,
        region: str,
        reference_year: int,
        query: str,
        school_stage: str,
    ) -> ConsumerDataResponse:
        release = await self.repository.latest_release(region, reference_year)
        if not release:
            return ConsumerDataResponse(release=None, facts=[])

        normalized_query = self._normalize_school_name(query)
        facts = await self.repository.facts_in_release(release.id, "school")
        candidates = []
        for fact in facts:
            if fact.value.get("school_stage") != school_stage:
                continue
            names = [fact.entity_name, fact.value.get("short_name", "")]
            normalized_names = [self._normalize_school_name(name) for name in names if name]
            if not any(normalized_query in name for name in normalized_names):
                continue
            ranking = min(
                0 if normalized_query == name else 1 if name.startswith(normalized_query) else 2
                for name in normalized_names
            )
            candidates.append((ranking, fact))
        matched = [fact for _, fact in sorted(candidates, key=lambda item: (item[0], item[1].entity_name))[:12]]
        return ConsumerDataResponse(
            release=self._release_read(release, len(matched)),
            facts=[await self._consumer_fact(fact) for fact in matched],
        )

    async def _consumer_fact(self, fact: DataFact) -> ConsumerFact:
        evidence = [await self._evidence_read(record) for record in await self.repository.get_evidence(fact.evidence_ids)]
        return ConsumerFact(
            id=fact.id,
            fact_type=fact.fact_type,
            entity_name=fact.entity_name,
            field=fact.field,
            region=fact.region,
            reference_year=fact.reference_year,
            scope=fact.scope,
            value=fact.value,
            confidence=fact.confidence,
            evidence=evidence,
        )

    async def _evidence_read(self, evidence: DataEvidence) -> EvidenceRead:
        source = await self.repository.source_for_evidence(evidence)
        return EvidenceRead(
            id=evidence.id,
            source_id=evidence.source_id,
            title=evidence.title,
            url=evidence.url,
            file_path=evidence.file_path,
            excerpt=evidence.excerpt,
            captured_at=evidence.captured_at,
            source_name=source.name if source else None,
            source_type=source.source_type if source else None,
        )

    @staticmethod
    def _normalize_school_name(value: str) -> str:
        normalized = value.replace(" ", "").lower()
        for source, target in (("第一", "一"), ("第二", "二"), ("第三", "三"), ("第四", "四"), ("第五", "五"), ("附属", "附")):
            normalized = normalized.replace(source, target)
        return normalized

    @staticmethod
    def _release_read(release: DataRelease, fact_count: int) -> DataReleaseRead:
        return DataReleaseRead(
            id=release.id,
            name=release.name,
            region=release.region,
            reference_year=release.reference_year,
            notes=release.notes,
            published_at=release.published_at,
            fact_count=fact_count,
        )
