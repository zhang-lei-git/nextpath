"""Compare immutable predictions with independently sourced school outcomes.

Candidate evidence produces provisional differences only. Only reviewed, fully
aligned score/rank observations contribute to formal metrics.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.curve_calibration import metrics


def compare(baseline, outcomes):
    rows=[]
    for prediction in baseline['schools']:
        matches=[item for item in outcomes if item['school']==prediction['school']]
        record=dict(prediction)
        if len(matches)!=1:
            record['validation_status']='missing_actual' if not matches else 'ambiguous_actual'
            rows.append(record);continue
        actual=matches[0]
        aligned=all(actual.get(k)==prediction.get(k) and actual.get(k) is not None
                    for k in ('campus','batch','school_code','admission_type'))
        reviewed=(actual.get('review_status')=='approved' and actual.get('evidence_kind')=='actual_admission'
                  and actual.get('source_url') and actual.get('published_on')
                  and actual.get('year')==baseline['target_year'] and actual.get('region')==baseline['region'])
        eligible=bool(reviewed and aligned and not baseline.get('input_quality'))
        record['validation_status']='verified_aligned' if eligible else 'provisional_not_scored'
        record['actual_candidate']=actual
        for field in ('score','rank'):
            predicted=prediction.get('predicted_'+field)
            observed=actual.get(field)
            difference=predicted-observed if isinstance(predicted,(int,float)) and isinstance(observed,(int,float)) else None
            record['provisional_'+field+'_error']=round(difference,2) if difference is not None else None
            # A curve-inferred rank is not an independently observed rank.
            rank_ok=field!='rank' or actual.get('rank_kind')=='observed'
            record[field+'_error']=difference if eligible and rank_ok else None
        rows.append(record)
    return dict(baseline_sha256=baseline.get('snapshot_sha256'),schools=rows,
                formal_score_metrics=metrics(rows,'score_error'),formal_rank_metrics=metrics(rows,'rank_error'),
                warning='候选摘要、未审核数据、校区批次未对齐或基线数据质量不合格时，只列差值，不计入正式指标。')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--outcomes',required=True);args=p.parse_args()
    print(json.dumps(compare(json.loads(Path(args.baseline).read_text()),json.loads(Path(args.outcomes).read_text())),ensure_ascii=False,indent=2))
