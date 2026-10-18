"""Validate and render page-bound explanations of comparative scores."""
import html, math, hashlib, shutil
from pathlib import Path
from reader_report import _image

LEVELS = {'object':'页内细节','slide':'单页表达','deck':'整稿'}

def total_score(result):
    levels = result['scores']['levels']; vals = [levels[k]['observed_score'] for k in LEVELS]
    if result.get('delivery',{}).get('evaluation_failures') or any(v is None for v in vals): return None
    weights = result.get('layer_weights') or [1,1,1]
    return round(sum(v*w for v,w in zip(vals,weights))/sum(weights),1)

def validate_insights(insights, entries):
    decks = {e['id']:e for e in entries}
    expected = {k:total_score(e['result']) for k,e in decks.items()}
    if {x['deck_id']:x['score_100'] for x in insights['headline']['score_lines']} != expected:
        raise ValueError('Insight scores differ from final scoring results')
    valid_winners = [] if any(v is None for v in expected.values()) else [k for k,v in expected.items() if v==max(expected.values())]
    if sorted(insights['headline']['winner_ids']) != sorted(valid_winners): raise ValueError('Insight winner differs from scores')
    if [s['level'] for s in insights['level_sections']] != list(LEVELS): raise ValueError('Three ordered levels required')
    def check(item):
        refs = item.get('refs', [])
        if not refs: raise ValueError('Narrative finding needs page-bound evidence')
        ref_decks = set()
        for ref in refs:
            ident = ref['deck_id']; ref_decks.add(ident)
            if ident not in decks: raise ValueError('Unknown deck in image reference')
            pages = {p['page'] for p in decks[ident]['result']['manifest']['pages']}
            if not ref['page_numbers'] or set(ref['page_numbers'])-pages: raise ValueError('Narrative references a missing page')
            if ref.get('scope')=='deck' and set(ref['page_numbers'])!=pages: raise ValueError('Deck evidence must show the full ordered deck')
        evidence = {x['id']:ident for ident,e in decks.items() for x in e['result'].get('insight_evidence',[])}
        if not item.get('evidence_ids') or any(x not in evidence for x in item['evidence_ids']): raise ValueError('Unknown or absent narrative evidence ID')
        if any(evidence[x] not in ref_decks for x in item['evidence_ids']): raise ValueError('Evidence and pictured deck disagree')
    for section in insights['level_sections']:
        if {d['deck_id'] for d in section['decks']} != set(decks): raise ValueError('Missing deck analysis')
        for d in section['decks']:
            if d['score_100'] != decks[d['deck_id']]['result']['scores']['levels'][section['level']]['observed_score']: raise ValueError('Level score mismatch')
            for finding in d['strengths']+d['deductions']: check(finding)
        for pair in section['pairwise']:
            if {pair['left_id'],pair['right_id']}-set(decks): raise ValueError('Unknown comparison deck')
            for finding in pair['left_advantages']+pair['right_advantages']+pair['shared_gaps']:
                check(finding)
                if {r['deck_id'] for r in finding['refs']} != {pair['left_id'],pair['right_id']}: raise ValueError('Relative advantage must reference both decks')
    for action in insights['iteration_plan']: check(action)
    return insights

