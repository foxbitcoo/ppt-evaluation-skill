"""Evidence-first reader report; raw diagnostics are written to a separate file."""
import base64, collections, html, json, mimetypes
from pathlib import Path
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
LABELS={'object':'页内细节','slide':'单页表达','deck':'整稿'}
H=html.escape
def B(value):
    return H(str(value).replace('事实包','核对资料').replace('Query','制作要求'))

def _image(path):
    p=Path(path);return 'data:'+(mimetypes.guess_type(p.name)[0]or'image/png')+';base64,'+base64.b64encode(p.read_bytes()).decode()

def _rating(row):
    if row['status']=='NOT_APPLICABLE':return '不适用'
    if row['rating']is None:return '待核验'
    return str(row['rating'])+'/4'

def _positive(row):
    # Reviewed BAD/UNKNOWN narratives may still mention deleted defects. Never reuse them.
    evidence=[e for e in row.get('evidence',[]) if isinstance(e,str)and not any(k in e for k in ['主扣','已在D','不重复扣','fact_id','source_id'])]
    return '；'.join(evidence[:2])if evidence else '已检查范围内基本有效。'

def _debug(result,path):
    body=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PPT评测调试资料</title><style>body{font:14px/1.7 monospace;max-width:1100px;margin:35px auto;padding:20px}pre{white-space:pre-wrap;overflow-wrap:anywhere}summary{cursor:pointer}</style><h1>调试资料</h1><p>包括原始历史意见与复核记录；历史文字不是最终结论。</p>']
    for title,key in [('输入清单','manifest'),('场景与来源','context'),('最终判项','assessments'),('评分数据','scores'),('复核','review'),('复核历史','review_history'),('模型历史意见','model_history'),('校验与候选','validation'),('调用与耗时','process')]:
        body+=['<details><summary>'+title+'</summary><pre>'+H(json.dumps(result.get(key),ensure_ascii=False,indent=2))+'</pre></details>']
    extra=result.get('report_metadata',{}).get('debug_url')
    if extra and urlsplit(str(extra)).scheme.lower()in {'','http','https'}:body.append('<p><a href="'+H(str(extra),quote=True)+'">完整白盒运行记录</a></p>')
    Path(path).write_text(''.join(body)+'</html>')

