#!/usr/bin/env python3
"""Aggregate page-scoped judgments and derive every final narrative from final rows."""
import argparse, base64, collections, copy, html, json, math, mimetypes
from pathlib import Path
from protocol import unknown
LABELS = {'object': '页内细节', 'slide': '单页表达', 'deck': '整稿'}

def canonical_rows(assessments, rules, manifest, context):
    if not manifest or manifest.get('evaluation_unit') != 'rendered_page':
        raise ValueError('This is the v0.2 page protocol; rerun legacy object-based input separately')
    pages = [p['page'] for p in manifest['pages']]
    if len(pages) != len(set(pages)): raise ValueError('Repeated source page')
    expected = {(r['id'], n): r for r in rules for n in ([None] if r['level'] == 'deck' else pages)}
    rows = {}; roots = set()
    for raw in assessments:
        row = copy.deepcopy(raw); key = (row.get('rule_id'), row.get('page'))
        if key not in expected or key in rows: raise ValueError('Duplicate or unknown page/rule target')
        if row.get('target_id') != ('deck' if key[1] is None else f'slide-{key[1]}'): raise ValueError('Wrong page target')
        if row['rule_id'] == 'D07' and not context.get('transcript'): row = unknown('D07', None, 'No supplied script')
        if row['rule_id'] == 'D01' and not context.get('query'): row = unknown('D01', None, 'No supplied Query')
        state, rating = row.get('status'), row.get('rating')
        if state in {'GOOD', 'BAD'}:
            if type(rating) is not int or not 0 <= rating <= 4 or (rating >= 3) != (state == 'GOOD') or not row.get('evidence'): raise ValueError('Invalid evidence-backed grade')
            if state == 'BAD' and not row.get('issues'): raise ValueError('Low rating without an owned defect')
        elif state not in {'UNCERTAIN', 'NOT_APPLICABLE'} or rating is not None or not row.get('reason'):
            raise ValueError('Unknown/N/A must have a reason and no grade')
        for i in row.get('issues', []):
            if i['root_defect_id'] in roots: raise ValueError('Same root charged twice')
            roots.add(i['root_defect_id'])
            if i['primary_rule'] != row['rule_id']: raise ValueError('Wrong defect owner')
        rows[key] = row
    for rid, page in expected: rows.setdefault((rid, page), unknown(rid, page, 'Expected page/rule not assessed'))
    return [rows[k] for k in expected]

