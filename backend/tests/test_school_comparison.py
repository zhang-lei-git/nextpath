import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('compare_outcomes',Path(__file__).parents[1]/'scripts/compare_school_outcomes.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_pending_evidence_and_curve_derived_ranks_are_not_scored_as_actual():
    prediction=dict(school='测试高中',predicted_score=600,predicted_rank=2000,
                    campus='本部',batch='一批',school_code='001',admission_type='统招')
    baseline=dict(target_year=2026,region='西安城六区',input_quality=[],schools=[prediction])
    actual=dict(school='测试高中',score=605,rank=2500,year=2026,region='西安城六区',
                campus='本部',batch='一批',school_code='001',admission_type='统招',
                review_status='pending',evidence_kind='actual_admission',source_url='https://school.example/notice',published_on='2026-08-01')
    assert module.compare(baseline,[actual])['formal_score_metrics']['samples']==0
    actual.update(review_status='approved',rank_kind='curve_interpolated')
    result=module.compare(baseline,[actual])
    assert result['formal_score_metrics']['mae']==5
    assert result['formal_rank_metrics']['samples']==0
    actual['rank_kind']='observed'
    assert module.compare(baseline,[actual])['formal_rank_metrics']['mae']==500
    baseline['input_quality']=['invalid denominator']
    assert module.compare(baseline,[actual])['formal_score_metrics']['samples']==0
