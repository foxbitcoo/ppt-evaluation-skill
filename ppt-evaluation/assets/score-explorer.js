/* Local score exploration only: no requests, storage or automatic regrading. */
(function () {
  function calculate(data, ruleWeights, layerWeights) {
    const round1 = x => Math.round((x+Number.EPSILON)*10)/10;
    const finite = x => typeof x === 'number' && Number.isFinite(x) && x >= 0;
    if (!Object.values(ruleWeights).every(finite) || !Object.values(layerWeights).every(finite)) throw Error('权重须为不小于0的数字');
    if (!Object.keys(data.layers).every(k=>finite(layerWeights[k])) || !Object.values(data.layers).flatMap(l=>l.rules).every(r=>finite(ruleWeights[r.rule_id]))) throw Error('缺少必要权重');
    const layers = {};
    for (const [level, source] of Object.entries(data.layers)) {
      const app = source.rules.filter(r => r.applicable);
      const active = app.filter(r => ruleWeights[r.rule_id] > 0);
      const rated = active.filter(r => r.mean_rating !== null);
      const den = rated.reduce((n,r) => n + ruleWeights[r.rule_id], 0);
      const full = active.reduce((n,r) => n + ruleWeights[r.rule_id], 0);
      layers[level] = {score: den ? round1(25 * rated.reduce((n,r) => n + ruleWeights[r.rule_id]*r.mean_rating,0)/den) : null,
        coverage: full ? active.reduce((n,r) => n + ruleWeights[r.rule_id]*r.coverage,0)/full : null,
        excluded: app.length-active.length};
    }
    const selected = Object.keys(layers).filter(l => layerWeights[l] > 0);
    if (!selected.length) throw Error('至少保留一个视角的权重');
    const den = selected.reduce((n,l) => n+layerWeights[l],0);
    const allScored = selected.every(l => layers[l].score !== null);
    const score = allScored ? selected.reduce((n,l) => n+layerWeights[l]*layers[l].score,0)/den : null;
    const coverage = selected.every(l => layers[l].coverage !== null) ? selected.reduce((n,l) => n+layerWeights[l]*layers[l].coverage,0)/den : null;
    const excluded = Object.values(layers).reduce((n,l) => n+l.excluded,0)+(3-selected.length);
    // A reduced scope must never turn an incomplete baseline into a complete full-deck score.
    const baselineComplete = Object.values(data.layers).every(l => l.complete_score !== null);
    const pages = {};
    for (const p of (data.pages || [])) {
      pages[p.page] = {};
      for (const level of ['object','slide']) {
        const active=p.rows.filter(r=>r.level===level && r.status!=='NOT_APPLICABLE' && ruleWeights[r.rule_id]>0);
        const graded=active.filter(r=>r.rating!==null);
        const den=graded.reduce((n,r)=>n+ruleWeights[r.rule_id],0);
        pages[p.page][level]=den ? 25*graded.reduce((n,r)=>n+ruleWeights[r.rule_id]*r.rating,0)/den : null;
      }
    }
    return {layers, score, coverage, excluded, pages, complete: baselineComplete && !excluded && data.mappingVerified ? score : null};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {calculate};
  if (typeof document === 'undefined') return;
  const node = document.getElementById('score-data');
  if (!node) return;
  const data = JSON.parse(node.textContent);
  const ruleNodes = [...document.querySelectorAll('[data-rule-weight]')];
  const layerNodes = [...document.querySelectorAll('[data-layer-weight]')];
  const read = (nodes, key) => Object.fromEntries(nodes.map(n => [n.dataset[key], n.value.trim() === '' ? NaN : Number(n.value)]));
  const text = (selector, value) => document.querySelectorAll(selector).forEach(n => n.textContent = value);
  const fmt = n => n === null ? '—' : n.toFixed(1);
  let current;
  function update() {
    try {
      const rules=read(ruleNodes,'ruleWeight'), layers=read(layerNodes,'layerWeight');
      current=calculate(data,rules,layers);
      text('[data-total]',fmt(current.score)); text('[data-total-coverage]',current.coverage===null?'—':(current.coverage*100).toFixed(1)+'%');
      text('[data-complete]',current.complete===null?'完整总分尚未形成':('完整总分 '+fmt(current.complete)));
      for (const [level,s] of Object.entries(current.layers)) {
        text('[data-layer-score="'+level+'"]',fmt(s.score));
        text('[data-layer-coverage="'+level+'"]',s.coverage===null?'无有效权重':(s.coverage*100).toFixed(1)+'%');
      }
      const den=Object.values(layers).reduce((n,w)=>n+w,0);
      layerNodes.forEach(n => text('[data-layer-share="'+n.dataset.layerWeight+'"]',(layers[n.dataset.layerWeight]/den*100).toFixed(1)+'%'));
      text('[data-weight-note]',current.excluded?'当前自定义范围排除了 '+current.excluded+' 个视角或适用维度；仍不是全范围完整分。':'按当前权重，仅汇总已评分项目；未知项不补分，仍计入覆盖率。');
      for (const [page,scores] of Object.entries(current.pages)) for (const [level,score] of Object.entries(scores)) text('[data-page-score="'+page+'-'+level+'"]',fmt(score));
      document.querySelectorAll('[data-excluded-rule]').forEach(n=>n.textContent=rules[n.dataset.excludedRule]===0?'当前权重为0：问题保留，不参与试算。':'');
      text('[data-weight-error]','');
    } catch(e) {
      current=null; text('[data-total]','—');text('[data-total-coverage]','—');text('[data-complete]','配置无效');
      text('[data-page-score]','—');text('[data-layer-score]','—');text('[data-layer-coverage]','—');text('[data-layer-share]','—');
      text('[data-weight-error]',e.message);
    }
  }
  [...ruleNodes,...layerNodes].forEach(n => n.addEventListener('input',update));
  document.getElementById('reset-weights').addEventListener('click',()=>{[...ruleNodes,...layerNodes].forEach(n=>n.value=n.defaultValue);update();});
  const dialog=document.getElementById('page-lightbox');
  document.querySelectorAll('[data-page-zoom]').forEach(b=>b.addEventListener('click',()=>{const img=b.querySelector('img');dialog.querySelector('img').src=img.src;dialog.querySelector('img').alt=img.alt;dialog.querySelector('p').textContent=img.alt;dialog.showModal();}));
  dialog.querySelector('button').addEventListener('click',()=>dialog.close());
  dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close();});
  update();
})();
