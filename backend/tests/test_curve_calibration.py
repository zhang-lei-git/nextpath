import pytest

from app.services.curve_calibration import fit_holdout, interpolate, validate_curve


def test_calibration_keeps_holdout_disjoint_and_preserves_monotonicity():
    points = tuple((float(score), 100 + (640-score)**2) for score in range(630, 519, -1))
    model, holdout = fit_holdout(points, target_year=2026, release_id='test-only', stride=10)
    assert not set(model.anchors) & set(holdout)
    assert len(model.anchors) + len(holdout) == len(points)
    ranks = [model.estimate(float(score)) for score in range(630, 519, -1)]
    assert all(left < right for left, right in zip(ranks, ranks[1:]))
    assert model.estimate(631) is None
    assert model.estimate(519) is None


def test_bad_population_metadata_is_flagged_and_missing_base_not_invented():
    points = ((600., 10), (500., 50440))
    assert any('小于' in warning for warning in validate_curve(points,640,49900))
    assert any('缺少' in warning for warning in validate_curve(points,640,None))
    assert interpolate(points,550) == 25225
    with pytest.raises(ValueError):
        fit_holdout(((600.,100),(500.,50)),target_year=2026,release_id='bad')


def test_school_predictions_are_excluded_from_actual_admission_validation():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('offline_backtest',Path(__file__).parents[1]/'scripts/backtest_db_releases.py')
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    import sqlite3,json
    db=sqlite3.connect(':memory:')
    db.executescript('''create table data_releases(id text,name text,reference_year integer,environment text,data_purpose text,region text,published_at text);
        create table data_facts(id text,entity_name text,field text,value text,scope text,confidence text,fact_type text);
        create table data_release_items(release_id text,fact_id text);''')
    for year,env,purpose in [(2025,'production','forecast'),(2026,'test','demo_or_backtest')]:
        rid=str(year)
        db.execute('insert into data_releases values(?,?,?,?,?,?,?)',(rid,rid,year,env,purpose,'西安','2026-01-01'))
        value={'points':[[630,10],[600,500],[570,2000],[540,6000]],'max_score':640,'source':'测试曲线'}
        db.execute('insert into data_facts values(?,?,?,?,?,?,?)',(rid,'区域','一分一段参考点',json.dumps(value),'{}','observation','admission'))
        db.execute('insert into data_release_items values(?,?)',(rid,rid))
    db.execute('insert into data_facts values(?,?,?,?,?,?,?)',('school','测试学校','录取参考线',json.dumps({'score':570,'source':'考前预测'}),json.dumps({'kind':'公开预测'}),'observation','admission'))
    db.execute('insert into data_release_items values(?,?)',('2026','school'))
    result=script.run(db,stride=2)
    assert result['status']=='experimental_not_eligible_for_production'
    assert result['school_boundary_validation']['verified_actual_outcomes']==0
    assert len(result['school_boundary_validation']['excluded_predictions'])==1
    assert result['school_boundary_validation']['status']=='blocked_missing_actual_admission_outcomes'