def aggregate(assessments, rules, weights=None, manifest=None, inventories=None, context=None):
    context = context or {}; rows = canonical_rows(assessments, rules, manifest, context)
    levels = {}; page_scores = []
    for level in LABELS:
        metrics = []
        for r in [r for r in rules if r['level'] == level]:
            items = [a for a in rows if a['rule_id'] == r['id']]
            applicable = [a for a in items if a['status'] != 'NOT_APPLICABLE']; graded = [a for a in applicable if a['rating'] is not None]
            metrics.append({'rule_id': r['id'], 'name': r['name'], 'weight': r['weight'], 'applicable': bool(applicable),
                            'mean_rating': sum(a['rating'] for a in graded) / len(graded) if graded else None,
                            'coverage': len(graded) / len(applicable) if applicable else 1,
                            'counts': dict(collections.Counter(a['status'] for a in items))})
        app = [r for r in metrics if r['applicable']]; graded = [r for r in app if r['mean_rating'] is not None]
        den = sum(r['weight'] for r in graded); full = sum(r['weight'] for r in app)
        observed = round(25 * sum(r['weight'] * r['mean_rating'] for r in graded) / den, 1) if den else None
        coverage = sum(r['weight'] * r['coverage'] for r in app) / full if full else 1
        complete = observed if math.isclose(coverage, 1) else None
        if not context.get('page_mapping_reviewed') and manifest.get('page_mapping_status') != 'EXPLICIT_SOURCE_PAGE_MAP': complete = None
        levels[level] = {'observed_score': observed, 'complete_score': complete, 'coverage': round(coverage, 4), 'rules': metrics}
    for page in manifest['pages']:
        row = {'page': page['page']}
        for level in ['object', 'slide']:
            ids = {r['id'] for r in rules if r['level'] == level}; items = [a for a in rows if a['page'] == page['page'] and a['rule_id'] in ids and a['status'] != 'NOT_APPLICABLE']; graded = [a for a in items if a['rating'] is not None]
            row[level] = {'observed_score': round(25 * sum(a['rating'] for a in graded) / len(graded), 1) if graded else None, 'coverage': len(graded) / len(items) if items else 1}
        page_scores.append(row)
    total = conditional = None
    if weights:
        if len(weights) != 3 or not all(isinstance(w, (int, float)) and math.isfinite(w) and w > 0 for w in weights): raise ValueError('Three finite positive weights required')
        vals = [levels[x]['complete_score'] for x in LABELS]; obs = [levels[x]['observed_score'] for x in LABELS]
        if all(v is not None for v in vals): total = round(sum(v*w for v,w in zip(vals,weights))/sum(weights),1)
        if all(v is not None for v in obs): conditional = round(sum(v*w for v,w in zip(obs,weights))/sum(weights),1)
    return {'levels': levels, 'pages': page_scores, 'overall_complete': total, 'overall_observed_conditional': conditional, 'layer_weights': weights,
            'issues': [i for a in rows for i in a.get('issues', [])], 'warning': 'PROVISIONAL_NOT_CALIBRATED; coverage is valid judgment coverage, not exhaustive factual truth'}

def refresh(result, rules):
    result['assessments'] = canonical_rows(result['assessments'], rules, result['manifest'], result.get('context', {}))
    result['scores'] = aggregate(result['assessments'], rules, result.get('layer_weights'), result['manifest'], context=result.get('context', {}))
    # Final findings never come from a stale model summary.
    result['final_summary'] = {'assessed_pages': sorted({a['page'] for a in result['assessments'] if a['page'] is not None and a['rating'] is not None}),
                               'open_issues': [{'id': i['id'], 'problem': i['problem'], 'affected_pages': i['affected_pages']} for i in result['scores']['issues']],
                               'unknown_checks': sum(a['status'] == 'UNCERTAIN' for a in result['assessments']),
                               'score_scope': 'Observation only unless complete_score is present; not human calibrated'}
    return result

def image_data(path):
    f = Path(path)
    return 'data:' + (mimetypes.guess_type(f.name)[0] or 'image/png') + ';base64,' + base64.b64encode(f.read_bytes()).decode()

