"""Read-only historical diagnostic and target-year interpolation experiment.

Run: python backend/scripts/backtest_db_releases.py --database /path/to/db
No production writes, model activation or user information exports occur.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.curve_calibration import fit_holdout, interpolate, metrics, validate_curve
from app.services.scoring_scheme import ScoreBridgeModel


def load_release(db, year, environment, purpose, region):
    release = db.execute(
        'select id,name,reference_year from data_releases where reference_year=? and environment=? and data_purpose=? and region=? order by published_at desc,id limit 1',
        (year, environment, purpose, region),
    ).fetchone()
    if not release:
        raise ValueError(f'Missing {year}/{region}/{environment}/{purpose}')
    rows = db.execute('''select f.entity_name,f.field,f.value,f.scope,f.confidence
        from data_facts f join data_release_items i on i.fact_id=f.id
        where i.release_id=? and f.fact_type='admission' ''', (release[0],)).fetchall()
    facts = [dict(entity=name, field=field, value=json.loads(value), scope=json.loads(scope), confidence=confidence)
             for name, field, value, scope, confidence in rows]
    curve = next(item for item in facts if item['field'] == '一分一段参考点')
    return dict(id=release[0], name=release[1], year=release[2], facts=facts,
                curve=curve, points=tuple((float(s), int(r)) for s, r in curve['value']['points']))


def run(db, *, region='西安', stride=10):
    history = load_release(db, 2025, 'production', 'forecast', region)
    evaluation = load_release(db, 2026, 'test', 'demo_or_backtest', region)
    quality = {}
    for label, data in [('historical', history), ('evaluation', evaluation)]:
        quality[label] = validate_curve(data['points'], data['curve']['value']['max_score'], data['curve']['value'].get('candidate_count'))
    bridge = ScoreBridgeModel()
    model, heldout = fit_holdout(evaluation['points'], target_year=2026, release_id=evaluation['id'], stride=stride)
    rows = []
    for score, reference_rank in heldout:
        converted = bridge.bridge((score, score), 2026, 2025)
        baseline = interpolate(history['points'], converted.target_equivalent_range[0])
        calibrated = model.estimate(score)
        rows.append(dict(score=score, reference_rank=reference_rank,
                         baseline_error=baseline-reference_rank if baseline is not None else None,
                         calibrated_error=calibrated-reference_rank if calibrated is not None else None))
    paired = [row for row in rows if row['baseline_error'] is not None and row['calibrated_error'] is not None]
    segments = {}
    for label, low, high in [('620+',620,1000),('590–619',590,619),('560–589',560,589),('530–559',530,559),('<530',0,529)]:
        selected = [row for row in rows if low <= row['score'] <= high]
        segments[label] = dict(baseline=metrics(selected,'baseline_error'), calibration=metrics(selected,'calibrated_error'))
    examples = []
    for score in [529.5,530,540,550,560,580]:
        converted = bridge.bridge((score,score),2026,2025)
        baseline_rank = interpolate(history['points'],converted.target_equivalent_range[0])
        examples.append(dict(score=score, baseline_rank=round(baseline_rank) if baseline_rank is not None else None,
                             reference_rank=interpolate(evaluation['points'],score), experimental_rank=model.estimate(score)))

    # School predictions and genuine admission outcomes must never share a metric.
    school_comparisons, excluded = [], []
    for item in evaluation['facts']:
        if item['field'] != '录取参考线':
            continue
        text = str(item['scope']) + str(item['value'].get('source',''))
        reason = '考前预测/未核验参考线，不是真实录取结果'
        if not any(word in text for word in ['预测','预估','待核验','非官方']) and item['confidence'] in ['official','verified'] and item['scope'].get('kind') == '实际录取':
            school_comparisons.append(item['entity'])
        else:
            excluded.append(dict(school=item['entity'],reason=reason,source=item['value'].get('source')))
    return dict(
        status='experimental_not_eligible_for_production',
        historical_release=history['name'], evaluation_release=evaluation['name'],
        data_quality=quality,
        interpretation='留出点来自同一届同一张表；误差只验证分段插值，不能证明考前预测或跨年预测准确。原始累计位次比较未按未知人数归一化。',
        calibration=dict(method='monotonic_piecewise_linear',anchor_count=len(model.anchors),holdout_count=len(heldout),
                         anchors=model.anchors,baseline=metrics(rows,'baseline_error'),holdout=metrics(rows,'calibrated_error'),
                         paired_comparison=dict(baseline=metrics(paired,'baseline_error'),calibration=metrics(paired,'calibrated_error')),
                         unscored_baseline_count=len(rows)-len(paired),segments=segments),
        examples=examples,
        school_boundary_validation=dict(status='blocked_missing_actual_admission_outcomes' if not school_comparisons else 'requires_school_campus_batch_and_population_alignment',
                                        verified_actual_outcomes=len(school_comparisons),excluded_predictions=excluded),
        release_gate=['核验2026曲线来源与完整覆盖范围','补齐2025/2026同口径全体考生人数','获取按学校校区招生代码批次区分的2026真实录取结果','跨年度时间留出验证后再审核发布'],
    )


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database',required=True)
    parser.add_argument('--region',default='西安')
    parser.add_argument('--stride',type=int,default=10)
    args=parser.parse_args()
    # URI mode=ro prevents accidental DDL/DML and refuses nonexistent paths.
    with sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        print(json.dumps(run(db,region=args.region,stride=args.stride),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
