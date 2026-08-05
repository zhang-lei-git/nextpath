"""Import the legacy Xi'an volunteer-planning dataset as a reviewed 2026 release.

The importer deliberately preserves evidence quality. Official policy and plan facts,
user-provided rank references, and third-party school estimates remain distinguishable
after import. Re-running it is safe once the named release already exists.
"""

import argparse
import asyncio
import json
import subprocess
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.domain.models import Base, DataEvidence, DataFact, DataRelease, DataReleaseItem, DataSource


REGION = "西安"
YEAR = 2026
RELEASE_NAME = "2026 西安城六区升学参考数据（旧系统迁移测试版 v2）"

NODE_EXTRACTOR = r"""
const fs = require('fs');
const vm = require('vm');
let source = fs.readFileSync(process.argv[1], 'utf8');
source = source.replace(/^const\s+([A-Za-z0-9_]+)\s*=/gm, 'globalThis.$1 =');
const context = {};
vm.createContext(context);
vm.runInContext(source, context);
const keys = [
  'SOURCE_LINKS', 'RANK_REFERENCE_DATA', 'PUBLIC_2026_ESTIMATES',
  'OFFICIAL_2026_ADMISSION_UPDATE', 'SCHOOL_DATA', 'TARGET_QUOTA_DATA',
  'SCHOOL_ADMISSION_PLAN_COMPARISON_DATA'
];
console.log(JSON.stringify(Object.fromEntries(keys.map((key) => [key, context[key]]))));
"""


