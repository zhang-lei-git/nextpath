"""Offline-only validation of a pre-exam score bridge against a later rank curve.

The comparison curve is evaluation data. It must never be loaded by the production
prediction path for an examination dated before that curve became available.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.position_engine import PositionEngine
from app.services.scoring_scheme import ScoreBridgeModel


NODE_EXTRACTOR = r"""
const fs = require('fs'); const vm = require('vm');
let source = fs.readFileSync(process.argv[1], 'utf8').replace(/^const\s+([A-Za-z0-9_]+)\s*=/gm, 'globalThis.$1 =');
const context = {}; vm.createContext(context); vm.runInContext(source, context);
console.log(JSON.stringify({historical: context.LEGACY_RANK_REFERENCE_DATA, actual: context.RANK_REFERENCE_DATA}));
"""


def load_data(path: Path) -> dict:
    result = subprocess.run(["node", "-e", NODE_EXTRACTOR, str(path)], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def percentile_metrics(rows: list[dict], lower: int, upper: int) -> dict:
    selected = [row for row in rows if lower <= row["score"] <= upper]
    errors = [row["predicted_percentile"] - row["actual_percentile"] for row in selected]
    return {
        "samples": len(selected),
        "mae_percentage_points": round(mean([abs(value) for value in errors]), 2),
        "bias_percentage_points": round(mean(errors), 2),
    }


def run(data: dict) -> dict:
    historical = data["historical"]
    actual = data["actual"]
    historical_points = tuple((float(item["score"]), int(item["rank"])) for item in historical["points"])
    engine = PositionEngine(historical_points)
    bridge = ScoreBridgeModel()
    rows = []
    for point in actual["points"]:
        converted = bridge.bridge((point["score"], point["score"]), 2026, 2025)
        predicted_rank = engine.estimate(converted.target_equivalent_range[0]).rank if converted else None
        if predicted_rank is None:
            continue
        rows.append({
            "score": point["score"],
            "predicted_percentile": predicted_rank / historical["totalRankBase"] * 100,
            "actual_percentile": point["rank"] / actual["totalRankBase"] * 100,
        })
    errors = [row["predicted_percentile"] - row["actual_percentile"] for row in rows]
    warnings = []
    historical_max_rank = max(item["rank"] for item in historical["points"])
    if historical["totalRankBase"] < historical_max_rank:
        warnings.append("2025 totalRankBase 小于曲线最大累计位次，分母口径存在不一致。")
    if "待核验" in actual.get("sourceTitle", "") or "网传" in actual.get("sourceTitle", ""):
        warnings.append("2026 对照曲线为网传待核验数据，只能用于内部诊断。")
    return {
        "model_version": bridge.version,
        "training_cutoff": "2025-12-31",
        "evaluation_only_year": 2026,
        "evaluation_source": actual.get("sourceTitle"),
        "samples": len(rows),
        "score_coverage": [min(row["score"] for row in rows), max(row["score"] for row in rows)],
        "mae_percentage_points": round(mean([abs(value) for value in errors]), 2),
        "bias_percentage_points": round(mean(errors), 2),
        "segments": {
            "620_plus": percentile_metrics(rows, 620, 1000),
            "590_619": percentile_metrics(rows, 590, 619),
            "560_589": percentile_metrics(rows, 560, 589),
            "530_559": percentile_metrics(rows, 530, 559),
            "below_530": percentile_metrics(rows, 0, 529),
        },
        "data_quality_warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(load_data(args.source)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
