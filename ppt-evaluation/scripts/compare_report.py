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
        signature = (result.get('rubric_version'), tuple((level, tuple((r['rule_id'],r['weight']) for r in levels[level]['rules'])) for level in LEVELS))
        if baseline is not None and signature != baseline:
            raise ValueError('Compare results with the same rubric and rule set')
        baseline = signature
        report = str(entry['report']); url = urlsplit(report)
        if url.scheme not in {'', 'http', 'https'} or url.netloc and not url.scheme:
            raise ValueError('Use a local relative report path or an HTTP(S) report')
        decks.append({'label': str(entry['label']), 'report': report,
                      'page_count': len(result['manifest']['pages']),
                      'layers': levels, 'mappingVerified': result['manifest'].get('page_mapping_status') == 'EXPLICIT_SOURCE_PAGE_MAP' or bool(result.get('context', {}).get('page_mapping_reviewed'))})
    contexts = [e['result'].get('context', {}) for e in entries]
    same_task = all(contexts[0].get('query') and c.get('query') == contexts[0]['query'] and c.get('mode') == contexts[0].get('mode') and c.get('facts') == contexts[0].get('facts') for c in contexts)
    return {'decks': decks, 'same_task': same_task}

def render_comparison(entries, out, title='PPT评测 · 分数对比'):
    data = comparison_data(entries); h = html.escape
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+h(title)+'</title><style>'+(ROOT/'assets/reader-report.css').read_text()+(ROOT/'assets/comparison-report.css').read_text()+'</style>',
             '<nav class="compare-nav" aria-label="报告切换"><b>PPT评测</b><button type="button" data-view="overview" aria-pressed="true">分数对比</button>']
    for n, d in enumerate(data['decks']):
        parts.append('<button type="button" data-view="'+str(n)+'" aria-pressed="false">'+h(d['label'])+'</button>')
    initial=[]
    for d in data['decks']:
        vals=[d['layers'][lev]['observed_score'] for lev in LEVELS]
        initial.append({'score':round(sum(vals)/len(vals),1) if all(v is not None for v in vals) else None,'coverage':sum(d['layers'][lev]['coverage'] for lev in LEVELS)/len(LEVELS)})
    fmt=lambda x:'—' if x is None else f'{x:.1f}'
    pct=lambda x:'—' if x is None else f'{x:.1%}'
    parts.append('</nav><main id="comparison"><header><p class="eyebrow">PRESENTATION COMPARISON</p><h1>'+h(title)+'</h1><p class="subtitle">'+('同题、同核对资料、同量表，使用下方同一组权重。' if data['same_task'] else '量表相同，任务或核对资料存在差异；请先确认比较范围。')+'</p></header><section class="comparison-scores" aria-label="综合观察分对比">')
    for n, d in enumerate(data['decks']):
        parts.append('<article><h2>'+h(d['label'])+'<small>'+str(d['page_count'])+'页</small></h2><p class="score-caption">综合观察分 /100</p><strong data-composite="'+str(n)+'">'+fmt(initial[n]['score'])+'</strong><p class="scope">已评覆盖 <span data-coverage="'+str(n)+'">'+pct(initial[n]['coverage'])+'</span></p><button type="button" class="control" data-view="'+str(n)+'">查看原页与问题 →</button></article>')
    parts.append('</section><p class="comparison-gap" data-comparison-gap aria-live="polite"></p><p class="scope">按各自已评范围汇总，待核验项不补分；覆盖范围不同，分差只作本轮观察。未经过人工标定。</p><section class="section"><h2>分项分数对照</h2><div class="table-wrap"><table class="comparison-table"><thead><tr><th>评分视角</th>')
    parts.extend('<th>'+h(d['label'])+'</th>' for d in data['decks'])
    if len(data['decks']) == 2: parts.append('<th>差值<small>第一份 − 第二份</small></th>')
    parts.append('</tr></thead><tbody>')
    for lev, label in LEVELS.items():
        parts.append('<tr><th>'+label+'</th>')
        for n in range(len(data['decks'])):
            parts.append('<td><b data-score="'+str(n)+'-'+lev+'">'+fmt(data['decks'][n]['layers'][lev]['observed_score'])+'</b><span class="score-track" aria-hidden="true"><i data-bar="'+str(n)+'-'+lev+'"></i></span><small>覆盖 <span data-cell-coverage="'+str(n)+'-'+lev+'">'+pct(data['decks'][n]['layers'][lev]['coverage'])+'</span></small></td>')
        if len(data['decks']) == 2: parts.append('<td data-gap="'+lev+'">—</td>')
        parts.append('</tr>')
    parts.append('</tbody></table></div></section><section class="section"><details class="weights"><summary>统一调整对比权重</summary><p class="scope">默认三视角等权、每个视角内各维度等权。这里的权重同时用于所有参评PPT，仅改变对比页试算；单份报告可独立查看自己的评分与权重。</p><div class="layer-controls">')
    for lev, label in LEVELS.items():
        parts.append('<label>'+label+'<input type="number" min="0" max="100" step="0.1" value="1" data-compare-layer="'+lev+'" aria-label="对比'+label+'权重"></label>')
    parts.append('</div><details><summary>细调各维度权重</summary><div class="table-wrap"><table><thead><tr><th>维度</th><th>相对权重</th></tr></thead><tbody>')
    for lev in LEVELS:
        for rule in data['decks'][0]['layers'][lev]['rules']:
            parts.append('<tr><td>'+h(rule['name'])+'</td><td><input type="number" min="0" max="100" step="0.1" value="'+str(rule['weight'])+'" data-compare-rule="'+h(rule['rule_id'])+'" aria-label="对比'+h(rule['name'])+'权重"></td></tr>')
    parts.append('</tbody></table></div></details><div class="controls"><button type="button" class="control" id="reset-comparison">恢复默认</button></div><p class="scope" data-comparison-scope></p><p class="error" data-comparison-error role="status"></p></details></section></main>')
    for n, d in enumerate(data['decks']):
        parts.append('<iframe hidden class="detail-report" id="detail-'+str(n)+'" title="'+h(d['label'], quote=True)+'详细报告" data-src="'+h(d['report'], quote=True)+'"></iframe>')
    parts.append('<script type="application/json" id="comparison-data">'+json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')+'</script><script>'+(ROOT/'assets/score-explorer.js').read_text()+'</script><script>'+(ROOT/'assets/comparison-report.js').read_text()+'</script></html>')
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True); out.write_text(''.join(parts)); return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('entries', help='JSON list of {label, result_file, report}'); ap.add_argument('--out', required=True); ap.add_argument('--title', default='PPT评测 · 分数对比'); args = ap.parse_args()
    entries = json.loads(Path(args.entries).read_text())
    for entry in entries: entry['result'] = json.loads(Path(entry['result_file']).read_text())
    print(render_comparison(entries, args.out, args.title))