def render(result, out):
    # Recompute before every render, including after review and manual imports.
    rules = json.loads((Path(__file__).resolve().parents[1]/'references/rubric.json').read_text())['rules']; refresh(result, rules)
    h = html.escape; s = result['scores']; fmt = lambda x: '未形成' if x is None else str(x)
    chunks = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PPT评测 · 页面视觉版</title><style>body{font:15px/1.75 system-ui,"PingFang SC",sans-serif;max-width:1180px;margin:36px auto;padding:0 22px;background:#f5f5f0;color:#193b32}table{width:100%;border-collapse:collapse}td,th{padding:12px;text-align:left;border-bottom:1px solid #cbd5c9;vertical-align:top}th{background:#e2eadf}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.75 monospace;max-height:500px;overflow:auto}img{width:100%;height:auto}.warn{padding:18px;background:#fff0cc}.page{margin-top:36px;border-top:2px solid #436551;padding-top:16px}.two{display:grid;grid-template-columns:1.2fr 1fr;gap:22px}article{padding:12px;border-left:3px solid #b08226;background:white;margin:12px 0}summary{cursor:pointer}small{color:#597362}@media(max-width:800px){.two{display:block}}</style><h1>PPT评测 · 页面视觉版</h1><p class="warn">'+h(result.get('rubric_version', ''))+' · 研究版，未经人工标定。检查单位是整页图片，不要求原生对象ID。分数与判项覆盖率一起读；覆盖率不代表全部事实已核验。</p>']
    chunks.append('<table><tr><th>视角</th><th>观察分 /100</th><th>完整分 /100</th><th>判项覆盖率</th></tr>')
    for lev, val in s['levels'].items(): chunks.append(f'<tr><td>{LABELS[lev]}</td><td>{fmt(val["observed_score"])}</td><td>{fmt(val["complete_score"])}</td><td>{val["coverage"]:.1%}</td></tr>')
    chunks.append('</table><p>完整总分：'+fmt(s['overall_complete'])+'。默认分别报告三个视角，不默认合并或跨产品排名。</p><h2>最终结论与修改清单</h2>')
    final = result['final_summary']; chunks.append('<p>已取得有效判项的页面：'+h(str(final['assessed_pages']))+'；未知判项 '+str(final['unknown_checks'])+' 项。复核状态：'+h(result.get('review', {}).get('status', '未复核'))+'。</p>')
    if not s['issues']: chunks.append('<p>当前有效结果未保留确定缺陷；请结合未知项与覆盖率判断，不能据此推断全部通过。</p>')
    for i in s['issues']: chunks.append('<article><b>'+h(i['severity']+' · '+i['primary_rule'])+'</b><p>'+h(i['problem'])+'</p><p>位置：'+h(i['location'])+'；关联页：'+h(str(i['affected_pages']))+'</p><p>修改：'+h(i['repair'])+'</p></article>')
    for page in result['manifest']['pages']:
        n = page['page']; rows = [a for a in result['assessments'] if a['page'] == n]; issues = [i for i in s['issues'] if n in i['affected_pages']]
        pending = any(a['status'] == 'UNCERTAIN' for a in rows)
        action = '需要重画/重构' if any(i['requires_redraw'] for i in issues) else '局部修改后复核' if issues else '待核验' if pending else '暂可保留（已检查范围）'
        chunks.append('<section class="page"><h2>第'+str(n)+'页 · '+action+'</h2><div class="two">')
        chunks.append('<img loading="lazy" src="'+image_data(page['image'])+'" alt="第'+str(n)+'页原图"><div>')
        for i in issues: chunks.append('<p><b>'+h(i['primary_rule'])+'</b> '+h(i['problem'])+'<br>修改：'+h(i['repair'])+'</p>')
        chunks.append('<details><summary>逐项分数、位置、证据和未知原因</summary><pre>'+h(json.dumps(rows,ensure_ascii=False,indent=2))+'</pre></details></div></div></section>')
    chunks.append('<h2>24维分项</h2>')
    for lev, val in s['levels'].items():
        chunks.append('<details><summary>'+LABELS[lev]+'</summary><table><tr><th>维度</th><th>均分0—4</th><th>覆盖率</th><th>状态分布</th></tr>')
        for r in val['rules']: chunks.append('<tr><td>'+h(r['rule_id']+' '+r['name'])+'</td><td>'+fmt(r['mean_rating'])+'</td><td>'+f'{r["coverage"]:.1%}'+'</td><td>'+h(str(r['counts']))+'</td></tr>')
        chunks.append('</table></details>')
    for name, key in [('复核与合并记录','review'), ('模型、耗时、usage与费用','process'), ('输入与场景边界','context'), ('原始模型意见（历史，非最终结论）','model_history'), ('校验隔离与待核验候选','validation')]:
        chunks.append('<details><summary>'+name+'</summary><pre>'+h(json.dumps(result.get(key, {}), ensure_ascii=False, indent=2))+'</pre></details>')
    Path(out).write_text(''.join(chunks)+'</html>')

if __name__ == '__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('result'); ap.add_argument('--out',required=True); a=ap.parse_args(); d=json.loads(Path(a.result).read_text()); render(d,a.out); print(a.out)
