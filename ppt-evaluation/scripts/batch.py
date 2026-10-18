#!/usr/bin/env python3
"""Run an explicit collection with bounded calls and separate coverage reports."""
import argparse, html, json, subprocess, sys
from pathlib import Path

def validate_jobs(jobs):
    if not isinstance(jobs,list) or not jobs: raise ValueError('A nonempty job list is required')
    ids=[]
    for job in jobs:
        ident=job.get('id','')
        if not isinstance(ident,str) or not ident or not all(c.isalnum() or c in '_-' for c in ident): raise ValueError('Unsafe job id')
        if not job.get('manifest'): raise ValueError('Each job needs a manifest')
        ids.append(ident)
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate job ID')
    return jobs

def main():
    ap=argparse.ArgumentParser();ap.add_argument('jobs',help='JSON list of {id, manifest, context}; non-secret paths only');ap.add_argument('--out',required=True);ap.add_argument('--max-calls-per-deck',type=int,default=12);ap.add_argument('--model',default='deepseek-flash');a=ap.parse_args()
    jobs=validate_jobs(json.loads(Path(a.jobs).read_text()));root=Path(a.out).resolve()
    if root.exists() and any(root.iterdir()): raise ValueError('Choose an empty batch output directory')
    if a.max_calls_per_deck<1: raise ValueError('Positive call budget required')
    root.mkdir(parents=True,exist_ok=True);entries=[]
    for job in jobs:
        ident=job['id'];dest=root/ident
        cmd=[sys.executable,str(Path(__file__).with_name('evaluate.py')),'--manifest',job['manifest'],'--out',str(dest),'--model',a.model,'--max-calls',str(a.max_calls_per_deck)]
        if job.get('context'):cmd+=['--context',job['context']]
        status=subprocess.run(cmd).returncode;f=dest/'result.json';result=json.loads(f.read_text())if status==0 and f.exists()else None
        entries.append({'id':ident,'status':'RESULT_WITH_COVERAGE'if result else'ERROR','scores':result['scores']['levels']if result else None,'report':f'{ident}/report.html'if result else None,'source_pages_missing':result.get('source_pages_missing')if result else None,'review_status':result.get('review',{}).get('status')if result else None,'process':result.get('process')if result else None})
    (root/'batch.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2));rows=[]
    for e in entries:
        scores=e['scores']or{};cells=''.join('<td>'+str(scores.get(level,{}).get('observed_score'))+' / '+str(round(scores.get(level,{}).get('coverage',0)*100,1))+'%</td>'for level in ['object','slide','deck'])
        rows.append('<tr><td>'+html.escape(e['id'])+'</td><td>'+html.escape(str(e['status'])+' / '+str(e['review_status']))+'</td>'+cells+'<td>'+('<a href="'+e['report']+'">完整报告</a>'if e['report']else'无有效结果')+'</td></tr>')
    (root/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PPT批量评测</title><style>body{font:16px/1.8 system-ui;max-width:1100px;margin:40px auto}td,th{padding:14px;border-bottom:1px solid #ccc;text-align:left}</style><h1>PPT批量评测</h1><p>每项为观察分/判项覆盖率；未经人工标定。请核对同题、同适用项和同渲染协议后比较。缺项不等于通过，不自动排名。</p><table><tr><th>产物</th><th>运行/复核状态</th><th>页内细节</th><th>单页表达</th><th>整稿</th><th>证据</th></tr>'+''.join(rows)+'</table></html>');print(root/'index.html')
if __name__=='__main__':main()
