import ipaddress
import hashlib
import difflib
import re
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from uuid import uuid4
from zipfile import ZipFile

import httpx
from fastapi import HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.domain.models import (
    CollectionJob,
    CollectionRun,
    DataEvidence,
    DataFact,
    DataIngestion,
    DataRelease,
    DataSource,
    GovernanceRuleVersion,
    OperationAlert,
    ProcessingStep,
    SourceSnapshot,
)
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
    GovernanceRuleCreate,
    GovernanceRuleRead,
    OperationAlertRead,
    OperationAlertUpdate,
    CollectionJobCreate,
    CollectionJobRead,
    CollectionJobUpdate,
    CollectionReprocessRequest,
    CollectionRunDetail,
    CollectionRunRead,
    DataIngestionRead,
    ProcessingStepRead,
    SourceSnapshotRead,
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

    async def create_governance_rule(
        self, payload: GovernanceRuleCreate, actor: str
    ) -> GovernanceRuleRead:
        self._validate_governance_rules(payload.rules)
        try:
            rule = await self.repository.add_governance_rule(GovernanceRuleVersion(
                **payload.model_dump(), created_by=actor
            ))
            await self.session.commit()
        except IntegrityError as error:
            await self.session.rollback()
            raise HTTPException(status_code=409, detail="治理规则版本已存在") from error
        return GovernanceRuleRead.model_validate(rule)

    async def list_governance_rules(self) -> list[GovernanceRuleRead]:
        return [
            GovernanceRuleRead.model_validate(rule)
            for rule in await self.repository.list_governance_rules()
        ]

    async def _require_governance_rule(
        self, version: str
    ) -> GovernanceRuleVersion:
        rule = await self.repository.governance_rule_by_version(version)
        if not rule:
            raise HTTPException(status_code=422, detail="治理规则版本不存在")
        if rule.status != "active":
            raise HTTPException(status_code=422, detail="治理规则版本未启用")
        return rule

    @staticmethod
    def _validate_governance_rules(rules: dict) -> None:
        for key in ("field_aliases", "entity_aliases"):
            aliases = rules.get(key, {})
            if not isinstance(aliases, dict) or not all(
                isinstance(source, str) and isinstance(target, str)
                for source, target in aliases.items()
            ):
                raise HTTPException(status_code=422, detail=f"{key} 必须是字符串映射")
        allowed = rules.get("allowed_fact_types", [])
        if not isinstance(allowed, list) or any(
            item not in {"school", "admission", "policy"} for item in allowed
        ):
            raise HTTPException(status_code=422, detail="allowed_fact_types 包含不支持的数据类别")

    async def list_alerts(
        self, *, status: str | None = None, severity: str | None = None
    ) -> list[OperationAlertRead]:
        return [
            OperationAlertRead.model_validate(alert)
            for alert in await self.repository.list_alerts(status=status, severity=severity)
        ]

    async def update_alert(
        self, alert_id: str, payload: OperationAlertUpdate
    ) -> OperationAlertRead:
        alert = await self.repository.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="未找到运营告警")
        alert.status = payload.status
        alert.resolved_at = datetime.now(timezone.utc) if payload.status == "resolved" else None
        await self.session.commit()
        await self.session.refresh(alert)
        return OperationAlertRead.model_validate(alert)

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
        if payload.governance_rule_version:
            await self._require_governance_rule(payload.governance_rule_version)
        self._validate_collect_url(payload.target_url)
        job = await self.repository.add_collection_job(CollectionJob(**payload.model_dump()))
        await self.session.commit()
        return CollectionJobRead.model_validate(job)

    async def list_collection_jobs(self) -> list[CollectionJobRead]:
        return [CollectionJobRead.model_validate(item) for item in await self.repository.list_collection_jobs()]

    async def update_collection_job(
        self, job_id: str, payload: CollectionJobUpdate
    ) -> CollectionJobRead:
        job = await self.repository.get_collection_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        changes = payload.model_dump(exclude_unset=True)
        required_fields = {
            "name", "target_url", "collection_type", "interval_minutes", "timeout_seconds",
            "max_retries", "rate_limit_per_minute", "parser_key", "priority", "is_active",
        }
        if any(changes.get(field) is None for field in required_fields if field in changes):
            raise HTTPException(status_code=422, detail="采集任务的必填配置不能设为空")
        if "source_id" in changes and changes["source_id"]:
            if not await self.repository.get_source(changes["source_id"]):
                raise HTTPException(status_code=404, detail="未找到数据来源")
        if changes.get("target_url"):
            self._validate_collect_url(changes["target_url"])
        if changes.get("governance_rule_version"):
            await self._require_governance_rule(changes["governance_rule_version"])
        updated = await self.repository.update_collection_job(job, changes)
        await self.session.commit()
        return CollectionJobRead.model_validate(updated)

    async def run_collection_job(
        self,
        job_id: str,
        actor: str,
        *,
        trigger_type: str = "manual",
        attempt: int = 1,
    ) -> DataIngestionRead:
        job = await self.repository.get_collection_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        if not job.is_active and trigger_type == "scheduled":
            raise HTTPException(status_code=409, detail="采集任务已停用")
        now = datetime.now(timezone.utc)
        run = await self.repository.add_collection_run(CollectionRun(
            job_id=job.id,
            trigger_type=trigger_type,
            status="running",
            idempotency_key=f"{job.id}:{uuid4()}",
            attempt=attempt,
            started_at=now,
            scheduled_at=now if trigger_type == "scheduled" else None,
        ))
        try:
            self._validate_collect_url(job.target_url)
            async with httpx.AsyncClient(timeout=job.timeout_seconds, follow_redirects=False) as client:
                response = await client.get(job.target_url, headers={"User-Agent": "NextPath-DataCollector/0.1"})
                if response.status_code >= 400:
                    raise RuntimeError(f"访问返回 HTTP {response.status_code}")
                if 300 <= response.status_code < 400:
                    raise RuntimeError("采集地址发生跳转，需要运营人员确认最终地址")
                content_type = response.headers.get("content-type", "")
                if "html" not in content_type and "text" not in content_type and "json" not in content_type:
                    raise RuntimeError("当前只采集网页、文本或 JSON 内容")
                attachments = await self._capture_attachments(
                    client,
                    base_url=str(response.url),
                    html=response.text if "html" in content_type else "",
                )
            content = response.content
            if len(content) > settings.max_upload_size:
                raise RuntimeError("采集页面超过 10MB")
            content_hash = hashlib.sha256(content).hexdigest()
            attachment_hashes = sorted(
                item["content_hash"] for item in attachments if item.get("content_hash")
            )
            attachment_hash = (
                hashlib.sha256("|".join(attachment_hashes).encode()).hexdigest()
                if attachment_hashes else None
            )
            structure = "|".join(re.findall(r"</?([a-zA-Z0-9]+)", response.text))
            structure_hash = hashlib.sha256(structure.encode()).hexdigest() if structure else None
            previous = await self.repository.latest_snapshot_for_job(job.id)
            unchanged = bool(
                previous
                and previous.content_hash == content_hash
                and previous.attachment_hash == attachment_hash
            )
            change_type = "unchanged" if unchanged else "changed" if previous else "new"
            suffix = ".json" if "json" in content_type else ".html" if "html" in content_type else ".txt"
            stored_name = f"data-snapshots/{content_hash}{suffix}"
            destination = settings.upload_dir / stored_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if not destination.exists():
                destination.write_bytes(content)
            snapshot = await self.repository.add_snapshot(SourceSnapshot(
                run_id=run.id,
                source_url=job.target_url,
                final_url=str(response.url),
                response_status=response.status_code,
                content_hash=content_hash,
                attachment_hash=attachment_hash,
                structure_hash=structure_hash,
                storage_path=stored_name,
                change_type=change_type,
                diff_summary={
                    "previous_hash": previous.content_hash if previous else None,
                    "current_hash": content_hash,
                    "structure_changed": bool(previous and previous.structure_hash != structure_hash),
                    "text_diff": self._build_text_diff(previous, response.text, content_type),
                    "attachments": attachments,
                    "attachments_added": self._attachment_hash_difference(attachments, previous, added=True),
                    "attachments_removed": self._attachment_hash_difference(attachments, previous, added=False),
                },
            ))
            await self._record_step(
                run.id, snapshot.id, "capture", "succeeded",
                output_payload={
                    "content_hash": content_hash,
                    "attachment_hash": attachment_hash,
                    "attachment_count": len(attachments),
                    "change_type": change_type,
                    "bytes": len(content),
                },
            )

            if change_type == "unchanged":
                ingestion = await self.repository.add_ingestion(DataIngestion(
                    source_id=job.source_id,
                    ingestion_type="web",
                    title=job.name,
                    source_url=job.target_url,
                    status="unchanged",
                    extraction_text=None,
                    suggested_facts=[],
                    created_by=actor,
                ))
                run.status = "unchanged"
                run.item_count = 1
                run.changed_count = 0
                run.finished_at = datetime.now(timezone.utc)
                job.last_run_at = run.finished_at
                job.last_status = "unchanged"
                job.last_message = "来源内容无变化，未重复治理。"
                await self.session.commit()
                return self._ingestion_read(ingestion)

            extracted_text = self._html_to_text(response.text)
            attachment_text = self._extract_attachment_text(attachments)
            if attachment_text:
                extracted_text = f"{extracted_text}\n{attachment_text}".strip()
            evidence = await self.repository.add_evidence(DataEvidence(
                source_id=job.source_id,
                title=f"{job.name} · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                url=job.target_url,
                excerpt=self._excerpt(extracted_text),
                created_by=actor,
            ))
            snapshot.evidence_id = evidence.id
            suggestions = self._suggest_facts(extracted_text, job.extraction_hint)
            ingestion = await self.repository.add_ingestion(DataIngestion(
                source_id=job.source_id,
                evidence_id=evidence.id,
                ingestion_type="web",
                title=job.name,
                source_url=job.target_url,
                extraction_text=extracted_text,
                suggested_facts=suggestions,
                status="extracted",
                created_by=actor,
            ))
            await self._record_step(
                run.id, snapshot.id, "extract", "succeeded",
                processor_version=f"parser:{job.parser_key}",
                output_payload={
                    "characters": len(extracted_text),
                    "attachment_count": len(attachments),
                    "suggestion_count": len(suggestions),
                },
            )
            candidates = await self._create_automatic_candidates(
                job,
                evidence,
                extracted_text,
                suggestions,
                actor,
                governance_seed=f"{content_hash}:{attachment_hash or '-'}",
                run_id=run.id,
            )
            await self._record_step(
                run.id, snapshot.id, "normalize", "succeeded",
                processor_version=job.governance_rule_version or "governance-baseline-v1",
                output_payload={"candidate_fact_ids": [item.id for item in candidates]},
            )
            run.status = "pending_review" if candidates else "normalized"
            run.item_count = 1
            run.changed_count = 1
            run.finished_at = datetime.now(timezone.utc)
            job.last_run_at = run.finished_at
            job.last_status = run.status
            job.last_message = f"已保存证据、治理材料和 {len(candidates)} 条候选事实：{ingestion.id}"
            await self.session.commit()
            return self._ingestion_read(ingestion)
        except (httpx.HTTPError, RuntimeError, ValueError, OSError, socket.gaierror) as error:
            finished_at = datetime.now(timezone.utc)
            run.status = "failed"
            run.error_message = str(error)
            run.finished_at = finished_at
            await self._record_step(run.id, None, "capture", "failed", error_message=str(error))
            await self.repository.add_alert(OperationAlert(
                alert_type="collection_failed",
                severity="high",
                source_id=job.source_id,
                job_id=job.id,
                run_id=run.id,
                title=f"采集失败：{job.name}",
                details={"error": str(error), "target_url": job.target_url},
            ))
            job.last_run_at = finished_at
            job.last_status = "failed"
            job.last_message = str(error)
            await self.session.commit()
            raise HTTPException(status_code=422, detail=f"采集失败：{error}") from error

    async def list_collection_runs(
        self, *, job_id: str | None = None, status: str | None = None
    ) -> list[CollectionRunRead]:
        return [
            CollectionRunRead.model_validate(item)
            for item in await self.repository.list_collection_runs(job_id=job_id, status=status)
        ]

    async def collection_run_detail(self, run_id: str) -> CollectionRunDetail:
        run = await self.repository.get_collection_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="未找到采集运行")
        snapshots = await self.repository.snapshots_for_run(run_id)
        steps = await self.repository.steps_for_run(run_id)
        return CollectionRunDetail(
            **CollectionRunRead.model_validate(run).model_dump(),
            snapshots=[SourceSnapshotRead.model_validate(item) for item in snapshots],
            steps=[ProcessingStepRead.model_validate(item) for item in steps],
        )

    async def retry_collection_run(self, run_id: str, actor: str) -> DataIngestionRead:
        previous = await self.repository.get_collection_run(run_id)
        if not previous:
            raise HTTPException(status_code=404, detail="未找到采集运行")
        if previous.status != "failed":
            raise HTTPException(status_code=409, detail="只有失败的采集运行可以重试")
        job = await self.repository.get_collection_job(previous.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        if previous.attempt >= job.max_retries + 1:
            raise HTTPException(status_code=409, detail="已达到该任务允许的最大重试次数")
        return await self.run_collection_job(
            job.id,
            actor,
            trigger_type="retry",
            attempt=previous.attempt + 1,
        )

    async def reprocess_collection_run(
        self,
        run_id: str,
        payload: CollectionReprocessRequest,
        actor: str,
    ) -> DataIngestionRead:
        previous = await self.repository.get_collection_run(run_id)
        if not previous:
            raise HTTPException(status_code=404, detail="未找到采集运行")
        snapshots = await self.repository.snapshots_for_run(run_id)
        if not snapshots:
            raise HTTPException(status_code=409, detail="该运行没有可重新治理的原始快照")
        original = snapshots[-1]
        job = await self.repository.get_collection_job(previous.job_id)
        if not job:
            raise HTTPException(status_code=404, detail="未找到采集任务")
        if payload.governance_rule_version:
            await self._require_governance_rule(payload.governance_rule_version)
        now = datetime.now(timezone.utc)
        run = await self.repository.add_collection_run(CollectionRun(
            job_id=job.id,
            trigger_type="reprocess",
            status="running",
            idempotency_key=f"{job.id}:reprocess:{uuid4()}",
            started_at=now,
        ))
        snapshot = await self.repository.add_snapshot(SourceSnapshot(
            run_id=run.id,
            source_url=original.source_url,
            final_url=original.final_url,
            response_status=original.response_status,
            content_hash=original.content_hash,
            attachment_hash=original.attachment_hash,
            structure_hash=original.structure_hash,
            storage_path=original.storage_path,
            change_type="reprocessed",
            diff_summary={
                **(original.diff_summary or {}),
                "reprocessed_from_run_id": previous.id,
                "reprocessed_from_snapshot_id": original.id,
            },
        ))
        try:
            await self._record_step(
                run.id,
                snapshot.id,
                "capture",
                "succeeded",
                output_payload={"reused_snapshot_id": original.id},
            )
            extracted_text = self._extract_snapshot_text(snapshot)
            if not extracted_text:
                raise RuntimeError("原始快照没有可提取的文本")
            evidence = await self.repository.add_evidence(DataEvidence(
                source_id=job.source_id,
                title=f"{job.name} · 重新治理 · {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                url=original.final_url or original.source_url,
                file_path=original.storage_path,
                excerpt=self._excerpt(extracted_text),
                created_by=actor,
            ))
            snapshot.evidence_id = evidence.id
            suggestions = self._suggest_facts(extracted_text, job.extraction_hint)
            ingestion = await self.repository.add_ingestion(DataIngestion(
                source_id=job.source_id,
                evidence_id=evidence.id,
                ingestion_type="reprocess",
                title=job.name,
                file_path=original.storage_path,
                source_url=original.final_url or original.source_url,
                extraction_text=extracted_text,
                suggested_facts=suggestions,
                status="extracted",
                created_by=actor,
            ))
            parser_key = payload.parser_key or job.parser_key
            rule_version = payload.governance_rule_version or job.governance_rule_version
            await self._record_step(
                run.id,
                snapshot.id,
                "extract",
                "succeeded",
                processor_version=f"parser:{parser_key}",
                input_payload={"source_run_id": previous.id},
                output_payload={"characters": len(extracted_text), "suggestion_count": len(suggestions)},
            )
            candidates = await self._create_automatic_candidates(
                job,
                evidence,
                extracted_text,
                suggestions,
                actor,
                governance_seed=f"{original.content_hash}:{original.attachment_hash or '-'}",
                governance_rule_version=rule_version,
                run_id=run.id,
            )
            await self._record_step(
                run.id,
                snapshot.id,
                "normalize",
                "succeeded",
                processor_version=rule_version or "governance-baseline-v1",
                input_payload={"source_run_id": previous.id},
                output_payload={"candidate_fact_ids": [item.id for item in candidates]},
            )
            run.status = "pending_review" if candidates else "normalized"
            run.item_count = 1
            run.changed_count = 0
            run.finished_at = datetime.now(timezone.utc)
            await self.session.commit()
            return self._ingestion_read(ingestion)
        except (RuntimeError, ValueError, OSError) as error:
            run.status = "failed"
            run.error_message = str(error)
            run.finished_at = datetime.now(timezone.utc)
            await self._record_step(
                run.id, snapshot.id, "reprocess", "failed", error_message=str(error)
            )
            await self.session.commit()
            raise HTTPException(status_code=422, detail=f"重新治理失败：{error}") from error

    async def list_ingestions(self) -> list[DataIngestionRead]:
        return [self._ingestion_read(item) for item in await self.repository.list_ingestions()]

    async def _record_step(
        self,
        run_id: str,
        snapshot_id: str | None,
        step_name: str,
        status: str,
        *,
        processor_version: str | None = None,
        input_payload: dict | None = None,
        output_payload: dict | None = None,
        error_message: str | None = None,
    ) -> ProcessingStep:
        now = datetime.now(timezone.utc)
        return await self.repository.add_processing_step(ProcessingStep(
            run_id=run_id,
            snapshot_id=snapshot_id,
            step_name=step_name,
            status=status,
            processor_version=processor_version,
            input_payload=input_payload or {},
            output_payload=output_payload or {},
            error_message=error_message,
            started_at=now,
            finished_at=now,
        ))

    async def _create_automatic_candidates(
        self,
        job: CollectionJob,
        evidence: DataEvidence,
        extracted_text: str,
        suggestions: list[dict],
        actor: str,
        *,
        governance_seed: str,
        governance_rule_version: str | None = None,
        run_id: str | None = None,
    ) -> list[DataFact]:
        if not job.region:
            return []
        year_match = re.search(r"20\d{2}", extracted_text[:2000])
        if not year_match:
            return []
        reference_year = int(year_match.group())
        if not 2020 <= reference_year <= 2100:
            return []
        rule_version = governance_rule_version or job.governance_rule_version or "governance-baseline-v1"
        rule = None
        if rule_version != "governance-baseline-v1":
            rule = await self._require_governance_rule(rule_version)
        rule_config = rule.rules if rule else {}
        field_aliases = rule_config.get("field_aliases", {})
        entity_aliases = rule_config.get("entity_aliases", {})
        allowed_fact_types = set(rule_config.get("allowed_fact_types", []))
        entity_name = entity_aliases.get(job.name, job.name)
        candidates = []
        seen = set()
        for suggestion in suggestions:
            fact_type = suggestion.get("fact_type")
            field = field_aliases.get(suggestion.get("field"), suggestion.get("field"))
            key = (fact_type, field)
            if fact_type not in {"school", "admission", "policy"} or not field or key in seen:
                continue
            if allowed_fact_types and fact_type not in allowed_fact_types:
                continue
            seen.add(key)
            governance_key = hashlib.sha256(
                f"{job.id}:{governance_seed}:{rule_version}:{fact_type}:{field}".encode()
            ).hexdigest()
            existing = await self.repository.find_automatic_fact(
                fact_type=fact_type,
                entity_name=entity_name,
                field=field,
                region=job.region,
                reference_year=reference_year,
                governance_key=governance_key,
            )
            if existing:
                continue
            candidate_value = {
                "summary": self._excerpt(extracted_text),
                "extraction_reason": suggestion.get("reason"),
            }
            matching = await self.repository.matching_facts(
                fact_type=fact_type,
                entity_name=entity_name,
                field=field,
                region=job.region,
                reference_year=reference_year,
            )
            conflicts = [
                item for item in matching
                if item.scope.get("governance_key") != governance_key and item.value != candidate_value
            ]
            candidate = await self.repository.add_fact(DataFact(
                fact_type=fact_type,
                entity_name=entity_name,
                field=field,
                region=job.region,
                reference_year=reference_year,
                scope={
                    "auto_extracted": True,
                    "needs_entity_review": True,
                    "collection_job_id": job.id,
                    "governance_key": governance_key,
                    "governance_rule_version": rule_version,
                    "conflict_fact_ids": [item.id for item in conflicts],
                },
                value=candidate_value,
                evidence_ids=[evidence.id],
                confidence="observation",
                status="pending_review",
                review_note="自动治理候选，发布前必须核对实体、字段和值。",
                created_by=actor,
            ))
            candidates.append(candidate)
            if conflicts:
                await self.repository.add_alert(OperationAlert(
                    alert_type="data_conflict",
                    severity="high" if any(item.status == "approved" for item in conflicts) else "medium",
                    source_id=job.source_id,
                    job_id=job.id,
                    run_id=run_id,
                    title=f"数据冲突：{entity_name} · {field}",
                    details={
                        "candidate_fact_id": candidate.id,
                        "conflict_fact_ids": [item.id for item in conflicts],
                        "reference_year": reference_year,
                        "region": job.region,
                    },
                ))
        return candidates

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
                environment=payload.environment,
                data_purpose=payload.data_purpose,
                usable_for_prediction=payload.usable_for_prediction,
                valid_from=payload.valid_from,
                valid_until=payload.valid_until,
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

    async def _capture_attachments(
        self,
        client: httpx.AsyncClient,
        *,
        base_url: str,
        html: str,
    ) -> list[dict]:
        if not html:
            return []
        supported = {".pdf", ".docx", ".xlsx", ".xls", ".csv", ".json", ".txt", ".md", ".png", ".jpg", ".jpeg"}
        base_host = urlparse(base_url).hostname
        candidates = []
        for raw_url in re.findall(r"href\s*=\s*['\"]([^'\"]+)['\"]", html, flags=re.I):
            absolute_url = urljoin(base_url, raw_url)
            parsed = urlparse(absolute_url)
            suffix = Path(parsed.path).suffix.lower()
            if suffix not in supported or parsed.hostname != base_host or absolute_url in candidates:
                continue
            candidates.append(absolute_url)
            if len(candidates) >= 10:
                break

        attachments = []
        for attachment_url in candidates:
            suffix = Path(urlparse(attachment_url).path).suffix.lower()
            item = {"url": attachment_url, "suffix": suffix}
            try:
                self._validate_collect_url(attachment_url)
                content_parts = []
                content_size = 0
                async with client.stream(
                    "GET",
                    attachment_url,
                    headers={"User-Agent": "NextPath-DataCollector/0.1"},
                ) as response:
                    if response.status_code >= 400 or 300 <= response.status_code < 400:
                        raise RuntimeError(f"附件访问返回 HTTP {response.status_code}")
                    declared_size = int(response.headers.get("content-length", "0") or 0)
                    if declared_size > settings.max_upload_size:
                        raise RuntimeError("附件超过 10MB")
                    async for chunk in response.aiter_bytes():
                        content_size += len(chunk)
                        if content_size > settings.max_upload_size:
                            raise RuntimeError("附件超过 10MB")
                        content_parts.append(chunk)
                    content_type = response.headers.get("content-type")
                content = b"".join(content_parts)
                content_hash = hashlib.sha256(content).hexdigest()
                stored_name = f"data-attachments/{content_hash}{suffix}"
                destination = settings.upload_dir / stored_name
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    destination.write_bytes(content)
                item.update({
                    "content_hash": content_hash,
                    "storage_path": stored_name,
                    "size": content_size,
                    "content_type": content_type,
                })
            except (httpx.HTTPError, RuntimeError, ValueError, OSError, socket.gaierror) as error:
                item["error"] = str(error)
            attachments.append(item)
        return attachments

    @staticmethod
    def _attachment_hash_difference(
        attachments: list[dict], previous: SourceSnapshot | None, *, added: bool
    ) -> list[str]:
        current = {item["content_hash"] for item in attachments if item.get("content_hash")}
        previous_items = (previous.diff_summary or {}).get("attachments", []) if previous else []
        old = {item["content_hash"] for item in previous_items if item.get("content_hash")}
        return sorted(current - old if added else old - current)

    def _build_text_diff(
        self,
        previous: SourceSnapshot | None,
        current_text: str,
        content_type: str,
    ) -> dict:
        if not previous or not previous.storage_path:
            return {"similarity": None, "added": [], "removed": []}
        previous_path = settings.upload_dir / previous.storage_path
        if not previous_path.exists():
            return {"similarity": None, "added": [], "removed": []}
        previous_raw = previous_path.read_text(encoding="utf-8", errors="replace")
        if "html" in content_type:
            previous_raw = self._html_to_text(previous_raw)
            current_text = self._html_to_text(current_text)
        previous_parts = self._diff_parts(previous_raw)
        current_parts = self._diff_parts(current_text)
        matcher = difflib.SequenceMatcher(a=previous_parts, b=current_parts, autojunk=False)
        added = []
        removed = []
        for operation, left_start, left_end, right_start, right_end in matcher.get_opcodes():
            if operation in {"insert", "replace"}:
                added.extend(current_parts[right_start:right_end])
            if operation in {"delete", "replace"}:
                removed.extend(previous_parts[left_start:left_end])
        return {
            "similarity": round(matcher.ratio(), 4),
            "added": added[:12],
            "removed": removed[:12],
            "added_count": len(added),
            "removed_count": len(removed),
        }

    @staticmethod
    def _diff_parts(value: str) -> list[str]:
        return [
            part.strip()
            for part in re.split(r"(?<=[。！？；.!?;])|\n+", value)
            if part.strip()
        ][:2000]

    def _extract_attachment_text(self, attachments: list[dict]) -> str:
        extracted = []
        for item in attachments:
            storage_path = item.get("storage_path")
            if not storage_path:
                continue
            path = settings.upload_dir / storage_path
            if not path.exists():
                continue
            text_value, _ = self._extract_document_text(path.read_bytes(), path.suffix.lower())
            if text_value:
                extracted.append(text_value)
        return "\n".join(extracted)

    def _extract_snapshot_text(self, snapshot: SourceSnapshot) -> str:
        if not snapshot.storage_path:
            return ""
        path = settings.upload_dir / snapshot.storage_path
        if not path.exists():
            raise RuntimeError("原始快照文件不存在")
        content = path.read_bytes()
        if path.suffix.lower() == ".html":
            extracted = self._html_to_text(content.decode("utf-8", errors="replace"))
        else:
            extracted, error = self._extract_document_text(content, path.suffix.lower())
            if error and not extracted:
                raise RuntimeError(error)
            extracted = extracted or ""
        attachment_text = self._extract_attachment_text(
            (snapshot.diff_summary or {}).get("attachments", [])
        )
        return f"{extracted}\n{attachment_text}".strip()

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
            environment=release.environment,
            data_purpose=release.data_purpose,
            usable_for_prediction=release.usable_for_prediction,
            valid_from=release.valid_from,
            valid_until=release.valid_until,
            notes=release.notes,
            published_at=release.published_at,
            fact_count=fact_count,
        )