def render_reader(result,out,rules):
    out=Path(out);debug=out.with_name(out.stem+'-debug.html');_debug(result,debug)
    s=result['scores'];rows=result['assessments'];meta=result.get('report_metadata',{});rule_by={r['id']:r for r in rules};by={(a['rule_id'],a['page']):a for a in rows};issues=s['issues'];pages=result['manifest']['pages']
    title=str(meta.get('title','PPT质量评测'));platform=str(meta.get('platform',''));basis=str(meta.get('review_label','本轮评测结果 · 未经人工标定'))
    images={p['page']:_image(p['image'])for p in pages}
    affected={p['page']:[i for i in issues if p['page']in i['affected_pages']]for p in pages};problem_pages=[p for p in pages if affected[p['page']]]
    default_layers=dict(zip(LABELS,result.get('layer_weights')or[1,1,1]))
    data={'rubric_version':result.get('rubric_version',''),'layers':s['levels'],'mappingVerified':bool(result.get('context',{}).get('page_mapping_reviewed')or result['manifest'].get('page_mapping_status')=='EXPLICIT_SOURCE_PAGE_MAP'),
          'pages':[{'page':p['page'],'rows':[{'rule_id':a['rule_id'],'level':rule_by[a['rule_id']]['level'],'rating':a['rating'],'status':a['status']}for a in rows if a['page']==p['page']]}for p in pages]}
    chunks=['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+H(title+' · '+platform)+'</title><style>'+(ROOT/'assets/reader-report.css').read_text()+'</style><main><header><p class="eyebrow">PRESENTATION REVIEW</p><h1>'+H(title)+'</h1><p class="subtitle">'+H(platform+' · '+str(len(pages))+'页 · '+basis)+'</p><nav class="nav"><a href="#overview">评分总览</a><a href="#deck">整稿逻辑</a><a href="#pages">逐页修改</a><a href="#weights">评分与权重</a></nav></header>']
    chunks.append('<section id="overview"><div class="overview"><div class="score-box total"><h2>综合观察分 · 权重试算</h2><strong class="number"><span data-total>—</span><span class="unit"> /100</span></strong><p>当前范围覆盖 <span data-total-coverage>—</span></p></div>')
    for lev,title_ in LABELS.items():chunks.append('<div class="score-box"><h2>'+title_+'</h2><strong class="number"><span data-layer-score="'+lev+'">—</span><span class="unit"> /100</span></strong><p>已评覆盖 <span data-layer-coverage="'+lev+'">—</span> · 权重 <span data-layer-share="'+lev+'">—</span></p></div>')
    chunks.append('</div><p class="scope"><span data-complete>完整总分尚未形成</span>；部分内容待核验。调权只改变汇总，不会重新判断问题。</p></section>')
    # One composed sheet, with page order always visible.
    chunks.append('<section class="section" id="deck"><h2>整稿 · 叙事与一致性</h2><div class="spread"><figure class="visual"><div class="sheet" aria-label="整稿页序拼图">')
    for p in pages:
        n=p['page'];chunks.append('<figure><button type="button" data-page-zoom aria-label="放大第'+str(n)+'页"><img src="'+images[n]+'" alt="第'+str(n)+'页原图"></button><figcaption>第'+str(n)+'页</figcaption></figure>')
    for _ in range((-len(pages))%3):chunks.append('<div class="empty">'+str(len(pages))+'页 · 按原顺序</div>')
    chunks.append('</div><figcaption>全稿按原顺序排列；点任一子图可放大。</figcaption></figure><div class="right">')
    if meta.get('storyline'):chunks.append('<div class="positive"><h3>当前主线</h3><p>'+H(str(meta['storyline']))+'</p></div>')
    chunks.append('<h3>有效之处</h3>')
    positives=[a for a in rows if a['page']is None and a['status']=='GOOD']
    if not positives:chunks.append('<p class="muted">当前结果没有可确定的正向整稿评价。</p>')
    for a in positives:
        chunks.append('<div class="positive"><small>'+H(rule_by[a['rule_id']]['name'])+' · '+_rating(a)+'</small><p>'+H(_positive(a))+'</p></div>')
    chunks.append('<h3>需要调整</h3>')
    deck_groups=collections.defaultdict(list)
    for i in issues:
        if rule_by[i['primary_rule']]['level']=='deck':deck_groups[i['primary_rule']].append(i)
    if not deck_groups:chunks.append('<p class="muted">当前未保留整稿修改项；不代表未核验内容已通过。</p>')
    for rid,group in deck_groups.items():
        row=by[(rid,None)];chunks.append('<div class="narrative-group"><div class="problem-title"><b>'+H(rule_by[rid]['name'])+'</b><span class="rating">'+_rating(row)+'</span></div>')
        for i in group[:2]:chunks.append('<p>'+B(i['problem'])+'</p>')
        if len(group)>2:chunks.append('<p class="muted">另有'+str(len(group)-2)+'项，见相应页面的修改建议。</p>')
        chunks.append('</div>')
    unknown_deck=[rule_by[a['rule_id']]['name']for a in rows if a['page']is None and a['status']=='UNCERTAIN']
    if unknown_deck:chunks.append('<p class="scope">待核验：'+H('、'.join(unknown_deck))+'。</p>')
    chunks.append('</div></div></section><section class="section" id="pages"><h2>逐页 · 只看需要修改的页面</h2><p class="scope">'+str(len(problem_pages))+'页有保留修改项；其余'+str(len(pages)-len(problem_pages))+'页不展开。未展开不等于全部核验通过。</p><p class="score-rule-note">每页每维度只记一次0—4评分，多条问题不逐条累加扣分；标为“整稿关联”的项目只在整稿计分一次。</p>')
    keep_notes={d['issue_id']:d['reason']for d in result.get('review',{}).get('decisions',[])if d.get('action')=='keep'}
    for p in problem_pages:
        n=p['page'];grouped=collections.defaultdict(list)
        for i in affected[n]:grouped[i['primary_rule']].append(i)
        redraw=any(i['requires_redraw']for i in affected[n]);chunks.append('<article class="page-detail" id="page-'+str(n)+'"><div class="page-head"><h2>第'+str(n)+'页</h2><span>'+('需要重画或重构'if redraw else'局部修改后复核')+'</span></div><div class="spread"><figure class="visual"><button type="button" class="page-image" data-page-zoom aria-label="放大第'+str(n)+'页原图"><img loading="lazy" src="'+images[n]+'" alt="第'+str(n)+'页原图"></button><figcaption>原始页面 · 点击放大</figcaption></figure><div class="right"><p class="page-summary">页内细节 <b data-page-score="'+str(n)+'-object">—</b> /100　单页表达 <b data-page-score="'+str(n)+'-slide">—</b> /100（均为已评范围）</p>')
        for rid,group in grouped.items():
            is_deck=rule_by[rid]['level']=='deck';row=by[(rid,None if is_deck else n)]
            chunks.append('<div class="issue-group"><div class="problem-title"><h3>'+H(rule_by[rid]['name'])+'</h3><span class="rating">'+_rating(row)+'</span></div>')
            chunks.append('<p class="scope" data-excluded-rule="'+rid+'"></p>')
            if is_deck:chunks.append('<p class="scope">整稿关联 · 全稿只计一次，此处展示问题位置。</p>')
            for i in group:
                chunks.append('<div class="issue"><p class="where">'+B(i['location'])+'</p><p>'+B(i['problem'])+'</p><p class="fix"><b>怎么改：</b>'+B(i['repair'])+'</p>')
                if i['id']in keep_notes:chunks.append('<p class="review-note">复核补充：'+H(keep_notes[i['id']])+'</p>')
                chunks.append('</div>')
            chunks.append('</div>')
        chunks.append('<details><summary>本页各项评分</summary><div class="table-wrap"><table><tr><th>维度</th><th>评分 /4</th></tr>')
        for a in rows:
            if a['page']==n:chunks.append('<tr><td>'+H(rule_by[a['rule_id']]['name'])+'</td><td>'+_rating(a)+'</td></tr>')
        chunks.append('</table></div></details></div></div></article>')
    if not problem_pages:chunks.append('<p>当前未保留需要修改的页面；请结合待核验项阅读。</p>')
    chunks.append('</section><section class="section" id="weights"><details class="weights"><summary>24项评分与可调权重</summary><p class="formula">单项0—4分 ×25 → 100分制；先跨页平均同一维度，再按维度权重形成三个视角分，最后按三个视角权重合成综合观察分。</p><div class="layer-controls">')
    for lev,label in LABELS.items():chunks.append('<label>'+label+'<input aria-label="'+label+'权重" type="number" min="0" max="100" step="0.1" data-layer-weight="'+lev+'" value="'+str(default_layers[lev])+'"></label>')
    chunks.append('</div><p class="scope">默认三视角等权，层内各维度等权；这是试算配置，不是行业标准。权重为0表示明确排除该项，页面会标明范围变化。</p>')
    for lev,title_ in LABELS.items():
        chunks.append('<h3>'+title_+'</h3><div class="table-wrap"><table><tr><th>维度</th><th>均分 /4</th><th>折算 /100</th><th>已评范围</th><th>相对权重</th></tr>')
        for r in s['levels'][lev]['rules']:
            mean=r['mean_rating'];formatted='待核验'if r['applicable']else'不适用';score='—'if mean is None else f'{mean*25:.1f}';coverage=f'{r["coverage"]:.1%}'if r['applicable']else'不适用'
            chunks.append('<tr><td>'+H(r['name'])+'</td><td>'+(f'{mean:.2f}'if mean is not None else formatted)+'</td><td>'+score+'</td><td>'+coverage+'</td><td><input type="number" min="0" max="100" step="0.1" aria-label="'+H(r['name'])+'权重" data-rule-weight="'+r['rule_id']+'" value="'+str(r['weight'])+'"></td></tr>')
        chunks.append('</table></div>')
    chunks.append('<div class="controls"><button class="control" id="reset-weights">恢复默认</button></div><p class="scope" data-weight-note></p><p class="error" data-weight-error role="status"></p></details></section><footer class="footer"><p>页面与评分来自同一结果版本；权重调整仅在本页试算，不改原评分、不调用模型。未经人工标定，不以不完整观察分直接排名。</p><a href="'+H(debug.name)+'">调试资料</a></footer></main><dialog id="page-lightbox"><img alt=""><div class="controls"><p></p><button class="control" type="button">关闭</button></div></dialog>')
    chunks.append('<script type="application/json" id="score-data">'+json.dumps(data,ensure_ascii=False).replace('<','\\u003c')+'</script><script>'+(ROOT/'assets/score-explorer.js').read_text()+'</script></html>')
    out.write_text(''.join(chunks));return out
