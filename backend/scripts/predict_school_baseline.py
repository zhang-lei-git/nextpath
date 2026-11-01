"""Freeze existing 2026 algorithm outputs using only published historical inputs.

This reproduces the deployed baseline even when input quality is inadequate;
every row is marked diagnostic. No fitted 2026 anchors are used.
"""
import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.annual_distribution import AnnualDistributionModel
from app.services.school_boundary import SchoolAdmissionObservation, SchoolBoundaryModel
from app.services.position_engine import PositionEngine
from app.services.curve_calibration import validate_curve
from app.services.analysis_model_service import DEFAULT_ANNUAL_DISTRIBUTION_PARAMETERS, DEFAULT_SCHOOL_BOUNDARY_PARAMETERS


def run(db, cutoff='2026-06-19'):
    release=db.execute('''select id,name,reference_year,published_at from data_releases
        where region='西安' and reference_year<2026 and environment='production'
        and data_purpose='forecast' and usable_for_prediction=1 and published_at<=?
        order by reference_year desc,published_at desc limit 1''',(cutoff+' 23:59:59',)).fetchone()
    # Database imports occurred after the exam. This fallback is explicitly a
    # retrospective reconstruction, not a claim the release existed beforehand.
    retrospective=False
    if not release:
        retrospective=True
        release=db.execute('''select id,name,reference_year,published_at from data_releases
        where region='西安' and reference_year<2026 and environment='production'
        and data_purpose='forecast' and usable_for_prediction=1
        order by reference_year desc,published_at desc limit 1''').fetchone()
    if not release: raise ValueError('No historical release')
    facts=[]
    for row in db.execute('''select f.id,f.entity_name,f.field,f.value,f.scope from data_facts f
        join data_release_items i on i.fact_id=f.id where i.release_id=?''',(release[0],)):
        facts.append(dict(id=row[0],school=row[1],field=row[2],value=json.loads(row[3]),scope=json.loads(row[4])))
    curve_fact=next(f for f in facts if f['field']=='一分一段参考点')
    value=curve_fact['value'];points=tuple(tuple(p) for p in value['points']);base=value['candidate_count']
    parameters={}
    for kind,default in [('annual_distribution',DEFAULT_ANNUAL_DISTRIBUTION_PARAMETERS),('school_boundary',DEFAULT_SCHOOL_BOUNDARY_PARAMETERS)]:
        row=db.execute('select version,parameters from analysis_model_versions where analysis_type=? and status=? order by created_at desc limit 1',(kind,'active')).fetchone()
        parameters[kind]=dict(version=row[0] if row else 'default',values={**default,**(json.loads(row[1]) if row else {})})
    curve=AnnualDistributionModel(parameters['annual_distribution']['values']).project(
        region='西安城六区',target_year=2026,reference_year=release[2],historical_points=points,
        historical_full_mark=value['max_score'],historical_candidate_count=base,target_full_mark=640)
    engine=PositionEngine(points)
    boundary_model=SchoolBoundaryModel(parameters['school_boundary']['values'])
    rows=[]
    for fact in facts:
        if fact['field']!='录取参考线': continue
        historical_rank=engine.estimate(float(fact['value']['score'])).rank
        if not historical_rank:
            rows.append(dict(school=fact['school'],status='outside_historical_curve'));continue
        boundary=boundary_model.estimate(fact['school'],(SchoolAdmissionObservation(
            fact['school'],release[2],historical_rank,base,batch=fact['scope'].get('batch')),),curve.candidate_count)
        center=sum(boundary.rank_range)/2
        center_score=curve.score_for_percentile(center/curve.candidate_count*100)
        score_range=curve.score_range_for_percentiles(boundary.percentile_range)
        rows.append(dict(school=fact['school'],batch=fact['scope'].get('batch'),campus=fact['scope'].get('campus'),
            historical_fact_id=fact['id'],historical_score=fact['value']['score'],historical_rank=historical_rank,
            predicted_rank=round(center),predicted_rank_range=boundary.rank_range,
            predicted_score=center_score,predicted_score_range=score_range,
            actual_score=None,actual_rank=None,validation_status='pending_verified_actual',
            status='diagnostic_input_quality_failed',source=fact['value'].get('source')))
    payload=dict(target_year=2026,region='西安城六区',cutoff=cutoff,historical_release=release[1],
        release_published_at=release[3],retrospective_reconstruction=retrospective,
        warning='仅复现现行模型；历史库分母有矛盾，不具备发布资格。导入时间晚于中考，无法声称严格考前数据快照。排名为曲线插值估计，不是官方学校录取排名。',
        input_quality=validate_curve(points,value['max_score'],base),parameters=parameters,schools=rows)
    payload['snapshot_sha256']=hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--database',required=True);args=parser.parse_args()
    with sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True) as db:
        print(json.dumps(run(db),ensure_ascii=False,indent=2))
