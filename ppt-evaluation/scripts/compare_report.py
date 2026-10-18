"""Render an explicit score comparison from existing results; never call a model."""
import argparse, html, json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
LEVELS = {'object': '页内细节', 'slide': '单页表达', 'deck': '整稿'}

def comparison_data(entries):
    if len(entries) < 2:
        raise ValueError('At least two results are required for comparison')
    baseline = None
    decks = []
    for entry in entries:
        result = entry['result']; levels = result['scores']['levels']
        signature = (result.get('rubric_version'),result['scores'].get('policy','audit@0.2.0'), tuple((level, tuple((r['rule_id'],r['weight']) for r in levels[level]['rules'])) for level in LEVELS))
        if baseline is not None and signature != baseline:
            raise ValueError('Compare results with the same rubric and rule set')
        baseline = signature
        report = str(entry['report']); url = urlsplit(report)
        if url.scheme not in {'', 'http', 'https'} or url.netloc and not url.scheme:
            raise ValueError('Use a local relative report path or an HTTP(S) report')
        decks.append({'id':entry.get('id',str(len(decks))), 'evaluationFailed':bool(result.get('delivery',{}).get('evaluation_failures')), 'label': str(entry['label']), 'report': report,
                      'page_count': len(result['manifest']['pages']),
                      'layers': levels, 'mappingVerified': result['manifest'].get('page_mapping_status') == 'EXPLICIT_SOURCE_PAGE_MAP' or bool(result.get('context', {}).get('page_mapping_reviewed'))})
    contexts = [e['result'].get('context', {}) for e in entries]
    same_task = all(contexts[0].get('query') and c.get('query') == contexts[0]['query'] and c.get('mode') == contexts[0].get('mode') and c.get('facts') == contexts[0].get('facts') for c in contexts)
    return {'decks': decks, 'same_task': same_task}

def render_comparison(entries, out, title='PPT评测 · 对比分析', insights=None):
    from insight_report import render_insights, total_score
    data=comparison_data(entries);h=html.escape;initial=[total_score(e['result']) for e in entries]
    fmt=lambda x:'—'if x is None else f'{x:.1f}'
    winner=[] if any(x is None for x in initial) else [n for n,x in enumerate(initial) if x==max(initial)]
    verdict='本轮评测未完成，暂不比较作品'if not winner else ('本轮综合评分并列'if len(winner)>1 else '本轮胜出：'+data['decks'][winner[0]]['label'])
    parts=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+h(title)+'</title><style>'+(ROOT/'assets/reader-report.css').read_text()+(ROOT/'assets/comparison-report.css').read_text()+'</style><nav class="compare-nav" aria-label="报告切换"><b>PPT评测</b><button type="button" data-view="overview" aria-pressed="true">对比分析</button>']
    for n,d in enumerate(data['decks']):parts.append('<button type="button" data-view="'+str(n)+'" aria-pressed="false">'+h(d['label'])+'</button>')
    parts.append('</nav><main id="comparison"><header><p class="eyebrow">PRESENTATION REVIEW</p><h1>'+h(title)+'</h1></header><section class="verdict"><h2 data-verdict>'+h(verdict)+'</h2>')
    if insights:parts.append('<p class="verdict-reason" data-baseline-insight>'+h(insights['headline']['reason'])+'</p>')
    if len(entries)>2: parts.append('<p class="scope">多份总览：逐一说明各厂商的亮点、主要问题和下一步改法。</p>')
    parts.append('<p class="scope" data-custom-verdict hidden>已按自定义权重重算推荐者；下方页面观察与修改建议不变。</p></section><section class="comparison-scores" aria-label="综合评分对比">')
    for n,d in enumerate(data['decks']):parts.append('<article><h2>'+h(d['label'])+'<small>'+str(d['page_count'])+'页</small></h2><p class="score-caption">综合评分 /100</p><strong data-composite="'+str(n)+'">'+fmt(initial[n])+'</strong><button type="button" class="control" data-view="'+str(n)+'">查看原页与问题 →</button></article>')
    parts.append('</section><section class="section"><h2>三个视角，各自好在哪里</h2><div class="table-wrap"><table class="comparison-table"><thead><tr><th>评分视角</th>')
    parts.extend('<th>'+h(d['label'])+'</th>' for d in data['decks']);parts.append('</tr></thead><tbody>')
    for lev,label in LEVELS.items():
        parts.append('<tr><th><a href="#insight-'+lev+'">'+label+'</a></th>')
        for n in range(len(data['decks'])):parts.append('<td><b data-score="'+str(n)+'-'+lev+'">'+fmt(data['decks'][n]['layers'][lev]['observed_score'])+'</b><span class="score-track" aria-hidden="true"><i data-bar="'+str(n)+'-'+lev+'"></i></span></td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div></section>')
    if insights:parts.append(render_insights(insights,entries,Path(out).parent/'report-assets'))
    else:parts.append('<p class="scope">尚未生成图文分析。可先查看各份原页与问题。</p>')
    parts.append('<section class="section"><details class="weights"><summary>调整评分权重与计分口径</summary><p class="scope">三视角默认等权，层内各维度默认等权。必要证据或讲稿不足按40分计入；同一根因只扣一次，技术故障不扣作品分。权重同时应用于全部参评PPT，修改权重不重新调用模型。</p><div class="layer-controls">')
    for lev,label in LEVELS.items():parts.append('<label>'+label+'<input type="number" min="0" max="100" step="0.1" value="1" data-compare-layer="'+lev+'" aria-label="对比'+label+'权重"></label>')
    parts.append('</div><details><summary>细调各维度权重</summary><div class="table-wrap"><table><thead><tr><th>维度</th><th>相对权重</th></tr></thead><tbody>')
    for lev in LEVELS:
        for r in data['decks'][0]['layers'][lev]['rules']:parts.append('<tr><td>'+h(r['name'])+'</td><td><input type="number" min="0" max="100" step="0.1" value="'+str(r['weight'])+'" data-compare-rule="'+h(r['rule_id'])+'" aria-label="对比'+h(r['name'])+'权重"></td></tr>')
    parts.append('</tbody></table></div></details><div class="controls"><button type="button" class="control" id="reset-comparison">恢复默认</button></div><p class="scope" data-comparison-scope></p><p class="error" data-comparison-error role="status"></p></details></section></main>')
    for n,d in enumerate(data['decks']):parts.append('<iframe hidden class="detail-report" id="detail-'+str(n)+'" title="'+h(d['label'],quote=True)+'详细报告" data-src="'+h(d['report'],quote=True)+'"></iframe>')
    parts.append('<script type="application/json" id="comparison-data">'+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+'</script><script>'+(ROOT/'assets/score-explorer.js').read_text()+'</script><script>'+(ROOT/'assets/comparison-report.js').read_text()+'</script></html>')
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(parts));return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('entries', help='JSON list of {label, result_file, report}'); ap.add_argument('--out', required=True); ap.add_argument('--insights'); ap.add_argument('--title', default='PPT评测 · 分数对比'); args = ap.parse_args()
    entries = json.loads(Path(args.entries).read_text())
    for entry in entries: entry['result'] = json.loads(Path(entry['result_file']).read_text())
    insights=json.loads(Path(args.insights).read_text())if args.insights else None
    print(render_comparison(entries,args.out,args.title,insights))