def load_legacy_data(path: Path) -> dict:
    result = subprocess.run(
        ["node", "-e", NODE_EXTRACTOR, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


async def find_or_create_source(session, *, name: str, source_type: str, reliability: str, homepage_url: str | None):
    source = await session.scalar(select(DataSource).where(DataSource.name == name).limit(1))
    if source:
        return source
    source = DataSource(
        name=name,
        source_type=source_type,
        reliability=reliability,
        homepage_url=homepage_url,
    )
    session.add(source)
    await session.flush()
    return source


async def create_evidence(session, source: DataSource, *, title: str, url: str | None, excerpt: str | None) -> DataEvidence:
    evidence = DataEvidence(source_id=source.id, title=title, url=url, excerpt=excerpt, created_by="legacy-import")
    session.add(evidence)
    await session.flush()
    return evidence


async def create_fact(
    session,
    *,
    fact_type: str,
    entity_name: str,
    field: str,
    scope: dict,
    value: dict,
    evidence_id: str,
    confidence: str,
) -> DataFact:
    fact = DataFact(
        fact_type=fact_type,
        entity_name=entity_name,
        field=field,
        region=REGION,
        reference_year=YEAR,
        scope=scope,
        value=value,
        evidence_ids=[evidence_id],
        confidence=confidence,
        status="approved",
        review_note="旧志愿预测系统迁移测试数据；已保留原始来源和可信度标识。",
        created_by="legacy-import",
        reviewed_by="legacy-import",
    )
    session.add(fact)
    await session.flush()
    return fact


def source_url(links: list[dict], title_fragment: str) -> str | None:
    return next((item.get("url") for item in links if title_fragment in item.get("title", "")), None)


async def import_data(legacy_data: dict) -> dict[str, int]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        existing = await session.scalar(select(DataRelease).where(DataRelease.name == RELEASE_NAME).limit(1))
        if existing:
            return {"skipped": 1, "release_id": existing.id}

        links = legacy_data["SOURCE_LINKS"]
        official_source = await find_or_create_source(
            session,
            name="西安市教育局公开发布",
            source_type="official",
            reliability="official",
            homepage_url="https://edu.xa.gov.cn/",
        )
        observation_source = await find_or_create_source(
            session,
            name="用户提供的一分一段表截图",
            source_type="manual",
            reliability="observation",
            homepage_url=None,
        )
        third_party_source = await find_or_create_source(
            session,
            name="公开媒体预测整理",
            source_type="media",
            reliability="observation",
            homepage_url="https://www.sohu.com/",
        )
        legacy_source = await find_or_create_source(
            session,
            name="旧版志愿预测系统结构化整理",
            source_type="manual",
            reliability="verified",
            homepage_url=None,
        )

        policy = legacy_data["OFFICIAL_2026_ADMISSION_UPDATE"]
        policy_evidence = await create_evidence(
            session,
            official_source,
            title="2026 年西安市高中阶段学校招生录取工作方案",
            url=source_url(links, "2026年高中阶段学校招生录取工作方案"),
            excerpt="城六区志愿填报、定向生和平行志愿规则。",
        )
        rank_data = legacy_data["RANK_REFERENCE_DATA"]
        rank_evidence = await create_evidence(
            session,
            observation_source,
            title=rank_data["sourceTitle"],
            url=None,
            excerpt="旧系统注明：用户提供图片，待教育主管部门正式发布后核验。",
        )
        estimate_evidence = await create_evidence(
            session,
            third_party_source,
            title="2026 年西安中考分数段与高中匹配预测",
            url=source_url(links, "2026西安中考分数段与高中匹配预测"),
            excerpt="公开预测区间，非官方录取线，仅用于风险提示。",
        )
        school_evidence = await create_evidence(
            session,
            legacy_source,
            title="旧志愿预测系统学校档案与历年录取参考线",
            url=None,
            excerpt="按学校、批次、层次、区域、办学性质和历年公开参考线整理。",
        )
        plan_evidence = await create_evidence(
            session,
            official_source,
            title="2026 年普通高中分学校招生计划",
            url=source_url(links, "2026年普通高中分学校招生计划"),
            excerpt="旧系统按城六区普通高中招生计划原表整理。",
        )
        junior_school_evidence = await create_evidence(
            session,
            official_source,
            title="2026 年城六区省级标准化高中定向生分学校生源计划",
            url=source_url(links, "定向生分学校生源计划"),
            excerpt="覆盖城六区初中学校及对应定向招生名额，作为初中学校基础名录导入。",
        )

        facts: list[DataFact] = []
        points = [[point["score"], point["rank"]] for point in rank_data["points"]]
        facts.append(await create_fact(
            session,
            fact_type="admission",
            entity_name="西安市城六区",
            field="一分一段参考点",
            scope={"coverage": "511-633 分", "verification": "待官方核验"},
            value={"points": points, "source": rank_data["sourceTitle"], "max_score": rank_data["max"]},
            evidence_id=rank_evidence.id,
            confidence="observation",
        ))
        facts.append(await create_fact(
            session,
            fact_type="policy",
            entity_name="西安市城六区",
            field="中招政策摘要",
            scope={"stage": "高中招生录取"},
            value={
                "summary": (
                    f"城六区普通高中控制线 {policy['citySixControlLine']} 分；"
                    f"志愿填报时间 {policy['citySixApplicationDates']}；"
                    f"{policy['directionalRule']}；{policy['secondBatchRule']}。"
                )
            },
            evidence_id=policy_evidence.id,
            confidence="official",
        ))
        facts.append(await create_fact(
            session,
            fact_type="admission",
            entity_name="西安市城六区",
            field="普通高中控制线",
            scope={"batch": "普通高中"},
            value={"score": policy["citySixControlLine"], "unit": "分"},
            evidence_id=policy_evidence.id,
            confidence="official",
        ))

        schools_by_id = {school["id"]: school for school in legacy_data["SCHOOL_DATA"]}
        for school in schools_by_id.values():
            facts.append(await create_fact(
                session,
                fact_type="school",
                entity_name=school["name"],
                field="学校档案",
                scope={"school_code": school.get("code"), "campus": school.get("campus")},
                value={
                    "school_stage": "senior",
                    "short_name": school.get("shortName"),
                    "batch": school.get("batch"),
                    "level": school.get("level"),
                    "ownership": school.get("ownership"),
                    "district": school.get("district"),
                    "tags": school.get("tags", []),
                    "historical_admission_lines": school.get("lines", {}),
                },
                evidence_id=school_evidence.id,
                confidence="verified",
            ))

        for junior_school in legacy_data["TARGET_QUOTA_DATA"]["schools"]:
            facts.append(await create_fact(
                session,
                fact_type="school",
                entity_name=junior_school["name"],
                field="学校档案",
                scope={"district": junior_school.get("district")},
                value={
                    "school_stage": "junior",
                    "district": junior_school.get("district"),
                    "directional_quota_total": junior_school.get("totalQuota"),
                    "source_year": legacy_data["TARGET_QUOTA_DATA"]["year"],
                },
                evidence_id=junior_school_evidence.id,
                confidence="official",
            ))

        for school_id, estimate in legacy_data["PUBLIC_2026_ESTIMATES"].items():
            school = schools_by_id.get(school_id)
            if not school:
                continue
            lower, upper = estimate["range"]
            facts.append(await create_fact(
                session,
                fact_type="admission",
                entity_name=school["name"],
                field="录取参考线",
                scope={"kind": "公开预测", "range": [lower, upper]},
                value={
                    "score": (lower + upper) / 2,
                    "range": [lower, upper],
                    "source": f"{estimate.get('source', '公开预测')}，非官方录取线",
                },
                evidence_id=estimate_evidence.id,
                confidence="observation",
            ))

        for record in legacy_data["SCHOOL_ADMISSION_PLAN_COMPARISON_DATA"]["records"]:
            plan = record.get("plan2026")
            if not plan:
                continue
            facts.append(await create_fact(
                session,
                fact_type="admission",
                entity_name=record["name"],
                field="招生计划",
                scope={"district": record.get("district"), "ownership": record.get("ownership")},
                value={"plan": plan, "previous_year_plan": record.get("plan2025")},
                evidence_id=plan_evidence.id,
                confidence="official",
            ))

        release = DataRelease(
            name=RELEASE_NAME,
            region=REGION,
            reference_year=YEAR,
            notes="从旧志愿预测系统导入的测试数据。来源与可信度已区分，非官方数据仅作参考。",
            published_by="legacy-import",
        )
        session.add(release)
        await session.flush()
        session.add_all([DataReleaseItem(release_id=release.id, fact_id=fact.id) for fact in facts])
        await session.commit()
        return {"sources": 4, "evidence": 6, "facts": len(facts), "release_id": release.id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="旧志愿预测系统的 schools-data.js 路径")
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"找不到数据文件：{args.source}")
    print(json.dumps(asyncio.run(import_data(load_legacy_data(args.source))), ensure_ascii=False))


if __name__ == "__main__":
    main()
