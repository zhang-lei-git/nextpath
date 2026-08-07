from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.data_repository import DataRepository


@dataclass(frozen=True)
class PublishedSchoolReference:
    name: str
    score: float
    source: str


@dataclass(frozen=True)
class PublishedReferenceData:
    reference_year: int
    release_id: str | None = None
    rank_source: str | None = None
    rank_points: tuple[tuple[float, int], ...] = ()
    school_references: tuple[PublishedSchoolReference, ...] = ()
    policy_summary: str | None = None
    rank_full_mark: float | None = None
    candidate_count: int | None = None

    @property
    def has_any_fact(self) -> bool:
        return bool(self.rank_points or self.school_references or self.policy_summary)


class PublishedReferenceDataService:
    """Reads only facts included in the latest published release."""

    def __init__(self, session: AsyncSession) -> None:
        self.repository = DataRepository(session)

    async def load(
        self, region: str, reference_year: int, *, as_of: datetime | None = None
    ) -> PublishedReferenceData | None:
        release = await self.repository.latest_release(region, reference_year, as_of=as_of)
        return await self._from_release(release, reference_year) if release else None

    async def load_latest_historical(
        self, region: str, before_year: int, *, as_of: datetime | None = None
    ) -> PublishedReferenceData | None:
        """Only returns data that existed before the student's target examination year."""
        release = await self.repository.latest_release_before(region, before_year, as_of=as_of)
        return await self._from_release(release, release.reference_year) if release else None

    async def _from_release(self, release, reference_year: int) -> PublishedReferenceData | None:
        admissions = await self.repository.facts_in_release(release.id, "admission")
        policies = await self.repository.facts_in_release(release.id, "policy")
        rank_points: tuple[tuple[float, int], ...] = ()
        rank_source: str | None = None
        rank_full_mark: float | None = None
        candidate_count: int | None = None
        school_references: list[PublishedSchoolReference] = []

        for fact in admissions:
            if fact.field == "一分一段参考点":
                points = fact.value.get("points", [])
                parsed_points = []
                for point in points:
                    if isinstance(point, list | tuple) and len(point) == 2:
                        parsed_points.append((float(point[0]), int(point[1])))
                rank_points = tuple(sorted(parsed_points, reverse=True))
                rank_source = fact.value.get("source") or "已发布一分一段参考数据"
                max_score = fact.value.get("max_score")
                rank_full_mark = float(max_score) if isinstance(max_score, (float, int)) else None
                base = fact.value.get("candidate_count")
                candidate_count = int(base) if isinstance(base, (float, int)) else None
            elif fact.field == "录取参考线" and "score" in fact.value:
                school_references.append(
                    PublishedSchoolReference(
                        name=fact.entity_name,
                        score=float(fact.value["score"]),
                        source=fact.value.get("source") or "已发布学校招录参考数据",
                    )
                )

        policy_summary = next(
            (
                fact.value.get("summary")
                for fact in policies
                if fact.field == "中招政策摘要" and fact.value.get("summary")
            ),
            None,
        )
        data = PublishedReferenceData(
            reference_year=reference_year,
            release_id=release.id,
            rank_source=rank_source,
            rank_points=rank_points,
            school_references=tuple(school_references),
            policy_summary=policy_summary,
            rank_full_mark=rank_full_mark,
            candidate_count=candidate_count,
        )
        return data if data.has_any_fact else None
