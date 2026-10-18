#!/usr/bin/env python3
"""Review a page-based result without altering its raw baseline or leaving stale summaries."""
import argparse, copy, hashlib, json
from pathlib import Path
from protocol import apply_decisions, deduplicate
from report import refresh, render

def review_result(baseline, decisions, reviewer, rules):
    result=copy.deepcopy(baseline)
    if result.get('schema_version')!='ppt-evaluation-result@0.2.0': raise ValueError('Use the original reviewer for legacy v0.1 results')
    rows,errors=apply_decisions(result['assessments'],decisions)
    if errors: raise ValueError('Invalid review decisions: '+json.dumps(errors,ensure_ascii=False))
    result['assessments'],merges=deduplicate(rows)
    result['review_history']=copy.deepcopy(result.get('review_history',[]))+[result.get('review',{})]
    result['review']={'status':'EXPLICIT_REVIEW_APPLIED','reviewer':reviewer,'decisions':decisions,'canonical_merges':merges,'warning':'Removed defects do not imply GOOD; Agent review is not human calibration'}
    return refresh(result,rules)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('result'); ap.add_argument('decisions'); ap.add_argument('--reviewer',required=True); ap.add_argument('--out',required=True); a=ap.parse_args()
    source=Path(a.result); rules=json.loads((Path(__file__).resolve().parents[1]/'references/rubric.json').read_text())['rules']
    d=review_result(json.loads(source.read_text()),json.loads(Path(a.decisions).read_text()),a.reviewer,rules); d['review']['baseline_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    if (out/'result.json').exists(): raise ValueError('Use a fresh review directory')
    render(d,out/'report.html'); (out/'result.json').write_text(json.dumps(d,ensure_ascii=False,indent=2)); print(out/'report.html')
if __name__=='__main__': main()