def render_insights(insights, entries, asset_directory=None):
    validate_insights(insights,entries); h=html.escape; decks={e['id']:e for e in entries}
    def asset(p):
        if asset_directory is None:return _image(p['image'])
        folder=Path(asset_directory);folder.mkdir(parents=True,exist_ok=True)
        raw=Path(p['image']).read_bytes();name=hashlib.sha256(raw).hexdigest()+Path(p['image']).suffix
        dest=folder/name
        if not dest.exists():shutil.copyfile(p['image'],dest)
        return folder.name+'/'+name
    images={k:{p['page']:asset(p) for p in e['result']['manifest']['pages']} for k,e in decks.items()}
    def visual(ref):
        ident=ref['deck_id']; nums=ref['page_numbers']; label=decks[ident]['label']
        if ref.get('scope')=='deck':
            return '<figure class="insight-visual"><div class="sheet">'+''.join('<figure><button type="button" data-insight-zoom><img src="'+images[ident][p]+'" alt="'+h(label)+'第'+str(p)+'页"></button><figcaption>第'+str(p)+'页</figcaption></figure>' for p in nums)+'</div><figcaption>'+h(label)+' · 整稿原序拼图</figcaption></figure>'
        return '<figure class="insight-visual">'+''.join('<button type="button" data-insight-zoom><img loading="lazy" src="'+images[ident][p]+'" alt="'+h(label)+'第'+str(p)+'页"></button><figcaption>'+h(label)+' · 第'+str(p)+'页</figcaption>' for p in nums)+'</figure>'
    def finding(item,label):
        refs=item['refs']; return '<div class="finding-row"><div class="finding-images">'+''.join(visual(r) for r in refs)+'</div><div><small class="finding-label">'+label+'</small><p>'+h(item['text'])+'</p></div></div>'
    parts=['<section class="section insight-sections" id="insights"><h2>分数背后的判断与改法</h2>']
    for section in insights['level_sections']:
        lev=section['level'];parts.append('<section class="insight-level" id="insight-'+lev+'"><h2>'+LEVELS[lev]+'</h2>')
        for pair in section['pairwise']:
            for item in pair['left_advantages']:parts.append(finding(item,h(decks[pair['left_id']]['label'])+'相对更好'))
            for item in pair['right_advantages']:parts.append(finding(item,h(decks[pair['right_id']]['label'])+'相对更好'))
            for item in pair['shared_gaps']:parts.append(finding(item,'共同改进点'))
        for profile in section['decks']:
            ident=profile['deck_id'];result=decks[ident]['result'];parts.append('<article class="insight-profile"><h3>'+h(decks[ident]['label'])+' <span data-insight-score="'+str(list(decks).index(ident))+'-'+lev+'">'+f'{profile["score_100"]:.1f}'+'</span>分</h3><p class="insight-summary">'+h(profile['summary'])+'</p>')
            if lev=='deck':
                nums=list(images[ident]);parts.append('<div class="finding-row">'+visual({'deck_id':ident,'page_numbers':nums,'scope':'deck'})+'<div>')
                for label,items in [('好在哪里',profile['strengths']),('差距与改法',profile['deductions'])]:
                    for item in items:parts.append('<div class="insight-text"><small class="finding-label">'+label+'</small><p>'+h(item['text'])+'</p></div>')
                parts.append('</div></div>')
            else:
                for item in profile['strengths']:parts.append(finding(item,'好在哪里'))
                for item in profile['deductions']:parts.append(finding(item,'差距与改法'))
            metrics=[r for r in result['scores']['levels'][lev]['rules'] if r['applicable'] and r['mean_rating'] is not None];den=sum(r['weight'] for r in metrics)
            parts.append('<details class="score-bridge"><summary>从理想100分到当前分数：查看评分构成</summary><p>每条规则先跨页平均，再按权重汇总。以下是各维度与满分的差距贡献，不是按问题条数重复扣分。</p><table><tr><th>维度</th><th>得分 /100</th><th>与满分差距贡献</th></tr>')
            for r in metrics:
                score=r['mean_rating']*25;loss=(100-score)*r['weight']/den
                parts.append('<tr><td>'+h(r['name'])+'</td><td>'+f'{score:.1f}'+'</td><td data-rule-loss="'+str(list(decks).index(ident))+'-'+lev+'-'+r['rule_id']+'">'+f'{loss:.2f}'+'</td></tr>')
            parts.append('</table></details></article>')
        parts.append('</section>')
    parts.append('</section><section class="section"><h2>下一版先改什么</h2>')
    for action in insights['iteration_plan']:
        parts.append('<article class="iteration-action">'+finding({'refs':action['refs'],'text':action['action']},'优先级 '+str(action['priority']))+'<p><b>改后检查：</b>'+h(action['acceptance'])+'</p><p>'+h(action['expected_benefit'])+'</p></article>')
    parts.append('</section><dialog id="insight-lightbox"><img alt=""><div class="controls"><p></p><button type="button" class="control">关闭</button></div></dialog>')
    return ''.join(parts)
