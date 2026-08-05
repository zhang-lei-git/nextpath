import ipaddress
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.domain.models import CollectionJob, DataEvidence, DataFact, DataIngestion, DataRelease, DataSource
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
    CollectionJobCreate,
    CollectionJobRead,
    DataIngestionRead,
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

    async def ingest_document(
        self,
        *,
        source_id: str | None,
        title: str,
        file: UploadFile,
        actor: str,
    ) -> DataIngestionRead:
        if source_id and not await self.repository.get_source(source_id):
            raise HTTPException(status_code=404, detail="未找到数据来源")
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".txt", ".md", ".csv", ".json", ".docx", ".pdf"}:
            raise HTTPException(status_code=415, detail="支持 TXT、MD、CSV、JSON、DOCX 和 PDF 文件")
        content = await file.read(settings.max_upload_size + 1)
        if len(content) > settings.max_upload_size:
            raise HTTPException(status_code=413, detail="文件不能超过 10MB")
        stored_name = f"data-evidence/{uuid4()}{suffix}"
        destination = settings.upload_dir / stored_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        extracted_text, extraction_error = self._extract_document_text(content, suffix)
        evidence = await self.repository.add_evidence(DataEvidence(
            source_id=source_id,
            title=title,
            file_path=stored_name,
            excerpt=self._excerpt(extracted_text),
            created_by=actor,
        ))
        ingestion = await self.repository.add_ingestion(DataIngestion(
            source_id=source_id,
            evidence_id=evidence.id,
            ingestion_type="document",
            title=title,
            original_filename=file.filename,
            file_path=stored_name,
            extraction_text=extracted_text,
            suggested_facts=self._suggest_facts(extracted_text),
            status="extracted" if extracted_text else "captured",
            error_message=extraction_error,
            created_by=actor,
        ))
        await self.session.commit()
        return self._ingestion_read(ingestion)

    async def create_collection_job(self, payload: CollectionJobCreate) -> CollectionJobRead:
        if payload.source_id and not await self.repository.get_source(payload.source_id):
            raise HTTPException(status_code=404, detail="未找到数据来源")
        self._validate_collect_url(payload.target_url)
        job = await self.repository.add_collection_job(CollectionJob(**payload.model_dump()))
        await self.session.commit()
        return CollectionJobRead.model_validate(job)

    async def list_collection_jobs(self) -> list[CollectionJobRead]:
        return [CollectionJobRead.model_validate(item) for item in await self.repository.list_collection_jobs()]

    async def run_collection_job(self, job_id: str, actor: str) -> DataIngestionRead:
        job = await self.repository.get_collection_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        try:
            self._validate_collect_url(job.target_url)
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                response = await client.get(job.target_url, headers={"User-Agent": "NextPath-DataCollector/0.1"})
            if response.status_code >= 400:
                raise RuntimeError(f"访问返回 HTTP {response.status_code}")
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "text" not in content_type and "json" not in content_type:
                raise RuntimeError("当前只采集网页、文本或 JSON 内容")
            extracted_text = self._html_to_text(response.text)
            evidence = await self.repository.add_evidence(DataEvidence(
                source_id=job.source_id,
                title=f"{job.name} · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                url=job.target_url,
                excerpt=self._excerpt(extracted_text),
                created_by=actor,
            ))
            ingestion = await self.repository.add_ingestion(DataIngestion(
                source_id=job.source_id,
                evidence_id=evidence.id,
                ingestion_type="web",
                title=job.name,
                source_url=job.target_url,
                extraction_text=extracted_text,
                suggested_facts=self._suggest_facts(extracted_text, job.extraction_hint),
                status="extracted",
                created_by=actor,
            ))
            job.last_run_at = datetime.now(timezone.utc)
            job.last_status = "succeeded"
            job.last_message = f"已保存证据与待治理材料：{ingestion.id}"
            await self.session.commit()
            return self._ingestion_read(ingestion)
        except (httpx.HTTPError, RuntimeError, ValueError, socket.gaierror) as error:
            job.last_run_at = datetime.now(timezone.utc)
            job.last_status = "failed"
            job.last_message = str(error)
            await self.session.commit()
            raise HTTPException(status_code=422, detail=f"采集失败：{error}") from error

    async def list_ingestions(self) -> list[DataIngestionRead]:
        return [self._ingestion_read(item) for item in await self.repository.list_ingestions()]

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
    def _ingestion_read(ingestion: DataIngestion) -> DataIngestionRead:
        return DataIngestionRead.model_validate(ingestion)

    @staticmethod
    def _extract_document_text(content: bytes, suffix: str) -> tuple[str | None, str | None]:
        try:
            if suffix in {".txt", ".md", ".csv", ".json"}:
                return content.decode("utf-8", errors="replace"), None
            if suffix == ".docx":
                with ZipFile(__import__("io").BytesIO(content)) as archive:
                    xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
                return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml)).strip(), None
            if suffix == ".pdf":
                try:
                    from pypdf import PdfReader
                    reader = PdfReader(__import__("io").BytesIO(content))
                    return "\n".join(page.extract_text() or "" for page in reader.pages), None
                except ImportError:
                    return None, "PDF 已保存，当前服务未安装文本提取组件，待后续解析。"
        except Exception as error:
            return None, f"文件已保存，但文本提取失败：{error}"
        return None, None

    @staticmethod
    def _html_to_text(value: str) -> str:
        no_script = re.sub(r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", value, flags=re.I)
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", no_script)).strip()

    @staticmethod
    def _excerpt(value: str | None) -> str | None:
        return value[:3900] if value else None

    @staticmethod
    def _suggest_facts(text: str | None, hint: str | None = None) -> list[dict]:
        if not text:
            return []
        hints = []
        for marker, fact_type, field in (
            ("一分一段", "admission", "一分一段参考点"),
            ("招生计划", "admission", "招生计划"),
            ("录取", "admission", "录取参考线"),
            ("志愿", "policy", "中招政策摘要"),
            ("学校", "school", "学校档案"),
        ):
            if marker in text:
                hints.append({"fact_type": fact_type, "field": field, "reason": f"文本包含“{marker}”，需要人工结构化和交叉核验。"})
        if hint:
            hints.insert(0, {"fact_type": "manual", "field": "采集说明", "reason": hint})
        return hints[:6]

    @staticmethod
    def _validate_collect_url(value: str) -> None:
        from urllib.parse import urlparse
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("采集地址必须是 HTTP 或 HTTPS 公网地址")
        addresses = socket.getaddrinfo(parsed.hostname, None, type=socket.SOCK_STREAM)
        for item in addresses:
            address = ipaddress.ip_address(item[4][0])
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
                raise ValueError("采集地址不能指向内网或本机")

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
