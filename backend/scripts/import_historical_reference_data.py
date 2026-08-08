"""Import only pre-exam reference data from the legacy planning prototype.

This intentionally excludes every 2026 rank table, control line and admission estimate.
It makes the 2025 curve and the 2025 school admission references available to the
pre-exam engine as an auditable historical release.
"""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.domain.models import Base, DataEvidence, DataFact, DataRelease, DataReleaseItem, DataSource


REGION = "西安"
YEAR = 2025
RELEASE_NAME = "2025 西安城六区历史升学参考数据（旧系统迁移 v1）"
NODE_EXTRACTOR = r"""
const fs = require('fs'); const vm = require('vm');
let source = fs.readFileSync(process.argv[1], 'utf8').replace(/^const\s+([A-Za-z0-9_]+)\s*=/gm, 'globalThis.$1 =');
const context = {}; vm.createContext(context); vm.runInContext(source, context);
console.log(JSON.stringify({legacy: context.LEGACY_RANK_REFERENCE_DATA, schools: context.SCHOOL_DATA, links: context.SOURCE_LINKS}));
"""


def load_data(path: Path) -> dict:
    result = subprocess.run(["node", "-e", NODE_EXTRACTOR, str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


async def import_data(data: dict) -> dict[str, int | str]:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        existing = await session.scalar(select(DataRelease).where(DataRelease.name == RELEASE_NAME).limit(1))
        if existing:
            return {"skipped": 1, "release_id": existing.id}
        source = await session.scalar(select(DataSource).where(DataSource.name == "旧版志愿预测系统结构化整理").limit(1))
        if not source:
            source = DataSource(name="旧版志愿预测系统结构化整理", source_type="manual", reliability="verified")
            session.add(source)
            await session.flush()
        legacy = data["legacy"]
        evidence = DataEvidence(
            source_id=source.id,
            title=legacy["sourceTitle"],
            excerpt="按历史年份导入。仅供中考前位置预测；学校分数线与一分一段均保留原始年份。",
            created_by="legacy-import",
        )
        session.add(evidence)
        await session.flush()

        def fact(entity_name: str, field: str, value: dict, scope: dict | None = None) -> DataFact:
            return DataFact(
                fact_type="admission", entity_name=entity_name, field=field, region=REGION, reference_year=YEAR,
                scope=scope or {}, value=value, evidence_ids=[evidence.id], confidence="verified", status="approved",
                review_note="旧志愿预测系统历史数据迁移；仅作为中考前预测参考。", created_by="legacy-import", reviewed_by="legacy-import",
            )

        rank_points = [[row["score"], row["rank"]] for row in legacy["points"]]
        facts = [fact(
            "西安市城六区", "一分一段参考点",
            {"points": rank_points, "source": legacy["sourceTitle"], "max_score": 820, "candidate_count": legacy["totalRankBase"]},
            {"year": YEAR, "verification": "旧系统结构化历史数据"},
        )]
        for school in data["schools"]:
            line = school.get("lines", {}).get(str(YEAR))
            if isinstance(line, (int, float)):
                facts.append(fact(
                    school["name"], "录取参考线",
                    {"score": line, "source": f"{YEAR} 年学校历史录取参考线（旧系统迁移）"},
                    {"year": YEAR, "batch": school.get("batch"), "kind": "历史参考"},
                ))
        session.add_all(facts)
        await session.flush()
        release = DataRelease(
            name=RELEASE_NAME, region=REGION, reference_year=YEAR,
            environment="production", data_purpose="forecast", usable_for_prediction=True,
            notes="中考前预测专用：只含 2025 年及此前可获得的历史参考，不含 2026 年出分后数据。",
            published_by="legacy-import",
        )
        session.add(release)
        await session.flush()
        session.add_all([DataReleaseItem(release_id=release.id, fact_id=item.id) for item in facts])
        await session.commit()
        return {"facts": len(facts), "release_id": release.id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"找不到数据文件：{args.source}")
    print(json.dumps(asyncio.run(import_data(load_data(args.source))), ensure_ascii=False))


if __name__ == "__main__":
    main()
